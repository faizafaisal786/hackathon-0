---
last_updated: 2026-03-13
version: 2.0
tier: platinum
---

# Company Handbook — Platinum Tier Rules of Engagement

> This handbook governs BOTH the Cloud Agent and the Local Agent. Always read before acting.

---

## 1. Work Zone Ownership

### Cloud Agent Owns (runs 24/7)
- Email triage and draft replies
- Social media post drafting and scheduling (DRAFT ONLY)
- Monitoring /Needs_Action/email/ and /Needs_Action/social/
- Writing to /Updates/ and /Pending_Approval/

### Local Agent Owns (runs when machine is on)
- All human approvals (reviewing /Pending_Approval/)
- WhatsApp session management
- Final "send" / "post" execution
- All payment and banking actions
- Merging Cloud updates into Dashboard.md (single-writer rule)

### Neither Agent May
- Store secrets in vault markdown
- Skip the HITL approval for payments, sends, or posts
- Modify the other agent's /In_Progress/ folder
- Write to Dashboard.md (Cloud writes to /Updates/ only)

---

## 2. Claim-by-Move Rule

To prevent double-work:
1. Agent finds item in `/Needs_Action/<domain>/`
2. Agent **moves** it to `/In_Progress/<agent>/` — this claims it
3. Other agent sees it in `/In_Progress/` and ignores it
4. When done, agent moves to `/Done/`

**First agent to move = owner. No exceptions.**

---

## 3. Communication Rules

- Polite and professional in all client-facing replies.
- Draft-only for new contacts — never auto-send.
- Flag: "urgent", "payment", "invoice", "legal", "contract", "refund".
- WhatsApp replies: Local agent only (session lives locally).

---

## 4. Financial Rules

- **All payments > $50**: Require human approval, always.
- **New payees**: Always require human approval, regardless of amount.
- **Odoo invoices**: Cloud drafts, Local approves before posting.
- Banking credentials: LOCAL ONLY — never sync to cloud vault.

---

## 5. Vault Sync Security Rules

These items **NEVER sync** to cloud:
- `.env` files
- WhatsApp session files
- Banking credentials
- API tokens
- `*.key`, `*.pem`, `*.p12` files

Vault sync includes ONLY: `.md` files, `.json` logs, `.gitkeep`

---

## 6. Escalation

Escalate immediately if:
- Payment > $100 or new payee
- Legal / contract message
- Unrecognized sender requesting data
- 3+ process restarts in 1 hour
- Vault sync conflict

---

## 7. Scheduled Operations

| Task | Schedule | Owner |
|------|----------|-------|
| Email check | Every 2 min | Cloud |
| Social monitoring | Every 15 min | Cloud |
| Finance check | Every 30 min | Cloud |
| Vault sync | Every 5 min | Git/Syncthing |
| Daily briefing | 8:00 AM | Local |
| Weekly audit | Sunday 10 PM | Cloud drafts, Local finalizes |
| CEO Briefing | Monday 7 AM | Cloud drafts, Local sends |
| Odoo health check | Every 1 hour | Cloud |
