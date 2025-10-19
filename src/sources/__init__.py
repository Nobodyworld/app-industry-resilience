"""Legacy import surface for external data adapters."""

from ..adapters import (
    BEAClientError,
    fetch_asm_manufacturing,
    fetch_go_ii_by_industry,
    select_bea_endpoint,
)

__all__ = [
    "BEAClientError",
    "fetch_asm_manufacturing",
    "fetch_go_ii_by_industry",
    "select_bea_endpoint",
]
