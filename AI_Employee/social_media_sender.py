"""
Social Media Sender Module -- Free Content Generation
======================================================
Generates ready-to-post content for LinkedIn, WhatsApp, Facebook, Instagram
using AI (Groq free tier) with graceful fallback templates.

All methods are COPY-READY -- no actual posting APIs required.
WhatsApp uses wa.me deep links (free, no Twilio needed).

Public API:
    generate_linkedin_post(content, filename)   -> str (status)
    generate_whatsapp_message(content, phone, filename) -> str (status)
    generate_facebook_post(content, filename)   -> str (status)
    generate_instagram_caption(content, filename) -> str (status)
    dispatch_social(channel, content, filename, phone) -> str (status)
    parse_social_from_action(file_path) -> dict
"""

import os
import re
import sys
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import quote


def _safe(text: str, max_len: int = 100) -> str:
    """Return a console-safe truncated preview (strips non-ASCII for Windows cp1252)."""
    preview = text[:max_len] if text else ""
    return preview.encode("ascii", errors="replace").decode("ascii")

# Try python-dotenv
try:
    from dotenv import load_dotenv
    _HAS_DOTENV = True
except ImportError:
    _HAS_DOTENV = False

# Try Groq
try:
    from groq import Groq
    _HAS_GROQ = True
except ImportError:
    _HAS_GROQ = False

# Try Gemini
try:
    import google.generativeai as genai
    _HAS_GEMINI = True
except ImportError:
    _HAS_GEMINI = False


# --------------------------------------------------
# CONFIG
# --------------------------------------------------

BASE_DIR = Path(__file__).parent
VAULT    = BASE_DIR / "AI_Employee_Vault"
DONE_DIR = VAULT / "Done"
LOGS_DIR = VAULT / "Logs"

GROQ_MODEL   = "llama-3.3-70b-versatile"
GEMINI_MODEL = "gemini-1.5-flash"

MAX_LINKEDIN_CHARS  = 3000
MAX_INSTAGRAM_CHARS = 2200

SOCIAL_CHANNELS = {"LinkedIn", "Facebook", "Instagram", "WhatsApp"}


# --------------------------------------------------
# CREDENTIAL LOADING
# --------------------------------------------------

def _load_env() -> dict:
    """Load API keys from .env file."""
    env_path = BASE_DIR / ".env"
    if _HAS_DOTENV:
        load_dotenv(env_path, override=False)
        return {
            "GROQ_API_KEY":   os.getenv("GROQ_API_KEY", ""),
            "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
        }
    config = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, val = line.split("=", 1)
                config[key.strip()] = val.strip()
    return config


# --------------------------------------------------
# AI GENERATION  (Groq -> Gemini -> template)
# --------------------------------------------------

def _call_ai(prompt: str, system: str = "", max_tokens: int = 800) -> str:
    """Call AI: Groq -> Gemini -> empty string (use template fallback)."""
    creds = _load_env()

    # -- Groq --
    if _HAS_GROQ:
        groq_key = creds.get("GROQ_API_KEY", "")
        if groq_key and "your_" not in groq_key:
            try:
                client   = Groq(api_key=groq_key)
                messages = []
                if system:
                    messages.append({"role": "system", "content": system})
                messages.append({"role": "user", "content": prompt})
                resp = client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=0.7,
                )
                return resp.choices[0].message.content.strip()
            except Exception as e:
                print(f"[Social] Groq failed: {e}, trying Gemini...")

    # -- Gemini --
    if _HAS_GEMINI:
        gemini_key = creds.get("GEMINI_API_KEY", "")
        if gemini_key and "your_" not in gemini_key:
            try:
                genai.configure(api_key=gemini_key)
                model       = genai.GenerativeModel(GEMINI_MODEL)
                full_prompt = f"{system}\n\n{prompt}" if system else prompt
                resp        = model.generate_content(full_prompt)
                return resp.text.strip()
            except Exception as e:
                print(f"[Social] Gemini failed: {e}, using template...")

    return ""


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def _extract_section(text: str, section: str) -> str:
    """Extract a named section block from AI response text."""
    pattern = rf"{section}:\s*\n(.*?)(?=\n[A-Z_]+:|$)"
    match   = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def _log_social(event: str, platform: str, filename: str, details: str):
    """Append social media event to daily JSON log."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    today    = datetime.now().strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"social_{today}.json"

    entries = []
    if log_file.exists():
        try:
            entries = json.loads(log_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            entries = []

    entries.append({
        "event":     event,
        "platform":  platform,
        "source":    filename,
        "details":   details,
        "timestamp": datetime.now().isoformat(),
    })
    log_file.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


# --------------------------------------------------
# LINKEDIN POST GENERATOR
# --------------------------------------------------

def generate_linkedin_post(content: str, filename: str = "social") -> str:
    """
    Generate a professional LinkedIn post from task content.

    Structure: Hook (1 line) + Post body (2-3 paragraphs) + Hashtags
    Saves to Done/LINKEDIN_POST_<timestamp>.md
    Returns: status string
    """
    DONE_DIR.mkdir(parents=True, exist_ok=True)

    system = (
        "You are a professional LinkedIn content writer. "
        "Write engaging, professional LinkedIn posts that get high engagement. "
        "Use proper paragraph breaks and a professional tone."
    )
    prompt = (
        f"Create a professional LinkedIn post about the following topic:\n\n"
        f"{content}\n\n"
        f"Format your response EXACTLY like this:\n\n"
        f"HOOK:\n[One powerful opening sentence that grabs attention]\n\n"
        f"POST:\n[2-3 paragraphs of professional content]\n\n"
        f"HASHTAGS:\n[5-8 relevant hashtags]"
    )

    ai_text  = _call_ai(prompt, system, max_tokens=600)

    if ai_text:
        hook     = _extract_section(ai_text, "HOOK")
        post     = _extract_section(ai_text, "POST")
        hashtags = _extract_section(ai_text, "HASHTAGS")
    else:
        hook     = "Excited to share something important with my network."
        post     = content[:500] if content else "Sharing professional insights."
        hashtags = "#LinkedIn #Professional #Business #Growth"

    if not hook:
        hook = (ai_text.split("\n")[0][:150] if ai_text else "Read this.")
    if not post:
        post = content[:500]
    if not hashtags:
        hashtags = "#LinkedIn #Professional"

    full_post = f"{hook}\n\n{post}\n\n{hashtags}"
    if len(full_post) > MAX_LINKEDIN_CHARS:
        full_post = full_post[:MAX_LINKEDIN_CHARS - 3] + "..."

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file  = DONE_DIR / f"LINKEDIN_POST_{timestamp}.md"

    md = (
        f"# LINKEDIN POST -- READY TO COPY\n\n"
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"**Source:** {filename}\n"
        f"**Platform:** LinkedIn\n"
        f"**Characters:** {len(full_post)} / {MAX_LINKEDIN_CHARS}\n\n"
        f"---\n\n"
        f"## HOOK (First Line)\n\n{hook}\n\n"
        f"---\n\n"
        f"## FULL POST (Copy this entire block)\n\n"
        f"```\n{full_post}\n```\n\n"
        f"---\n\n"
        f"## POSTING CHECKLIST\n\n"
        f"- [ ] Copy the FULL POST block above\n"
        f"- [ ] Go to LinkedIn -> Start a post\n"
        f"- [ ] Paste the content\n"
        f"- [ ] Add a relevant image/document\n"
        f"- [ ] Click Post\n\n"
        f"---\n\n"
        f"*Generated by AI Employee | Ralph Loop v3.0 PLATINUM*\n"
    )

    out_file.write_text(md, encoding="utf-8")

    print(f"[LinkedIn] Post ready   : {out_file.name}")
    print(f"[LinkedIn] Hook         : {_safe(hook, 80)}...")
    print(f"[LinkedIn] Chars        : {len(full_post)} / {MAX_LINKEDIN_CHARS}")

    _log_social("GENERATED", "LinkedIn", filename, f"Saved to {out_file.name}")
    return "LinkedIn post ready for publishing"


# --------------------------------------------------
# WHATSAPP MESSAGE GENERATOR  (wa.me links -- FREE)
# --------------------------------------------------

def generate_whatsapp_message(
    content: str, phone: str = "", filename: str = "social"
) -> str:
    """
    Generate a WhatsApp message with a free wa.me deep link.

    wa.me link format: https://wa.me/{phone}?text={url_encoded_message}
    No API key required.

    Saves to Done/WHATSAPP_MSG_<timestamp>.md
    Returns: status string
    """
    DONE_DIR.mkdir(parents=True, exist_ok=True)

    system = (
        "You are a professional business communication writer. "
        "Write clear, concise WhatsApp messages that are professional yet conversational."
    )
    prompt = (
        f"Write a professional WhatsApp message about:\n\n"
        f"{content}\n\n"
        f"Format EXACTLY like this:\n\n"
        f"MESSAGE:\n[Clear, professional WhatsApp message, max 300 words]\n\n"
        f"SUBJECT:\n[One line topic summary]"
    )

    ai_text = _call_ai(prompt, system, max_tokens=400)

    if ai_text:
        message = _extract_section(ai_text, "MESSAGE")
        subject = _extract_section(ai_text, "SUBJECT")
    else:
        message = content[:500] if content else "Hello, I wanted to reach out regarding an important matter."
        subject = "Important Message"

    if not message:
        message = content[:500]
    if not subject:
        subject = "Important Update"

    # Build wa.me link (strip + and spaces; wa.me uses digits only)
    clean_phone = re.sub(r"[^\d+]", "", phone) if phone else ""
    if clean_phone.startswith("+"):
        clean_phone = clean_phone[1:]

    encoded_msg = quote(message)
    if clean_phone:
        wame_link  = f"https://wa.me/{clean_phone}?text={encoded_msg}"
        wame_plain = f"https://wa.me/{clean_phone}"
    else:
        wame_link  = f"https://wa.me/?text={encoded_msg}"
        wame_plain = "https://wa.me/ (add phone number)"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file  = DONE_DIR / f"WHATSAPP_MSG_{timestamp}.md"

    md = (
        f"# WHATSAPP MESSAGE -- READY TO SEND\n\n"
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"**Source:** {filename}\n"
        f"**Platform:** WhatsApp\n"
        f"**Subject:** {subject}\n"
        f"**Recipient:** {phone if phone else 'Not specified'}\n\n"
        f"---\n\n"
        f"## MESSAGE (Copy this)\n\n"
        f"```\n{message}\n```\n\n"
        f"---\n\n"
        f"## ONE-CLICK SEND LINK\n\n"
        f"Click to open WhatsApp with the message pre-filled:\n\n"
        f"[Click to Send on WhatsApp]({wame_link})\n\n"
        f"**Direct link:** `{wame_plain}`\n\n"
        f"---\n\n"
        f"## HOW TO USE\n\n"
        f"**Option A (one-click):**\n"
        f"1. Click the link above -- opens WhatsApp Web or app\n"
        f"2. Message is pre-filled -- review and press Send\n\n"
        f"**Option B (manual):**\n"
        f"1. Open WhatsApp\n"
        f"2. Open the contact's chat\n"
        f"3. Paste the MESSAGE section above\n"
        f"4. Press Send\n\n"
        f"---\n\n"
        f"*Generated by AI Employee | Ralph Loop v3.0 PLATINUM*\n"
    )

    out_file.write_text(md, encoding="utf-8")

    print(f"[WhatsApp] Message ready : {out_file.name}")
    print(f"[WhatsApp] Subject       : {_safe(subject, 80)}")
    print(f"[WhatsApp] wa.me link    : {wame_plain}")

    _log_social("GENERATED", "WhatsApp", filename, f"Saved to {out_file.name}")
    return "WhatsApp message ready to send"


# --------------------------------------------------
# FACEBOOK POST GENERATOR
# --------------------------------------------------

def generate_facebook_post(content: str, filename: str = "social") -> str:
    """
    Generate a copy-ready Facebook post from task content.

    Structure: Headline + Body + Call to Action + Hashtags
    Saves to Done/FACEBOOK_POST_<timestamp>.md
    Returns: status string
    """
    DONE_DIR.mkdir(parents=True, exist_ok=True)

    system = (
        "You are a Facebook content specialist. "
        "Write engaging Facebook posts that drive interactions. "
        "Use conversational tone, emojis where appropriate, clear calls to action."
    )
    prompt = (
        f"Create an engaging Facebook post about:\n\n"
        f"{content}\n\n"
        f"Format EXACTLY like this:\n\n"
        f"HEADLINE:\n[One attention-grabbing opening line, can include emojis]\n\n"
        f"BODY:\n[2-3 paragraphs of engaging content with emojis]\n\n"
        f"CTA:\n[Clear call to action -- e.g. 'Comment below', 'Share this']\n\n"
        f"HASHTAGS:\n[4-6 relevant hashtags]"
    )

    ai_text = _call_ai(prompt, system, max_tokens=600)

    if ai_text:
        headline = _extract_section(ai_text, "HEADLINE")
        body     = _extract_section(ai_text, "BODY")
        cta      = _extract_section(ai_text, "CTA")
        hashtags = _extract_section(ai_text, "HASHTAGS")
    else:
        headline = "Important update for our community!"
        body     = content[:500] if content else "We have something important to share."
        cta      = "Let us know your thoughts in the comments below!"
        hashtags = "#Facebook #Community #Update"

    if not headline:
        headline = "Important Update"
    if not body:
        body = content[:500]
    if not cta:
        cta = "Share your thoughts in the comments!"
    if not hashtags:
        hashtags = "#Facebook #Business"

    full_post = f"{headline}\n\n{body}\n\n{cta}\n\n{hashtags}"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file  = DONE_DIR / f"FACEBOOK_POST_{timestamp}.md"

    md = (
        f"# FACEBOOK POST -- READY TO COPY\n\n"
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"**Source:** {filename}\n"
        f"**Platform:** Facebook\n"
        f"**Characters:** {len(full_post)}\n\n"
        f"---\n\n"
        f"## HEADLINE\n\n{headline}\n\n"
        f"---\n\n"
        f"## BODY\n\n{body}\n\n"
        f"---\n\n"
        f"## CALL TO ACTION\n\n{cta}\n\n"
        f"---\n\n"
        f"## HASHTAGS\n\n{hashtags}\n\n"
        f"---\n\n"
        f"## FULL POST (Copy this entire block)\n\n"
        f"```\n{full_post}\n```\n\n"
        f"---\n\n"
        f"## POSTING CHECKLIST\n\n"
        f"- [ ] Copy the FULL POST block above\n"
        f"- [ ] Go to Facebook -> Create Post\n"
        f"- [ ] Paste the content\n"
        f"- [ ] Add an image or video for better reach\n"
        f"- [ ] Click Post\n\n"
        f"---\n\n"
        f"*Generated by AI Employee | Ralph Loop v3.0 PLATINUM*\n"
    )

    out_file.write_text(md, encoding="utf-8")

    print(f"[Facebook] Post ready   : {out_file.name}")
    print(f"[Facebook] Headline     : {_safe(headline, 80)}")
    print(f"[Facebook] Chars        : {len(full_post)}")

    _log_social("GENERATED", "Facebook", filename, f"Saved to {out_file.name}")
    return "Facebook post ready for publishing"


# --------------------------------------------------
# INSTAGRAM CAPTION GENERATOR
# --------------------------------------------------

def generate_instagram_caption(content: str, filename: str = "social") -> str:
    """
    Generate an Instagram caption with hashtags and image idea.

    Structure: Caption + Hashtags (separated by dots) + Image Idea suggestion
    Saves to Done/INSTAGRAM_POST_<timestamp>.md
    Returns: status string
    """
    DONE_DIR.mkdir(parents=True, exist_ok=True)

    system = (
        "You are an Instagram content creator and social media strategist. "
        "Write compelling Instagram captions that drive engagement. "
        "Use strategic hashtags and suggest visual content ideas."
    )
    prompt = (
        f"Create an Instagram post about:\n\n"
        f"{content}\n\n"
        f"Format EXACTLY like this:\n\n"
        f"CAPTION:\n[Engaging caption with emojis, max 150 words, conversational]\n\n"
        f"HASHTAGS:\n[20-25 relevant hashtags, mix of popular and niche]\n\n"
        f"IMAGE_IDEA:\n[Specific visual content suggestion for the image or video]"
    )

    ai_text = _call_ai(prompt, system, max_tokens=600)

    if ai_text:
        caption    = _extract_section(ai_text, "CAPTION")
        hashtags   = _extract_section(ai_text, "HASHTAGS")
        image_idea = _extract_section(ai_text, "IMAGE_IDEA")
    else:
        caption    = content[:300] if content else "Sharing something special with our community!"
        hashtags   = "#Instagram #Business #Growth #Success #Entrepreneur"
        image_idea = "Professional photo related to the topic with good lighting and clean background."

    if not caption:
        caption = content[:300]
    if not hashtags:
        hashtags = "#Instagram #Business #Growth"
    if not image_idea:
        image_idea = "Professional photo related to the post topic."

    # Instagram format: caption + dot separators + hashtags
    full_caption = f"{caption}\n.\n.\n.\n{hashtags}"
    if len(full_caption) > MAX_INSTAGRAM_CHARS:
        caption      = caption[:MAX_INSTAGRAM_CHARS - len(hashtags) - 20]
        full_caption = f"{caption}\n.\n.\n.\n{hashtags}"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file  = DONE_DIR / f"INSTAGRAM_POST_{timestamp}.md"

    md = (
        f"# INSTAGRAM POST -- READY TO COPY\n\n"
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"**Source:** {filename}\n"
        f"**Platform:** Instagram\n"
        f"**Characters:** {len(full_caption)} / {MAX_INSTAGRAM_CHARS}\n\n"
        f"---\n\n"
        f"## CAPTION\n\n{caption}\n\n"
        f"---\n\n"
        f"## HASHTAGS\n\n{hashtags}\n\n"
        f"---\n\n"
        f"## IMAGE / VIDEO IDEA\n\n"
        f"> {image_idea}\n\n"
        f"---\n\n"
        f"## FULL CAPTION (Copy this to Instagram)\n\n"
        f"```\n{full_caption}\n```\n\n"
        f"---\n\n"
        f"## POSTING CHECKLIST\n\n"
        f"- [ ] Prepare image/video (see IMAGE IDEA above)\n"
        f"- [ ] Open Instagram -> Create new post\n"
        f"- [ ] Upload your image/video\n"
        f"- [ ] Copy the FULL CAPTION block\n"
        f"- [ ] Paste as caption\n"
        f"- [ ] Add location tag if relevant\n"
        f"- [ ] Post!\n\n"
        f"---\n\n"
        f"*Generated by AI Employee | Ralph Loop v3.0 PLATINUM*\n"
    )

    out_file.write_text(md, encoding="utf-8")

    print(f"[Instagram] Caption ready : {out_file.name}")
    print(f"[Instagram] Caption start : {_safe(caption, 80)}...")
    print(f"[Instagram] Image idea    : {_safe(image_idea, 80)}...")

    _log_social("GENERATED", "Instagram", filename, f"Saved to {out_file.name}")
    return "Instagram post ready for publishing"


# --------------------------------------------------
# UNIFIED SOCIAL DISPATCHER
# --------------------------------------------------

def dispatch_social(
    channel: str, content: str, filename: str, phone: str = ""
) -> str:
    """
    Unified entry point for all social media content generation.

    Args:
        channel:  "LinkedIn", "Facebook", "Instagram", "WhatsApp"
        content:  Task content / brief
        filename: Source task filename (for logging / output naming)
        phone:    WhatsApp recipient number (optional, for wa.me link)

    Returns:
        Status string like "LinkedIn post ready for publishing"
    """
    ch = channel.strip()

    # Normalize casing variants
    _map = {
        "linkedin":  "LinkedIn",
        "facebook":  "Facebook",
        "instagram": "Instagram",
        "whatsapp":  "WhatsApp",
    }
    ch = _map.get(ch.lower(), ch)

    if ch == "LinkedIn":
        return generate_linkedin_post(content, filename)
    if ch == "WhatsApp":
        return generate_whatsapp_message(content, phone, filename)
    if ch == "Facebook":
        return generate_facebook_post(content, filename)
    if ch == "Instagram":
        return generate_instagram_caption(content, filename)

    return f"Unknown social channel: {channel}"


# --------------------------------------------------
# ACTION FILE PARSER
# --------------------------------------------------

def parse_social_from_action(file_path: str) -> dict:
    """
    Extract social media details from an ACTION_*.md file.

    Returns:
        dict with keys: channel, content, phone, approved
    """
    raw = Path(file_path).read_text(encoding="utf-8")

    data = {
        "channel":  None,
        "content":  raw,
        "phone":    None,
        "approved": False,
    }

    # Channel from markdown table  | Channel | Facebook |
    m = re.search(r"Channel\s*\|\s*(\w+)", raw, re.IGNORECASE)
    if m:
        data["channel"] = m.group(1).strip()

    # Phone/recipient for WhatsApp
    m = re.search(r"(?:Recipient|Phone|To)\s*\|\s*([\+\d\-\s\(\)]+)", raw)
    if m:
        data["phone"] = m.group(1).strip()

    # Approval check
    if "APPROVED" in raw:
        data["approved"] = True

    # Extract quoted body lines as the actual content
    body_lines = []
    for line in raw.split("\n"):
        stripped = line.strip()
        if stripped.startswith(">"):
            body_lines.append(stripped[1:].strip())

    if body_lines:
        data["content"] = "\n".join(body_lines).strip()

    return data


# --------------------------------------------------
# CLI TEST
# --------------------------------------------------

if __name__ == "__main__":
    print("=" * 55)
    print("  SOCIAL MEDIA SENDER -- Diagnostic Test")
    print("=" * 55)

    creds      = _load_env()
    groq_key   = creds.get("GROQ_API_KEY", "")
    gemini_key = creds.get("GEMINI_API_KEY", "")

    print(f"\n  Groq API key   : {'SET (' + groq_key[:8] + '...)' if groq_key and 'your_' not in groq_key else 'NOT SET'}")
    print(f"  Gemini API key : {'SET (' + gemini_key[:8] + '...)' if gemini_key and 'your_' not in gemini_key else 'NOT SET'}")
    print(f"  Groq package   : {'INSTALLED' if _HAS_GROQ else 'NOT INSTALLED'}")
    print(f"  Gemini package : {'INSTALLED' if _HAS_GEMINI else 'NOT INSTALLED'}")
    print(f"  Output dir     : {DONE_DIR}")

    test_content = (
        "Announcing the launch of AI Employee -- an autonomous AI system that handles "
        "emails, social media, and more using a multi-agent PLATINUM pipeline with "
        "Groq free tier, self-improving memory, and 4-agent THINKER->PLANNER->EXECUTOR->REVIEWER."
    )

    print(f"\n  Running platform tests...\n")

    for ch, extra in [
        ("LinkedIn",  {}),
        ("WhatsApp",  {"phone": "+923001234567"}),
        ("Facebook",  {}),
        ("Instagram", {}),
    ]:
        r = dispatch_social(ch, test_content, "CLI_TEST", **extra)
        print(f"  {ch:12s}: {r}\n")

    print("=" * 55)
    print(f"  All posts saved to: {DONE_DIR}")
    print("=" * 55)
