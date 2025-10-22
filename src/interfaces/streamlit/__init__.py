"""Streamlit interface layer for the Idiot Index application."""

from .bootstrap import (
    BootstrapError,
    BootstrapState,
    SidebarContext,
    get_bootstrap_state,
    reset_bootstrap_state,
)
from .components import (
    SidebarState,
    build_data_story,
    load_custom_styles,
    render_deep_dive,
    render_download_panel,
    render_insight_tabs,
    render_page_header,
    render_sidebar,
    render_signal_bar,
    render_state_banner,
)
from .helpers import (
    DownloadArtifact,
    build_comparison_table,
    calculate_benchmark,
    decode_query_params,
    encode_query_params,
    prepare_download_artifacts,
    prepare_trend_data,
)

__all__ = [
    "BootstrapError",
    "BootstrapState",
    "SidebarContext",
    "DownloadArtifact",
    "SidebarState",
    "build_comparison_table",
    "build_data_story",
    "calculate_benchmark",
    "decode_query_params",
    "encode_query_params",
    "load_custom_styles",
    "prepare_download_artifacts",
    "prepare_trend_data",
    "get_bootstrap_state",
    "render_deep_dive",
    "render_download_panel",
    "render_insight_tabs",
    "render_page_header",
    "render_sidebar",
    "render_signal_bar",
    "render_state_banner",
    "reset_bootstrap_state",
]
