#!/usr/bin/env python3
"""
RSS to Discord - Veille cyber/tech automatisee
Lit les flux RSS configures et poste les nouveaux articles sur Discord via webhook.
"""

import json
import os
import sys
import time
import re
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

import feedparser
import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
STATE_FILE = os.path.join(SCRIPT_DIR, "state.json")

# Rate limit Discord: max 30 messages/min, on reste safe
DISCORD_DELAY = 2  # secondes entre chaque message


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"posted": [], "first_run_done": False}


def save_state(state, max_entries):
    state["posted"] = state["posted"][-max_entries:]
    # Timestamp a chaque run -> garantit un commit git = keepalive repo (bypass 60 jours)
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def get_entry_id(entry):
    """Genere un identifiant unique pour un article RSS."""
    return entry.get("id", entry.get("link", entry.get("title", "")))


def get_entry_date(entry):
    """Extrait la date de publication d'un article."""
    for date_field in ("published", "updated", "created"):
        raw = entry.get(date_field)
        if raw:
            try:
                return parsedate_to_datetime(raw)
            except (ValueError, TypeError):
                pass
    # Fallback: date de parsing feedparser
    for parsed_field in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed = entry.get(parsed_field)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc)
            except (ValueError, TypeError):
                pass
    return None


def strip_html(text):
    """Retire les balises HTML et nettoie le texte pour Discord."""
    # Convertit <li> en tirets pour garder la lisibilite
    text = re.sub(r"<li[^>]*>", "- ", text)
    text = re.sub(r"</li>", "\n", text)
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    # Nettoie les lignes vides multiples
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build_embed(entry, feed_config, max_desc_len):
    """Construit un embed Discord a partir d'un article RSS."""
    title = entry.get("title", "Sans titre")
    link = entry.get("link", "")
    summary = entry.get("summary", entry.get("description", ""))

    # Nettoie et tronque la description
    description = strip_html(summary)
    if len(description) > max_desc_len:
        description = description[:max_desc_len].rsplit("\n", 1)[0] + "\n..."

    embed = {
        "title": f"{feed_config['emoji']} {title}"[:256],
        "url": link,
        "description": description,
        "color": feed_config["color"],
        "footer": {"text": f"\U0001f4e1 {feed_config['name']}"},
    }

    # Ajoute le timestamp si disponible
    pub_date = get_entry_date(entry)
    if pub_date:
        embed["timestamp"] = pub_date.isoformat()

    return embed


def post_to_discord(webhook_url, embed):
    """Envoie un embed sur Discord via webhook."""
    payload = {"embeds": [embed]}
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code == 429:
            # Rate limited, attendre et reessayer
            retry_after = resp.json().get("retry_after", 5)
            print(f"  Rate limited, attente {retry_after}s...")
            time.sleep(retry_after)
            resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"  Erreur Discord: {e}")
        return False


def process_feed(feed_config, state, webhook_url, config, dry_run=False):
    """Traite un flux RSS et poste les nouveaux articles."""
    feed_name = feed_config["name"]
    feed_url = feed_config["url"]
    print(f"\n[*] {feed_name} ({feed_url})")

    try:
        feed = feedparser.parse(feed_url)
    except Exception as e:
        print(f"  Erreur parsing: {e}")
        return 0

    if feed.bozo and not feed.entries:
        print(f"  Erreur feed: {feed.bozo_exception}")
        return 0

    now = datetime.now(timezone.utc)
    first_run_cutoff = now - timedelta(hours=config.get("first_run_hours", 24))
    is_first_run = not state.get("first_run_done", False)
    new_count = 0

    # Traite les entries en ordre chronologique (plus ancien d'abord)
    entries = list(reversed(feed.entries))

    for entry in entries:
        entry_id = get_entry_id(entry)

        # Deja poste ?
        if entry_id in state["posted"]:
            continue

        # Premier run : ne poste que les articles recents
        if is_first_run:
            pub_date = get_entry_date(entry)
            if pub_date and pub_date < first_run_cutoff:
                state["posted"].append(entry_id)
                continue

        # Construit l'embed
        embed = build_embed(entry, feed_config, config.get("max_description_length", 400))

        if dry_run:
            print(f"  [DRY RUN] {entry.get('title', 'Sans titre')}")
        else:
            print(f"  -> {entry.get('title', 'Sans titre')}")
            if post_to_discord(webhook_url, embed):
                time.sleep(DISCORD_DELAY)
            else:
                print(f"  Echec envoi, on reessaiera au prochain run")
                continue

        state["posted"].append(entry_id)
        new_count += 1

    print(f"  {new_count} nouveau(x) article(s)")
    return new_count


def main():
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("=" * 50)
        print("MODE DRY RUN - Aucun message ne sera envoye")
        print("=" * 50)

    # Webhook URL depuis variable d'environnement
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not webhook_url and not dry_run:
        print("Erreur: DISCORD_WEBHOOK_URL non definie")
        print("Utilise --dry-run pour tester sans webhook")
        sys.exit(1)

    config = load_config()
    state = load_state()
    total_new = 0

    for feed_config in config["feeds"]:
        new = process_feed(feed_config, state, webhook_url, config, dry_run)
        total_new += new

    state["first_run_done"] = True
    save_state(state, config.get("max_state_entries", 500))

    print(f"\n{'=' * 50}")
    print(f"Termine: {total_new} nouvel(aux) article(s) au total")
    print(f"State: {len(state['posted'])} entrees en memoire")


if __name__ == "__main__":
    main()
