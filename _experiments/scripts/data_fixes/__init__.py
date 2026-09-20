"""Build and validation tooling for the single-turn benchmark data.

``benchmarks/`` and ``benchmarks_en/`` are generated and checked from here rather
than edited by hand, so every value in them traces back to HOFINET, to the
platform tool schema or to the platform catalog. ``lint_benchmarks`` is the gate
the data has to clear, ``terminology`` holds the question-wording convention,
``build_account_map`` derives the account map from the database, and the
``new_cases`` and ``multiturn`` sub-packages hold the case authoring and the
verification that goes with it.
"""
