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
├── data/
│   ├── raw/                ← données source (jamais modifiées)
│   ├── processed/          ← données transformées
│   └── external/
├── artifacts/
│   └── ingestions/
│       └── incidents/
│           ├── runs_registry.json     ← registre de tous les runs
│           └── AAAAMMJJHHMM/          ← un dossier par run
│               ├── incidents_anonymized.csv
│               ├── dist_incidents_day.png
│               ├── dist_incidents_week.png
│               ├── dist_incidents_shift.png
│               ├── hist_signals_machine.png
│               ├── corr_incidents_signals.png
│               └── run_report.md
├── src/
│   ├── ingestion/
│   │   ├── loader.py
│   │   ├── anonymizer.py
│   │   └── pipeline.py
│   └── visualization/
│       ├── distributions.py
│       ├── histograms.py
│       └── correlations.py
├── scripts/
│   └── run_ingestion.py    ← point d'entrée CLI
└── notebooks/              ← exploration EDA (non versionnés dans DVC)
```

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

### Lancer le pipeline d'ingestion

```bash
# Prérequis : copier .env.example en .env et renseigner ANONYMIZATION_SALT
uv run python scripts/run_ingestion.py --input data/raw/incidents.csv
```

Le script crée automatiquement un dossier `artifacts/ingestions/incidents/AAAAMMJJHHMM/`
et met à jour `runs_registry.json`.

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

| Fichier | Description |
|---|---|
| `incidents_anonymized.csv` | Dataset nettoyé et anonymisé |
| `dist_incidents_day.png` | Distribution des incidents par jour |
| `dist_incidents_week.png` | Distribution par semaine |
| `dist_incidents_shift.png` | Distribution par shift |
| `hist_signals_machine.png` | Histogrammes par signal et par machine |
| `corr_incidents_signals.png` | Matrice de corrélation |
| `run_report.md` | Rapport du run (métriques, observations) |

Le registre `runs_registry.json` est mis à jour automatiquement.
