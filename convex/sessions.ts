import { v } from "convex/values";
import { mutation, query } from "./_generated/server";

export const listBySystem = query({
  args: { systemId: v.id("systems") },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("sessions")
      .withIndex("by_systemId", (q) => q.eq("systemId", args.systemId))
      .order("desc")
      .collect();
  },
});

export const get = query({
  args: { id: v.id("sessions") },
  handler: async (ctx, args) => {
    return await ctx.db.get(args.id);
  },
});

export const create = mutation({
  args: {
    systemId: v.id("systems"),
    title: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("sessions", {
      systemId: args.systemId,
      title: args.title ?? "New Chat",
      createdAt: Date.now(),
      updatedAt: Date.now(),
      messageCount: 0,
      toolCallCount: 0,
    });
  },
});

export const updateTitle = mutation({
  args: { id: v.id("sessions"), title: v.string() },
  handler: async (ctx, args) => {
    await ctx.db.patch(args.id, { title: args.title, updatedAt: Date.now() });
  },
});

export const incrementCounters = mutation({
  args: {
    id: v.id("sessions"),
    messages: v.optional(v.number()),
    toolCalls: v.optional(v.number()),
  },
  handler: async (ctx, args) => {
    const session = await ctx.db.get(args.id);
    if (!session) return;
    await ctx.db.patch(args.id, {
      messageCount: session.messageCount + (args.messages ?? 0),
      toolCallCount: session.toolCallCount + (args.toolCalls ?? 0),
      updatedAt: Date.now(),
    });
  },
});

export const remove = mutation({
  args: { id: v.id("sessions") },
  handler: async (ctx, args) => {
    // Delete all messages for this session
    const messages = await ctx.db
      .query("messages")
      .withIndex("by_sessionId", (q) => q.eq("sessionId", args.id))
      .collect();
    for (const msg of messages) {
      await ctx.db.delete(msg._id);
    }
    // Delete all workflows for this session
    const workflows = await ctx.db
      .query("workflows")
      .withIndex("by_sessionId", (q) => q.eq("sessionId", args.id))
      .collect();
    for (const wf of workflows) {
      await ctx.db.delete(wf._id);
    }
    // Delete the session itself
    await ctx.db.delete(args.id);
  },
});
