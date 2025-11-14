import sys
import signal
import threading
import logging

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from server import config, data_stream
from server.algos import algos
from server.algos.feed import make_handler
from server.data_filter import operations_callback
from server.publish_feed import create_feed
from server.models import Feed


# App setup
app = FastAPI()
logging.basicConfig(level=logging.INFO)

stream_stop_event = threading.Event()
stream_thread = threading.Thread(
    target=data_stream.run,
    args=(config.SERVICE_DID, operations_callback, stream_stop_event),
)

def sigint_handler(*_):
    logging.info("SIGINT received, stopping...")
    stream_stop_event.set()
    sys.exit(0)

signal.signal(signal.SIGINT, sigint_handler)


@app.on_event("startup")
async def start_stream():
    stream_thread.start()
    logging.info("Data stream started.")

@app.on_event("shutdown")
async def stop_stream():
    logging.info("Stopping data stream...")
    stream_stop_event.set()
    stream_thread.join()
    logging.info("Data stream stopped.")

# Routes
@app.get("/")
async def index():
    return "ATProto Feed Generator powered by The AT Protocol SDK for Python (https://github.com/MarshalX/atproto)."

@app.get("/.well-known/did.json")
async def did_json():
    if not config.SERVICE_DID.endswith(config.HOSTNAME):
        raise HTTPException(status_code=404)
    return {
        "@context": ["https://www.w3.org/ns/did/v1"],
        "id": config.SERVICE_DID,
        "service": [
            {
                "id": "#bsky_fg",
                "type": "BskyFeedGenerator",
                "serviceEndpoint": f"https://{config.HOSTNAME}"
            }
        ]
    }

@app.get("/xrpc/app.bsky.feed.describeFeedGenerator")
async def describe_feed_generator():
    feeds = [{"uri": uri} for uri in algos.keys()]
    return {
        "encoding": "application/json",
        "body": {
            "did": config.SERVICE_DID,
            "feeds": feeds
        }
    }

@app.get("/xrpc/app.bsky.feed.getFeedSkeleton")
async def get_feed_skeleton(feed: str, cursor: str = None, limit: int = 20):
    algo = algos.get(feed)
    if not algo:
        raise HTTPException(status_code=400, detail="Unsupported algorithm")
    
    try:
        body = await algo(cursor, limit)
    except ValueError:
        raise HTTPException(status_code=400, detail="Malformed cursor")
    
    return body

@app.post("/manage-feed")
async def create_feed_endpoint(data: dict):
    try:
        # Create feed via ATProto API
        uri = create_feed(**data)

        # Dynamically add handler for this new feed
        algos[uri] = make_handler(uri)
        logging.info("Feed and handler added for URI: %s", uri)

    except Exception as e:
        logging.error("Error in /manage-feed: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))

    return {"uri": uri}
