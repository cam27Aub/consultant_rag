import os

MODE = "azure"

DOCS_DIR   = "./sample_docs"
STORE_DIR  = "./store"
STORE_FILE = "./store/index.json"
EVAL_DIR   = "./evaluation/results"

SUPPORTED_EXTENSIONS = {".pdf", ".pptx", ".docx"}

CHUNK_STRATEGY  = "sentence"
CHUNK_SIZE      = 400
CHUNK_OVERLAP   = 60
MIN_CHUNK_WORDS = 15

LOCAL_EMBED_DIM = 128

AZURE_OPENAI_ENDPOINT    = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_KEY         = os.getenv("AZURE_OPENAI_KEY", "")
AZURE_OPENAI_API_VERSION = "2024-02-01"
AZURE_EMBED_DEPLOYMENT   = "text-embedding-3-large"
AZURE_CHAT_DEPLOYMENT    = "gpt-4o"
AZURE_EMBED_DIM          = 3072

AZURE_SEARCH_ENDPOINT    = os.getenv("AZURE_SEARCH_ENDPOINT", "")
AZURE_SEARCH_KEY         = os.getenv("AZURE_SEARCH_KEY", "")
AZURE_SEARCH_INDEX       = "consulting-rag"

RETRIEVAL_MODE   = "hybrid"
TOP_K            = 5
RRF_K            = 60

EVAL_TOP_K = [1, 3, 5]
