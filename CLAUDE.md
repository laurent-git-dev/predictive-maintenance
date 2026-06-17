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
│   ├── common/             ← partagé : metrics, registry, reporting, env, profiling,
│   │                          stage (run_layer : compréhension + rapports + mise en base)
│   ├── processing/         ← OUTILS MUTUALISÉS : anonymization, transformation,
│   │                          imputation, outliers, pipeline (apply_processing)
│   ├── database/           ← engine (PostgreSQL, ensure_schema) + loader (to_sql par schéma)
│   ├── sources/            ← 1 package/source (runner MINCE : load_bronze/to_silver/numeric)
│   │   ├── registry.py     ← SOURCE_SPECS (load_bronze, to_silver, numeric, table)
│   │   ├── incidents/ telemetry/ machines/
│   └── analyses/           ← analyses inter-sources (joins, plots, runner)
├── scripts/
│   ├── run_pipeline.py     ← ORCHESTRATEUR : tout, toutes sources, Bronze+Silver (commande unique)
│   └── run_{incidents,telemetry,machines,cross_source}.py ← par source/analyse
└── notebooks/
    └── pipeline.ipynb      ← notebook UNIQUE, toutes les phases (non DVC)
```

> **Architecture médaillon** : pour chaque source, **Bronze** (données brutes ;
> `operator_name`/`operator_badge` pseudonymisés dès le Bronze) puis **Silver**
> (traitement : feature engineering, encodage, imputation, outliers). Chaque couche
> produit la **même compréhension per-feature** (synthèse adaptée au type + boxplot/
> distribution) et une **table** dans son schéma PostgreSQL (`bronze.*`, `silver.*`).
> **Gold** viendra ensuite (même mécanique). Tout est **mutualisé** dans `src/common/`
> (`stage.run_layer`, `profiling`) ; les runners de source sont **minces** (`load_bronze`,
> `to_silver`, `BRONZE_NUMERIC`/`SILVER_NUMERIC`). Orchestrateur : `src/orchestrator.py`.

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

### Base de données (PostgreSQL / Docker)

```bash
docker compose up -d        # démarre la base (port 5432, identifiants dans .env)
docker compose ps           # statut / santé
docker compose stop         # arrête (les données persistent dans le volume pgdata)
```
Chaque source produit **deux tables** : `bronze.<table>` (brut, opérateurs
pseudonymisés) et `silver.<table>` (après traitement), où `<table>` ∈
{`incidents`, `telemetry`, `maintenance`}. Les schémas `bronze`/`silver` sont créés
au besoin (`CREATE SCHEMA IF NOT EXISTS`) et les tables **rechargées entièrement**
(`to_sql` replace) à chaque run → idempotent.

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

**Modèle « per-feature » (uniforme pour toutes les sources)** : pour chaque
**feature numérique**, un boxplot par machine et une distribution (histogramme +
densité/KDE). La synthèse par colonne, **adaptée au type** (uniques, % manquants ;
numérique : min/Q1/médiane/Q3/max + plage + écart-type + skew + outliers IQR ;
datetime : plage temporelle ; catégoriel : mode ; booléen : % True), est dans
`dataset_report.md`.

```
artifacts/ingestions/<source>/<run>/{bronze,silver}/
```

| Fichier (par couche) | Description |
|---|---|
| `<source>.csv` | Dataset de la couche (gitignoré ; versionnable via DVC) |
| `1.<i>_box_<feature>.png` | Boxplot d'une feature numérique par machine |
| `2.<i>_dist_<feature>.png` | Distribution (histogramme + densité/KDE) d'une feature |
| `run_report.md` | Rapport technique de la couche (métriques + manquants/colonne) |
| `dataset_report.md` | Rapport partageable : profil **per-feature** (synthèse + graphes) |

> Features numériques par source et couche : **incidents** — Bronze = `severity` ;
> Silver = `severity`, `n_active_signals`, `confidence_index`. **telemetry** — les 5
> paramètres (Bronze = Silver). **machines** — `duration_hours` (Bronze = Silver).
> La synthèse couvre **toutes** les colonnes.

Le registre `runs_registry.json` est mis à jour automatiquement (lignes Bronze/Silver
+ statut de mise en base par schéma).

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

Registre dédié : `artifacts/ingestions/telemetry/runs_registry.json`.
Tables : `bronze.telemetry`, `silver.telemetry`.

---

## Source 3 — Machines / maintenance (SQL)

Troisième source : **dump PostgreSQL** (`data/raw/machines.sql`) avec deux tables :
- **`machine`** — référentiel (modèle, ligne, atelier, criticité, capacités, date
  de mise en service) ;
- **`maintenance`** — événements (`machine_code`, `maintenance_at`, `maintenance_type`
  *proactive/reactive*, `action_type`, `component`, `description`,
  `related_incident_id`, `duration_hours`).

**Accès** : le dump est chargé dans une base **SQLite locale** via **SQLAlchemy ORM**
(modèles `Machine` / `Maintenance` dans `src/sources/machines/models.py` = schéma
documenté), puis lu en DataFrames avec `pandas.read_sql`. La syntaxe PostgreSQL
non portable (`NOW()`, `ON CONFLICT`) est neutralisée au chargement. À la lecture,
`machine_code` est renommé `machine_id` (cohérence inter-sources / jointures).

```bash
uv run python scripts/run_machines.py
```

Artefacts dans `artifacts/ingestions/machines/AAAAMMJJHHMM/{bronze,silver}/`, modèle
**per-feature** (`1.1_box_duration_hours.png`, `2.1_dist_duration_hours.png`,
`run_report.md`, `dataset_report.md`). Silver = encodage (`maintenance_type`,
`component`) + traitement des outliers (IQR) sur `duration_hours`.

Registre dédié : `artifacts/ingestions/machines/runs_registry.json`.
Tables : `bronze.maintenance`, `silver.maintenance`.

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
   - `runner.py` (**mince**) exposant :
     - `SOURCE_NAME`, `TABLE` (nom de table PostgreSQL) ;
     - `BRONZE_NUMERIC` / `SILVER_NUMERIC` (features numériques à grapher par couche) ;
     - `load_bronze(input_path=None) -> df` : brut typé (+ `pseudonymise_operators`
       si PII opérateurs, via `src.processing.anonymization`) ;
     - `to_silver(bronze_df) -> df` : feature engineering + `apply_processing(...)`
       (`src.processing` : encodage / imputation / outliers **déjà existants**).
3. **Aucun traitement en Bronze** (sauf pseudonymisation PII opérateurs). Tout le
   reste (encodage texte→valeur, imputation, outliers, features dérivées) est en
   **Silver** via `to_silver`, en réutilisant `src.processing`.
4. **Enregistrer la source dans `src/sources/registry.py`** (`SOURCE_SPECS`) via
   `_spec(<nom>_runner)` : `name`, `load_bronze`, `to_silver`, `bronze_numeric`,
   `silver_numeric`, `table`, `machine_col`. → l'orchestrateur (`run_pipeline`) la
   prend automatiquement en charge (Bronze + Silver + mise en base par schéma).
5. **`scripts/run_<nom>.py`** : wrapper CLI minimal (`run_source_by_name("<nom>")`,
   fixe le backend `Agg`, option `--no-db`).
6. **Notebook** : ajouter une sous-section dans `notebooks/pipeline.ipynb` (couches
   **Bronze** puis **Silver** : `load_bronze()` puis `to_silver()`, profilées via
   `show_per_feature`).
7. **Documenter** dans `CLAUDE.md` et `README.md`.

> Rappel : **chaque couche produit `run_report.md` ET `dataset_report.md`** (per-feature).
> La mise en base utilise `to_sql` replace par schéma (`bronze.*` / `silver.*`,
> idempotent) et est ignorée si la DB est éteinte.
