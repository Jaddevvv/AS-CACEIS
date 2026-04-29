from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


DEFAULT_PANEL_PATH = Path("Sujet Alberthon/HR Data/Data.xlsx")
DEFAULT_EAE_PATH = Path(
    "Sujet Alberthon/HR Data/20250218 - Stats CACEIS EAE EP 18-02-2025 Version Définitive cloture.xlsx"
)
DEFAULT_TRAINING_PATH = Path("Sujet Alberthon/Training/Training_Records_Unnamed.xlsx")
DEFAULT_QUICK_REVIEW_PATH = Path("Sujet Alberthon/Training/Quick_Review_Unnamed.xlsx")
DEFAULT_COLD_REVIEW_PATH = Path("Sujet Alberthon/Training/Cold_Review_Unnamed.xlsx")


@dataclass(frozen=True)
class KPI3Config:
    panel_path: Path = DEFAULT_PANEL_PATH
    eae_path: Path = DEFAULT_EAE_PATH
    training_path: Path = DEFAULT_TRAINING_PATH
    quick_review_path: Path = DEFAULT_QUICK_REVIEW_PATH
    cold_review_path: Path = DEFAULT_COLD_REVIEW_PATH


@dataclass
class KPI3Result:
    employee_year_table: pd.DataFrame
    latest_year_table: pd.DataFrame
    yearly_summary: pd.DataFrame
    trained_vs_non_trained: pd.DataFrame
    entity_learning: pd.DataFrame
    scatter_training_performance: pd.DataFrame
    scatter_training_impact: pd.DataFrame


def _normalize_id(values: pd.Series) -> pd.Series:
    cleaned = values.astype(str).str.strip()
    return cleaned.replace({"": pd.NA, "nan": pd.NA, "NaN": pd.NA, "None": pd.NA, "NaT": pd.NA})


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip().replace("\xa0", " ")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _extract_event_year(
    frame: pd.DataFrame, date_columns: list[str], fallback_year_column: str | None = None
) -> pd.Series:
    event_date = pd.Series(pd.NaT, index=frame.index, dtype="datetime64[ns]")
    for col in date_columns:
        if col in frame.columns:
            parsed = pd.to_datetime(frame[col], errors="coerce", dayfirst=True)
            event_date = event_date.fillna(parsed)

    if fallback_year_column and fallback_year_column in frame.columns:
        year_values = pd.to_numeric(frame[fallback_year_column], errors="coerce")
        fallback_date = pd.to_datetime(year_values, format="%Y", errors="coerce")
        event_date = event_date.fillna(fallback_date)

    return event_date.dt.year


def build_employee_year_base(panel_path: Path) -> pd.DataFrame:
    """
    KPI_PLAN step 3 foundation:
    Employee-year population used to compare trained vs non-trained employees.
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
            "ENTITY_LABEL_LOCAL": "entity",
            "POSTE_LABEL_LOCAL": "job",
        }
    )
    panel["employee_id"] = _normalize_id(panel["employee_id"])
    panel["period"] = pd.to_datetime(panel["period"], errors="coerce", dayfirst=True)
    panel["year"] = panel["period"].dt.year
    panel = panel.dropna(subset=["employee_id", "period", "year"]).copy()
    panel["year"] = panel["year"].astype(int)

    # Keep the last monthly row in each employee-year to retain a stable segment label.
    ordered = panel.sort_values(["employee_id", "year", "period"])
    base = (
        ordered.groupby(["employee_id", "year"], as_index=False)
        .tail(1)
        .loc[:, ["employee_id", "year", "country", "entity", "job"]]
        .reset_index(drop=True)
    )
    return base


def aggregate_training_records(training_path: Path) -> pd.DataFrame:
    """
    KPI_PLAN step 1:
    Aggregate training records by employee-year.
    """
    raw = pd.read_excel(training_path, sheet_name="Final_CSV")
    needed = ["Employee Code", "Status", "Total_Training_Hours", "Session_ID", "Certifications"]
    missing = [col for col in needed if col not in raw.columns]
    if missing:
        raise ValueError(f"Missing columns in training source: {missing}")

    train = raw.rename(
        columns={
            "Employee Code": "employee_id",
            "Status": "status",
            "Total_Training_Hours": "training_hours",
            "Session_ID": "session_id",
            "Certifications": "certifications",
        }
    )
    train["employee_id"] = _normalize_id(train["employee_id"])
    train["training_hours"] = pd.to_numeric(train["training_hours"], errors="coerce").fillna(0.0)
    train["year"] = _extract_event_year(
        train,
        date_columns=["Session_End_Date", "Seesion_Start_Date"],
        fallback_year_column="Year",
    )
    train["status_norm"] = train["status"].map(_normalize_text)

    effective_status = {"realise", "completed", "completee"}
    train = train[
        train["status_norm"].isin(effective_status)
        | ((train["training_hours"] > 0.0) & train["status_norm"].eq(""))
    ].copy()

    train = train.dropna(subset=["employee_id", "year"]).copy()
    train["year"] = train["year"].astype(int)
    train["certification_flag"] = train["certifications"].map(
        lambda v: 1.0 if _normalize_text(v).startswith("yes") else 0.0
    )
    train["session_non_null"] = train["session_id"].notna().astype(float)

    grouped = (
        train.groupby(["employee_id", "year"], as_index=False)
        .agg(
            training_hours=("training_hours", "sum"),
            training_count=("session_non_null", "sum"),
            certification_flag=("certification_flag", "max"),
        )
        .sort_values(["employee_id", "year"])
        .reset_index(drop=True)
    )
    return grouped


def aggregate_quick_reviews(quick_review_path: Path) -> pd.DataFrame:
    """
    KPI_PLAN step 2 (part):
    Aggregate quick review scores by employee-year.
    """
    raw = pd.read_excel(quick_review_path, sheet_name="Data")
    needed = ["Matricule", "Note générale"]
    missing = [col for col in needed if col not in raw.columns]
    if missing:
        raise ValueError(f"Missing columns in quick-review source: {missing}")

    quick = raw.rename(columns={"Matricule": "employee_id", "Note générale": "quick_review_score"})
    quick["employee_id"] = _normalize_id(quick["employee_id"])
    quick["year"] = _extract_event_year(
        quick,
        date_columns=["Date de fin de session", "Date de début de session", "Date"],
    )
    quick["quick_review_score"] = pd.to_numeric(quick["quick_review_score"], errors="coerce")
    quick["session_non_null"] = quick.get("ID de session", pd.Series(index=quick.index)).notna().astype(float)
    quick = quick.dropna(subset=["employee_id", "year", "quick_review_score"]).copy()
    quick["year"] = quick["year"].astype(int)

    grouped = (
        quick.groupby(["employee_id", "year"], as_index=False)
        .agg(
            quick_review_score=("quick_review_score", "mean"),
            quick_review_count=("session_non_null", "sum"),
        )
        .sort_values(["employee_id", "year"])
        .reset_index(drop=True)
    )
    return grouped


def _map_cold_answer(value: object) -> float:
    normalized = _normalize_text(value)
    if normalized == "":
        return float("nan")
    if normalized == "oui":
        return 1.0
    if normalized.startswith("oui tout a fait"):
        return 1.0
    if normalized.startswith("oui en partie"):
        return 0.5
    if normalized.startswith("non"):
        return 0.0
    return float("nan")


def _select_cold_answer_columns(columns: list[object]) -> list[str]:
    patterns = [
        "considerez vous que cette formation vous a permis",
        "la formation a t elle repondu a vos attentes initiales",
        "estimez vous que la formation etait en adequation",
        "recommanderiez vous ce stage",
        "utilisez vous les connaissances acquises",
    ]
    selected: list[str] = []
    for col in columns:
        col_name = str(col)
        normalized = _normalize_text(col_name)
        if any(pattern in normalized for pattern in patterns):
            selected.append(col_name)
    return selected


def aggregate_cold_reviews(cold_review_path: Path) -> pd.DataFrame:
    """
    KPI_PLAN step 2 (part):
    Aggregate converted cold-review impact score by employee-year.
    """
    raw = pd.read_excel(cold_review_path, sheet_name="Data")
    if "Matricule" not in raw.columns:
        raise ValueError("Missing 'Matricule' column in cold-review source.")

    answer_columns = _select_cold_answer_columns(list(raw.columns))
    if not answer_columns:
        raise ValueError("No cold-review impact answer columns detected.")

    cold = raw.rename(columns={"Matricule": "employee_id"})
    cold["employee_id"] = _normalize_id(cold["employee_id"])
    cold["year"] = _extract_event_year(
        cold,
        date_columns=["Date de fin de session", "Date de début de session", "Date"],
    )
    cold["status_norm"] = cold.get("Status", pd.Series(index=cold.index)).map(_normalize_text)

    mapped = cold.loc[:, answer_columns].apply(lambda col: col.map(_map_cold_answer))
    cold["cold_impact_score"] = mapped.mean(axis=1, skipna=True)

    blocked_status = {"annulee", "non envoyee", "en attente"}
    valid_rows = ~cold["status_norm"].isin(blocked_status) | cold["status_norm"].eq("")

    cold = cold[valid_rows].dropna(subset=["employee_id", "year", "cold_impact_score"]).copy()
    cold["year"] = cold["year"].astype(int)

    grouped = (
        cold.groupby(["employee_id", "year"], as_index=False)
        .agg(
            cold_impact_score=("cold_impact_score", "mean"),
            cold_review_count=("cold_impact_score", "count"),
        )
        .sort_values(["employee_id", "year"])
        .reset_index(drop=True)
    )
    return grouped


def load_eae_scores(eae_path: Path) -> pd.DataFrame:
    """
    KPI_PLAN step 3 (part):
    Join annual performance score from EAE.
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
    perf = perf.dropna(subset=["employee_id", "year", "performance_score"]).copy()
    perf["year"] = perf["year"].astype(int)

    return (
        perf.groupby(["employee_id", "year"], as_index=False)["performance_score"]
        .mean()
        .sort_values(["employee_id", "year"])
        .reset_index(drop=True)
    )


def build_learning_performance_table(
    employee_year_base: pd.DataFrame,
    training_agg: pd.DataFrame,
    quick_agg: pd.DataFrame,
    cold_agg: pd.DataFrame,
    eae_scores: pd.DataFrame,
) -> pd.DataFrame:
    """
    KPI_PLAN step 3:
    Join training, review scores, and EAE performance.
    """
    table = employee_year_base.merge(training_agg, on=["employee_id", "year"], how="left")
    table = table.merge(quick_agg, on=["employee_id", "year"], how="left")
    table = table.merge(cold_agg, on=["employee_id", "year"], how="left")
    table = table.merge(eae_scores, on=["employee_id", "year"], how="left")

    for col in ["training_hours", "training_count", "quick_review_count", "cold_review_count"]:
        if col in table.columns:
            table[col] = pd.to_numeric(table[col], errors="coerce").fillna(0.0)

    table["certification_flag"] = pd.to_numeric(table.get("certification_flag"), errors="coerce").fillna(0.0)
    table["certification_flag"] = table["certification_flag"].clip(lower=0.0, upper=1.0)

    table["quick_review_score"] = pd.to_numeric(table.get("quick_review_score"), errors="coerce")
    table["cold_impact_score"] = pd.to_numeric(table.get("cold_impact_score"), errors="coerce")

    table["trained_flag"] = ((table["training_hours"] > 0.0) | (table["training_count"] > 0.0)).astype(int)

    positive_hours_p95 = (
        table.loc[table["training_hours"] > 0.0]
        .groupby("year")["training_hours"]
        .quantile(0.95)
        .rename("p95_hours")
    )
    training_denominator = table["year"].map(positive_hours_p95).fillna(1.0)
    training_denominator = training_denominator.where(training_denominator > 0.0, 1.0)

    table["training_hours_norm"] = (table["training_hours"] / training_denominator).clip(lower=0.0, upper=1.0)
    table["quick_review_norm"] = ((table["quick_review_score"] - 1.0) / 4.0).clip(lower=0.0, upper=1.0)
    table["cold_impact_norm"] = table["cold_impact_score"].clip(lower=0.0, upper=1.0)

    table["training_hours_norm"] = table["training_hours_norm"].fillna(0.0)
    table["quick_review_norm"] = table["quick_review_norm"].fillna(0.0)
    table["cold_impact_norm"] = table["cold_impact_norm"].fillna(0.0)

    table["learning_to_performance_index"] = (
        0.40 * table["training_hours_norm"]
        + 0.30 * table["cold_impact_norm"]
        + 0.20 * table["quick_review_norm"]
        + 0.10 * table["certification_flag"]
    ).clip(lower=0.0, upper=1.0)

    return table.sort_values(["year", "learning_to_performance_index"], ascending=[True, False]).reset_index(
        drop=True
    )


def build_kpi3_result(config: KPI3Config) -> KPI3Result:
    """
    KPI_PLAN steps 1-5 end-to-end builder.
    """
    base = build_employee_year_base(config.panel_path)
    training_agg = aggregate_training_records(config.training_path)
    quick_agg = aggregate_quick_reviews(config.quick_review_path)
    cold_agg = aggregate_cold_reviews(config.cold_review_path)
    eae_scores = load_eae_scores(config.eae_path)

    table = build_learning_performance_table(
        employee_year_base=base,
        training_agg=training_agg,
        quick_agg=quick_agg,
        cold_agg=cold_agg,
        eae_scores=eae_scores,
    )

    latest_year = int(table["year"].max()) if not table.empty else None
    latest_year_table = (
        table.loc[table["year"] == latest_year].sort_values("learning_to_performance_index", ascending=False)
        if latest_year is not None
        else table.copy()
    ).reset_index(drop=True)

    yearly_summary = (
        table.groupby("year", as_index=False)
        .agg(
            employees=("employee_id", "nunique"),
            trained_share=("trained_flag", "mean"),
            certified_share=("certification_flag", "mean"),
            avg_training_hours=("training_hours", "mean"),
            avg_training_count=("training_count", "mean"),
            avg_quick_review_score=("quick_review_score", "mean"),
            avg_cold_impact_score=("cold_impact_score", "mean"),
            avg_learning_index=("learning_to_performance_index", "mean"),
            avg_performance_score=("performance_score", "mean"),
            performance_coverage=("performance_score", lambda s: float(s.notna().mean())),
        )
        .sort_values("year")
        .reset_index(drop=True)
    )

    status_summary = (
        table.groupby(["year", "trained_flag"], as_index=False)
        .agg(
            employees=("employee_id", "nunique"),
            avg_performance_score=("performance_score", "mean"),
            avg_learning_index=("learning_to_performance_index", "mean"),
            avg_training_hours=("training_hours", "mean"),
            avg_cold_impact_score=("cold_impact_score", "mean"),
        )
        .sort_values(["year", "trained_flag"])
        .reset_index(drop=True)
    )

    trained = status_summary[status_summary["trained_flag"] == 1].rename(
        columns={
            "employees": "trained_employees",
            "avg_performance_score": "trained_avg_performance",
            "avg_learning_index": "trained_avg_learning_index",
            "avg_training_hours": "trained_avg_training_hours",
            "avg_cold_impact_score": "trained_avg_cold_impact_score",
        }
    )
    non_trained = status_summary[status_summary["trained_flag"] == 0].rename(
        columns={
            "employees": "non_trained_employees",
            "avg_performance_score": "non_trained_avg_performance",
            "avg_learning_index": "non_trained_avg_learning_index",
            "avg_training_hours": "non_trained_avg_training_hours",
            "avg_cold_impact_score": "non_trained_avg_cold_impact_score",
        }
    )

    trained_vs_non_trained = trained.merge(non_trained, on="year", how="outer", suffixes=("", "_drop"))
    trained_vs_non_trained = trained_vs_non_trained.loc[
        :,
        [
            "year",
            "trained_employees",
            "non_trained_employees",
            "trained_avg_performance",
            "non_trained_avg_performance",
            "trained_avg_learning_index",
            "non_trained_avg_learning_index",
            "trained_avg_training_hours",
            "non_trained_avg_training_hours",
            "trained_avg_cold_impact_score",
            "non_trained_avg_cold_impact_score",
        ],
    ].sort_values("year")
    trained_vs_non_trained["performance_gap_trained_minus_non_trained"] = (
        trained_vs_non_trained["trained_avg_performance"]
        - trained_vs_non_trained["non_trained_avg_performance"]
    )
    trained_vs_non_trained["learning_index_gap_trained_minus_non_trained"] = (
        trained_vs_non_trained["trained_avg_learning_index"]
        - trained_vs_non_trained["non_trained_avg_learning_index"]
    )
    trained_vs_non_trained = trained_vs_non_trained.reset_index(drop=True)

    entity_learning = (
        latest_year_table.groupby("entity", as_index=False)
        .agg(
            employees=("employee_id", "nunique"),
            trained_share=("trained_flag", "mean"),
            avg_learning_index=("learning_to_performance_index", "mean"),
            avg_training_hours=("training_hours", "mean"),
            avg_performance_score=("performance_score", "mean"),
        )
        .sort_values(["avg_learning_index", "employees"], ascending=[False, False])
        .reset_index(drop=True)
    )

    scatter_training_performance = (
        table.loc[(table["training_hours"] > 0.0) & table["performance_score"].notna()]
        .loc[
            :,
            [
                "employee_id",
                "year",
                "country",
                "entity",
                "job",
                "training_hours",
                "training_count",
                "performance_score",
                "learning_to_performance_index",
            ],
        ]
        .reset_index(drop=True)
    )

    scatter_training_impact = (
        table.loc[(table["training_hours"] > 0.0) & table["cold_impact_score"].notna()]
        .loc[
            :,
            [
                "employee_id",
                "year",
                "country",
                "entity",
                "job",
                "training_hours",
                "training_count",
                "cold_impact_score",
                "learning_to_performance_index",
            ],
        ]
        .reset_index(drop=True)
    )

    return KPI3Result(
        employee_year_table=table,
        latest_year_table=latest_year_table,
        yearly_summary=yearly_summary,
        trained_vs_non_trained=trained_vs_non_trained,
        entity_learning=entity_learning,
        scatter_training_performance=scatter_training_performance,
        scatter_training_impact=scatter_training_impact,
    )


def summarize_kpi3(result: KPI3Result) -> list[str]:
    """
    KPI_PLAN steps 4-5:
    Short business interpretation for learning and performance signal.
    """
    table = result.employee_year_table
    if table.empty:
        return ["No KPI 3 records were generated."]

    latest_year = int(table["year"].max())
    latest = table[table["year"] == latest_year]
    avg_index = float(latest["learning_to_performance_index"].mean())
    trained_share = float(latest["trained_flag"].mean())
    lines = [
        (
            f"Latest year: {latest_year}. Average Learning-to-Performance Index is {avg_index:.3f}, "
            f"with {trained_share:.1%} employees trained."
        )
    ]

    compare_valid = result.trained_vs_non_trained.dropna(
        subset=["performance_gap_trained_minus_non_trained"]
    ).sort_values("year")
    if not compare_valid.empty:
        row = compare_valid.iloc[-1]
        lines.append(
            "Performance gap (trained - non-trained) in latest year with EAE coverage "
            f"({int(row['year'])}): {row['performance_gap_trained_minus_non_trained']:+.3f} points."
        )

    if not result.scatter_training_performance.empty:
        corr_perf = result.scatter_training_performance["training_hours"].corr(
            result.scatter_training_performance["performance_score"]
        )
        if pd.notna(corr_perf):
            lines.append(f"Correlation between training hours and performance score: {corr_perf:+.3f}.")

    if not result.scatter_training_impact.empty:
        corr_impact = result.scatter_training_impact["training_hours"].corr(
            result.scatter_training_impact["cold_impact_score"]
        )
        if pd.notna(corr_impact):
            lines.append(f"Correlation between training hours and cold impact score: {corr_impact:+.3f}.")

    if not result.entity_learning.empty:
        top_entity = result.entity_learning.iloc[0]["entity"]
        lines.append(f"Highest learning index entity in latest year: {top_entity}.")

    return lines
