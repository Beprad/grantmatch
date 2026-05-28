"""
GrantMatch — Script de veille automatique
==========================================
Sources :
  - Calenda RSS (archéologie, bourses, zones géo)
  - EURAXESS (archéologie + anthropologie)
  - archpostgrad.wordpress.com (RSS postdoc archaeology)
  - Sites fondations (Gerda Henkel, Wenner-Gren, ANR, EFEO, Quai Branly)

Sortie :
  - discovered.json  : nouvelles annonces trouvées (à valider manuellement)
  - grants.json      : deadlines mises à jour si détectées (pour les grants connus)
"""

import json
import re
import sys
import datetime
import hashlib
import requests
import feedparser
from dateutil import parser as dateparser

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

HEADERS = {
    "User-Agent": "GrantMatch-Bot/1.0 (academic funding aggregator; contact via GitHub)"
}

TODAY = datetime.date.today()

# Mots-clés pour filtrer les annonces pertinentes
KEYWORDS_GRANT = [
    "postdoc", "post-doc", "post doc", "fellowship", "bourse", "grant",
    "funding", "financement", "scholarship", "stipend", "allocation",
    "appel à candidature", "call for applications", "research position",
    "contrat postdoctoral", "poste postdoctoral"
]

KEYWORDS_DISCIPLINE = [
    "archéologie", "archaeology", "archeology",
    "anthropologie", "anthropology",
    "bioarchaeology", "bioarchéologie",
    "préhistoire", "prehistory", "prehistoric",
    "paléolithique", "neolithic", "neolithique",
    "archéométrie", "archaeometry",
    "fouille", "excavation",
    "SHS", "humanities", "sciences humaines"
]

# Mots à exclure (réduire le bruit)
KEYWORDS_EXCLUDE = [
    "colloque", "conférence", "conference", "séminaire", "seminar",
    "appel à contribution", "call for papers", "cfp",
    "master", "licence", "bachelor", "doctorat", "phd position",
    "thèse", "thesis"
]

# ─────────────────────────────────────────────
# FLUX RSS CALENDA
# Sources : https://calenda.org/feeds
# ─────────────────────────────────────────────

CALENDA_FEEDS = [
    # Bourses, prix et emploi — général
    {"url": "https://calenda.org/feed.php?type=47", "label": "Calenda – Bourses & emploi"},
    # Archéologie (catégorie discipline)
    {"url": "https://calenda.org/feed.php?cat=293", "label": "Calenda – Archéologie"},
    # Préhistoire et Antiquité
    {"url": "https://calenda.org/feed.php?cat=303", "label": "Calenda – Préhistoire & Antiquité"},
    # Ethnologie, anthropologie
    {"url": "https://calenda.org/feed.php?cat=213", "label": "Calenda – Anthropologie"},
    # Asie du Sud-Est
    {"url": "https://calenda.org/feed.php?cat=353", "label": "Calenda – Asie du Sud-Est"},
    # Méditerranée
    {"url": "https://calenda.org/feed.php?cat=355", "label": "Calenda – Méditerranée"},
    # Afrique subsaharienne
    {"url": "https://calenda.org/feed.php?cat=331", "label": "Calenda – Afrique subsaharienne"},
    # Afrique du Nord
    {"url": "https://calenda.org/feed.php?cat=329", "label": "Calenda – Afrique du Nord"},
    # Monde indien
    {"url": "https://calenda.org/feed.php?cat=351", "label": "Calenda – Monde indien"},
    # Amériques
    {"url": "https://calenda.org/feed.php?cat=336", "label": "Calenda – Amériques"},
    # Proche-Orient
    {"url": "https://calenda.org/feed.php?cat=345", "label": "Calenda – Proche-Orient"},
    # Vie de la recherche (financements institutionnels)
    {"url": "https://calenda.org/feed.php?cat=289", "label": "Calenda – Vie de la recherche"},
]

# ─────────────────────────────────────────────
# AUTRES FLUX RSS
# ─────────────────────────────────────────────

OTHER_FEEDS = [
    {
        "url": "https://archpostgrad.wordpress.com/feed/",
        "label": "ArchPostgrad – Postdoc archaeology"
    },
    {
        "url": "https://www.prehistoire.org/rss.php",
        "label": "Société Préhistorique Française"
    },
]

# ─────────────────────────────────────────────
# PAGES WEB (scraping léger des sites fondations)
# On vérifie juste si une nouvelle section "appel ouvert" est apparue
# ─────────────────────────────────────────────

FOUNDATION_PAGES = [
    {
        "id": "gerda",
        "label": "Gerda Henkel Stiftung",
        "url": "https://www.gerda-henkel-stiftung.de/en/researchscholarships",
        "deadline_patterns": [
            r"(\d{1,2}[\s\.]\w+[\s\.]\d{4})",       # "28 May 2026"
            r"(\w+\s+\d{1,2},?\s+\d{4})",             # "November 30, 2026"
            r"deadline[:\s]+([^\n<]{5,40})",
            r"closing date[:\s]+([^\n<]{5,40})",
        ]
    },
    {
        "id": "wenner",
        "label": "Wenner-Gren Foundation",
        "url": "https://www.wennergren.org/grants/post-phd-research-grants",
        "deadline_patterns": [
            r"(May 1|November 1)[,\s]+\d{4}",
            r"deadline[:\s]+([^\n<]{5,40})",
        ]
    },
    {
        "id": "anr",
        "label": "ANR – Appels en cours",
        "url": "https://anr.fr/fr/appels-ouverts/appels-en-cours/",
        "deadline_patterns": [
            r"Access.ERC[^\n]*(\d{2}/\d{2}/\d{4})",
            r"JCJC[^\n]*(\d{2}/\d{2}/\d{4})",
        ]
    },
    {
        "id": "efeo",
        "label": "EFEO – Contrats postdoctoraux",
        "url": "https://www.efeo.fr/base.php?code=563",
        "deadline_patterns": [
            r"(\d{1,2}\s+\w+\s+\d{4})",
            r"date limite[:\s]+([^\n<]{5,40})",
        ]
    },
    {
        "id": "mqb",
        "label": "Musée du Quai Branly – Bourses",
        "url": "https://www.quaibranly.fr/fr/recherche-scientifique/activites/bourses-et-prix-de-these/bourses-de-recherches-doctorales-et-contrats-postdoctoraux",
        "deadline_patterns": [
            r"(\d{1,2}\s+\w+\s+\d{4})",
            r"date limite[:\s]+([^\n<]{5,40})",
            r"avant le\s+([^\n<]{5,30})",
        ]
    },
    {
        "id": "fyssen",
        "label": "Fondation Fyssen",
        "url": "https://www.fondationfyssen.fr/en/study-grants/",
        "deadline_patterns": [
            r"deadline[:\s]+([^\n<]{5,40})",
            r"(\w+\s+\d{1,2},?\s+\d{4})",
        ]
    },
]

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def make_id(text):
    """Génère un identifiant court et stable depuis un texte."""
    return hashlib.md5(text.encode()).hexdigest()[:10]

def is_relevant(title, summary=""):
    """Retourne True si l'annonce semble pertinente (financement en archéo/SHS)."""
    text = (title + " " + summary).lower()

    # Exclure le bruit
    for kw in KEYWORDS_EXCLUDE:
        if kw.lower() in text:
            return False

    # Doit contenir au moins un mot-clé de financement ET un de discipline
    has_grant = any(kw.lower() in text for kw in KEYWORDS_GRANT)
    has_discipline = any(kw.lower() in text for kw in KEYWORDS_DISCIPLINE)

    return has_grant and has_discipline

def extract_deadline(text):
    """Tente d'extraire une date de deadline depuis un texte brut."""
    patterns = [
        r"deadline[:\s]+(\d{1,2}[\/\.\s]\w+[\/\.\s]\d{2,4})",
        r"closing date[:\s]+(\d{1,2}[\/\.\s]\w+[\/\.\s]\d{2,4})",
        r"date limite[:\s]+(\d{1,2}[\/\.\s]\w+[\/\.\s]\d{2,4})",
        r"avant le[:\s]+(\d{1,2}[\/\.\s]\w+[\/\.\s]\d{2,4})",
        r"(\d{1,2}\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4})",
        r"(\d{1,2}\s+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+\d{4})",
    ]
    for p in patterns:
        m = re.search(p, text.lower())
        if m:
            try:
                d = dateparser.parse(m.group(1), dayfirst=True)
                if d and d.date() > TODAY:
                    return d.date().isoformat()
            except Exception:
                pass
    return None

def load_existing():
    """Charge discovered.json existant pour éviter les doublons."""
    try:
        with open("discovered.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"last_updated": TODAY.isoformat(), "items": []}

def load_grants():
    """Charge grants.json."""
    with open("grants.json", "r", encoding="utf-8") as f:
        return json.load(f)

def save_grants(data):
    with open("grants.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def save_discovered(data):
    with open("discovered.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ─────────────────────────────────────────────
# SCRAPERS
# ─────────────────────────────────────────────

def scrape_rss(feed_config):
    """Parse un flux RSS et retourne les annonces pertinentes."""
    results = []
    try:
        feed = feedparser.parse(feed_config["url"])
        for entry in feed.entries:
            title = entry.get("title", "")
            summary = entry.get("summary", "") or entry.get("description", "")
            link = entry.get("link", "")
            published = entry.get("published", "") or entry.get("updated", "")

            # Filtre de pertinence
            if not is_relevant(title, summary):
                continue

            # Date de publication
            pub_date = None
            if published:
                try:
                    pub_date = dateparser.parse(published).date().isoformat()
                except Exception:
                    pass

            # Ne garder que les annonces récentes (< 90 jours)
            if pub_date:
                try:
                    if (TODAY - datetime.date.fromisoformat(pub_date)).days > 90:
                        continue
                except Exception:
                    pass

            deadline = extract_deadline(title + " " + summary)

            results.append({
                "id": make_id(link or title),
                "source": feed_config["label"],
                "title": title.strip(),
                "url": link,
                "published": pub_date,
                "deadline": deadline,
                "summary": summary[:300].strip() if summary else "",
                "auto": True,
                "validated": False,
            })
    except Exception as e:
        print(f"  ⚠ Erreur RSS {feed_config['label']}: {e}", file=sys.stderr)

    return results

def scrape_foundation_page(page_config):
    """
    Scrape légèrement une page fondation pour détecter des deadlines.
    Retourne un dict avec la deadline trouvée (ou None).
    """
    result = {
        "id": page_config["id"],
        "label": page_config["label"],
        "url": page_config["url"],
        "deadline_found": None,
        "raw_snippet": None,
    }
    try:
        r = requests.get(page_config["url"], headers=HEADERS, timeout=15)
        r.raise_for_status()
        text = r.text

        # Strip HTML tags pour l'analyse
        clean = re.sub(r"<[^>]+>", " ", text)
        clean = re.sub(r"\s+", " ", clean)

        # Chercher les deadlines via les patterns
        for pattern in page_config.get("deadline_patterns", []):
            m = re.search(pattern, clean, re.IGNORECASE)
            if m:
                raw = m.group(0)
                result["raw_snippet"] = raw[:100]
                # Tenter de parser la date
                date_str = m.group(1) if m.lastindex else raw
                try:
                    d = dateparser.parse(date_str, dayfirst=True)
                    if d and d.date() > TODAY:
                        result["deadline_found"] = d.date().isoformat()
                        break
                except Exception:
                    pass

    except Exception as e:
        print(f"  ⚠ Erreur scraping {page_config['label']}: {e}", file=sys.stderr)

    return result

# ─────────────────────────────────────────────
# MISE À JOUR GRANTS.JSON
# ─────────────────────────────────────────────

def update_known_deadlines(grants_data, foundation_results):
    """
    Met à jour les deadlines dans grants.json si le scraping
    détecte une date différente de celle stockée.
    Retourne True si des changements ont eu lieu.
    """
    changed = False
    id_map = {r["id"]: r for r in foundation_results}

    for grant in grants_data["grants"]:
        gid = grant["id"].split("_")[0]  # "gerda_may" → "gerda"
        if gid in id_map:
            found = id_map[gid].get("deadline_found")
            if found and found != grant.get("deadline"):
                print(f"  📅 Deadline mise à jour : {grant['id']} : {grant.get('deadline')} → {found}")
                grant["_deadline_previous"] = grant.get("deadline")
                grant["deadline"] = found
                grant["_deadline_auto_updated"] = TODAY.isoformat()
                changed = True

    if changed:
        grants_data["meta"]["last_updated"] = TODAY.isoformat()

    return changed

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print(f"🔍 GrantMatch Scraper — {TODAY}")
    print("=" * 50)

    # Charger l'existant
    discovered = load_existing()
    existing_ids = {item["id"] for item in discovered.get("items", [])}
    grants_data = load_grants()

    new_items = []

    # 1. Flux RSS Calenda
    print("\n📡 Flux RSS Calenda…")
    for feed in CALENDA_FEEDS:
        print(f"  → {feed['label']}")
        items = scrape_rss(feed)
        for item in items:
            if item["id"] not in existing_ids:
                new_items.append(item)
                existing_ids.add(item["id"])
        print(f"     {len(items)} annonces trouvées, {len([i for i in items if i['id'] in {x['id'] for x in new_items}])} nouvelles")

    # 2. Autres flux RSS
    print("\n📡 Autres flux RSS…")
    for feed in OTHER_FEEDS:
        print(f"  → {feed['label']}")
        try:
            items = scrape_rss(feed)
            for item in items:
                if item["id"] not in existing_ids:
                    new_items.append(item)
                    existing_ids.add(item["id"])
            print(f"     {len(items)} annonces pertinentes")
        except Exception as e:
            print(f"     ⚠ Erreur : {e}")

    # 3. Scraping pages fondations
    print("\n🏛  Vérification des pages fondations…")
    foundation_results = []
    for page in FOUNDATION_PAGES:
        print(f"  → {page['label']}")
        result = scrape_foundation_page(page)
        foundation_results.append(result)
        if result["deadline_found"]:
            print(f"     📅 Deadline détectée : {result['deadline_found']} ({result['raw_snippet']})")
        else:
            print(f"     — Aucune deadline future détectée")

    # 4. Mettre à jour grants.json si des deadlines ont changé
    print("\n⚙️  Mise à jour de grants.json…")
    grants_changed = update_known_deadlines(grants_data, foundation_results)
    if grants_changed:
        save_grants(grants_data)
        print("  ✅ grants.json mis à jour")
    else:
        print("  — Aucun changement détecté")

    # 5. Sauvegarder discovered.json
    # Purger les entrées de plus de 90 jours
    cutoff = (TODAY - datetime.timedelta(days=90)).isoformat()
    old_items = [
        item for item in discovered.get("items", [])
        if item.get("published", "9999") >= cutoff or not item.get("published")
    ]

    discovered["last_updated"] = TODAY.isoformat()
    discovered["last_checked"] = TODAY.isoformat()
    discovered["new_this_run"] = len(new_items)
    discovered["items"] = old_items + new_items

    save_discovered(discovered)

    # 6. Résumé
    print(f"\n{'='*50}")
    print(f"✅ Terminé — {len(new_items)} nouvelles annonces ajoutées à discovered.json")
    if grants_changed:
        print("⚠️  Des deadlines dans grants.json ont été mises à jour — PR créée pour validation")
    else:
        print("— Aucune deadline connue modifiée")

    # Exit code non-zéro si rien de nouveau (pour le workflow GitHub Actions)
    if len(new_items) == 0 and not grants_changed:
        sys.exit(0)
    else:
        sys.exit(0)  # Toujours 0 pour ne pas faire échouer le workflow

if __name__ == "__main__":
    main()
