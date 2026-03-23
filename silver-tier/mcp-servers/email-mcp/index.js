#!/usr/bin/env node
/**
 * email-mcp/index.js — Email MCP Server for Silver Tier
 *
 * Provides Claude with the ability to SEND emails via Gmail API.
 * This server implements the Model Context Protocol (MCP) stdio transport.
 *
 * Tools exposed:
 *   - send_email(to, subject, body, cc?, bcc?)
 *   - list_drafts()
 *   - check_approval(approval_file_path) → verifies an approval exists before sending
 *
 * Setup:
 *   1. npm install @modelcontextprotocol/sdk googleapis dotenv
 *   2. Place your Google OAuth credentials.json next to this file
 *   3. Set env vars (see below) or create a .env file
 *   4. Register in Claude settings:
 *      { "mcpServers": { "email": { "command": "node", "args": ["path/to/index.js"] } } }
 *
 * Environment variables:
 *   GMAIL_CREDENTIALS_PATH  — Path to OAuth credentials.json
 *   GMAIL_TOKEN_PATH        — Path to cached token.json (auto-created)
 *   VAULT_PATH              — Path to vault (for approval verification)
 *   DRY_RUN                 — "true" to log but not send (default: false)
 *   GMAIL_FROM              — Sender display name (default: from credentials)
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { google } from "googleapis";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// ── Load .env if present ──────────────────────────────────────────────────────
try {
  const dotenv = await import("dotenv");
  dotenv.config({ path: path.join(__dirname, "../../.env") });
} catch {
  // dotenv optional
}

// ── Configuration ─────────────────────────────────────────────────────────────
const CREDENTIALS_PATH =
  process.env.GMAIL_CREDENTIALS_PATH ||
  path.join(__dirname, "credentials.json");
const TOKEN_PATH =
  process.env.GMAIL_TOKEN_PATH || path.join(__dirname, "token.json");
const VAULT_PATH = process.env.VAULT_PATH || path.join(__dirname, "../..");
const DRY_RUN = process.env.DRY_RUN === "true";
const GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"];

// ── Gmail Auth ────────────────────────────────────────────────────────────────

async function getGmailClient() {
  if (!fs.existsSync(CREDENTIALS_PATH)) {
    throw new Error(
      `Gmail credentials not found at ${CREDENTIALS_PATH}. ` +
        "Download from Google Cloud Console."
    );
  }

  const credentials = JSON.parse(fs.readFileSync(CREDENTIALS_PATH, "utf-8"));
  const { client_secret, client_id, redirect_uris } =
    credentials.installed || credentials.web;
  const oAuth2Client = new google.auth.OAuth2(
    client_id,
    client_secret,
    redirect_uris[0]
  );

  if (!fs.existsSync(TOKEN_PATH)) {
    throw new Error(
      `Gmail token not found at ${TOKEN_PATH}. ` +
        "Run the Python gmail_watcher.py once to generate the token via browser OAuth flow."
    );
  }

  const token = JSON.parse(fs.readFileSync(TOKEN_PATH, "utf-8"));
  oAuth2Client.setCredentials(token);
  return oAuth2Client;
}

// ── Email utilities ───────────────────────────────────────────────────────────

function buildMimeMessage({ to, subject, body, cc, bcc, from: fromAddr }) {
  const lines = [
    `From: ${fromAddr || "me"}`,
    `To: ${to}`,
  ];
  if (cc) lines.push(`Cc: ${cc}`);
  if (bcc) lines.push(`Bcc: ${bcc}`);
  lines.push(`Subject: ${subject}`);
  lines.push("MIME-Version: 1.0");
  lines.push("Content-Type: text/plain; charset=utf-8");
  lines.push("Content-Transfer-Encoding: 7bit");
  lines.push("");
  lines.push(body);

  const raw = lines.join("\r\n");
  return Buffer.from(raw).toString("base64url");
}

async function sendEmail({ to, subject, body, cc, bcc }) {
  if (DRY_RUN) {
    console.error(
      `[DRY RUN] Would send email: To=${to} Subject="${subject}"`
    );
    return { success: true, dry_run: true, message_id: "dry-run-id" };
  }

  const auth = await getGmailClient();
  const gmail = google.gmail({ version: "v1", auth });

  const raw = buildMimeMessage({ to, subject, body, cc, bcc });
  const res = await gmail.users.messages.send({
    userId: "me",
    requestBody: { raw },
  });

  return {
    success: true,
    message_id: res.data.id,
    thread_id: res.data.threadId,
  };
}

// ── Approval verification ─────────────────────────────────────────────────────

function verifyApproval(approvalFileName) {
  const approvedDir = path.join(VAULT_PATH, "Approved");
  const approvalPath = path.join(approvedDir, approvalFileName);

  if (!fs.existsSync(approvalPath)) {
    const pendingPath = path.join(VAULT_PATH, "Pending_Approval", approvalFileName);
    if (fs.existsSync(pendingPath)) {
      return {
        approved: false,
        reason: `Approval '${approvalFileName}' is still pending. Move it to Approved/ folder to authorize.`,
      };
    }
    return {
      approved: false,
      reason: `Approval file '${approvalFileName}' not found in Approved/ or Pending_Approval/.`,
    };
  }

  // Read the approval file and check for rejection markers
  const content = fs.readFileSync(approvalPath, "utf-8");
  if (content.toLowerCase().includes("rejected") || content.toLowerCase().includes("deny")) {
    return {
      approved: false,
      reason: "Approval file contains rejection marker.",
    };
  }

  return { approved: true, approval_file: approvalPath };
}

// ── MCP Server ────────────────────────────────────────────────────────────────

const server = new Server(
  { name: "email-mcp", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "send_email",
      description:
        "Send an email via Gmail. ALWAYS call check_approval first for sensitive emails. " +
        "Requires an approved action in the vault Approved/ folder.",
      inputSchema: {
        type: "object",
        properties: {
          to: { type: "string", description: "Recipient email address" },
          subject: { type: "string", description: "Email subject line" },
          body: { type: "string", description: "Plain text email body" },
          cc: { type: "string", description: "CC email address (optional)" },
          bcc: { type: "string", description: "BCC email address (optional)" },
          approval_file: {
            type: "string",
            description:
              "Filename of the approval document in vault Approved/ folder (required for sensitive emails)",
          },
        },
        required: ["to", "subject", "body"],
      },
    },
    {
      name: "check_approval",
      description:
        "Verify that an action has been approved by checking vault Approved/ folder. " +
        "Call this BEFORE any send_email for sensitive communications.",
      inputSchema: {
        type: "object",
        properties: {
          approval_file: {
            type: "string",
            description: "Filename to look for in Approved/ folder",
          },
        },
        required: ["approval_file"],
      },
    },
    {
      name: "list_approved_emails",
      description: "List all email approvals waiting to be sent in the vault Approved/ folder.",
      inputSchema: { type: "object", properties: {} },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    if (name === "check_approval") {
      const result = verifyApproval(args.approval_file);
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(result, null, 2),
          },
        ],
      };
    }

    if (name === "send_email") {
      // If approval_file provided, verify it first
      if (args.approval_file) {
        const approval = verifyApproval(args.approval_file);
        if (!approval.approved) {
          return {
            content: [
              {
                type: "text",
                text: JSON.stringify(
                  {
                    success: false,
                    error: "Email blocked: approval not verified.",
                    detail: approval.reason,
                  },
                  null,
                  2
                ),
              },
            ],
          };
        }
      }

      const result = await sendEmail({
        to: args.to,
        subject: args.subject,
        body: args.body,
        cc: args.cc,
        bcc: args.bcc,
      });

      // Log to vault
      const logEntry =
        `${new Date().toISOString()} | send_email | to=${args.to} | ` +
        `subject="${args.subject}" | dry_run=${DRY_RUN} | ` +
        `result=${JSON.stringify(result)}\n`;
      const logPath = path.join(VAULT_PATH, "Logs", "email_sent.log");
      fs.mkdirSync(path.dirname(logPath), { recursive: true });
      fs.appendFileSync(logPath, logEntry);

      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      };
    }

    if (name === "list_approved_emails") {
      const approvedDir = path.join(VAULT_PATH, "Approved");
      if (!fs.existsSync(approvedDir)) {
        return {
          content: [{ type: "text", text: JSON.stringify({ files: [] }) }],
        };
      }
      const files = fs
        .readdirSync(approvedDir)
        .filter((f) => f.endsWith(".md"));
      return {
        content: [{ type: "text", text: JSON.stringify({ files }, null, 2) }],
      };
    }

    return {
      content: [{ type: "text", text: `Unknown tool: ${name}` }],
      isError: true,
    };
  } catch (error) {
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({ error: error.message }, null, 2),
        },
      ],
      isError: true,
    };
  }
});

// ── Start server ──────────────────────────────────────────────────────────────

const transport = new StdioServerTransport();
await server.connect(transport);
console.error(`Email MCP server running | DRY_RUN=${DRY_RUN}`);
