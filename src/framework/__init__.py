"""Generic medallion engine (use-case agnostic).

Reusable plumbing — per-feature profiling, layer staging, processing tools, validation,
lineage and the database engine — configured by the shared kernel (``src.config`` +
``src.quality``). It must never import ``src.usecase.*``.
"""
