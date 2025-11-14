from peewee import Model, SqliteDatabase, TextField, ForeignKeyField, IntegerField

db = SqliteDatabase('feeds.db')

class Feed(Model):
    uri = TextField(unique=True)
    handle = TextField()
    record_name = TextField()
    display_name = TextField()
    description = TextField(null=True)
    avatar_path = TextField(null=True)

    class Meta:
        database = db


class FeedSource(Model):
    feed = ForeignKeyField(Feed, backref='sources', on_delete='CASCADE')
    source_type = TextField()   # 'account' or 'topic'
    identifier = TextField()    # e.g., 'did:web:example.com' or 'sports'

    class Meta:
        database = db
        indexes = (
            (('feed', 'source_type', 'identifier'), True),
        )

class FeedCache(Model):
    feed_uri = TextField(unique=True)
    response_json = TextField()  # JSON string of {"cursor":..., "feed":[...]}
    timestamp = IntegerField()   # UNIX timestamp

    class Meta:
        database = db