"""First-class Streamlit Industry Pulse experience."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd
import plotly.express as px

import streamlit as st
from src.application.industry_pulse_exports import build_industry_pulse_exports
from src.application.industry_pulse_service import IndustryPulseService
from src.core.industry_pulse import (
    INDUSTRY_PULSE_INTERPRETATION,
    IndustryPulseChangeSummary,
    IndustryPulseSeriesHistory,
)


def render_industry_pulse(
    *,
    selected_industry_code: str | None,
    comparison_codes: Sequence[str],
    service: IndustryPulseService | None,
    load_error: str | None = None,
) -> None:
    """Render exact mapping, browse, history, export, and availability states."""

    st.subheader("Industry Pulse")
    st.caption(
        "Recent official BLS producer-price context from a reviewed offline snapshot. "
        "Industry Pulse remains separate from annual ratios, rankings, scenarios, and bands."
    )
    if service is None:
        st.error(
            "Industry Pulse is temporarily unavailable because the reviewed offline snapshot "
            "could not be loaded."
        )
        if load_error:
            st.caption("Snapshot validation failed; no provider request was attempted.")
        return

    _render_comparison_availability(service, comparison_codes)
    exact_mapping = (
        service.registry.by_industry_code(selected_industry_code)
        if selected_industry_code is not None
        else None
    )
    history: IndustryPulseSeriesHistory
    manually_browsed = False
    if exact_mapping is not None:
        st.success(
            f"Exact verified mapping: annual industry {selected_industry_code} is synchronized "
            f"to BLS series {exact_mapping.series_id}."
        )
        history = service.for_industry_code(exact_mapping.industry_code)
        browse_different = st.checkbox(
            "Browse a different verified signal",
            help=(
                "Browsing is contextual only and does not replace the exact annual-industry "
                "mapping."
            ),
        )
        if browse_different:
            browse_code = st.selectbox(
                "Browse verified signals",
                options=[entry.industry_code for entry in service.registry.entries],
                format_func=lambda code: _mapping_label(service, code),
                key="industry_pulse_browse_mapped",
            )
            history = service.for_industry_code(browse_code)
            manually_browsed = browse_code != exact_mapping.industry_code
    else:
        selected_text = selected_industry_code or "the current selection"
        st.warning(
            f"No verified exact six-digit BLS PPI mapping is available for {selected_text}. "
            "Industry Pulse never substitutes a broader code or display-label match."
        )
        browse_code = st.selectbox(
            "Browse verified signals",
            options=[entry.industry_code for entry in service.registry.entries],
            format_func=lambda code: _mapping_label(service, code),
            key="industry_pulse_browse_unmapped",
            help=("This manually browsed signal is independent of the selected annual industry."),
        )
        history = service.for_industry_code(browse_code)
        manually_browsed = True

    if manually_browsed:
        st.info(
            "Manual browse state: this contextual signal is not an exact mapping for the "
            "selected annual industry and does not change annual calculations."
        )
    _render_history(history)


def _render_history(history: IndustryPulseSeriesHistory) -> None:
    if history.availability == "unmapped" or history.mapping is None:
        st.warning("No reviewed Industry Pulse mapping is available.")
        return
    mapping = history.mapping
    st.markdown(f"### {mapping.registry_label}")
    st.caption(
        f"Official BLS title: {mapping.source_title} · NAICS {mapping.industry_code} · "
        f"Series {mapping.series_id}"
    )
    if history.availability == "empty_range" or not history.observations:
        st.info(
            "The verified mapping is available, but the requested snapshot range contains "
            "no monthly observations."
        )
        st.caption(INDUSTRY_PULSE_INTERPRETATION)
        return
    latest = history.latest_observation
    if latest is None:
        st.error("Industry Pulse could not determine a latest observation.")
        return
    metric_columns = st.columns(4)
    metric_columns[0].metric("Latest PPI value", f"{latest.value:,.3f}")
    metric_columns[1].metric("Observation month", latest.observation_date.strftime("%Y-%m"))
    metric_columns[2].metric(
        "Month-over-month",
        _change_metric_value(history.month_over_month),
    )
    metric_columns[3].metric(
        "Year-over-year",
        _change_metric_value(history.year_over_year),
    )
    summary = (
        f"Latest observation: {latest.observation_date:%B %Y} at {latest.value:,.3f}. "
        f"Month-over-month: {_change_sentence(history.month_over_month)} "
        f"Year-over-year: {_change_sentence(history.year_over_year)}"
    )
    st.write(summary)
    freshness = history.freshness
    freshness_text = (
        f"{freshness.state.title()} as of {freshness.as_of.isoformat()} "
        f"({freshness.age_days} days since the latest observation; "
        f"{freshness.threshold_days}-day monthly threshold)."
    )
    if freshness.state == "stale":
        st.warning(f"Freshness: {freshness_text}")
    else:
        st.caption(f"Freshness: {freshness_text}")

    rows = pd.DataFrame([item.to_dict() for item in history.observations])
    rows["observation_date"] = pd.to_datetime(rows["observation_date"])
    chart_col, table_col = st.columns(2)
    with chart_col:
        chart = px.line(
            rows,
            x="observation_date",
            y="value",
            markers=True,
            title=f"Monthly PPI history — {mapping.registry_label}",
        )
        chart.update_layout(xaxis_title="Observation month", yaxis_title=mapping.units)
        st.plotly_chart(chart, use_container_width=True)
    with table_col:
        st.markdown("**Accessible monthly data table**")
        table = rows.loc[:, ["observation_date", "value", "release_period"]].rename(
            columns={
                "observation_date": "Observation month",
                "value": "PPI value",
                "release_period": "Release period",
            }
        )
        table["Observation month"] = table["Observation month"].dt.strftime("%Y-%m")
        st.dataframe(table, use_container_width=True, hide_index=True)

    st.markdown("**Signal metadata and provenance**")
    st.write(
        f"Units: {mapping.units} · Seasonal adjustment: {mapping.seasonal_adjustment} · "
        f"BLS base date: {mapping.base_date} · Release period: {history.release_period}"
    )
    st.write(f"Mapping basis: {mapping.mapping_basis}")
    st.caption(
        f"Source: {mapping.source_url} · Retrieval mode: "
        f"{history.provenance.retrieval_mode} · Snapshot: "
        f"{history.provenance.manifest_identity}"
    )
    st.warning(history.limitations[0])
    st.caption(history.limitations[1])

    st.markdown("**Industry Pulse downloads**")
    st.caption(
        "Signal exports are separate from annual dataset exports and carry signal-only provenance."
    )
    for artifact in build_industry_pulse_exports(history):
        st.download_button(
            artifact.label,
            data=artifact.data,
            file_name=artifact.file_name,
            mime=artifact.mime,
            use_container_width=True,
        )


def _render_comparison_availability(
    service: IndustryPulseService, comparison_codes: Sequence[str]
) -> None:
    if not comparison_codes:
        return
    rows = []
    for code in comparison_codes:
        mapping = service.registry.by_industry_code(str(code))
        rows.append(
            {
                "Annual industry code": str(code),
                "Verified signal mapping": "Available" if mapping else "Unmapped",
                "BLS series ID": mapping.series_id if mapping else "—",
                "Signal label": mapping.registry_label if mapping else "—",
            }
        )
    st.markdown("**Comparison mapping availability**")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption(
        "Availability only: raw levels from different BLS series are not compared or "
        "charted together."
    )


def _mapping_label(service: IndustryPulseService, code: str) -> str:
    mapping = service.registry.by_industry_code(code)
    if mapping is None:
        return code
    return f"{mapping.registry_label} ({code}) — {mapping.series_id}"


def _change_metric_value(change: IndustryPulseChangeSummary) -> str:
    return f"{change.value_pct:+.2f}%" if change.value_pct is not None else "Unavailable"


def _change_sentence(change: IndustryPulseChangeSummary) -> str:
    if change.value_pct is not None:
        return f"{change.value_pct:+.2f}%."
    reasons = {
        "comparison_period_missing": "the exact comparison month is missing.",
        "denominator_zero": "the exact comparison value is zero.",
        "period_malformed": "the observation period is malformed.",
        "insufficient_history": "there is insufficient history.",
    }
    if change.reason is None:
        return "the comparison is unavailable."
    return reasons[change.reason]


__all__ = ["render_industry_pulse"]
