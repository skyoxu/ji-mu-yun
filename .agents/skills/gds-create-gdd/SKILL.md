---
name: gds-create-gdd
description: Compatibility entry for the current GDS GDD workflow. Use when an existing caller invokes gds-create-gdd; route all workflow behavior to gds-gdd.
---

# GDS Create GDD Compatibility

This skill preserves the legacy `gds-create-gdd` entry point for existing repository callers.

Read and follow the canonical `gds-gdd` skill completely. Do not execute a separate legacy workflow from this directory.

The adjacent `game-types.csv` and `game-types/` directory mirror the canonical files under `gds-gdd/assets/` for Phase A read compatibility only.
