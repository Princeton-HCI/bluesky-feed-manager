# Bluesky Feed Generator Deployment Guide (bluesky-feed-manager)

This guide walks through deploying your ATProto feed generator on a VM with NGINX and SSL, using Python, SQLite, and Waitress.

---

## 1. VM & Network Setup

To run your Bluesky Feed Manager, you’ll need a small Linux VM with a static external IP, DNS pointing to it, and firewall rules allowing web traffic. Below is a recommended setup based on a working configuration deployed on Google Cloud Platform (GCP), though the same approach works on AWS, Azure, DigitalOcean, etc.

---

### 1.1 Create a VM Instance

Choose any cloud provider and create a lightweight virtual machine.

**Recommended VM configuration (example using GCP):**

| Setting                           | Recommended Value                                                     |
| --------------------------------- | --------------------------------------------------------------------- |
| **Name**                          | `bluesky-feed-manager`                                                |
| **Region / Zone**                 | e.g., `us-central1-f`                                                 |
| **Machine Type**                  | `e2-micro` (2 vCPUs, 1 GB RAM) — works well and is free-tier eligible |
| **Boot Disk**                     | Ubuntu **22.04** LTS or Ubuntu **24.04** LTS                          |
| **Disk Size**                     | ~10 GB                                                                |
| **External IP**                   | Static or Ephemeral (Static preferred)                                |
| **Firewall (during VM creation)** | ✔ Allow HTTP, ✔ Allow HTTPS                                           |

This kind of configuration is sufficient for running a Feed Generator service in production.

Once created, your VM will receive:

- An **internal IP** (e.g., `10.128.0.3`)
- An **external IPv4** (e.g., `203.0.113.45`)

You will use the external IP when configuring DNS.

---

### 1.2 Reserve or Assign an External IP

If possible, reserve a **static** external IP so your feed hostname does not change.

Example (placeholder):

```
External IP (static): 203.0.113.45
```

Attach this IP to the VM’s primary network interface.

---

### 1.3 Configure DNS for Your Feed Subdomain

In your DNS provider (e.g., GoDaddy, Cloudflare, Namecheap), create an **A record** that points your feed domain to your VM’s external IP.

Example DNS records (safe placeholder values):

| Type | Name    | Data (IP)        | Meaning                               |
| ---- | ------- | ---------------- | ------------------------------------- |
| A    | `feeds` | **203.0.113.45** | `feeds.example.com` → Feed Manager VM |

For example:

```
feeds.example.com → 203.0.113.45
```

This domain will later be used as your `HOSTNAME` and for your SSL certificate.

---

### 1.4 Create Firewall Rules (Provider Example: GCP)

Your VM must receive inbound traffic on these ports:

| Purpose                    | Port |
| -------------------------- | ---- |
| HTTP (NGINX)               | 80   |
| HTTPS (NGINX + Certbot)    | 443  |
| App Server / API (Uvicorn) | 8000 |

Create an ingress firewall rule:

```
Name: allow-web
Direction: Ingress
Source IP Range: 0.0.0.0/0
Allowed Protocols: tcp:80, tcp:443, tcp:8000
Target: All instances (or apply a network tag)
```

If your cloud provider automatically adds `allow-http` and `allow-https`, you only need to add `tcp:8000`.

---

## 2. Install Dependencies

SSH into your VM and run:

```bash
sudo apt update
sudo apt install nginx certbot python3-certbot-nginx -y
sudo pip3 install --upgrade --force-reinstall --ignore-installed \
    python-dotenv \
    atproto \
    peewee \
    typing-extensions \
    numpy \
    onnxruntime \
    transformers \
    fastapi \
    uvicorn \
    --break-system-packages
```

---

## 3. Pull Down the GitHub Repository

Clone this repo into the VM and enter the project directory:

```bash
git clone https://github.com/Princeton-HCI/bluesky-feed-manager.git
cd bluesky-feed-manager
```

---

## 4. Configure Environment Variables

1. Copy the example environment file:

```bash
cp .env.example .env
nano .env
```

2. Set the required variables. Common ones include:

- `HOSTNAME` - Replace `'feed.example.com'` with the actual subdomain you pointed to your VM (e.g., `feeds.princetonhci.social`).
- `CUSTOM_API_URL` - Keep as-is if you're using your existing PDS; otherwise change to the URL of your own API instance.
- `API_KEY` - A secure key you define. Clients must include this key in requests to access the APIs provided by this service.
- Any optional variables your project requires

Save and exit when done.

---

## 5. Run the Server

First, make the server script executable:

```bash
chmod +x run_server.sh
```

Then start the Bluesky Feed Manager service:

```bash
./run_server.sh start
```

To check whether it's running:

```bash
./run_server.sh status
```

To stop it:

```bash
./run_server.sh stop
```

### **Optional: Run in the foreground to view logs directly**

If you prefer to run the server without backgrounding it (useful for debugging and watching logs live), run Uvicorn manually:

```bash
uvicorn server.app:app --host 0.0.0.0 --port 8000 --reload
```

---

## 6. Configure NGINX & SSL

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

Below is a clean, rewritten **Step 7** that replaces your original Step 11.
It focuses on **trying the service**, **deploying a new custom feed**, and includes the **updated request body shape**.

---

Here is the updated Step 7 with clear instructions about the required **API key header**, written cleanly so you can drop it directly into your README.

---

## 7. Test the Service: Deploy a New Custom Feed (Dynamic Feed Creation)

Once your server is running and NGINX/SSL is configured, you can **create new custom feeds dynamically**—without editing code or restarting the service. This step verifies that your deployment works end-to-end.

---

### Endpoint

```
POST /create_feed
Content-Type: application/json
x-api-key: <your API key>
```

> Important:
> All requests to this endpoint must include your API key in the `x-api-key` header.
> This key is the same one you configured in your `.env` file under `API_KEY`.

Your Feed Manager will automatically:

1. Authenticate with the ATProto account you provide
2. Publish a new feed generator record
3. Transiently store the feed in SQLite
4. Register it dynamically so it’s instantly live
5. Serve the feed immediately from your hostname (e.g., `https://feeds.example.com`)

---

### Example Request Body

Here is an example of the JSON body you would POST to this service:

```json
{
  "handle": "<your bluesky handle>",
  "password": "<the app password for the said handle>",
  "hostname": "feeds.example.com",
  "record_name": "adorable-pets-feed",
  "display_name": "Adorable Pets",
  "description": "A feed featuring cute and adorable pictures of pets without any bad language or vulgarity.",
  "blueprint": {
    "topics": [
      { "name": "pets", "priority": 1 },
      { "name": "dogs", "priority": 0.9 },
      { "name": "cats", "priority": 0.9 },
      { "name": "puppies", "priority": 0.8 },
      { "name": "kittens", "priority": 0.8 }
    ],
    "filters": {
      "limit_posts_about": [
        "bad language",
        "vulgarity",
        "profanity",
        "offensive content"
      ]
    },
    "ranking_weights": {
      "focused": 0.8,
      "fresh": 0.7,
      "balanced": 0.6,
      "trending": 0.5
    },
    "suggested_accounts": [
      "did:plc:t4q27bc5gswob4zskgcqi4b6",
      "did:plc:pk5nq3gedpdb6xedfeobsm52",
      "did:plc:f4d76fjna5nxqsy2fu6cgmp3",
      "did:plc:gyjeilekf6276652rhhvjs5c",
      "did:plc:xrr5j2okn7ew2zvcwsxus3gb",
      "did:plc:2ho7jhe6opdnsptcxjmrwca2",
      "did:plc:hh7jwr3vgpojfulwekw36zms",
      "did:plc:kptddmrndbfzof3yzmhdg3fq",
      "did:plc:fvzkql2aqtbk7qmqjkoo2lv2"
    ]
  },
  "timestamp": 1763270109926
}
```

---

### Example cURL Command (with API key)

```bash
curl -X POST https://feeds.example.com/create_feed \
  -H "Content-Type: application/json" \
  -H "x-api-key: <your api key>" \
  -d '{
    "handle": "<your bluesky handle>",
    "password": "<the app password for the said handle>",
    "hostname": "feeds.example.com",
    "record_name": "adorable-pets-feed",
    "display_name": "Adorable Pets",
    "description": "A feed featuring cute and adorable pictures of pets without any bad language or vulgarity.",
    "blueprint": {
      "topics": [
        { "name": "pets", "priority": 1 },
        { "name": "dogs", "priority": 0.9 },
        { "name": "cats", "priority": 0.9 },
        { "name": "puppies", "priority": 0.8 },
        { "name": "kittens", "priority": 0.8 }
      ],
      "filters": {
        "limit_posts_about": [
          "bad language",
          "vulgarity",
          "profanity",
          "offensive content"
        ]
      },
      "ranking_weights": {
        "focused": 0.8,
        "fresh": 0.7,
        "balanced": 0.6,
        "trending": 0.5
      },
      "suggested_accounts": [
        "did:plc:t4q27bc5gswob4zskgcqi4b6",
        "did:plc:pk5nq3gedpdb6xedfeobsm52",
        "did:plc:f4d76fjna5nxqsy2fu6cgmp3",
        "did:plc:gyjeilekf6276652rhhvjs5c",
        "did:plc:xrr5j2okn7ew2zvcwsxus3gb",
        "did:plc:2ho7jhe6opdnsptcxjmrwca2",
        "did:plc:hh7jwr3vgpojfulwekw36zms",
        "did:plc:kptddmrndbfzof3yzmhdg3fq",
        "did:plc:fvzkql2aqtbk7qmqjkoo2lv2"
      ]
    },
    "timestamp": 1763270109926
  }'
```

---

### Example Response

If successful, the server returns the feed URI:

```json
{
  "uri": "at://did:web:feeds.example.com/app.bsky.feed.generator/adorable-pets-feed"
}
```

You can now:

- Add this feed to Bluesky as a custom algorithm
- Share the feed URL publicly
- Immediately begin seeing ranked posts generated from your blueprint

---
