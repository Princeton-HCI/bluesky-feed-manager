import os
import json
import httpx
import numpy as np
import onnxruntime as ort
from transformers import AutoTokenizer
import asyncio
import time
from server.models import Feed, FeedSource, FeedCache

CACHE_TTL = 60  # seconds

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


async def fetch_author_posts(actor_did: str, limit: int = 20) -> list[dict]:
    """Fetch posts from a Bluesky author DID."""
    url = (
        "https://public.api.bsky.app/xrpc/"
        "app.bsky.feed.getAuthorFeed"
        f"?actor={actor_did}&limit={limit}"
    )
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url)

    if r.status_code != 200:
        print("Author fetch failed:", r.text)
        return []

    items = r.json().get("feed", [])
    results = []

    for item in items:
        post = item.get("post")
        if not post:
            continue
        uri = post.get("uri")
        if not uri:
            continue

        try:
            _, _, repo, _, rkey = uri.split("/", 4)
        except ValueError:
            continue

        results.append(await fetch_post_by_identifier(repo, rkey))

    return results


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
    # Hardcoded feed for testing
    HARDCODED_FEED = {
        "cursor": "1763164205598::bafyreiakbqx7jhzmhjhh463ugzpg7xtpsvwgplujbqkw65pctxelgtanqa",
        "feed": [
            {"post": "at://did:plc:wymilg6dl7apufaqxvj4nvnq/app.bsky.feed.post/3m5mjwtbku22a"},
            {"post": "at://did:plc:wymilg6dl7apufaqxvj4nvnq/app.bsky.feed.post/3m5mjvjys7c2a"},
            {"post": "at://did:plc:kqwgubh6vutpu3cli2gll6at/app.bsky.feed.post/3m5ml2t3d3s22"},
            {"post": "at://did:plc:3cj63bm5lp7vtshcmi64jcu6/app.bsky.feed.post/3m5mkn4mirc2m"},
            {"post": "at://did:plc:3cj63bm5lp7vtshcmi64jcu6/app.bsky.feed.post/3m5mklfrrfk2m"},
            {"post": "at://did:plc:3cj63bm5lp7vtshcmi64jcu6/app.bsky.feed.post/3m5mkgl7g722m"},
            {"post": "at://did:plc:3cj63bm5lp7vtshcmi64jcu6/app.bsky.feed.post/3m5mk5fzuac2m"},
            {"post": "at://did:plc:bnr7lud6lkmvebxcdumuw7hd/app.bsky.feed.post/3m5mhvuodkc2e"},
            {"post": "at://did:plc:7rtxsl6akfz3a62jqrqb5ryd/app.bsky.feed.post/3m5lu5tbe4k2u"},
            {"post": "at://did:plc:oe5k5kgdudinkw6jpzzfcw4q/app.bsky.feed.post/3m5mhdtvpak2u"},
            # … you can include all the rest from your JSON
        ]
    }

    async def handler(cursor=None, limit=20):
        # Always return the hardcoded feed (optionally slice to `limit`)
        feed = HARDCODED_FEED.copy()
        feed["feed"] = feed["feed"][:limit]
        return feed

    return handler
