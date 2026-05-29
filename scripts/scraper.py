"""
GrantMatch — Script de veille automatique v2
=============================================
Sources RSS/API scrapables :
  - Calenda (archéologie, bourses, zones géo)
  - jobs.ac.uk (Historical & Philosophical Studies)
  - THE Jobs (Times Higher Education)
  - BAJR (British Archaeology Jobs)
  - AcademicPositions.eu (scraping HTML léger)
  - USAJobs API (séries 0193 archéologie + 0190 anthropologie)
  - Sites fondations (Gerda Henkel, Wenner-Gren, ANR, EFEO, Quai Branly)

Sources non-scrapables → liens directs dans l'interface :
  - emploi.cnrs.fr, Galaxie/CNU, IRD, FNRS, EAA, DAI, IFAO

Sortie :
  - discovered.json  : nouvelles annonces (à valider)
  - grants.json      : deadlines mises à jour si détectées
"""

import json, re, sys, datetime, hashlib, requests, feedparser
from dateutil import parser as dateparser

TODAY = datetime.date.today()

HEADERS = {
    "User-Agent": "GrantMatch-Bot/2.0 (academic funding aggregator; "
                  "contact via GitHub Issues)"
}

# ─────────────────────────────────────────────
# MOTS-CLÉS
# ─────────────────────────────────────────────

KW_GRANT = [
    "postdoc","post-doc","post doc","fellowship","bourse","grant",
    "funding","financement","scholarship","stipend","allocation",
    "appel à candidature","call for applications","research position",
    "contrat postdoctoral","poste postdoctoral","research fellow",
    "research associate","junior researcher","chercheur postdoctoral",
]

KW_DISCIPLINE = [
    "archéologie","archaeology","archeology",
    "anthropologie","anthropology","bioarchaeology","bioarchéologie",
    "préhistoire","prehistory","prehistoric","paléolithique",
    "neolithic","neolithique","archéométrie","archaeometry",
    "fouille","excavation","SHS","humanities","sciences humaines",
    "ancient history","histoire ancienne","patrimoine","heritage",
    "numismatique","numismatics","épigraphie","epigraphy",
]

KW_EXCLUDE = [
    "colloque","conférence","conference","séminaire","seminar",
    "appel à contribution","call for papers","cfp",
    "master","licence","bachelor",
]

KW_MCF = [
    "maître de conférences","MCF","lecturer","assistant professor",
    "associate professor","professeur des universités","PU",
    "permanent position","tenure","poste permanent","poste titulaire",
]

# ─────────────────────────────────────────────
# FLUX RSS
# ─────────────────────────────────────────────

CALENDA_FEEDS = [
    {"url":"https://calenda.org/feed.php?type=47",          "label":"Calenda – Bourses & emploi",        "job":True},
    {"url":"https://calenda.org/feed.php?cat=293",          "label":"Calenda – Archéologie",             "job":True},
    {"url":"https://calenda.org/feed.php?cat=303",          "label":"Calenda – Préhistoire & Antiquité", "job":True},
    {"url":"https://calenda.org/feed.php?cat=213",          "label":"Calenda – Anthropologie",           "job":True},
    {"url":"https://calenda.org/feed.php?cat=289",          "label":"Calenda – Vie de la recherche",     "job":True},
    {"url":"https://calenda.org/feed.php?cat=353",          "label":"Calenda – Asie du Sud-Est",         "job":True},
    {"url":"https://calenda.org/feed.php?cat=355",          "label":"Calenda – Méditerranée",            "job":True},
    {"url":"https://calenda.org/feed.php?cat=331",          "label":"Calenda – Afrique subsaharienne",   "job":True},
    {"url":"https://calenda.org/feed.php?cat=329",          "label":"Calenda – Afrique du Nord",         "job":True},
    {"url":"https://calenda.org/feed.php?cat=351",          "label":"Calenda – Monde indien",            "job":True},
    {"url":"https://calenda.org/feed.php?cat=336",          "label":"Calenda – Amériques",               "job":True},
    {"url":"https://calenda.org/feed.php?cat=345",          "label":"Calenda – Proche-Orient",           "job":True},
]

OTHER_FEEDS = [
    # jobs.ac.uk — recherche ciblée archéologie + postdoc
    {
        "url":   "https://www.jobs.ac.uk/search/rss?keywords=archaeology&jobType%5B%5D=postdoctoral-research",
        "label": "jobs.ac.uk – Archaeology postdoc",
        "job":   True,
        "country": "uk",
        "flag":  "🇬🇧",
    },
    {
        "url":   "https://www.jobs.ac.uk/search/rss?keywords=archaeology&jobType%5B%5D=academic-research",
        "label": "jobs.ac.uk – Archaeology research",
        "job":   True,
        "country": "uk",
        "flag":  "🇬🇧",
    },
    # THE Jobs
    {
        "url":   "https://www.timeshighereducation.com/unijobs/jobsrss/?keywords=archaeology+postdoc",
        "label": "THE Jobs – Archaeology postdoc",
        "job":   True,
        "country": "uk",
        "flag":  "🇬🇧",
    },
    # BAJR — WordPress RSS standard
    {
        "url":   "https://www.bajr.org/feed/",
        "label": "BAJR – British Archaeology Jobs",
        "job":   True,
        "country": "uk",
        "flag":  "🇬🇧",
    },
    # Société Préhistorique Française
    {
        "url":   "https://www.prehistoire.org/rss.php",
        "label": "Société Préhistorique Française",
        "job":   True,
        "country": "france",
        "flag":  "🇫🇷",
    },
    # EAA (European Association of Archaeologists) — blog WordPress
    {
        "url":   "https://www.e-a-a.org/feed/",
        "label": "EAA – European Association of Archaeologists",
        "job":   True,
        "country": "other_eu",
        "flag":  "🇪🇺",
    },
    # DAI (Deutsches Archäologisches Institut)
    {
        "url":   "https://www.dainst.org/en/feed",
        "label": "DAI – Deutsches Archäologisches Institut",
        "job":   True,
        "country": "de",
        "flag":  "🇩🇪",
    },
]

# ─────────────────────────────────────────────
# PAGES FONDATIONS (scraping deadline)
# ─────────────────────────────────────────────

FOUNDATION_PAGES = [
    {
        "id": "gerda",
        "label": "Gerda Henkel Stiftung",
        "url": "https://www.gerda-henkel-stiftung.de/en/researchscholarships",
        "deadline_patterns": [
            r"(\d{1,2}[\s\.](?:january|february|march|april|may|june|july|august|september|october|november|december)[\s\.]\d{4})",
            r"(\d{1,2}[\s\.](?:januar|februar|märz|april|mai|juni|juli|august|september|oktober|november|dezember)[\s\.]\d{4})",
            r"deadline[:\s]+([^\n<]{5,40})",
        ],
    },
    {
        "id": "wenner",
        "label": "Wenner-Gren Foundation",
        "url": "https://www.wennergren.org/grants/post-phd-research-grants",
        "deadline_patterns": [
            r"(May 1|November 1)[,\s]+\d{4}",
            r"deadline[:\s]+([^\n<]{5,40})",
        ],
    },
    {
        "id": "anr",
        "label": "ANR – Appels en cours",
        "url": "https://anr.fr/fr/appels-ouverts/appels-en-cours/",
        "deadline_patterns": [
            r"Access.ERC[^\n]*(\d{2}/\d{2}/\d{4})",
            r"JCJC[^\n]*(\d{2}/\d{2}/\d{4})",
        ],
    },
    {
        "id": "efeo",
        "label": "EFEO – Contrats postdoctoraux",
        "url": "https://www.efeo.fr/base.php?code=563",
        "deadline_patterns": [
            r"(\d{1,2}\s+\w+\s+\d{4})",
            r"date limite[:\s]+([^\n<]{5,40})",
        ],
    },
    {
        "id": "mqb",
        "label": "Musée du Quai Branly",
        "url": "https://www.quaibranly.fr/fr/recherche-scientifique/activites/bourses-et-prix-de-these/bourses-de-recherches-doctorales-et-contrats-postdoctoraux",
        "deadline_patterns": [
            r"(\d{1,2}\s+\w+\s+\d{4})",
            r"avant le\s+([^\n<]{5,30})",
        ],
    },
    {
        "id": "fyssen",
        "label": "Fondation Fyssen",
        "url": "https://www.fondationfyssen.fr/en/study-grants/",
        "deadline_patterns": [
            r"deadline[:\s]+([^\n<]{5,40})",
            r"(\w+\s+\d{1,2},?\s+\d{4})",
        ],
    },
    {
        "id": "ifao",
        "label": "IFAO – Bourses postdoctorales",
        "url": "https://www.ifao.egnet.net/recherche/recherche-soutien/bourses-doctorales-et-post-doctorales/",
        "deadline_patterns": [
            r"(\d{1,2}\s+\w+\s+\d{4})",
            r"date limite[:\s]+([^\n<]{5,40})",
            r"avant le\s+([^\n<]{5,30})",
        ],
    },
]

# ─────────────────────────────────────────────
# USAJOBS API
# ─────────────────────────────────────────────

USAJOBS_API = "https://data.usajobs.gov/api/search"
USAJOBS_HEADERS = {
    "User-Agent": "grantmatch@archaeology-shs.org",
    "Authorization-Key": "",  # API key publique non requise pour recherches basiques
    "Host": "data.usajobs.gov",
}
USAJOBS_QUERIES = [
    {"Keyword": "archaeologist", "PositionOfferingTypeCode": "15317"},  # postdoc/research
    {"Keyword": "anthropologist", "PositionOfferingTypeCode": "15317"},
    {"Keyword": "archaeologist", "JobCategoryCode": "0193"},
    {"Keyword": "anthropologist", "JobCategoryCode": "0190"},
]

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def make_id(text):
    return hashlib.md5(text.encode()).hexdigest()[:10]

def is_relevant(title, summary="", check_mcf=False):
    text = (title + " " + summary).lower()
    for kw in KW_EXCLUDE:
        if kw.lower() in text:
            return False
    has_grant = any(kw.lower() in text for kw in KW_GRANT)
    has_disc  = any(kw.lower() in text for kw in KW_DISCIPLINE)
    if check_mcf:
        has_mcf = any(kw.lower() in text for kw in KW_MCF)
        return (has_grant or has_mcf) and has_disc
    return has_grant and has_disc

def extract_deadline(text):
    patterns = [
        r"deadline[:\s]+(\d{1,2}[\/\.\s]\w+[\/\.\s]\d{2,4})",
        r"closing date[:\s]+(\d{1,2}[\/\.\s]\w+[\/\.\s]\d{2,4})",
        r"date limite[:\s]+(\d{1,2}[\/\.\s]\w+[\/\.\s]\d{2,4})",
        r"avant le[:\s]+(\d{1,2}[\/\.\s]\w+[\/\.\s]\d{2,4})",
        r"close[sd]?\s+(?:on|by)?[:\s]+(\d{1,2}[\/\.\s]\w+[\/\.\s]\d{2,4})",
        r"(\d{1,2}\s+(?:january|february|march|april|may|june|july|august"
        r"|september|october|november|december)\s+\d{4})",
        r"(\d{1,2}\s+(?:janvier|février|mars|avril|mai|juin|juillet|août"
        r"|septembre|octobre|novembre|décembre)\s+\d{4})",
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

def guess_type(title, summary):
    text = (title + " " + summary).lower()
    if any(kw in text for kw in ["maître de conférences","mcf","lecturer",
                                   "assistant professor","permanent","titulaire",
                                   "associate professor","professeur"]):
        return "mcf"
    return "postdoc"

def load_existing():
    try:
        with open("discovered.json","r",encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"last_updated": TODAY.isoformat(), "items": []}

def load_grants():
    with open("grants.json","r",encoding="utf-8") as f:
        return json.load(f)

def save_grants(data):
    with open("grants.json","w",encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def save_discovered(data):
    with open("discovered.json","w",encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ─────────────────────────────────────────────
# SCRAPERS
# ─────────────────────────────────────────────

def scrape_rss(feed_config, existing_ids):
    results = []
    try:
        feed = feedparser.parse(feed_config["url"])
        for entry in feed.entries:
            title   = entry.get("title","")
            summary = entry.get("summary","") or entry.get("description","")
            link    = entry.get("link","")
            published = entry.get("published","") or entry.get("updated","")

            if not is_relevant(title, summary, check_mcf=True):
                continue

            pub_date = None
            if published:
                try:
                    pub_date = dateparser.parse(published).date().isoformat()
                except Exception:
                    pass

            # Ignorer les annonces > 90 jours
            if pub_date:
                try:
                    if (TODAY - datetime.date.fromisoformat(pub_date)).days > 90:
                        continue
                except Exception:
                    pass

            item_id = make_id(link or title)
            if item_id in existing_ids:
                continue

            deadline = extract_deadline(title + " " + summary)
            job_type = guess_type(title, summary)

            item = {
                "id":        item_id,
                "type":      job_type,  # "postdoc" ou "mcf"
                "source":    feed_config["label"],
                "country":   feed_config.get("country",""),
                "flag":      feed_config.get("flag","🌍"),
                "title":     title.strip(),
                "url":       link,
                "published": pub_date,
                "deadline":  deadline,
                "summary":   summary[:400].strip() if summary else "",
                "auto":      True,
                "validated": False,
                "active":    True,
            }
            results.append(item)
    except Exception as e:
        print(f"  ⚠ Erreur RSS {feed_config['label']}: {e}", file=sys.stderr)
    return results


def scrape_academic_positions(existing_ids):
    """Scraping léger de la page archéologie sur AcademicPositions.eu"""
    results = []
    url = "https://academicpositions.eu/jobs/archaeology"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        clean = re.sub(r"<[^>]+>"," ", r.text)
        clean = re.sub(r"\s+"," ", clean)

        # Chercher les blocs d'annonces (heuristique)
        blocks = re.findall(
            r"((?:postdoc|fellowship|research\s+fellow|research\s+associate)[^\.]{20,300})",
            clean, re.IGNORECASE
        )
        for block in blocks[:20]:
            if not any(kw.lower() in block.lower() for kw in KW_DISCIPLINE):
                continue
            item_id = make_id(block[:60])
            if item_id in existing_ids:
                continue
            deadline = extract_deadline(block)
            results.append({
                "id":        item_id,
                "type":      "postdoc",
                "source":    "AcademicPositions.eu",
                "country":   "other_eu",
                "flag":      "🇪🇺",
                "title":     block[:120].strip(),
                "url":       url,
                "published": TODAY.isoformat(),
                "deadline":  deadline,
                "summary":   block[:400].strip(),
                "auto":      True,
                "validated": False,
                "active":    True,
            })
    except Exception as e:
        print(f"  ⚠ Erreur AcademicPositions: {e}", file=sys.stderr)
    return results


def scrape_usajobs(existing_ids):
    """Appel à l'API publique USAJobs pour postes archéologie/anthropologie."""
    results = []
    seen = set()
    for query in USAJOBS_QUERIES:
        params = {
            "ResultsPerPage": 25,
            "Fields": "Min",
            **query
        }
        try:
            r = requests.get(USAJOBS_API, headers={**HEADERS,
                "Host": "data.usajobs.gov",
                "User-Agent": "grantmatch@archaeology-shs.org",
            }, params=params, timeout=15)
            if r.status_code != 200:
                continue
            data = r.json()
            jobs = (data.get("SearchResult",{})
                        .get("SearchResultItems",[]))
            for job in jobs:
                mv = job.get("MatchedObjectDescriptor",{})
                title      = mv.get("PositionTitle","")
                link       = mv.get("PositionURI","")
                org        = mv.get("OrganizationName","")
                close_date = mv.get("ApplicationCloseDate","")
                open_date  = mv.get("PublicationStartDate","")
                locations  = mv.get("PositionLocationDisplay","")
                salary     = mv.get("PositionRemuneration",[{}])[0]
                salary_str = ""
                if salary:
                    sal_min = salary.get("MinimumRange","")
                    sal_max = salary.get("MaximumRange","")
                    sal_cur = salary.get("CurrencyCode","USD")
                    if sal_min:
                        salary_str = f"{sal_min}–{sal_max} {sal_cur}/an"

                item_id = make_id(link or title)
                if item_id in existing_ids or item_id in seen:
                    continue
                seen.add(item_id)

                # Formater la deadline
                deadline = None
                if close_date:
                    try:
                        d = dateparser.parse(close_date)
                        if d and d.date() > TODAY:
                            deadline = d.date().isoformat()
                    except Exception:
                        pass

                results.append({
                    "id":        item_id,
                    "type":      "postdoc",
                    "source":    "USAJobs.gov",
                    "country":   "intl",
                    "flag":      "🇺🇸",
                    "title":     title,
                    "lab":       f"{org} – {locations}",
                    "url":       link,
                    "published": open_date[:10] if open_date else TODAY.isoformat(),
                    "deadline":  deadline,
                    "salary":    salary_str,
                    "summary":   f"{org} | {locations}",
                    "auto":      True,
                    "validated": False,
                    "active":    True,
                })
        except Exception as e:
            print(f"  ⚠ Erreur USAJobs ({query}): {e}", file=sys.stderr)
    return results


def scrape_foundation_page(page_config):
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
        clean = re.sub(r"<[^>]+"," ", r.text)
        clean = re.sub(r"\s+"," ", clean)

        for pattern in page_config.get("deadline_patterns",[]):
            m = re.search(pattern, clean, re.IGNORECASE)
            if m:
                raw = m.group(0)
                result["raw_snippet"] = raw[:100]
                date_str = m.group(1) if m.lastindex else raw
                try:
                    d = dateparser.parse(date_str, dayfirst=True)
                    if d and d.date() > TODAY:
                        result["deadline_found"] = d.date().isoformat()
                        break
                except Exception:
                    pass
    except Exception as e:
        print(f"  ⚠ Erreur {page_config['label']}: {e}", file=sys.stderr)
    return result


def update_known_deadlines(grants_data, foundation_results):
    changed = False
    id_map = {r["id"]: r for r in foundation_results}
    for grant in grants_data["grants"]:
        gid = grant["id"].split("_")[0]
        if gid in id_map:
            found = id_map[gid].get("deadline_found")
            if found and found != grant.get("deadline"):
                print(f"  📅 {grant['id']}: {grant.get('deadline')} → {found}")
                grant["_deadline_previous"]    = grant.get("deadline")
                grant["deadline"]              = found
                grant["_deadline_auto_updated"]= TODAY.isoformat()
                changed = True
    if changed:
        grants_data["meta"]["last_updated"] = TODAY.isoformat()
    return changed

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print(f"🔍 GrantMatch Scraper v2 — {TODAY}")
    print("=" * 55)

    discovered   = load_existing()
    grants_data  = load_grants()
    existing_ids = {item["id"] for item in discovered.get("items",[])}
    new_items    = []

    # 1. Calenda
    print("\n📡 Calenda RSS…")
    for feed in CALENDA_FEEDS:
        items = scrape_rss(feed, existing_ids)
        for item in items:
            new_items.append(item)
            existing_ids.add(item["id"])
        if items:
            print(f"  ✓ {feed['label']}: {len(items)} nouvelles")

    # 2. Autres flux RSS
    print("\n📡 Flux RSS spécialisés…")
    for feed in OTHER_FEEDS:
        print(f"  → {feed['label']}")
        items = scrape_rss(feed, existing_ids)
        for item in items:
            new_items.append(item)
            existing_ids.add(item["id"])
        if items:
            print(f"     {len(items)} nouvelles annonces")

    # 3. AcademicPositions.eu
    print("\n🌐 AcademicPositions.eu…")
    items = scrape_academic_positions(existing_ids)
    for item in items:
        new_items.append(item)
        existing_ids.add(item["id"])
    print(f"  {len(items)} nouvelles annonces")

    # 4. USAJobs API
    print("\n🇺🇸 USAJobs API…")
    items = scrape_usajobs(existing_ids)
    for item in items:
        new_items.append(item)
        existing_ids.add(item["id"])
    print(f"  {len(items)} nouvelles annonces")

    # 5. Fondations — vérification deadlines
    print("\n🏛  Vérification pages fondations…")
    foundation_results = []
    for page in FOUNDATION_PAGES:
        print(f"  → {page['label']}")
        result = scrape_foundation_page(page)
        foundation_results.append(result)
        if result["deadline_found"]:
            print(f"     📅 {result['deadline_found']}")

    # 6. Mise à jour grants.json
    print("\n⚙️  Mise à jour grants.json…")
    grants_changed = update_known_deadlines(grants_data, foundation_results)
    if grants_changed:
        save_grants(grants_data)
        print("  ✅ grants.json mis à jour")
    else:
        print("  — Aucun changement")

    # 7. Purge + sauvegarde discovered.json
    cutoff  = (TODAY - datetime.timedelta(days=90)).isoformat()
    old_items = [
        i for i in discovered.get("items",[])
        if i.get("published","9999") >= cutoff or not i.get("published")
    ]
    discovered.update({
        "last_updated":   TODAY.isoformat(),
        "last_checked":   TODAY.isoformat(),
        "new_this_run":   len(new_items),
        "items":          old_items + new_items,
    })
    save_discovered(discovered)

    print(f"\n{'='*55}")
    n_postdoc = len([i for i in new_items if i.get("type")=="postdoc"])
    n_mcf     = len([i for i in new_items if i.get("type")=="mcf"])
    print(f"✅ {len(new_items)} nouvelles annonces "
          f"({n_postdoc} postdoc, {n_mcf} MCF/permanent)")
    if grants_changed:
        print("⚠️  Deadlines modifiées dans grants.json — PR créée")

if __name__ == "__main__":
    main()
