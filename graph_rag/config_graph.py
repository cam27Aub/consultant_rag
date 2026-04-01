import os

def _secret(key, default=""):
    """Read from Streamlit secrets first, then environment variables."""
    try:
        import streamlit as st
        return st.secrets.get(key, os.getenv(key, default))
    except Exception:
        return os.getenv(key, default)

AZURE_OPENAI_ENDPOINT    = _secret("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_VERSION = "2024-02-01"
AZURE_OPENAI_KEY         = _secret("AZURE_OPENAI_KEY")
AZURE_CHAT_DEPLOYMENT    = "gpt-4o"
AZURE_EMBED_DEPLOYMENT   = "text-embedding-3-large"
AZURE_EMBED_DIM          = 3072

GREMLIN_ENDPOINT = _secret("GREMLIN_ENDPOINT")
GREMLIN_KEY      = _secret("GREMLIN_KEY")
GREMLIN_DATABASE = "consulting_graph"
GREMLIN_GRAPH    = "knowledge"

SUPPORTED_EXTENSIONS = {".pdf", ".pptx", ".docx"}
MAX_ENTITIES_PER_CHUNK = 10
CHUNK_WORDS = 400
CHUNK_OVERLAP = 60
