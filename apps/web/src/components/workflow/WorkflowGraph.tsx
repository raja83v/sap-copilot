import { useState, useEffect } from "react";
import type { WorkflowGraphNode, WorkflowGraphEdge } from "@sap-copilot/shared";
import { getWorkflowGraph } from "@/lib/gateway";

interface WorkflowGraphProps {
  workflowType: string;
  currentNode?: string | null;
  completedNodes?: string[];
  failedNodes?: string[];
}

interface LayoutNode extends WorkflowGraphNode {
  x: number;
  y: number;
}

const NODE_WIDTH = 120;
const NODE_HEIGHT = 50;
const H_GAP = 40;
const V_GAP = 30;

const TYPE_COLORS: Record<string, string> = {
  agent: "#3b82f6",
  approval: "#f59e0b",
  gate: "#8b5cf6",
  internal: "#6b7280",
};

/**
 * Simple left-to-right layout algorithm.
 * Assigns nodes to columns based on topological order.
 */
function layoutNodes(
  nodes: WorkflowGraphNode[],
  edges: WorkflowGraphEdge[],
  entry: string,
): LayoutNode[] {
  // Build adjacency
  const adj: Record<string, string[]> = {};
  for (const n of nodes) adj[n.id] = [];
  for (const e of edges) {
    if (e.to !== "END" && adj[e.from]) {
      adj[e.from].push(e.to);
    }
  }

  // BFS to assign columns
  const col: Record<string, number> = {};
  const visited = new Set<string>();
  const queue: Array<{ id: string; depth: number }> = [{ id: entry, depth: 0 }];
  visited.add(entry);

  while (queue.length > 0) {
    const { id, depth } = queue.shift()!;
    col[id] = Math.max(col[id] ?? 0, depth);
    for (const next of adj[id] ?? []) {
      if (!visited.has(next)) {
        visited.add(next);
        queue.push({ id: next, depth: depth + 1 });
      }
    }
  }

  // Assign unvisited nodes
  for (const n of nodes) {
    if (!(n.id in col)) col[n.id] = 0;
  }

  // Group by column
  const columns: Record<number, string[]> = {};
  for (const [id, c] of Object.entries(col)) {
    if (!columns[c]) columns[c] = [];
    columns[c].push(id);
  }

  // Position nodes
  const nodeMap = new Map(nodes.map((n) => [n.id, n]));
  const layoutNodes: LayoutNode[] = [];

  for (const [colStr, ids] of Object.entries(columns)) {
    const c = parseInt(colStr);
    ids.forEach((id, row) => {
      const node = nodeMap.get(id);
      if (!node) return;
      layoutNodes.push({
        ...node,
        x: c * (NODE_WIDTH + H_GAP) + 20,
        y: row * (NODE_HEIGHT + V_GAP) + 20,
      });
    });
  }

  return layoutNodes;
}

export function WorkflowGraph({
  workflowType,
  currentNode,
  completedNodes = [],
  failedNodes = [],
}: WorkflowGraphProps) {
  const [graphData, setGraphData] = useState<{
    nodes: WorkflowGraphNode[];
    edges: WorkflowGraphEdge[];
    entry: string;
  } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const data = await getWorkflowGraph(workflowType);
        setGraphData(data);
      } catch (e) {
        console.error("Failed to load graph:", e);
      } finally {
        setLoading(false);
      }
    })();
  }, [workflowType]);

  if (loading) {
    return (
      <div style={{ padding: 20, textAlign: "center", color: "var(--sapContent_LabelColor)", fontSize: 13 }}>
        Loading graph...
      </div>
    );
  }

  if (!graphData) {
    return (
      <div style={{ padding: 20, textAlign: "center", color: "var(--sapContent_LabelColor)", fontSize: 13 }}>
        Graph not available for this workflow type.
      </div>
    );
  }

  const layoutResult = layoutNodes(graphData.nodes, graphData.edges, graphData.entry);
  const nodePositions = new Map(layoutResult.map((n) => [n.id, { x: n.x, y: n.y }]));

  // Calculate SVG dimensions
  const maxX = Math.max(...layoutResult.map((n) => n.x)) + NODE_WIDTH + 40;
  const maxY = Math.max(...layoutResult.map((n) => n.y)) + NODE_HEIGHT + 40;

  const getNodeStatus = (id: string) => {
    if (currentNode === id) return "active";
    if (failedNodes.includes(id)) return "failed";
    if (completedNodes.includes(id)) return "completed";
    return "pending";
  };

  const getNodeColor = (node: LayoutNode) => {
    const status = getNodeStatus(node.id);
    if (status === "active") return "#3b82f6";
    if (status === "completed") return "#22c55e";
    if (status === "failed") return "#ef4444";
    return TYPE_COLORS[node.type] ?? "#6b7280";
  };

  return (
    <div style={{ overflow: "auto", borderRadius: 8, border: "1px solid var(--sapGroup_ContentBorderColor)" }}>
      <svg
        width={maxX}
        height={maxY}
        style={{ background: "var(--sapList_Background)", display: "block" }}
      >
        {/* Edges */}
        {graphData.edges.map((edge, i) => {
          const from = nodePositions.get(edge.from);
          const to = edge.to === "END" ? null : nodePositions.get(edge.to);
          if (!from) return null;

          const x1 = from.x + NODE_WIDTH;
          const y1 = from.y + NODE_HEIGHT / 2;

          if (!to) {
            // Edge to END — draw a small circle
            return (
              <g key={i}>
                <line
                  x1={x1} y1={y1}
                  x2={x1 + 30} y2={y1}
                  stroke="var(--sapContent_LabelColor)"
                  strokeWidth={1.5}
                  strokeDasharray={edge.condition ? "4,3" : "none"}
                  markerEnd="url(#arrowhead)"
                />
                <circle cx={x1 + 40} cy={y1} r={6} fill="#22c55e" />
                <text x={x1 + 40} y={y1 + 3} textAnchor="middle" fontSize={8} fill="#fff" fontWeight="bold">✓</text>
              </g>
            );
          }

          const x2 = to.x;
          const y2 = to.y + NODE_HEIGHT / 2;

          // Simple bezier curve
          const midX = (x1 + x2) / 2;

          return (
            <g key={i}>
              <path
                d={`M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`}
                fill="none"
                stroke="var(--sapContent_LabelColor)"
                strokeWidth={1.5}
                strokeDasharray={edge.condition ? "4,3" : "none"}
                markerEnd="url(#arrowhead)"
                opacity={0.6}
              />
              {edge.condition && (
                <text
                  x={midX}
                  y={Math.min(y1, y2) - 4}
                  textAnchor="middle"
                  fontSize={9}
                  fill="var(--sapContent_LabelColor)"
                  opacity={0.7}
                >
                  {edge.condition}
                </text>
              )}
            </g>
          );
        })}

        {/* Nodes */}
        {layoutResult.map((node) => {
          const status = getNodeStatus(node.id);
          const color = getNodeColor(node);
          const isApproval = node.type === "approval" || node.type === "gate";

          return (
            <g key={node.id}>
              {isApproval ? (
                // Diamond shape for approval/gate nodes
                <g>
                  <polygon
                    points={`
                      ${node.x + NODE_WIDTH / 2},${node.y}
                      ${node.x + NODE_WIDTH},${node.y + NODE_HEIGHT / 2}
                      ${node.x + NODE_WIDTH / 2},${node.y + NODE_HEIGHT}
                      ${node.x},${node.y + NODE_HEIGHT / 2}
                    `}
                    fill={color}
                    opacity={status === "pending" ? 0.3 : 0.9}
                    stroke={status === "active" ? "#fff" : "none"}
                    strokeWidth={status === "active" ? 2 : 0}
                  />
                  <text
                    x={node.x + NODE_WIDTH / 2}
                    y={node.y + NODE_HEIGHT / 2 - 4}
                    textAnchor="middle"
                    fontSize={12}
                  >
                    {node.icon}
                  </text>
                  <text
                    x={node.x + NODE_WIDTH / 2}
                    y={node.y + NODE_HEIGHT / 2 + 10}
                    textAnchor="middle"
                    fontSize={9}
                    fill="#fff"
                    fontWeight="600"
                  >
                    {node.label}
                  </text>
                </g>
              ) : (
                // Rounded rectangle for agent nodes
                <g>
                  <rect
                    x={node.x}
                    y={node.y}
                    width={NODE_WIDTH}
                    height={NODE_HEIGHT}
                    rx={8}
                    fill={color}
                    opacity={status === "pending" ? 0.3 : 0.9}
                    stroke={status === "active" ? "#fff" : "none"}
                    strokeWidth={status === "active" ? 2 : 0}
                  />
                  {status === "active" && (
                    <rect
                      x={node.x}
                      y={node.y}
                      width={NODE_WIDTH}
                      height={NODE_HEIGHT}
                      rx={8}
                      fill="none"
                      stroke="#93c5fd"
                      strokeWidth={3}
                      opacity={0.5}
                    >
                      <animate attributeName="opacity" values="0.5;0.1;0.5" dur="1.5s" repeatCount="indefinite" />
                    </rect>
                  )}
                  <text
                    x={node.x + NODE_WIDTH / 2}
                    y={node.y + NODE_HEIGHT / 2 - 6}
                    textAnchor="middle"
                    fontSize={14}
                  >
                    {node.icon}
                  </text>
                  <text
                    x={node.x + NODE_WIDTH / 2}
                    y={node.y + NODE_HEIGHT / 2 + 10}
                    textAnchor="middle"
                    fontSize={10}
                    fill="#fff"
                    fontWeight="600"
                  >
                    {node.label}
                  </text>
                </g>
              )}
            </g>
          );
        })}

        {/* Arrow marker definition */}
        <defs>
          <marker
            id="arrowhead"
            markerWidth="8"
            markerHeight="6"
            refX="8"
            refY="3"
            orient="auto"
          >
            <polygon
              points="0 0, 8 3, 0 6"
              fill="var(--sapContent_LabelColor)"
              opacity={0.6}
            />
          </marker>
        </defs>
      </svg>
    </div>
  );
}
