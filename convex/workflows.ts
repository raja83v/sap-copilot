import { v } from "convex/values";
import { mutation, query } from "./_generated/server";

const toolCallValidator = v.object({
  id: v.string(),
  name: v.string(),
  parameters: v.string(),
  result: v.optional(v.string()),
  duration: v.optional(v.number()),
  status: v.string(),
});

const approvalValidator = v.object({
  id: v.string(),
  phase: v.string(),
  status: v.string(),
  details: v.string(),
  requestedAt: v.number(),
  respondedAt: v.optional(v.number()),
  feedback: v.optional(v.string()),
});

const stepValidator = v.object({
  id: v.string(),
  agent: v.string(),
  action: v.string(),
  status: v.string(),
  startedAt: v.number(),
  completedAt: v.optional(v.number()),
  result: v.optional(v.string()),
  toolCalls: v.optional(v.array(toolCallValidator)),
});

// ─── Queries ───

export const get = query({
  args: { id: v.id("workflows") },
  handler: async (ctx, args) => {
    return await ctx.db.get(args.id);
  },
});

export const listBySession = query({
  args: { sessionId: v.id("sessions") },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("workflows")
      .withIndex("by_sessionId", (q) => q.eq("sessionId", args.sessionId))
      .order("desc")
      .collect();
  },
});

export const listBySystem = query({
  args: { systemId: v.id("systems") },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("workflows")
      .withIndex("by_systemId", (q) => q.eq("systemId", args.systemId))
      .order("desc")
      .collect();
  },
});

export const listByStatus = query({
  args: { status: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("workflows")
      .withIndex("by_status", (q) => q.eq("status", args.status))
      .order("desc")
      .collect();
  },
});

export const countPendingApprovals = query({
  args: { systemId: v.optional(v.id("systems")) },
  handler: async (ctx, args) => {
    let workflows;
    if (args.systemId) {
      workflows = await ctx.db
        .query("workflows")
        .withIndex("by_systemId", (q) => q.eq("systemId", args.systemId!))
        .collect();
    } else {
      workflows = await ctx.db
        .query("workflows")
        .withIndex("by_status", (q) => q.eq("status", "paused"))
        .collect();
    }
    let count = 0;
    for (const wf of workflows) {
      for (const approval of wf.approvals) {
        if (approval.status === "pending") count++;
      }
      // Also count pending clarifications
      for (const clar of wf.clarifications ?? []) {
        if (!clar.answer) count++;
      }
    }
    return count;
  },
});

// ─── Mutations ───

export const create = mutation({
  args: {
    sessionId: v.id("sessions"),
    systemId: v.id("systems"),
    type: v.string(),
    userRequest: v.string(),
    graphType: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const now = Date.now();
    return await ctx.db.insert("workflows", {
      sessionId: args.sessionId,
      systemId: args.systemId,
      type: args.type,
      status: "planning",
      phase: "planning",
      graphType: args.graphType,
      userRequest: args.userRequest,
      approvals: [],
      steps: [],
      clarifications: [],
      createdAt: now,
      updatedAt: now,
    });
  },
});

export const updatePhase = mutation({
  args: {
    id: v.id("workflows"),
    phase: v.string(),
    status: v.string(),
  },
  handler: async (ctx, args) => {
    await ctx.db.patch(args.id, {
      phase: args.phase,
      status: args.status,
      updatedAt: Date.now(),
    });
  },
});

export const updatePlan = mutation({
  args: {
    id: v.id("workflows"),
    plan: v.string(),
  },
  handler: async (ctx, args) => {
    await ctx.db.patch(args.id, {
      plan: args.plan,
      updatedAt: Date.now(),
    });
  },
});

export const updateArtifacts = mutation({
  args: {
    id: v.id("workflows"),
    artifacts: v.string(), // JSON-serialized
  },
  handler: async (ctx, args) => {
    await ctx.db.patch(args.id, {
      artifacts: args.artifacts,
      updatedAt: Date.now(),
    });
  },
});

export const updateMetadata = mutation({
  args: {
    id: v.id("workflows"),
    metadata: v.string(), // JSON-serialized
  },
  handler: async (ctx, args) => {
    await ctx.db.patch(args.id, {
      metadata: args.metadata,
      updatedAt: Date.now(),
    });
  },
});

export const setError = mutation({
  args: {
    id: v.id("workflows"),
    error: v.string(),
  },
  handler: async (ctx, args) => {
    await ctx.db.patch(args.id, {
      error: args.error,
      status: "failed",
      updatedAt: Date.now(),
    });
  },
});

export const addStep = mutation({
  args: {
    id: v.id("workflows"),
    step: stepValidator,
  },
  handler: async (ctx, args) => {
    const wf = await ctx.db.get(args.id);
    if (!wf) return;
    await ctx.db.patch(args.id, {
      steps: [...wf.steps, args.step],
      updatedAt: Date.now(),
    });
  },
});

export const updateStep = mutation({
  args: {
    id: v.id("workflows"),
    stepId: v.string(),
    status: v.string(),
    result: v.optional(v.string()),
    toolCalls: v.optional(v.array(toolCallValidator)),
  },
  handler: async (ctx, args) => {
    const wf = await ctx.db.get(args.id);
    if (!wf) return;
    const steps = wf.steps.map((s) => {
      if (s.id !== args.stepId) return s;
      return {
        ...s,
        status: args.status,
        completedAt: args.status === "completed" || args.status === "failed" ? Date.now() : undefined,
        result: args.result ?? s.result,
        toolCalls: args.toolCalls ?? s.toolCalls,
      };
    });
    await ctx.db.patch(args.id, { steps, updatedAt: Date.now() });
  },
});

export const requestApproval = mutation({
  args: {
    id: v.id("workflows"),
    approval: approvalValidator,
  },
  handler: async (ctx, args) => {
    const wf = await ctx.db.get(args.id);
    if (!wf) return;
    await ctx.db.patch(args.id, {
      approvals: [...wf.approvals, args.approval],
      status: "paused",
      updatedAt: Date.now(),
    });
  },
});

export const respondApproval = mutation({
  args: {
    id: v.id("workflows"),
    approvalId: v.string(),
    status: v.string(), // approved | rejected
    feedback: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const wf = await ctx.db.get(args.id);
    if (!wf) return;
    const approvals = wf.approvals.map((a) => {
      if (a.id !== args.approvalId) return a;
      return {
        ...a,
        status: args.status,
        respondedAt: Date.now(),
        feedback: args.feedback,
      };
    });
    await ctx.db.patch(args.id, {
      approvals,
      // Resume the workflow — the gateway will pick up the response
      status: args.status === "approved" ? wf.phase : "paused",
      updatedAt: Date.now(),
    });
  },
});

export const addClarification = mutation({
  args: {
    id: v.id("workflows"),
    clarification: v.object({
      id: v.string(),
      question: v.string(),
      questionType: v.string(),
      options: v.optional(v.array(v.string())),
      defaultValue: v.optional(v.string()),
      required: v.boolean(),
    }),
  },
  handler: async (ctx, args) => {
    const wf = await ctx.db.get(args.id);
    if (!wf) return;
    const clarifications = [...(wf.clarifications ?? []), {
      ...args.clarification,
      answer: undefined,
      answeredAt: undefined,
    }];
    await ctx.db.patch(args.id, {
      clarifications,
      status: "paused",
      updatedAt: Date.now(),
    });
  },
});

export const answerClarification = mutation({
  args: {
    id: v.id("workflows"),
    clarificationId: v.string(),
    answer: v.string(),
  },
  handler: async (ctx, args) => {
    const wf = await ctx.db.get(args.id);
    if (!wf) return;
    const clarifications = (wf.clarifications ?? []).map((c) => {
      if (c.id !== args.clarificationId) return c;
      return {
        ...c,
        answer: args.answer,
        answeredAt: Date.now(),
      };
    });
    await ctx.db.patch(args.id, {
      clarifications,
      updatedAt: Date.now(),
    });
  },
});

export const updateAnalysis = mutation({
  args: {
    id: v.id("workflows"),
    analysisSummary: v.string(),
  },
  handler: async (ctx, args) => {
    await ctx.db.patch(args.id, {
      analysisSummary: args.analysisSummary,
      updatedAt: Date.now(),
    });
  },
});

export const updateDocumentation = mutation({
  args: {
    id: v.id("workflows"),
    documentation: v.string(),
  },
  handler: async (ctx, args) => {
    await ctx.db.patch(args.id, {
      documentation: args.documentation,
      updatedAt: Date.now(),
    });
  },
});

export const updateMigrationLog = mutation({
  args: {
    id: v.id("workflows"),
    migrationLog: v.string(), // JSON-serialized
  },
  handler: async (ctx, args) => {
    await ctx.db.patch(args.id, {
      migrationLog: args.migrationLog,
      updatedAt: Date.now(),
    });
  },
});

export const retryStep = mutation({
  args: {
    id: v.id("workflows"),
    stepId: v.string(),
  },
  handler: async (ctx, args) => {
    const wf = await ctx.db.get(args.id);
    if (!wf) return;
    const steps = wf.steps.map((s) => {
      if (s.id !== args.stepId) return s;
      return {
        ...s,
        status: "running",
        result: "Retrying...",
        completedAt: undefined,
      };
    });
    await ctx.db.patch(args.id, {
      steps,
      status: wf.phase, // Resume from current phase
      updatedAt: Date.now(),
    });
  },
});

export const remove = mutation({
  args: { id: v.id("workflows") },
  handler: async (ctx, args) => {
    await ctx.db.delete(args.id);
  },
});
