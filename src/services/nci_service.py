"""
NCIService — Natural Command Interface content scoring (Tier 3).

Scores article text or video transcripts to help judge whether a piece of
content is worth pulling into podcast/article research. Fully local and
heuristic-based — no external LLM calls — consistent with the rest of the
assistant's local-engine design (LocalEngine, offline voice I/O, etc.).

Two independent facets are combined into one composite score:
  - Quality: research-worthiness signals that don't require a topic —
    depth, evidence density, readability, vocabulary richness.
  - Relevance: how much the content actually engages with a caller-supplied
    topic/query. Only computed when a topic is given.

Input is either raw text or a URL:
  - Raw text works for an article body OR a video transcript — NCI has no
    concept of "video" as a distinct source; scoring only ever looks at
    text. A real video/vision pipeline is a separate, not-yet-built piece
    (see architecture_baseline.md); once it exists, feeding its transcript
    output into `content` here is all that's needed for video support.
  - A URL is fetched (via the shared WebFetcher, see web_fetch.py) and the
    main article text extracted. If both content and url are supplied,
    content is used as-is (no fetch) and url is kept only for source
    metadata (domain) — avoids a redundant network call when the caller
    already has the text in hand.
"""

import re
from collections import Counter
from urllib.parse import urlparse

from src.services.web_fetch import WebFetcher, WebFetchError


_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "so", "of", "to",
    "in", "on", "at", "for", "with", "about", "as", "by", "is", "are",
    "was", "were", "be", "been", "being", "this", "that", "these", "those",
    "it", "its", "from", "into", "over", "under", "up", "down", "out",
    "not", "no", "do", "does", "did", "has", "have", "had", "can", "could",
    "will", "would", "should", "i", "you", "he", "she", "they", "we",
    "what", "which", "who", "how", "when", "where", "why",
}


class NCIFetchError(Exception):
    """Raised when a URL is supplied but couldn't be fetched or parsed.
    Kept as NCI's own exception type (rather than callers catching
    WebFetchError directly) so NCI's public contract — what
    AssistantCore.analyze() catches — doesn't change if the shared
    fetcher's error type ever does."""


class NCIService:
    """Local, heuristic content scorer. See module docstring for design."""

    def __init__(self, fetcher: WebFetcher = None):
        self._fetcher = fetcher or WebFetcher()

    def interpret(self, content: str = None, url: str = None, topic: str = None) -> dict:
        if not content and not url:
            raise ValueError("NCIService.interpret() requires content and/or url.")

        metadata = {}
        if url:
            metadata["url"] = url
            metadata["domain"] = urlparse(url).netloc

        if url and not content:
            content, fetched_meta = self._fetch_url(url)
            metadata.update(fetched_meta)

        content = (content or "").strip()
        if not content:
            return {
                "score": 0.0,
                "label": "unscoreable",
                "reason": "No content available to score.",
                "topic": topic,
                "metadata": metadata,
            }

        words = self._tokenize(content)
        quality = self._score_quality(content, words)

        components = {"quality": quality["score"]}
        weights = {"quality": 1.0}

        relevance = None
        if topic:
            relevance = self._score_relevance(words, topic)
            components["relevance"] = relevance["score"]
            weights = {"quality": 0.5, "relevance": 0.5}

        composite = sum(components[k] * weights[k] for k in components) / sum(weights.values())
        composite = round(composite, 1)

        breakdown = {"quality": quality}
        if relevance is not None:
            breakdown["relevance"] = relevance

        return {
            "score": composite,
            "label": self._label(composite),
            "topic": topic,
            "breakdown": breakdown,
            "stats": {
                "word_count": len(words),
                "unique_words": len(set(words)),
            },
            "metadata": metadata,
        }

    # -----------------------------------------------------------------
    # Fetching
    # -----------------------------------------------------------------
    def _fetch_url(self, url: str):
        try:
            fetched = self._fetcher.fetch(url)
        except WebFetchError as exc:
            raise NCIFetchError(str(exc)) from exc

        meta = {k: fetched[k] for k in ("title", "author", "published") if k in fetched}
        return fetched["text"], meta

    # -----------------------------------------------------------------
    # Tokenizing
    # -----------------------------------------------------------------
    @staticmethod
    def _tokenize(text: str):
        return re.findall(r"[a-zA-Z']+", text.lower())

    # -----------------------------------------------------------------
    # Quality scoring (no topic required)
    # -----------------------------------------------------------------
    def _score_quality(self, text: str, words: list) -> dict:
        word_count = len(words)
        sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
        sentence_count = max(1, len(sentences))

        # Depth: reward substantial content; full marks by 600 words, no
        # bonus (and no penalty) for going longer — length past that point
        # says nothing about quality on its own.
        if word_count < 100:
            depth = (word_count / 100) * 0.4
        elif word_count < 600:
            depth = 0.4 + (word_count - 100) / 500 * 0.6
        else:
            depth = 1.0

        # Vocabulary richness: type-token ratio, normalized against a
        # typical prose ceiling (~0.5) so it doesn't require a huge corpus.
        ttr = (len(set(words)) / word_count) if word_count else 0.0
        vocabulary = min(1.0, ttr / 0.5)

        # Evidence density: digits, quoted material, and citation-style
        # phrases, normalized per 100 words of content.
        digit_hits = len(re.findall(r"\d", text))
        quote_hits = text.count('"') // 2
        citation_hits = len(re.findall(
            r"\baccording to\b|\bstudy\b|\bstudies\b|\bresearch(?:ers)?\b|"
            r"\breport(?:ed|s)?\b|\bdata\b|\bsurvey(?:ed)?\b|\bstatistics\b",
            text, re.IGNORECASE,
        ))
        evidence_hits = digit_hits * 0.1 + quote_hits + citation_hits
        per_100_words = max(1.0, word_count / 100)
        evidence = min(1.0, (evidence_hits / per_100_words) / 3)

        # Readability: moderate average sentence length (10-25 words) reads
        # easiest without being choppy; scores taper off outside that band.
        avg_sentence_len = word_count / sentence_count
        if 10 <= avg_sentence_len <= 25:
            readability = 1.0
        elif avg_sentence_len < 10:
            readability = max(0.3, avg_sentence_len / 10)
        else:
            readability = max(0.3, 1 - (avg_sentence_len - 25) / 40)

        weights = {"depth": 0.35, "vocabulary": 0.2, "evidence": 0.25, "readability": 0.2}
        signals = {"depth": depth, "vocabulary": vocabulary, "evidence": evidence, "readability": readability}
        composite = sum(signals[k] * weights[k] for k in weights)

        return {
            "score": round(composite * 100, 1),
            "signals": {k: round(v * 100, 1) for k, v in signals.items()},
        }

    # -----------------------------------------------------------------
    # Relevance scoring (topic required)
    # -----------------------------------------------------------------
    def _score_relevance(self, words: list, topic: str) -> dict:
        topic_terms = {t for t in self._tokenize(topic) if t not in _STOPWORDS}
        if not topic_terms:
            return {"score": 0.0, "matched_terms": [], "coverage": 0.0,
                     "note": "Topic had no scorable terms after stopword removal."}

        counts = Counter(words)
        total = len(words) or 1

        matched = sorted(t for t in topic_terms if counts.get(t, 0))
        density = sum(counts.get(t, 0) for t in matched) / total

        coverage = len(matched) / len(topic_terms)
        density_score = min(1.0, density * 200)  # topic terms are sparse by nature
        composite = 0.6 * coverage + 0.4 * density_score

        return {
            "score": round(composite * 100, 1),
            "matched_terms": matched,
            "coverage": round(coverage * 100, 1),
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
