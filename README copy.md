# Bluesky Feed Generator Deployment Guide (bluesky-feed-manager)

This guide walks through deploying your ATProto feed generator on a VM with NGINX and SSL, using Python, SQLite, and Waitress.

---

## 1. VM & Network Setup

1. **Create VM**
2. **Assign a new external IP**
3. **Point your feeds subdomain** to the VM’s external IP

Example: `feeds.princetonhci.social → <external IP>`

---

## 2. Install Dependencies

SSH into your VM and run:

```bash
sudo apt update
sudo pip install --upgrade --force-reinstall --ignore-installed \
    python-dotenv atproto peewee Flask typing-extensions --break-system-packages
```

---

## 3. Configure Environment

1. Copy `.env` example:

```bash
cp .env.example .env
nano .env
```

2. Configure key variables:

- `FEED_URI` – Set after first publish if using `did:web`.
- Display info: `FEED_NAME`, `FEED_DESCRIPTION`, `FEED_AVATAR`.
- Any other credentials, database settings, or API keys.

---

## 4. Implement Filtering & Feed Logic

- Edit `server/data_filter.py` to define which posts to include/exclude.
- Optionally, add custom feed algorithms in `server/algos/`.

Example:

```python
# server/data_filter.py
def filter_post(post):
    return post.author in ALLOWED_AUTHORS
```

---

## 5. Publish Your Feed

```bash
python publish_feed.py
```

- The script creates the feed in ATProto, uploads the avatar if provided, and stores it in SQLite.
- The feed is immediately available to the server and dynamically registered in `algos`.
- Example verification:

```text
http://feeds.princetonhci.social:8000/xrpc/app.bsky.feed.describeFeedGenerator
http://feeds.princetonhci.social:8000/xrpc/app.bsky.feed.getFeedSkeleton?feed=<feed_uri>
```

---

## 6. Run the Server

1. **Development server:**

```bash
flask --debug run
```

2. **Production server with Waitress:**

```bash
waitress-serve --listen=0.0.0.0:8000 server.app:app
```

- Optional: create a helper shell script (`run_waitress.sh`) for start/stop/status management (see your script above).

---

## 7. Configure NGINX & SSL

1. Install NGINX and Certbot:

```bash
sudo apt install nginx certbot python3-certbot-nginx -y
```

2. Create NGINX site configuration:

```bash
sudo nano /etc/nginx/sites-available/feedgen
```

Paste:

```nginx
server {
    listen 80;
    server_name feeds.princetonhci.social;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

3. Enable site and test:

```bash
sudo ln -s /etc/nginx/sites-available/feedgen /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

4. Obtain SSL certificate:

```bash
sudo certbot --nginx -d feeds.princetonhci.social
```

- After successful setup, SSL certificates are located in:

```
/etc/letsencrypt/live/feeds.princetonhci.social/fullchain.pem
/etc/letsencrypt/live/feeds.princetonhci.social/privkey.pem
```

---

## 8. Verify Feeds

- List all registered feeds:

```text
http://feeds.princetonhci.social/xrpc/app.bsky.feed.describeFeedGenerator
```

- Retrieve feed skeleton (paginated):

```text
http://feeds.princetonhci.social/xrpc/app.bsky.feed.getFeedSkeleton?feed=<feed_uri>&limit=20
```

---

## 9. Dynamic Updates

- **New feeds** can be created without restarting the server.
- **Existing feeds** can be updated by re-running `publish_feed.py` with new display info or avatar.
- Handlers are dynamically added to `algos` using `make_handler(feed_uri)`.

---

## 10. Optional: Automated Waitress Script

- `run_waitress.sh` allows easy start/stop/status management:

```bash
./run_waitress.sh start
./run_waitress.sh stop
./run_waitress.sh status
```

---

## 11. Dynamic Feed Creation via API

You can now **create feeds dynamically** without touching the server code or restarting it.

### Endpoint

```
POST /create_feed
Content-Type: application/json
```

### Request JSON Example

```json
{
  "handle": "princetonhci.social",
  "password": "<example password>",
  "hostname": "feeds.princetonhci.social",
  "record_name": "demo-custom-feed",
  "display_name": "Demo Custom Feed",
  "description": "An example of a custom feed"
}
```

- `handle` / `password` — login credentials for the ATProto account that will own the feed.
- `hostname` — the domain for your feed (`did:web` format).
- `record_name` — unique key for this feed record.
- `display_name` / `description` / `avatar_path` — optional metadata for the feed.

### Response Example

```json
{
  "uri": "at://did:web:feeds.princetonhci.social/app.bsky.feed.generator/feeds-test3"
}
```

- The feed URI is returned and automatically added to your **`algos` registry**, making it immediately available via the server.

### How It Works

1. `create_feed_endpoint()` receives the POST request.
2. Calls `create_feed(**data)` to interact with the ATProto API.
3. Saves the feed record in **SQLite** via `Feed.create()`.
4. Dynamically adds the handler for this feed using `make_handler(uri)`.
5. No server restart is required — the new feed is live immediately.

### Example cURL

```bash
curl -X POST https://feeds.princetonhci.social/create_feed \
  -H "Content-Type: application/json" \
  -d '{
        "handle": "princetonhci.social",
        "password": "<example password>",
        "hostname": "feeds.princetonhci.social",
        "record_name": "demo-custom-feed",
        "display_name": "Demo Custom Feed",
        "description": "An example of a custom feed"
      }'
```
