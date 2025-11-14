from peewee import Model, SqliteDatabase, TextField

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

# create the table if it doesn't exist
db.connect()
db.create_tables([Feed], safe=True)
