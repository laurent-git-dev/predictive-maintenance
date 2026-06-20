# CLAUDE.md — Projet : Maintenance Prédictive Industrielle

> Ce fichier est lu automatiquement par **Claude Code** à chaque session.
> Il définit le contexte, les conventions et les commandes du projet.

---

## Contexte métier

Projet de **détection précoce de pannes** dans un environnement industriel.
Phase actuelle : **Étape 2 — Données : ingestion & gouvernance**.

L'objectif immédiat est de :
1. Ingérer le fichier CSV de relevés d'incidents
2. Anonymiser les données opérateurs
3. Produire les graphes d'analyse exploratoire (EDA)
4. Versionner le dataset produit et enregistrer le run dans le registre

---

## Stack technique

| Couche | Outil |
|---|---|
| Langage | Python 3.12 |
| Environnement & dépendances | `uv` (`.venv/`, `uv.lock`) |
| Versioning code | Git |
| Versioning données | DVC (remote local) |
| Manipulation données | pandas |
| Visualisation | matplotlib |
| SQL / ORM | SQLAlchemy (SQLite pour l'ingestion du dump, PostgreSQL pour la mise en base) |
| Base de données | PostgreSQL (Docker, `docker-compose.yml`) |
| Stats | scipy |
| Qualité code | ruff, black |

---

## Structure du projet

```
predictive_maintenance/
├── CLAUDE.md               ← ce fichier
├── README.md
├── .env.example
├── .gitignore
├── pyproject.toml          ← dépendances + config (uv, ruff, black)
├── uv.lock                 ← versions verrouillées (uv)
├── .python-version         ← Python 3.12
├── .dvc/                   ← config DVC (ne pas modifier manuellement)
├── docker-compose.yml      ← service PostgreSQL (mise en base)
├── data/raw/               ← sources d'entrée (2 CSV + 1 SQL) ; jamais modifiées
├── artifacts/
│   ├── ingestions/<source>/<run>/{bronze,silver}/ ← graphes + rapports par couche
│   └── analyses/cross_source/
├── src/
│   ├── config.py           ← chemins, schémas, réglages DB, BRONZE/SILVER_SCHEMA
│   ├── orchestrator.py     ← run_pipeline : Bronze→Silver × chaque source + cross-source
│   ├── common/             ← partagé : metrics, registry, reporting, env,
│   │                          profiling (compréhension per-feature + graphes + status),
│   │                          quality (critères OK/NOK par feature), processing_summary
│   │                          (résumé Bronze→Silver), overview (stub global par couche),
│   │                          stage (run_layer : compréhension + rapports + mise en base)
│   ├── processing/         ← OUTILS MUTUALISÉS : anonymization, dedup, transformation
│   │                          (encode), imputation, outliers, normalization, pipeline
│   │                          (apply_processing : dedup→encode→impute→outliers→normalize)
│   ├── database/           ← engine (PostgreSQL, ensure_schema) + loader (to_sql par schéma)
│   ├── sources/            ← 1 package/source (runner MINCE : load_bronze/to_silver + hooks)
│   │   ├── registry.py     ← SOURCE_SPECS (déclaratif : load_bronze/to_silver/numeric/table
│   │   │                      + hooks count/keyword/heatmap/timeseries/overview/processing)
│   │   ├── incidents/ telemetry/ machines/   (+ overview.py par source ; machines :
│   │   │                      runner=maintenance + referential_runner=dimension machine)
│   └── analyses/           ← analyses inter-sources (joins, plots, runner)
├── scripts/
│   ├── run_pipeline.py     ← ORCHESTRATEUR : tout, toutes sources, Bronze+Silver (commande unique)
│   └── run_{incidents,telemetry,machines,cross_source}.py ← par source/analyse
└── notebooks/
    └── pipeline.ipynb      ← notebook UNIQUE, organisé PAR COUCHE (non DVC)
```

> **Architecture médaillon** : pour chaque source, **Bronze** (données brutes ;
> `operator_name`/`operator_badge` pseudonymisés dès le Bronze) puis **Silver**
> (traitement : feature engineering, dédoublonnage, encodage texte→value, imputation,
> outliers, normalisation). `to_silver` renvoie `(df, report)` ; le mapping texte→value
> est tracé dans `…/silver/text_encodings.json`. Chaque couche produit la **même
> compréhension per-feature** (synthèse adaptée au type + **status OK/NOK** par feature
> + graphes) et une **table** dans son schéma PostgreSQL (`bronze.*`, `silver.*`).
> **Gold** viendra ensuite (même mécanique). Tout est **mutualisé** dans `src/common/`
> (`stage.run_layer`, `profiling`, `quality`) ; les runners de source sont **minces** :
> ils déclarent `load_bronze`, `to_silver`, `BRONZE_NUMERIC`/`SILVER_NUMERIC` et des
> **hooks optionnels** (voir « Ajouter une source »). Orchestrateur : `src/orchestrator.py`.
>
> **4 sources Bronze** dans `SOURCE_SPECS` : `incidents`, `telemetry`, `machine`
> (dimension/référentiel ; titres notebook *Machines/machine*) et `machines` (faits de
> maintenance). **En Silver il n'y a que 3 sources** : `incidents`, `telemetry`,
> `maintenance`. La dimension `machine` est **Bronze-only** (`BRONZE_ONLY = True`,
> contrôles de cohérence en Bronze) : ses attributs sont **fusionnés en tête** de
> `to_silver` de maintenance (merge-first, star schema) — donc **pas de `silver.machine`**.
>
> **Notebook organisé par couche, titres numérotés & repliables** (niveaux : `##` phase
> → `###` source → `####` sous-section → `#####` feature) : `## 1. Bronze (raw)` →
> `## 2. Processing Bronze → Silver` → `## 3. Silver (treated)` → `## 4. Database` →
> `## 5. Cross-source`. En **Bronze** et **Silver**, chaque source d'une couche se décline
> en sous-sections **« … - Per feature »**, **« … - Overview »** et (Bronze) **« … - Inline
> analysis »** (graphes exploratoires **propres au notebook**) ; chaque couche se termine par
> **« <Couche> - Global overview »**. En **Processing**, le traitement est documenté
> **par feature** (`##### 2.x.i <feature>`). Bronze a 4 sources ; **Processing et Silver n'en
> ont que 3** (`incidents`, `telemetry`, `maintenance` — la dimension `machine` est fusionnée).

---

## Commandes fréquentes

> 🖥️ **Shell de travail : PowerShell dans VS Code (Windows 11).**
> Les commandes doivent être fournies en **syntaxe PowerShell**, pas bash. Exemples :
> - Variable : `$RUN = "202606161452"` (et non `RUN=...`), utilisée via `"...$RUN..."`.
> - Variable d'environnement le temps d'une commande :
>   `$env:UV_SYSTEM_CERTS = "true"` ou `$env:ANONYMIZATION_SALT = "..."`.
> - Enchaînement de commandes : `;` (pas `&&`).
> - Copie de fichier : `Copy-Item .env.example .env` (plutôt que `cp`).

### Environnement (uv)

Le projet est géré avec **uv** (lockfile `uv.lock`, dépendances dans `pyproject.toml`).

```bash
# Installer / synchroniser l'environnement (.venv créé automatiquement)
uv sync

# Ajouter une dépendance
uv add <paquet>

# Réseau d'entreprise avec interception TLS : ajouter --native-tls
# ou définir une fois UV_SYSTEM_CERTS=true
uv add --native-tls <paquet>
```

> ⚠️ Sur ce poste, le proxy d'entreprise impose `--native-tls` (ou
> `UV_SYSTEM_CERTS=true`) pour toute opération réseau de uv.

### Pipeline complète (orchestrateur — recommandé)

Enchaîne, **pour chaque source**, les deux couches médaillon **Bronze → Silver**
(compréhension per-feature + rapports + mise en base par schéma à chaque couche),
puis l'analyse inter-sources. **Relançable à l'identique** dès qu'une donnée change
dans `data/raw/`.

```bash
# Prérequis : cp .env.example .env ; renseigner ANONYMIZATION_SALT (+ POSTGRES_* au besoin)
docker compose up -d                       # démarre PostgreSQL (mise en base)
uv run python scripts/run_pipeline.py      # tout, toutes les sources (Bronze + Silver)
uv run python scripts/run_pipeline.py --no-db   # sans l'étape base
```

> Si PostgreSQL n'est pas démarré, l'étape de mise en base est **ignorée avec un
> warning** (Bronze/Silver : compréhension + rapports tournent quand même).

### Lancer une source isolée

```bash
uv run python scripts/run_incidents.py            # Bronze + Silver incidents
uv run python scripts/run_telemetry.py
uv run python scripts/run_machines.py
uv run python scripts/run_cross_source.py
uv run python scripts/run_incidents.py --no-db    # sans l'étape base
```

Chaque run crée `artifacts/ingestions/<source>/AAAAMMJJHHMM/{bronze,silver}/`
(graphes per-feature, `run_report.md`, `dataset_report.md`, `<source>.csv`) et met à
jour le `runs_registry.json` de la source (lignes Bronze/Silver + statut base).

> `<source>` est le **nom de dossier** renvoyé par `config.source_artifacts_dirname` :
> identique au nom de source pour `incidents`/`telemetry`, mais désambiguïsé pour les deux
> sources `machines.sql` → `machines_machine` (dimension) et `machines_maintenance` (faits).

### Base de données (PostgreSQL / Docker)

```bash
docker compose up -d        # démarre la base (port 5432, identifiants dans .env)
docker compose ps           # statut / santé
docker compose stop         # arrête (les données persistent dans le volume pgdata)
```
**Bronze** : 4 tables — `bronze.{incidents, telemetry, machine, maintenance}` (brut,
opérateurs pseudonymisés). **Silver** : 3 tables — `silver.{incidents, telemetry,
maintenance}` (la dimension `machine` est Bronze-only → **pas de `silver.machine`**).
`silver.maintenance` est **enrichie** des attributs de la dimension `machine` (criticité,
ligne, atelier, modèle, capacités, date de mise en service + `machine_age_years`). Les
schémas `bronze`/`silver` sont créés au besoin (`CREATE SCHEMA IF NOT EXISTS`) et les
tables **rechargées entièrement** (`to_sql` replace) à chaque run → idempotent.

### DVC — versioning des données

```powershell
# Versionner les datasets produits par un run (remote local : pas de réseau)
$RUN = "AAAAMMJJHHMM"
uv run dvc add "artifacts/ingestions/incidents/$RUN/bronze/incidents.csv" `
               "artifacts/ingestions/incidents/$RUN/silver/incidents.csv"
git add "artifacts/ingestions/incidents/$RUN/bronze/incidents.csv.dvc" `
        "artifacts/ingestions/incidents/$RUN/silver/incidents.csv.dvc"
git commit -m "feat(data): add bronze/silver datasets run $RUN"
uv run dvc push
```

### Git — convention de commits

Utiliser le format **Conventional Commits** :

```
feat(ingestion): ajout anonymisation opérateurs
fix(viz): correction axe temporel distribution hebdomadaire
docs: mise à jour README étape 2
refactor(src): découplage loader / anonymizer
```

---

## Conventions de code

- **Langue des éléments générés** : **anglais obligatoire**. Tout contenu produit
  (code, noms d'identifiants, commentaires, docstrings, messages de log,
  notebooks, libellés de graphes, rapports `run_report.md`, clés JSON du registre,
  messages de commit, etc.) doit être rédigé en **anglais**.
  > Exception : ce fichier `CLAUDE.md` et les échanges de discussion restent en français.
- **Encodage fichiers** : UTF-8
- **Séparateur CSV** : virgule (`,`)
- **Format dates** : ISO 8601 (`YYYY-MM-DD`)
- **Nommage variables** : snake_case
- **Nommage constantes** : SCREAMING_SNAKE_CASE
- **Docstrings** : format NumPy/Google
- **Logging** : utiliser `logging` (pas de `print` en production)

---

## Schéma des données source

Fichier : `data/raw/incidents.csv`

| Colonne | Type attendu | Description |
|---|---|---|
| `incident_id` | str | Identifiant unique de l'incident |
| `date` | date (YYYY-MM-DD) | Date de l'incident |
| `time` | time (HH:MM:SS) | Heure de l'incident |
| `operator_name` | str | **PII — à anonymiser** |
| `machine_id` | str | Identifiant de la machine |
| `severity` | int/str | Niveau de gravité |
| `operator_badge` | str | **PII — à anonymiser** |
| `comment` | str | **PII potentielle — à pseudonymiser** |
| `shift` | str | Poste de travail (matin / après-midi / nuit) |
| `type_surchauffe` | bool/int | Signal de type surchauffe |
| `type_baisse_pression` | bool/int | Signal baisse de pression |
| `type_vibration` | bool/int | Signal vibration |
| `type_bruit_mecanique` | bool/int | Signal bruit mécanique |
| `type_surconsommation` | bool/int | Signal surconsommation |
| `type_blocage_mecanique` | bool/int | Signal blocage mécanique |
| `type_alarme_capteur` | bool/int | Signal alarme capteur |
| `type_arret_urgence` | bool/int | Signal arrêt d'urgence |
| `type_defaut_qualite` | bool/int | Signal défaut qualité |

**Définition — signaux** :
Les **signaux** désignent l'ensemble des colonnes **préfixées par `type_`**
(`type_surchauffe`, `type_baisse_pression`, …). Chaque signal est une valeur
binaire (0/1) indiquant si ce type d'anomalie a été relevé pour l'incident.
Cette définition fait foi dans tout le code (`SIGNAL_COLUMNS` dans `src/config.py`)
et dans les analyses.

**Colonnes PII (données personnelles identifiables)** :
- `operator_name` → pseudonymisé par HMAC-SHA256 tronqué (**dès le Bronze**)
- `operator_badge` → pseudonymisé par HMAC-SHA256 tronqué (**dès le Bronze**)
- `comment` → conservé **brut** en Bronze ; en Silver, un drapeau `comment_pii_flag`
  signale la présence de texte libre (revue manuelle recommandée)

> Exception médaillon : les opérateurs (`operator_name`, `operator_badge`) sont
> pseudonymisés **dès le Bronze** (PII jamais persistée en clair). Tous les autres
> traitements n'ont lieu qu'en Silver.

---

## Règles de sécurité données

- Ne jamais committer `data/raw/` dans Git (géré via `.gitignore` + DVC)
- Ne jamais committer de fichiers contenant des données nominatives
- Les clés de mapping (hash → nom réel) ne doivent pas être stockées dans ce dépôt

---

## Artefacts attendus (par couche médaillon)

À chaque run, **chaque couche** (`bronze/`, `silver/`) produit les mêmes artefacts.

**Modèle « per-feature » (uniforme pour toutes les sources)** : pour **chaque colonne**,
un **status OK/NOK** (badge vert/rouge accolé au titre, cf. « Status & qualité ») et une
**synthèse adaptée au type** :
- **numérique continu** : count/unique/missing ; plage min→max + Q1/médiane/Q3 ;
  mean/std/skew ; **tableau outliers** (méthodes IQR k=1.5 **et** z-score k=3, avec bornes
  et plages des valeurs atypiques) ;
- **ordinal** (ex. `severity`) : synthèse allégée (plage seule) ;
- **booléen** (signaux `type_*`, flags 0/1) : pas de stats numériques, % par valeur 0/1 ;
- **datetime** : plage temporelle ; pour une série horaire par machine (ex. `timestamp`),
  **tableau QC par machine** (doublons + heures manquantes) ;
- **catégoriel** : valeur la plus fréquente (ou plage si heure `HH:MM`).

Graphes (préfixe = type, `<i>` = index dans la liste) :

```
artifacts/ingestions/<source>/<run>/{bronze,silver}/
```

| Fichier (par couche) | Description |
|---|---|
| `<source>.csv` | Dataset de la couche (gitignoré ; versionnable via DVC) |
| `1.<i>_box_<feature>.png` | Boxplot d'une feature numérique par machine (si `machine_col` présent) |
| `2.<i>_dist_<feature>.png` | Distribution (histogramme + densité/KDE) d'une feature numérique |
| `3.<i>_count_<feature>.png` | Comptage par catégorie (hook `COUNT_FEATURES`) ; horizontal si > 20 modalités |
| `4.<i>_kw_<feature>.png` | Détail par mot-clé dans du texte libre (hook `KEYWORD_BARS`) |
| `5.<i>_heat_<row>_<col>.png` | Heatmap crosstab normalisée par ligne (hook `HEATMAPS`) |
| `6.<i>_ts_<feature>.png` | Série temporelle par machine (hook `TIMESERIES`) |
| `run_report.md` | Rapport technique de la couche (métriques + manquants/colonne) |
| `dataset_report.md` | Rapport partageable : profil **per-feature** (synthèse + status + graphes) |
| `text_encodings.json` | (Silver) traçabilité des encodages texte→value appliqués (`value → code`) |

> Features numériques par source et couche : **incidents** — Bronze = ∅ (`severity` n'a
> qu'un graphe de comptage) ; Silver = `n_active_signals`, `confidence_index`.
> **telemetry** — les 5 paramètres (Bronze = Silver). **machines** (maintenance) —
> `duration_hours`. **machine** (dimension) — `max_daily_capacity`,
> `max_hourly_capacity_pieces` (pas de boxplot par machine : 1 ligne/machine). La synthèse
> couvre **toutes** les colonnes.

Le registre `runs_registry.json` est mis à jour automatiquement (lignes Bronze/Silver
+ statut de mise en base par schéma).

---

## Status & qualité par feature (OK/NOK)

Chaque feature peut déclarer des **critères de qualité** ; le profilage affiche un **status
OK (vert) / NOK (rouge)** à côté du titre, et, si NOK, une ligne listant les critères
échoués. Tout est centralisé dans **`src/common/quality.py`** :

- `FEATURE_CHECKS: dict[str, list[Check]]` — critères **par nom de feature** (s'appliquent
  à toutes les sources/couches). Un `Check` = un libellé + un prédicat sur
  `(profile, series, df)` (le DataFrame permet les contrôles **inter-colonnes**).
- `SOURCE_FEATURE_CHECKS: dict[(source, feature), list[Check]]` — critères **scopés à une
  source** (s'ajoutent aux globaux). Ex. : `machine_id` est une **clé primaire** (pas de
  doublon) **uniquement** dans la dimension `machine`, alors qu'il se répète légitimement
  ailleurs.

Critères réutilisables : `NO_MISSING`, `NO_DUPLICATES`, `VALID_DATE_FORMAT`,
`VALID_TIME_FORMAT`, `UNIQUE_PER_MACHINE` / `NO_MISSING_HOURS` (séries horaires),
`IN_CRITICALITY_DOMAIN`, `STRICTLY_POSITIVE`, `NOT_IN_FUTURE`,
`SAME_DISTINCT_AS_OPERATOR_NAME`. Réglages d'affichage associés : `ORDINAL_FEATURES`
(synthèse allégée) et `HOURLY_PER_MACHINE_FEATURES` (tableau QC).

> Le status reflète les données **de la couche** : une même feature peut être NOK en
> Bronze (ex. valeurs manquantes) puis OK en Silver (après imputation).

---

## Source 2 — Télémétrie machines

Deuxième source de données : relevés de **télémétrie** horaires par machine.
**Pas de PII → pas d'anonymisation.**

Fichier : `data/raw/telemetry.csv`

| Colonne | Type | Description |
|---|---|---|
| `machine_id` | str | Identifiant de la machine |
| `timestamp` | datetime | Horodatage du relevé |
| `temperature_c` | float | Température (°C) |
| `pressure_bar` | float | Pression (bar) |
| `voltage_mean_v` | float | Tension moyenne (V) |
| `rotation_mean_rpm` | float | Vitesse de rotation moyenne (rpm) |
| `pieces_produced` | int | Pièces produites |

Source `src/sources/telemetry/`, lancée par `scripts/run_telemetry.py` :

```bash
uv run python scripts/run_telemetry.py
```

Artefacts produits dans `artifacts/ingestions/telemetry/AAAAMMJJHHMM/{bronze,silver}/`,
modèle **per-feature** (voir « Artefacts attendus »). Pas de PII : Bronze = `load_telemetry`,
Silver = imputation (médiane) + traitement des outliers (IQR) sur les 5 paramètres.
Hooks déclarés : `TIMESERIES` (production journalière/hebdomadaire par machine sur
`pieces_produced`) et `OVERVIEW` (`src/sources/telemetry/overview.py` : évolution des 4
mesures physiques dans le temps). `timestamp` porte les critères `UNIQUE_PER_MACHINE` +
`NO_MISSING_HOURS` (tableau QC par machine).

Registre dédié : `artifacts/ingestions/telemetry/runs_registry.json`.
Tables : `bronze.telemetry`, `silver.telemetry`.

---

## Source 3 — Machines / maintenance (SQL) — **2 sources** : fait + dimension

Troisième fichier d'entrée : **dump PostgreSQL** (`data/raw/machines.sql`) avec deux
tables qui donnent **deux sources médaillon** :
- **`maintenance`** — table de **faits** : événements (`machine_code`, `maintenance_at`,
  `maintenance_type` *proactive/reactive*, `action_type`, `component`, `description`,
  `related_incident_id`, `duration_hours`). Source `machines`.
- **`machine`** — **dimension/référentiel** (modèle, ligne, atelier, criticité, capacités,
  date de mise en service ; 1 ligne/machine). Source `machine`.

**Accès** : le dump est chargé dans une base **SQLite locale** via **SQLAlchemy ORM**
(modèles `Machine` / `Maintenance` dans `src/sources/machines/models.py` = schéma
documenté), puis lu en DataFrames avec `pandas.read_sql`. La syntaxe PostgreSQL
non portable (`NOW()`, `ON CONFLICT`) est neutralisée au chargement. À la lecture,
`machine_code` est renommé `machine_id` (cohérence inter-sources / jointures).

```bash
uv run python scripts/run_machines.py   # lance la source maintenance (la dimension passe par run_pipeline)
```

**Source `machines` (maintenance, faits ; notebook : *Machines/maintenance*)** — runner `src/sources/machines/runner.py` :
`to_silver` fusionne **d'abord** la dimension `machine` (merge-first, jointure `machine_id`
= tous les attributs, dont `commissioning_date`), puis dérive les features (calendaires sur
`maintenance_at` + `machine_age_years`) et encode (`maintenance_type`, `action_type`,
`component`, `criticality`, `production_line`, `location`, `model`). `duration_hours` est
laissée **brute**. Numérique : `duration_hours`. Tables : `bronze.maintenance`,
`silver.maintenance` (enrichie). C'est la **seule** source Silver issue de `machines.sql`.

**Source `machine` (dimension ; notebook : *Machines/machine*)** — runner `src/sources/machines/referential_runner.py` :
**Bronze-only** (`BRONZE_ONLY = True`) — pas de `silver.machine`. Le **Bronze vérifie la
cohérence** du référentiel (status : `machine_id` PK = pas de vide + **pas de doublon**
*(critère scopé à cette source)* ; `criticality` ∈ {LOW, MEDIUM, HIGH} ; capacités > 0 ;
`commissioning_date` non future). C'est une dimension (1 ligne/machine) → **pas de boxplot
par machine** (`MACHINE_COL = ""`) : distributions des capacités + comptages (`criticality`,
`model`, `production_line`, `location`) ; ses encodages sont appliqués lors de la fusion dans
`silver.maintenance`. Table : `bronze.machine`.

Registre dédié : `artifacts/ingestions/{machines_maintenance,machines_machine}/runs_registry.json`
(les deux sources `machines.sql` écrivent dans des dossiers **désambiguïsés** : `machines`
→ `machines_maintenance`, `machine` → `machines_machine` ; mapping dans
`config.source_artifacts_dirname`, dérivé de `SOURCE_DISPLAY_NAMES`).

---

## Analyses inter-sources

Une **analyse inter-sources** combine plusieurs sources (elle n'ingère rien de
nouveau). Elle vit dans **`src/analyses/`** (et non `src/sources/`), réutilise les
**loaders des sources**, et joint sur **`machine_id`** (et `incident_id` pour le
lien maintenance↔incident).

```bash
uv run python scripts/run_cross_source.py
```

Artefacts dans `artifacts/analyses/cross_source/AAAAMMJJHHMM/` :

| Fichier | Description |
|---|---|
| `machine_profile.csv` | Table jointe : 1 ligne/machine (incidents + télémétrie + maintenance + criticité) |
| `1_incidents_vs_maintenance.png` | Incidents vs maintenances par machine |
| `2_reactive_vs_severity.png` | Maintenance reactive ↔ sévérité de l'incident |
| `3_telemetry_vs_incidents.png` | Température moyenne vs incidents par machine |
| `run_report.md` | Rapport technique (corrélations clés) |
| `dataset_report.md` | Rapport de synthèse partageable (métier) compilant les graphes |

Registre dédié : `artifacts/analyses/cross_source/runs_registry.json`.
Exploration interactive : `notebooks/pipeline.ipynb`.

> Pour ajouter une analyse : un module de jointure/plots dans `src/analyses/`,
> branché dans son `runner.py` ; même logique d'artefacts que les sources.

---

## Ajouter une nouvelle source de données

> ⚙️ **Instruction permanente** : lorsqu'une nouvelle source est demandée,
> réaliser **directement l'ensemble** des tâches ci-dessous (sans procéder étape
> par étape), en réutilisant `src/common/` et en suivant le modèle des sources
> existantes.

Checklist pour une source `<nom>` (le **runner reste mince** : toute la mécanique —
compréhension per-feature, rapports, mise en base — est mutualisée dans
`src/common/stage.run_layer` et `src/common/profiling`) :

1. **Schéma & chemins** dans `src/config.py` (colonnes attendues, chemin du fichier
   d'entrée, dossier d'artefacts/registre).
2. **`src/sources/<nom>/`** :
   - `loader.py` : `load_<nom>()` (lecture, validation, typage **brut** — pas de
     traitement) ;
   - `runner.py` (**mince**) exposant **au minimum** :
     - `SOURCE_NAME`, `TABLE` (nom de table PostgreSQL) ;
     - `BRONZE_NUMERIC` / `SILVER_NUMERIC` (features numériques à grapher par couche) ;
     - `load_bronze(input_path=None) -> df` : brut typé (+ `pseudonymise_operators`
       si PII opérateurs, via `src.processing.anonymization`) ;
     - `to_silver(bronze_df) -> (df, report)` : feature engineering + `apply_processing(...)`
       (`src.processing` : dédoublonnage / encodage / imputation / outliers / normalisation
       **déjà existants**). `report["encode"]` alimente `text_encodings.json` ;
   - **hooks optionnels** (lus par `getattr` dans `_spec`, donc facultatifs) :
     `COUNT_FEATURES`/`COUNT_LABEL` (barres de comptage), `KEYWORD_BARS`
     `(feature, mots-clés, titre)`, `HEATMAPS` `(row, col)`, `TIMESERIES`
     `(value, time, titre, freq)`, `OVERVIEW` (fonction `plots(df, out)->list[Path]`,
     typiquement dans `overview.py`), `FEATURE_PLOTS` (`dict {feature: fn(df, out)->list[Path]}` :
     graphe(s) **rattaché(s) à une feature** dans la compréhension per-feature, ex. cohérence des
     capacités sous `max_hourly_capacity_pieces`), `MACHINE_COL` (override ; `""` pour désactiver le
     boxplot par machine sur une dimension), `PROCESSING` (la `ProcessingConfig` :
     `dedup`/`encode`/`impute`/`outliers`/`normalize`), `BRONZE_ONLY` (`True` = source
     Bronze-only, sans table Silver — ex. dimension fusionnée ailleurs).
3. **Aucun traitement en Bronze** (sauf pseudonymisation PII opérateurs). Tout le
   reste (encodage texte→valeur, imputation, outliers, features dérivées) est en
   **Silver** via `to_silver`, en réutilisant `src.processing`.
4. **Enregistrer la source dans `src/sources/registry.py`** (`SOURCE_SPECS`) via
   `_spec(<nom>_runner)`. → l'orchestrateur (`run_pipeline`) la prend automatiquement
   en charge (Bronze + Silver + mise en base par schéma).
5. **Qualité (optionnel mais recommandé)** : déclarer les critères de status dans
   `src/common/quality.py` — `FEATURE_CHECKS` (par nom de feature) ou
   `SOURCE_FEATURE_CHECKS` (scopé `(source, feature)`), en réutilisant les `Check`
   existants ou en ajoutant un prédicat `(profile, series, df) -> bool`.
6. **`scripts/run_<nom>.py`** : wrapper CLI minimal (`run_source_by_name("<nom>")`,
   fixe le backend `Agg`, option `--no-db`).
7. **Notebook** (organisé **par couche**) : ajouter la source dans **les trois phases**
   `## 1. Bronze` / `## 2. Processing` / `## 3. Silver` (markdown `### <Source> - …` +
   cellule `show_per_feature_spec(SPECS["<nom>"], …)` / `show_processing(...)`).
8. **Documenter** dans `CLAUDE.md` et `README.md`.

> Rappel : **chaque couche produit `run_report.md` ET `dataset_report.md`** (per-feature).
> La mise en base utilise `to_sql` replace par schéma (`bronze.*` / `silver.*`,
> idempotent) et est ignorée si la DB est éteinte.
