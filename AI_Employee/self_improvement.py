"""
PLATINUM Self-Improvement Engine
==================================
Analyzes completed tasks and automatically improves AI prompts.

Runs every IMPROVEMENT_INTERVAL loop passes (default: 10).

What it does:
  1. Reads Done/ folder for outcome signals (rejections, quality scores)
  2. Reads stats from memory_manager
  3. Applies 4 improvement rules to adjust prompts
  4. Saves improved prompts back to memory/prompts.json
  5. Logs every improvement for audit

Rules:
  RULE 1 -- High rejection rate   -> add caution to THINK prompt
  RULE 2 -- Low quality scores    -> add quality rules to EXECUTE prompt
  RULE 3 -- Channel dominance     -> add channel bias hint to THINK prompt
  RULE 4 -- Consistently high     -> calibrate REVIEWER to maintain standards
"""

import json
import re
from datetime import datetime
from pathlib import Path

from memory_manager import (
    get_improved_prompt,
    update_prompt,
    get_stats,
    _ensure_memory,
    MEMORY_DIR,
)

# ── Paths ─────────────────────────────────────────────────────────────────────
VAULT            = Path(__file__).parent / "AI_Employee_Vault"
DONE_DIR         = VAULT / "Done"
IMPROVEMENT_LOG  = MEMORY_DIR / "improvement_log.json"


# ── Internal helpers ──────────────────────────────────────────────────────────

def _log_improvement(reason: str, metric: str, before_snippet: str, after_snippet: str):
    """Append one improvement record to improvement_log.json."""
    _ensure_memory()
    if IMPROVEMENT_LOG.exists():
        with open(IMPROVEMENT_LOG, "r", encoding="utf-8") as f:
            log = json.load(f)
    else:
        log = {"improvements": [], "total": 0}

    log["total"] = log.get("total", 0) + 1
    log["improvements"].append({
        "id":             f"IMP-{log['total']:04d}",
        "timestamp":      datetime.now().isoformat(),
        "metric":         metric,
        "reason":         reason,
        "before_snippet": before_snippet[:120],
        "after_snippet":  after_snippet[:120],
    })

    with open(IMPROVEMENT_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


def _read_stats_from_log() -> dict:
    """Read outcome statistics from improvement_log.json."""
    if not IMPROVEMENT_LOG.exists():
        return {}
    with open(IMPROVEMENT_LOG, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


# ── Main analysis ─────────────────────────────────────────────────────────────

def analyze_done_folder() -> dict:
    """
    Scan Done/ folder and extract outcome signals.
    Returns insights dict with counts and patterns.
    """
    if not DONE_DIR.exists():
        return {}

    done_files = list(DONE_DIR.glob("*.md"))
    if not done_files:
        return {}

    insights = {
        "total_done":       len(done_files),
        "rejected_count":   0,
        "executed_count":   0,
        "channels":         {},
        "rejection_signals": [],
        "quality_signals":  [],
    }

    for file_path in done_files:
        try:
            content = file_path.read_text(encoding="utf-8")
            content_upper = content.upper()

            if "REJECTED" in content_upper or "REJECTION" in content_upper:
                insights["rejected_count"] += 1
                # Extract context around rejection keyword
                for match in re.finditer(r'(?i)reject\w*', content):
                    start = max(0, match.start() - 80)
                    end   = min(len(content), match.end() + 80)
                    insights["rejection_signals"].append(content[start:end].strip())
            else:
                insights["executed_count"] += 1

            # Extract channel
            ch_match = re.search(r'(?i)channel[:\s]+(\w+)', content)
            if ch_match:
                ch = ch_match.group(1).strip()
                insights["channels"][ch] = insights["channels"].get(ch, 0) + 1

            # Extract quality scores (reviewer format: "score": 8)
            score_match = re.search(r'"score"\s*:\s*(\d+)', content)
            if score_match:
                insights["quality_signals"].append(int(score_match.group(1)))

        except Exception:
            continue

    return insights


# ── Self-improvement rules ────────────────────────────────────────────────────

def improve_prompts() -> dict:
    """
    Main self-improvement function. Applies rules and updates prompts.
    Returns dict: {rule_name: "description of improvement made"}
    """
    stats    = get_stats()
    insights = analyze_done_folder()
    improvements = {}

    if not insights:
        return improvements

    total    = max(insights.get("total_done", 0), 1)
    rejected = insights.get("rejected_count", 0)
    executed = insights.get("executed_count", 0)
    rejection_rate = rejected / total

    avg_quality = stats.get("avg_quality_score", 7.0)
    total_processed = stats.get("total_processed", 0)

    # ── RULE 1: High rejection rate -> tighten THINK prompt ─────────────────
    if rejection_rate > 0.30 and total >= 5:
        key     = "system_think"
        current = get_improved_prompt(key)
        marker  = "[CAUTION-RULE-1]"
        if marker not in current:
            addition = (
                f"\n\n{marker} CAUTION (auto-added: rejection rate={rejection_rate:.1%}): "
                "Recent rejection rate is high. Be MORE conservative. "
                "If the task intent or channel is ambiguous, "
                "set action_required='review' rather than auto-sending. "
                "Prioritize accuracy over speed."
            )
            improved = current + addition
            update_prompt(key, improved)
            improvements["think_caution_added"] = (
                f"Rejection rate {rejection_rate:.1%} (>{30}%) -> added caution rule to THINK"
            )
            _log_improvement(
                reason=f"High rejection rate: {rejection_rate:.1%}",
                metric="rejection_rate",
                before_snippet=current[-80:],
                after_snippet=addition[:80],
            )
            print(f"  [IMPROVE] RULE 1 applied: THINK prompt tightened (rejection={rejection_rate:.1%})")

    # ── RULE 2: Low quality scores -> improve EXECUTE prompt ────────────────
    if avg_quality < 6.5 and total_processed >= 5:
        key     = "system_execute"
        current = get_improved_prompt(key)
        marker  = "[QUALITY-RULE-2]"
        if marker not in current:
            addition = (
                f"\n\n{marker} QUALITY BOOST (auto-added: avg_score={avg_quality:.1f}): "
                "Reviewer scores have been below threshold. Every drafted response MUST: "
                "(1) Open with a direct reference to the task. "
                "(2) Include specific, concrete details -- no vague statements. "
                "(3) End with a clear next step or call to action. "
                "(4) Match the channel tone exactly (formal for Email, casual for WhatsApp, "
                "engaging for LinkedIn)."
            )
            improved = current + addition
            update_prompt(key, improved)
            improvements["execute_quality_boosted"] = (
                f"Avg quality {avg_quality:.1f} (<6.5) -> added quality rules to EXECUTE"
            )
            _log_improvement(
                reason=f"Low quality score: avg={avg_quality:.1f}",
                metric="avg_quality_score",
                before_snippet=current[-80:],
                after_snippet=addition[:80],
            )
            print(f"  [IMPROVE] RULE 2 applied: EXECUTE prompt quality-boosted (avg_score={avg_quality:.1f})")

    # ── RULE 3: Dominant channel -> add detection bias hint ─────────────────
    channels = insights.get("channels", {})
    if channels and total >= 5:
        dominant_ch    = max(channels, key=channels.get)
        dominant_count = channels[dominant_ch]
        dominance_rate = dominant_count / total

        if dominance_rate > 0.75:
            key     = "system_think"
            current = get_improved_prompt(key)
            marker  = f"[CHANNEL-BIAS-{dominant_ch}]"
            if marker not in current:
                addition = (
                    f"\n\n{marker} PATTERN (auto-added: {dominant_ch}={dominance_rate:.1%}): "
                    f"Historical data shows {dominant_ch} is the dominant channel "
                    f"({dominant_count}/{total} tasks). "
                    f"When channel is ambiguous, lean toward {dominant_ch}."
                )
                improved = current + addition
                update_prompt(key, improved)
                improvements["channel_bias_added"] = (
                    f"{dominant_ch} dominates at {dominance_rate:.1%} -> added detection hint"
                )
                _log_improvement(
                    reason=f"Channel dominance: {dominant_ch}={dominance_rate:.1%}",
                    metric="channel_dominance",
                    before_snippet=current[-80:],
                    after_snippet=addition[:80],
                )
                print(f"  [IMPROVE] RULE 3 applied: Channel bias {dominant_ch} added to THINK")

    # ── RULE 4: Consistently high quality -> calibrate reviewer ─────────────
    total_success = stats.get("total_success", 0)
    if avg_quality >= 8.0 and total_success >= 10:
        key     = "system_review"
        current = get_improved_prompt(key)
        marker  = "[CALIBRATION-RULE-4]"
        if marker not in current:
            addition = (
                f"\n\n{marker} CALIBRATION (auto-added: avg_score={avg_quality:.1f}, "
                f"successes={total_success}): "
                "System is performing well. Maintain high standards. "
                "Score >= 7 only when content genuinely meets all criteria. "
                "Do not inflate scores -- this trains the system to stay excellent."
            )
            improved = current + addition
            update_prompt(key, improved)
            improvements["reviewer_calibrated"] = (
                f"High performance (avg={avg_quality:.1f}, success={total_success}) "
                "-> reviewer calibrated"
            )
            _log_improvement(
                reason=f"High consistent quality: avg={avg_quality:.1f}",
                metric="high_performance",
                before_snippet=current[-80:],
                after_snippet=addition[:80],
            )
            print(f"  [IMPROVE] RULE 4 applied: Reviewer calibrated (avg={avg_quality:.1f})")

    # ── Update stats with improvement count ────────────────────────────────
    if improvements:
        from memory_manager import STATS_FILE
        if STATS_FILE.exists():
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                s = json.load(f)
            s["total_improvements"]   = s.get("total_improvements", 0) + len(improvements)
            s["last_improvement_run"] = datetime.now().isoformat()
            with open(STATS_FILE, "w", encoding="utf-8") as f:
                json.dump(s, f, indent=2, ensure_ascii=False)

    return improvements


def get_improvement_log() -> list:
    """Return all historical improvement records."""
    if not IMPROVEMENT_LOG.exists():
        return []
    with open(IMPROVEMENT_LOG, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("improvements", [])


def get_improvement_summary() -> str:
    """Return a human-readable improvement summary for the dashboard."""
    log   = get_improvement_log()
    stats = get_stats()
    if not log:
        return "No improvements yet."
    lines = [
        f"Total improvements: {len(log)}",
        f"Last run: {stats.get('last_improvement_run', 'Never')}",
        "Recent:",
    ]
    for imp in log[-3:]:
        lines.append(f"  [{imp['timestamp'][:10]}] {imp['reason']}")
    return "\n".join(lines)
