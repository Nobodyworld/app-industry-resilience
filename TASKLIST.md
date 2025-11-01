# TASKLIST: Task Compilation

-*NEVER REMOVE SPEC.md, STYLE-GUIDE.md, or TASKLIST.md FROM THE ROOT*

Use this file to compile and track all tasks that need to be completed for this repository. Check off items as they are finished. Keep each task on a single line. Check off already completed tasks and keep things in chronological order when updating and adding to the file. Follow Template Entry below.

Keep entries one-line, oldest-first. When completing a task, check it off and append a one-line completion note indented underneath (date + PR/link + 1â€“2 sentence summary).

## Template (single-line + optional completion note)

```text
- [ ] Short task description â€” TK-YYYYMMDD-###
```

Completion note (indented, one line):

```text
  - Completed: YYYY-MM-DD â€” PR: <url> â€” short summary
```

---

## Tasks
## Done
- [x] Add repo defaults (no functional changes) | owner: automation | added: 2025-10-29 | closed: 2025-10-30 – `.gitattributes` committed, defaults verified.
- [x] Wire reusable CI (workflow_call) | owner: automation | added: 2025-10-29 | closed: 2025-10-30 – new `quality-gate` workflow in place and CI wired to it.
- [x] Fill URGENT.md from template | owner: automation | added: 2025-10-29 | closed: 2025-10-30 – repository plan populated with current state.
- [x] Compare dependencies to MASTER-VERSIONS.json | owner: automation | added: 2025-10-29 | closed: 2025-10-30 – targets captured in `MASTER-VERSIONS.json` with alignment report.
- [x] Consolidate docs and relocate agent toolkit | owner: automation | added: 2025-10-30 | closed: 2025-10-30 – documentation moved into `docs/handbook/`, agent toolkit now under `src/agents`, and README highlights the structure.
