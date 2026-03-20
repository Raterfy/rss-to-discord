#!/usr/bin/env python3
"""
RSS to Discord - Veille cyber/tech automatisee
Lit les flux RSS configures et poste les nouveaux articles sur Discord via webhook.
Supporte les resumes IA via Groq (gratuit).
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

# Groq API
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"posted": []}


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


def summarize_article(title, description, groq_api_key, lang=None):
    """Resume un article via l'API Groq (gratuit)."""
    if not groq_api_key:
        return None

    # Detecte la langue si non specifiee dans le config
    lang_map = {"fr": "french", "en": "english"}
    if lang and lang in lang_map:
        lang = lang_map[lang]
    elif not lang:
        text = f"{title}\n{description}"
        fr_words = {"les", "des", "une", "pour", "dans", "avec", "sur", "par",
                    "est", "sont", "qui", "que", "nom", "adresse", "prénom",
                    "données", "numéro", "téléphone", "fuite", "sécurité",
                    "vulnérabilité", "découverte", "attaque", "réseau"}
        words = set(text.lower().split())
        lang = "french" if len(words & fr_words) >= 2 else "english"

    prompt = (
        f"Write a concise summary (2-3 sentences) in {lang} for a cybersecurity Discord channel.\n\n"
        f"Be specific and technical: mention CVE numbers, software names, attack techniques, "
        f"and key facts when they appear in the content. "
        f"Cover the main points of the article clearly so readers understand what it's about. "
        f"Keep a professional tone.\n\n"
        f"Do not start with 'This article'.\n"
        f"Do not repeat the title.\n"
        f"Do not tease ('worth reading', 'dive deeper', 'explore').\n"
        f"Do not use casual language ('So,', 'Basically,').\n"
        f"Do not invent CVEs, stats, or facts not present in the content.\n\n"
        f"Title: {title}\n\n"
        f"Content: {description[:2000]}"
    )

    try:
        resp = requests.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {groq_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 200,
                "temperature": 0.3,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
        else:
            print(f"  Groq API erreur {resp.status_code}: {resp.text[:100]}")
            return None
    except requests.RequestException as e:
        print(f"  Groq API erreur: {e}")
        return None


def build_embed(entry, feed_config, max_desc_len, groq_api_key=None):
    """Construit un embed Discord a partir d'un article RSS."""
    title = entry.get("title", "Sans titre")
    link = entry.get("link", "")
    summary = entry.get("summary", entry.get("description", ""))

    # Nettoie la description
    clean_desc = strip_html(summary)

    # Resume IA si active pour ce feed
    should_summarize = feed_config.get("summarize", False)
    ai_summary = None
    if should_summarize and groq_api_key:
        feed_lang = feed_config.get("lang", None)
        ai_summary = summarize_article(title, clean_desc, groq_api_key, feed_lang)

    # Tronque la description originale
    if len(clean_desc) > max_desc_len:
        clean_desc = clean_desc[:max_desc_len].rsplit("\n", 1)[0] + "\n..."

    # Ajoute le resume IA en dessous si disponible
    if ai_summary:
        description = f"{clean_desc}\n\n**\U0001f916 Resume IA :**\n{ai_summary}"
    else:
        description = clean_desc

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


def process_feed(feed_config, state, webhook_url, config, groq_api_key=None, dry_run=False):
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
    max_age_hours = config.get("max_article_age_hours", 24)
    age_cutoff = now - timedelta(hours=max_age_hours)
    new_count = 0

    # Traite les entries en ordre chronologique (plus ancien d'abord)
    entries = list(reversed(feed.entries))

    for entry in entries:
        entry_id = get_entry_id(entry)

        # Deja poste ?
        if entry_id in state["posted"]:
            continue

        # Ignore les articles plus vieux que max_article_age_hours
        pub_date = get_entry_date(entry)
        if pub_date and pub_date < age_cutoff:
            state["posted"].append(entry_id)
            continue

        # Filtre par mots-cles exclus (ex: HTB, THM)
        exclude_keywords = feed_config.get("exclude_keywords", [])
        if exclude_keywords:
            title_lower = entry.get("title", "").lower()
            if any(kw.lower() in title_lower for kw in exclude_keywords):
                print(f"  [FILTRE] {entry.get('title', 'Sans titre')}")
                state["posted"].append(entry_id)
                continue

        # Construit l'embed (avec resume IA si active)
        embed = build_embed(entry, feed_config, config.get("max_description_length", 400), groq_api_key)

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

    # Groq API key (optionnel, pour les resumes IA)
    groq_api_key = os.environ.get("GROQ_API_KEY", "")
    if groq_api_key:
        print("[+] Groq API detectee - resumes IA actifs")
    else:
        print("[*] Pas de GROQ_API_KEY - resumes IA desactives")

    config = load_config()
    state = load_state()
    total_new = 0

    for feed_config in config["feeds"]:
        new = process_feed(feed_config, state, webhook_url, config, groq_api_key, dry_run)
        total_new += new

    save_state(state, config.get("max_state_entries", 500))

    print(f"\n{'=' * 50}")
    print(f"Termine: {total_new} nouvel(aux) article(s) au total")
    print(f"State: {len(state['posted'])} entrees en memoire")


if __name__ == "__main__":
    main()
