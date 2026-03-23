"""
verify_social.py -- Social Media Output Verification
=====================================================
Scans Done/ folder and verifies all 4 platform outputs.
No external libraries. Windows-safe. No emoji in print.

Run:
    python verify_social.py
"""

from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent
DONE = BASE / "AI_Employee_Vault" / "Done"

# Minimum byte size to consider a file non-empty / valid
MIN_SIZE = 200

# Required sections per platform (must appear in the file)
REQUIRED = {
    "LinkedIn":  ["HOOK", "FULL POST", "POSTING CHECKLIST"],
    "WhatsApp":  ["MESSAGE", "ONE-CLICK SEND LINK", "wa.me", "HOW TO USE"],
    "Facebook":  ["HEADLINE", "FULL POST", "POSTING CHECKLIST"],
    "Instagram": ["CAPTION", "HASHTAGS", "IMAGE", "FULL CAPTION", "POSTING CHECKLIST"],
}

# File prefix patterns per platform
PREFIXES = {
    "LinkedIn":  "LINKEDIN_POST_",
    "WhatsApp":  "WHATSAPP_MSG_",
    "Facebook":  "FACEBOOK_POST_",
    "Instagram": "INSTAGRAM_POST_",
}


# --------------------------------------------------
def scan_platform(platform):
    """
    Find the latest file for a platform, run checks.
    Returns (passed: bool, details: list[str])
    """
    prefix = PREFIXES[platform]
    files  = sorted(DONE.glob(prefix + "*.md"))
    details = []

    if not files:
        return False, ["No " + prefix + "*.md file found in Done/"]

    latest = files[-1]
    size   = latest.stat().st_size
    details.append("File    : " + latest.name)
    details.append("Size    : " + str(size) + " bytes")

    if size < MIN_SIZE:
        details.append("FAIL    : File too small (< " + str(MIN_SIZE) + " bytes)")
        return False, details

    content = latest.read_text(encoding="utf-8")

    # Check required sections
    missing = []
    for section in REQUIRED[platform]:
        if section.upper() not in content.upper():
            missing.append(section)

    if missing:
        details.append("FAIL    : Missing sections: " + ", ".join(missing))
        return False, details

    details.append("Sections: all " + str(len(REQUIRED[platform])) + " required sections found")

    # Platform-specific extra checks
    if platform == "WhatsApp":
        if "https://wa.me/" not in content:
            details.append("FAIL    : wa.me link not found")
            return False, details
        details.append("wa.me   : link present")

    if platform == "Instagram":
        if "." in content and "#" in content:
            details.append("Format  : dot-separator + hashtags found")
        else:
            details.append("FAIL    : dot separator or hashtags missing")
            return False, details

    if platform == "LinkedIn":
        if "Characters:" in content:
            details.append("Chars   : character count present")

    return True, details


# --------------------------------------------------
def main():
    print("")
    print("=" * 46)
    print("  SOCIAL MEDIA VERIFICATION REPORT")
    print("  Run: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("  Dir: " + str(DONE))
    print("=" * 46)

    if not DONE.exists():
        print("")
        print("  ERROR: Done/ folder does not exist.")
        print("  Run ralph_loop.py or social_media_sender.py first.")
        print("")
        return

    results = {}
    for platform in ["LinkedIn", "WhatsApp", "Facebook", "Instagram"]:
        passed, details = scan_platform(platform)
        results[platform] = passed

        label = "PASS" if passed else "FAIL"
        print("")
        print("  [" + label + "] " + platform)
        for d in details:
            print("         " + d)

    # Summary
    print("")
    print("=" * 46)
    print("  SUMMARY")
    print("=" * 46)
    for platform, passed in results.items():
        label = "PASS" if passed else "FAIL"
        print("  " + platform.ljust(12) + ": " + label)

    total  = len(results)
    passed_count = sum(1 for v in results.values() if v)
    print("")
    print("  Score: " + str(passed_count) + "/" + str(total) + " platforms verified")

    if passed_count == total:
        print("  STATUS: ALL PLATFORMS READY")
    else:
        print("  STATUS: SOME PLATFORMS NEED ATTENTION")
    print("=" * 46)
    print("")


if __name__ == "__main__":
    main()
