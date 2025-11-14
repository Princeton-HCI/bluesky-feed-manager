from datetime import datetime
from typing import Optional
from server.database import Post

CURSOR_EOF = 'eof'

def make_handler(feed_uri: str):
    """Return a handler function bound to a specific feed URI."""
    def handler(cursor: Optional[str], limit: int) -> dict:
        posts = Post.select().where(Post.feed_uri == feed_uri)\
                    .order_by(Post.cid.desc())\
                    .order_by(Post.indexed_at.desc())\
                    .limit(limit)

        if cursor:
            if cursor == CURSOR_EOF:
                return {'cursor': CURSOR_EOF, 'feed': []}

            indexed_at, cid = cursor.split('::')
            indexed_at = datetime.fromtimestamp(int(indexed_at)/1000)
            posts = posts.where(
                ((Post.indexed_at == indexed_at) & (Post.cid < cid)) | (Post.indexed_at < indexed_at)
            )

        feed = [{'post': post.uri} for post in posts]

        cursor_val = CURSOR_EOF
        last_post = posts[-1] if posts else None
        if last_post:
            cursor_val = f'{int(last_post.indexed_at.timestamp() * 1000)}::{last_post.cid}'

        return {'cursor': cursor_val, 'feed': feed}

    return handler
