import { v } from "convex/values";
import { mutation, query } from "./_generated/server";

export const list = query({
  handler: async (ctx) => {
    return await ctx.db.query("systems").collect();
  },
});

export const get = query({
  args: { id: v.id("systems") },
  handler: async (ctx, args) => {
    return await ctx.db.get(args.id);
  },
});

export const add = mutation({
  args: {
    name: v.string(),
    description: v.optional(v.string()),
    baseUrl: v.string(),
    client: v.string(),
    language: v.string(),
    username: v.string(),
    password: v.string(),
    proxy: v.optional(v.string()),
    color: v.string(),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("systems", {
      ...args,
      status: "disconnected",
    });
  },
});

export const updateStatus = mutation({
  args: {
    id: v.id("systems"),
    status: v.union(
      v.literal("connected"),
      v.literal("disconnected"),
      v.literal("connecting"),
      v.literal("error")
    ),
    lastConnected: v.optional(v.number()),
    lastError: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const { id, ...updates } = args;
    await ctx.db.patch(id, updates);
  },
});

export const update = mutation({
  args: {
    id: v.id("systems"),
    name: v.string(),
    description: v.optional(v.string()),
    baseUrl: v.string(),
    client: v.string(),
    language: v.string(),
    username: v.string(),
    password: v.string(),
    proxy: v.optional(v.string()),
    color: v.string(),
  },
  handler: async (ctx, args) => {
    const { id, ...updates } = args;
    await ctx.db.patch(id, updates);
  },
});

export const remove = mutation({
  args: { id: v.id("systems") },
  handler: async (ctx, args) => {
    // Delete all sessions and their messages for this system
    const sessions = await ctx.db
      .query("sessions")
      .withIndex("by_systemId", (q) => q.eq("systemId", args.id))
      .collect();
    for (const session of sessions) {
      const messages = await ctx.db
        .query("messages")
        .withIndex("by_sessionId", (q) => q.eq("sessionId", session._id))
        .collect();
      for (const msg of messages) {
        await ctx.db.delete(msg._id);
      }
      await ctx.db.delete(session._id);
    }
    await ctx.db.delete(args.id);
  },
});
