from .feed import make_handler
from server.models import Feed

# Dictionary mapping feed URI to handler
algos = {}

# Load all persisted feeds from the database at startup
for feed in Feed.select():
    algos[feed.uri] = make_handler(feed.uri)
