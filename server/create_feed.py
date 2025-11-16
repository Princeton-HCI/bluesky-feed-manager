from atproto import Client, models
from server.models import Feed, FeedSource
from server.algos import algos
from server.algos.feed import make_handler
import os

def create_feed(handle, password, hostname, record_name, display_name='', description='',
                avatar_path=os.path.join(os.path.dirname(__file__), "avatar.png"),
                blueprint=None):
    client = Client()
    client.login(handle, password)

    feed_did = f'did:web:{hostname}'

    avatar_blob = None
    if avatar_path and os.path.exists(avatar_path):
        with open(avatar_path, 'rb') as f:
            avatar_blob = client.upload_blob(f.read()).blob

    # Create or update record on Bluesky
    response = client.com.atproto.repo.put_record(
        models.ComAtprotoRepoPutRecord.Data(
            repo=client.me.did,
            collection=models.ids.AppBskyFeedGenerator,
            rkey=record_name,
            record=models.AppBskyFeedGenerator.Record(
                did=feed_did,
                display_name=display_name,
                description=description,
                avatar=avatar_blob,
                accepts_interactions=False,
                content_mode=None,
                created_at=client.get_current_time_iso(),
            )
        )
    )

    feed_uri = response.uri

    # Save feed metadata locally
    data = {
        "handle": handle,
        "record_name": record_name,
        "display_name": display_name,
        "description": description,
        "avatar_path": avatar_path,
    }

    feed, created = Feed.get_or_create(
        uri=feed_uri,
        defaults=data
    )

    if not created:
        updated = False
        for field in ["handle", "record_name", "display_name", "description", "avatar_path"]:
            value = data.get(field)
            if value and getattr(feed, field) != value:
                setattr(feed, field, value)
                updated = True
        if updated:
            feed.save()

    # Feed blueprint processing
    if blueprint:
        # Delete old sources for this feed
        FeedSource.delete().where(FeedSource.feed == feed).execute()

        # Preferences (positive)
        for topic in blueprint.get('topics', []):
            FeedSource.create(
                feed=feed,
                source_type='topic_preference',
                identifier=topic['name']
            )
        for account_did in blueprint.get('suggested_accounts', []):
            FeedSource.create(
                feed=feed,
                source_type='account_preference',
                identifier=account_did
            )

        # Filters (negative)
        filters = blueprint.get("filters", {})

        for keyword in filters.get("limit_posts_about", []):
            FeedSource.create(
                feed=feed,
                source_type='topic_filter',
                identifier=keyword
            )
        for blocked_did in filters.get("limit_posts_from", []):
            FeedSource.create(
                feed=feed,
                source_type='account_filter',
                identifier=blocked_did
            )

    # Dynamically add handler to algos
    algos[feed_uri] = make_handler(feed_uri)

    # Warm the cache of dynamically collected posts immediately
    try:
        handler = algos[feed_uri]
        import asyncio

        # Trigger handler in the background
        asyncio.get_event_loop().create_task(handler())
        print(f"[Cache Warm] Started background warm for {feed_uri}")

    except Exception as e:
        print(f"[Cache Warm Error] Could not warm cache for {feed_uri}: {e}")

    return feed_uri
