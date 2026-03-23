"""
PLATINUM Memory Manager
========================
Stores and retrieves task memories for context injection into AI prompts.
Uses JSON storage + cosine similarity (pure Python, zero extra dependencies).

Memory Record Schema:
{
  "id": "MEM-0001",
  "timestamp": "2026-02-24T10:00:00",
  "task_hash": "abc123def456",
  "filename": "email_client.md",
  "channel": "Email",
  "intent": "Send follow-up email to client about proposal",
  "outcome": "SUCCESS",            # PENDING / SUCCESS / FAILED / REJECTED
  "quality_score": 8,              # 1-10 from Reviewer
  "was_rejected": false,
  "ai_backend": "groq",
  "revisions_needed": 0,
  "confidence": 0.85,
  "drafted_response_snippet": "first 200 chars of output...",
  "tags": ["email", "client", "formal"]
}
"""

import json
import math
import re
import hashlib
from datetime import datetime
from pathlib import Path
from collections import Counter

# ── Paths ────────────────────────────────────────────────────────────────────
MEMORY_DIR  = Path(__file__).parent / "memory"
MEMORY_FILE = MEMORY_DIR / "tasks.json"
PROMPT_FILE = MEMORY_DIR / "prompts.json"
STATS_FILE  = MEMORY_DIR / "stats.json"

# ── Default base prompts (improved over time by self_improvement.py) ─────────
_DEFAULT_PROMPTS = {
    "system_think": (
        "You are an AI Employee Thinker. Analyze incoming tasks with deep understanding.\n"
        "Consider channel, intent, recipient, and tone carefully.\n"
        "Use past task patterns when available to make better decisions.\n"
        "Return ONLY valid JSON."
    ),
    "system_plan": (
        "You are an AI Employee Planner. Create precise, executable action plans.\n"
        "Each step must be specific, achievable, and ordered logically.\n"
        "Return ONLY valid JSON."
    ),
    "system_execute": (
        "You are an AI Employee Executor. Draft perfect, ready-to-send content.\n"
        "Quality over speed. Every sentence must add value.\n"
        "Return ONLY the message content -- no labels, no JSON."
    ),
    "system_review": (
        "You are a Quality Reviewer for an AI Employee system.\n"
        "Review drafted content for quality, accuracy, and channel-appropriateness.\n"
        "Be strict but fair. Score 1-10. Return ONLY valid JSON."
    ),
}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _ensure_memory():
    """Create memory directory and default files if they don't exist."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    if not MEMORY_FILE.exists():
        MEMORY_FILE.write_text(json.dumps({
            "version": "1.0",
            "memories": [],
            "total": 0,
        }, indent=2), encoding="utf-8")

    if not PROMPT_FILE.exists():
        PROMPT_FILE.write_text(json.dumps({
            "version": "1.0",
            "current_version": "v1",
            "last_updated": datetime.now().isoformat(),
            "prompts": _DEFAULT_PROMPTS,
        }, indent=2), encoding="utf-8")

    if not STATS_FILE.exists():
        STATS_FILE.write_text(json.dumps({
            "total_processed": 0,
            "total_success": 0,
            "total_failed": 0,
            "total_rejected": 0,
            "channel_counts": {},
            "avg_quality_score": 0.0,
            "backend_usage": {},
            "total_improvements": 0,
            "last_improvement_run": None,
        }, indent=2), encoding="utf-8")


def _tokenize(text: str) -> list:
    """Simple word tokenizer -- lowercases and extracts 2+ char words."""
    return re.findall(r'\b[a-z]{2,}\b', text.lower())


def _build_idf(memories: list) -> dict:
    """Build inverse document frequency table from all memory records."""
    n_docs = len(memories) + 1
    word_doc_count = Counter()
    for mem in memories:
        words = set(_tokenize(
            mem.get("intent", "") + " " + mem.get("filename", "") + " " + mem.get("channel", "")
        ))
        word_doc_count.update(words)
    return {
        word: math.log(n_docs / (count + 1)) + 1
        for word, count in word_doc_count.items()
    }


def _tfidf_vector(text: str, idf: dict) -> dict:
    """Compute TF-IDF sparse vector for a text string."""
    tokens = _tokenize(text)
    if not tokens:
        return {}
    tf = Counter(tokens)
    total = len(tokens)
    return {
        word: (count / total) * idf.get(word, 1.0)
        for word, count in tf.items()
    }


def _cosine_similarity(vec1: dict, vec2: dict) -> float:
    """Cosine similarity between two sparse TF-IDF vectors."""
    if not vec1 or not vec2:
        return 0.0
    common = set(vec1.keys()) & set(vec2.keys())
    if not common:
        return 0.0
    dot   = sum(vec1[w] * vec2[w] for w in common)
    mag1  = math.sqrt(sum(v ** 2 for v in vec1.values()))
    mag2  = math.sqrt(sum(v ** 2 for v in vec2.values()))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)


# ── Public API ────────────────────────────────────────────────────────────────

def save_memory(record: dict):
    """Save or update a task memory record (deduplicates by task hash)."""
    _ensure_memory()
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    memories = data.get("memories", [])

    # Compute hash for deduplication
    raw_key = record.get("filename", "") + record.get("intent", "")
    task_hash = hashlib.md5(raw_key.encode()).hexdigest()[:10]
    record["task_hash"] = task_hash
    record["timestamp"] = datetime.now().isoformat()

    # Update if exists, insert if new
    existing_idx = next(
        (i for i, m in enumerate(memories) if m.get("task_hash") == task_hash),
        None
    )
    if existing_idx is not None:
        memories[existing_idx].update(record)
    else:
        count = data.get("total", 0) + 1
        record["id"] = f"MEM-{count:04d}"
        memories.append(record)
        data["total"] = count

    data["memories"] = memories
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def retrieve_similar(query: str, channel: str = None, top_k: int = 3) -> list:
    """
    Retrieve top_k most similar past task memories to the query.
    Optionally filtered by channel. Returns list of memory records.
    """
    _ensure_memory()
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    memories = data.get("memories", [])
    if not memories:
        return []

    # Prefer same-channel memories; fall back to all if none
    candidates = [m for m in memories if m.get("channel") == channel] if channel else memories
    if not candidates:
        candidates = memories

    # Prefer successful tasks
    good = [m for m in candidates if m.get("outcome") in ("SUCCESS", "PENDING")]
    if good:
        candidates = good

    idf       = _build_idf(candidates)
    query_vec = _tfidf_vector(query, idf)

    scored = []
    for mem in candidates:
        mem_text = " ".join([
            mem.get("intent", ""),
            mem.get("filename", ""),
            mem.get("channel", ""),
        ])
        mem_vec = _tfidf_vector(mem_text, idf)
        score   = _cosine_similarity(query_vec, mem_vec)
        scored.append((score, mem))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [mem for _, mem in scored[:top_k]]


def format_memory_context(memories: list) -> str:
    """Format retrieved memories as a context string for AI prompts."""
    if not memories:
        return ""
    lines = ["\n--- RELEVANT PAST TASKS (use for better decisions) ---"]
    for i, mem in enumerate(memories, 1):
        lines.append(f"[Past Task {i}]")
        lines.append(f"  Channel:       {mem.get('channel', 'Unknown')}")
        lines.append(f"  Intent:        {mem.get('intent', 'N/A')}")
        lines.append(f"  Outcome:       {mem.get('outcome', 'Unknown')}")
        lines.append(f"  Quality Score: {mem.get('quality_score', 'N/A')}/10")
        lines.append(f"  Revisions:     {mem.get('revisions_needed', 0)}")
        snippet = mem.get("drafted_response_snippet", "")
        if snippet:
            lines.append(f"  Sample:        {snippet[:120]}...")
    lines.append("--- END PAST TASKS ---\n")
    return "\n".join(lines)


def update_memory_outcome(filename: str, outcome: str):
    """Update a memory record's outcome after execution (SUCCESS/FAILED/REJECTED)."""
    _ensure_memory()
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    memories = data.get("memories", [])
    base_name = Path(filename).stem.replace("ACTION_", "").replace("PLAN_", "")
    updated = False
    for mem in memories:
        mem_base = Path(mem.get("filename", "")).stem
        if mem_base == base_name or base_name in mem_base:
            mem["outcome"]      = outcome
            mem["was_rejected"] = outcome == "REJECTED"
            updated = True
            break
    if updated:
        data["memories"] = memories
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


def get_improved_prompt(prompt_key: str) -> str:
    """Get the current (possibly self-improved) prompt for a role."""
    _ensure_memory()
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    stored = data.get("prompts", {}).get(prompt_key, "")
    return stored if stored else _DEFAULT_PROMPTS.get(prompt_key, "")


def update_prompt(prompt_key: str, new_prompt: str, version: str = None):
    """Persist an improved prompt (called by self_improvement.py)."""
    _ensure_memory()
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["prompts"][prompt_key] = new_prompt
    if version:
        data["current_version"] = version
    data["last_updated"] = datetime.now().isoformat()
    with open(PROMPT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def update_stats(channel: str, outcome: str, quality_score: float, backend: str):
    """Update running statistics after each task."""
    _ensure_memory()
    with open(STATS_FILE, "r", encoding="utf-8") as f:
        stats = json.load(f)

    stats["total_processed"] = stats.get("total_processed", 0) + 1
    if outcome == "SUCCESS":
        stats["total_success"]  = stats.get("total_success", 0) + 1
    elif outcome == "FAILED":
        stats["total_failed"]   = stats.get("total_failed", 0) + 1
    elif outcome == "REJECTED":
        stats["total_rejected"] = stats.get("total_rejected", 0) + 1

    ch             = stats.get("channel_counts", {})
    ch[channel]    = ch.get(channel, 0) + 1
    stats["channel_counts"] = ch

    n             = stats["total_processed"]
    prev_avg      = stats.get("avg_quality_score", 0.0)
    stats["avg_quality_score"] = round(
        (prev_avg * (n - 1) + quality_score) / n, 2
    )

    bk             = stats.get("backend_usage", {})
    bk[backend]    = bk.get(backend, 0) + 1
    stats["backend_usage"]  = bk
    stats["last_updated"]   = datetime.now().isoformat()

    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)


def get_stats() -> dict:
    """Return current system statistics."""
    _ensure_memory()
    with open(STATS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
