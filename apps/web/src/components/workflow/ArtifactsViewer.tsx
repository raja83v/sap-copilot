import { useState } from "react";

interface ArtifactsViewerProps {
  artifacts?: string;  // JSON-serialized { name: source }
  createdObjects?: string[];
}

export function ArtifactsViewer({ artifacts, createdObjects = [] }: ArtifactsViewerProps) {
  const [selectedObject, setSelectedObject] = useState<string | null>(null);

  let parsed: Record<string, string> = {};
  if (artifacts) {
    try {
      parsed = JSON.parse(artifacts);
    } catch {
      // Not valid JSON
    }
  }

  const objectNames = Object.keys(parsed).length > 0
    ? Object.keys(parsed)
    : createdObjects;

  if (objectNames.length === 0) {
    return (
      <div style={{ padding: 20, textAlign: "center", color: "var(--sapContent_LabelColor)", fontSize: 13 }}>
        No artifacts created yet. Objects will appear here as the Coder agent creates them.
      </div>
    );
  }

  const selectedSource = selectedObject ? parsed[selectedObject] : null;

  return (
    <div style={{ display: "flex", gap: 12, height: "100%", minHeight: 300 }}>
      {/* Object list */}
      <div style={{
        width: 200,
        flexShrink: 0,
        borderRadius: 8,
        border: "1px solid var(--sapGroup_ContentBorderColor)",
        background: "var(--sapList_Background)",
        overflow: "auto",
      }}>
        <div style={{
          padding: "8px 12px",
          fontSize: 11,
          fontWeight: 600,
          color: "var(--sapContent_LabelColor)",
          borderBottom: "1px solid var(--sapGroup_ContentBorderColor)",
        }}>
          Objects ({objectNames.length})
        </div>
        {objectNames.map((name) => (
          <div
            key={name}
            onClick={() => setSelectedObject(name)}
            style={{
              padding: "8px 12px",
              fontSize: 12,
              cursor: "pointer",
              background: selectedObject === name ? "var(--sapList_SelectionBackgroundColor)" : "transparent",
              borderLeft: selectedObject === name ? "3px solid var(--sapButton_Emphasized_Background)" : "3px solid transparent",
              color: "var(--sapTextColor)",
              transition: "background 0.15s",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            <span style={{ marginRight: 6 }}>📄</span>
            {name}
          </div>
        ))}
      </div>

      {/* Source viewer */}
      <div style={{
        flex: 1,
        borderRadius: 8,
        border: "1px solid var(--sapGroup_ContentBorderColor)",
        background: "var(--sapList_Background)",
        overflow: "auto",
        display: "flex",
        flexDirection: "column",
      }}>
        {selectedSource ? (
          <>
            <div style={{
              padding: "8px 12px",
              fontSize: 11,
              fontWeight: 600,
              color: "var(--sapContent_LabelColor)",
              borderBottom: "1px solid var(--sapGroup_ContentBorderColor)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}>
              <span>{selectedObject}</span>
              <button
                onClick={() => navigator.clipboard.writeText(selectedSource)}
                style={{
                  padding: "2px 8px",
                  borderRadius: 4,
                  border: "1px solid var(--sapButton_BorderColor)",
                  background: "transparent",
                  color: "var(--sapButton_TextColor)",
                  fontSize: 10,
                  cursor: "pointer",
                }}
              >
                📋 Copy
              </button>
            </div>
            <pre style={{
              margin: 0,
              padding: 12,
              fontSize: 12,
              fontFamily: "'Cascadia Code', 'Fira Code', 'JetBrains Mono', monospace",
              lineHeight: 1.6,
              color: "var(--sapTextColor)",
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              flex: 1,
              overflow: "auto",
            }}>
              {selectedSource}
            </pre>
          </>
        ) : (
          <div style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--sapContent_LabelColor)",
            fontSize: 13,
          }}>
            {objectNames.length > 0
              ? "Select an object to view its source code"
              : "No source code available"}
          </div>
        )}
      </div>
    </div>
  );
}
