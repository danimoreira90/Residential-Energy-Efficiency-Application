# Agentic Engineering

This directory contains detailed engineering rules for AI coding agents working
on this project.

For the primary agent ruleset, see `AGENTS.md` at the repository root.
For Claude Code specifically, see `CLAUDE.md`.

## Contents

Files to be created during Sprint 0:

- `PROTECTED-PATHS.md` — full path-by-path read-only rules referenced in `CLAUDE.md`.
- `ROLES.md` — branch role system (feature/, data/, quality/, infra/, bugfix/, chore/).

## Quick reference

The non-negotiable rules that apply to every agent on this repo are in:

| File | Contents |
|------|----------|
| `CLAUDE.md` (root) | Project-specific hard rules HR-1 through HR-7 |
| `AGENTS.md` (root) | Multi-model agent rules mirroring HR-1 through HR-7 |
| `~/.claude/rules/` | Global engineering rules (TDD, EDD, anti-cheat, etc.) |
