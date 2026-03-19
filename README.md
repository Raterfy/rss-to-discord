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
| [CERT-FR Alertes](https://www.cert.ssi.gouv.fr/) | ANSSI critical alerts (France) |
| [Next.ink](https://next.ink/) | French tech/digital law news |
| [Krebs on Security](https://krebsonsecurity.com/) | Cyber investigations |
| [Dark Reading](https://www.darkreading.com/) | Enterprise cybersecurity |
| [Schneier on Security](https://www.schneier.com/) | Crypto/security analysis |
| [Ars Technica Security](https://arstechnica.com/tag/security/) | In-depth security articles |

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
