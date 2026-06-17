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
│   ├── ingestions/<source>/← runs par source (graphes, rapports, processed.csv)
│   └── analyses/cross_source/
├── src/
│   ├── config.py           ← chemins, schémas, réglages DB
│   ├── orchestrator.py     ← run_pipeline : 4 étapes × chaque source + cross-source
│   ├── pipeline.py         ← run_all (sources, ancien point d'entrée conservé)
│   ├── common/             ← partagé : metrics, registry, reporting, env
│   ├── processing/         ← OUTILS MUTUALISÉS : anonymization, transformation,
│   │                          imputation, outliers, pipeline (apply_processing)
│   ├── database/           ← engine (PostgreSQL) + loader (to_sql)
│   ├── sources/            ← ingestion + compréhension (1 package/source)
│   │   ├── registry.py     ← SOURCE_SPECS (déclaratif : ingestion/compréhension/
│   │   │                      traitement/table par source)
│   │   ├── incidents/ telemetry/ machines/
│   └── analyses/           ← analyses inter-sources (joins, plots, runner)
├── scripts/
│   ├── run_pipeline.py     ← ORCHESTRATEUR : tout, toutes sources (commande unique)
│   ├── run_all.py          ← sources seules (compréhension)
│   └── run_{incidents,telemetry,machines,cross_source}.py ← par source/analyse
└── notebooks/
    └── pipeline.ipynb      ← notebook UNIQUE, toutes les phases (non DVC)
```

> **Principe d'organisation** : **par source** sous `src/sources/<nom>/` (ingestion +
> compréhension). Les **traitements** (`src/processing/`) et la **mise en base**
> (`src/database/`) sont **mutualisés** et pilotés par `SOURCE_SPECS`
> (`src/sources/registry.py`). L'**orchestrateur** (`src/orchestrator.py`) enchaîne les
> 4 étapes pour chaque source. Code partagé dans `src/common/`.

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

Enchaîne, **pour chaque source du répertoire d'entrée**, les 4 étapes :
**ingestion → compréhension → traitement → mise en base**, puis l'analyse inter-sources.
**Relançable à l'identique** dès qu'une donnée change dans `data/raw/`.

```bash
# Prérequis : cp .env.example .env ; renseigner ANONYMIZATION_SALT (+ POSTGRES_* au besoin)
docker compose up -d                       # démarre PostgreSQL (mise en base)
uv run python scripts/run_pipeline.py      # tout, toutes les sources
uv run python scripts/run_pipeline.py --no-db   # sans l'étape base
```

> Si PostgreSQL n'est pas démarré, l'étape de mise en base est **ignorée avec un
> warning** (ingestion/compréhension/traitement tournent quand même).

### Lancer une source isolée (ou la compréhension seule)

```bash
uv run python scripts/run_incidents.py --input data/raw/incidents.csv
uv run python scripts/run_telemetry.py --input data/raw/telemetry.csv
uv run python scripts/run_machines.py  --input data/raw/machines.sql
uv run python scripts/run_cross_source.py
uv run python scripts/run_all.py           # les 3 sources (compréhension)
```

Chaque run crée `artifacts/ingestions/<source>/AAAAMMJJHHMM/` (graphes, `run_report.md`,
`dataset_report.md`, `processed.csv`) et met à jour le `runs_registry.json` de la source.

### Base de données (PostgreSQL / Docker)

```bash
docker compose up -d        # démarre la base (port 5432, identifiants dans .env)
docker compose ps           # statut / santé
docker compose stop         # arrête (les données persistent dans le volume pgdata)
```
Les tables `incidents`, `telemetry`, `maintenance` sont **rechargées entièrement**
(`to_sql` replace) à chaque `run_pipeline` → idempotent.

### DVC — versioning des données

```powershell
# Versionner le dataset anonymisé produit par un run (remote local : pas de réseau)
$RUN = "AAAAMMJJHHMM"
uv run dvc add "artifacts/ingestions/incidents/$RUN/incidents_anonymized.csv"
git add "artifacts/ingestions/incidents/$RUN/incidents_anonymized.csv.dvc"
git commit -m "feat(data): add anonymised dataset run $RUN"
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
- `operator_name` → remplacé par un hash SHA-256 tronqué (pseudonymisation)
- `operator_badge` → remplacé par un identifiant opaque `OP_XXXX`
- `comment` → conservé mais signalé (analyse manuelle recommandée)

---

## Règles de sécurité données

- Ne jamais committer `data/raw/` dans Git (géré via `.gitignore` + DVC)
- Ne jamais committer de fichiers contenant des données nominatives
- Les clés de mapping (hash → nom réel) ne doivent pas être stockées dans ce dépôt

---

## Artefacts attendus (étape 2)

À chaque run d'ingestion, les fichiers suivants doivent être produits :

Les graphes sont nommés avec un **préfixe numéroté** pour rester dans l'ordre.

| Fichier | Description |
|---|---|
| `incidents_anonymized.csv` | Dataset nettoyé et anonymisé |
| `1.1_dist_incidents_day.png` | Distribution des incidents par jour |
| `1.2_dist_incidents_week.png` | Distribution par semaine |
| `1.3_dist_incidents_shift.png` | Distribution par shift |
| `2.1_hist_incidents_machine.png` | Histogramme des incidents par machine |
| `2.2_hist_incidents_operator.png` | Histogramme des incidents par opérateur |
| `2.3_hist_incidents_signal.png` | Histogramme des incidents par signal |
| `2.4_hist_incidents_confidence.png` | Histogramme par indice de confiance |
| `3.1_corr_severity_signals.png` | Corrélation sévérité / signaux |
| `3.2_corr_severity_comment.png` | Corrélation sévérité / catégorie de commentaire (χ² + V de Cramér) |
| `run_report.md` | Rapport technique du run (métriques) |
| `dataset_report.md` | Rapport de synthèse partageable (métier) compilant les graphes |

Le registre `runs_registry.json` est mis à jour automatiquement.

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

Pipeline parallèle (`src/telemetry/`, lancé par `scripts/run_telemetry.py`) :

```bash
uv run python scripts/run_telemetry.py --input data/raw/telemetry.csv
```

Artefacts produits dans `artifacts/ingestions/telemetry/AAAAMMJJHHMM/` :

| Fichier | Description |
|---|---|
| `1.1_box_temperature_c.png` | Boxplot température par machine |
| `1.2_box_pressure_bar.png` | Boxplot pression par machine |
| `1.3_box_voltage_mean_v.png` | Boxplot tension par machine |
| `1.4_box_rotation_mean_rpm.png` | Boxplot rotation par machine |
| `1.5_box_pieces_produced.png` | Boxplot pièces produites par machine |
| `run_report.md` | Rapport technique (métriques + stats des paramètres) |
| `dataset_report.md` | Rapport de synthèse partageable (métier) compilant les graphes |

Registre dédié : `artifacts/ingestions/telemetry/runs_registry.json`.

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
uv run python scripts/run_machines.py --input data/raw/machines.sql
```

Artefacts dans `artifacts/ingestions/machines/AAAAMMJJHHMM/` :

| Fichier | Description |
|---|---|
| `1.1_hist_maintenance_machine.png` | Nombre de maintenances par machine |
| `1.2_box_duration_machine.png` | Durée de maintenance par machine (boxplot) |
| `1.3_maintenance_type_split.png` | Proactive vs reactive par machine |
| `1.4_hist_maintenance_component.png` | Maintenances par composant |
| `run_report.md` | Rapport technique (métriques + synthèse maintenance) |
| `dataset_report.md` | Rapport de synthèse partageable (métier) compilant les graphes |

Registre dédié : `artifacts/ingestions/machines/runs_registry.json`.

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

Checklist pour une source `<nom>` :

1. **Schéma & chemins** dans `src/config.py` (colonnes attendues, chemin du fichier
   d'entrée, dossier d'artefacts/registre).
2. **`src/sources/<nom>/`** :
   - `loader.py` : `load_<nom>()` (lecture, validation, typage) ;
   - module(s) de graphes (PNG préfixés numérotés) ;
   - `runner.py` : `execute_run()`, `write_run_report()`, `write_dataset_report()`
     (**obligatoire**, via `src.common.reporting`), `update_registry()`
     (via `src.common.registry.upsert_run`), **`run_default()`** + **`load_dataframe()`**
     (DataFrame prêt pour traitement/base ; anonymisé à l'ingestion si PII) ;
   - réutiliser `src.common.metrics.compute_quality_metrics`.
3. **Traitement** : si PII, l'anonymisation se fait **à l'ingestion** (dans
   `load_dataframe`, via `src.processing.anonymization`). Les autres traitements
   (encodage texte→valeur, imputation, outliers) sont **déclarés**, pas codés.
4. **Enregistrer la source dans `src/sources/registry.py`** (`SOURCE_SPECS`) :
   `name`, `run_understanding=run_default`, `load_dataframe`, `processing`
   (`ProcessingConfig`), `table` (nom de table PostgreSQL). → l'orchestrateur
   (`run_pipeline`) la prend automatiquement en charge (4 étapes + base).
5. **`scripts/run_<nom>.py`** : wrapper CLI (optionnel ; fixe le backend `Agg`).
6. **Notebook** : ajouter une sous-section dans `notebooks/pipeline.ipynb` (phases
   ingestion / compréhension [A via `src/` + B inline] / traitement).
7. **Documenter** dans `CLAUDE.md` et `README.md`.

> Rappel : **tout run produit `run_report.md` ET `dataset_report.md`**. La mise en
> base utilise `to_sql` replace (idempotent) et est ignorée si la DB est éteinte.
