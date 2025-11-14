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
    async def build_feed(limit=20):
        """Build fresh feed skeleton by fetching sources + posts."""
        sources = (
            FeedSource
            .select()
            .join(Feed)
            .where(Feed.uri == feed_uri)
        )

        posts = []

        for src in sources:
            if src.source_type == "account":
                posts.extend(await fetch_author_posts(src.identifier, limit))
            elif src.source_type == "topic":
                posts.extend(await search_topics(src.identifier, limit=limit))

        # Format for Bluesky
        feed = {"cursor": None,
                "feed": [{"post": p["uri"]} for p in posts[:limit]]}

        # Save to SQLite
        FeedCache.insert(
            feed_uri=feed_uri,
            response_json=json.dumps(feed),
            timestamp=int(time.time())
        ).on_conflict_replace().execute()

        return feed

    async def serve_from_cache(limit=20):
        """Return cached feed if recent, otherwise None."""
        row = FeedCache.get_or_none(FeedCache.feed_uri == feed_uri)
        if row is None:
            return None

        age = time.time() - row.timestamp
        if age < CACHE_TTL:
            return json.loads(row.response_json)

        return json.loads(row.response_json)  # stale but still valid

    async def background_refresh(limit=20):
        """Refresh cache in the background (non-blocking)."""
        try:
            await build_feed(limit)
        except Exception as e:
            print("Background refresh failed:", e)

    async def handler(cursor=None, limit=20):
        # 1. Try cached version first
        cached = await serve_from_cache(limit)

        if cached:
            # 2. If cached but stale then refresh in background
            row = FeedCache.get_or_none(FeedCache.feed_uri == feed_uri)
            if time.time() - row.timestamp >= CACHE_TTL:
                asyncio.create_task(background_refresh(limit))
            return cached

        # 3. If there's no cache build immediately
        fresh = await build_feed(limit)
        return fresh

    return handler