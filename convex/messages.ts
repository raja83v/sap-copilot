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

export const listBySession = query({
  args: { sessionId: v.id("sessions") },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("messages")
      .withIndex("by_sessionId", (q) => q.eq("sessionId", args.sessionId))
      .order("asc")
      .collect();
  },
});

export const add = mutation({
  args: {
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
    model: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("messages", {
      ...args,
      timestamp: Date.now(),
    });
  },
});

export const updateContent = mutation({
  args: {
    id: v.id("messages"),
    content: v.string(),
    toolCalls: v.optional(v.array(toolCallValidator)),
  },
  handler: async (ctx, args) => {
    const { id, ...updates } = args;
    const clean: Record<string, unknown> = { content: updates.content };
    if (updates.toolCalls !== undefined) clean.toolCalls = updates.toolCalls;
    await ctx.db.patch(id, clean);
  },
});
