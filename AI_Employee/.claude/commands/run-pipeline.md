# Agent Skill: Run Full Pipeline

Run the complete AI Employee pipeline — one full pass through all stages.

## Instructions

Run in sequence:

1. **INBOX PROCESSING**
   - Run `watcher.py` — move new files from Inbox → Needs_Action
   - Run `gmail_watcher.py` — fetch new Gmail → Inbox → Needs_Action

2. **ZONE ROUTING**
   - Run `claim_manager.py --route` — sort tasks into cloud/local zones

3. **AI PIPELINE** (for each task in Needs_Action)
   - THINKER: analyze intent
   - PLANNER: create execution plan
   - EXECUTOR: draft content/action
   - REVIEWER: score quality (≥7.0 passes)

4. **APPROVAL QUEUE**
   - Write action files to `Pending_Approval/`
   - Notify via Telegram if urgent

5. **EXECUTE APPROVED**
   - Run `local_agent.py` — process Approved/ folder, execute sends

6. **BRIEFING** (if Monday)
   - Generate CEO Briefing via `briefing_generator.py`

7. **DASHBOARD UPDATE**
   - Update `Dashboard.md` with full pipeline status

## Usage

```
/run-pipeline
```

## Equivalent to

```bash
python ralph_loop.py
```
