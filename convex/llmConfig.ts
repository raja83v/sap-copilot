import { v } from "convex/values";
import { mutation, query } from "./_generated/server";

export const get = query({
  handler: async (ctx) => {
    return await ctx.db.query("llmConfig").first();
  },
});

export const upsert = mutation({
  args: {
    baseUrl: v.string(),
    apiKey: v.string(),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db.query("llmConfig").first();
    if (existing) {
      await ctx.db.patch(existing._id, args);
      return existing._id;
    }
    return await ctx.db.insert("llmConfig", args);
  },
});
