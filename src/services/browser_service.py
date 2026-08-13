"""
BrowserService — general-purpose "fetch a URL and read it" (Tier 3).

architecture_baseline.md flagged this as the one deliberately-deferred
piece from the original Coding/Social/Creative agent build: "the NCI
service already does URL fetching internally (`_fetch_url`) but there's
no standalone agent exposing that as a general-purpose capability." This
closes that gap using the shared WebFetcher (src/services/web_fetch.py,
extracted from NCIService's fetch logic for exactly this reuse) rather
than a second, separate fetch implementation.

Deliberately NOT a general web-browsing agent: no JavaScript execution,
no session/cookie handling, no following redirects beyond what `requests`
does by default, no crawling beyond the single page requested (`links`
in the result are surfaced for the caller to follow explicitly, one
fetch() call at a time — this service never fetches a link on its own).
Matches the rest of the codebase's local-engine, no-external-model
design: this is mechanical extraction, not interpretation. Summarizing
or judging what was fetched is NCIService's job (feed the returned text
into `assistant.analyze()`), not this one's.
"""

from src.services.web_fetch import WebFetcher, WebFetchError


class BrowserFetchError(Exception):
    """Raised when a URL can't be fetched or parsed. Kept as this
    service's own exception type (mirroring NCIFetchError) so callers
    don't need to import from web_fetch.py directly."""


class BrowserService:
    MAX_LINKS = 50
    MAX_TEXT_CHARS = 20000  # guards against handing a huge page back
    # to a caller (e.g. over the HTTP API) uncapped; the full fetched
    # text is still what NCI scoring sees if text is then also passed
    # to assistant.analyze() as its own separate call — this cap is
    # about a single fetch() response size, not scoring accuracy.

    def __init__(self, fetcher: WebFetcher = None):
        self._fetcher = fetcher or WebFetcher()

    def fetch(self, url: str) -> dict:
        """Fetches `url` and returns a read-friendly dict: url, domain,
        status_code, title, author, published (each omitted if absent),
        text (truncated to MAX_TEXT_CHARS, with `text_truncated: True`
        set if so), word_count (over the untruncated text), and links
        (deduped, capped to MAX_LINKS, with `links_truncated: True` set
        if the page had more).

        Raises BrowserFetchError on any fetch/parse failure — unlike
        NCIService.interpret(), this doesn't swallow the failure into a
        "score: 0" result, since there's no score to degrade to here;
        callers (BrowserAgent.execute) decide how to report it."""
        if not url:
            raise ValueError("BrowserService.fetch() requires a url.")

        try:
            fetched = self._fetcher.fetch(url)
        except WebFetchError as exc:
            raise BrowserFetchError(str(exc)) from exc

        text = fetched["text"]
        word_count = len(text.split())
        text_truncated = len(text) > self.MAX_TEXT_CHARS
        if text_truncated:
            text = text[: self.MAX_TEXT_CHARS]

        links = fetched["links"]
        links_truncated = len(links) > self.MAX_LINKS
        links = links[: self.MAX_LINKS]

        result = {
            "url": url,
            "domain": fetched["domain"],
            "status_code": fetched["status_code"],
            "text": text,
            "text_truncated": text_truncated,
            "word_count": word_count,
            "links": links,
            "links_truncated": links_truncated,
        }
        for key in ("title", "author", "published"):
            if key in fetched:
                result[key] = fetched[key]
        return result
