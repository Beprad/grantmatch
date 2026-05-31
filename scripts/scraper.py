"""
GrantMatch — Script de veille automatique v3
=============================================
Sources RSS/API scrapables :
  BOURSES INSTITUTIONNELLES :
  - Calenda (archéologie, bourses, zones géo)
  - Sites fondations (Gerda Henkel, Wenner-Gren, ANR, EFEO, Quai Branly, IFAO)

  OFFRES POSTDOC / EMPLOI :
  - archeojob.canalblog.com  ← agrégateur français postdoc archéo
  - Place de l'emploi public (RSS archéologie)
  - emploi-territorial.fr RSS
  - jobs.ac.uk (archaeology postdoc + research)
  - THE Jobs (Times Higher Education)
  - BAJR (British Archaeology Jobs)
  - EAA (European Association of Archaeologists)
  - DAI (Deutsches Archäologisches Institut)
  - AcademicPositions.eu (scraping HTML)
  - USAJobs API (séries 0193 archéologie + 0190 anthropologie)
  - Hypothèses.org (blogs labos SHS)
  - Société Préhistorique Française

Toutes les annonces vont dans discovered.json et s'affichent
immédiatement dans l'onglet Offres Postdoc (badge ⚠ auto).

Sortie :
  - discovered.json  : nouvelles annonces (affichage immédiat)
  - grants.json      : deadlines mises à jour si détectées
"""

import json, re, sys, datetime, hashlib, requests, feedparser
from dateutil import parser as dateparser

TODAY = datetime.date.today()

HEADERS = {
    "User-Agent": "GrantMatch-Bot/3.0 (academic funding aggregator; "
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
    "CDD chercheur","contrat de recherche",
]

KW_DISCIPLINE = [
    "archéologie","archaeology","archeology",
    "anthropologie","anthropology","bioarchaeology","bioarchéologie",
    "préhistoire","prehistory","prehistoric","paléolithique",
    "neolithic","neolithique","archéométrie","archaeometry",
    "fouille","excavation","SHS","humanities","sciences humaines",
    "ancient history","histoire ancienne","patrimoine","heritage",
    "numismatique","numismatics","épigraphie","epigraphy",
    "archéothanatologie","ostéologie","osteoarchaeology",
    "paléogénomique","ancient dna","ancient genome",
    "micromorphologie","zooarchaeology","archéozoologie",
]

KW_EXCLUDE = [
    "colloque","call for papers","cfp",
    "master","licence","bachelor","thèse doctorale",
    "emploi saisonnier","vacataire","animateur",
    "technicien de fouille","aide-archéologue",
]

KW_MCF = [
    "maître de conférences","MCF","lecturer","assistant professor",
    "associate professor","professeur des universités",
    "permanent position","tenure","poste permanent","poste titulaire",
    "chargé de recherche","directeur de recherche",
]

# ─────────────────────────────────────────────
# PROFIL — zones et spécialités (pour tag auto)
# ─────────────────────────────────────────────

ZONE_KEYWORDS = {
    "france":       ["france","français","bretagne","normandie","provence","alsace","occitanie"],
    "europe_occ":   ["britain","england","spain","espagne","italie","italy","allemagne","germany",
                     "belgique","belgium","portugal","ireland","pays-bas","netherlands"],
    "europe_orient":["balkans","grèce","greece","turquie","turkey","roumanie","pologne","bulgarie"],
    "med":          ["méditerranée","mediterranean","proche-orient","near east","levant","syrie",
                     "liban","israel","jordan","egypt","égypte","grèce antique","rome","romain"],
    "afrique_nord": ["egypt","égypte","maroc","algérie","tunisie","libye","nubie","nubia","soudan"],
    "afrique_ss":   ["africa","afrique","kenya","tanzanie","éthiopie","mali","sénégal","nigeria",
                     "sub-saharan","sahara"],
    "asie_sud":     ["india","inde","pakistan","sri lanka","bangladesh","nepal","south asia"],
    "asie_se":      ["southeast asia","asie du sud-est","laos","thaïlande","thailand","vietnam",
                     "cambodge","cambodia","indonesia","birmanie","myanmar","philippines","borneo"],
    "asie_e":       ["china","chine","japan","japon","korea","corée","east asia","mongolie"],
    "asie_c":       ["central asia","asie centrale","kazakhstan","ouzbékistan","afghanistan","iran","perse"],
    "ameriques":    ["america","amérique","mexique","mexico","peru","pérou","chili","brésil",
                     "brazil","maya","inca","aztec"],
    "oceanie":      ["australia","australie","pacific","pacifique","oceania","new zealand","polynesia"],
}

SPEC_KEYWORDS = {
    "prehist":      ["préhistoire","prehistory","prehistoric","paleolithic","paléolithique",
                     "neolithic","neolithique","mesolithic","mésolithique","stone age"],
    "protohistoire":["protohistoire","âge du bronze","bronze age","âge du fer","iron age",
                     "hallstatt","la tène"],
    "antiquite":    ["antiquité","antiquity","roman","romain","grec","greek","classique",
                     "classical","byzantine","byzantin"],
    "bioarch":      ["bioarchaeology","bioarchéologie","ostéologie","osteoarchaeology",
                     "squelette","skeletal","ossement"],
    "archeo_mort":  ["funéraire","funerary","sépulture","burial","mort","death","nécropole",
                     "necropolis","tombeau","tomb"],
    "paleogenom":   ["paleogenomics","paléogénomique","ancient dna","adn ancien","ancient genome",
                     "ancient population","archéogénétique"],
    "medieval":     ["médiéval","medieval","middle ages","moyen âge","carolingien","viking"],
    "anthropo":     ["anthropologie","anthropology","ethnoarchaeology","ethnoarchéologie",
                     "social anthropology","cultural anthropology"],
    "archeo_env":   ["environnement","environment","palynologie","palynology","geoarchaeology",
                     "géoarchéologie","landscape","paysage","quaternaire"],
    "archeo_sci":   ["archéométrie","archaeometry","isotope","spectro","datation","radiocarbone",
                     "radiocarbon","xrf","provenance"],
    "numismat":     ["numismatique","numismatic","monnaie","coin","épigraphie","epigraphy",
                     "inscription","manuscrit"],
    "histoire_art": ["histoire de l art","art history","iconographie","iconography","peinture",
                     "sculpture","céramique","pottery"],
}

def detect_zones(text):
    t = text.lower()
    return [z for z, kws in ZONE_KEYWORDS.items() if any(k in t for k in kws)]

def detect_specs(text):
    t = text.lower()
    return [s for s, kws in SPEC_KEYWORDS.items() if any(k in t for k in kws)]

def detect_country(source_label, text):
    t = (source_label + " " + text).lower()
    if any(k in t for k in ["jobs.ac.uk","bajr","timeshighereducation","uk ","u.k.","united kingdom","britain"]):
        return "uk", "🇬🇧"
    if any(k in t for k in ["dainst","deutsches","german","allemagne"]):
        return "de", "🇩🇪"
    if any(k in t for k in ["usajobs","united states","usa ","u.s."]):
        return "intl", "🇺🇸"
    if any(k in t for k in ["calenda","préhistoire française","archeojob","place de l emploi","france"]):
        return "france", "🇫🇷"
    if any(k in t for k in ["eaa","european association"]):
        return "other_eu", "🇪🇺"
    return "", "🌍"

# ─────────────────────────────────────────────
# FLUX RSS — BOURSES
# ─────────────────────────────────────────────

CALENDA_FEEDS = [
    {"url":"https://calenda.org/feed.php?type=47",    "label":"Calenda – Bourses & emploi",       "job":True},
    {"url":"https://calenda.org/feed.php?cat=293",    "label":"Calenda – Archéologie",            "job":True},
    {"url":"https://calenda.org/feed.php?cat=303",    "label":"Calenda – Préhistoire & Antiquité","job":True},
    {"url":"https://calenda.org/feed.php?cat=213",    "label":"Calenda – Anthropologie",          "job":True},
    {"url":"https://calenda.org/feed.php?cat=289",    "label":"Calenda – Vie de la recherche",    "job":True},
    {"url":"https://calenda.org/feed.php?cat=353",    "label":"Calenda – Asie du Sud-Est",        "job":True},
    {"url":"https://calenda.org/feed.php?cat=355",    "label":"Calenda – Méditerranée",           "job":True},
    {"url":"https://calenda.org/feed.php?cat=331",    "label":"Calenda – Afrique subsaharienne",  "job":True},
    {"url":"https://calenda.org/feed.php?cat=329",    "label":"Calenda – Afrique du Nord",        "job":True},
    {"url":"https://calenda.org/feed.php?cat=351",    "label":"Calenda – Monde indien",           "job":True},
    {"url":"https://calenda.org/feed.php?cat=336",    "label":"Calenda – Amériques",              "job":True},
    {"url":"https://calenda.org/feed.php?cat=345",    "label":"Calenda – Proche-Orient",          "job":True},
]

# ─────────────────────────────────────────────
# FLUX RSS — OFFRES EMPLOI/POSTDOC
# ─────────────────────────────────────────────

JOB_FEEDS = [
    # ── France ──
    {
        "url":     "https://archeojob.canalblog.com/rss.xml",
        "label":   "ArcheoJob – Emplois archéologie France",
        "country": "france", "flag": "🇫🇷",
    },
    {
        "url":     "https://place-emploi-public.gouv.fr/rss?keyword=arch%C3%A9ologie&type=emploi",
        "label":   "Place de l'emploi public – Archéologie",
        "country": "france", "flag": "🇫🇷",
    },
    {
        "url":     "https://www.emploi-territorial.fr/offres-emploi/archeologie/rss",
        "label":   "Emploi Territorial – Archéologie",
        "country": "france", "flag": "🇫🇷",
    },
    {
        "url":     "https://www.prehistoire.org/rss.php",
        "label":   "Société Préhistorique Française – Emplois",
        "country": "france", "flag": "🇫🇷",
    },
    {
        "url":     "https://f.hypotheses.org/feeds/disciplines/archeologie",
        "label":   "Hypothèses – Blogs archéologie (labos SHS)",
        "country": "france", "flag": "🇫🇷",
    },
    # ── UK ──
    {
        "url":     "https://www.jobs.ac.uk/search/rss?keywords=archaeology&jobType%5B%5D=postdoctoral-research",
        "label":   "jobs.ac.uk – Archaeology postdoc",
        "country": "uk", "flag": "🇬🇧",
    },
    {
        "url":     "https://www.jobs.ac.uk/search/rss?keywords=archaeology+research+fellow",
        "label":   "jobs.ac.uk – Archaeology research fellow",
        "country": "uk", "flag": "🇬🇧",
    },
    {
        "url":     "https://www.timeshighereducation.com/unijobs/jobsrss/?keywords=archaeology+postdoc",
        "label":   "THE Jobs – Archaeology postdoc",
        "country": "uk", "flag": "🇬🇧",
    },
    {
        "url":     "https://www.bajr.org/feed/",
        "label":   "BAJR – British Archaeology Jobs",
        "country": "uk", "flag": "🇬🇧",
    },
    # ── Europe ──
    {
        "url":     "https://www.e-a-a.org/feed/",
        "label":   "EAA – European Association of Archaeologists",
        "country": "other_eu", "flag": "🇪🇺",
    },
    {
        "url":     "https://www.dainst.org/en/feed",
        "label":   "DAI – Deutsches Archäologisches Institut",
        "country": "de", "flag": "🇩🇪",
    },
]

# ─────────────────────────────────────────────
# PAGES FONDATIONS
# ─────────────────────────────────────────────

FOUNDATION_PAGES = [
    {"id":"gerda",  "label":"Gerda Henkel Stiftung",
     "url":"https://www.gerda-henkel-stiftung.de/en/researchscholarships",
     "deadline_patterns":[
         r"(\d{1,2}[\s\.](?:january|february|march|april|may|june|july|august|september|october|november|december)[\s\.]\d{4})",
         r"deadline[:\s]+([^\n<]{5,40})",
     ]},
    {"id":"wenner", "label":"Wenner-Gren Foundation",
     "url":"https://www.wennergren.org/grants/post-phd-research-grants",
     "deadline_patterns":[r"(May 1|November 1)[,\s]+\d{4}"]},
    {"id":"anr",    "label":"ANR – Appels en cours",
     "url":"https://anr.fr/fr/appels-ouverts/appels-en-cours/",
     "deadline_patterns":[
         r"Access.ERC[^\n]*(\d{2}/\d{2}/\d{4})",
         r"JCJC[^\n]*(\d{2}/\d{2}/\d{4})",
     ]},
    {"id":"efeo",   "label":"EFEO – Contrats postdoctoraux",
     "url":"https://www.efeo.fr/base.php?code=563",
     "deadline_patterns":[r"(\d{1,2}\s+\w+\s+\d{4})",r"date limite[:\s]+([^\n<]{5,40})"]},
    {"id":"mqb",    "label":"Musée du Quai Branly",
     "url":"https://www.quaibranly.fr/fr/recherche-scientifique/activites/bourses-et-prix-de-these/bourses-de-recherches-doctorales-et-contrats-postdoctoraux",
     "deadline_patterns":[r"(\d{1,2}\s+\w+\s+\d{4})",r"avant le\s+([^\n<]{5,30})"]},
    {"id":"fyssen", "label":"Fondation Fyssen",
     "url":"https://www.fondationfyssen.fr/en/study-grants/",
     "deadline_patterns":[r"deadline[:\s]+([^\n<]{5,40})"]},
    {"id":"ifao",   "label":"IFAO – Bourses postdoctorales",
     "url":"https://www.ifao.egnet.net/recherche/recherche-soutien/bourses-doctorales-et-post-doctorales/",
     "deadline_patterns":[r"(\d{1,2}\s+\w+\s+\d{4})",r"date limite[:\s]+([^\n<]{5,40})"]},
]

# ─────────────────────────────────────────────
# USAJOBS API
# ─────────────────────────────────────────────

USAJOBS_API = "https://data.usajobs.gov/api/search"
USAJOBS_QUERIES = [
    {"Keyword":"archaeologist","JobCategoryCode":"0193"},
    {"Keyword":"anthropologist","JobCategoryCode":"0190"},
]

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def make_id(text):
    return hashlib.md5(text.encode()).hexdigest()[:10]

def is_relevant(title, summary="", is_job_feed=False):
    text = (title + " " + summary).lower()
    for kw in KW_EXCLUDE:
        if kw.lower() in text:
            return False
    has_disc = any(kw.lower() in text for kw in KW_DISCIPLINE)
    if not has_disc:
        return False
    if is_job_feed:
        # Pour les flux emploi, on accepte aussi les postes permanents
        has_grant = any(kw.lower() in text for kw in KW_GRANT)
        has_mcf   = any(kw.lower() in text for kw in KW_MCF)
        return has_grant or has_mcf
    return any(kw.lower() in text for kw in KW_GRANT)

def extract_deadline(text):
    patterns = [
        r"deadline[:\s]+(\d{1,2}[\/.\s]\w+[\/.\s]\d{2,4})",
        r"closing date[:\s]+(\d{1,2}[\/.\s]\w+[\/.\s]\d{2,4})",
        r"date limite[:\s]+(\d{1,2}[\/.\s]\w+[\/.\s]\d{2,4})",
        r"avant le[:\s]+(\d{1,2}[\/.\s]\w+[\/.\s]\d{2,4})",
        r"close[sd]?\s+(?:on|by)?[:\s]+(\d{1,2}[\/.\s]\w+[\/.\s]\d{2,4})",
        r"(\d{1,2}\s+(?:january|february|march|april|may|june|july|august"
        r"|september|october|november|december)\s+\d{4})",
        r"(\d{1,2}\s+(?:janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[uû]t"
        r"|septembre|octobre|novembre|d[ée]cembre)\s+\d{4})",
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
                                   "associate professor","chargé de recherche"]):
        return "mcf"
    return "postdoc"

def load_existing():
    try:
        with open("discovered.json","r",encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"last_updated":TODAY.isoformat(),"items":[]}

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

def scrape_rss(feed_config, existing_ids, is_job_feed=False):
    results = []
    try:
        feed = feedparser.parse(feed_config["url"])
        for entry in feed.entries:
            title     = entry.get("title","")
            summary   = entry.get("summary","") or entry.get("description","")
            link      = entry.get("link","")
            published = entry.get("published","") or entry.get("updated","")

            if not is_relevant(title, summary, is_job_feed=is_job_feed):
                continue

            pub_date = None
            if published:
                try:
                    pub_date = dateparser.parse(published).date().isoformat()
                except Exception:
                    pass

            if pub_date:
                try:
                    if (TODAY - datetime.date.fromisoformat(pub_date)).days > 90:
                        continue
                except Exception:
                    pass

            item_id = make_id(link or title)
            if item_id in existing_ids:
                continue

            text = title + " " + summary
            country = feed_config.get("country","")
            flag    = feed_config.get("flag","🌍")
            if not country:
                country, flag = detect_country(feed_config["label"], text)

            results.append({
                "id":        item_id,
                "type":      guess_type(title, summary),
                "source":    feed_config["label"],
                "country":   country,
                "flag":      flag,
                "title":     title.strip(),
                "url":       link,
                "published": pub_date,
                "deadline":  extract_deadline(text),
                "summary":   summary[:400].strip() if summary else "",
                "zones":     detect_zones(text),
                "specs":     detect_specs(text),
                "auto":      True,
                "validated": True,   # affichage immédiat
                "active":    True,
            })
    except Exception as e:
        print(f"  ⚠ {feed_config['label']}: {e}", file=sys.stderr)
    return results


def scrape_academic_positions(existing_ids):
    results = []
    url = "https://academicpositions.eu/jobs/archaeology"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        clean = re.sub(r"<[^>]+"," ", r.text)
        clean = re.sub(r"\s+"," ", clean)
        blocks = re.findall(
            r"((?:postdoc|fellowship|research\s+fellow|research\s+associate)[^.]{20,300})",
            clean, re.IGNORECASE
        )
        for block in blocks[:20]:
            if not any(kw.lower() in block.lower() for kw in KW_DISCIPLINE):
                continue
            item_id = make_id(block[:60])
            if item_id in existing_ids:
                continue
            text = block
            results.append({
                "id": item_id, "type":"postdoc",
                "source":"AcademicPositions.eu", "country":"other_eu", "flag":"🇪🇺",
                "title": block[:120].strip(), "url": url,
                "published": TODAY.isoformat(),
                "deadline":  extract_deadline(text),
                "summary":   block[:400].strip(),
                "zones":     detect_zones(text),
                "specs":     detect_specs(text),
                "auto":True, "validated":True, "active":True,
            })
    except Exception as e:
        print(f"  ⚠ AcademicPositions: {e}", file=sys.stderr)
    return results


def scrape_usajobs(existing_ids):
    results, seen = [], set()
    for query in USAJOBS_QUERIES:
        try:
            r = requests.get(USAJOBS_API,
                headers={**HEADERS,"Host":"data.usajobs.gov",
                         "User-Agent":"grantmatch@archaeology-shs.org"},
                params={"ResultsPerPage":25,"Fields":"Min",**query}, timeout=15)
            if r.status_code != 200:
                continue
            for job in r.json().get("SearchResult",{}).get("SearchResultItems",[]):
                mv         = job.get("MatchedObjectDescriptor",{})
                title      = mv.get("PositionTitle","")
                link       = mv.get("PositionURI","")
                org        = mv.get("OrganizationName","")
                close_date = mv.get("ApplicationCloseDate","")
                open_date  = mv.get("PublicationStartDate","")
                locations  = mv.get("PositionLocationDisplay","")
                sal        = (mv.get("PositionRemuneration") or [{}])[0]
                salary_str = f"{sal.get('MinimumRange','')}–{sal.get('MaximumRange','')} {sal.get('CurrencyCode','USD')}/an" if sal.get("MinimumRange") else ""

                item_id = make_id(link or title)
                if item_id in existing_ids or item_id in seen:
                    continue
                seen.add(item_id)

                deadline = None
                if close_date:
                    try:
                        d = dateparser.parse(close_date)
                        if d and d.date() > TODAY:
                            deadline = d.date().isoformat()
                    except Exception:
                        pass

                text = title + " " + org + " " + locations
                results.append({
                    "id": item_id, "type":"postdoc",
                    "source":"USAJobs.gov", "country":"intl", "flag":"🇺🇸",
                    "title": title, "lab": f"{org} – {locations}",
                    "url": link, "salary": salary_str,
                    "published": open_date[:10] if open_date else TODAY.isoformat(),
                    "deadline": deadline,
                    "summary": f"{org} | {locations}",
                    "zones": detect_zones(text),
                    "specs": detect_specs(text),
                    "auto":True, "validated":True, "active":True,
                })
        except Exception as e:
            print(f"  ⚠ USAJobs ({query}): {e}", file=sys.stderr)
    return results


def scrape_foundation_page(cfg):
    result = {"id":cfg["id"],"label":cfg["label"],"url":cfg["url"],
              "deadline_found":None,"raw_snippet":None}
    try:
        r = requests.get(cfg["url"], headers=HEADERS, timeout=15)
        r.raise_for_status()
        clean = re.sub(r"<[^>]+"," ", r.text)
        clean = re.sub(r"\s+"," ", clean)
        for pattern in cfg.get("deadline_patterns",[]):
            m = re.search(pattern, clean, re.IGNORECASE)
            if m:
                result["raw_snippet"] = m.group(0)[:100]
                date_str = m.group(1) if m.lastindex else m.group(0)
                try:
                    d = dateparser.parse(date_str, dayfirst=True)
                    if d and d.date() > TODAY:
                        result["deadline_found"] = d.date().isoformat()
                        break
                except Exception:
                    pass
    except Exception as e:
        print(f"  ⚠ {cfg['label']}: {e}", file=sys.stderr)
    return result


def update_known_deadlines(grants_data, foundation_results):
    changed = False
    id_map = {r["id"]:r for r in foundation_results}
    for grant in grants_data["grants"]:
        gid = grant["id"].split("_")[0]
        if gid in id_map:
            found = id_map[gid].get("deadline_found")
            if found and found != grant.get("deadline"):
                print(f"  📅 {grant['id']}: {grant.get('deadline')} → {found}")
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
    print(f"🔍 GrantMatch Scraper v3 — {TODAY}")
    print("=" * 55)

    discovered   = load_existing()
    grants_data  = load_grants()
    existing_ids = {item["id"] for item in discovered.get("items",[])}
    new_items    = []

    # 1. Calenda (bourses + emploi)
    print("\n📡 Calenda…")
    for feed in CALENDA_FEEDS:
        items = scrape_rss(feed, existing_ids, is_job_feed=True)
        for i in items:
            new_items.append(i); existing_ids.add(i["id"])
        if items: print(f"  ✓ {feed['label']}: {len(items)} nouvelles")

    # 2. Flux RSS emploi
    print("\n📡 Flux RSS emploi/postdoc…")
    for feed in JOB_FEEDS:
        print(f"  → {feed['label']}")
        items = scrape_rss(feed, existing_ids, is_job_feed=True)
        for i in items:
            new_items.append(i); existing_ids.add(i["id"])
        if items: print(f"     ✓ {len(items)} nouvelles")

    # 3. AcademicPositions.eu
    print("\n🌐 AcademicPositions.eu…")
    items = scrape_academic_positions(existing_ids)
    for i in items:
        new_items.append(i); existing_ids.add(i["id"])
    print(f"  {len(items)} nouvelles")

    # 4. USAJobs
    print("\n🇺🇸 USAJobs API…")
    items = scrape_usajobs(existing_ids)
    for i in items:
        new_items.append(i); existing_ids.add(i["id"])
    print(f"  {len(items)} nouvelles")

    # 5. Fondations
    print("\n🏛  Fondations (deadlines)…")
    foundation_results = []
    for page in FOUNDATION_PAGES:
        print(f"  → {page['label']}")
        r = scrape_foundation_page(page)
        foundation_results.append(r)
        if r["deadline_found"]: print(f"     📅 {r['deadline_found']}")

    # 6. Mise à jour grants.json
    print("\n⚙️  grants.json…")
    grants_changed = update_known_deadlines(grants_data, foundation_results)
    if grants_changed:
        save_grants(grants_data)
        print("  ✅ mis à jour")
    else:
        print("  — aucun changement")

    # 7. Purge 90j + sauvegarde
    cutoff = (TODAY - datetime.timedelta(days=90)).isoformat()
    old = [i for i in discovered.get("items",[])
           if i.get("published","9999") >= cutoff or not i.get("published")]
    discovered.update({
        "last_updated": TODAY.isoformat(),
        "last_checked": TODAY.isoformat(),
        "new_this_run": len(new_items),
        "items": old + new_items,
    })
    save_discovered(discovered)

    n_postdoc = sum(1 for i in new_items if i.get("type")=="postdoc")
    n_mcf     = sum(1 for i in new_items if i.get("type")=="mcf")
    print(f"\n{'='*55}")
    print(f"✅ {len(new_items)} nouvelles annonces "
          f"({n_postdoc} postdoc, {n_mcf} MCF/permanent)")
    if grants_changed:
        print("⚠️  Deadlines modifiées dans grants.json → PR créée")

if __name__ == "__main__":
    main()
