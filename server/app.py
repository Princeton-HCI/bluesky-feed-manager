import sys
import signal
import threading
import logging

from server import config
from server import data_stream

from flask import Flask, jsonify, request
import threading, sys, signal

from server import config, data_stream
from server.algos import algos
from server.algos.feed import make_handler
from server.data_filter import operations_callback
from server.publish_feed import create_feed
from server.models import Feed


app = Flask(__name__)

stream_stop_event = threading.Event()
stream_thread = threading.Thread(
    target=data_stream.run, args=(config.SERVICE_DID, operations_callback, stream_stop_event,)
)
stream_thread.start()


def sigint_handler(*_):
    print('Stopping data stream...')
    stream_stop_event.set()
    sys.exit(0)


signal.signal(signal.SIGINT, sigint_handler)

logging.basicConfig(level=logging.INFO)


@app.route('/')
def index():
    return 'ATProto Feed Generator powered by The AT Protocol SDK for Python (https://github.com/MarshalX/atproto).'


@app.route('/.well-known/did.json', methods=['GET'])
def did_json():
    if not config.SERVICE_DID.endswith(config.HOSTNAME):
        return '', 404

    return jsonify({
        '@context': ['https://www.w3.org/ns/did/v1'],
        'id': config.SERVICE_DID,
        'service': [
            {
                'id': '#bsky_fg',
                'type': 'BskyFeedGenerator',
                'serviceEndpoint': f'https://{config.HOSTNAME}'
            }
        ]
    })


@app.route('/xrpc/app.bsky.feed.describeFeedGenerator', methods=['GET'])
def describe_feed_generator():
    feeds = [{'uri': uri} for uri in algos.keys()]
    response = {
        'encoding': 'application/json',
        'body': {
            'did': config.SERVICE_DID,
            'feeds': feeds
        }
    }
    return jsonify(response)


@app.route('/xrpc/app.bsky.feed.getFeedSkeleton', methods=['GET'])
def get_feed_skeleton():
    feed = request.args.get('feed', default=None, type=str)
    algo = algos.get(feed)
    if not algo:
        return 'Unsupported algorithm', 400

    # Example of how to check auth if giving user-specific results:
    """
    from server.auth import AuthorizationError, validate_auth
    try:
        requester_did = validate_auth(request)
    except AuthorizationError:
        return 'Unauthorized', 401
    """

    try:
        cursor = request.args.get('cursor', default=None, type=str)
        limit = request.args.get('limit', default=20, type=int)
        body = algo(cursor, limit)
    except ValueError:
        return 'Malformed cursor', 400

    return jsonify(body)

@app.route('/create_feed', methods=['POST'])
def create_feed_endpoint():
    data = request.json
    logging.info("Received /create_feed POST with data: %s", data)  # <-- log the incoming JSON

    try:
        # Create feed via ATProto API
        uri = create_feed(**data)
        logging.info("Feed created with URI: %s", uri)

        # Save new feed to database
        print(data)
        feed, created = Feed.get_or_create(
            uri=uri,
            defaults={
                "handle": data["handle"],
                "record_name": data["record_name"],
                "display_name": data.get("display_name", ""),
                "description": data.get("description"),
                "avatar_path": data.get("avatar_path")
            }
        )

        if not created:
            # Update missing fields
            updated = False
            for field in ["handle", "record_name", "display_name", "description", "avatar_path"]:
                value = data.get(field)
                if value and getattr(feed, field) != value:
                    setattr(feed, field, value)
                    updated = True
            if updated:
                feed.save()

        logging.info("Feed saved to DB: %s (created: %s)", feed.__data__, created)

        # Dynamically add handler for this new feed
        algos[uri] = make_handler(uri)
        logging.info("Handler added for URI: %s", uri)

    except Exception as e:
        logging.error("Error in /create_feed: %s", e, exc_info=True)
        return str(e), 400

    return jsonify({"uri": uri})