# Changelog

All notable changes to SincroLab are documented in this file.

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
