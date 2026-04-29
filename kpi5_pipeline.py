from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


DEFAULT_DATA_PATH = Path("Sujet Alberthon/HR Data/Data.xlsx")
DEFAULT_PANEL_PATH = DEFAULT_DATA_PATH
DEFAULT_COMPENSATION_PATH = DEFAULT_DATA_PATH
DEFAULT_EAE_PATH = Path(
    "Sujet Alberthon/HR Data/20250218 - Stats CACEIS EAE EP 18-02-2025 Version Définitive cloture.xlsx"
)


@dataclass(frozen=True)
class KPI5Config:
    panel_path: Path = DEFAULT_PANEL_PATH
    compensation_path: Path = DEFAULT_COMPENSATION_PATH
    eae_path: Path = DEFAULT_EAE_PATH


@dataclass
class KPI5Result:
    role_cost_table: pd.DataFrame
    latest_year_table: pd.DataFrame
    country_year_summary: pd.DataFrame
    quadrant_summary: pd.DataFrame
    join_coverage: pd.DataFrame
    efficiency_risk_roles: pd.DataFrame
    strategic_high_value_roles: pd.DataFrame
    retention_risk_roles: pd.DataFrame


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


def _extract_year(text: object) -> int | None:
    if text is None:
        return None
    match = re.search(r"(\d{4})", str(text))
    return int(match.group(1)) if match else None


def _map_eae_country(pays: object, legal_employer: object) -> str | None:
    pays_code = str(pays).strip().upper()
    if pays_code == "FR":
        return "France"
    if pays_code in {"LU", "LUX", "INT"}:
        # In this EAE extract, Luxembourg population is coded as INT.
        return "Luxembourg"

    employer = _normalize_text(legal_employer)
    if "luxembourg" in employer or "luxcellence" in employer:
        return "Luxembourg"
    if "france" in employer:
        return "France"
    return None


def _weighted_average(values: pd.Series, weights: pd.Series) -> float:
    valid = values.notna() & weights.notna() & (weights >= 0.0)
    if not valid.any():
        return float("nan")
    w = weights[valid]
    v = values[valid]
    w_sum = float(w.sum())
    if w_sum <= 0.0:
        return float(v.mean())
    return float((v * w).sum() / w_sum)


def load_compensation_long(compensation_path: Path) -> pd.DataFrame:
    """
    KPI_PLAN step 1:
    Transform compensation FR/LU sheets into clean long format.
    """
    sheet_country = {
        "Compensation Data FR": "France",
        "Compensation Data LU": "Luxembourg",
    }
    block_starts = [0, 6, 12]

    frames: list[pd.DataFrame] = []
    for sheet, country in sheet_country.items():
        raw = pd.read_excel(compensation_path, sheet_name=sheet, header=None)

        for start_col in block_starts:
            period_cell = raw.iat[1, start_col + 1] if start_col + 1 < raw.shape[1] else None
            year = _extract_year(period_cell)
            if year is None:
                continue

            block = raw.iloc[:, start_col : start_col + 4].copy()
            block.columns = ["job", "effectif", "avg_fixed_salary", "avg_variable_salary"]
            block = block.iloc[4:].copy()

            block["job"] = block["job"].astype(str).str.strip()
            block["job_norm"] = block["job"].map(_normalize_text)
            block = block[block["job_norm"] != ""]
            block = block[~block["job_norm"].str.contains(r"^total(?: general)?$", regex=True)]

            block["effectif"] = pd.to_numeric(block["effectif"], errors="coerce")
            block["avg_fixed_salary"] = pd.to_numeric(block["avg_fixed_salary"], errors="coerce")
            block["avg_variable_salary"] = pd.to_numeric(block["avg_variable_salary"], errors="coerce")
            block = block.dropna(subset=["avg_fixed_salary", "avg_variable_salary"], how="all")

            block["country"] = country
            block["year"] = int(year)
            frames.append(block)

    if not frames:
        raise ValueError("No compensation rows were extracted from FR/LU sheets.")

    all_rows = pd.concat(frames, ignore_index=True)

    def aggregate_role(group: pd.DataFrame) -> pd.Series:
        effectif = pd.to_numeric(group["effectif"], errors="coerce").fillna(0.0)
        avg_fixed = _weighted_average(group["avg_fixed_salary"], effectif)
        avg_variable = _weighted_average(group["avg_variable_salary"], effectif)
        if pd.isna(avg_fixed):
            avg_fixed = float(pd.to_numeric(group["avg_fixed_salary"], errors="coerce").mean())
        if pd.isna(avg_variable):
            avg_variable = float(pd.to_numeric(group["avg_variable_salary"], errors="coerce").mean())
        best_label = (
            group.sort_values(["effectif", "avg_fixed_salary"], ascending=[False, False]).iloc[0]["job"]
        )
        return pd.Series(
            {
                "job": str(best_label).strip(),
                "effectif": float(effectif.sum()),
                "avg_fixed_salary": float(avg_fixed),
                "avg_variable_salary": float(avg_variable),
            }
        )

    grouped_rows: list[dict[str, object]] = []
    for (country, year, job_norm), group in all_rows.groupby(["country", "year", "job_norm"]):
        agg = aggregate_role(group)
        grouped_rows.append(
            {
                "country": country,
                "year": int(year),
                "job_norm": job_norm,
                "job": agg["job"],
                "effectif": agg["effectif"],
                "avg_fixed_salary": agg["avg_fixed_salary"],
                "avg_variable_salary": agg["avg_variable_salary"],
            }
        )
    grouped = pd.DataFrame(grouped_rows)

    grouped["average_total_compensation"] = grouped["avg_fixed_salary"] + grouped["avg_variable_salary"]
    grouped["variable_pay_ratio"] = grouped["avg_variable_salary"] / grouped["average_total_compensation"]
    grouped["variable_pay_ratio"] = grouped["variable_pay_ratio"].clip(lower=0.0, upper=1.0)

    return grouped.sort_values(["country", "year", "job"]).reset_index(drop=True)


def build_employee_year_roles(panel_path: Path) -> pd.DataFrame:
    """
    KPI_PLAN step 2 (part):
    Build employee job/country/year base from Data.xlsx > Sheet1.
    """
    raw = pd.read_excel(panel_path, sheet_name="Sheet1")
    use_cols = ["PERIOD", "ID Employee", "COUNTRY_GROUP_LABEL_EN", "POSTE_LABEL_LOCAL", "ENTITY_LABEL_LOCAL"]
    missing_cols = [col for col in use_cols if col not in raw.columns]
    if missing_cols:
        raise ValueError(f"Missing columns in panel source: {missing_cols}")

    panel = raw.loc[:, use_cols].rename(
        columns={
            "PERIOD": "period",
            "ID Employee": "employee_id",
            "COUNTRY_GROUP_LABEL_EN": "country",
            "POSTE_LABEL_LOCAL": "job",
            "ENTITY_LABEL_LOCAL": "entity",
        }
    )
    panel["employee_id"] = _normalize_id(panel["employee_id"])
    panel["period"] = pd.to_datetime(panel["period"], errors="coerce", dayfirst=True)
    panel["year"] = panel["period"].dt.year
    panel["job"] = panel["job"].astype(str).str.strip()
    panel["job_norm"] = panel["job"].map(_normalize_text)

    panel = panel.dropna(subset=["employee_id", "period", "year"]).copy()
    panel = panel[panel["country"].isin(["France", "Luxembourg"])].copy()
    panel = panel[panel["job_norm"] != ""].copy()
    panel["year"] = panel["year"].astype(int)

    ordered = panel.sort_values(["employee_id", "year", "period"])
    base = (
        ordered.groupby(["employee_id", "year"], as_index=False)
        .tail(1)
        .loc[:, ["employee_id", "year", "country", "entity", "job", "job_norm"]]
        .reset_index(drop=True)
    )
    return base


def aggregate_role_performance(eae_path: Path) -> pd.DataFrame:
    """
    KPI_PLAN step 3:
    Aggregate EAE performance by job/year/country.
    """
    raw = pd.read_excel(eae_path, sheet_name="Database")
    raw.columns = [col.strip() if isinstance(col, str) else col for col in raw.columns]

    needed = ["IUG", "Année", "Libellé emploi", "Note de performance", "Pays", "Nom de l'employeur légal"]
    missing = [col for col in needed if col not in raw.columns]
    if missing:
        raise ValueError(f"Missing columns in EAE source: {missing}")

    perf = raw.loc[:, needed].rename(
        columns={
            "IUG": "employee_id",
            "Année": "year",
            "Libellé emploi": "job",
            "Note de performance": "performance_score",
            "Pays": "pays",
            "Nom de l'employeur légal": "legal_employer",
        }
    )

    perf["employee_id"] = _normalize_id(perf["employee_id"])
    perf["year"] = pd.to_numeric(perf["year"], errors="coerce")
    perf["performance_score"] = pd.to_numeric(perf["performance_score"], errors="coerce")
    perf["country"] = perf.apply(
        lambda row: _map_eae_country(row["pays"], row["legal_employer"]), axis=1
    )
    perf["job"] = perf["job"].astype(str).str.strip()
    perf["job_norm"] = perf["job"].map(_normalize_text)

    perf = perf.dropna(subset=["employee_id", "year", "performance_score", "country"]).copy()
    perf = perf[perf["job_norm"] != ""].copy()
    perf["year"] = perf["year"].astype(int)
    perf = perf[perf["country"].isin(["France", "Luxembourg"])].copy()

    per_employee = (
        perf.groupby(["employee_id", "year", "country", "job_norm"], as_index=False)
        .agg(
            performance_score=("performance_score", "mean"),
            job_label_eae=("job", "first"),
        )
        .sort_values(["employee_id", "year"])
        .reset_index(drop=True)
    )

    role = (
        per_employee.groupby(["country", "year", "job_norm"], as_index=False)
        .agg(
            average_role_performance=("performance_score", "mean"),
            performance_employees=("employee_id", "nunique"),
            performance_records=("performance_score", "count"),
            job_label_eae=("job_label_eae", "first"),
        )
        .sort_values(["country", "year", "job_norm"])
        .reset_index(drop=True)
    )
    return role


def build_role_cost_table(
    employee_year: pd.DataFrame,
    compensation_long: pd.DataFrame,
    role_performance: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    KPI_PLAN steps 2-4:
    Join compensation benchmark to employee job/country/year then compute role cost efficiency metrics.
    """
    employee_joined = employee_year.merge(
        compensation_long[
            [
                "country",
                "year",
                "job_norm",
                "job",
                "effectif",
                "avg_fixed_salary",
                "avg_variable_salary",
                "average_total_compensation",
                "variable_pay_ratio",
            ]
        ],
        on=["country", "year", "job_norm"],
        how="left",
        suffixes=("", "_comp"),
    )

    role_population = (
        employee_joined.groupby(["country", "year", "job_norm"], as_index=False)
        .agg(
            employees_panel=("employee_id", "nunique"),
            entities_panel=("entity", "nunique"),
            job_label_panel=("job", "first"),
            compensation_match_share=("average_total_compensation", lambda s: float(s.notna().mean())),
        )
        .sort_values(["country", "year", "job_norm"])
        .reset_index(drop=True)
    )

    role_table = role_population.merge(
        compensation_long,
        on=["country", "year", "job_norm"],
        how="left",
        suffixes=("_panel", "_comp"),
    )
    role_table = role_table.merge(role_performance, on=["country", "year", "job_norm"], how="left")

    role_table["job"] = role_table["job"].fillna(role_table["job_label_panel"]).fillna(
        role_table["job_label_eae"]
    )

    role_table["median_country_year_compensation"] = role_table.groupby(["country", "year"])[
        "average_total_compensation"
    ].transform("median")
    role_table["role_compensation_index"] = (
        role_table["average_total_compensation"] / role_table["median_country_year_compensation"]
    )

    role_table["performance_score_norm_0_1"] = (role_table["average_role_performance"] / 5.0).clip(
        lower=0.0, upper=1.0
    )
    role_table["median_country_year_role_performance"] = role_table.groupby(["country", "year"])[
        "average_role_performance"
    ].transform("median")
    role_table["normalized_average_role_performance"] = (
        role_table["average_role_performance"] / role_table["median_country_year_role_performance"]
    )

    fallback_norm = role_table["performance_score_norm_0_1"] * 2.0
    role_table["normalized_average_role_performance"] = role_table[
        "normalized_average_role_performance"
    ].fillna(fallback_norm)

    role_table["role_cost_efficiency"] = (
        role_table["normalized_average_role_performance"] / role_table["role_compensation_index"]
    )

    has_comp = role_table["role_compensation_index"].notna()
    has_perf = role_table["normalized_average_role_performance"].notna()
    high_cost = role_table["role_compensation_index"] >= 1.0
    high_perf = role_table["normalized_average_role_performance"] >= 1.0

    role_table["quadrant"] = "Data unavailable"
    role_table.loc[has_comp & has_perf & high_cost & high_perf, "quadrant"] = (
        "High cost + high performance"
    )
    role_table.loc[has_comp & has_perf & high_cost & (~high_perf), "quadrant"] = (
        "High cost + low performance"
    )
    role_table.loc[has_comp & has_perf & (~high_cost) & high_perf, "quadrant"] = (
        "Low cost + high performance"
    )
    role_table.loc[has_comp & has_perf & (~high_cost) & (~high_perf), "quadrant"] = (
        "Low cost + low performance"
    )

    ordered_cols = [
        "country",
        "year",
        "job",
        "job_norm",
        "employees_panel",
        "entities_panel",
        "effectif",
        "avg_fixed_salary",
        "avg_variable_salary",
        "average_total_compensation",
        "variable_pay_ratio",
        "median_country_year_compensation",
        "role_compensation_index",
        "average_role_performance",
        "performance_score_norm_0_1",
        "median_country_year_role_performance",
        "normalized_average_role_performance",
        "role_cost_efficiency",
        "performance_employees",
        "performance_records",
        "compensation_match_share",
        "quadrant",
    ]
    role_table = role_table.loc[:, ordered_cols].sort_values(
        ["year", "country", "role_cost_efficiency"], ascending=[True, True, False]
    )
    return role_table.reset_index(drop=True), employee_joined


def build_kpi5_result(config: KPI5Config) -> KPI5Result:
    """
    KPI_PLAN steps 1-5 end-to-end builder.
    """
    compensation_long = load_compensation_long(config.compensation_path)
    employee_year = build_employee_year_roles(config.panel_path)
    role_performance = aggregate_role_performance(config.eae_path)

    role_cost_table, employee_joined = build_role_cost_table(
        employee_year=employee_year,
        compensation_long=compensation_long,
        role_performance=role_performance,
    )

    valid_years = role_cost_table.loc[role_cost_table["average_role_performance"].notna(), "year"]
    latest_year = int(valid_years.max()) if not valid_years.empty else int(role_cost_table["year"].max())
    latest = role_cost_table[role_cost_table["year"] == latest_year].copy()
    latest = latest.sort_values(["country", "role_cost_efficiency"], ascending=[True, False]).reset_index(
        drop=True
    )

    country_year_summary = (
        role_cost_table.groupby(["country", "year"], as_index=False)
        .agg(
            roles=("job_norm", "nunique"),
            employees_panel=("employees_panel", "sum"),
            avg_total_compensation=("average_total_compensation", "mean"),
            median_total_compensation=("average_total_compensation", "median"),
            avg_role_compensation_index=("role_compensation_index", "mean"),
            avg_role_performance=("average_role_performance", "mean"),
            avg_normalized_role_performance=("normalized_average_role_performance", "mean"),
            avg_role_cost_efficiency=("role_cost_efficiency", "mean"),
            performance_coverage=("average_role_performance", lambda s: float(s.notna().mean())),
            efficiency_risk_share=("quadrant", lambda s: float((s == "High cost + low performance").mean())),
            retention_risk_share=("quadrant", lambda s: float((s == "Low cost + high performance").mean())),
        )
        .sort_values(["year", "country"])
        .reset_index(drop=True)
    )

    quadrant_summary = (
        latest.groupby(["country", "quadrant"], as_index=False)
        .agg(
            roles=("job_norm", "nunique"),
            employees_panel=("employees_panel", "sum"),
        )
        .sort_values(["country", "roles"], ascending=[True, False])
        .reset_index(drop=True)
    )

    join_coverage = (
        employee_joined.groupby(["country", "year"], as_index=False)
        .agg(
            employee_year_rows=("employee_id", "count"),
            employees=("employee_id", "nunique"),
            panel_jobs=("job_norm", "nunique"),
            compensation_match_share=("average_total_compensation", lambda s: float(s.notna().mean())),
            matched_employee_year_rows=("average_total_compensation", lambda s: int(s.notna().sum())),
        )
        .sort_values(["year", "country"])
        .reset_index(drop=True)
    )

    efficiency_risk_roles = (
        latest[latest["quadrant"] == "High cost + low performance"]
        .sort_values(["role_compensation_index", "employees_panel"], ascending=[False, False])
        .reset_index(drop=True)
    )
    strategic_high_value_roles = (
        latest[latest["quadrant"] == "High cost + high performance"]
        .sort_values(["role_cost_efficiency", "employees_panel"], ascending=[False, False])
        .reset_index(drop=True)
    )
    retention_risk_roles = (
        latest[latest["quadrant"] == "Low cost + high performance"]
        .sort_values(["role_cost_efficiency", "employees_panel"], ascending=[False, False])
        .reset_index(drop=True)
    )

    return KPI5Result(
        role_cost_table=role_cost_table,
        latest_year_table=latest,
        country_year_summary=country_year_summary,
        quadrant_summary=quadrant_summary,
        join_coverage=join_coverage,
        efficiency_risk_roles=efficiency_risk_roles,
        strategic_high_value_roles=strategic_high_value_roles,
        retention_risk_roles=retention_risk_roles,
    )


def summarize_kpi5(result: KPI5Result) -> list[str]:
    """
    KPI_PLAN step 5:
    Provide business interpretation for role cost-performance alignment.
    """
    latest = result.latest_year_table
    if latest.empty:
        return ["No KPI 5 role records were generated."]

    latest_year = int(latest["year"].max())
    perf_coverage = float(latest["average_role_performance"].notna().mean())
    avg_efficiency = float(latest["role_cost_efficiency"].mean())
    messages = [
        (
            f"Latest year with role performance data: {latest_year}. "
            f"Average role cost efficiency is {avg_efficiency:.3f} with {perf_coverage:.1%} role-level performance coverage."
        )
    ]

    if not result.efficiency_risk_roles.empty:
        top_risk = result.efficiency_risk_roles.iloc[0]
        messages.append(
            "Top efficiency-risk role: "
            f"{top_risk['job']} ({top_risk['country']}), "
            f"cost index {top_risk['role_compensation_index']:.2f}, "
            f"normalized performance {top_risk['normalized_average_role_performance']:.2f}."
        )

    if not result.strategic_high_value_roles.empty:
        top_strategic = result.strategic_high_value_roles.iloc[0]
        messages.append(
            "Top strategic high-value role: "
            f"{top_strategic['job']} ({top_strategic['country']}), "
            f"role cost efficiency {top_strategic['role_cost_efficiency']:.2f}."
        )

    if not result.retention_risk_roles.empty:
        top_retention = result.retention_risk_roles.iloc[0]
        messages.append(
            "Top retention-risk role (high performance at lower relative cost): "
            f"{top_retention['job']} ({top_retention['country']})."
        )

    messages.append(
        "Limitation: compensation input is role-level average benchmark, not individual employee salary."
    )
    return messages
