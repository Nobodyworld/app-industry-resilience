"""First-class Streamlit experience for reviewed multi-source Industry Momentum."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import pandas as pd
import plotly.express as px

import streamlit as st
from src.application.industry_momentum_exports import build_industry_momentum_exports
from src.application.industry_momentum_service import IndustryMomentumService
from src.core.industry_momentum import (
    INDUSTRY_MOMENTUM_COMPARISON_LIMITATION,
    INDUSTRY_MOMENTUM_INTERPRETATION,
    IndustryMomentumChange,
    IndustryMomentumFamilyResult,
    IndustryMomentumResult,
    IndustryMomentumSignalHistory,
)


def render_industry_momentum(
    *,
    selected_industry_code: str | None,
    comparison_codes: Sequence[str],
    service: IndustryMomentumService | None,
    load_error: str | None = None,
) -> None:
    """Render mapping, family state, histories, manual browse, and signal exports."""

    st.subheader("Industry Momentum")
    st.caption(
        "Recent official price, employment, production, and capacity context from reviewed "
        "offline snapshots. These observations stay separate from annual ratios, rankings, "
        "Scenario Lab, health scores, bands, and lineage."
    )
    if service is None:
        st.error(
            "Industry Momentum is temporarily unavailable because its reviewed offline "
            "snapshots could not be initialized."
        )
        if load_error:
            st.caption("Snapshot validation failed; no provider request was attempted.")
        return

    _render_family_availability(service)
    _render_comparison_availability(service, comparison_codes)
    target_codes = sorted({entry.target_industry_code for entry in service.registry.entries})
    selected_mappings = (
        service.registry.for_industry(selected_industry_code)
        if selected_industry_code is not None
        else ()
    )
    manually_browsed = False
    if selected_mappings:
        active_code = str(selected_industry_code)
        relationship = (
            "exact"
            if all(entry.mapping_relationship == "exact" for entry in selected_mappings)
            else "exact and broader-published"
        )
        st.success(
            f"Verified {relationship} context is available for selected annual industry "
            f"{active_code}."
        )
        if st.checkbox(
            "Browse a different verified industry",
            help="Contextual browsing never changes the selected annual industry.",
        ):
            active_code = st.selectbox(
                "Browse verified Industry Momentum mappings",
                target_codes,
                format_func=lambda code: _mapping_label(service, code),
                key="industry_momentum_browse_mapped",
            )
            manually_browsed = active_code != selected_industry_code
    else:
        selected_text = selected_industry_code or "the current selection"
        st.warning(
            f"No verified Industry Momentum mapping is available for {selected_text}. "
            "No broader code or label match is substituted automatically."
        )
        active_code = st.selectbox(
            "Browse verified Industry Momentum mappings",
            target_codes,
            format_func=lambda code: _mapping_label(service, code),
            key="industry_momentum_browse_unmapped",
            help="This manual context does not change annual dashboard state.",
        )
        manually_browsed = True
    if manually_browsed:
        st.info(
            "Manual browse state: the displayed context is independent of the selected "
            "annual industry and does not change any annual calculation."
        )

    history_start: date | None = None
    history_end: date | None = None
    if st.checkbox(
        "Use a custom Industry Momentum history window",
        help=(
            "Optionally limit only the contextual monthly display and signal-only downloads. "
            "Annual analysis, comparisons, Scenario Lab, scores, bands, and lineage stay unchanged."
        ),
        key="industry_momentum_custom_history_window",
    ):
        default_start, default_end = _history_window_defaults(service)
        start_col, end_col = st.columns(2)
        with start_col:
            selected_start = st.date_input(
                "History start month",
                value=default_start,
                help="The selected date is normalized to the first day of its month.",
                key="industry_momentum_history_start",
            )
        with end_col:
            selected_end = st.date_input(
                "History end month",
                value=default_end,
                help="The selected date is normalized to the first day of its month.",
                key="industry_momentum_history_end",
            )
        history_start = selected_start.replace(day=1)
        history_end = selected_end.replace(day=1)
        if history_start > history_end:
            st.error("History start month must be on or before history end month.")
            return
        st.caption(
            f"Custom history window: {history_start:%Y-%m} through {history_end:%Y-%m}. "
            "Only the contextual display and signal-only downloads use this range."
        )

    result = service.for_industry_code(active_code, start=history_start, end=history_end)
    _render_overall_state(result)
    prices_tab, employment_tab, production_tab = st.tabs(
        ["Prices", "Employment", "Production & Capacity"]
    )
    by_family = {family.source_family: family for family in result.families}
    with prices_tab:
        _render_family(by_family.get("bls_ppi"), "Producer prices")
    with employment_tab:
        _render_family(by_family.get("bls_ces"), "Employment")
    with production_tab:
        _render_family(by_family.get("fed_g17"), "Production and capacity")

    st.markdown("**Industry Momentum downloads**")
    st.caption(
        "Signal-only exports remain separate from annual exports and carry allowlisted "
        "source-family provenance."
    )
    for artifact in build_industry_momentum_exports(result):
        st.download_button(
            artifact.label,
            data=artifact.data,
            file_name=artifact.file_name,
            mime=artifact.mime,
            use_container_width=True,
        )
    st.warning(INDUSTRY_MOMENTUM_INTERPRETATION)
    st.caption(INDUSTRY_MOMENTUM_COMPARISON_LIMITATION)


def _render_family_availability(service: IndustryMomentumService) -> None:
    rows = []
    labels = {
        "bls_ppi": "BLS PPI",
        "bls_ces": "BLS CES",
        "fed_g17": "Federal Reserve G.17",
    }
    for family, summary in service.availability_summary().items():
        rows.append(
            {
                "Source family": labels[family],
                "State": str(summary["availability"]).title(),
                "Verified series": summary["series_count"],
                "Observation range": (
                    f"{summary['observation_start']} to {summary['observation_end']}"
                    if summary["observation_start"]
                    else "Unavailable"
                ),
            }
        )
    st.markdown("**Source-family availability**")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_comparison_availability(
    service: IndustryMomentumService, comparison_codes: Sequence[str]
) -> None:
    if not comparison_codes:
        return
    rows = []
    for code in comparison_codes:
        mappings = service.registry.for_industry(str(code))
        relationships = sorted({entry.mapping_relationship for entry in mappings})
        rows.append(
            {
                "Annual industry code": str(code),
                "Mapping availability": "Available" if mappings else "Unmapped",
                "Relationship": ", ".join(relationships) if relationships else "—",
                "Source families": ", ".join(sorted({entry.source_family for entry in mappings}))
                or "—",
            }
        )
    st.markdown("**Comparison mapping availability**")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption("Availability only; unlike raw signals are never placed on one value axis.")


def _render_overall_state(result: IndustryMomentumResult) -> None:
    relationship = result.mapping_relationship or "none"
    st.write(
        f"Overall state: **{result.availability}** · Mapping relationship: "
        f"**{relationship.replace('_', ' ')}**."
    )
    if result.availability == "partial":
        st.warning(
            "Partial state: at least one mapped source family is unavailable or has no "
            "observations while another family remains usable."
        )
    elif result.availability == "unmapped":
        st.warning("No reviewed mapping is available for this industry.")
    elif result.availability == "empty_range":
        st.info("Mapped signals exist, but the requested date range is empty.")
    elif result.availability == "unavailable":
        st.error("Every requested mapped source family is unavailable.")


def _render_family(family: IndustryMomentumFamilyResult | None, heading: str) -> None:
    st.markdown(f"### {heading}")
    if family is None or family.availability == "unmapped":
        st.info(f"No reviewed {heading.lower()} mapping is available for this industry.")
        return
    st.write(f"Source-family state: **{family.availability}**")
    if family.availability == "unavailable":
        st.error(
            f"The reviewed offline {heading.lower()} snapshot is unavailable; no live "
            "provider request was attempted."
        )
        return
    for history in family.histories:
        _render_history(history)


def _render_history(history: IndustryMomentumSignalHistory) -> None:
    mapping = history.mapping
    st.markdown(f"#### {mapping.registry_label}")
    st.caption(
        f"Official title: {mapping.official_title} · Series {mapping.series_id} · "
        f"Published industry {mapping.published_industry_code} · Selected annual industry "
        f"{mapping.target_industry_code}"
    )
    if mapping.mapping_relationship == "broader_published":
        st.warning(
            f"Broader published mapping ({mapping.mapping_level.replace('_', ' ')}): this "
            "is not an exact six-digit industry match."
        )
    else:
        st.success("Exact six-digit published mapping.")
    if history.availability == "empty_range" or not history.observations:
        st.info("The mapping exists, but the requested snapshot range has no observations.")
        return
    latest = history.latest_observation
    if latest is None:
        st.error("A latest observation could not be determined.")
        return
    metrics = st.columns(4)
    metrics[0].metric("Latest value", f"{latest.value:,.3f} {latest.units}")
    metrics[1].metric("Latest month", latest.observation_date.strftime("%Y-%m"))
    metrics[2].metric("Month-over-month", _change_text(history.month_over_month))
    metrics[3].metric("Year-over-year", _change_text(history.year_over_year))
    st.write(
        f"Latest {mapping.registry_label.lower()} was {latest.value:,.3f} {latest.units} in "
        f"{latest.observation_date:%B %Y}. MoM: {_change_sentence(history.month_over_month)} "
        f"YoY: {_change_sentence(history.year_over_year)}"
    )
    freshness = history.freshness
    freshness_text = f"{freshness.state.title()} as of {freshness.as_of.isoformat()}" + (
        f" ({freshness.age_days} days old)." if freshness.age_days is not None else "."
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
            title=f"Monthly history — {mapping.registry_label}",
        )
        chart.update_layout(xaxis_title="Observation month", yaxis_title=mapping.units)
        st.plotly_chart(chart, use_container_width=True)
    with table_col:
        st.markdown("**Accessible monthly data table**")
        table = rows[["observation_date", "value", "units", "release_period"]].copy()
        table["observation_date"] = table["observation_date"].dt.strftime("%Y-%m")
        table.rename(
            columns={
                "observation_date": "Observation month",
                "value": "Value",
                "units": "Units",
                "release_period": "Release period",
            },
            inplace=True,
        )
        st.dataframe(table, use_container_width=True, hide_index=True)

    st.markdown("**Signal metadata and provenance**")
    st.write(
        f"Change method: {mapping.change_method.replace('_', ' ')} · Units: {mapping.units} · "
        f"Seasonal adjustment: {mapping.seasonal_adjustment} · Base period: "
        f"{mapping.base_period or 'Not applicable'} · Release period: {history.release_period}"
    )
    st.write(f"Mapping basis: {mapping.mapping_basis}")
    if history.provenance is not None:
        provenance = history.provenance
        st.caption(
            f"Provider: {provenance.provider} · Source: {mapping.source_url} · Retrieval mode: "
            f"{provenance.retrieval_mode} · Snapshot: {provenance.manifest_identity}"
        )


def _mapping_label(service: IndustryMomentumService, code: str) -> str:
    mappings = service.registry.for_industry(code)
    labels = sorted({entry.registry_label for entry in mappings})
    return f"{code} — {'; '.join(labels[:2])}"


def _history_window_defaults(service: IndustryMomentumService) -> tuple[date, date]:
    summaries = service.availability_summary().values()
    starts = [
        date.fromisoformat(str(summary["observation_start"]))
        for summary in summaries
        if summary["observation_start"] is not None
    ]
    ends = [
        date.fromisoformat(str(summary["observation_end"]))
        for summary in summaries
        if summary["observation_end"] is not None
    ]
    if not starts or not ends:
        fallback = date(2024, 1, 1)
        return fallback, fallback
    return min(starts).replace(day=1), max(ends).replace(day=1)


def _change_text(change: IndustryMomentumChange) -> str:
    if change.value is None:
        return "Unavailable"
    suffix = "pp" if change.method == "percentage_point_change" else "%"
    return f"{change.value:+.2f}{suffix}"


def _change_sentence(change: IndustryMomentumChange) -> str:
    if change.value is not None:
        return f"{_change_text(change)} ({change.method.replace('_', ' ')})."
    reasons = {
        "comparison_period_missing": "the exact comparison month is missing.",
        "denominator_zero": "the exact comparison value is zero.",
        "period_malformed": "the observation period is malformed.",
        "insufficient_history": "there is insufficient history.",
    }
    if change.unavailable_reason is None:
        return "the comparison is unavailable."
    return reasons[change.unavailable_reason]


__all__ = ["render_industry_momentum"]
