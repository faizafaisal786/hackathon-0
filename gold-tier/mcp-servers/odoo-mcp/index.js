#!/usr/bin/env node
/**
 * odoo-mcp/index.js — Odoo Community MCP Server (Gold Tier)
 * ==========================================================
 * Integrates with Odoo 19+ via JSON-RPC External API.
 * DRAFT-ONLY mode by default — all writes require human approval.
 *
 * Tools: list_invoices, create_invoice_draft, get_accounting_summary,
 *        list_customers, get_transactions
 *
 * Docs: https://www.odoo.com/documentation/19.0/developer/reference/external_api.html
 *
 * Setup:
 *   npm install @modelcontextprotocol/sdk node-fetch
 *   ODOO_URL=http://localhost:8069 ODOO_DB=mydb ODOO_USER=admin ODOO_PASSWORD=admin
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

// ─── Config ──────────────────────────────────────────────────────────────────

const ODOO_URL = process.env.ODOO_URL || "http://localhost:8069";
const ODOO_DB = process.env.ODOO_DB || "odoo";
const ODOO_USER = process.env.ODOO_USER || "admin";
const ODOO_PASSWORD = process.env.ODOO_PASSWORD;
const DRAFT_ONLY = process.env.ODOO_DRAFT_ONLY !== "false"; // Default: true

if (!ODOO_PASSWORD) {
  console.error("Warning: ODOO_PASSWORD not set. Set it via environment variable.");
}

// ─── Odoo JSON-RPC Client ─────────────────────────────────────────────────────

let _uid = null;

async function odooCall(endpoint, params) {
  const res = await fetch(`${ODOO_URL}${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", method: "call", params }),
  });
  const data = await res.json();
  if (data.error) throw new Error(data.error.data?.message || JSON.stringify(data.error));
  return data.result;
}

async function authenticate() {
  if (_uid) return _uid;
  _uid = await odooCall("/web/dataset/call_kw", {
    model: "res.users",
    method: "authenticate",
    args: [ODOO_DB, ODOO_USER, ODOO_PASSWORD, {}],
    kwargs: {},
  });
  // Standard auth endpoint
  _uid = await odooCall("/web/session/authenticate", {
    db: ODOO_DB,
    login: ODOO_USER,
    password: ODOO_PASSWORD,
  });
  return _uid?.uid;
}

async function odooExecute(model, method, args = [], kwargs = {}) {
  return odooCall("/web/dataset/call_kw", {
    model,
    method,
    args,
    kwargs: { context: {}, ...kwargs },
  });
}

// ─── Tool Implementations ─────────────────────────────────────────────────────

async function listInvoices({ state = "open", limit = 10 }) {
  const domain = state === "all" ? [] : [["state", "=", state]];
  const invoices = await odooExecute("account.move", "search_read", [domain], {
    fields: ["name", "partner_id", "amount_total", "state", "invoice_date", "invoice_date_due"],
    limit,
    order: "invoice_date desc",
  });
  return { invoices, count: invoices.length };
}

async function createInvoiceDraft({ partner_name, amount, description, currency = "USD" }) {
  if (DRAFT_ONLY) {
    // Return what WOULD be created — requires human approval to actually post
    return {
      draft_only: true,
      message: "Invoice draft prepared. Move approval file to /Approved to post in Odoo.",
      proposed: { partner_name, amount, description, currency },
    };
  }

  // Find partner
  const partners = await odooExecute("res.partner", "search_read", [[["name", "ilike", partner_name]]], {
    fields: ["id", "name"],
    limit: 1,
  });
  if (!partners.length) throw new Error(`Partner not found: ${partner_name}`);

  const invoice = await odooExecute("account.move", "create", [{
    move_type: "out_invoice",
    partner_id: partners[0].id,
    invoice_line_ids: [[0, 0, { name: description, price_unit: amount }]],
  }]);

  return { success: true, invoice_id: invoice, state: "draft" };
}

async function getAccountingSummary() {
  const [receivable, payable] = await Promise.all([
    odooExecute("account.move", "search_read",
      [[["move_type", "=", "out_invoice"], ["state", "=", "posted"], ["payment_state", "!=", "paid"]]],
      { fields: ["amount_residual"], limit: 100 }
    ),
    odooExecute("account.move", "search_read",
      [[["move_type", "=", "in_invoice"], ["state", "=", "posted"], ["payment_state", "!=", "paid"]]],
      { fields: ["amount_residual"], limit: 100 }
    ),
  ]);

  const totalReceivable = receivable.reduce((s, i) => s + (i.amount_residual || 0), 0);
  const totalPayable = payable.reduce((s, i) => s + (i.amount_residual || 0), 0);

  return {
    accounts_receivable: totalReceivable.toFixed(2),
    accounts_payable: totalPayable.toFixed(2),
    net_position: (totalReceivable - totalPayable).toFixed(2),
    open_invoices: receivable.length,
    open_bills: payable.length,
  };
}

async function listCustomers({ limit = 20 }) {
  const customers = await odooExecute("res.partner", "search_read",
    [[["customer_rank", ">", 0]]],
    { fields: ["name", "email", "phone", "customer_rank"], limit }
  );
  return { customers, count: customers.length };
}

// ─── MCP Server ──────────────────────────────────────────────────────────────

const server = new Server(
  { name: "odoo-mcp", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "list_invoices",
      description: "List invoices from Odoo. Safe read-only operation.",
      inputSchema: {
        type: "object",
        properties: {
          state: { type: "string", enum: ["open", "draft", "paid", "all"], default: "open" },
          limit: { type: "number", default: 10 },
        },
      },
    },
    {
      name: "create_invoice_draft",
      description: "Prepare an invoice draft in Odoo. DRAFT ONLY — requires human approval to post.",
      inputSchema: {
        type: "object",
        properties: {
          partner_name: { type: "string" },
          amount: { type: "number" },
          description: { type: "string" },
          currency: { type: "string", default: "USD" },
        },
        required: ["partner_name", "amount", "description"],
      },
    },
    {
      name: "get_accounting_summary",
      description: "Get accounts receivable/payable summary from Odoo.",
      inputSchema: { type: "object", properties: {} },
    },
    {
      name: "list_customers",
      description: "List customers from Odoo CRM.",
      inputSchema: {
        type: "object",
        properties: { limit: { type: "number", default: 20 } },
      },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  try {
    let result;
    if (name === "list_invoices") result = await listInvoices(args);
    else if (name === "create_invoice_draft") result = await createInvoiceDraft(args);
    else if (name === "get_accounting_summary") result = await getAccountingSummary();
    else if (name === "list_customers") result = await listCustomers(args);
    else throw new Error(`Unknown tool: ${name}`);
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  } catch (err) {
    return { content: [{ type: "text", text: `Error: ${err.message}` }], isError: true };
  }
});

const transport = new StdioServerTransport();
await server.connect(transport);
console.error(`Odoo MCP Server running | URL: ${ODOO_URL} | Draft-only: ${DRAFT_ONLY}`);
