# Changelog

All notable changes to SincroLab are documented in this file.

## [Unreleased]

### Added

- Static educational web using Pyodide 0.27.7, its NumPy distribution and the
  normal SincroLab wheel, with verified SHA-256 identity and a thin JSON bridge.
- Real guided workflow, prediction invalidation on intervention, on-demand
  hints/solution, original baseline comparisons and deterministic explanations.
- Browser-local free mode, worker execution, explicit loading/error states,
  responsive sampled trajectory plots and canonical JSON downloads.
- Reproducible static assembly from checkout or sdist, explicit asset packaging,
  native CLI/Desktop/bridge parity and a real HTTP/Chrome/Pyodide check.

- Optional educational Qt desktop consuming the existing portable API through
  a single adapter, with real guided-case metadata and prediction-first runs.
- Restricted intervention editors, retained baseline/attempt comparisons,
  sampled angle/speed plots, progressive hints and one possible solution.
- Deterministic H24 explanations, unchanged H19 bracket semantics, in-memory
  attempt history and optional complete pre/post assessment through H25.
- Free-mode transient evaluation with explicit inertia, clearing time, horizon
  and time step; background execution and visible input/domain errors.

## [0.1.0-core] - 2026-09-05

### Added

- Classical SMIB power-angle relations, machine domain, and swing equation.
- Project-owned explicit Euler and classical RK4 integrators with convergence
  evidence and exact event-boundary segmentation.
- Prefault, fault, and postfault transient simulation using documented
  equivalent `Pmax` values.
- Sampled first-swing assessment with `STABLE`, `UNSTABLE`, and
  `INDETERMINATE` outcomes and adjacent-sample event brackets.
- Equal Area assessment for compatible zero-damping cases and an analytic
  critical clearing angle.
- Temporal critical-clearing search as a validated stable-to-unstable bracket,
  plus an independent angle/time cross-check.
- SciPy `solve_ivp` comparison as test-only external numerical evidence and
  systematic time-step sensitivity regressions.
- Public synthetic golden/reference cases with explicit evidence taxonomy.
- Exhaustively parity-checked packaged projection of canonical H23 evidence,
  with per-observation comparison semantics, tolerances, evidence types, and
  provenance.
- Reference reproduction that verifies every reported canonical observation
  for stable/unstable runs and one explicit retained-resolution claim for the
  adversarial case.
- Deterministic pedagogical explanations and three local guided-learning cases
  with prediction, progressive hints, one possible solution, pre/post scoring,
  and evidence-based debriefs.
- Portable application DTOs and facade shared by future desktop/web adapters
  and the H26 CLI.
- JSON export for structured results and CSV export for trajectory samples.
- Minimal `sincrolab` CLI for capabilities, guided cases, and scientific
  reference cases.

### Scientific scope

- Results apply to the documented classical SMIB model and supplied numerical
  configuration.
- The fault is represented by equivalent transfer capacities, not a complete
  short-circuit or network model.
- Temporal critical-clearing output is a bracket. Its search tolerance is a
  stopping criterion, not physical uncertainty or an exact-CCT error bar.
- First-swing classifications do not establish global, asymptotic, or
  multimachine stability.
