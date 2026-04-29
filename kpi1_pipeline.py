from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

Scope = Literal["group", "europe"]


@dataclass(frozen=True)
class KPI1Config:
    file_path: Path
    scope: Scope = "group"


PL_ROW_PNB = "Net Banking Income (PNB)"
PL_ROW_OTHER_OPERATING_COSTS = "Other Operating Costs"
PL_ROW_TOTAL_PERSONNEL_COSTS = "Total Personnel Costs"


def _read_pl_raw(file_path: Path) -> pd.DataFrame:
    return pd.read_excel(file_path, sheet_name="Synthese_PL")


def _read_fte_raw(file_path: Path) -> pd.DataFrame:
    return pd.read_excel(file_path, sheet_name="Synthese_ETP", header=None)


def _extract_year(text: object) -> int | None:
    if text is None:
        return None
    match = re.search(r"(\d{4})", str(text))
    return int(match.group(1)) if match else None


def extract_pl_rows(file_path: Path, scope: Scope = "group") -> pd.DataFrame:
    """
    Step 1 in KPI_PLAN:
    Extract yearly P&L rows from Synthese_PL.
    """
    raw = _read_pl_raw(file_path)

    if scope == "group":
        label_col = raw.columns[0]
        value_cols = raw.columns[1:5]
    elif scope == "europe":
        label_col = raw.columns[6]
        value_cols = raw.columns[7:11]
    else:
        raise ValueError(f"Unsupported scope: {scope}")

    table = raw.loc[:, [label_col, *value_cols]].copy()
    year_cols = [2022, 2023, 2024, 2025]
    table.columns = ["metric", *year_cols]

    table["metric"] = table["metric"].astype(str).str.strip()
    table = table[table["metric"].isin(
        {
            PL_ROW_PNB,
            PL_ROW_OTHER_OPERATING_COSTS,
            PL_ROW_TOTAL_PERSONNEL_COSTS,
        }
    )]

    long = table.melt(
        id_vars="metric",
        value_vars=year_cols,
        var_name="year",
        value_name="value_raw",
    )
    long["value_raw"] = pd.to_numeric(long["value_raw"], errors="coerce")
    long = long.dropna(subset=["value_raw"])

    # In the source sheet, cost lines are negative; convert to positive costs for business KPIs.
    long["value"] = long["value_raw"]
    cost_mask = long["metric"].isin(
        [PL_ROW_OTHER_OPERATING_COSTS, PL_ROW_TOTAL_PERSONNEL_COSTS]
    )
    long.loc[cost_mask, "value"] = long.loc[cost_mask, "value_raw"].abs()

    return long.sort_values(["year", "metric"]).reset_index(drop=True)


def extract_avg_fte(file_path: Path, scope: Scope = "group") -> pd.DataFrame:
    """
    Step 2 in KPI_PLAN:
    Extract yearly average FTE from Synthese_ETP.
    """
    raw = _read_fte_raw(file_path)

    if scope == "group":
        row_mask = raw.iloc[:, 0].astype(str).str.contains(
            "TOTAL \\(Toutes Filiales conso\\)", regex=True, na=False
        )
    elif scope == "europe":
        row_mask = raw.iloc[:, 0].astype(str).str.contains(
            "o/w TOTAL \\(Europe\\)", regex=True, na=False
        )
    else:
        raise ValueError(f"Unsupported scope: {scope}")

    if not row_mask.any():
        raise ValueError(f"Unable to locate FTE row for scope={scope!r}")

    row_values = raw.loc[row_mask].iloc[0]

    records: list[dict[str, float | int]] = []
    for col_idx in raw.columns:
        second_header = str(raw.iat[1, col_idx]).strip()
        if second_header != "ETP moyen période":
            continue

        year = _extract_year(raw.iat[0, col_idx])
        if year is None and isinstance(col_idx, int) and col_idx > 0:
            # In this sheet layout, year labels can be stored in the previous column.
            year = _extract_year(raw.iat[0, col_idx - 1])
        if year is None:
            continue

        value = pd.to_numeric(row_values[col_idx], errors="coerce")
        if pd.notna(value):
            records.append({"year": int(year), "avg_fte": float(value)})

    if not records:
        raise ValueError("No 'ETP moyen période' columns found in Synthese_ETP")

    return pd.DataFrame(records).sort_values("year").reset_index(drop=True)


def build_kpi1_table(config: KPI1Config) -> pd.DataFrame:
    """
    Step 3 in KPI_PLAN:
    Build yearly finance KPI table, 2022-2025.
    """
    pl_long = extract_pl_rows(config.file_path, config.scope)
    fte = extract_avg_fte(config.file_path, config.scope)

    pivot = pl_long.pivot(index="year", columns="metric", values="value").reset_index()
    pivot.columns.name = None

    kpi = pivot.merge(fte, on="year", how="inner")

    kpi["hcva"] = kpi[PL_ROW_PNB] - kpi[PL_ROW_OTHER_OPERATING_COSTS]
    kpi["hcva_per_fte"] = kpi["hcva"] / kpi["avg_fte"]
    kpi["hcroi"] = kpi["hcva"] / kpi[PL_ROW_TOTAL_PERSONNEL_COSTS]
    kpi["revenue_per_fte"] = kpi[PL_ROW_PNB] / kpi["avg_fte"]

    ordered_cols = [
        "year",
        PL_ROW_PNB,
        PL_ROW_OTHER_OPERATING_COSTS,
        PL_ROW_TOTAL_PERSONNEL_COSTS,
        "avg_fte",
        "hcva",
        "hcva_per_fte",
        "hcroi",
        "revenue_per_fte",
    ]
    return kpi.loc[:, ordered_cols].sort_values("year").reset_index(drop=True)


def summarize_trend(kpi_table: pd.DataFrame) -> list[str]:
    """
    Step 5 in KPI_PLAN:
    Provide business interpretation for KPI movement over time.
    """
    if kpi_table.empty or len(kpi_table) < 2:
        return ["Not enough yearly points to compute trend interpretation."]

    start = kpi_table.iloc[0]
    end = kpi_table.iloc[-1]

    def pct_change(start_value: float, end_value: float) -> float:
        if start_value == 0:
            return float("nan")
        return ((end_value - start_value) / start_value) * 100.0

    hcva_fte_change = pct_change(start["hcva_per_fte"], end["hcva_per_fte"])
    hcroi_change = pct_change(start["hcroi"], end["hcroi"])
    rev_fte_change = pct_change(start["revenue_per_fte"], end["revenue_per_fte"])

    lines = [
        (
            f"HCVA per FTE moved from {start['hcva_per_fte']:,.2f} in {int(start['year'])} "
            f"to {end['hcva_per_fte']:,.2f} in {int(end['year'])} ({hcva_fte_change:+.1f}%)."
        ),
        (
            f"HCROI moved from {start['hcroi']:.2f} to {end['hcroi']:.2f} "
            f"({hcroi_change:+.1f}%)."
        ),
        (
            f"Revenue per FTE moved from {start['revenue_per_fte']:,.2f} "
            f"to {end['revenue_per_fte']:,.2f} ({rev_fte_change:+.1f}%)."
        ),
    ]

    if end["hcroi"] >= start["hcroi"] and end["hcva_per_fte"] >= start["hcva_per_fte"]:
        lines.append(
            "Interpretation: workforce value creation improved relative to workforce cost."
        )
    elif end["hcroi"] < start["hcroi"] and end["hcva_per_fte"] < start["hcva_per_fte"]:
        lines.append(
            "Interpretation: value creation is weakening versus workforce cost; investigate drivers."
        )
    else:
        lines.append(
            "Interpretation: signals are mixed; inspect entity mix, cost structure, and productivity drivers."
        )

    return lines
