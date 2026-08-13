"""
WebFetcher — shared HTTP fetch + HTML parsing (Tier 3).

Pulled out of NCIService while building the browser agent: NCIService's
`_fetch_url` already did requests+BeautifulSoup fetching to score a URL's
content, and the browser agent needs the exact same fetch-and-parse
capability as a general-purpose, standalone thing rather than something
buried inside content scoring. Rather than duplicate that logic, both
NCIService and BrowserService now share this one implementation — same
timeout, same user agent, same "raise a typed error, let the caller
decide how to report it" contract NCIService already had.

Purely mechanical extraction/text/link extraction — no LLM, no
interpretation of what was fetched, no execution of anything on the
page (scripts are stripped, never run). Matches the rest of this
codebase's local-engine, no-external-model design.
"""

from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


class WebFetchError(Exception):
    """Raised when a URL can't be fetched or returns no parseable HTML."""


class WebFetcher:
    USER_AGENT = "ECLIPSIS-AI/1.0 (+local research fetch)"
    REQUEST_TIMEOUT = 10

    def fetch(self, url: str) -> dict:
        """Fetches `url` and returns a dict with:
          - domain, status_code
          - title, author, published (each omitted if not present in the
            page's <title>/meta tags)
          - text: main article text (paragraph-filtered — only <p> tags
            with more than 3 words — falling back to the full page text
            if that yields nothing, e.g. a page that isn't paragraph-
            structured)
          - links: absolute http(s) URLs found on the page, deduped,
            in document order

        Raises WebFetchError on any request failure (network error,
        timeout, non-2xx status) or if the response has no parseable
        HTML — callers decide how to surface that (NCIService scores it
        as unscoreable; BrowserAgent returns an error result), this
        module never swallows the failure itself.
        """
        try:
            resp = requests.get(
                url, timeout=self.REQUEST_TIMEOUT,
                headers={"User-Agent": self.USER_AGENT},
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise WebFetchError(f"Could not fetch {url}: {exc}") from exc

        soup = BeautifulSoup(resp.text, "lxml")

        result = {"domain": urlparse(url).netloc, "status_code": resp.status_code}

        title_tag = soup.find("title")
        if title_tag and title_tag.get_text(strip=True):
            result["title"] = title_tag.get_text(strip=True)

        author_tag = soup.find("meta", attrs={"name": "author"})
        if author_tag and author_tag.get("content"):
            result["author"] = author_tag["content"]

        published_tag = (
            soup.find("meta", attrs={"property": "article:published_time"})
            or soup.find("meta", attrs={"name": "date"})
        )
        if published_tag and published_tag.get("content"):
            result["published"] = published_tag["content"]

        # Links are collected before the strip-and-extract pass below —
        # nav/footer links are still useful for a general-purpose browse
        # (e.g. "what else does this page link to"), unlike NCI's article
        # text extraction, which deliberately discards that chrome.
        links = []
        seen = set()
        for a in soup.find_all("a", href=True):
            href = urljoin(url, a["href"])
            if href.startswith(("http://", "https://")) and href not in seen:
                seen.add(href)
                links.append(href)
        result["links"] = links

        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
            tag.decompose()

        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        text = "\n".join(p for p in paragraphs if len(p.split()) > 3)
        if not text:
            text = soup.get_text(" ", strip=True)
        result["text"] = text

        return result
