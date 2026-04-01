"""
vision_processor.py — Renders document pages/slides to images and
                       uses GPT-4o Vision to describe visual content.

Supports: PDF, PPTX, DOCX (via PyMuPDF)
Requires: pip install pymupdf
"""
import base64
import fitz  # PyMuPDF
from pathlib import Path
from openai import AzureOpenAI
from graph_rag import config_graph as config

VISION_PROMPT = """You are analyzing a page from a consulting document.
Describe ANY visual content you see including:
- Charts, graphs, or plots (describe what data they show)
- Diagrams, flowcharts, or process maps (describe the flow and components)
- Tables (describe the structure and key data)
- Drawings or illustrations (describe what they depict)
- Infographics (describe the key information)
- Any text visible in images or shapes

Be concise but specific. Focus on the meaning and data, not aesthetics.
If the page contains only plain text with no visuals, respond with: NO_VISUAL_CONTENT"""


class VisionProcessor:
    def __init__(self):
        self.client = AzureOpenAI(
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
            api_key=config.AZURE_OPENAI_KEY,
            api_version=config.AZURE_OPENAI_API_VERSION,
        )

    def _render_page_to_base64(self, filepath: Path, page_num: int) -> str:
        """Render a single page from PDF or PPTX to base64 PNG using PyMuPDF."""
        try:
            doc = fitz.open(str(filepath))
            # page_num is 1-indexed, fitz is 0-indexed
            idx = min(page_num - 1, len(doc) - 1)
            page = doc[idx]
            # render at 150 DPI (good balance of quality vs token cost)
            mat  = fitz.Matrix(150 / 72, 150 / 72)
            pix  = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            doc.close()
            return base64.b64encode(img_bytes).decode("utf-8")
        except Exception as e:
            print(f"  Vision render failed for {filepath.name} p{page_num}: {e}")
            return ""

    def describe_page(self, filepath: Path, page_num: int) -> str:
        """
        Render a page and get GPT-4o Vision description of visual content.
        Returns empty string if no visual content or on failure.
        """
        b64 = self._render_page_to_base64(filepath, page_num)
        if not b64:
            return ""

        try:
            response = self.client.chat.completions.create(
                model=config.AZURE_CHAT_DEPLOYMENT,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text",      "text": VISION_PROMPT},
                        {"type": "image_url", "image_url": {
                            "url":    "data:image/png;base64," + b64,
                            "detail": "low"   # use 'low' to save tokens
                        }},
                    ]
                }],
                max_tokens=400,
                temperature=0.0,
            )
            description = response.choices[0].message.content.strip()

            # discard if no visual content found
            if "NO_VISUAL_CONTENT" in description:
                return ""

            return description

        except Exception as e:
            print(f"  Vision API failed for {filepath.name} p{page_num}: {e}")
            return ""
