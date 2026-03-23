# Company Handbook

## Company Overview

**Company Name:** AI Employee Systems
**Type:** AI-Powered Business Automation
**Version:** 2.0 — Platinum Pipeline

---

## AI Employee Role & Responsibilities

The AI Employee autonomously handles business communication and task execution across multiple channels:

- **Email** — Client communication, proposals, meeting follow-ups
- **WhatsApp** — Quick client updates, reminders, short messages
- **LinkedIn** — Marketing posts, hiring announcements, product launches
- **General** — Reports, documents, internal notes

---

## Communication Guidelines

### Tone Policy
| Channel | Tone |
|---------|------|
| Email | Formal, professional |
| WhatsApp | Friendly, concise (2–4 sentences max) |
| LinkedIn | Engaging, insightful, ends with hashtags |
| General | Professional, structured |

### Quality Standard
- All content must score **7/10 or above** before dispatch
- Content scoring below 7 is automatically revised (max 2 revision rounds)
- Final output is logged and archived in `/Done`

---

## Workflow Pipeline

```
Inbox → Needs_Action → Plans → Pending_Approval → Approved → Done
                                      ↓
                                  Rejected → Done
```

| Stage | Description |
|-------|-------------|
| `/Inbox` | New tasks dropped here by user or watcher |
| `/Needs_Action` | Tasks picked up by watcher, awaiting AI processing |
| `/Plans` | AI-generated execution plans stored here |
| `/Pending_Approval` | Completed drafts awaiting human approval |
| `/Done` | Archived completed tasks |

---

## Agent Team

| Agent | Role |
|-------|------|
| **THINKER** | Understands task, picks channel, tone, priority |
| **PLANNER** | Creates step-by-step execution plan |
| **EXECUTOR** | Drafts final ready-to-send content |
| **REVIEWER** | Scores output 1–10, requests revision if needed |

---

## Escalation Policy

- Tasks scored **below 7** → auto-revised by Reviewer
- Tasks requiring **human approval** → moved to `/Pending_Approval`
- **High priority** tasks → flagged in `Dashboard.md`
- **Failed tasks** → logged in `/Logs` with error details

---

## Working Hours

- **Availability:** 24/7 automated via `watcher.py`
- **Monitoring interval:** Every 5 seconds (configurable)
- **Dashboard refresh:** Live mode available via `python dashboard.py --live`

---

## AI Backend Chain

```
Groq (Llama-3.3-70b)  →  Gemini (1.5 Flash)  →  Fallback (hardcoded)
```

System never crashes — fallback always available.

---

## Security Policy

- All API keys stored in `.env` (never committed to git)
- `.gitignore` protects secrets from version control
- No sensitive data written to vault markdown files
- All actions logged with timestamp and actor for full audit trail

---

## Memory & Learning

- Every completed task saved to `memory/tasks.json`
- Similar past tasks retrieved before processing new ones
- Prompts auto-improved based on performance via `self_improvement.py`
- Stats tracked per channel in `memory/stats.json`

---

## Log Files

| File | Purpose |
|------|---------|
| `Logs/YYYY-MM-DD.json` | Main audit log |
| `Logs/email_YYYY-MM-DD.json` | Email channel log |
| `Logs/whatsapp_YYYY-MM-DD.json` | WhatsApp channel log |
| `Logs/linkedin_YYYY-MM-DD.json` | LinkedIn channel log |

---

*Last Updated: 2026-03-11*
*AI Employee System v2.0 — Platinum Pipeline*
