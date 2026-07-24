from __future__ import annotations

from pathlib import Path


def replace_exact(path: str, old: str, new: str, *, count: int = 1) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    actual = text.count(old)
    if actual != count:
        raise SystemExit(f"{path}: expected {count} occurrence(s), found {actual}: {old!r}")
    file_path.write_text(text.replace(old, new), encoding="utf-8")


replace_exact("pyproject.toml", 'version = "0.2.0rc1"', 'version = "0.2.0"', count=2)
replace_exact("src/version.py", '__version__ = "0.2.0rc1"', '__version__ = "0.2.0"')

replace_exact(
    "README.md",
    "> **Status: v0.2.0rc1 PUBLIC BETA RELEASE CANDIDATE** — Automated candidate validation is in progress. The analytical metrics remain experimental and should not be treated as financial, investment, credit, or policy advice.",
    "> **Status: v0.2.0 PUBLIC BETA** — Released after protected CI, production Docker validation, and Windows/Microsoft Edge acceptance. The analytical metrics remain experimental and should not be treated as financial, investment, credit, or policy advice.",
)
replace_exact(
    "README.md",
    "Release-candidate evidence and manual Windows/Edge acceptance are tracked in [issue #107](https://github.com/Nobodyworld/app-industry-resilience/issues/107) and [`docs/execplans/v0.2.0-public-beta-release-candidate.md`](docs/execplans/v0.2.0-public-beta-release-candidate.md). The final `v0.2.0` tag and GitHub release must not be created before the recorded release-owner GO decision.",
    "The `v0.2.0` Public Beta release evidence, Windows/Edge acceptance matrix, and remaining publication bookkeeping are tracked in [issue #107](https://github.com/Nobodyworld/app-industry-resilience/issues/107), [`docs/execplans/v0.2.0-public-beta-release-candidate.md`](docs/execplans/v0.2.0-public-beta-release-candidate.md), and [`docs/RELEASE_NOTES_V0.2.0.md`](docs/RELEASE_NOTES_V0.2.0.md).",
)
replace_exact(
    "README.md",
    "- [v0.2.0 release-candidate plan](docs/execplans/v0.2.0-public-beta-release-candidate.md)",
    "- [v0.2.0 release validation and acceptance](docs/execplans/v0.2.0-public-beta-release-candidate.md)\n- [v0.2.0 Public Beta release notes](docs/RELEASE_NOTES_V0.2.0.md)",
)

replace_exact("docs/RELEASE_NOTES_V0.2.0.md", "**Status:** Release candidate draft  ", "**Status:** Final Public Beta release  ")
replace_exact("docs/RELEASE_NOTES_V0.2.0.md", "**Candidate package version:** `0.2.0rc1`  ", "**Package version:** `0.2.0`  ")
replace_exact("docs/RELEASE_NOTES_V0.2.0.md", "**Final intended version/tag:** `0.2.0` / `v0.2.0`  ", "**Release version/tag:** `0.2.0` / `v0.2.0`  ")
replace_exact(
    "docs/RELEASE_NOTES_V0.2.0.md",
    "These notes describe the intended `v0.2.0` Public Beta release. Publication remains blocked until protected automated validation and the recorded Windows/Edge manual acceptance pass are complete.",
    "These notes describe the final `v0.2.0` Public Beta release. The complete Windows/Edge acceptance matrix passed, and publication proceeds only after fresh protected CI and Docker validation on the exact final release head.",
)
replace_exact(
    "docs/RELEASE_NOTES_V0.2.0.md",
    "- Manual keyboard, focus, screen-reader, 200% zoom, and light/dark rendered-browser acceptance must be recorded before publication.",
    "- Keyboard, focus, 200% zoom, light/dark appearance, and chart-alternative checks passed in Microsoft Edge; a screen reader was not run and no screen-reader PASS is claimed.",
)
replace_exact(
    "docs/RELEASE_NOTES_V0.2.0.md",
    "Exact automated and manual results will be recorded in:",
    "Exact automated and manual results are recorded in:",
)
replace_exact(
    "docs/RELEASE_NOTES_V0.2.0.md",
    "- the final release pull request and protected workflow runs",
    "- release pull request #110 and its protected workflow runs",
)
replace_exact(
    "docs/RELEASE_NOTES_V0.2.0.md",
    "The final release notes must name the exact merged `main` SHA, CI run, Docker Smoke run, annotated tag, and GitHub release URL before publication is considered complete.",
    "Post-merge bookkeeping will record the exact merged `main` SHA, final CI and Docker runs, annotated tag, GitHub release URL, and tag/release SHA parity.",
)

replace_exact(
    "docs/execplans/v0.2.0-public-beta-release-candidate.md",
    "**Status:** Phase 2 complete — Windows/Edge acceptance passed; GO recommended<br>",
    "**Status:** Phase 3 — GO accepted; final `0.2.0` publication validation<br>",
)
replace_exact(
    "docs/execplans/v0.2.0-public-beta-release-candidate.md",
    "**Candidate package version:** `0.2.0rc1`  ",
    "**Final package version:** `0.2.0`  ",
)
replace_exact(
    "docs/execplans/v0.2.0-public-beta-release-candidate.md",
    "The candidate is not a `1.0.0` stability declaration. Manual rendered-browser accessibility checks and release-owner acceptance are required before final publication.",
    "This is not a `1.0.0` stability declaration. The rendered-browser acceptance matrix passed in Microsoft Edge; screen-reader coverage remains explicitly NOT RUN.",
)
replace_exact(
    "docs/execplans/v0.2.0-public-beta-release-candidate.md",
    "Decision owner: Acceptance recommendation recorded by Codex; final release-owner approval remains required<br>",
    "Decision owner: Nobodyworld repository owner; GO accepted through the release workflow on 2026-07-24<br>",
)
replace_exact(
    "docs/execplans/v0.2.0-public-beta-release-candidate.md",
    "Decision notes: GO recommended. Protected CI #229 and Docker Smoke #109 passed exact accepted candidate `9b8bc27c…`; focused recovery, complete dashboard/API/export/provenance, and dedicated Edge accessibility matrices passed. Screen reader was not run and no PASS was claimed. No new release-blocking defect was found.",
    "Decision notes: GO accepted. Protected CI #229 and Docker Smoke #109 passed the accepted code; focused recovery, complete dashboard/API/export/provenance, and dedicated Edge accessibility matrices passed. Screen reader was not run and no PASS was claimed. No release-blocking defect remains.",
)
replace_exact(
    "docs/execplans/v0.2.0-public-beta-release-candidate.md",
    "- [ ] Change package, Commitizen, and fallback versions from `0.2.0rc1` to `0.2.0`.\n- [ ] Replace candidate placeholders with exact manual and hosted validation results.\n- [ ] Consolidate `v0.2.0` release notes.",
    "- [x] Change package, Commitizen, and fallback versions from `0.2.0rc1` to `0.2.0`.\n- [x] Replace candidate placeholders with exact manual and hosted validation results.\n- [x] Consolidate `v0.2.0` release notes.",
)
replace_exact(
    "docs/execplans/v0.2.0-public-beta-release-candidate.md",
    "| Final package version | Pending |",
    "| Final package version | `0.2.0` |",
)

changelog = Path("docs/CHANGELOG.md")
text = changelog.read_text(encoding="utf-8")
marker = "# Changelog\n\n"
if text.count(marker) != 1:
    raise SystemExit("docs/CHANGELOG.md: unexpected header count")
entry = (
    "# 2026-07-24 – v0.2.0 Public Beta finalization\n"
    "- Accepted the completed Windows/Edge GO recommendation and promoted package, Commitizen, and fallback versions from `0.2.0rc1` to `0.2.0`.\n"
    "- Finalized Public Beta status and release notes while preserving all experimental-methodology limitations and explicit screen-reader NOT RUN disclosure.\n"
    "- Publication remains gated on fresh protected CI/Docker checks, exact-head merge, annotated tag, GitHub release, and post-release SHA-parity bookkeeping.\n\n"
)
changelog.write_text(text.replace(marker, marker + entry), encoding="utf-8")
