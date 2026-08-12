"""
SocialContentService — local analysis of a social-media post the caller
already has, to help judge it before posting elsewhere.

There's no OAuth/API-key infrastructure anywhere in this codebase for
actually publishing to a platform (Twitter/X, Instagram, LinkedIn, etc.),
and building one would mean fabricating credentials/integration this
project doesn't have. Scope here is deliberately limited to analysis:
character count against a platform's practical limit, hashtag/mention/
link counts, and a small set of engagement heuristics (call-to-action
phrasing, a direct question, shouting via ALL-CAPS, hashtag density).
Fully local, no external API call — same design as NCIService.
"""

import re


# Practical caption/post limits, not necessarily each platform's absolute
# technical maximum — e.g. Instagram allows up to 2,200 characters but
# captions are conventionally kept much shorter for readability.
_PLATFORM_LIMITS = {
    "twitter": 280,
    "x": 280,
    "instagram": 2200,
    "linkedin": 3000,
    "facebook": 63206,
    "tiktok": 2200,
    "generic": None,
}

_CTA_PHRASES = (
    "comment below", "drop a comment", "let us know", "let me know",
    "share this", "tag a friend", "tag someone", "link in bio",
    "swipe up", "double tap", "click the link", "sign up", "learn more",
    "follow for more", "save this post", "dm us", "dm me",
)

_HASHTAG_RE = re.compile(r"#\w+")
_MENTION_RE = re.compile(r"@\w+")
_URL_RE = re.compile(r"https?://\S+")


class SocialContentService:
    def analyze(self, text: str, platform: str = "generic") -> dict:
        text = text or ""
        platform_key = platform.lower().strip()
        limit = _PLATFORM_LIMITS.get(platform_key, _PLATFORM_LIMITS["generic"])

        hashtags = _HASHTAG_RE.findall(text)
        mentions = _MENTION_RE.findall(text)
        links = _URL_RE.findall(text)

        char_count = len(text)
        over_limit = limit is not None and char_count > limit
        has_question = "?" in text
        cta_hits = [p for p in _CTA_PHRASES if p in text.lower()]

        letters = [c for c in text if c.isalpha()]
        caps_ratio = (sum(1 for c in letters if c.isupper()) / len(letters)) if letters else 0.0
        shouting = caps_ratio > 0.6 and len(letters) > 10

        signals = {
            "within_length_limit": not over_limit,
            "has_hashtags": bool(hashtags),
            "hashtag_count_reasonable": 1 <= len(hashtags) <= 8,
            "has_call_to_action": bool(cta_hits),
            "asks_a_question": has_question,
            "not_shouting": not shouting,
        }
        score = round(sum(signals.values()) / len(signals) * 100, 1)

        return {
            "platform": platform_key,
            "score": score,
            "label": self._label(score),
            "char_count": char_count,
            "char_limit": limit,
            "over_limit": over_limit,
            "hashtags": hashtags,
            "mentions": mentions,
            "links": links,
            "call_to_action_phrases": cta_hits,
            "shouting": shouting,
            "signals": signals,
        }

    @staticmethod
    def _label(score: float) -> str:
        if score >= 75:
            return "strong"
        if score >= 50:
            return "moderate"
        if score >= 25:
            return "weak"
        return "poor"
