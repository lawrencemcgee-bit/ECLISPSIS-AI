"""
CreativeContentService — local, non-LLM creative-writing tools.

No LLM exists anywhere in this codebase — a deliberate design choice
matching NCIService, CodingService, and SocialContentService, all of
which are local/heuristic rather than calling out to a generative model.
This service keeps that honesty rather than pretending to be an AI
writer. Two distinct, genuinely useful things it can do without one:

  - Generation: template + curated-list based procedural generators
    (headline variants, writing prompts, content outlines). These
    produce real, usable output — but it's assembled from fixed
    templates and word lists with randomized selection, not composed
    prose. A caller asking for "5 headline ideas" gets 5 real, distinct
    strings; a caller expecting an LLM to have understood their topic
    and written something novel about it will be disappointed, and the
    docstrings/README should say so plainly.

  - Critique: heuristic analysis of text the caller already wrote —
    passive voice, filler/weak words, cliches, repeated words, sentence
    length variety, and a plain-English list of suggestions. Same
    approach as NCIService's quality scoring, aimed at a writer
    improving their own draft rather than a researcher judging a
    source's worth.
"""

import random
import re
from collections import Counter


_HEADLINE_TEMPLATES = (
    "The Ultimate Guide to {topic}",
    "{n} Things You Didn't Know About {topic}",
    "Why {topic} Matters More Than You Think",
    "How to Master {topic} in Record Time",
    "Is {topic} Really Worth It? Here's the Truth",
    "{topic}: A Beginner's Guide",
    "The Surprising Truth About {topic}",
    "{n} Mistakes to Avoid With {topic}",
    "What Nobody Tells You About {topic}",
    "{topic} Explained in Plain English",
)

_PROMPT_ARCHETYPES = {
    "general": ["a reluctant hero", "a curious child", "a retired professional pulled back in",
                "someone who's lost everything once already", "a stranger who knows too much"],
    "sci-fi": ["a disgraced scientist", "a rogue ship's AI", "a colonist born off-world",
               "a soldier who no longer trusts their orders", "an engineer who built the thing now hunting them"],
    "fantasy": ["an exiled queen", "an apprentice who outgrew their master", "a con artist with real magic",
                "the last of a forgotten order", "a farmer who finds out their bloodline isn't human"],
    "mystery": ["a detective who already knows the answer, but not the reason",
                "a witness who lied to protect someone", "a journalist chasing a story that chases back",
                "the one person with an alibi that's somehow too perfect"],
}

_PROMPT_SETTINGS = {
    "general": ["a town everyone seems to be leaving", "a house that's been empty for years",
                "a job interview that's taking a strange turn"],
    "sci-fi": ["a floating city above the clouds", "a space station orbiting a dying star",
               "an underground bunker decades after a war nobody remembers starting",
               "a colony ship that's been traveling three generations too long"],
    "fantasy": ["a forest that remembers everyone who's walked through it", "a city built on the back of something sleeping",
                "a kingdom where magic is rationed like water", "a library where every book writes itself"],
    "mystery": ["a small town where nothing bad has happened in fifty years — until now",
                "a locked room with no explanation", "an island cut off by a storm, with one extra body count"],
}

_PROMPT_CONFLICTS = (
    "must recover something stolen from their own past",
    "discovers a secret that could destroy everyone they love",
    "is given 24 hours to undo a mistake with no clear way to undo it",
    "must choose between duty and the one person who'd forgive them for choosing wrong",
    "finds a door that shouldn't exist, and someone on the other side who knows their name",
    "realizes the thing they've been hunting has been hunting them longer",
)

_OUTLINE_TEMPLATES = {
    "blog_post": ["Hook / opening story", "Why this matters right now", "Core idea, part 1",
                  "Core idea, part 2", "Common mistakes or misconceptions", "Actionable takeaways",
                  "Conclusion / call to action"],
    "listicle": ["Hook — why this list, why now", "Item-by-item breakdown (see count)",
                 "Honorable mentions / what almost made the cut", "Wrap-up takeaway"],
    "how_to_guide": ["Overview — what you'll accomplish", "What you'll need", "Step-by-step instructions",
                      "Common pitfalls / troubleshooting", "Summary / next steps"],
    "video_script": ["Hook (first 5 seconds)", "Introduction — who/what/why", "Main content, beat by beat",
                      "Call to action", "Outro"],
}

_CLICHES = (
    "at the end of the day", "think outside the box", "low-hanging fruit", "it is what it is",
    "time will tell", "when all is said and done", "each and every", "in this day and age",
    "needle in a haystack", "read between the lines", "leave no stone unturned",
    "the tip of the iceberg", "back to square one", "easier said than done",
)

_WEAK_WORDS = (
    "very", "really", "just", "actually", "basically", "literally", "somewhat",
    "quite", "rather", "extremely", "definitely", "totally", "simply",
)

_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "so", "of", "to", "in", "on", "at",
    "for", "with", "about", "as", "by", "is", "are", "was", "were", "be", "been", "being",
    "this", "that", "these", "those", "it", "its", "from", "into", "over", "under", "up",
    "down", "out", "not", "no", "do", "does", "did", "has", "have", "had", "can", "could",
    "will", "would", "should", "i", "you", "he", "she", "they", "we",
}

_PASSIVE_RE = re.compile(
    r"\b(am|is|are|was|were|be|been|being)\s+\w+ed\b", re.IGNORECASE,
)

# Regular -ed participles are covered by _PASSIVE_RE above; irregular
# past participles ("thrown", "given", "taken"...) don't end in -ed, so
# they need their own list to be caught at all. Even with this, passive
# detection here is a heuristic, not a parser — it can still miss
# multi-word auxiliaries or unusual phrasing. Documented as a known
# limitation rather than silently under-counting.
_IRREGULAR_PARTICIPLES = (
    "thrown", "given", "taken", "made", "done", "seen", "known", "written",
    "broken", "chosen", "drawn", "driven", "eaten", "fallen", "forgotten",
    "gotten", "grown", "hidden", "ridden", "risen", "shown", "spoken",
    "stolen", "sung", "swum", "torn", "worn", "woven", "born", "beaten",
    "begun", "bitten", "blown", "bound", "bought", "brought", "built",
    "burnt", "caught", "come", "cut", "dealt", "dug", "dreamt", "drunk",
    "felt", "fought", "found", "flown", "frozen", "gone", "ground",
    "held", "hung", "hurt", "kept", "knelt", "laid", "led", "left",
    "lent", "let", "lit", "lost", "meant", "met", "paid", "put", "read",
    "rung", "run", "said", "sold", "sent", "set", "shaken", "shed",
    "shot", "shrunk", "shut", "slept", "slid", "spent", "split", "spread",
    "sprung", "stood", "struck", "sworn", "swept", "taught", "told",
    "thought", "understood", "woken", "won", "wound",
)
_PASSIVE_IRREGULAR_RE = re.compile(
    r"\b(am|is|are|was|were|be|been|being)\s+(" + "|".join(_IRREGULAR_PARTICIPLES) + r")\b",
    re.IGNORECASE,
)


class CreativeContentService:
    """`seed` (accepted by every generator method) makes output
    reproducible for tests/demos; omit it for real random variety."""

    # -----------------------------------------------------------------
    # Generation
    # -----------------------------------------------------------------
    def generate_headlines(self, topic: str, count: int = 5, seed: int = None) -> list:
        rng = random.Random(seed)
        topic = (topic or "your topic").strip()
        templates = list(_HEADLINE_TEMPLATES)
        rng.shuffle(templates)
        count = max(1, min(count, len(templates)))
        return [
            t.format(topic=topic, n=rng.choice((3, 5, 7, 9, 10)))
            for t in templates[:count]
        ]

    def generate_writing_prompt(self, genre: str = None, seed: int = None) -> dict:
        rng = random.Random(seed)
        key = (genre or "general").lower().strip()
        if key not in _PROMPT_ARCHETYPES:
            key = "general"
        archetype = rng.choice(_PROMPT_ARCHETYPES[key])
        setting = rng.choice(_PROMPT_SETTINGS[key])
        conflict = rng.choice(_PROMPT_CONFLICTS)
        first_sentence = archetype[0].upper() + archetype[1:]
        prompt = f"{first_sentence}, in {setting}, {conflict}."
        return {"genre": key, "prompt": prompt, "archetype": archetype,
                "setting": setting, "conflict": conflict}

    def generate_outline(self, topic: str, content_type: str = "blog_post") -> dict:
        key = (content_type or "blog_post").lower().strip()
        sections = _OUTLINE_TEMPLATES.get(key)
        if sections is None:
            return {
                "topic": topic, "content_type": key, "sections": [],
                "note": f"No outline template for '{key}'. Available: "
                        f"{', '.join(sorted(_OUTLINE_TEMPLATES))}.",
            }
        return {
            "topic": (topic or "").strip(),
            "content_type": key,
            "sections": [{"title": s} for s in sections],
        }

    # -----------------------------------------------------------------
    # Critique
    # -----------------------------------------------------------------
    def critique(self, text: str) -> dict:
        text = text or ""
        words = re.findall(r"[a-zA-Z']+", text)
        sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
        sentence_lengths = [len(re.findall(r"[a-zA-Z']+", s)) for s in sentences]

        passive_hits = _PASSIVE_RE.findall(text) + _PASSIVE_IRREGULAR_RE.findall(text)
        weak_hits = self._count_hits(text, _WEAK_WORDS)
        cliches_found = [c for c in _CLICHES if c in text.lower()]
        overused = self._overused_words(words)
        adverb_count = sum(1 for w in words if w.lower().endswith("ly") and len(w) > 3)

        avg_len = sum(sentence_lengths) / len(sentence_lengths) if sentence_lengths else 0
        variety = self._stdev(sentence_lengths)

        suggestions = []
        if len(passive_hits) > max(1, len(sentences) * 0.15):
            suggestions.append(
                f"{len(passive_hits)} likely passive-voice constructions — "
                "consider active voice for more direct writing."
            )
        if sum(weak_hits.values()) > max(2, len(words) // 100):
            top = sorted(weak_hits.items(), key=lambda kv: -kv[1])[:3]
            suggestions.append(
                "Frequent filler words (" +
                ", ".join(f"'{w}' x{c}" for w, c in top if c) +
                ") — trimming these usually tightens the prose."
            )
        if cliches_found:
            suggestions.append(f"Cliché phrases found: {', '.join(cliches_found)}.")
        if overused:
            top = sorted(overused.items(), key=lambda kv: -kv[1])[:3]
            suggestions.append(
                "Words repeated often: " + ", ".join(f"'{w}' x{c}" for w, c in top) + "."
            )
        if variety is not None and variety < 3 and len(sentences) > 3:
            suggestions.append(
                "Sentence lengths are fairly uniform — varying sentence length "
                "usually improves rhythm."
            )

        return {
            "word_count": len(words),
            "sentence_count": len(sentences),
            "passive_voice_count": len(passive_hits),
            "weak_words": {w: c for w, c in weak_hits.items() if c},
            "adverb_count": adverb_count,
            "cliches_found": cliches_found,
            "overused_words": overused,
            "sentence_length": {
                "average": round(avg_len, 1),
                "stdev": round(variety, 1) if variety is not None else None,
            },
            "suggestions": suggestions,
        }

    # -----------------------------------------------------------------
    def _count_hits(self, text: str, phrases: tuple) -> dict:
        lowered = text.lower()
        return {p: len(re.findall(r"\b" + re.escape(p) + r"\b", lowered)) for p in phrases}

    def _overused_words(self, words: list, min_len: int = 4, threshold: int = 4) -> dict:
        counts = Counter(w.lower() for w in words if len(w) >= min_len and w.lower() not in _STOPWORDS)
        return {w: c for w, c in counts.items() if c >= threshold}

    @staticmethod
    def _stdev(values: list):
        if len(values) < 2:
            return None
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
        return variance ** 0.5
