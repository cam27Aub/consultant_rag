"""
extractor.py — Uses GPT-4o to extract entities and relationships from text chunks.
"""
import json
import re
from openai import AzureOpenAI
from graph_rag import config_graph as config

SYSTEM_PROMPT = """You are a knowledge graph extraction engine for academic, technical, and consulting documents.

Given a text passage, extract:
1. ENTITIES — capture ALL of the following types:
   - Named frameworks, models, methodologies (e.g. "Porter's Five Forces", "Big Data Value Chain")
   - Metrics, KPIs, and measurements (e.g. "EBITDA", "NPS Score")
   - Tools, platforms, technologies (e.g. "Azure OpenAI", "Hadoop")
   - Companies, organizations, institutions
   - Roles and job functions (e.g. "Engagement Manager", "Data Steward")
   - Processes and workflows (e.g. "Data Curation", "Model Training Pipeline")
   - KEY ARGUMENTS and CLAIMS — important ideas or assertions made in the text, even if not a proper noun
     (e.g. "Dataset Primacy in AI", "Model Convergence Hypothesis", "Architecture Independence Principle")
   - ABSTRACT CONCEPTS that are central to the passage's meaning
     (e.g. "Data Lifecycle", "Model Behavior Determinism", "Interstitial Frequency Distribution")

2. RELATIONSHIPS — directed connections between entities.

Return ONLY valid JSON in this exact format:
{
  "entities": [
    {
      "id": "<snake_case_unique_id>",
      "label": "<one of: Framework | Metric | Company | Strategy | Tool | Role | Process | Concept | Argument | Technology>",
      "name": "<full display name — for arguments/claims, give a descriptive name that captures the core idea>",
      "description": "<one sentence description that captures the meaning precisely>"
    }
  ],
  "relationships": [
    {
      "from": "<entity_id>",
      "to": "<entity_id>",
      "type": "<SCREAMING_SNAKE_CASE e.g. HAS_COMPONENT, USED_IN, MEASURES, PART_OF, LEADS_TO, DETERMINES, CONTRADICTS, SUPPORTS, REQUIRES, DEFINES>"
    }
  ]
}

Rules:
- Extract between 5 and 12 entities per passage
- For key arguments: name them descriptively (e.g. "Dataset Determines Model Behavior" not just "dataset")
- Entity ids must be snake_case and unique — for arguments add a suffix like "_principle" or "_claim"
- Only create relationships between entities extracted in the same response
- Return valid JSON only — no markdown, no explanation
"""


class EntityExtractor:
    def __init__(self):
        self.client = AzureOpenAI(
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
            api_key=config.AZURE_OPENAI_KEY,
            api_version=config.AZURE_OPENAI_API_VERSION,
        )

    def extract(self, text: str, source: str, page: int) -> dict:
        try:
            response = self.client.chat.completions.create(
                model=config.AZURE_CHAT_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": "SOURCE: %s | PAGE: %d\n\nTEXT:\n%s" % (source, page, text[:2000])}
                ],
                temperature=0.0,
                max_tokens=1800,
            )
            raw = response.choices[0].message.content.strip()
            raw = re.sub(r"^```json\s*", "", raw)
            raw = re.sub(r"\s*```$",    "", raw)

            result = json.loads(raw)

            for e in result.get("entities", []):
                e["source"] = source
                e["page"]   = page

            return result

        except (json.JSONDecodeError, Exception) as ex:
            print("  Extraction failed for %s p%d: %s" % (source, page, ex))
            return {"entities": [], "relationships": []}
