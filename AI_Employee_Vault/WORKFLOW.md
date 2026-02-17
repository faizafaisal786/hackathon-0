# AI Employee - Overall Architecture

## System Flow (Simple)

```
              Incoming Message
              (Email / WhatsApp / LinkedIn / Manual)
                       |
                       v
              +--------+--------+
              |     INBOX       |  watcher.py auto-picks
              +-----------------+
                       |
                       v
              +--------+--------+
              |  NEEDS_ACTION   |  Task lands here
              +-----------------+
                       |
                       v
              +--------+--------+
              |   CLAUDE PLAN   |  claude_runner.py analyzes
              |   (Plans/)      |  Creates PLAN_*.md
              +-----------------+
                       |
                       v
              +--------+--------+
              | PENDING_APPROVAL|  Human reviews
              |                 |  Approve / Edit / Reject
              +-----------------+
                       |
                       v
              +--------+--------+
              |    APPROVED     |  Green light
              +-----------------+
                       |
                       v
              +--------+--------+
              |   REAL SEND     |  executor.py runs
              |                 |
              |  - Email        |
              |  - WhatsApp     |
              |  - LinkedIn     |
              +-----------------+
                       |
                       v
              +--------+--------+
              |   DONE + LOGS   |  Logs/YYYY-MM-DD.json
              |   + BRIEFING    |  Briefings/Monday_CEO.md
              +-----------------+
```

---

## Modules

```
AI_Employee/
|
|-- watcher.py           # Inbox --> Needs_Action (auto)
|-- claude_runner.py      # Needs_Action --> Plans (AI brain)
|-- executor.py           # Approved --> Done (execute + log)
|-- workflow.py           # Pipeline engine + stage management
|
|-- AI_Employee_Vault/
    |-- Inbox/            # Incoming tasks land here
    |-- Needs_Action/     # Awaiting AI analysis
    |-- Plans/            # PLAN_*.md structured plans
    |-- Pending_Approval/ # ACTION_*.md awaiting human OK
    |-- Approved/         # Green-lit, ready to execute
    |-- Done/             # Completed + archived
    |-- Logs/             # Daily JSON logs (2026-02-12.json)
    |-- Briefings/        # CEO reports (Monday_CEO.md)
    |-- WORKFLOW.md       # This file
```

---

## Module Responsibilities

### watcher.py - The Gatekeeper
```
Inbox/ --> Needs_Action/
```
- Runs continuously (every 5 seconds)
- Auto-moves new files from Inbox to Needs_Action
- No human intervention needed

### claude_runner.py - The Brain
```
Needs_Action/ --> Plans/
```
- Reads task files from Needs_Action
- Analyzes content and requirements
- Creates structured PLAN_*.md in Plans
- Moves action file to Pending_Approval

### executor.py - The Doer
```
Approved/ --> Done/ + Logs/
```
- Picks up approved tasks
- Executes real actions (send email, message, etc.)
- Moves completed files to Done
- Logs every action in daily JSON

### workflow.py - The Engine
```
Pipeline management + stage transitions
```
- Defines all 6 workflow stages
- Handles file movement between stages
- Maintains audit trail in Logs

---

## Communication Channels (Real Send)

| Channel   | Use Case                    | Status          |
|-----------|-----------------------------|-----------------|
| Email     | Client replies, follow-ups  | To Implement    |
| WhatsApp  | Quick updates, alerts       | To Implement    |
| LinkedIn  | Professional outreach       | To Implement    |

### How Real Send Works

```
Approved Task
     |
     v
executor.py reads ACTION_*.md
     |
     +-- Detects channel (email/whatsapp/linkedin)
     |
     +-- Sends via API
     |       |-- Email: SMTP / Gmail API
     |       |-- WhatsApp: Twilio / WhatsApp Business API
     |       |-- LinkedIn: LinkedIn API
     |
     +-- Moves to Done/
     |
     +-- Logs result in Logs/YYYY-MM-DD.json
```

---

## Data Flow Example

```
1. CEO drops "reply_client.txt" in Inbox/
                    |
2. watcher.py       | auto-moves (5 sec)
                    v
3. Needs_Action/reply_client.txt
                    |
4. claude_runner.py | reads + analyzes
                    v
5. Plans/PLAN_reply_client.md (structured plan + draft)
                    |
6. Human            | reviews draft
                    v
7. Pending_Approval/ACTION_reply_client.md
                    |
8. Human            | approves
                    v
9. Approved/ACTION_reply_client.md
                    |
10. executor.py     | sends email + moves + logs
                    v
11. Done/ACTION_reply_client.md
    Logs/2026-02-12.json  -->  {"task": "reply_client", "status": "Completed", "time": "05:44 AM"}
    Briefings/Monday_CEO.md  -->  updated automatically
```

---

## Log Format

**File:** `Logs/YYYY-MM-DD.json`

```json
[
  {
    "task": "ACTION_client_email_reply",
    "status": "Completed",
    "time": "05:44 AM"
  }
]
```

---

## CEO Briefing Format

**File:** `Briefings/Monday_CEO.md`

Contains:
- Tasks completed this week
- Pending approvals needing attention
- Pipeline snapshot (what's where)
- System health + suggestions

---

## Current System Status

| Component        | File                | Status              |
|------------------|---------------------|---------------------|
| Gatekeeper       | watcher.py          | Active              |
| Brain            | claude_runner.py    | Active              |
| Doer             | executor.py         | Active + Logging    |
| Engine           | workflow.py         | Active              |
| Master Demo      | main.py             | Active (3 modes)    |
| Logging          | Logs/*.json         | Active              |
| Briefings        | Briefings/*.md      | Active              |
| Email Send       | email_sender.py     | Active (SMTP/Demo)  |
| WhatsApp Send    | whatsapp_sender.py  | Active (Twilio/Sim) |
| LinkedIn Send    | linkedin_sender.py  | Active (API/Sim)    |

---

## Run Commands

```bash
python main.py --demo     # Full auto demo (hackathon presentation)
python main.py --live     # Interactive mode (human approves each task)
python main.py --status   # Show pipeline status only
```
