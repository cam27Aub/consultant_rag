import json
import re
from openai import AzureOpenAI
from web_scraper.scraper import TrustedScraper
from web_scraper import config_scraper as config

PLAN_PROMPT = """You are a research planning agent. Given a user question, decide:
1. Which source categories are most relevant
2. What specific search queries to run (1-3 queries max)

Available categories: consulting, financial_news, academic, news, government

Return ONLY valid JSON in this format:
{
  "categories": ["consulting", "financial_news"],
  "queries": ["query 1", "query 2"],
  "reasoning": "one sentence explaining why these sources"
}"""

ANSWER_PROMPT = """You are ConsultantIQ Research, a professional research assistant.
Answer the user's question using ONLY the web sources provided below.

SOURCES:
{sources}

Rules:
1. Use ONLY information from the provided sources — no general knowledge
2. Cite every claim with [Source N] inline
3. If sources are paywalled or insufficient, say so clearly
4. Be concise, professional, and structured
5. End with a References section listing all sources used

QUESTION: {question}"""


class SearchAgent:
    def __init__(self):
        self.client  = AzureOpenAI(
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
            api_key=config.AZURE_OPENAI_KEY,
            api_version=config.AZURE_OPENAI_API_VERSION,
        )
        self.scraper = TrustedScraper()

    def _plan_search(self, question: str) -> dict:
        """Use GPT-4o to decide which sources and queries to use."""
        try:
            resp = self.client.chat.completions.create(
                model=config.AZURE_CHAT_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": PLAN_PROMPT},
                    {"role": "user",   "content": question},
                ],
                temperature=0.0,
                max_tokens=300,
            )
            raw = resp.choices[0].message.content.strip()
            raw = re.sub(r"^```json\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            return json.loads(raw)
        except Exception:
            # fallback plan
            return {
                "categories": list(config.CATEGORY_LABELS.keys()),
                "queries":    [question],
                "reasoning":  "Broad search across all categories",
            }

    def _format_sources(self, results: list) -> str:
        """Format scraped results as a numbered source list for GPT-4o."""
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(
                "[Source %d] %s — %s\nURL: %s\n%s"
                % (i, r.source_name, r.title, r.url,
                   r.content[:1500])
            )
        return "\n\n---\n\n".join(lines)

    def search_and_answer(self, question: str,
                          categories: list = None) -> dict:
        """
        Full pipeline: plan → scrape → answer.
        Returns dict with answer, sources, plan.
        """
        # Step 1: plan
        plan = self._plan_search(question)
        effective_cats = categories or plan.get("categories", [])
        queries        = plan.get("queries", [question])

        print("  Search plan: %s" % plan.get("reasoning", ""))
        print("  Categories: %s" % ", ".join(effective_cats))
        print("  Queries: %s" % ", ".join(queries))

        # Step 2: scrape
        all_results = []
        seen_urls   = set()
        for query in queries:
            results = self.scraper.search(
                query,
                categories=effective_cats,
                max_results=config.MAX_RESULTS,
            )
            for r in results:
                if r.url not in seen_urls:
                    seen_urls.add(r.url)
                    all_results.append(r)

        print("  %d valid sources fetched" % len(all_results))

        if not all_results:
            return {
                "answer":  "No accessible content could be retrieved from trusted sources for this query. The sources may be paywalled or temporarily unavailable.",
                "sources": [],
                "plan":    plan,
            }

        # Step 3: synthesise answer
        sources_text = self._format_sources(all_results)
        resp = self.client.chat.completions.create(
            model=config.AZURE_CHAT_DEPLOYMENT,
            messages=[{
                "role": "user",
                "content": ANSWER_PROMPT.format(
                    sources=sources_text,
                    question=question,
                ),
            }],
            temperature=0.1,
            max_tokens=1000,
        )
        answer = resp.choices[0].message.content.strip()

        return {
            "answer":  answer,
            "sources": all_results,
            "plan":    plan,
        }
