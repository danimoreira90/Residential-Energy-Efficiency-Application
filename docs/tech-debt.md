# Tech Debt Log

Entries are added when technical debt is knowingly introduced. Each entry must
include: what, why, and the resolution target.

| ID | Date | What | Why introduced | Resolution target |
|----|------|------|----------------|-------------------|
| TD-001 | 2026-05-10 | ~158 MB NREL CSV files remain in git history (Q5 from MIGRATION.md deferred) | `git filter-repo` rewrites history and requires `git push --force` to origin — a destructive operation that needs Daniel's explicit approval before execution. Working tree files are deleted and gitignored in the legacy cleanup commit. | Sprint 0 close — delete from working tree, confirm git history approach with Daniel, execute `git filter-repo` or accept history bloat. |
