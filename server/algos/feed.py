import os
import json
import httpx
import numpy as np
import onnxruntime as ort
from transformers import AutoTokenizer

from server.models import Feed, FeedSource
from atproto import Client

CUSTOM_API_URL = os.environ.get("CUSTOM_API_URL")

# --- ONNX model setup ---
MODEL_PATH = os.path.join(os.path.dirname(__file__), "all-MiniLM-L6-v2.onnx")
TOKENIZER_NAME = "sentence-transformers/all-MiniLM-L6-v2"

tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_NAME)
session = ort.InferenceSession(MODEL_PATH, providers=["CPUExecutionProvider"])

def encode_onnx(texts):
    """Return embedding vectors using the ONNX model."""
    if isinstance(texts, str):
        texts = [texts]
    inputs = tokenizer(texts, padding=True, truncation=True, return_tensors="np")
    outputs = session.run(None, dict(inputs))
    embeddings = outputs[0]
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1
    embeddings = embeddings / norms
    return embeddings


async def fetch_post_by_identifier(repo: str, rkey: str) -> dict:
    """Return minimal post info (just enough to build a URI)."""
    uri = f"at://{repo}/app.bsky.feed.post/{rkey}"
    return {"uri": uri, "repo": repo, "rkey": rkey}


async def search_topics(query: str, limit: int = 2) -> list[dict]:
    """Use vector search to find relevant posts, returning minimal identifiers."""
    vector = encode_onnx(query).tolist()[0][0]
    body = json.dumps(vector)

    async with httpx.AsyncClient(timeout=30.0) as client:
        r_vector = await client.post(
            f"{CUSTOM_API_URL}/vector/search/posts",
            content=body,
            headers={"Content-Type": "application/json"}
        )

    if r_vector.status_code != 200:
        print("Vector search failed:", r_vector.text)
        return []

    results = []
    for post in r_vector.json()[:limit]:
        repo = post.get("repo")
        rkey = post.get("rkey")
        if repo and rkey:
            results.append(await fetch_post_by_identifier(repo, rkey))

    return results


def make_handler(feed_uri: str):
    client = Client()

    async def handler(cursor=None, limit=20):
        # Get sources for this feed
        sources = (
            FeedSource
            .select()
            .join(Feed)
            .where(Feed.uri == feed_uri)
        )

        posts = []

        for src in sources:
            if src.source_type == "account":
                account_posts = await client.get_posts_by_account(src.identifier, limit=limit)
                posts.extend([{"uri": p.uri, "repo": p.repo, "rkey": p.rkey} for p in account_posts])
            elif src.source_type == "topic":
                topic_posts = await search_topics(src.identifier, limit=limit)
                posts.extend(topic_posts)

        # Sort by timestamp if available, otherwise leave as is
        posts = posts[:limit]

        return {"cursor": None, "feed": posts}

    return handler
