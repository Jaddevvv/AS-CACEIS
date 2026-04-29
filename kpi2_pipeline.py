from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


DEFAULT_PANEL_PATH = Path("Sujet Alberthon/HR Data/Data.xlsx")
DEFAULT_EAE_PATH = Path(
    "Sujet Alberthon/HR Data/20250218 - Stats CACEIS EAE EP 18-02-2025 Version Définitive cloture.xlsx"
)
DEFAULT_TRAINING_PATH = Path("Sujet Alberthon/Training/Training_Records_Unnamed.xlsx")
DEFAULT_ABSENCE_PATHS = (
    Path("Sujet Alberthon/HR Data/Absentéisme_-_détail_affectation_-_Bilan_social.xlsx"),
    Path("Sujet Alberthon/HR Data/Absentéisme_-_détail_affectation_-_Bilan_social (1).xlsx"),
    Path(
        "Sujet Alberthon/HR Data/20260121 - Absentéisme_-_détail_affectation_-_Bilan_social 2025.xlsx"
    ),
)


@dataclass(frozen=True)
class KPI2Config:
    panel_path: Path = DEFAULT_PANEL_PATH
    eae_path: Path = DEFAULT_EAE_PATH
    training_path: Path = DEFAULT_TRAINING_PATH
    absence_paths: tuple[Path, ...] = DEFAULT_ABSENCE_PATHS


@dataclass
class KPI2Result:
    risk_table: pd.DataFrame
    latest_risk_table: pd.DataFrame
    entity_risk: pd.DataFrame
    job_risk: pd.DataFrame
    segment_risk: pd.DataFrame
    risk_trend: pd.DataFrame


def _normalize_id(values: pd.Series) -> pd.Series:
    cleaned = values.astype(str).str.strip()
    return cleaned.replace({"": pd.NA, "nan": pd.NA, "NaN": pd.NA, "None": pd.NA, "NaT": pd.NA})


def _to_month_start(values: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(values, errors="coerce", dayfirst=True)
    return parsed.dt.to_period("M").dt.to_timestamp()


def _months_diff(start: pd.Series, end: pd.Series) -> pd.Series:
    delta = (end.dt.year - start.dt.year) * 12 + (end.dt.month - start.dt.month)
    delta = delta.where(start.notna() & end.notna())
    return delta.clip(lower=0)


def build_employee_month_table(panel_path: Path) -> pd.DataFrame:
    """
    KPI_PLAN step 1:
    Build employee-month table from Data.xlsx > Sheet1.
    """
    raw = pd.read_excel(panel_path, sheet_name="Sheet1")

    use_cols = [
        "COUNTRY_GROUP",
        "COUNTRY_GROUP_LABEL_EN",
        "PERIOD",
        "ID Employee",
        "Age range",
        "SEXE_GROUP_LABEL_EN",
        "CONTRACT_GROUP_LABEL_EN",
        "DATE_ENTRY_CACEIS",
        "DATE_ENTRY_POSTE",
        "POSTE_LABEL_LOCAL",
        "ENTITY_LABEL_LOCAL",
    ]

    missing_cols = [col for col in use_cols if col not in raw.columns]
    if missing_cols:
        raise ValueError(f"Missing columns in panel source: {missing_cols}")

    panel = raw.loc[:, use_cols].rename(
        columns={
            "COUNTRY_GROUP": "country_code",
            "COUNTRY_GROUP_LABEL_EN": "country",
            "PERIOD": "period",
            "ID Employee": "employee_id",
            "Age range": "age_range",
            "SEXE_GROUP_LABEL_EN": "gender",
            "CONTRACT_GROUP_LABEL_EN": "contract_type",
            "DATE_ENTRY_CACEIS": "date_entry_caceis",
            "DATE_ENTRY_POSTE": "date_entry_poste",
            "POSTE_LABEL_LOCAL": "job",
            "ENTITY_LABEL_LOCAL": "entity",
        }
    )

    panel["employee_id"] = _normalize_id(panel["employee_id"])
    panel["period"] = _to_month_start(panel["period"])
    panel["date_entry_caceis"] = pd.to_datetime(panel["date_entry_caceis"], errors="coerce")
    panel["date_entry_poste"] = pd.to_datetime(panel["date_entry_poste"], errors="coerce")
    panel = panel.dropna(subset=["employee_id", "period"]).copy()

    panel = panel.drop_duplicates(subset=["employee_id", "period"], keep="first")

    panel["tenure_caceis_months"] = _months_diff(panel["date_entry_caceis"], panel["period"])
    panel["months_in_current_post"] = _months_diff(panel["date_entry_poste"], panel["period"])

    return panel.sort_values(["employee_id", "period"]).reset_index(drop=True)


def detect_left_next_6m(employee_month: pd.DataFrame) -> pd.DataFrame:
    """
    KPI_PLAN step 2:
    Detect employees who disappear from the monthly panel for the following 6 months.
    """
    presence = employee_month[["employee_id", "period"]].drop_duplicates()
    ordered_months = sorted(presence["period"].unique())

    pivot = (
        presence.assign(present=1.0)
        .pivot(index="employee_id", columns="period", values="present")
        .reindex(columns=ordered_months)
        .fillna(0.0)
    )

    future_presence = 0.0
    for step in range(1, 7):
        future_presence = future_presence + pivot.shift(-step, axis=1).fillna(0.0)

    left_flag = (future_presence == 0.0).astype(float)
    if left_flag.shape[1] >= 6:
        left_flag.iloc[:, -6:] = float("nan")

    long = (
        left_flag.reset_index()
        .melt(id_vars="employee_id", var_name="period", value_name="left_next_6m")
        .sort_values(["employee_id", "period"])
        .reset_index(drop=True)
    )
    long["period"] = pd.to_datetime(long["period"], errors="coerce")
    return long


def _read_absence_rows(file_path: Path) -> pd.DataFrame:
    required = {"Employee Code", "Date Absence", "Jours Ouvrés Absence"}
    xl = pd.ExcelFile(file_path)

    chosen_sheet: str | None = None
    chosen_header: int | None = None

    for sheet in xl.sheet_names:
        for header_row in range(0, 4):
            try:
                preview = pd.read_excel(file_path, sheet_name=sheet, header=header_row, nrows=0)
            except Exception:
                continue
            preview_cols = {str(col).strip() for col in preview.columns}
            if required.issubset(preview_cols):
                chosen_sheet = sheet
                chosen_header = header_row
                break
        if chosen_sheet is not None:
            break

    if chosen_sheet is None or chosen_header is None:
        raise ValueError(f"Could not locate absence headers in file: {file_path}")

    df = pd.read_excel(
        file_path,
        sheet_name=chosen_sheet,
        header=chosen_header,
        usecols=["Employee Code", "Date Absence", "Jours Ouvrés Absence"],
    ).rename(
        columns={
            "Employee Code": "employee_id",
            "Date Absence": "absence_date",
            "Jours Ouvrés Absence": "absence_days",
        }
    )

    df["employee_id"] = _normalize_id(df["employee_id"])
    df["period"] = _to_month_start(df["absence_date"])
    df["absence_days"] = pd.to_numeric(df["absence_days"], errors="coerce").fillna(0.0)
    return df.dropna(subset=["employee_id", "period"])[["employee_id", "period", "absence_days"]]


def load_absence_monthly(absence_paths: Iterable[Path]) -> pd.DataFrame:
    """
    KPI_PLAN step 3 (part):
    Aggregate absence by employee-month.
    """
    frames: list[pd.DataFrame] = []
    for path in absence_paths:
        if path.exists():
            frames.append(_read_absence_rows(path))

    if not frames:
        return pd.DataFrame(columns=["employee_id", "period", "absence_days"])

    all_absence = pd.concat(frames, ignore_index=True)
    return (
        all_absence.groupby(["employee_id", "period"], as_index=False)["absence_days"]
        .sum()
        .sort_values(["employee_id", "period"])
        .reset_index(drop=True)
    )


def load_training_monthly(training_path: Path) -> pd.DataFrame:
    """
    KPI_PLAN step 3 (part):
    Aggregate training by employee-month.
    """
    raw = pd.read_excel(training_path, sheet_name="Final_CSV")

    if "Employee Code" not in raw.columns or "Total_Training_Hours" not in raw.columns:
        raise ValueError("Training source is missing required columns.")

    train = raw.rename(
        columns={
            "Employee Code": "employee_id",
            "Session_End_Date": "session_end_date",
            "Seesion_Start_Date": "session_start_date",
            "Total_Training_Hours": "training_hours",
            "Year": "year",
        }
    )

    train["employee_id"] = _normalize_id(train["employee_id"])
    train["training_hours"] = pd.to_numeric(train["training_hours"], errors="coerce").fillna(0.0)
    train["session_end_date"] = pd.to_datetime(train["session_end_date"], errors="coerce", dayfirst=True)
    train["session_start_date"] = pd.to_datetime(
        train["session_start_date"], errors="coerce", dayfirst=True
    )
    fallback_year = pd.to_numeric(train.get("year"), errors="coerce")
    fallback_date = pd.to_datetime(fallback_year, format="%Y", errors="coerce")
    event_date = train["session_end_date"].fillna(train["session_start_date"]).fillna(fallback_date)

    train["period"] = event_date.dt.to_period("M").dt.to_timestamp()
    train = train.dropna(subset=["employee_id", "period"])

    return (
        train.groupby(["employee_id", "period"], as_index=False)["training_hours"]
        .sum()
        .sort_values(["employee_id", "period"])
        .reset_index(drop=True)
    )


def load_eae_scores(eae_path: Path) -> pd.DataFrame:
    """
    KPI_PLAN step 3 (part):
    Extract performance score from EAE data.
    """
    raw = pd.read_excel(eae_path, sheet_name="Database")
    raw.columns = [col.strip() if isinstance(col, str) else col for col in raw.columns]

    needed = ["IUG", "Année", "Note de performance"]
    missing = [col for col in needed if col not in raw.columns]
    if missing:
        raise ValueError(f"Missing columns in EAE source: {missing}")

    perf = raw.loc[:, needed].rename(
        columns={"IUG": "employee_id", "Année": "year", "Note de performance": "performance_score"}
    )

    perf["employee_id"] = _normalize_id(perf["employee_id"])
    perf["year"] = pd.to_numeric(perf["year"], errors="coerce")
    perf["performance_score"] = pd.to_numeric(perf["performance_score"], errors="coerce")
    perf = perf.dropna(subset=["employee_id", "year", "performance_score"])
    perf["year"] = perf["year"].astype(int)

    return (
        perf.groupby(["employee_id", "year"], as_index=False)["performance_score"]
        .mean()
        .sort_values(["employee_id", "year"])
        .reset_index(drop=True)
    )


def _attach_trailing_12m(
    panel: pd.DataFrame, monthly_values: pd.DataFrame, input_col: str, output_col: str
) -> pd.DataFrame:
    if monthly_values.empty:
        with_default = panel.copy()
        with_default[output_col] = 0.0
        return with_default

    all_months = pd.date_range(panel["period"].min(), panel["period"].max(), freq="MS")
    all_ids = panel["employee_id"].dropna().unique()
    full_index = pd.MultiIndex.from_product([all_ids, all_months], names=["employee_id", "period"])

    series = monthly_values.set_index(["employee_id", "period"])[input_col]
    dense = series.reindex(full_index, fill_value=0.0).reset_index(name=input_col)
    dense[output_col] = dense.groupby("employee_id")[input_col].transform(
        lambda s: s.rolling(window=12, min_periods=1).sum()
    )

    return panel.merge(dense[["employee_id", "period", output_col]], on=["employee_id", "period"], how="left")


def enrich_kpi2_features(
    employee_month: pd.DataFrame,
    left_next_6m: pd.DataFrame,
    eae_scores: pd.DataFrame,
    training_monthly: pd.DataFrame,
    absence_monthly: pd.DataFrame,
) -> pd.DataFrame:
    """
    KPI_PLAN step 3:
    Join EAE, training, and absence features to employee-month data.
    """
    base = employee_month.merge(left_next_6m, on=["employee_id", "period"], how="left")
    base = _attach_trailing_12m(base, absence_monthly, "absence_days", "absence_days_12m")
    base = _attach_trailing_12m(base, training_monthly, "training_hours", "training_hours_12m")

    base["year"] = base["period"].dt.year
    joined = base.merge(eae_scores, on=["employee_id", "year"], how="left")

    emp_perf_avg = eae_scores.groupby("employee_id")["performance_score"].mean()
    global_perf_median = eae_scores["performance_score"].median()
    joined["performance_score"] = joined["performance_score"].fillna(joined["employee_id"].map(emp_perf_avg))
    joined["performance_score"] = joined["performance_score"].fillna(global_perf_median)

    joined["absence_days_12m"] = joined["absence_days_12m"].fillna(0.0)
    joined["training_hours_12m"] = joined["training_hours_12m"].fillna(0.0)
    joined["tenure_caceis_months"] = joined["tenure_caceis_months"].fillna(0.0)
    joined["months_in_current_post"] = joined["months_in_current_post"].fillna(0.0)

    return joined


def compute_risk_scores(kpi2_features: pd.DataFrame) -> pd.DataFrame:
    """
    KPI_PLAN step 4:
    Create weighted Workforce Value-at-Risk score.
    """
    df = kpi2_features.copy()

    df["new_joiner_risk"] = ((24.0 - df["tenure_caceis_months"]).clip(lower=0.0, upper=24.0)) / 24.0
    df["low_performance_risk"] = ((5.0 - df["performance_score"]).clip(lower=0.0, upper=4.0)) / 4.0

    absence_p90 = df["absence_days_12m"].quantile(0.90)
    if pd.isna(absence_p90) or absence_p90 <= 0:
        absence_p90 = 1.0
    df["high_absence_risk"] = (df["absence_days_12m"] / absence_p90).clip(lower=0.0, upper=1.0)

    training_p75 = df["training_hours_12m"].quantile(0.75)
    if pd.isna(training_p75) or training_p75 <= 0:
        training_p75 = 1.0
    df["low_training_risk"] = 1.0 - (df["training_hours_12m"] / training_p75).clip(lower=0.0, upper=1.0)

    df["long_time_in_post_risk"] = (
        (df["months_in_current_post"] - 36.0) / 60.0
    ).clip(lower=0.0, upper=1.0)

    segment_cols = ["country", "entity", "job"]
    labeled = df.dropna(subset=["left_next_6m"]).copy()
    global_leave_rate = labeled["left_next_6m"].mean() if not labeled.empty else 0.0
    smoothing = 20.0

    if not labeled.empty:
        segment_stats = (
            labeled.groupby(segment_cols)["left_next_6m"]
            .agg(["sum", "count"])
            .reset_index()
            .rename(columns={"sum": "leavers", "count": "observations"})
        )
        segment_stats["segment_risk"] = (
            segment_stats["leavers"] + smoothing * global_leave_rate
        ) / (segment_stats["observations"] + smoothing)
        df = df.merge(segment_stats[segment_cols + ["segment_risk"]], on=segment_cols, how="left")
    else:
        df["segment_risk"] = global_leave_rate

    df["segment_risk"] = df["segment_risk"].fillna(global_leave_rate).clip(lower=0.0, upper=1.0)

    df["risk_score"] = (
        0.25 * df["new_joiner_risk"]
        + 0.20 * df["low_performance_risk"]
        + 0.20 * df["high_absence_risk"]
        + 0.15 * df["low_training_risk"]
        + 0.10 * df["long_time_in_post_risk"]
        + 0.10 * df["segment_risk"]
    ).clip(lower=0.0, upper=1.0)

    q_low = float(df["risk_score"].quantile(0.33))
    q_high = float(df["risk_score"].quantile(0.67))
    if q_high <= q_low:
        q_low, q_high = 0.33, 0.66

    df["risk_band"] = pd.cut(
        df["risk_score"],
        bins=[-0.001, q_low, q_high, 1.0],
        labels=["Low", "Medium", "High"],
        include_lowest=True,
    )

    return df.sort_values(["period", "risk_score"], ascending=[True, False]).reset_index(drop=True)


def build_kpi2_result(config: KPI2Config) -> KPI2Result:
    """
    KPI_PLAN steps 1-5 end-to-end builder.
    """
    panel = build_employee_month_table(config.panel_path)
    left_next_6m = detect_left_next_6m(panel)
    absence_monthly = load_absence_monthly(config.absence_paths)
    training_monthly = load_training_monthly(config.training_path)
    eae_scores = load_eae_scores(config.eae_path)

    features = enrich_kpi2_features(
        employee_month=panel,
        left_next_6m=left_next_6m,
        eae_scores=eae_scores,
        training_monthly=training_monthly,
        absence_monthly=absence_monthly,
    )
    scored = compute_risk_scores(features)

    latest_period = scored["period"].max()
    latest = scored[scored["period"] == latest_period].copy()

    latest_risk_table = latest.sort_values("risk_score", ascending=False).reset_index(drop=True)

    entity_risk = (
        latest.groupby("entity", as_index=False)
        .agg(
            employees=("employee_id", "nunique"),
            avg_risk_score=("risk_score", "mean"),
            high_risk_share=("risk_band", lambda s: float((s == "High").mean())),
        )
        .sort_values(["avg_risk_score", "employees"], ascending=[False, False])
        .reset_index(drop=True)
    )

    job_risk = (
        latest.groupby("job", as_index=False)
        .agg(
            employees=("employee_id", "nunique"),
            avg_risk_score=("risk_score", "mean"),
            high_risk_share=("risk_band", lambda s: float((s == "High").mean())),
        )
        .sort_values(["avg_risk_score", "employees"], ascending=[False, False])
        .reset_index(drop=True)
    )

    segment_risk = (
        latest.groupby(["country", "entity", "job"], as_index=False)
        .agg(
            employees=("employee_id", "nunique"),
            avg_risk_score=("risk_score", "mean"),
            high_risk_share=("risk_band", lambda s: float((s == "High").mean())),
        )
        .sort_values(["avg_risk_score", "employees"], ascending=[False, False])
        .reset_index(drop=True)
    )

    risk_trend = (
        scored.groupby("period", as_index=False)
        .agg(
            avg_risk_score=("risk_score", "mean"),
            high_risk_share=("risk_band", lambda s: float((s == "High").mean())),
            observed_leave_rate=("left_next_6m", "mean"),
            employees=("employee_id", "nunique"),
        )
        .sort_values("period")
        .reset_index(drop=True)
    )

    return KPI2Result(
        risk_table=scored,
        latest_risk_table=latest_risk_table,
        entity_risk=entity_risk,
        job_risk=job_risk,
        segment_risk=segment_risk,
        risk_trend=risk_trend,
    )


def summarize_kpi2(result: KPI2Result) -> list[str]:
    """
    KPI_PLAN step 5:
    Provide short business interpretation for top-risk segments.
    """
    latest = result.latest_risk_table
    trend = result.risk_trend

    if latest.empty:
        return ["No risk records were generated."]

    latest_period = latest["period"].max()
    high_share = float((latest["risk_band"] == "High").mean())
    avg_risk = float(latest["risk_score"].mean())
    top_entity = result.entity_risk.iloc[0]["entity"] if not result.entity_risk.empty else "N/A"
    top_job = result.job_risk.iloc[0]["job"] if not result.job_risk.empty else "N/A"

    messages = [
        (
            f"Latest month in panel: {latest_period:%Y-%m}. "
            f"Average risk score is {avg_risk:.3f} with {high_share:.1%} employees in High risk."
        ),
        f"Highest-risk entity (by average score): {top_entity}.",
        f"Highest-risk job family (by average score): {top_job}.",
    ]

    if not trend.empty and trend["avg_risk_score"].notna().sum() >= 2:
        start = trend.iloc[0]
        end = trend.iloc[-1]
        delta = float(end["avg_risk_score"] - start["avg_risk_score"])
        messages.append(
            f"Average risk score trend moved from {start['avg_risk_score']:.3f} "
            f"to {end['avg_risk_score']:.3f} ({delta:+.3f})."
        )

    return messages
