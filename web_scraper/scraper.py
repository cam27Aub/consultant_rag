import time
import re
import hashlib
import urllib.robotparser
from urllib.parse import urlparse, urljoin, quote_plus
from typing import Optional
import requests
from bs4 import BeautifulSoup
from web_scraper import config_scraper as config


PAYWALL_SIGNALS = [
    "subscribe to read", "subscription required", "sign in to read",
    "premium content", "members only", "create a free account to continue",
    "you have reached your article limit", "to continue reading",
    "exclusive to subscribers", "log in to access",
]

NOISE_SELECTORS = [
    "nav", "header", "footer", "aside", ".cookie", ".banner",
    ".newsletter", ".subscribe", ".ad", ".advertisement",
    ".sidebar", ".popup", ".modal", "script", "style",
    ".related-articles", ".recommended", ".social-share",
]


class ScrapedResult:
    def __init__(self, url, title, content, source_name,
                 category, trust, is_paywalled=False, error=None):
        self.url          = url
        self.title        = title
        self.content      = content
        self.source_name  = source_name
        self.category     = category
        self.trust        = trust
        self.is_paywalled = is_paywalled
        self.error        = error
        self.content_hash = hashlib.md5(content.encode()).hexdigest()[:8] if content else ""

    def is_valid(self):
        return (not self.error and not self.is_paywalled
                and self.content and len(self.content) > 100)


class TrustedScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent":      config.USER_AGENT,
            "Accept":          "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        })
        self._robots_cache = {}
        self._seen_hashes  = set()

    def _get_source(self, url: str) -> Optional[dict]:
        """Return source config if URL belongs to a trusted domain."""
        domain = urlparse(url).netloc.lower()
        domain = domain.replace("www.", "").replace("www2.", "")
        for trusted_domain, info in config.TRUSTED_SOURCES.items():
            if domain == trusted_domain or domain.endswith("." + trusted_domain):
                return {**info, "domain": trusted_domain}
        return None

    def is_trusted(self, url: str) -> bool:
        return self._get_source(url) is not None

    def _can_fetch(self, url: str) -> bool:
        parsed = urlparse(url)
        robots_url = "%s://%s/robots.txt" % (parsed.scheme, parsed.netloc)
        if robots_url not in self._robots_cache:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(robots_url)
            try:
                rp.read()
            except Exception:
                # if robots.txt unreachable, assume allowed
                self._robots_cache[robots_url] = None
                return True
            self._robots_cache[robots_url] = rp
        rp = self._robots_cache[robots_url]
        if rp is None:
            return True
        return rp.can_fetch(config.USER_AGENT, url)

    def _is_paywalled(self, soup: BeautifulSoup, raw_html: str) -> bool:
        text = raw_html.lower()
        return any(signal in text for signal in PAYWALL_SIGNALS)

    def _extract_content(self, soup: BeautifulSoup) -> tuple:
        """Returns (title, clean_content)."""
        # title
        title = ""
        if soup.find("h1"):
            title = soup.find("h1").get_text(strip=True)
        elif soup.find("title"):
            title = soup.find("title").get_text(strip=True)

        # strip noise
        for selector in NOISE_SELECTORS:
            for tag in soup.select(selector):
                tag.decompose()

        # try article/main content areas first
        content_tag = (
            soup.find("article") or
            soup.find("main") or
            soup.find(class_=re.compile(r"(article|content|body|text|post)", re.I)) or
            soup.find("body")
        )
        if content_tag:
            text = content_tag.get_text(separator=" ", strip=True)
        else:
            text = soup.get_text(separator=" ", strip=True)

        # clean whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return title, text[:config.MAX_CONTENT_CHARS]

    def _fetch_arxiv(self, query: str) -> list:
        import xml.etree.ElementTree as ET
        results = []
        url = config.TRUSTED_SOURCES["arxiv.org"]["api"].format(
            query=quote_plus(query)
        )
        try:
            resp = self.session.get(url, timeout=config.REQUEST_TIMEOUT)
            root = ET.fromstring(resp.content)
            ns   = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("atom:entry", ns)[:config.MAX_RESULTS]:
                title   = entry.find("atom:title", ns).text.strip()
                summary = entry.find("atom:summary", ns).text.strip()
                link    = entry.find("atom:id", ns).text.strip()
                results.append(ScrapedResult(
                    url=link, title=title,
                    content=summary[:config.MAX_CONTENT_CHARS],
                    source_name="arXiv", category="academic", trust=5,
                ))
        except Exception as e:
            print("  arXiv API error: %s" % e)
        return results

    def _fetch_worldbank(self, query: str) -> list:
        results = []
        url = "https://search.worldbank.org/api/v2/wds?format=json&rows=3&qterm=%s" % quote_plus(query)
        try:
            resp = self.session.get(url, timeout=config.REQUEST_TIMEOUT)
            data = resp.json()
            for doc in data.get("documents", {}).values():
                if not isinstance(doc, dict):
                    continue
                title   = doc.get("display_title", "")
                content = doc.get("txtfield", "") or doc.get("teaser", "")
                link    = doc.get("url", "https://www.worldbank.org")
                if title and content:
                    results.append(ScrapedResult(
                        url=link, title=title,
                        content=content[:config.MAX_CONTENT_CHARS],
                        source_name="World Bank", category="government", trust=5,
                    ))
        except Exception as e:
            print("  World Bank API error: %s" % e)
        return results

    def fetch_url(self, url: str) -> ScrapedResult:
        source = self._get_source(url)
        if not source:
            return ScrapedResult(
                url=url, title="", content="",
                source_name="Unknown", category="unknown", trust=0,
                error="Domain not in trusted whitelist",
            )

        if not self._can_fetch(url):
            return ScrapedResult(
                url=url, title="", content="",
                source_name=source["name"], category=source["category"],
                trust=source["trust"],
                error="Blocked by robots.txt",
            )

        time.sleep(config.RATE_LIMIT_DELAY)

        try:
            resp = self.session.get(url, timeout=config.REQUEST_TIMEOUT,
                                    allow_redirects=True)
            if resp.status_code != 200:
                return ScrapedResult(
                    url=url, title="", content="",
                    source_name=source["name"], category=source["category"],
                    trust=source["trust"],
                    error="HTTP %d" % resp.status_code,
                )

            soup     = BeautifulSoup(resp.text, "html.parser")
            paywalled = self._is_paywalled(soup, resp.text)
            title, content = self._extract_content(soup)

            result = ScrapedResult(
                url=url, title=title, content=content,
                source_name=source["name"], category=source["category"],
                trust=source["trust"], is_paywalled=paywalled,
            )

            # dedup by content hash
            if result.content_hash in self._seen_hashes:
                result.error = "Duplicate content"
            else:
                self._seen_hashes.add(result.content_hash)

            return result

        except requests.exceptions.Timeout:
            return ScrapedResult(url=url, title="", content="",
                source_name=source["name"], category=source["category"],
                trust=source["trust"], error="Request timed out")
        except Exception as e:
            return ScrapedResult(url=url, title="", content="",
                source_name=source["name"], category=source["category"],
                trust=source["trust"], error=str(e))

    def search_ddg(self, query: str, source_domain: str) -> list:
        """
        Search DuckDuckGo restricted to a trusted domain.
        Returns list of URLs to fetch.
        """
        search_query = "site:%s %s" % (source_domain, query)
        url = "https://html.duckduckgo.com/html/?q=%s" % quote_plus(search_query)
        urls = []
        try:
            resp = self.session.get(url, timeout=config.REQUEST_TIMEOUT)
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.select(".result__a")[:3]:
                href = a.get("href", "")
                if href and source_domain in href:
                    urls.append(href)
        except Exception:
            pass
        return urls

    def search(self, query: str, categories: list = None,
               max_results: int = None) -> list:
        """
        Search trusted sources and return valid ScrapedResults.
        """
        max_r    = max_results or config.MAX_RESULTS
        results  = []

        # use arXiv API for academic queries
        if not categories or "academic" in categories:
            results.extend(self._fetch_arxiv(query))

        # use World Bank API for government/data queries
        if not categories or "government" in categories:
            results.extend(self._fetch_worldbank(query))

        # for other sources: DuckDuckGo site-search then fetch
        target_domains = [
            d for d, info in config.TRUSTED_SOURCES.items()
            if (not categories or info["category"] in categories)
            and "api" not in info  # skip those with dedicated APIs
        ]

        for domain in target_domains:
            if len(results) >= max_r:
                break
            urls = self.search_ddg(query, domain)
            for url in urls[:2]:
                if len(results) >= max_r:
                    break
                result = self.fetch_url(url)
                if result.is_valid():
                    results.append(result)
                    print("  %s -- %s" % (result.source_name, result.title[:50]))
                elif result.error:
                    print("  %s -- %s" % (result.source_name, result.error))

        return [r for r in results if r.is_valid()][:max_r]
