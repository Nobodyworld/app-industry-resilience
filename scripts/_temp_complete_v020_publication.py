from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected exactly one occurrence of {old!r}")
    file_path.write_text(text.replace(old, new), encoding="utf-8")


execplan = "docs/execplans/v0.2.0-public-beta-release-candidate.md"
replace_once(execplan, "# v0.2.0 Public Beta Release Candidate", "# v0.2.0 Public Beta Release")
replace_once(
    execplan,
    "**Status:** Phase 3 — GO accepted; final `0.2.0` publication validation<br>",
    "**Status:** Published and verified — `v0.2.0` Public Beta<br>",
)
replace_once(
    execplan,
    "**Intended final version/tag:** `0.2.0` / `v0.2.0`",
    "**Published version/tag:** `0.2.0` / `v0.2.0`",
)
replace_once(
    execplan,
    "- [ ] Run fresh protected CI and Docker checks on the exact final release head.\n- [ ] Squash-merge the release PR with an exact-head guard.\n- [ ] Verify merged `main` equals the expected release SHA.\n- [ ] Create immutable annotated tag `v0.2.0` at that SHA.\n- [ ] Create the GitHub release classified as Public Beta.\n- [ ] Verify the tag and release resolve to the same commit.\n- [ ] Move issue #107 from active TASKLIST work into completed history.",
    "- [x] Run fresh protected CI and Docker checks on the exact final release head.\n- [x] Squash-merge the release PR with an exact-head guard.\n- [x] Verify merged `main` equals the expected release SHA.\n- [x] Create immutable annotated tag `v0.2.0` at that SHA.\n- [x] Create the GitHub release classified as Public Beta.\n- [x] Verify the tag and release resolve to the same commit.\n- [ ] Move issue #107 from active TASKLIST work into completed history.",
)
replace_once(execplan, "| Final merged main SHA | Pending |", "| Final merged main SHA | `5e600a301e36287449742738260f4f66f218f416` |")
replace_once(execplan, "| Final CI run | Pending |", "| Final CI run | Protected CI / Quality Gate #239 — passed |")
replace_once(execplan, "| Final Docker Smoke run | Pending |", "| Final Docker Smoke run | Docker Deployment Smoke #119 — passed |")
replace_once(execplan, "| Annotated tag | Pending |", "| Annotated tag | `v0.2.0` → `5e600a301e36287449742738260f4f66f218f416` |")
replace_once(execplan, "| GitHub release | Pending |", "| GitHub release | https://github.com/Nobodyworld/app-industry-resilience/releases/tag/v0.2.0 |")
replace_once(execplan, "| Tag/release SHA parity | Pending |", "| Tag/release SHA parity | Verified true |")

notes = "docs/RELEASE_NOTES_V0.2.0.md"
replace_once(
    notes,
    "**Final pre-merge validation base:** `441f9b0f76f28358ee1c51bbbcf054ecd0d10897`<br>",
    "**Final pre-merge validation base:** `441f9b0f76f28358ee1c51bbbcf054ecd0d10897`<br>\n**Merged `main` SHA:** `5e600a301e36287449742738260f4f66f218f416`<br>\n**Final protected CI:** Quality Gate #239 — passed<br>\n**Final Docker Smoke:** #119 — passed<br>\n**GitHub release:** https://github.com/Nobodyworld/app-industry-resilience/releases/tag/v0.2.0<br>\n**Tag/release SHA parity:** verified true<br>",
)
replace_once(
    notes,
    "Post-merge bookkeeping will record the exact merged `main` SHA, final CI and Docker runs, annotated tag, GitHub release URL, and tag/release SHA parity.",
    "Publication is complete: annotated tag `v0.2.0` and the GitHub Public Beta prerelease both resolve to merged `main` SHA `5e600a301e36287449742738260f4f66f218f416`.",
)
