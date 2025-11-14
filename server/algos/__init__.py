from .feed import make_handler
from server.models import db, Feed, FeedSource, FeedCache

# Dictionary mapping feed URI to handler
algos = {}

# Connect to the database at startup
db.connect(reuse_if_open=True)

# Ensure tables exist
db.create_tables([Feed, FeedSource, FeedCache], safe=True)

# Load all persisted feeds into algos
for feed in Feed.select():
    algos[feed.uri] = make_handler(feed.uri)

# Do NOT close the DB here — leave it open for the lifetime of the server
