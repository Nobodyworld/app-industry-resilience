#!/usr/bin/env python
"""Generate a scaffold for a new Idiot Index extension module."""

from __future__ import annotations

try:
    from scripts import _bootstrap  # type: ignore  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - allow `python scripts/scaffold_extension.py`
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts import _bootstrap  # type: ignore  # noqa: F401

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


def scaffold_extension(
    name: str,
    *,
    include_scenario: bool,
    include_instrumentation: bool,
    include_connector: bool,
    force: bool,
) -> Path:
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

    contracts: list[str] = ["ExtensionContributions", "SummaryExtension"]
    if include_scenario:
        contracts.append("ScenarioExtension")
    if include_instrumentation:
        contracts.append("InstrumentationExtension")
    if include_connector:
        contracts.append("ConnectorExtension")

    extra_imports: list[str] = []
    if include_connector:
        extra_imports.append("from src.extensions.connectors import ConnectorRegistration")
        extra_imports.append(
            "from src.infrastructure.observability.health import HealthComponent"
        )

    lines: list[str] = [
        '"""Generated extension scaffold."""',
        "",
        "from __future__ import annotations",
        "",
        "from dataclasses import dataclass",
        "",
        f"from src.extensions.contracts import {', '.join(contracts)}",
        "from src.extensions.manager import ExtensionManager",
    ]

    lines.extend(extra_imports)

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

    if include_instrumentation:
        lines.extend(
            [
                "",
                "",
                "@dataclass",
                "class _InstrumentationExtension(InstrumentationExtension):",
                f'    name: str = "{safe_name}"',
                "",
                "    def register(self, registry) -> None:  # type: ignore[override]",
                '        """Hook into the shared observability registry."""',
                "        counter = registry.counter(",
                f'            "{safe_name}_events_total",',
                '            "Total events recorded by this extension",',
                '            label_names=("status",),',
                "        )",
                "",
                "        def _record(event) -> None:",
                '            counter.increment(labels={"status": event.status})',
                "",
                "        registry.subscribe(\"service.idiot_index.evaluate\", _record)",
                "        # TODO-P3(2h): Register additional observability hooks or health checks.",
            ]
        )

    if include_connector:
        lines.extend(
            [
                "",
                "",
                "def _connector_health() -> HealthComponent:",
                '    """TODO-P2(2h): Implement connector health validation."""',
                "    return HealthComponent(",
                f'        name="connector:{safe_name}",',
                "        status=\"warn\",",
                "        summary=\"Connector health check not implemented\",",
                "    )",
                "",
                "",
                "@dataclass",
                "class _ConnectorExtension(ConnectorExtension):",
                f'    name: str = "{safe_name}"',
                "",
                "    def register(self, registry) -> None:  # type: ignore[override]",
                '        """Register connector metadata with optional health checks."""',
                "        registry.register(",
                "            ConnectorRegistration(",
                f'                identifier="{safe_name}",',
                f"                name=\"{safe_name.replace('_', ' ').title()} Connector\",",
                "                kind=\"data_source\",",
                "                version=\"0.1.0\",",
                "                description=\"TODO-P2(2h): Describe connector purpose.\",",
                "                tags=(\"experimental\",),",
                "                capabilities=(\"read\",),",
                "                metadata={},",
                "                health_check=_connector_health,",
                "            )",
                "        )",
                "",
            ]
        )

    lines.extend(["", "", "def register(manager: ExtensionManager) -> None:"])
    lines.append("    manager.register_summary_extension(_SummaryExtension())")
    if include_scenario:
        lines.append("    manager.register_scenario_extension(_ScenarioExtension())")
    if include_instrumentation:
        lines.append("    manager.register_instrumentation_extension(_InstrumentationExtension())")
    if include_connector:
        lines.append("    manager.register_connector_extension(_ConnectorExtension())")
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
        "--instrumentation",
        action="store_true",
        help="Include an instrumentation extension scaffold for observability hooks.",
    )
    parser.add_argument(
        "--with-connector",
        action="store_true",
        help="Include a connector extension scaffold registered with ConnectorRegistry.",
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
        args.name,
        include_scenario=args.with_scenario,
        include_instrumentation=args.instrumentation,
        include_connector=args.with_connector,
        force=args.force,
    )

    message = textwrap.dedent(
        f"""
        [idiot-index] Extension scaffold created at {module_path}.
        Remember to implement SummaryExtension.contribute (and ScenarioExtension.contribute when requested).
        Instrumentation scaffolds emit basic counters and should be customised to capture domain events.
        The manifest at {MANIFEST_PATH} now includes the module so it loads automatically.
        """
    ).strip()
    print(message)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
