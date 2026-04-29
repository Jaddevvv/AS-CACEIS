from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from kpi1_pipeline import KPI1Config, Scope, build_kpi1_table


DEFAULT_PANEL_PATH = Path("Sujet Alberthon/HR Data/Data.xlsx")
DEFAULT_FINANCE_PATH = Path("Sujet Alberthon/Finance/AlbertSchool_CACEIS_PL-FTE_22-25_Sent.xlsx")
DEFAULT_ABSENCE_PATHS = (
    Path("Sujet Alberthon/HR Data/Absentéisme_-_détail_affectation_-_Bilan_social.xlsx"),
    Path("Sujet Alberthon/HR Data/Absentéisme_-_détail_affectation_-_Bilan_social (1).xlsx"),
    Path(
        "Sujet Alberthon/HR Data/20260121 - Absentéisme_-_détail_affectation_-_Bilan_social 2025.xlsx"
    ),
)


@dataclass(frozen=True)
class KPI4Config:
    panel_path: Path = DEFAULT_PANEL_PATH
    finance_path: Path = DEFAULT_FINANCE_PATH
    finance_scope: Scope = "group"
    absence_paths: tuple[Path, ...] = DEFAULT_ABSENCE_PATHS


@dataclass
class KPI4Result:
    absence_standardized_rows: pd.DataFrame
    employee_month_entity_reason: pd.DataFrame
    monthly_drag: pd.DataFrame
    yearly_drag: pd.DataFrame
    entity_year_drag: pd.DataFrame
    reason_group_year_drag: pd.DataFrame
    reason_detail_year_drag: pd.DataFrame
    latest_year_entity_drag: pd.DataFrame
    latest_year_reason_group_drag: pd.DataFrame
    latest_year_reason_detail_drag: pd.DataFrame


def _normalize_id(values: pd.Series) -> pd.Series:
    cleaned = values.astype(str).str.strip()
    return cleaned.replace({"": pd.NA, "nan": pd.NA, "NaN": pd.NA, "None": pd.NA, "NaT": pd.NA})


def _to_month_start(values: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(values, errors="coerce", dayfirst=True)
    return parsed.dt.to_period("M").dt.to_timestamp()


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denominator_num = pd.to_numeric(denominator, errors="coerce")
    return numerator / denominator_num.where(denominator_num > 0.0)


def _read_absence_rows(file_path: Path) -> pd.DataFrame:
    required = {"Employee Code", "Date Absence", "Jours Ouvrés Absence"}
    optional = [
        "Motif Jour Absence",
        "Regroupement Jour Absences",
        "Société",
    ]

    xl = pd.ExcelFile(file_path)
    chosen_sheet: str | None = None
    chosen_header: int | None = None
    chosen_columns: list[str] = []

    for sheet in xl.sheet_names:
        for header_row in range(0, 4):
            try:
                preview = pd.read_excel(file_path, sheet_name=sheet, header=header_row, nrows=0)
            except Exception:
                continue

            columns = [str(col).strip() for col in preview.columns]
            if required.issubset(set(columns)):
                chosen_sheet = sheet
                chosen_header = header_row
                chosen_columns = columns
                break

        if chosen_sheet is not None:
            break

    if chosen_sheet is None or chosen_header is None:
        raise ValueError(f"Could not locate expected absence headers in file: {file_path}")

    usecols = [col for col in [*required, *optional] if col in chosen_columns]
    raw = pd.read_excel(file_path, sheet_name=chosen_sheet, header=chosen_header, usecols=usecols)

    absence = raw.rename(
        columns={
            "Employee Code": "employee_id",
            "Date Absence": "absence_date",
            "Jours Ouvrés Absence": "absence_days",
            "Motif Jour Absence": "reason_detail",
            "Regroupement Jour Absences": "reason_group",
            "Société": "absence_entity_raw",
        }
    )

    absence["employee_id"] = _normalize_id(absence["employee_id"])
    absence["period"] = _to_month_start(absence["absence_date"])
    absence["year"] = absence["period"].dt.year
    absence["absence_days"] = pd.to_numeric(absence["absence_days"], errors="coerce").fillna(0.0)
    absence["absence_days"] = absence["absence_days"].clip(lower=0.0)
    absence["reason_detail"] = (
        absence.get("reason_detail", pd.Series(index=absence.index))
        .astype(str)
        .str.strip()
        .replace({"": pd.NA, "nan": pd.NA, "NaN": pd.NA})
    )
    absence["reason_group"] = (
        absence.get("reason_group", pd.Series(index=absence.index))
        .astype(str)
        .str.strip()
        .replace({"": pd.NA, "nan": pd.NA, "NaN": pd.NA})
    )
    absence["absence_entity_raw"] = (
        absence.get("absence_entity_raw", pd.Series(index=absence.index))
        .astype(str)
        .str.strip()
        .replace({"": pd.NA, "nan": pd.NA, "NaN": pd.NA})
    )
    absence["reason_group"] = absence["reason_group"].fillna(absence["reason_detail"]).fillna("Unknown")
    absence["reason_detail"] = absence["reason_detail"].fillna("Unknown")

    absence = absence.dropna(subset=["employee_id", "period", "year"]).copy()
    absence["year"] = absence["year"].astype(int)

    return absence.loc[
        :,
        [
            "employee_id",
            "period",
            "year",
            "absence_entity_raw",
            "reason_group",
            "reason_detail",
            "absence_days",
        ],
    ]


def load_absence_standardized(absence_paths: Iterable[Path]) -> pd.DataFrame:
    """
    KPI_PLAN step 1-2:
    Load absence files and standardize employee/month/reason/day fields.
    """
    frames: list[pd.DataFrame] = []
    for path in absence_paths:
        if path.exists():
            frames.append(_read_absence_rows(path))

    if not frames:
        return pd.DataFrame(
            columns=[
                "employee_id",
                "period",
                "year",
                "absence_entity_raw",
                "reason_group",
                "reason_detail",
                "absence_days",
            ]
        )

    stacked = pd.concat(frames, ignore_index=True)
    return (
        stacked.groupby(
            ["employee_id", "period", "year", "absence_entity_raw", "reason_group", "reason_detail"],
            as_index=False,
        )["absence_days"]
        .sum()
        .sort_values(["period", "employee_id"])
        .reset_index(drop=True)
    )


def load_employee_month_dimension(panel_path: Path) -> pd.DataFrame:
    """
    Panel dimensions used for employee count denominator and entity enrichment.
    """
    raw = pd.read_excel(panel_path, sheet_name="Sheet1")
    use_cols = ["PERIOD", "ID Employee", "COUNTRY_GROUP_LABEL_EN", "ENTITY_LABEL_LOCAL", "POSTE_LABEL_LOCAL"]
    missing_cols = [col for col in use_cols if col not in raw.columns]
    if missing_cols:
        raise ValueError(f"Missing columns in panel source: {missing_cols}")

    panel = raw.loc[:, use_cols].rename(
        columns={
            "PERIOD": "period",
            "ID Employee": "employee_id",
            "COUNTRY_GROUP_LABEL_EN": "country",
            "ENTITY_LABEL_LOCAL": "panel_entity",
            "POSTE_LABEL_LOCAL": "job",
        }
    )
    panel["employee_id"] = _normalize_id(panel["employee_id"])
    panel["period"] = _to_month_start(panel["period"])
    panel = panel.dropna(subset=["employee_id", "period"]).copy()
    panel = panel.sort_values(["employee_id", "period"]).drop_duplicates(
        subset=["employee_id", "period"], keep="last"
    )
    return panel.reset_index(drop=True)


def enrich_absence_with_panel(absence_standardized: pd.DataFrame, panel_dimension: pd.DataFrame) -> pd.DataFrame:
    joined = absence_standardized.merge(
        panel_dimension,
        on=["employee_id", "period"],
        how="left",
    )
    joined["entity"] = joined["panel_entity"].fillna(joined["absence_entity_raw"]).fillna("Unknown")
    joined["country"] = joined["country"].fillna("Unknown")
    joined["job"] = joined["job"].fillna("Unknown")
    return joined


def aggregate_employee_month_entity_reason(absence_enriched: pd.DataFrame) -> pd.DataFrame:
    """
    KPI_PLAN step 3:
    Aggregate absence by month, entity, reason, employee.
    """
    if absence_enriched.empty:
        return pd.DataFrame(
            columns=[
                "employee_id",
                "period",
                "year",
                "country",
                "entity",
                "job",
                "reason_group",
                "reason_detail",
                "total_absence_days",
            ]
        )

    grouped = (
        absence_enriched.groupby(
            ["employee_id", "period", "year", "country", "entity", "job", "reason_group", "reason_detail"],
            as_index=False,
        )["absence_days"]
        .sum()
        .rename(columns={"absence_days": "total_absence_days"})
        .sort_values(["period", "entity", "employee_id"])
        .reset_index(drop=True)
    )
    return grouped


def compute_monthly_drag(employee_month_entity_reason: pd.DataFrame, panel_dimension: pd.DataFrame) -> pd.DataFrame:
    """
    KPI_PLAN step 4:
    Convert monthly absence days into lost FTE.
    """
    if employee_month_entity_reason.empty:
        return pd.DataFrame(
            columns=[
                "period",
                "year",
                "total_absence_days",
                "employees_with_absence",
                "active_employees",
                "absence_days_per_employee",
                "employees_with_absence_share",
                "lost_fte",
                "absence_productivity_drag_proxy",
            ]
        )

    absence_monthly = (
        employee_month_entity_reason.groupby(["period", "year"], as_index=False)
        .agg(
            total_absence_days=("total_absence_days", "sum"),
            employees_with_absence=("employee_id", "nunique"),
        )
        .sort_values("period")
        .reset_index(drop=True)
    )

    active_monthly = (
        panel_dimension.groupby("period", as_index=False)["employee_id"]
        .nunique()
        .rename(columns={"employee_id": "active_employees"})
    )

    monthly = absence_monthly.merge(active_monthly, on="period", how="left")
    monthly["active_employees"] = pd.to_numeric(monthly["active_employees"], errors="coerce")
    monthly["absence_days_per_employee"] = _safe_divide(monthly["total_absence_days"], monthly["active_employees"])
    monthly["employees_with_absence_share"] = _safe_divide(
        monthly["employees_with_absence"], monthly["active_employees"]
    )
    monthly["lost_fte"] = monthly["total_absence_days"] / 220.0
    monthly["absence_productivity_drag_proxy"] = _safe_divide(monthly["lost_fte"], monthly["active_employees"])

    return monthly.sort_values("period").reset_index(drop=True)


def load_finance_reference(finance_path: Path, finance_scope: Scope) -> pd.DataFrame:
    """
    Load yearly HCVA per FTE and average FTE from KPI 1 source.
    """
    table = build_kpi1_table(KPI1Config(file_path=finance_path, scope=finance_scope))
    return table.loc[:, ["year", "avg_fte", "hcva", "hcva_per_fte", "hcroi", "revenue_per_fte"]].copy()


def compute_yearly_drag(monthly_drag: pd.DataFrame, finance_reference: pd.DataFrame) -> pd.DataFrame:
    """
    KPI_PLAN step 5:
    Compute yearly absence drag and estimated value lost.
    """
    if monthly_drag.empty:
        return pd.DataFrame(
            columns=[
                "year",
                "total_absence_days",
                "lost_fte",
                "avg_active_employees",
                "absence_days_per_employee",
                "avg_fte",
                "absence_productivity_drag",
                "hcva_per_fte",
                "estimated_value_lost",
                "estimated_value_lost_share_of_hcva",
            ]
        )

    yearly = (
        monthly_drag.groupby("year", as_index=False)
        .agg(
            total_absence_days=("total_absence_days", "sum"),
            lost_fte=("lost_fte", "sum"),
            avg_active_employees=("active_employees", "mean"),
            avg_employees_with_absence=("employees_with_absence", "mean"),
            avg_absence_share=("employees_with_absence_share", "mean"),
            months_observed=("period", "nunique"),
        )
        .sort_values("year")
        .reset_index(drop=True)
    )

    yearly["absence_days_per_employee"] = _safe_divide(yearly["total_absence_days"], yearly["avg_active_employees"])
    yearly = yearly.merge(finance_reference, on="year", how="left")
    yearly["avg_fte_for_drag"] = yearly["avg_fte"].fillna(yearly["avg_active_employees"])
    yearly["absence_productivity_drag"] = _safe_divide(yearly["lost_fte"], yearly["avg_fte_for_drag"])
    yearly["estimated_value_lost"] = yearly["lost_fte"] * yearly["hcva_per_fte"]
    yearly["estimated_value_lost_share_of_hcva"] = _safe_divide(yearly["estimated_value_lost"], yearly["hcva"])

    return yearly


def compute_entity_year_drag(
    employee_month_entity_reason: pd.DataFrame,
    panel_dimension: pd.DataFrame,
    finance_reference: pd.DataFrame,
) -> pd.DataFrame:
    if employee_month_entity_reason.empty:
        return pd.DataFrame(
            columns=[
                "year",
                "entity",
                "total_absence_days",
                "affected_employees",
                "lost_fte",
                "avg_active_employees",
                "absence_days_per_employee",
                "absence_drag_proxy",
                "estimated_value_lost",
            ]
        )

    absence_entity = (
        employee_month_entity_reason.groupby(["year", "entity"], as_index=False)
        .agg(
            total_absence_days=("total_absence_days", "sum"),
            affected_employees=("employee_id", "nunique"),
        )
        .sort_values(["year", "total_absence_days"], ascending=[True, False])
        .reset_index(drop=True)
    )
    absence_entity["lost_fte"] = absence_entity["total_absence_days"] / 220.0

    panel_entity_month = (
        panel_dimension.assign(year=panel_dimension["period"].dt.year)
        .groupby(["year", "period", "panel_entity"], as_index=False)["employee_id"]
        .nunique()
        .rename(columns={"panel_entity": "entity", "employee_id": "active_employees"})
    )
    panel_entity_year = (
        panel_entity_month.groupby(["year", "entity"], as_index=False)["active_employees"]
        .mean()
        .rename(columns={"active_employees": "avg_active_employees"})
    )

    entity = absence_entity.merge(panel_entity_year, on=["year", "entity"], how="left")
    entity["absence_days_per_employee"] = _safe_divide(entity["total_absence_days"], entity["avg_active_employees"])
    entity["absence_drag_proxy"] = _safe_divide(entity["lost_fte"], entity["avg_active_employees"])
    entity = entity.merge(finance_reference[["year", "hcva_per_fte"]], on="year", how="left")
    entity["estimated_value_lost"] = entity["lost_fte"] * entity["hcva_per_fte"]
    return entity.sort_values(["year", "estimated_value_lost"], ascending=[True, False]).reset_index(drop=True)


def compute_reason_year_drag(
    employee_month_entity_reason: pd.DataFrame,
    finance_reference: pd.DataFrame,
    reason_column: str,
) -> pd.DataFrame:
    if employee_month_entity_reason.empty:
        return pd.DataFrame(
            columns=[
                "year",
                reason_column,
                "total_absence_days",
                "affected_employees",
                "lost_fte",
                "estimated_value_lost",
            ]
        )

    grouped = (
        employee_month_entity_reason.groupby(["year", reason_column], as_index=False)
        .agg(
            total_absence_days=("total_absence_days", "sum"),
            affected_employees=("employee_id", "nunique"),
        )
        .sort_values(["year", "total_absence_days"], ascending=[True, False])
        .reset_index(drop=True)
    )
    grouped["lost_fte"] = grouped["total_absence_days"] / 220.0
    grouped = grouped.merge(finance_reference[["year", "hcva_per_fte"]], on="year", how="left")
    grouped["estimated_value_lost"] = grouped["lost_fte"] * grouped["hcva_per_fte"]
    return grouped.sort_values(["year", "estimated_value_lost"], ascending=[True, False]).reset_index(drop=True)


def build_kpi4_result(config: KPI4Config) -> KPI4Result:
    """
    KPI_PLAN steps 1-5 end-to-end builder for KPI 4.
    """
    absence_standardized = load_absence_standardized(config.absence_paths)
    panel_dimension = load_employee_month_dimension(config.panel_path)
    absence_enriched = enrich_absence_with_panel(absence_standardized, panel_dimension)
    employee_month_entity_reason = aggregate_employee_month_entity_reason(absence_enriched)

    monthly_drag = compute_monthly_drag(employee_month_entity_reason, panel_dimension)
    finance_reference = load_finance_reference(config.finance_path, config.finance_scope)
    yearly_drag = compute_yearly_drag(monthly_drag, finance_reference)
    entity_year_drag = compute_entity_year_drag(employee_month_entity_reason, panel_dimension, finance_reference)
    reason_group_year_drag = compute_reason_year_drag(
        employee_month_entity_reason=employee_month_entity_reason,
        finance_reference=finance_reference,
        reason_column="reason_group",
    )
    reason_detail_year_drag = compute_reason_year_drag(
        employee_month_entity_reason=employee_month_entity_reason,
        finance_reference=finance_reference,
        reason_column="reason_detail",
    )

    latest_year = int(yearly_drag["year"].max()) if not yearly_drag.empty else None
    latest_year_entity_drag = (
        entity_year_drag.loc[entity_year_drag["year"] == latest_year].copy()
        if latest_year is not None
        else entity_year_drag.copy()
    )
    latest_year_reason_group_drag = (
        reason_group_year_drag.loc[reason_group_year_drag["year"] == latest_year].copy()
        if latest_year is not None
        else reason_group_year_drag.copy()
    )
    latest_year_reason_detail_drag = (
        reason_detail_year_drag.loc[reason_detail_year_drag["year"] == latest_year].copy()
        if latest_year is not None
        else reason_detail_year_drag.copy()
    )

    latest_year_entity_drag = latest_year_entity_drag.sort_values(
        ["estimated_value_lost", "total_absence_days"], ascending=[False, False]
    ).reset_index(drop=True)
    latest_year_reason_group_drag = latest_year_reason_group_drag.sort_values(
        ["estimated_value_lost", "total_absence_days"], ascending=[False, False]
    ).reset_index(drop=True)
    latest_year_reason_detail_drag = latest_year_reason_detail_drag.sort_values(
        ["estimated_value_lost", "total_absence_days"], ascending=[False, False]
    ).reset_index(drop=True)

    return KPI4Result(
        absence_standardized_rows=absence_standardized,
        employee_month_entity_reason=employee_month_entity_reason,
        monthly_drag=monthly_drag,
        yearly_drag=yearly_drag,
        entity_year_drag=entity_year_drag,
        reason_group_year_drag=reason_group_year_drag,
        reason_detail_year_drag=reason_detail_year_drag,
        latest_year_entity_drag=latest_year_entity_drag,
        latest_year_reason_group_drag=latest_year_reason_group_drag,
        latest_year_reason_detail_drag=latest_year_reason_detail_drag,
    )


def summarize_kpi4(result: KPI4Result) -> list[str]:
    """
    Short business interpretation for KPI 4 outputs.
    """
    yearly = result.yearly_drag
    if yearly.empty:
        return ["No KPI 4 records were generated."]

    latest = yearly.sort_values("year").iloc[-1]
    latest_year = int(latest["year"])

    lines = [
        (
            f"Latest year: {latest_year}. Total absence days = {latest['total_absence_days']:,.1f}, "
            f"Lost FTE = {latest['lost_fte']:,.1f}, Absence Productivity Drag = {latest['absence_productivity_drag']:.2%}."
        )
    ]

    if pd.notna(latest.get("estimated_value_lost")):
        lines.append(
            f"Estimated value lost in {latest_year}: {latest['estimated_value_lost']:,.2f} "
            "(Lost FTE multiplied by HCVA per FTE)."
        )

    if len(yearly) >= 2:
        first = yearly.sort_values("year").iloc[0]
        days_delta = latest["total_absence_days"] - first["total_absence_days"]
        lost_fte_delta = latest["lost_fte"] - first["lost_fte"]
        lines.append(
            f"From {int(first['year'])} to {latest_year}, absence days moved by {days_delta:+,.1f} "
            f"and lost FTE moved by {lost_fte_delta:+,.1f}."
        )

    if not result.latest_year_entity_drag.empty:
        top_entity = result.latest_year_entity_drag.iloc[0]
        lines.append(
            f"Top entity drag in {latest_year}: {top_entity['entity']} "
            f"(Lost FTE {top_entity['lost_fte']:,.1f}, value lost {top_entity['estimated_value_lost']:,.2f})."
        )

    if not result.latest_year_reason_group_drag.empty:
        top_reason_group = result.latest_year_reason_group_drag.iloc[0]
        lines.append(
            f"Top absence reason group in {latest_year}: {top_reason_group['reason_group']} "
            f"({top_reason_group['total_absence_days']:,.1f} days)."
        )

    return lines
