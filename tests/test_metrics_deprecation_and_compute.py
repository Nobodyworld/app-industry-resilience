from __future__ import annotations

import warnings

import pandas as pd

from src.core.metrics import compute_metrics


def test_compute_metrics_no_pandas_deprecation_warning() -> None:
    df = pd.DataFrame(
        [
            {
                "industry_code": "311",
                "industry_name": "Food",
                "year": 2020,
                "gross_output": 100.0,
                "materials_cost": 60.0,
            },
            {
                "industry_code": "312",
                "industry_name": "Beverage",
                "year": 2020,
                "gross_output": 200.0,
                "materials_cost": 120.0,
            },
        ]
    )
    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        out = compute_metrics(df)
        # Ensure that there are no FutureWarning related to use_inf_as_na
        assert not any("use_inf_as_na" in str(w.message) for w in rec)
    assert "resilience_score" in out.columns
    assert not out["resilience_score"].isna().all()
