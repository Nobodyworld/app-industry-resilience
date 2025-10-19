```md
# Universal Meta UI/UX – Active Creation Mode

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

Reference: .agent/PLANS.md. Maintain this document according to that specification.

## Purpose / Big Picture

We will transform the Streamlit interface in `app.py` into a guided, adaptive experience that feels like a living intelligence. After this change, users will move through a purposeful narrative: orienting in a welcoming hero, preparing data in an adaptive sidebar, glancing at pulse metrics, exploring insights via responsive tabs, and diving deeper through contextual storytelling. They will experience context-aware messaging that reacts to their selections and data state, plus a reusable component system that keeps visuals and tone consistent. Acceptance is demonstrated by running `streamlit run app.py` and observing the redesigned layout, interactive tabs, adaptive guidance banners, and refined styling.

## Progress

- [x] (2025-01-08 04:10Z) Captured current UI structure and clarified redesign goals.
- [x] (2025-01-08 04:45Z) Introduced `src/ui/components.py` with reusable layout primitives.
- [x] (2025-01-08 05:20Z) Refactored `app.py` to orchestrate new narrative flow and adaptive states.
- [x] (2025-01-08 05:35Z) Validated redesigned app launches via `streamlit run` without errors.

## Surprises & Discoveries

- None yet.

## Decision Log

- Decision: Create a dedicated `src/ui/components.py` module to house reusable UI primitives rather than scattering helper functions in `app.py`.
  Rationale: Keeps the narrative-focused surface lean and enables future scaling of the component library.
  Date/Author: 2025-01-08 / Assistant

## Outcomes & Retrospective

- The redesigned Streamlit surface now guides users through a hero header, adaptive banner, insight tabs, and a narrative deep dive powered by reusable UI components. Future enhancements can extend the component library with historical trend visualizations and comparison views.

## Context and Orientation

The Streamlit app lives in `app.py`. It currently handles configuration, data loading, normalization, and presentation directly, using inline layout primitives (`st.columns`, `st.subheader`, etc.). There is no abstraction for components or adaptive states. Supporting utilities reside under `src/` for metrics, normalization, and security, all of which remain valid. We will augment this structure by introducing a `src/ui` package that supplies layout primitives (e.g., hero sections, metric ribbons, tabs) consumed by the refactored `app.py`.

## Plan of Work

First, add a new module `src/ui/components.py` defining composable helpers: `load_custom_styles()` to inject CSS, `render_page_header()` for the hero narrative, `render_sidebar()` for stateful guidance, `render_signal_bar()` for summary metrics, `render_tabs()` for the main exploration surface, and `render_deep_dive()` for contextual storytelling. Include adaptive helper functions such as `build_data_story()` that synthesizes messages from the selected industry and dataset size. Next, modify `app.py` to rely on these primitives. Split the main logic into stages: configuration & data loading (largely unchanged but extracted into helper functions where clarity improves), presentation scaffolding (hero, sidebar, system banner), insights (table + metrics consolidated into tabs), motion/story (contextual messages and optional reveal sections), and download/export. Introduce `st.session_state` keys to remember selected industry and last filter query, enabling continuity between reruns. Implement adaptive messaging that reacts to dataset size, filter usage, and data mode. Apply new CSS classes to standardize spacing, typography, and card visuals. Ensure all imports reference the new component module. Keep data pipeline functions unchanged beyond necessary reorganizing for clarity.

## Concrete Steps

1. Working directory: repository root. Create `src/ui/__init__.py` (empty) and `src/ui/components.py` with the component functions described above, ensuring each uses Streamlit primitives and returns values where needed.
2. Update `app.py`:
   - Import the new component helpers.
   - Initialize `st.session_state` for `focus_mode`, `industry_selection`, and `search_query`.
   - Call `load_custom_styles()` immediately after `st.set_page_config`.
   - Rebuild the sidebar using `render_sidebar()` to gather inputs and produce a structured dict of selections, falling back gracefully on validation errors.
   - Replace inline headers/columns with hero and narrative sections from the component module.
   - Swap the table and metrics layout into a tabbed interface that contains: `Pulse` (summary metrics), `Industries` (filterable table), and `Top Signals` (plotly chart). Each tab uses the helper functions to render content and share consistent styling.
   - Use `render_deep_dive()` to present selected industry details along with `build_data_story()` context text.
   - Ensure download button remains but is nested within a stylized container.
3. Run `streamlit run app.py` locally to confirm no runtime errors (visual verification acknowledged if environment lacks browser access).

## Validation and Acceptance

Launch the app: from repository root run `streamlit run app.py`. Expect to see the new hero header with narrative copy, an adaptive sidebar showing contextual tips, summary signal cards in a horizontal layout, tabs for pulse metrics, industry table, and chart, plus a deep dive panel that narrates insights about the selected industry. Confirm that filter text updates session state, tab navigation works, and the download button appears in the final section.

## Idempotence and Recovery

All changes are additive or refactors within version-controlled files. Re-running the steps is safe. If a regression occurs, revert `app.py` and delete `src/ui` to restore the previous interface. No migrations or persistent side effects occur.

## Artifacts and Notes

None yet.

## Interfaces and Dependencies

The new component functions rely solely on Streamlit and existing app data structures (Pandas DataFrame with fields such as `industry_name`, `industry_code`, `idiot_index`, etc.). No external dependencies are added.
```
