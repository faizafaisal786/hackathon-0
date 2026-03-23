# Agent Skill: Post to Social Media

Generate and schedule social media content across LinkedIn, Twitter, Facebook, Instagram.

## Instructions

1. Read the task or topic provided
2. Check `AI_Employee_Vault/Company_Handbook.md` for brand voice and posting rules
3. Generate platform-specific content:
   - **LinkedIn**: Professional tone, 150-300 words, 3-5 hashtags
   - **Twitter/X**: Max 280 chars per tweet, thread if needed
   - **Facebook**: Conversational, 100-200 words, include CTA
   - **Instagram**: Caption 150 chars, 10-15 hashtags
4. Score all content with REVIEWER (must be ≥ 7.0/10)
5. Write to `AI_Employee_Vault/Pending_Approval/` for CEO review
6. After approval, call respective sender scripts:
   - `linkedin_sender.py`
   - `twitter_sender.py`
   - `social_media_sender.py` (Facebook/Instagram)
7. Log to `AI_Employee_Vault/Logs/social_YYYY-MM-DD.json`
8. Move to `AI_Employee_Vault/Done/`

## Usage

```
/post-social "Announce our new AI automation service"
/post-social linkedin "Weekly business update"
```
