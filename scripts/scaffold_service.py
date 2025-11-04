"""Generate an instrumented service scaffold leveraging observability hooks."""

from __future__ import annotations

try:
    from scripts import _bootstrap  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - allow scaffolder CLI execution
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts import _bootstrap  # noqa: F401

import argparse
import textwrap
from pathlib import Path
from typing import Sequence

SERVICE_PACKAGE = Path("src/application/services")


def _ensure_package() -> None:
    SERVICE_PACKAGE.mkdir(parents=True, exist_ok=True)
    init_file = SERVICE_PACKAGE / "__init__.py"
    if not init_file.exists():
        init_file.write_text('"""Generated service scaffolds."""\n\n__all__ = []\n', encoding="utf-8")


def scaffold_service(name: str, *, force: bool) -> Path:
    safe_name = name.strip().replace(" ", "_").replace("-", "_")
    if not safe_name:
        raise ValueError("Service name must not be empty.")
    _ensure_package()
    module_path = SERVICE_PACKAGE / f"{safe_name}.py"
    if module_path.exists() and not force:
        raise FileExistsError(
            f"Service module {module_path} already exists. Use --force to overwrite."
        )

    template = textwrap.dedent(
        f"""
        '''Generated service scaffold.'''

        from __future__ import annotations

        from dataclasses import dataclass

        from src.extensions.manager import get_extension_manager
        from src.infrastructure.observability import bootstrap_observability
        from src.infrastructure.observability.instrumentation import ObservabilityRegistry


        @dataclass
        class {safe_name.title().replace('_', '')}Service:
            '''Service orchestrating domain operations for `{safe_name}`.'''

            observability: ObservabilityRegistry | None = None

            def __post_init__(self) -> None:
                if self.observability is None:
                    self.observability = bootstrap_observability()
                manager = get_extension_manager()
                manager.apply_instrumentation_extensions(self.observability)

            def run(self) -> None:
                '''Execute the service workflow.'''

                registry = self.observability
                context = (
                    registry.operation("service.{safe_name}.run", attributes={{}})
                    if registry is not None
                    else None
                )
                if context is None:
                    # TODO-P2(3h): Replace placeholder logic with real orchestration.
                    return
                with context:
                    # TODO-P2(3h): Implement the core service behaviour.
                    pass
        """
    ).strip()

    module_path.write_text(template + "\n", encoding="utf-8")
    return module_path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an instrumented service skeleton.")
    parser.add_argument("--name", required=True, help="Service identifier (snake-case recommended).")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files when set.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    module_path = scaffold_service(args.name, force=args.force)
    print(f"[idiot-index] Service scaffold created at {module_path}.")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

