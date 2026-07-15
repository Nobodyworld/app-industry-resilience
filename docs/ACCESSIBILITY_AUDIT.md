# Public-beta accessibility audit

Audit date: 2026-07-15

Repository state reviewed: `bafa8af627b163effab99729b3f667af6c8afdb3`

## Purpose

This audit records the accessibility state of the public-beta Streamlit dashboard and the remediation required by issue #78. It covers first-run usability, keyboard order, labels, headings, status messaging, contrast, and non-visual alternatives for key charts and indicators.

The dashboard remains an analytical demonstration. Its ratios and composite indicators are experimental and must not be interpreted as credit, insolvency, causal, investment, or policy conclusions.

## Methodology

The audit used:

- static review of `app.py` and `src/interfaces/streamlit/components.py`;
- review of existing Streamlit AppTest and component tests;
- inspection of rendered-control order implied by the Streamlit source;
- WCAG-style contrast calculations for custom CSS tokens;
- review of textual alternatives adjacent to Plotly charts and risk indicators.

This connector-based audit did not perform a manual desktop-browser screen-reader session. Native tab order, focus visibility, Streamlit tab semantics, and Plotly accessibility must be verified in a rendered browser after implementation.

## Surfaces reviewed

- Page title, hero metadata, and introductory guidance
- Sidebar source, year, upload, and API-key controls
- Loading, success, warning, and error states
- Overview, Explore, Compare, and Scenario Lab tabs
- Signal cards, metrics, risk-band tables, and deep-dive content
- Historical trend, scenario, and observability charts
- Export controls and technical diagnostics
- Root README setup and walkthrough instructions

## Existing strengths

- Inputs generally have visible labels.
- Loading, success, warning, and failure states include descriptive text and do not rely on color alone.
- Public-beta and methodology limitations are prominent.
- Overview risk-band information is available as a table.
- Scenario charts are accompanied by a comparison table and leading-change table.
- Observability charts are accompanied by snapshot-history tables.
- The source-to-year-to-conditional-input order in the sidebar is logically structured in source code.

## Remediation status (issue #78)

- **Implemented:** A11Y-01, A11Y-02, A11Y-03, A11Y-04, A11Y-05, A11Y-07, and A11Y-08. New sessions begin with the bundled sample source, include a dismissible/reopenable native guide, expose clearer sidebar controls, add the historical-trend table alternative, darken muted text to `#5f7488`, and improve native/ARIA semantics where custom markup remains.
- **Rendered browser evidence:** The local sample-data session showed the native sidebar source control before the tablist, the guide could be dismissed and reopened, and the single-year Compare caption remained clear. The bundled sample has no multi-year trend to render the table in that session.
- **Manual verification remains required:** A11Y-06 and the browser/assistive-technology checks below. This implementation does not claim full keyboard traversal, screen-reader, 200% zoom, dark-mode, or Streamlit/Plotly focus verification.

## Findings

| ID | Severity | Surface | Finding | Required remediation |
| --- | --- | --- | --- | --- |
| A11Y-01 | High | First run | A new session does not explicitly enter a guided bundled-sample workflow, even though sample data is the safest no-credential starting point. | Default a true first-run session to sample data while preserving explicit query/session choices, and add a dismissible guide. |
| A11Y-02 | High | Compare | The historical trend chart has no adjacent table or equivalent textual representation. | Add an expandable, clearly labelled trend-data table next to the chart. |
| A11Y-03 | Medium | Custom CSS | Muted text token `#8ca1b4` has approximately 2.5–2.7:1 contrast against the light surfaces, below the 4.5:1 target for normal text. | Replace it with a darker token that retains the visual hierarchy and reaches the target. |
| A11Y-04 | Medium | Headings and cards | Some custom HTML uses styled `div` elements where semantic headings or groups would communicate structure more clearly. | Add semantic roles/labels or use native Streamlit headings where practical. |
| A11Y-05 | Medium | Sidebar controls | `Source`, upload, reference-year, and credential-dependent controls could provide more explicit labels and help. | Use meaningful labels, stable widget keys, and concise help text. |
| A11Y-06 | Medium | Keyboard navigation | Source order appears logical, but Streamlit owns the generated DOM, tab semantics, and focus behavior. | Preserve source order, avoid positive `tabindex`, and complete manual keyboard verification in a rendered desktop browser. |
| A11Y-07 | Low | Status and badges | Several statuses are visually styled, although their text is already descriptive. | Keep explicit prefixes and text values whenever status wording changes. |
| A11Y-08 | Low | README | Setup guidance duplicates commands and places a Windows activation command in a Bash-labelled block. | Separate platform-specific activation commands and remove avoidable duplication. |

## Implementation acceptance checks

The issue #78 implementation should demonstrate that:

1. A first-run session can begin with bundled sample data and no credentials.
2. The guide explains source selection, metric limitations, the Explore → Compare → Scenario workflow, and exports.
3. Primary controls retain a logical source order.
4. Inputs have meaningful visible labels and help where needed.
5. Status messages remain understandable without color.
6. Key charts and risk indicators have adjacent tables or text.
7. Muted custom text reaches normal-text contrast expectations.
8. README Markdown and setup instructions render consistently.
9. Streamlit AppTest/component tests cover changed behavior.
10. `make quality-gate` passes on the exact pull-request head.

## Manual browser verification still required

After the implementation is rendered in a desktop browser, verify:

- keyboard-only traversal from sidebar controls through the four primary tabs;
- visible focus indication for select boxes, upload, text input, multiselect, sliders, buttons, expanders, and download controls;
- meaningful announcements of loading, success, warning, and error messages with a screen reader;
- Streamlit tab names and selected state;
- Plotly chart titles and access to adjacent tables;
- zoom to 200% without loss of controls or essential text;
- contrast in both supported application appearances.

Browser or assistive-technology defects that originate in Streamlit or Plotly should be recorded as platform limitations rather than worked around with fragile DOM scripting.
