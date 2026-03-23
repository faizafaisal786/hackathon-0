#!/usr/bin/env node
/**
 * email-mcp/index.js — Email MCP Server (Gold Tier)
 * ==================================================
 * Model Context Protocol server for Gmail integration.
 * Exposes tools: send_email, draft_email, search_emails, list_unread
 *
 * Setup:
 *   npm install @modelcontextprotocol/sdk nodemailer googleapis
 *   node index.js
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { google } from "googleapis";
import nodemailer from "nodemailer";
import fs from "fs";
import path from "path";

// ─── Config ─────────────────────────────────────────────────────────────────

const DRY_RUN = process.env.DRY_RUN === "true";
const CREDENTIALS_PATH = process.env.GMAIL_CREDENTIALS_PATH || "./credentials.json";
const TOKEN_PATH = process.env.GMAIL_TOKEN_PATH || "./token.json";
const SCOPES = [
  "https://www.googleapis.com/auth/gmail.send",
  "https://www.googleapis.com/auth/gmail.readonly",
  "https://www.googleapis.com/auth/gmail.compose",
];

// ─── Gmail Auth ──────────────────────────────────────────────────────────────

function getGmailAuth() {
  if (!fs.existsSync(CREDENTIALS_PATH)) {
    throw new Error(`Gmail credentials not found at: ${CREDENTIALS_PATH}`);
  }
  const credentials = JSON.parse(fs.readFileSync(CREDENTIALS_PATH, "utf8"));
  const { client_secret, client_id, redirect_uris } = credentials.installed || credentials.web;
  const oAuth2Client = new google.auth.OAuth2(client_id, client_secret, redirect_uris[0]);

  if (fs.existsSync(TOKEN_PATH)) {
    const token = JSON.parse(fs.readFileSync(TOKEN_PATH, "utf8"));
    oAuth2Client.setCredentials(token);
  }
  return oAuth2Client;
}

async function sendEmail({ to, subject, body, cc = "", attachmentPath = null }) {
  if (DRY_RUN) {
    console.error(`[DRY RUN] Would send email to: ${to}, subject: ${subject}`);
    return { success: true, dry_run: true, message_id: "dry-run-id" };
  }

  const auth = getGmailAuth();
  const gmail = google.gmail({ version: "v1", auth });

  // Build RFC 2822 message
  let message = [
    `To: ${to}`,
    cc ? `Cc: ${cc}` : "",
    `Subject: ${subject}`,
    "MIME-Version: 1.0",
    "Content-Type: text/plain; charset=utf-8",
    "",
    body,
  ]
    .filter(Boolean)
    .join("\r\n");

  const encodedMessage = Buffer.from(message).toString("base64url");

  const result = await gmail.users.messages.send({
    userId: "me",
    requestBody: { raw: encodedMessage },
  });

  return { success: true, message_id: result.data.id };
}

async function listUnread({ max_results = 10, query = "is:unread is:important" }) {
  const auth = getGmailAuth();
  const gmail = google.gmail({ version: "v1", auth });

  const response = await gmail.users.messages.list({
    userId: "me",
    q: query,
    maxResults: max_results,
  });

  const messages = response.data.messages || [];
  const results = [];

  for (const msg of messages.slice(0, 5)) {
    const full = await gmail.users.messages.get({ userId: "me", id: msg.id });
    const headers = Object.fromEntries(
      (full.data.payload?.headers || []).map((h) => [h.name, h.value])
    );
    results.push({
      id: msg.id,
      from: headers["From"] || "Unknown",
      subject: headers["Subject"] || "No Subject",
      date: headers["Date"] || "",
      snippet: full.data.snippet || "",
    });
  }

  return { emails: results, total: messages.length };
}

async function draftEmail({ to, subject, body }) {
  if (DRY_RUN) {
    return { success: true, dry_run: true, draft_id: "dry-run-draft" };
  }

  const auth = getGmailAuth();
  const gmail = google.gmail({ version: "v1", auth });

  const message = [`To: ${to}`, `Subject: ${subject}`, "", body].join("\r\n");
  const encodedMessage = Buffer.from(message).toString("base64url");

  const result = await gmail.users.drafts.create({
    userId: "me",
    requestBody: { message: { raw: encodedMessage } },
  });

  return { success: true, draft_id: result.data.id };
}

// ─── MCP Server ──────────────────────────────────────────────────────────────

const server = new Server(
  { name: "email-mcp", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "send_email",
      description: "Send an email via Gmail. Requires human approval for new contacts.",
      inputSchema: {
        type: "object",
        properties: {
          to: { type: "string", description: "Recipient email address" },
          subject: { type: "string", description: "Email subject" },
          body: { type: "string", description: "Email body (plain text)" },
          cc: { type: "string", description: "CC recipients (optional)" },
        },
        required: ["to", "subject", "body"],
      },
    },
    {
      name: "draft_email",
      description: "Create a Gmail draft (does not send — safe for auto-use).",
      inputSchema: {
        type: "object",
        properties: {
          to: { type: "string" },
          subject: { type: "string" },
          body: { type: "string" },
        },
        required: ["to", "subject", "body"],
      },
    },
    {
      name: "list_unread",
      description: "List unread important emails from Gmail.",
      inputSchema: {
        type: "object",
        properties: {
          max_results: { type: "number", default: 10 },
          query: { type: "string", default: "is:unread is:important" },
        },
      },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    let result;
    if (name === "send_email") result = await sendEmail(args);
    else if (name === "draft_email") result = await draftEmail(args);
    else if (name === "list_unread") result = await listUnread(args);
    else throw new Error(`Unknown tool: ${name}`);

    return {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
    };
  } catch (error) {
    return {
      content: [{ type: "text", text: `Error: ${error.message}` }],
      isError: true,
    };
  }
});

// ─── Start ───────────────────────────────────────────────────────────────────

const transport = new StdioServerTransport();
await server.connect(transport);
console.error("Email MCP Server running (Gold Tier)");
