"""
Persistent chat memory using Azure Cosmos DB (NoSQL API).
Stores conversations, messages, and user preferences.
"""

from azure.cosmos import CosmosClient, PartitionKey, exceptions
import os, time

# Cosmos DB config
COSMOS_ENDPOINT = os.getenv("COSMOS_CHAT_ENDPOINT", "")
COSMOS_KEY = os.getenv("COSMOS_CHAT_KEY", "")
DATABASE_NAME = "chat_memory"

_client = None
_db = None
_conversations_container = None
_messages_container = None
_preferences_container = None


def init_db():
    """Initialize Cosmos DB client and container references."""
    global _client, _db, _conversations_container, _messages_container, _preferences_container

    if not COSMOS_ENDPOINT or not COSMOS_KEY:
        print("[chat_memory] WARNING: COSMOS_CHAT_ENDPOINT or COSMOS_CHAT_KEY not set. Memory disabled.")
        return False

    try:
        _client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
        _db = _client.get_database_client(DATABASE_NAME)
        _conversations_container = _db.get_container_client("conversations")
        _messages_container = _db.get_container_client("messages")
        _preferences_container = _db.get_container_client("user_preferences")
        # Quick connectivity check
        _conversations_container.read()
        print("[chat_memory] Cosmos DB connected successfully.")
        return True
    except Exception as e:
        print(f"[chat_memory] Failed to connect to Cosmos DB: {e}")
        return False


def _is_ready():
    return _conversations_container is not None


# ── Conversations ──────────────────────────────────────────────

def list_conversations():
    """Return all conversations sorted by updated_at desc (without messages)."""
    if not _is_ready():
        return []
    try:
        query = "SELECT c.id, c.title, c.createdAt, c.updatedAt FROM c ORDER BY c.updatedAt DESC"
        items = list(_conversations_container.query_items(query=query, enable_cross_partition_query=True))
        return items
    except Exception as e:
        print(f"[chat_memory] Error listing conversations: {e}")
        return []


def get_conversation(conversation_id: str):
    """Get a single conversation with all its messages."""
    if not _is_ready():
        return None
    try:
        convo = _conversations_container.read_item(item=conversation_id, partition_key=conversation_id)
        # Get messages for this conversation
        query = "SELECT * FROM m WHERE m.conversation_id = @cid ORDER BY m.timestamp ASC"
        params = [{"name": "@cid", "value": conversation_id}]
        messages = list(_messages_container.query_items(
            query=query, parameters=params, enable_cross_partition_query=False
        ))
        # Clean Cosmos metadata from messages
        clean_messages = []
        for m in messages:
            clean_messages.append({
                "id": m["id"],
                "role": m["role"],
                "content": m["content"],
                "responseType": m.get("responseType", "text"),
                "fileName": m.get("fileName"),
                "downloadUrl": m.get("downloadUrl"),
                "timestamp": m["timestamp"],
            })
        return {
            "id": convo["id"],
            "title": convo.get("title", "New Chat"),
            "messages": clean_messages,
            "createdAt": convo.get("createdAt", 0),
            "updatedAt": convo.get("updatedAt", 0),
        }
    except exceptions.CosmosResourceNotFoundError:
        return None
    except Exception as e:
        print(f"[chat_memory] Error getting conversation {conversation_id}: {e}")
        return None


def save_conversation(conversation: dict):
    """Upsert a conversation and all its messages."""
    if not _is_ready():
        return False
    try:
        convo_id = conversation["id"]

        # Upsert conversation metadata
        convo_doc = {
            "id": convo_id,
            "title": conversation.get("title", "New Chat"),
            "createdAt": conversation.get("createdAt", int(time.time() * 1000)),
            "updatedAt": conversation.get("updatedAt", int(time.time() * 1000)),
        }
        _conversations_container.upsert_item(convo_doc)

        # Upsert all messages
        for msg in conversation.get("messages", []):
            msg_doc = {
                "id": msg["id"],
                "conversation_id": convo_id,
                "role": msg["role"],
                "content": msg["content"],
                "responseType": msg.get("responseType", "text"),
                "fileName": msg.get("fileName"),
                "downloadUrl": msg.get("downloadUrl"),
                "timestamp": msg.get("timestamp", int(time.time() * 1000)),
            }
            _messages_container.upsert_item(msg_doc)

        return True
    except Exception as e:
        print(f"[chat_memory] Error saving conversation: {e}")
        return False


def delete_conversation(conversation_id: str):
    """Delete a conversation and all its messages."""
    if not _is_ready():
        return False
    try:
        # Delete all messages for this conversation
        query = "SELECT m.id FROM m WHERE m.conversation_id = @cid"
        params = [{"name": "@cid", "value": conversation_id}]
        messages = list(_messages_container.query_items(
            query=query, parameters=params, enable_cross_partition_query=False
        ))
        for msg in messages:
            _messages_container.delete_item(item=msg["id"], partition_key=conversation_id)

        # Delete the conversation
        _conversations_container.delete_item(item=conversation_id, partition_key=conversation_id)
        return True
    except exceptions.CosmosResourceNotFoundError:
        return True  # Already deleted
    except Exception as e:
        print(f"[chat_memory] Error deleting conversation: {e}")
        return False


# ── User Preferences ──────────────────────────────────────────

def get_preferences():
    """Get all user preferences as a dict."""
    if not _is_ready():
        return {}
    try:
        query = "SELECT * FROM p"
        items = list(_preferences_container.query_items(query=query, enable_cross_partition_query=True))
        return {item["key"]: item["value"] for item in items}
    except Exception as e:
        print(f"[chat_memory] Error getting preferences: {e}")
        return {}


def save_preference(key: str, value: str):
    """Save a single preference."""
    if not _is_ready():
        return False
    try:
        doc = {"id": key, "key": key, "value": value}
        _preferences_container.upsert_item(doc)
        return True
    except Exception as e:
        print(f"[chat_memory] Error saving preference: {e}")
        return False


def save_preferences(prefs: dict):
    """Save multiple preferences at once."""
    if not _is_ready():
        return False
    try:
        for key, value in prefs.items():
            doc = {"id": key, "key": key, "value": str(value)}
            _preferences_container.upsert_item(doc)
        return True
    except Exception as e:
        print(f"[chat_memory] Error saving preferences: {e}")
        return False
