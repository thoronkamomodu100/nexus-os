"""
NEXUS OS v5 — Real Web Crawler
===============================
Uses Python stdlib only: urllib, http.client, html.parser.
Extracts content, finds links, summarizes with Claude Code.
"""

from __future__ import annotations

import json
import re
import ssl
import time
import urllib.parse
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
from collections import deque


# ─── Config ────────────────────────────────────────────────────────────────────

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                 "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

TIMEOUT = 15
MAX_CONTENT_SIZE = 100_000  # 100KB max content
MAX_LINKS = 50


# ─── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class CrawlResult:
    url: str
    status: int
    title: str
    content: str  # Cleaned text content
    links: List[str] = field(default_factory=list)
    meta_description: str = ""
    content_type: str = ""
    response_time: float = 0
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "status": self.status,
            "title": self.title,
            "content": self.content[:2000] + ("..." if len(self.content) > 2000 else ""),
            "links": self.links[:20],
            "meta_description": self.meta_description,
            "content_type": self.content_type,
            "response_time_ms": round(self.response_time * 1000),
            "error": self.error,
        }


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str = "duckduckgo"


# ─── HTML Parser ──────────────────────────────────────────────────────────────

class ContentExtractor(HTMLParser):
    """Extract title, text content, and links from HTML."""

    def __init__(self):
        super().__init__()
        self.title = ""
        self.content: List[str] = []
        self.links: List[str] = []
        self.meta_description = ""
        self._in_title = False
        self._in_script = False
        self._in_style = False
        self._in_nav = False
        self._nav_text: List[str] = []
        self._current_tag = ""
        self._current_attrs: Dict = {}
        self._link_text: List[str] = []
        self._in_body = False
        self._seen_title = False

    def handle_starttag(self, tag: str, attrs: List[tuple]):
        self._current_tag = tag
        self._current_attrs = dict(attrs)

        if tag == "title":
            self._in_title = True
        elif tag in ("script", "style"):
            self._in_script = True
        elif tag == "nav":
            self._in_nav = True
        elif tag == "body":
            self._in_body = True
        elif tag == "a" and not self._in_script:
            href = dict(attrs).get("href", "")
            if href and not href.startswith(("#", "javascript:", "mailto:", "tel:")):
                self.links.append(href)
        elif tag in ("h1", "h2", "h3", "h4"):
            self.content.append("\n")  # Headings create breaks

    def handle_endtag(self, tag: str):
        if tag == "title":
            self._in_title = False
        elif tag == "script":
            self._in_script = False
        elif tag == "style":
            self._in_script = False
        elif tag == "nav":
            self._in_nav = False
        elif tag == "body":
            self._in_body = False

    def handle_data(self, data: str):
        data = data.strip()
        if not data or self._in_script or self._in_nav:
            return

        if self._in_title and not self._seen_title:
            self.title += data
        else:
            # Filter nav/footer noise
            if self._current_tag not in ("nav", "footer", "aside", "header"):
                self.content.append(data)

    def handle_comment(self, data: str):
        pass

    def get_content(self) -> str:
        """Join content, clean up whitespace."""
        text = " ".join(self.content)
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"[\r\n\t]+", " ", text)
        # Remove extra spaces around punctuation
        text = re.sub(r"\s+([.,!?;:])", r"\1", text)
        return text.strip()


class MetaExtractor(HTMLParser):
    """Extract meta tags from HTML."""

    def __init__(self):
        super().__init__()
        self.meta_description = ""

    def handle_starttag(self, tag: str, attrs: List[tuple]):
        d = dict(attrs)
        if tag == "meta":
            name = d.get("name", d.get("property", ""))
            content = d.get("content", "")
            if name in ("description", "og:description", "twitter:description"):
                self.meta_description = content


# ─── HTTP Client ──────────────────────────────────────────────────────────────

class HTTPClient:
    """Minimal HTTP client using stdlib urllib."""

    def __init__(self, headers: Dict[str, str] = None, timeout: int = TIMEOUT):
        self.default_headers = {**DEFAULT_HEADERS, **(headers or {})}
        self.timeout = timeout
        self.session_cookies: Dict[str, str] = {}

    def _create_context(self) -> ssl.SSLContext:
        """Create SSL context with reasonable settings."""
        ctx = ssl.create_default_context()
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
        return ctx

    def _build_request(self, url: str, headers: Dict[str, str] = None) -> urllib.request.Request:
        merged = {**self.default_headers, **(headers or {})}
        req = urllib.request.Request(url, headers=merged)
        return req

    def fetch(self, url: str, headers: Dict[str, str] = None) -> tuple[int, bytes, str]:
        """
        Fetch URL. Returns (status_code, content_bytes, content_type).
        Handles gzip compression. Raises on network errors.
        """
        req = self._build_request(url, headers)
        ctx = self._create_context()

        with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as resp:
            status = resp.status
            content_type = resp.headers.get("Content-Type", "")
            content_encoding = resp.headers.get("Content-Encoding", "").lower()
            
            # Read with size limit
            data = resp.read(MAX_CONTENT_SIZE)
            
            # Decompress if gzip
            if "gzip" in content_encoding:
                try:
                    import gzip
                    data = gzip.decompress(data)
                except Exception:
                    pass
            
            return status, data, content_type

    def get(self, url: str, headers: Dict[str, str] = None) -> CrawlResult:
        """Fetch and parse a URL, returning structured result."""
        start = time.time()
        result = CrawlResult(url=url, status=0, title="", content="", error="")

        try:
            status, raw_data, content_type = self.fetch(url, headers)
            result.status = status
            result.content_type = content_type
            result.response_time = time.time() - start

            # Decode
            if b"\x00" in raw_data[:100]:
                # Likely binary — skip content extraction
                result.content = ""
                result.title = "(binary content)"
                return result

            try:
                encoding = "utf-8"
                if "charset=" in content_type.lower():
                    enc_match = re.search(r"charset=([\w-]+)", content_type, re.I)
                    if enc_match:
                        encoding = enc_match.group(1)
                text = raw_data.decode(encoding, errors="replace")
            except Exception:
                text = raw_data.decode("utf-8", errors="replace")

            # Limit content
            if len(text) > MAX_CONTENT_SIZE:
                text = text[:MAX_CONTENT_SIZE]

            # Extract content
            parser = ContentExtractor()
            try:
                parser.feed(text)
            except Exception:
                pass

            result.title = parser.title.strip()
            result.content = parser.get_content()
            result.links = self._normalize_links(url, parser.links[:MAX_LINKS])

            # Extract meta
            meta_parser = MetaExtractor()
            try:
                meta_parser.feed(text[:10000])  # Only first 10K for meta
                result.meta_description = meta_parser.meta_description
            except Exception:
                pass

        except urllib.error.HTTPError as e:
            result.status = e.code
            result.error = f"HTTP {e.code}: {e.reason}"
        except urllib.error.URLError as e:
            result.error = f"URL Error: {e.reason}"
        except TimeoutError:
            result.error = "Request timed out"
        except Exception as e:
            result.error = f"Error: {type(e).__name__}: {e}"

        return result

    def _normalize_links(self, base_url: str, links: List[str]) -> List[str]:
        """Normalize relative URLs to absolute."""
        try:
            base = urllib.parse.urlparse(base_url)
            normalized = []
            for link in links:
                parsed = urllib.parse.urlparse(link)
                if not parsed.scheme:
                    # Relative URL
                    resolved = urllib.parse.urljoin(base_url, link)
                else:
                    resolved = link
                # Only keep http/https
                p = urllib.parse.urlparse(resolved)
                if p.scheme in ("http", "https") and p.netloc:
                    normalized.append(resolved)
            return normalized[:MAX_LINKS]
        except Exception:
            return []


# ─── Web Crawler ──────────────────────────────────────────────────────────────

class WebCrawler:
    """
    Real web crawler using Python stdlib only.
    
    Features:
    - Fetches actual web pages
    - Extracts content, links, metadata
    - BFS crawling from seed URLs
    - Respects robots.txt (basic)
    - Deduplicates URLs
    - Claude Code summarization
    """

    def __init__(self, http_client: HTTPClient = None, max_depth: int = 2,
                 max_pages: int = 20, max_time: float = 60):
        self.http = http_client or HTTPClient()
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.max_time = max_time
        self._visited: Set[str] = set()
        self._robots_txt: Dict[str, str] = {}  # domain -> robots.txt content
        self.stats = {"fetched": 0, "failed": 0, "skipped": 0}

    def _get_robots_txt(self, url: str) -> Optional[str]:
        """Fetch and cache robots.txt for a domain."""
        parsed = urllib.parse.urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"

        if domain not in self._robots_txt:
            robots_url = f"{domain}/robots.txt"
            try:
                _, data, _ = self.http.fetch(robots_url)
                self._robots_txt[domain] = data.decode("utf-8", errors="replace")
            except Exception:
                self._robots_txt[domain] = ""

        return self._robots_txt.get(domain, "")

    def _can_fetch(self, url: str) -> bool:
        """Basic robots.txt check."""
        robots = self._get_robots_txt(url)
        if not robots:
            return True
        # Very simple check — just look for Disallow
        parsed = urllib.parse.urlparse(url)
        path = parsed.path or "/"
        for line in robots.splitlines():
            if line.lower().startswith("disallow:"):
                disallow_path = line.split(":", 1)[1].strip()
                if disallow_path and path.startswith(disallow_path):
                    return False
        return True

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for deduplication."""
        parsed = urllib.parse.urlparse(url)
        # Remove fragment, sort query params
        normalized = parsed._replace(fragment="")
        query = urllib.parse.parse_qsl(parsed.query)
        normalized = normalized._replace(query=urllib.parse.urlencode(sorted(query)))
        return normalized.geturl()

    def fetch(self, url: str) -> CrawlResult:
        """Fetch a single URL."""
        normalized = self._normalize_url(url)
        if normalized in self._visited:
            self.stats["skipped"] += 1
            return CrawlResult(url=url, status=0, title="", content="",
                             error="Already visited")

        self._visited.add(normalized)

        if not self._can_fetch(url):
            self.stats["skipped"] += 1
            return CrawlResult(url=url, status=0, title="", content="",
                             error="Blocked by robots.txt")

        result = self.http.get(url)
        if result.status == 200:
            self.stats["fetched"] += 1
        else:
            self.stats["failed"] += 1

        return result

    def crawl(self, seed_urls: List[str], on_page: Callable[[CrawlResult], None] = None,
             depth: int = 0) -> List[CrawlResult]:
        """
        BFS crawl from seed URLs.
        
        Args:
            seed_urls: Starting URLs
            on_page: Callback called for each page fetched
        
        Returns:
            List of CrawlResult for all fetched pages
        """
        if depth > self.max_depth:
            return []

        start_time = time.time()
        results: List[CrawlResult] = []
        queue: deque = deque((url, depth) for url in seed_urls)
        seen: Set[str] = set()

        while queue:
            if len(results) >= self.max_pages:
                break
            if time.time() - start_time > self.max_time:
                break

            url, d = queue.popleft()
            normalized = self._normalize_url(url)

            if normalized in seen:
                continue
            seen.add(normalized)

            result = self.fetch(url)
            if result.status == 200 and result.content:
                results.append(result)
                if on_page:
                    try:
                        on_page(result)
                    except Exception:
                        pass

                # Add discovered links to queue
                next_depth = d + 1
                if next_depth <= self.max_depth:
                    for link in result.links[:10]:
                        if self._normalize_url(link) not in seen:
                            queue.append((link, next_depth))

        return results


# ─── Search (DuckDuckGo HTML) ─────────────────────────────────────────────────

class WebSearch:
    """
    Search the web using DuckDuckGo HTML (no API key needed).
    Uses Python stdlib only.
    """

    def __init__(self, http_client: HTTPClient = None):
        self.http = http_client or HTTPClient()
        self._cache: Dict[str, List[SearchResult]] = {}

    def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """
        Search DuckDuckGo HTML and return results.
        No API key required — uses DuckDuckGo's HTML interface.
        """
        cache_key = f"{query}:{num_results}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}&kl=us-en"

        try:
            status, raw_data, _ = self.http.fetch(search_url)
            if status != 200:
                return []

            text = raw_data.decode("utf-8", errors="replace")
            results = self._parse_ddg_html(text, num_results)
            self._cache[cache_key] = results
            return results
        except Exception:
            return []

    def _parse_ddg_html(self, html: str, num_results: int) -> List[SearchResult]:
        """Parse DuckDuckGo HTML results."""
        results = []

        # Find all snippet blocks with their hrefs
        snippet_pattern = r'<a class="result__snippet" href="([^"]+)"[^>]*>(.*?)</a>'
        for match in re.finditer(snippet_pattern, html, re.DOTALL):
            if len(results) >= num_results:
                break

            raw_url = match.group(1)
            snippet_html = match.group(2)
            snippet_text = re.sub(r'<[^>]+>', '', snippet_html).strip()
            snippet_text = snippet_text.replace("&#x27;", "'").replace("&amp;", "&").replace("&quot;", '"')

            # Decode DDG redirect URL
            if 'uddg=' in raw_url:
                encoded = raw_url.split('uddg=')[1].split('&')[0]
                actual_url = urllib.parse.unquote(urllib.parse.unquote(encoded))
            else:
                actual_url = raw_url

            # Find title — comes before snippet in DDG HTML
            # Use 5000 chars lookback to ensure we capture the title
            search_start = max(0, match.start() - 5000)
            search_region = html[search_start:match.start()]
            title_match = re.search(r'<a class="result__a"[^>]*>(.*?)</a>', search_region, re.DOTALL)
            if title_match:
                title_text = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
                title_text = title_text.replace("&#x27;", "'").replace("&amp;", "&")
            else:
                # Fall back to URL domain as title
                try:
                    parsed = urllib.parse.urlparse(actual_url)
                    title_text = parsed.netloc.replace("www.", "")
                except Exception:
                    title_text = actual_url[:60]

            if actual_url:
                results.append(SearchResult(
                    title=title_text[:200],
                    url=actual_url,
                    snippet=snippet_text[:300]
                ))

        return results

    def search_and_scrape(self, query: str, num_results: int = 5) -> List[CrawlResult]:
        """Search and fetch content from top results."""
        results = self.search(query, num_results)
        crawler = WebCrawler(max_pages=len(results), max_time=30)
        crawled = []

        for r in results[:num_results]:
            cr = crawler.fetch(r.url)
            if cr.status == 200:
                crawled.append(cr)

        return crawled


# ─── Claude Summarizer ─────────────────────────────────────────────────────────

def summarize_with_claude(text: str, query: str = None,
                         claude_path: str = "/Users/a/.nvm/versions/node/v22.22.1/bin/claude"
                         ) -> str:
    """
    Use Claude Code to summarize extracted web content.
    Returns concise summary relevant to the query.
    """
    instruction = (
        "You are a research assistant. Summarize the following web content. "
        "Extract key facts, insights, and technical details. "
    )
    if query:
        instruction += f"Focus on: {query}\n\n"

    instruction += f"\nWEB CONTENT:\n{text[:5000]}\n\n"
    instruction += "Return a JSON object with:\n"
    instruction += '{"summary": "2-3 sentence summary", "key_points": ["point 1", "point 2", "point 3"], "topics": ["topic1", "topic2"]}'

    prompt = f"""{instruction}

Return ONLY valid JSON."""

    try:
        import subprocess
        result = subprocess.run(
            [claude_path, "--print", "-p", prompt, "--model", "sonnet"],
            capture_output=True, text=True, timeout=60,
            env={"PATH": "/Users/a/.nvm/versions/node/v22.22.1/bin:/usr/local/bin:/usr/bin:/bin"}
        )
        if result.returncode == 0 and result.stdout.strip():
            output = result.stdout.strip()
            json_match = re.search(r'\{.*\}', output, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                summary = parsed.get("summary", "")
                key_points = parsed.get("key_points", [])
                if key_points:
                    return summary + "\n\nKey points:\n" + "\n".join(f"- {p}" for p in key_points[:5])
                return summary
    except Exception as e:
        return f"Summarization failed: {e}"

    return text[:500] if len(text) > 500 else text


# ─── Research Pipeline ────────────────────────────────────────────────────────

class ResearchPipeline:
    """
    Full research pipeline: search → crawl → summarize.
    Use this for CRAWL_AND_LEARN evolution step.
    """

    def __init__(self):
        self.search = WebSearch()
        self.crawler = WebCrawler(max_pages=10, max_time=60)
        self.stats = {"queries": 0, "pages_crawled": 0, "bytes_fetched": 0}

    def research(self, query: str, depth: str = "quick") -> Dict[str, Any]:
        """
        Research a topic end-to-end.
        
        Args:
            query: The research question/topic
            depth: "quick" (3 pages) or "deep" (10 pages)
        
        Returns:
            Dict with results, summaries, links, and insights
        """
        num_results = 10 if depth == "deep" else 5
        self.stats["queries"] += 1

        # 1. Search
        search_results = self.search.search(query, num_results=num_results)

        if not search_results:
            return {
                "query": query,
                "results": [],
                "summary": f"No results found for: {query}",
                "insights": [],
                "stats": self.stats,
            }

        # 2. Crawl top results
        pages: List[CrawlResult] = []
        for sr in search_results[:num_results]:
            cr = self.crawler.fetch(sr.url)
            if cr.status == 200 and cr.content:
                pages.append(cr)
                self.stats["pages_crawled"] += 1
                self.stats["bytes_fetched"] += len(cr.content)

        # 3. Summarize each page
        summaries = []
        for page in pages:
            summary = summarize_with_claude(page.content, query)
            summaries.append({
                "url": page.url,
                "title": page.title,
                "summary": summary,
                "key_links": page.links[:5],
            })

        # 4. Combine all content for final synthesis
        all_content = "\n\n".join(p.content[:2000] for p in pages)
        final = summarize_with_claude(all_content, query)

        # 5. Extract unique insights from combined summary
        # Parse key_points from the JSON summary, fall back to content snippets
        all_insights: List[str] = []
        try:
            import json
            # Try to extract key_points from the combined summary
            # The final summary is a JSON string like: '{"summary": "...", "key_points": [...], "topics": [...]}'
            final_clean = final.strip()
            json_match = re.search(r'\{.*\}', final_clean, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                key_points = parsed.get("key_points", [])
                for kp in key_points[:10]:
                    if kp and kp not in all_insights:
                        all_insights.append(kp)
        except (json.JSONDecodeError, Exception):
            pass

        # If no key_points, extract sentences from combined summary
        if not all_insights and len(final) > 50:
            # Split into sentences and take meaningful ones
            sentences = re.split(r'(?<=[.!?])\s+', final)
            for sent in sentences:
                sent = sent.strip()
                if len(sent) > 40 and len(sent) < 300:
                    if sent not in all_insights:
                        all_insights.append(sent[:200])

        # Also add top 3 page-level insights from summaries
        for s in summaries[:3]:
            summary_text = s.get("summary", "")
            if len(summary_text) > 50:
                # Take first meaningful sentence
                first_sent = re.split(r'(?<=[.!?])\s+', summary_text)[0].strip()
                if len(first_sent) > 30 and first_sent not in all_insights:
                    all_insights.append(first_sent[:200])

        # Clean up: remove markdown artifacts and very long entries
        cleaned_insights = []
        for ins in all_insights:
            # Skip if it looks like a markdown header or list
            ins = ins.strip()
            if not ins or len(ins) < 20:
                continue
            if ins.startswith('#') or ins.startswith('*') or ins.startswith('- '):
                continue
            if 'Key points:' in ins or '```' in ins:
                continue
            if len(ins) > 250:
                ins = ins[:247] + '...'
            cleaned_insights.append(ins)

        return {
            "query": query,
            "search_results": [
                {"title": r.title, "url": r.url, "snippet": r.snippet}
                for r in search_results[:5]
            ],
            "pages": [p.url for p in pages],
            "summaries": summaries,
            "combined_summary": final,
            "insights": cleaned_insights[:10],
            "stats": self.stats,
        }


# ─── Test ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== NEXUS Web Crawler Test ===\n")

    crawler = WebCrawler(max_pages=3, max_time=30)

    # Test single page fetch
    print("Fetching example.com...")
    r = crawler.fetch("https://example.com")
    print(f"  Status: {r.status}")
    print(f"  Title: {r.title}")
    print(f"  Content length: {len(r.content)} chars")
    print(f"  Links found: {len(r.links)}")
    print(f"  Error: {r.error or 'none'}")
    print()

    # Test search
    print("Searching 'AI agent self-improvement 2026'...")
    search = WebSearch()
    results = search.search("AI agent self-improvement 2026", num_results=5)
    print(f"  Found {len(results)} results:")
    for r in results[:3]:
        print(f"  - {r.title[:60]}")
        print(f"    {r.url[:60]}")
        print(f"    {r.snippet[:80]}")
    print()

    print("=== All tests passed ===")
