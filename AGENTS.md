# Repository Agent Instructions

These instructions supplement, and do not weaken, stricter owner or project instructions,
[`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md), [`.agent/PLANS.md`](.agent/PLANS.md), or more
specific `AGENTS.md` files.

## Work-slice workspace hygiene

A work slice is not complete until every temporary workspace and external artifact created for that
slice has been reconciled safely.

### Start-of-slice rules

- Treat the primary checkout and every pre-existing worktree, clone, stash, recovery path, and
  temporary directory as protected. Do not modify, clean, move, or delete them merely to prepare the
  slice.
- Run `git worktree list --porcelain` and inventory matching temporary clones or directories before
  creating anything. Record the pre-existing paths and refs so they cannot be mistaken for
  slice-owned workspaces later.
- Use at most one agent-owned disposable checkout and one external artifact directory for the slice
  unless concurrent isolation genuinely requires more. Reuse them instead of creating serial
  workspaces.
- Create temporary workspaces outside the primary checkout. Record each owned path, branch or
  detached ref, starting SHA, origin, purpose, and expected disposition.
- Do not use a stash as a substitute for preserving or reconciling work.

### Safe reconciliation gate

Before removing an agent-owned worktree, independent clone, or external artifact directory:

1. Leave the directory and stop every task-created process that might reference it.
2. Confirm the exact path, whether it is a normal directory or reparse point, and whether Git treats
   it as a registered worktree or an independent clone.
3. Record its branch or detached ref, exact `HEAD`, origin, and
   `git status --short --untracked-files=all` output when applicable.
4. Inventory ignored and untracked paths that removal would delete, using
   `git status --short --ignored=matching`, `git ls-files`, or an equivalent reviewed report. A clean
   ordinary status is not proof that ignored content is disposable.
5. Prove that no staged, unstaged, untracked, ignored, or external content contains unique user work,
   credentials, environment files, databases, downloads, evidence, or unknown data.
6. Prove the exact `HEAD` is already preserved by an approved destination such as a pushed branch,
   pull request, merged base, published tag, or explicitly retained rescue ref.
7. Confirm the workspace was created by the current slice, is not registered elsewhere, and is not
   referenced by another process.

If any proof is missing, ownership is uncertain, deletion is blocked, ignored content is
unexplained, or unique work exists, stop and retain the path. Report the blocker; do not force
cleanup.

If a normal removal partially succeeds, stop and report the exact remaining state. Do not restore,
reset, change permissions, or retry destructively merely to make cleanup easier.

### Prohibited cleanup shortcuts

- Never use `git worktree remove --force`, `git clean -fd`, `git clean -fdx`, or
  `git reset --hard` to make a cleanup check pass.
- Never change ownership or ACLs, recursively rewrite permissions, or use repeated force retries to
  bypass an access-rights failure.
- Never delete a local or remote branch merely because its worktree was removed. Branch deletion
  requires separate preservation proof and authorization when repository policy requires it.
- Never clear shared npm, pnpm, Yarn, Cargo, Rustup, NuGet, pip, Python, Playwright, browser, or
  operating-system caches during ordinary slice cleanup.
- Never delete environment files, secrets, local databases, user data, fixtures, evidence, or
  unknown untracked or ignored paths.
- Do not run repository-wide garbage collection or aggressive Git maintenance as an incidental
  cleanup step.

### Allowed cleanup

- Remove a slice-owned registered worktree that passed the reconciliation gate using normal
  `git worktree remove <path>` without force.
- Remove a slice-owned independent clone that passed the gate using one normal, exact-path
  filesystem removal from outside the directory. If that removal fails, retain the remainder and
  report it rather than changing permissions or retrying destructively.
- Remove exact task-created logs, browser profiles, downloads, harnesses, and similar external
  artifacts only after their paths, contents, age, ownership, process use, and reparse-point status
  have been reviewed.
- After successful worktree removal, run `git worktree prune --dry-run`. Prune stale metadata only
  when every reported entry is understood and belongs to a workspace already removed safely.
- Generated outputs inside a retained workspace may be removed only when they are documented as
  reproducible, ignored by Git, explicitly scoped, and reviewed before deletion. Prefer removing a
  safely reconciled disposable workspace as a unit.

### Required completion evidence

The final slice report must include:

- the primary checkout path and confirmation that it was not cleaned or overwritten;
- before-and-after `git worktree list --porcelain` inventories;
- every temporary workspace and external artifact path created by the slice and its disposition;
- the exact SHA and branch, pull request, merged base, tag, or rescue ref preserving its work;
- the ignored/untracked inventory and classification used before removal;
- cleanup commands and safety checks actually run;
- any retained workspace or storage-heavy path, with the exact reason it was not removed.

Do not claim workspace cleanup complete while a slice-owned path remains unexplained.

