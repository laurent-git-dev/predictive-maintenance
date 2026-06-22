# CLAUDE.md — Maintenance prédictive industrielle

> Lu automatiquement par Claude Code à chaque session. **Conventions + commandes + pièges.**
> Détail d'architecture : **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** (lire à la demande).
> Vue utilisateur : `README.md`. État courant : git log + `meta.processing_runs`.

---

## Pièges à connaître (gotchas)

- 🖥️ **Shell = PowerShell (VS Code, Windows 11)** : fournir les commandes en **PowerShell**
  (`$RUN = "..."`, `$env:VAR = "..."`, enchaînement `;`, `Copy-Item`), pas en bash.
- 🌐 **Proxy d'entreprise (TLS interception)** : `uv`/`dvc` réseau → ajouter `--native-tls`
  (ou `$env:UV_SYSTEM_CERTS = "true"`) ; `curl` → `--ssl-no-revoke` ; `git` (déjà en config
  locale) → `http.sslBackend=schannel` + `http.schannelCheckRevoke=false`.
- 🗄️ **Base** : créer/mettre à jour le schéma avec `uv run alembic upgrade head` (schémas
  `bronze` + `meta`). Silver/Gold partent des tables en base → DB requise (sinon `--no-db`).
- 📓 **Notebook** : kernel `.venv` (Python 3.14). Helpers dans `src/notebook/render.py`
  (la cellule Setup fait `from src.notebook.render import *`) — **ne pas** relire tout le notebook.

---

## Conventions de code (impératif)

- **Langue de tout contenu généré : anglais** (code, identifiants, commentaires, docstrings,
  logs, libellés de graphes, rapports, clés JSON, messages de commit).
  > Exception : `CLAUDE.md` et les échanges de discussion restent en **français**.
- Encodage **UTF-8** · CSV séparateur **`,`** · dates **ISO 8601** (`YYYY-MM-DD`).
- Variables **snake_case** · constantes **SCREAMING_SNAKE_CASE** · docstrings **NumPy/Google**.
- **`logging`** (pas de `print` en production). `ruff` + `black` (ligne 100) doivent passer.

## Règles de sécurité données

- Ne **jamais** committer `data/raw/` (géré par `.gitignore` + DVC) ni de données nominatives.
- Les clés de mapping (hash → identité réelle) ne sont **jamais** stockées dans le dépôt.
- PII opérateurs (`operator_name`, `operator_badge`) **pseudonymisées dès le Bronze**
  (HMAC-SHA256 tronqué) ; `comment` brut en Bronze, flagué ensuite.

---

## Stack

Python **3.14** (`.python-version` ; `requires-python >=3.12`) · **uv** (`.venv`, `uv.lock`) ·
pandas · matplotlib · scipy · **SQLAlchemy** + **Alembic** (PostgreSQL Docker) · **Pydantic**
(validation Bronze) · **DVC** (remote local) · ruff/black.

---

## Commandes fréquentes

```bash
# Environnement (proxy : ajouter --native-tls si besoin)
uv sync
uv add <paquet>

# Base + schéma
docker compose up -d                 # PostgreSQL (port 5432, identifiants .env)
uv run alembic upgrade head          # schémas bronze + meta

# Pipeline complète (Bronze→Silver→Gold + cross-source, idempotent)
uv run python scripts/run_pipeline.py
uv run python scripts/run_pipeline.py --no-db     # sans la base (fallback fichiers)

# Une source isolée (Bronze + Silver)
uv run python scripts/run_{incidents,telemetry,machines,cross_source}.py [--no-db]

# Qualité
uv run ruff check . ; uv run black .
```

> Si PostgreSQL est éteint, la mise en base est ignorée avec un warning (le reste tourne).
> Procédure complète run → DVC → commit → push : voir **`RUNBOOK.md`**.

### DVC & Git
- Versionner les CSV produits : `uv run dvc add <…/*.csv>` → `git add <…>.dvc` → `dvc push`
  (remote local, pas de réseau). Les CSV bronze/silver/gold sont gitignorés (DVC).
- Commits **Conventional Commits** (`feat(...)`, `fix(...)`, `docs:`, `refactor(...)`,
  `chore(...)`) ; terminer par le trailer `Co-Authored-By` quand demandé.

---

## Architecture (invariant — détail dans docs/ARCHITECTURE.md)

- **Médaillon chaîné en base** : `data/raw/` → **`bronze.*`** → **`silver.*`** → **`gold.features`**,
  chaque couche lisant la précédente **depuis PostgreSQL**.
- **Bronze** : load brut typé + pseudonymisation + **validation Pydantic** non destructive
  (`parse_ok`/`parse_reason`) ; tables ORM gérées par **Alembic**. 4 sources.
- **Silver** : lit `bronze.*`, **politique de rejet** (duplicate/missing corrigeables, reste
  rejeté), puis traitements (`apply_processing`) → `silver.*`. 3 sources (dimension `machine`
  fusionnée dans `silver.maintenance`).
- **Gold** : **1 table** `gold.features` (grain machine×heure) construite depuis `silver.*` ;
  cible = panne (severity ≥ 4) à +6/12/24/48 h ; features mémoire/tendance/anomalie/contexte +
  labels (antifuite).
- **Traçabilité** : chaque exécution = un `batch_id` ; chaque étape → 1 ligne dans
  `meta.processing_runs` (`src/lineage/`).
- **Mutualisation** : `src/common/` (`stage.run_layer`, `profiling`, `quality`) ; runners de
  source **minces** ; orchestrateur `src/orchestrator.py`.
- **Notebook** : 3 chapitres (BRONZE/SILVER/GOLD), gabarit par source **PREVIEW / PROCESSING /
  OVERVIEW** + appendices ; helpers dans `src/notebook/render.py`.

## Ajouter une source de données

> ⚙️ **Instruction permanente** : réaliser **directement l'ensemble** de la checklist
> (sans étape par étape), en réutilisant `src/common/` et le modèle des sources existantes.

Checklist détaillée : voir **[docs/ARCHITECTURE.md → « Add a new source »](docs/ARCHITECTURE.md)**.
En bref : `config.py` (schéma/chemins) → `src/sources/<nom>/` (`loader.py`, `runner.py` mince :
`load_bronze`/`to_silver` + hooks) → enregistrer dans `src/sources/registry.py` → critères
qualité (`src/common/quality.py`) → `scripts/run_<nom>.py` → cellules notebook → documenter.
