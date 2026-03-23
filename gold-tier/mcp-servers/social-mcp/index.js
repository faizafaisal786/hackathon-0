#!/usr/bin/env node
/**
 * social-mcp/index.js — Social Media MCP Server (Gold Tier)
 * ==========================================================
 * Handles posting to Facebook, Instagram, and Twitter/X.
 * All posts go through human approval before publishing.
 *
 * Tools: post_facebook, post_instagram, post_twitter, get_analytics
 *
 * Setup:
 *   npm install @modelcontextprotocol/sdk node-fetch
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

const DRY_RUN = process.env.DRY_RUN === "true";

// ─── Facebook / Meta Graph API ───────────────────────────────────────────────

async function postFacebook({ message, page_id, image_url = null }) {
  if (DRY_RUN) {
    return { success: true, dry_run: true, post_id: "dry-run-fb-post" };
  }

  const token = process.env.FACEBOOK_PAGE_ACCESS_TOKEN;
  if (!token) throw new Error("FACEBOOK_PAGE_ACCESS_TOKEN not set in environment.");

  const endpoint = image_url
    ? `https://graph.facebook.com/${page_id}/photos`
    : `https://graph.facebook.com/${page_id}/feed`;

  const body = image_url
    ? { message, url: image_url, access_token: token }
    : { message, access_token: token };

  const res = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const data = await res.json();
  if (!res.ok) throw new Error(data.error?.message || "Facebook API error");
  return { success: true, post_id: data.id };
}

async function postInstagram({ caption, image_url, instagram_user_id }) {
  if (DRY_RUN) {
    return { success: true, dry_run: true, media_id: "dry-run-ig-media" };
  }

  const token = process.env.INSTAGRAM_ACCESS_TOKEN;
  if (!token) throw new Error("INSTAGRAM_ACCESS_TOKEN not set.");

  // Step 1: Create media container
  const createRes = await fetch(
    `https://graph.facebook.com/${instagram_user_id}/media`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image_url, caption, access_token: token }),
    }
  );
  const createData = await createRes.json();
  if (!createRes.ok) throw new Error(createData.error?.message || "Instagram create media error");

  // Step 2: Publish media
  const publishRes = await fetch(
    `https://graph.facebook.com/${instagram_user_id}/media_publish`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ creation_id: createData.id, access_token: token }),
    }
  );
  const publishData = await publishRes.json();
  if (!publishRes.ok) throw new Error(publishData.error?.message || "Instagram publish error");

  return { success: true, media_id: publishData.id };
}

async function postTwitter({ text, reply_to_id = null }) {
  if (DRY_RUN) {
    return { success: true, dry_run: true, tweet_id: "dry-run-tweet" };
  }

  const token = process.env.TWITTER_BEARER_TOKEN;
  const apiKey = process.env.TWITTER_API_KEY;
  const apiSecret = process.env.TWITTER_API_SECRET;
  const accessToken = process.env.TWITTER_ACCESS_TOKEN;
  const accessSecret = process.env.TWITTER_ACCESS_TOKEN_SECRET;

  if (!accessToken) throw new Error("Twitter credentials not set in environment.");

  const body = { text };
  if (reply_to_id) body.reply = { in_reply_to_tweet_id: reply_to_id };

  // Note: Twitter v2 requires OAuth 1.0a for user-context actions
  // This is a simplified version — use twitter-api-v2 npm package in production
  const res = await fetch("https://api.twitter.com/2/tweets", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });

  const data = await res.json();
  if (!res.ok) throw new Error(JSON.stringify(data.errors || data));
  return { success: true, tweet_id: data.data?.id };
}

async function getSocialAnalytics({ platform, page_id, days = 7 }) {
  if (DRY_RUN) {
    return {
      platform,
      dry_run: true,
      metrics: { impressions: 0, reach: 0, engagement: 0 },
    };
  }
  // In production: call each platform's analytics API
  return { platform, message: "Analytics integration — configure platform API credentials." };
}

// ─── MCP Server ──────────────────────────────────────────────────────────────

const server = new Server(
  { name: "social-mcp", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "post_facebook",
      description: "Post a message to a Facebook Page. Always requires human approval first.",
      inputSchema: {
        type: "object",
        properties: {
          message: { type: "string" },
          page_id: { type: "string" },
          image_url: { type: "string", description: "Optional image URL" },
        },
        required: ["message", "page_id"],
      },
    },
    {
      name: "post_instagram",
      description: "Post an image with caption to Instagram Business account.",
      inputSchema: {
        type: "object",
        properties: {
          caption: { type: "string" },
          image_url: { type: "string" },
          instagram_user_id: { type: "string" },
        },
        required: ["caption", "image_url", "instagram_user_id"],
      },
    },
    {
      name: "post_twitter",
      description: "Post a tweet to Twitter/X.",
      inputSchema: {
        type: "object",
        properties: {
          text: { type: "string", maxLength: 280 },
          reply_to_id: { type: "string", description: "Optional tweet ID to reply to" },
        },
        required: ["text"],
      },
    },
    {
      name: "get_social_analytics",
      description: "Get engagement analytics for a social platform.",
      inputSchema: {
        type: "object",
        properties: {
          platform: { type: "string", enum: ["facebook", "instagram", "twitter"] },
          page_id: { type: "string" },
          days: { type: "number", default: 7 },
        },
        required: ["platform"],
      },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  try {
    let result;
    if (name === "post_facebook") result = await postFacebook(args);
    else if (name === "post_instagram") result = await postInstagram(args);
    else if (name === "post_twitter") result = await postTwitter(args);
    else if (name === "get_social_analytics") result = await getSocialAnalytics(args);
    else throw new Error(`Unknown tool: ${name}`);
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  } catch (err) {
    return { content: [{ type: "text", text: `Error: ${err.message}` }], isError: true };
  }
});

const transport = new StdioServerTransport();
await server.connect(transport);
console.error("Social MCP Server running (Gold Tier)");
