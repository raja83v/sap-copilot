import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

const toolCallValidator = v.object({
  id: v.string(),
  name: v.string(),
  parameters: v.string(),
  result: v.optional(v.string()),
  duration: v.optional(v.number()),
  status: v.string(),
});

const workflowApprovalValidator = v.object({
  id: v.string(),
  phase: v.string(),
  status: v.string(), // pending | approved | rejected
  details: v.string(),
  requestedAt: v.number(),
  respondedAt: v.optional(v.number()),
  feedback: v.optional(v.string()),
});

const workflowStepValidator = v.object({
  id: v.string(),
  agent: v.string(), // planner | clarifier | coder | reviewer | tester | activator
  action: v.string(),
  status: v.string(), // running | completed | failed | skipped
  startedAt: v.number(),
  completedAt: v.optional(v.number()),
  result: v.optional(v.string()),
  toolCalls: v.optional(v.array(toolCallValidator)),
});

export default defineSchema({
  systems: defineTable({
    name: v.string(),
    description: v.optional(v.string()),
    baseUrl: v.string(),
    client: v.string(),
    language: v.string(),
    username: v.string(),
    password: v.string(),
    proxy: v.optional(v.string()),
    color: v.string(),
    status: v.union(
      v.literal("connected"),
      v.literal("disconnected"),
      v.literal("connecting"),
      v.literal("error")
    ),
    lastConnected: v.optional(v.number()),
    lastError: v.optional(v.string()),
  }),

  sessions: defineTable({
    systemId: v.id("systems"),
    title: v.string(),
    createdAt: v.number(),
    updatedAt: v.number(),
    messageCount: v.number(),
    toolCallCount: v.number(),
  }).index("by_systemId", ["systemId"]),

  messages: defineTable({
    sessionId: v.id("sessions"),
    role: v.union(
      v.literal("user"),
      v.literal("assistant"),
      v.literal("system"),
      v.literal("tool")
    ),
    content: v.string(),
    toolCalls: v.optional(v.array(toolCallValidator)),
    toolCallId: v.optional(v.string()),
    timestamp: v.number(),
    model: v.optional(v.string()),
    workflowId: v.optional(v.string()),
  }).index("by_sessionId", ["sessionId"]),

  workflows: defineTable({
    sessionId: v.id("sessions"),
    systemId: v.id("systems"),
    type: v.string(),   // create_report | create_class | create_cds_view | ...
    status: v.string(),  // planning | clarifying | coding | reviewing | testing | activating | completed | failed | paused
    phase: v.string(),
    graphType: v.optional(v.string()),  // which graph pattern was used
    userRequest: v.string(),
    plan: v.optional(v.string()),
    artifacts: v.optional(v.string()),   // JSON-serialized { name: source }
    metadata: v.optional(v.string()),    // JSON-serialized { package, transport, ... }
    approvals: v.array(workflowApprovalValidator),
    steps: v.array(workflowStepValidator),
    clarifications: v.optional(v.array(v.object({
      id: v.string(),
      question: v.string(),
      questionType: v.string(),          // text | select | confirm
      options: v.optional(v.array(v.string())),
      defaultValue: v.optional(v.string()),
      required: v.boolean(),
      answer: v.optional(v.string()),
      answeredAt: v.optional(v.number()),
    }))),
    analysisSummary: v.optional(v.string()),
    documentation: v.optional(v.string()),
    migrationLog: v.optional(v.string()),  // JSON-serialized
    error: v.optional(v.string()),
    createdAt: v.number(),
    updatedAt: v.number(),
  })
    .index("by_sessionId", ["sessionId"])
    .index("by_systemId", ["systemId"])
    .index("by_status", ["status"]),

  llmConfig: defineTable({
    baseUrl: v.string(),
    apiKey: v.string(),
  }),
});
