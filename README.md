# GrantMatch — Archéologie & SHS

Outil interactif de recherche de financements postdoctoraux pour les chercheurs en archéologie et SHS.  
Bourses institutionnelles + offres postdoc ponctuelles, avec mise à jour automatique hebdomadaire.

---

## Structure du projet

```
grantmatch-site/
├── index.html                        ← Interface web (ne pas modifier)
├── grants.json                       ← Bourses institutionnelles (éditez les deadlines ici)
├── jobs.json                         ← Offres postdoc de laboratoires (ajoutez/supprimez ici)
├── discovered.json                   ← Nouvelles annonces trouvées automatiquement (auto-généré)
├── scripts/
│   ├── scraper.py                    ← Script de veille (exécuté par GitHub Actions)
│   └── requirements.txt              ← Dépendances Python
└── .github/
    └── workflows/
        └── update-grants.yml         ← Déclencheur GitHub Actions (toutes les semaines)
```

---

## ÉTAPE 1 — Mise en ligne sur GitHub Pages

### 1.1 Créer le repository

1. Connectez-vous sur [github.com](https://github.com)
2. Cliquez **"New repository"** (bouton vert, coin supérieur droit)
3. Nommez-le `grantmatch`
4. Cochez **"Public"** (obligatoire pour GitHub Pages gratuit)
5. **Ne cochez pas** "Add a README" (vous allez uploader les vôtres)
6. Cliquez **"Create repository"**

### 1.2 Uploader les fichiers

Une fois sur la page du repo vide :

1. Cliquez **"uploading an existing file"**
2. Glissez-déposez **tous les fichiers et dossiers** du ZIP :
   - `index.html`
   - `grants.json`
   - `jobs.json`
   - `scripts/requirements.txt`
   - `scripts/scraper.py`
   - `.github/workflows/update-grants.yml`
   
   > ⚠️ **Important** : GitHub ne crée pas les sous-dossiers automatiquement via drag & drop.  
   > Pour les fichiers dans des sous-dossiers (`scripts/` et `.github/`), utilisez plutôt  
   > l'interface en ligne de commande (voir section 1.3) ou créez les fichiers un par un via "Add file".

3. Message de commit : `Initial commit — GrantMatch`
4. Cliquez **"Commit changes"**

### 1.3 Alternative : upload via terminal Git (recommandé)

Si vous avez Git installé sur votre ordinateur :

```bash
# Décompressez le ZIP, puis :
cd grantmatch-site
git init
git add .
git commit -m "Initial commit — GrantMatch"
git branch -M main
git remote add origin https://github.com/VOTRE-NOM/grantmatch.git
git push -u origin main
```

### 1.4 Activer GitHub Pages

1. Dans votre repo, allez dans **Settings** (onglet en haut)
2. Menu gauche → **Pages**
3. Sous "Source" → **"Deploy from a branch"**
4. Branch → **main** | Folder → **/ (root)**
5. Cliquez **Save**

Votre site sera accessible dans 1-2 minutes à :  
**`https://VOTRE-NOM-GITHUB.github.io/grantmatch/`**

---

## ÉTAPE 2 — Activer la mise à jour automatique

Le script de veille tourne automatiquement chaque lundi à 7h (UTC) via **GitHub Actions**.  
Il nécessite une seule permission à activer :

### 2.1 Autoriser GitHub Actions à créer des Pull Requests

1. Dans votre repo → **Settings**
2. Menu gauche → **Actions** → **General**
3. Faites défiler jusqu'à **"Workflow permissions"**
4. Sélectionnez **"Read and write permissions"**
5. Cochez **"Allow GitHub Actions to create and approve pull requests"**
6. Cliquez **Save**

C'est tout. Le script se déclenchera automatiquement chaque lundi.

### 2.2 Déclencher manuellement (pour tester)

1. Dans votre repo → onglet **Actions**
2. Dans la liste à gauche → cliquez **"Mise à jour automatique des financements"**
3. Bouton **"Run workflow"** → **"Run workflow"**
4. Attendez ~1-2 minutes, rafraîchissez la page

### 2.3 Ce qui se passe chaque semaine

Le script :
1. **Lit les flux RSS** de Calenda (archéologie, bourses, zones géo), ArchPostgrad
2. **Vérifie les pages** des fondations (Gerda Henkel, Wenner-Gren, ANR, EFEO, Quai Branly)
3. **Compare** avec les deadlines stockées dans `grants.json`
4. Si des changements sont détectés → **crée une Pull Request** dans l'onglet "Pull requests"
5. Vous recevez une notification par email GitHub

### 2.4 Valider une Pull Request

Quand vous recevez une notification :

1. Allez dans l'onglet **"Pull requests"** de votre repo
2. Ouvrez la PR créée par le bot
3. Consultez l'onglet **"Files changed"** pour voir ce qui a changé
4. Si les changements semblent corrects → cliquez **"Merge pull request"**
5. Le site se met à jour automatiquement dans la minute

> ⚠️ **Toujours vérifier avant de merger** — le script peut se tromper sur une date.  
> En cas de doute, vérifiez directement sur le site de la fondation.

---

## ÉTAPE 3 — Ajouter des offres postdoc manuellement

### Option A : via l'interface du site (recommandée)

1. Ouvrez votre site → onglet **"Offres Postdoc"**
2. Remplissez le formulaire en bas de page
3. Cliquez **"Générer le bloc JSON"**
4. Copiez le bloc généré
5. Sur GitHub → `jobs.json` → crayon ✏️ → collez le bloc **avant le dernier `]`**
6. Cliquez **"Commit changes"**

### Option B : éditer jobs.json directement

Chaque offre suit cette structure :

```json
{
  "id": "job_unique_123",
  "title": "Postdoc en archéologie du Bronze Age",
  "lab": "UMR 5138 ArAr — Université Lyon 2",
  "country": "france",
  "flag": "🇫🇷",
  "deadline": "2026-09-01",
  "duration": "24 mois",
  "salary": "~2 700 €/mois brut",
  "url": "https://lien-vers-annonce.fr",
  "contact": "recrutement@labo.fr",
  "description": "Description courte du poste et du projet.",
  "source": "Manuel",
  "added": "2026-05-29",
  "active": true
}
```

Pour **désactiver** une offre expirée sans la supprimer : mettez `"active": false`.
Vous pouvez aussi préciser des critères de filtrage :

- `"age": ["lt1","1to2",... ]` — ancienneté de thèse acceptée
- `"stat": ["assoc","funded","indep","mcf"]` — statut requis
- `"specs": ["bioarch","prehist",...]` — spécialités ciblées
### Valeurs de `country`

`france` · `de` · `uk` · `nl` · `ch` · `at` · `other_eu` · `intl`

---

## Mettre à jour une deadline dans grants.json

Si vous constatez qu'une deadline a changé :

1. Sur GitHub → `grants.json` → crayon ✏️
2. Trouvez le bloc correspondant (cherchez `"id": "msca"` par exemple)
3. Modifiez le champ `"deadline": "2027-09-10"`
4. Mettez à jour `"last_updated"` dans `"meta"` en haut du fichier
5. Commit

---

## Ajouter un nouveau financement institutionnel dans grants.json

Copiez un bloc existant et adaptez. Les règles d'éligibilité disponibles :

| Règle | Description |
|---|---|
| `"age": ["lt1","1to2",...]` | Ancienneté de thèse acceptée |
| `"stat": ["funded","mcf"]` | Statut institutionnel requis |
| `"mono_required": true` | Thèse publiée en monographie requise |
| `"zones_any": ["asie_se",...]` | Au moins une de ces zones doit être sélectionnée |
| `"links_required": ["l_jp"]` | Lien institutionnel requis |
| `"exclude_if_had": ["h_msca"]` | Masqué si déjà perçu |
| `"cty_exclude": ["uk"]` | Exclu si thèse dans ce pays |

**Codes zones :** `france` · `europe_occ` · `europe_orient` · `med` · `afrique_nord` · `afrique_ss` · `asie_sud` · `asie_se` · `asie_e` · `asie_c` · `ameriques` · `oceanie`

**Codes spécialités :** `prehist` · `protohistoire` · `antiquite` · `bioarch` · `archeo_mort` · `paleogenom` · `medieval` · `anthropo` · `archeo_env` · `archeo_sci` · `numismat` · `histoire_art` · `autre_shs`

---

## Sources surveillées par le scraper

| Source | Type | Fréquence |
|---|---|---|
| Calenda — Archéologie (cat=293) | RSS | Hebdomadaire |
| Calenda — Bourses & emploi (type=47) | RSS | Hebdomadaire |
| Calenda — Préhistoire & Antiquité | RSS | Hebdomadaire |
| Calenda — Anthropologie | RSS | Hebdomadaire |
| Calenda — Asie du Sud-Est, Méditerranée, Afrique, Amériques... | RSS | Hebdomadaire |
| ArchPostgrad (WordPress) | RSS | Hebdomadaire |
| Sites fondations (Gerda Henkel, Wenner-Gren, ANR, EFEO, Quai Branly) | HTML | Hebdomadaire |

Pour ajouter une source RSS, éditez `scripts/scraper.py` → liste `CALENDA_FEEDS` ou `OTHER_FEEDS`.

---

## Sources surveillées par le scraper v2

| Source | Type | Pays | Scrapable ? |
|---|---|---|---|
| Calenda (archéologie, bourses, zones géo) | RSS | FR | ✅ Automatique |
| jobs.ac.uk (archaeology postdoc) | RSS | UK | ✅ Automatique |
| THE Jobs (Times Higher Education) | RSS | UK | ✅ Automatique |
| BAJR (British Archaeology Jobs) | RSS | UK | ✅ Automatique |
| EAA (European Association of Archaeologists) | RSS | EU | ✅ Automatique |
| DAI (Deutsches Archäologisches Institut) | RSS | DE | ✅ Automatique |
| AcademicPositions.eu | HTML | EU | ✅ Automatique |
| USAJobs.gov (séries 0193+0190) | API REST | US | ✅ Automatique |
| Société Préhistorique Française | RSS | FR | ✅ Automatique |
| Gerda Henkel, Wenner-Gren, ANR, EFEO, Quai Branly, IFAO | HTML | — | ✅ Deadlines |
| emploi.cnrs.fr, Galaxie/CNU, IRD, FNRS | JS dynamique | FR/BE | ❌ Liens directs |
| Chronicle Vitae, JobiJoba | Login/agrégateur | — | ❌ Impossible |

## Postes MCF et permanents (nouvelle question dans le wizard)

Si vous répondez "Oui, qualifié(e)" à la question sur la qualification MCF, des liens directs s'affichent vers :

- **Galaxie** — postes MCF sections 20 (Anthropologie), 21 (Histoire), 22 (Histoire & civilisations) — `galaxie.enseignementsup-recherche.gouv.fr`
- **Emploi CNRS** — concours chargé de recherche — `emploi.cnrs.fr`
- **Concours IRD** — `ird.fr/les-concours-ird`
- **FNRS (Belgique)** — postes de chercheur qualifié — `fnrs.be`
- **jobs.ac.uk** — Lecturer in Archaeology (UK)
- **AcademicPositions.eu** — postes permanents Europe
- **DAI** — postes permanents Allemagne
- **Academic Jobs Wiki** Archaeology 2025-26
