import os

def _secret(key, default=""):
    """Read from Streamlit secrets first, then environment variables."""
    try:
        import streamlit as st
        return st.secrets.get(key, os.getenv(key, default))
    except Exception:
        return os.getenv(key, default)

# Reuse from your existing consultant_rag/config.py
AZURE_OPENAI_ENDPOINT    = _secret("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY         = _secret("AZURE_OPENAI_KEY")
AZURE_OPENAI_API_VERSION = "2024-02-01"
AZURE_CHAT_DEPLOYMENT    = "gpt-4o"

REQUEST_TIMEOUT   = 15          # seconds per request
RATE_LIMIT_DELAY  = 1.5         # seconds between requests
MAX_RESULTS       = 5           # max sources to fetch per query
MAX_CONTENT_CHARS = 4000        # max chars to extract per page
USER_AGENT        = "ConsultantIQ-Research/1.0 (Academic Research Bot)"

# Each entry: domain -> {name, category, search_url, trust_level}
TRUSTED_SOURCES = {

    "mckinsey.com": {
        "name": "McKinsey & Company",
        "category": "consulting",
        "trust": 5,
        "search": "https://www.mckinsey.com/search#q={query}",
        "base": "https://www.mckinsey.com",
    },
    "bcg.com": {
        "name": "Boston Consulting Group",
        "category": "consulting",
        "trust": 5,
        "search": "https://www.bcg.com/search#query={query}",
        "base": "https://www.bcg.com",
    },
    "deloitte.com": {
        "name": "Deloitte Insights",
        "category": "consulting",
        "trust": 5,
        "search": "https://www2.deloitte.com/us/en/insights/search.html?q={query}",
        "base": "https://www2.deloitte.com",
    },
    "hbr.org": {
        "name": "Harvard Business Review",
        "category": "consulting",
        "trust": 5,
        "search": "https://hbr.org/search?term={query}",
        "base": "https://hbr.org",
    },
    "pwc.com": {
        "name": "PwC Insights",
        "category": "consulting",
        "trust": 4,
        "search": "https://www.pwc.com/gx/en/search.html?q={query}",
        "base": "https://www.pwc.com",
    },

    "reuters.com": {
        "name": "Reuters",
        "category": "financial_news",
        "trust": 5,
        "search": "https://www.reuters.com/site-search/?query={query}",
        "base": "https://www.reuters.com",
    },
    "ft.com": {
        "name": "Financial Times",
        "category": "financial_news",
        "trust": 5,
        "search": "https://www.ft.com/search?q={query}",
        "base": "https://www.ft.com",
    },
    "wsj.com": {
        "name": "Wall Street Journal",
        "category": "financial_news",
        "trust": 5,
        "search": "https://www.wsj.com/search?query={query}",
        "base": "https://www.wsj.com",
    },
    "bloomberg.com": {
        "name": "Bloomberg",
        "category": "financial_news",
        "trust": 5,
        "search": "https://www.bloomberg.com/search?query={query}",
        "base": "https://www.bloomberg.com",
    },

    "arxiv.org": {
        "name": "arXiv",
        "category": "academic",
        "trust": 5,
        "search": "https://arxiv.org/search/?searchtype=all&query={query}",
        "base": "https://arxiv.org",
        "api": "https://export.arxiv.org/api/query?search_query=all:{query}&max_results=5",
    },
    "ssrn.com": {
        "name": "SSRN",
        "category": "academic",
        "trust": 5,
        "search": "https://papers.ssrn.com/sol3/results.cfm?txtkey={query}",
        "base": "https://papers.ssrn.com",
    },

    "bbc.com": {
        "name": "BBC News",
        "category": "news",
        "trust": 5,
        "search": "https://www.bbc.co.uk/search?q={query}",
        "base": "https://www.bbc.com",
    },
    "economist.com": {
        "name": "The Economist",
        "category": "news",
        "trust": 5,
        "search": "https://www.economist.com/search?q={query}",
        "base": "https://www.economist.com",
    },

    "worldbank.org": {
        "name": "World Bank",
        "category": "government",
        "trust": 5,
        "search": "https://www.worldbank.org/en/search?q={query}",
        "base": "https://www.worldbank.org",
        "api": "https://search.worldbank.org/api/v2/wds?format=json&rows=5&qterm={query}",
    },
    "imf.org": {
        "name": "IMF",
        "category": "government",
        "trust": 5,
        "search": "https://www.imf.org/en/Search#q={query}",
        "base": "https://www.imf.org",
    },
    "sec.gov": {
        "name": "SEC EDGAR",
        "category": "government",
        "trust": 5,
        "search": "https://efts.sec.gov/LATEST/search-index?q={query}",
        "base": "https://www.sec.gov",
        "api": "https://efts.sec.gov/LATEST/search-index?q={query}&hits.hits.total.value=5",
    },
}

# Category display names
CATEGORY_LABELS = {
    "consulting":     "Consulting & Business",
    "financial_news": "Financial News",
    "academic":       "Academic & Research",
    "news":           "News",
    "government":     "Government & Regulatory",
}
