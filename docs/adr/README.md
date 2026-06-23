# Architecture Decision Records

Short records of the **structuring decisions** behind this pipeline — the *why*, not the *how*
(the code and [ARCHITECTURE.md](../ARCHITECTURE.md) cover the how). One file per decision,
append-only; supersede rather than rewrite.

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-medallion-db-chained.md) | Medallion layers chained through PostgreSQL | Accepted |
| [0002](0002-bronze-non-destructive-validation.md) | Bronze validates by flagging, never modifying | Accepted |
| [0003](0003-silver-reject-policy.md) | Silver reject policy (correctable vs rejected) | Accepted |
| [0004](0004-gold-single-table-no-leakage.md) | One Gold table at (machine, hour); leakage-safe labels | Accepted |
| [0005](0005-lineage-and-golden-tests.md) | Lineage table + golden tests via output hash | Accepted |
| [0006](0006-framework-usecase-split.md) | Framework / use-case split + shared kernel | Accepted |
| [0007](0007-copy-bulk-load.md) | Bulk-load via PostgreSQL COPY | Accepted |
| [0008](0008-gold-params-no-dvc-dag.md) | Gold spec in params.yaml; no DVC DAG | Accepted |
| [0009](0009-schema-contract-drift-guard.md) | Pydantic↔ORM drift guard instead of generated ORM | Accepted |
| [0010](0010-gold-enrichment-and-leakage-fix.md) | Gold feature enrichment, leakage fix, train/val/test split | Accepted |
