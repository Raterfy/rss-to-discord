# RSS to Discord

Automated cyber/tech monitoring on Discord via GitHub Actions. Free, serverless, unlimited feeds.

## Configured feeds

| Source | Description |
|--------|-------------|
| [Bonjour la Fuite](https://bonjourlafuite.eu.org/) | Data leaks in France |
| [Korben](https://korben.info/) | French tech/cyber news |
| [The Hacker News](https://thehackernews.com/) | International cybersecurity |
| [EFF](https://www.eff.org/) | Digital rights |
| [MIT Tech Review - AI](https://www.technologyreview.com/) | Artificial intelligence |
| [BleepingComputer](https://www.bleepingcomputer.com/) | Malware, vulnerabilities, ransomware |
| [Next.ink](https://next.ink/) | French tech/digital law news |
| [Krebs on Security](https://krebsonsecurity.com/) | Cyber investigations |
| [Dark Reading](https://www.darkreading.com/) | Enterprise cybersecurity |
| [Schneier on Security](https://www.schneier.com/) | Crypto/security analysis |
| [Ars Technica Security](https://arstechnica.com/tag/security/) | In-depth security articles |
| [PortSwigger Research](https://portswigger.net/research) | Web security research (Burp Suite team) |
| [Intigriti Blog](https://blog.intigriti.com/) | Bug bounty writeups & news |
| [InfoSec Write-ups](https://infosecwriteups.com/) | Community security writeups |
| [Project Discovery](https://blog.projectdiscovery.io/) | Vulnerability research & tooling |
| [Watchtowr Labs](https://labs.watchtowr.com/) | Detailed 0-day writeups |
| [Google Project Zero](https://googleprojectzero.blogspot.com/) | Elite 0-day research |

## Setup

### 1. Create a Discord webhook

1. Open Discord, go to your server
2. Right-click on the target channel > **Edit Channel**
3. **Integrations** > **Webhooks** > **New Webhook**
4. Give it a name (e.g. `RSS Cyber Watch`)
5. **Copy the webhook URL**
6. Save

### 2. Create the GitHub repo

```bash
# Clone or fork this repo
git clone https://github.com/YOUR_USER/rss-to-discord.git
cd rss-to-discord

# Or from scratch
git init
git remote add origin https://github.com/YOUR_USER/rss-to-discord.git
git add .
git commit -m "init rss-to-discord"
git push -u origin master
```

> The repo can be **public** (unlimited Actions) or **private** (2000 free min/month, more than enough).

### 3. Add the webhook secret

1. On GitHub, go to your repo > **Settings** > **Secrets and variables** > **Actions**
2. Click **New repository secret**
3. Name: `DISCORD_WEBHOOK_URL`
4. Value: the Discord webhook URL copied in step 1
5. **Add secret**

### 4. Run the first check

1. Go to the **Actions** tab in your repo
2. Click on the **RSS to Discord** workflow
3. Click **Run workflow** > **Run workflow**
4. Check your Discord channel

After that, the cron runs **automatically every hour**, 24/7.

## AI Summaries (optional)

Feeds with `"summarize": true` in `config.json` get an AI-generated summary appended below the original article description. This is **completely optional** - the bot works perfectly fine without it.

Without Groq: articles are posted with their original description only.
With Groq: a short AI summary is added below the description for feeds that have `"summarize": true`.

### Setup Groq (free, 2 minutes)

1. Create a free account at **https://console.groq.com** (no credit card required)
2. Go to **API Keys** > **Create API Key**
3. Add it as a GitHub Secret: **Settings** > **Secrets** > **New repository secret**
   - Name: `GROQ_API_KEY`
   - Value: your `gsk_...` key
4. In `config.json`, add `"summarize": true` to feeds you want summarized

If you don't add a `GROQ_API_KEY` secret, the bot simply skips summaries and posts articles normally. No errors, no impact.

### Per-feed config

```json
{
  "name": "Watchtowr Labs",
  "url": "https://labs.watchtowr.com/rss/",
  "color": 15277667,
  "emoji": "\ud83c\udfaf",
  "summarize": true
}
```

The `"summarize"` field is optional. If omitted, it defaults to `false`.

Model used: **Llama 3.3 70B** via Groq (free tier: 14,400 requests/day).

## Configuration

Key settings in `config.json`:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `max_article_age_hours` | Only post articles newer than this | `24` |
| `max_state_entries` | Max article IDs to remember | `500` |
| `max_description_length` | Truncate descriptions at this length | `400` |

## Local testing

```bash
# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Dry run (no messages sent to Discord)
python rss_to_discord.py --dry-run

# Real test
DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..." python rss_to_discord.py
```

## Adding a feed

Edit `config.json` and add an entry:

```json
{
  "name": "Feed name",
  "url": "https://example.com/feed.xml",
  "color": 3447003,
  "emoji": "\ud83d\udcf0"
}
```

Colors are in decimal ([converter](https://www.mathsisfun.com/hexadecimal-decimal-colors.html)):

| Color | Decimal | Hex |
|-------|---------|-----|
| Red | `15158332` | `#e74c3c` |
| Blue | `3447003` | `#3498db` |
| Green | `3066993` | `#2ecc71` |
| Purple | `10181046` | `#9b59b6` |
| Orange | `15105570` | `#e67e22` |

## Project structure

```
rss-to-discord/
├── .github/workflows/rss-check.yml   # GitHub Actions cron (every hour)
├── config.json                        # RSS feeds list + settings
├── rss_to_discord.py                  # Main script
├── requirements.txt                   # Python dependencies
├── state.json                         # Auto-generated (posted articles history)
└── README.md
```

## FAQ

**Does the bot stop after 60 days of inactivity?**
No. The script writes a `last_run` timestamp to `state.json` on every execution, which generates an automatic commit and keeps the repo active.

**Does it cost anything?**
No. GitHub Actions is free for public repos (unlimited) and private repos (2000 min/month, this bot uses ~720).

**Can an article be posted twice?**
No. The script stores the IDs of already posted articles in `state.json`.

**Are old articles posted?**
No. Only articles from the last 24 hours are posted (`max_article_age_hours` in config).

**Discord rate limit?**
The script waits 2 seconds between each message and handles the 429 (rate limit) response automatically.
