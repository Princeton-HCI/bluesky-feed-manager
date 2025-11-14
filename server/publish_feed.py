from atproto import Client, models
from server.models import Feed
import os

def create_feed(handle, password, hostname, record_name, display_name='', description='', avatar_path=os.path.join(os.path.dirname(__file__), "avatar.png")):
    client = Client()
    client.login(handle, password)

    feed_did = f'did:web:{hostname}'

    avatar_blob = None
    if avatar_path and os.path.exists(avatar_path):
        with open(avatar_path, 'rb') as f:
            avatar_blob = client.upload_blob(f.read()).blob

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

    # Save feed to DB, update if it already exists
    feed, created = Feed.get_or_create(
        uri=feed_uri,
        defaults={
            'display_name': display_name,
            'description': description,
            'avatar_path': avatar_path
        }
    )

    if not created:
        feed.display_name = display_name
        feed.description = description
        feed.avatar_path = avatar_path
        feed.save()

    # Dynamically add handler to algos
    from server.algos import algos
    from server.algos.feed import make_handler
    algos[feed_uri] = make_handler(feed_uri)

    return feed_uri