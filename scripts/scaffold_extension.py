#!/usr/bin/env python
"""Generate a scaffold for a new Idiot Index extension module."""

from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path

MANIFEST_PATH = Path("extensions/manifest.json")
COMMUNITY_PACKAGE = Path("src/extensions/community")


def _ensure_package() -> None:
    COMMUNITY_PACKAGE.mkdir(parents=True, exist_ok=True)
    init_file = COMMUNITY_PACKAGE / "__init__.py"
    if not init_file.exists():
        init_file.write_text(
            '"""Community extension scaffolds."""\n\n__all__ = []\n', encoding="utf-8"
        )


def _update_manifest(module_path: str) -> None:
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    else:
        manifest = {"modules": []}
    modules = set(manifest.get("modules", []))
    modules.add(module_path)
    manifest["modules"] = sorted(modules)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def scaffold_extension(name: str, *, include_scenario: bool, force: bool) -> Path:
    safe_name = name.strip().replace(" ", "_").replace("-", "_")
    if not safe_name:
        raise ValueError("Extension name must not be empty.")
    module_dir = COMMUNITY_PACKAGE
    module_dir.mkdir(parents=True, exist_ok=True)
    module_path = module_dir / f"{safe_name}.py"
    if module_path.exists() and not force:
        raise FileExistsError(
            f"Extension module {module_path} already exists. Use --force to overwrite."
        )

    lines: list[str] = [
        '"""Generated extension scaffold."""',
        "",
        "from __future__ import annotations",
        "",
        "from dataclasses import dataclass",
        "",
        "from src.extensions.contracts import ExtensionContributions, SummaryExtension",
        "from src.extensions.manager import ExtensionManager",
    ]
    if include_scenario:
        lines.insert(7, "from src.extensions.contracts import ScenarioExtension")

    lines.extend(
        [
            "",
            "",
            "@dataclass",
            "class _SummaryExtension(SummaryExtension):",
            f'    name: str = "{safe_name}"',
            "",
            "    def contribute(self, summary) -> ExtensionContributions:  # type: ignore[override]",
            '        """Compute extension contributions for an IdiotIndexSummary."""',
            "        # TODO-P2(4h): Implement custom contribution logic.",
            "        return ExtensionContributions()",
        ]
    )

    if include_scenario:
        lines.extend(
            [
                "",
                "",
                "@dataclass",
                "class _ScenarioExtension(ScenarioExtension):",
                f'    name: str = "{safe_name}"',
                "",
                "    def contribute(self, result) -> ExtensionContributions:  # type: ignore[override]",
                '        """Compute extension contributions for a ScenarioResult."""',
                "        # TODO-P2(4h): Implement scenario contribution logic.",
                "        return ExtensionContributions()",
            ]
        )

    lines.extend(["", "", "def register(manager: ExtensionManager) -> None:"])
    lines.append("    manager.register_summary_extension(_SummaryExtension())")
    if include_scenario:
        lines.append("    manager.register_scenario_extension(_ScenarioExtension())")
    lines.append('\n\n__all__ = ["register"]\n')

    content = "\n".join(lines)
    module_path.write_text(content, encoding="utf-8")

    module_import_path = f"src.extensions.community.{safe_name}"
    _update_manifest(module_import_path)
    return module_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--name", required=True, help="Extension identifier (snake-case recommended)."
    )
    parser.add_argument(
        "--with-scenario",
        action="store_true",
        help="Include a scenario planning hook in addition to the summary extension.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files if the target extension already exists.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    _ensure_package()
    module_path = scaffold_extension(
        args.name, include_scenario=args.with_scenario, force=args.force
    )

    message = textwrap.dedent(
        f"""
        [idiot-index] Extension scaffold created at {module_path}.
        Remember to implement SummaryExtension.contribute (and ScenarioExtension.contribute when requested).
        The manifest at {MANIFEST_PATH} now includes the module so it loads automatically.
        """
    ).strip()
    print(message)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
