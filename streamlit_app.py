from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import streamlit as st

from kpi1_pipeline import KPI1Config, build_kpi1_table, summarize_trend
from kpi2_pipeline import (
    DEFAULT_ABSENCE_PATHS as KPI2_DEFAULT_ABSENCE_PATHS,
    DEFAULT_EAE_PATH as KPI2_DEFAULT_EAE_PATH,
    DEFAULT_PANEL_PATH as KPI2_DEFAULT_PANEL_PATH,
    DEFAULT_TRAINING_PATH as KPI2_DEFAULT_TRAINING_PATH,
    KPI2Config,
    build_kpi2_result,
    summarize_kpi2,
)
from kpi3_pipeline import (
    DEFAULT_COLD_REVIEW_PATH,
    DEFAULT_EAE_PATH as KPI3_DEFAULT_EAE_PATH,
    DEFAULT_PANEL_PATH as KPI3_DEFAULT_PANEL_PATH,
    DEFAULT_QUICK_REVIEW_PATH,
    DEFAULT_TRAINING_PATH as KPI3_DEFAULT_TRAINING_PATH,
    KPI3Config,
    build_kpi3_result,
    summarize_kpi3,
)
from kpi4_pipeline import (
    DEFAULT_ABSENCE_PATHS as KPI4_DEFAULT_ABSENCE_PATHS,
    DEFAULT_FINANCE_PATH,
    DEFAULT_PANEL_PATH as KPI4_DEFAULT_PANEL_PATH,
    KPI4Config,
    build_kpi4_result,
    summarize_kpi4,
)
from kpi5_pipeline import (
    DEFAULT_COMPENSATION_PATH,
    DEFAULT_EAE_PATH as KPI5_DEFAULT_EAE_PATH,
    DEFAULT_PANEL_PATH as KPI5_DEFAULT_PANEL_PATH,
    KPI5Config,
    build_kpi5_result,
    summarize_kpi5,
)
from ai_module import (
    EvolvedPrototypeResult,
    run_evolved_prototype,
)

LOGO_PATH = Path(__file__).parent / "logo.png"
KPI1_DEFAULT_FILE = Path("Sujet Alberthon/Finance/AlbertSchool_CACEIS_PL-FTE_22-25_Sent.xlsx")

KPI_OPTIONS = [
    "KPI 1 - HCVA / HCROI",
    "KPI 2 - Workforce Value-at-Risk",
    "KPI 3 - Learning-to-Performance",
    "KPI 4 - Absence Productivity Drag",
    "KPI 5 - Role Cost Efficiency",
    "AI Lab - Evolved Prototype (D3)",
]


# ---------------------------------------------------------------------------
# Branding / theme injection
# ---------------------------------------------------------------------------

_CSS = """
<style>
:root {
  --caceis-grey: #6F6F6F;
  --caceis-red: #A81C36;
  --caceis-red-dark: #8B1429;
  --caceis-dark: #2B2B2B;
  --caceis-bg: #FAFAFA;
  --caceis-card: #FFFFFF;
  --caceis-border: #E6E2DD;
  --caceis-soft: #F7F5F2;
}

#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
.stDeployButton {display: none;}
header[data-testid="stHeader"] {background: transparent;}

/* Tighter top padding so the hero sits high */
.block-container {
  padding-top: 1.6rem !important;
  padding-bottom: 4rem;
  max-width: 1300px;
}

/* Sidebar */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #FFFFFF 0%, #F4F1EE 100%);
  border-right: 1px solid var(--caceis-border);
}
[data-testid="stSidebar"] .block-container {
  padding-top: 1.25rem;
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
  color: var(--caceis-dark);
}
.sidebar-tag {
  display: inline-block;
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--caceis-red);
  margin-top: 0.6rem;
  margin-bottom: 0.2rem;
}
.sidebar-title {
  font-size: 1rem;
  font-weight: 700;
  color: var(--caceis-dark);
  margin: 0 0 0.5rem 0;
  line-height: 1.25;
}
.sidebar-divider {
  height: 1px;
  background: var(--caceis-border);
  margin: 0.9rem 0 0.6rem 0;
}

/* Hero block */
.kpi-hero {
  border-left: 6px solid var(--caceis-red);
  padding: 0.4rem 0 0.4rem 1.25rem;
  margin: 0.25rem 0 1.4rem 0;
}
.kpi-badge {
  display: inline-block;
  background: var(--caceis-red);
  color: white;
  padding: 0.22rem 0.75rem;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 0.55rem;
}
.kpi-title {
  font-size: 1.95rem;
  font-weight: 700;
  color: var(--caceis-dark);
  margin: 0 0 0.3rem 0;
  line-height: 1.15;
}
.kpi-subtitle {
  color: var(--caceis-grey);
  font-size: 1rem;
  margin: 0;
}

/* Metric cards */
[data-testid="stMetric"] {
  background: var(--caceis-card);
  border: 1px solid var(--caceis-border);
  border-radius: 10px;
  padding: 0.9rem 1.05rem;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
[data-testid="stMetricLabel"] p {
  color: var(--caceis-grey);
  font-size: 0.74rem !important;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
[data-testid="stMetricValue"] {
  color: var(--caceis-dark);
  font-weight: 700;
}

/* Section subheaders */
.stApp h3 {
  color: var(--caceis-dark);
  font-size: 1.05rem;
  font-weight: 700;
  margin-top: 1.6rem;
  margin-bottom: 0.5rem;
  padding-bottom: 0.35rem;
  border-bottom: 1px solid var(--caceis-border);
}

/* Insight box */
.insight-box {
  background: #FBF7F4;
  border: 1px solid #ECE4DB;
  border-left: 4px solid var(--caceis-red);
  padding: 1rem 1.25rem;
  border-radius: 8px;
  margin: 1.1rem 0 0.4rem 0;
}
.insight-title {
  font-weight: 700;
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--caceis-red);
  margin-bottom: 0.55rem;
}
.insight-list {
  margin: 0;
  padding-left: 1.15rem;
  color: var(--caceis-dark);
  line-height: 1.55;
  font-size: 0.95rem;
}
.insight-list li {
  margin-bottom: 0.4rem;
}
.insight-list li:last-child {
  margin-bottom: 0;
}

/* Buttons */
.stButton > button {
  border-radius: 8px;
  font-weight: 600;
}
.stButton > button[kind="primary"] {
  background: var(--caceis-red);
  border-color: var(--caceis-red);
  color: white;
}
.stButton > button[kind="primary"]:hover {
  background: var(--caceis-red-dark);
  border-color: var(--caceis-red-dark);
  color: white;
}
.stButton > button[kind="secondary"]:hover {
  border-color: var(--caceis-red);
  color: var(--caceis-red);
}

/* DataFrames */
[data-testid="stDataFrame"] {
  border: 1px solid var(--caceis-border);
  border-radius: 8px;
  overflow: hidden;
}

/* Captions */
[data-testid="stCaptionContainer"] p,
.stCaption {
  color: #888 !important;
  font-size: 0.82rem;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
  gap: 0.4rem;
  border-bottom: 1px solid var(--caceis-border);
}
.stTabs [data-baseweb="tab"] {
  background: transparent;
  border-radius: 6px 6px 0 0;
  padding: 0.5rem 0.95rem;
  font-weight: 600;
  color: var(--caceis-grey);
}
.stTabs [aria-selected="true"] {
  color: var(--caceis-red) !important;
  border-bottom: 2px solid var(--caceis-red) !important;
}

/* Expanders */
.streamlit-expanderHeader,
[data-testid="stExpander"] summary {
  font-weight: 600;
  color: var(--caceis-dark);
}

/* Footer */
.app-footer {
  margin-top: 2.5rem;
  padding-top: 1rem;
  border-top: 1px solid var(--caceis-border);
  color: #999;
  font-size: 0.78rem;
  text-align: center;
}
</style>
"""


def _inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Reusable rendering helpers
# ---------------------------------------------------------------------------


def _render_hero(badge: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="kpi-hero">
          <span class="kpi-badge">{badge}</span>
          <h1 class="kpi-title">{title}</h1>
          <p class="kpi-subtitle">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_metric_row(metrics: list[tuple[str, str, str | None]]) -> None:
    if not metrics:
        return
    cols = st.columns(len(metrics))
    for col, (label, value, delta) in zip(cols, metrics):
        if delta:
            col.metric(label, value, delta)
        else:
            col.metric(label, value)


def _render_insight_box(lines: Iterable[str], title: str = "Business interpretation") -> None:
    items = "".join(f"<li>{line}</li>" for line in lines)
    if not items:
        return
    st.markdown(
        f"""
        <div class="insight-box">
          <div class="insight-title">{title}</div>
          <ul class="insight-list">{items}</ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _format_eur(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "—"
    if abs(value) >= 1_000_000_000:
        return f"€{value / 1_000_000_000:.2f}B"
    if abs(value) >= 1_000_000:
        return f"€{value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"€{value / 1_000:.1f}k"
    return f"€{value:,.0f}"


def _format_pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{value * 100:.1f}%"


def _format_int(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{value:,.0f}"


def _format_float(value: float | None, decimals: int = 2, suffix: str = "") -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{value:.{decimals}f}{suffix}"


# ---------------------------------------------------------------------------
# State / cached helpers (functional behavior preserved)
# ---------------------------------------------------------------------------


def _parse_absence_paths(raw_text: str) -> tuple[Path, ...]:
    paths = [Path(line.strip()) for line in raw_text.splitlines() if line.strip()]
    return tuple(paths)


def _missing_paths(paths: list[Path]) -> list[str]:
    return [str(path) for path in paths if not path.exists()]


def _file_mtime(path: Path) -> float:
    return path.stat().st_mtime


def _file_mtimes(paths: list[Path]) -> tuple[float, ...]:
    return tuple(_file_mtime(path) for path in paths)


def _init_state_defaults() -> None:
    defaults: dict[str, Any] = {
        "kpi1_input": str(KPI1_DEFAULT_FILE),
        "kpi1_scope": "group",
        "kpi2_panel": str(KPI2_DEFAULT_PANEL_PATH),
        "kpi2_eae": str(KPI2_DEFAULT_EAE_PATH),
        "kpi2_training": str(KPI2_DEFAULT_TRAINING_PATH),
        "kpi2_absence": "\n".join(str(path) for path in KPI2_DEFAULT_ABSENCE_PATHS),
        "kpi3_panel": str(KPI3_DEFAULT_PANEL_PATH),
        "kpi3_eae": str(KPI3_DEFAULT_EAE_PATH),
        "kpi3_training": str(KPI3_DEFAULT_TRAINING_PATH),
        "kpi3_quick": str(DEFAULT_QUICK_REVIEW_PATH),
        "kpi3_cold": str(DEFAULT_COLD_REVIEW_PATH),
        "kpi4_panel": str(KPI4_DEFAULT_PANEL_PATH),
        "kpi4_finance": str(DEFAULT_FINANCE_PATH),
        "kpi4_scope": "group",
        "kpi4_absence": "\n".join(str(path) for path in KPI4_DEFAULT_ABSENCE_PATHS),
        "kpi5_panel": str(KPI5_DEFAULT_PANEL_PATH),
        "kpi5_comp": str(DEFAULT_COMPENSATION_PATH),
        "kpi5_eae": str(KPI5_DEFAULT_EAE_PATH),
        "selected_kpi": KPI_OPTIONS[0],
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

    for kpi_key in ("kpi1", "kpi2", "kpi3", "kpi4", "kpi5", "ailab"):
        st.session_state.setdefault(f"{kpi_key}_result", None)
        st.session_state.setdefault(f"{kpi_key}_error", None)
    st.session_state.setdefault("ailab_n_clusters", 5)


@st.cache_data(show_spinner=False)
def _cached_kpi1(file_path: str, scope: str, finance_mtime: float) -> pd.DataFrame:
    _ = finance_mtime
    return build_kpi1_table(KPI1Config(file_path=Path(file_path), scope=scope))


@st.cache_data(show_spinner=False)
def _cached_kpi2(
    panel_path: str,
    eae_path: str,
    training_path: str,
    absence_paths: tuple[str, ...],
    source_mtimes: tuple[float, ...],
) -> Any:
    _ = source_mtimes
    config = KPI2Config(
        panel_path=Path(panel_path),
        eae_path=Path(eae_path),
        training_path=Path(training_path),
        absence_paths=tuple(Path(path) for path in absence_paths),
    )
    return build_kpi2_result(config)


@st.cache_data(show_spinner=False)
def _cached_kpi3(
    panel_path: str,
    eae_path: str,
    training_path: str,
    quick_review_path: str,
    cold_review_path: str,
    source_mtimes: tuple[float, ...],
) -> Any:
    _ = source_mtimes
    config = KPI3Config(
        panel_path=Path(panel_path),
        eae_path=Path(eae_path),
        training_path=Path(training_path),
        quick_review_path=Path(quick_review_path),
        cold_review_path=Path(cold_review_path),
    )
    return build_kpi3_result(config)


@st.cache_data(show_spinner=False)
def _cached_kpi4(
    panel_path: str,
    finance_path: str,
    finance_scope: str,
    absence_paths: tuple[str, ...],
    source_mtimes: tuple[float, ...],
) -> Any:
    _ = source_mtimes
    config = KPI4Config(
        panel_path=Path(panel_path),
        finance_path=Path(finance_path),
        finance_scope=finance_scope,
        absence_paths=tuple(Path(path) for path in absence_paths),
    )
    return build_kpi4_result(config)


@st.cache_data(show_spinner=False)
def _cached_kpi5(
    panel_path: str,
    compensation_path: str,
    eae_path: str,
    source_mtimes: tuple[float, ...],
) -> Any:
    _ = source_mtimes
    config = KPI5Config(
        panel_path=Path(panel_path),
        compensation_path=Path(compensation_path),
        eae_path=Path(eae_path),
    )
    return build_kpi5_result(config)


def _set_result(kpi_key: str, result: Any | None, error: str | None) -> None:
    st.session_state[f"{kpi_key}_result"] = result
    st.session_state[f"{kpi_key}_error"] = error


def _run_kpi1(file_path_value: str, scope: str) -> None:
    file_path = Path(file_path_value)
    missing = _missing_paths([file_path])
    if missing:
        _set_result("kpi1", None, "Missing file(s):\n- " + "\n- ".join(missing))
        return
    try:
        result = _cached_kpi1(file_path_value, scope, _file_mtime(file_path))
    except Exception as exc:
        _set_result("kpi1", None, str(exc))
        return
    _set_result("kpi1", result, None)


def _run_kpi2(panel_path_value: str, eae_path_value: str, training_path_value: str, absence_text: str) -> None:
    absence_paths = _parse_absence_paths(absence_text)
    paths = [Path(panel_path_value), Path(eae_path_value), Path(training_path_value), *absence_paths]
    missing = _missing_paths(paths)
    if missing:
        _set_result("kpi2", None, "Missing file(s):\n- " + "\n- ".join(missing))
        return
    try:
        result = _cached_kpi2(
            panel_path_value,
            eae_path_value,
            training_path_value,
            tuple(str(path) for path in absence_paths),
            _file_mtimes(paths),
        )
    except Exception as exc:
        _set_result("kpi2", None, str(exc))
        return
    _set_result("kpi2", result, None)


def _run_kpi3(
    panel_path_value: str,
    eae_path_value: str,
    training_path_value: str,
    quick_review_path_value: str,
    cold_review_path_value: str,
) -> None:
    paths = [
        Path(panel_path_value),
        Path(eae_path_value),
        Path(training_path_value),
        Path(quick_review_path_value),
        Path(cold_review_path_value),
    ]
    missing = _missing_paths(paths)
    if missing:
        _set_result("kpi3", None, "Missing file(s):\n- " + "\n- ".join(missing))
        return
    try:
        result = _cached_kpi3(
            panel_path_value,
            eae_path_value,
            training_path_value,
            quick_review_path_value,
            cold_review_path_value,
            _file_mtimes(paths),
        )
    except Exception as exc:
        _set_result("kpi3", None, str(exc))
        return
    _set_result("kpi3", result, None)


def _run_kpi4(panel_path_value: str, finance_path_value: str, finance_scope: str, absence_text: str) -> None:
    absence_paths = _parse_absence_paths(absence_text)
    paths = [Path(panel_path_value), Path(finance_path_value), *absence_paths]
    missing = _missing_paths(paths)
    if missing:
        _set_result("kpi4", None, "Missing file(s):\n- " + "\n- ".join(missing))
        return
    try:
        result = _cached_kpi4(
            panel_path_value,
            finance_path_value,
            finance_scope,
            tuple(str(path) for path in absence_paths),
            _file_mtimes(paths),
        )
    except Exception as exc:
        _set_result("kpi4", None, str(exc))
        return
    _set_result("kpi4", result, None)


def _run_kpi5(panel_path_value: str, compensation_path_value: str, eae_path_value: str) -> None:
    paths = [Path(panel_path_value), Path(compensation_path_value), Path(eae_path_value)]
    missing = _missing_paths(paths)
    if missing:
        _set_result("kpi5", None, "Missing file(s):\n- " + "\n- ".join(missing))
        return
    try:
        result = _cached_kpi5(
            panel_path_value,
            compensation_path_value,
            eae_path_value,
            _file_mtimes(paths),
        )
    except Exception as exc:
        _set_result("kpi5", None, str(exc))
        return
    _set_result("kpi5", result, None)


def _run_all_kpis() -> None:
    _run_kpi1(st.session_state["kpi1_input"], st.session_state["kpi1_scope"])
    _run_kpi2(
        st.session_state["kpi2_panel"],
        st.session_state["kpi2_eae"],
        st.session_state["kpi2_training"],
        st.session_state["kpi2_absence"],
    )
    _run_kpi3(
        st.session_state["kpi3_panel"],
        st.session_state["kpi3_eae"],
        st.session_state["kpi3_training"],
        st.session_state["kpi3_quick"],
        st.session_state["kpi3_cold"],
    )
    _run_kpi4(
        st.session_state["kpi4_panel"],
        st.session_state["kpi4_finance"],
        st.session_state["kpi4_scope"],
        st.session_state["kpi4_absence"],
    )
    _run_kpi5(
        st.session_state["kpi5_panel"],
        st.session_state["kpi5_comp"],
        st.session_state["kpi5_eae"],
    )


def _display_top_table(df: pd.DataFrame, n: int = 50) -> pd.DataFrame:
    show = df.head(n).copy()
    numeric_cols = show.select_dtypes(include=["number"]).columns
    for col in numeric_cols:
        show[col] = pd.to_numeric(show[col], errors="coerce")
    return show


def _format_kpi1_table_for_display(kpi_table: pd.DataFrame) -> pd.DataFrame:
    table = kpi_table.copy()
    numeric_cols = [
        "Net Banking Income (PNB)",
        "Other Operating Costs",
        "Total Personnel Costs",
        "avg_fte",
        "hcva",
        "hcva_per_fte",
        "hcroi",
        "revenue_per_fte",
    ]
    for col in numeric_cols:
        table[col] = pd.to_numeric(table[col], errors="coerce")
    return table


# ---------------------------------------------------------------------------
# Headline metric extractors
# ---------------------------------------------------------------------------


def _kpi1_headline_metrics(kpi_table: pd.DataFrame) -> list[tuple[str, str, str | None]]:
    if kpi_table is None or kpi_table.empty:
        return []
    sorted_t = kpi_table.sort_values("year")
    latest = sorted_t.iloc[-1]
    prev = sorted_t.iloc[-2] if len(sorted_t) > 1 else None
    year = int(latest["year"])

    def _delta(curr_key: str) -> str | None:
        if prev is None or pd.isna(prev[curr_key]) or prev[curr_key] == 0 or pd.isna(latest[curr_key]):
            return None
        d = (latest[curr_key] - prev[curr_key]) / prev[curr_key] * 100
        return f"{d:+.1f}% YoY"

    hcroi = latest.get("hcroi")
    return [
        (f"HCVA / FTE ({year})", _format_eur(latest.get("hcva_per_fte")), _delta("hcva_per_fte")),
        (f"HCROI ({year})", _format_float(hcroi, 2, "x"), _delta("hcroi")),
        (f"Revenue / FTE ({year})", _format_eur(latest.get("revenue_per_fte")), _delta("revenue_per_fte")),
        ("Years analyzed", f"{len(sorted_t)}", None),
    ]


def _kpi2_headline_metrics(result: Any) -> list[tuple[str, str, str | None]]:
    metrics: list[tuple[str, str, str | None]] = []
    table = getattr(result, "latest_risk_table", None)
    if table is not None and not table.empty:
        total = len(table)
        avg_risk = table["risk_score"].mean() if "risk_score" in table.columns else None
        if "risk_band" in table.columns:
            high = (table["risk_band"].astype(str).str.lower() == "high").sum()
        elif "risk_score" in table.columns:
            high = int((table["risk_score"] >= 0.6).sum())
        else:
            high = 0
        high_share = high / total if total else 0
        metrics.append(("Employees observed", _format_int(total), None))
        metrics.append(("Avg risk score", _format_float(avg_risk, 2), None))
        metrics.append(("High-risk share", _format_pct(high_share), f"{int(high)} employees"))
    trend = getattr(result, "risk_trend", None)
    if trend is not None and not trend.empty and "observed_leave_rate" in trend.columns:
        latest_leave = trend["observed_leave_rate"].dropna()
        if not latest_leave.empty:
            metrics.append(("Recent leave rate", _format_pct(latest_leave.iloc[-1]), None))
    return metrics


def _kpi3_headline_metrics(result: Any) -> list[tuple[str, str, str | None]]:
    yearly = getattr(result, "yearly_summary", None)
    if yearly is None or yearly.empty:
        return []
    latest = yearly.sort_values("year").iloc[-1]
    year = int(latest["year"])
    return [
        (f"Avg training hours ({year})", _format_float(latest.get("avg_training_hours"), 1, "h"), None),
        ("Trained share", _format_pct(latest.get("trained_share")), None),
        ("Avg learning index", _format_float(latest.get("avg_learning_index"), 2), None),
        ("Certified share", _format_pct(latest.get("certified_share")), None),
    ]


def _kpi4_headline_metrics(result: Any) -> list[tuple[str, str, str | None]]:
    yearly = getattr(result, "yearly_drag", None)
    if yearly is None or yearly.empty:
        return []
    latest = yearly.sort_values("year").iloc[-1]
    year = int(latest["year"])
    return [
        (f"Total absence days ({year})", _format_int(latest.get("total_absence_days")), None),
        ("Lost FTE", _format_float(latest.get("lost_fte"), 1), None),
        ("Days / employee", _format_float(latest.get("absence_days_per_employee"), 1), None),
        ("Estimated value lost", _format_eur(latest.get("estimated_value_lost")), None),
    ]


def _kpi5_headline_metrics(result: Any) -> list[tuple[str, str, str | None]]:
    metrics: list[tuple[str, str, str | None]] = []
    latest_table = getattr(result, "latest_year_table", None)
    summary = getattr(result, "country_year_summary", None)
    if latest_table is not None and not latest_table.empty:
        roles = len(latest_table)
        avg_eff = latest_table["role_cost_efficiency"].dropna().mean() if "role_cost_efficiency" in latest_table.columns else None
        metrics.append(("Roles analyzed", _format_int(roles), None))
        metrics.append(("Avg cost efficiency", _format_float(avg_eff, 2), None))
    if summary is not None and not summary.empty and "year" in summary.columns:
        latest_year = summary["year"].max()
        latest_summary = summary[summary["year"] == latest_year]
        eff_risk = latest_summary["efficiency_risk_share"].mean() if "efficiency_risk_share" in latest_summary.columns else None
        ret_risk = latest_summary["retention_risk_share"].mean() if "retention_risk_share" in latest_summary.columns else None
        metrics.append(("Efficiency-risk share", _format_pct(eff_risk), None))
        metrics.append(("Retention-risk share", _format_pct(ret_risk), None))
    return metrics


# ---------------------------------------------------------------------------
# KPI render functions
# ---------------------------------------------------------------------------


def _render_kpi1() -> None:
    with st.sidebar:
        st.markdown('<div class="sidebar-tag">KPI 1 inputs</div>', unsafe_allow_html=True)
        with st.expander("Data sources", expanded=False):
            input_path = st.text_input(
                "Finance workbook path",
                value=str(KPI1_DEFAULT_FILE),
                key="kpi1_input",
            )
            scope = st.selectbox(
                "Scope",
                options=["group", "europe"],
                format_func=lambda s: "Toutes Filiales conso" if s == "group" else "o/w Europe",
                key="kpi1_scope",
            )
        run = st.button("Compute KPI 1", key="kpi1_run", type="primary", use_container_width=True)

    _render_hero(
        "KPI 01",
        "HCVA / HCROI per FTE",
        "Financial value created by the workforce — Human Capital ROI",
    )

    with st.expander("Method & formulas", expanded=False):
        st.markdown(
            """
            - `HCVA = PNB - Other Operating Costs`
            - `HCVA per FTE = HCVA / Average FTE`
            - `HCROI = HCVA / Total Personnel Costs`
            - `Revenue per FTE = PNB / Average FTE`

            *In the source P&L, cost rows are negative. The pipeline converts costs to positive
            amounts before KPI calculation.*
            """
        )

    if run:
        _run_kpi1(input_path, scope)

    if st.session_state["kpi1_error"]:
        st.error(st.session_state["kpi1_error"])
        return

    kpi_table = st.session_state["kpi1_result"]
    if kpi_table is None:
        st.info("Click **Compute KPI 1** in the sidebar (or **Run all KPIs**) to compute outputs.")
        return

    _render_metric_row(_kpi1_headline_metrics(kpi_table))

    st.subheader("Yearly KPI table (2022 – 2025)")
    display_table = _format_kpi1_table_for_display(kpi_table)
    st.dataframe(display_table, use_container_width=True, hide_index=True)

    left, right = st.columns(2)
    with left:
        st.subheader("HCVA / FTE vs Revenue / FTE")
        chart_a = kpi_table.set_index("year")[["hcva_per_fte", "revenue_per_fte"]]
        st.line_chart(chart_a)

    with right:
        st.subheader("HCROI trend")
        chart_b = kpi_table.set_index("year")[["hcroi"]]
        st.line_chart(chart_b)

    _render_insight_box(summarize_trend(kpi_table))


def _render_kpi2() -> None:
    with st.sidebar:
        st.markdown('<div class="sidebar-tag">KPI 2 inputs</div>', unsafe_allow_html=True)
        with st.expander("Data sources", expanded=False):
            panel_path = st.text_input("Panel file (Data.xlsx)", value=str(KPI2_DEFAULT_PANEL_PATH), key="kpi2_panel")
            eae_path = st.text_input("EAE file", value=str(KPI2_DEFAULT_EAE_PATH), key="kpi2_eae")
            training_path = st.text_input(
                "Training file",
                value=str(KPI2_DEFAULT_TRAINING_PATH),
                key="kpi2_training",
            )
            absence_paths_text = st.text_area(
                "Absence files (one path per line)",
                value="\n".join(str(path) for path in KPI2_DEFAULT_ABSENCE_PATHS),
                height=120,
                key="kpi2_absence",
            )
        run = st.button("Compute KPI 2", key="kpi2_run", type="primary", use_container_width=True)

    _render_hero(
        "KPI 02",
        "Workforce Value-at-Risk",
        "Employees and segments at risk of attrition or value loss",
    )

    with st.expander("Method & formulas", expanded=False):
        st.markdown(
            """
            **Target & features**
            - `Left_Next_6M = 1` if the employee disappears from the monthly panel for the next 6 months
            - `Tenure_CACEIS_Months = PERIOD - DATE_ENTRY_CACEIS`
            - `Months_In_Current_Post = PERIOD - DATE_ENTRY_POSTE`
            - `Absence_Days_12M = trailing 12-month sum of absence days`
            - `Training_Hours_12M = trailing 12-month sum of training hours`

            **Risk score**
            - 0.25 × New-Joiner Risk
            - 0.20 × Low-Performance Risk
            - 0.20 × High-Absence Risk
            - 0.15 × Low-Training Risk
            - 0.10 × Long-Time-In-Post Risk
            - 0.10 × Segment Risk

            *Segment risk is estimated from observed historical leave rates with smoothing.
            For the last 6 panel months, `Left_Next_6M` is right-censored.*
            """
        )

    if run:
        _run_kpi2(panel_path, eae_path, training_path, absence_paths_text)

    if st.session_state["kpi2_error"]:
        st.error(st.session_state["kpi2_error"])
        return

    result = st.session_state["kpi2_result"]
    if result is None:
        st.info("Click **Compute KPI 2** in the sidebar (or **Run all KPIs**) to compute outputs.")
        return

    _render_metric_row(_kpi2_headline_metrics(result))

    latest_period = result.latest_risk_table["period"].max()
    st.subheader(f"Top-risk employees — {latest_period:%B %Y}")
    employee_cols = [
        "employee_id",
        "country",
        "entity",
        "job",
        "tenure_caceis_months",
        "months_in_current_post",
        "absence_days_12m",
        "training_hours_12m",
        "performance_score",
        "risk_score",
        "risk_band",
    ]
    st.dataframe(
        _display_top_table(result.latest_risk_table.loc[:, employee_cols], n=200),
        use_container_width=True,
        hide_index=True,
    )

    left_col, right_col = st.columns(2)
    with left_col:
        st.subheader("Risk trend")
        trend = result.risk_trend.set_index("period")[["avg_risk_score", "high_risk_share", "observed_leave_rate"]]
        st.line_chart(trend)

    with right_col:
        st.subheader("Risk-score distribution (latest month)")
        bins = pd.cut(result.latest_risk_table["risk_score"], bins=10).value_counts().sort_index()
        dist = bins.rename_axis("risk_bin").reset_index(name="employees")
        dist["risk_bin"] = dist["risk_bin"].astype(str)
        st.bar_chart(dist.set_index("risk_bin"))

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Top-risk entities")
        st.dataframe(_display_top_table(result.entity_risk, n=20), use_container_width=True, hide_index=True)

    with c2:
        st.subheader("Top-risk jobs")
        st.dataframe(_display_top_table(result.job_risk, n=20), use_container_width=True, hide_index=True)

    st.subheader("Top-risk segments (country + entity + job)")
    st.dataframe(_display_top_table(result.segment_risk, n=40), use_container_width=True, hide_index=True)

    _render_insight_box(summarize_kpi2(result))


def _render_kpi3() -> None:
    with st.sidebar:
        st.markdown('<div class="sidebar-tag">KPI 3 inputs</div>', unsafe_allow_html=True)
        with st.expander("Data sources", expanded=False):
            panel_path = st.text_input("Panel file (Data.xlsx)", value=str(KPI3_DEFAULT_PANEL_PATH), key="kpi3_panel")
            eae_path = st.text_input("EAE file", value=str(KPI3_DEFAULT_EAE_PATH), key="kpi3_eae")
            training_path = st.text_input(
                "Training records file",
                value=str(KPI3_DEFAULT_TRAINING_PATH),
                key="kpi3_training",
            )
            quick_review_path = st.text_input(
                "Quick review file",
                value=str(DEFAULT_QUICK_REVIEW_PATH),
                key="kpi3_quick",
            )
            cold_review_path = st.text_input(
                "Cold review file",
                value=str(DEFAULT_COLD_REVIEW_PATH),
                key="kpi3_cold",
            )
        run = st.button("Compute KPI 3", key="kpi3_run", type="primary", use_container_width=True)

    _render_hero(
        "KPI 03",
        "Learning-to-Performance Index",
        "Whether training investment improves capability and performance",
    )

    with st.expander("Method & formulas", expanded=False):
        st.markdown(
            """
            **Aggregations**
            - `Training_Hours = SUM(Total_Training_Hours)`
            - `Training_Count = COUNT(Session_ID)`
            - `Quick_Review_Score = AVG(Note générale)`
            - `Cold_Impact_Score = average converted cold-review answers`
            - Cold mapping: `Oui, tout à fait = 1` · `Oui, en partie = 0.5` · `Non = 0`

            **Index**
            - 0.40 × Normalized Training Hours
            - 0.30 × Normalized Cold Impact Score
            - 0.20 × Normalized Quick Review Score
            - 0.10 × Certification Flag

            *Training hours are clipped at the year-specific P95 to reduce outlier effects;
            quick review score is rescaled from 1-5 to 0-1.*
            """
        )

    if run:
        _run_kpi3(panel_path, eae_path, training_path, quick_review_path, cold_review_path)

    if st.session_state["kpi3_error"]:
        st.error(st.session_state["kpi3_error"])
        return

    result = st.session_state["kpi3_result"]
    if result is None:
        st.info("Click **Compute KPI 3** in the sidebar (or **Run all KPIs**) to compute outputs.")
        return

    _render_metric_row(_kpi3_headline_metrics(result))

    latest_year = int(result.latest_year_table["year"].max()) if not result.latest_year_table.empty else None

    st.subheader("Yearly learning summary")
    st.dataframe(_display_top_table(result.yearly_summary, n=20), use_container_width=True, hide_index=True)

    st.subheader("Trained vs non-trained comparison")
    st.dataframe(_display_top_table(result.trained_vs_non_trained, n=20), use_container_width=True, hide_index=True)

    if latest_year is not None:
        st.subheader(f"Top learning-index employees — {latest_year}")
        employee_cols = [
            "employee_id",
            "country",
            "entity",
            "job",
            "training_hours",
            "training_count",
            "quick_review_score",
            "cold_impact_score",
            "performance_score",
            "certification_flag",
            "learning_to_performance_index",
            "trained_flag",
        ]
        st.dataframe(
            _display_top_table(result.latest_year_table.loc[:, employee_cols], n=200),
            use_container_width=True,
            hide_index=True,
        )

    left_col, right_col = st.columns(2)
    with left_col:
        st.subheader("Training activity trend")
        if not result.yearly_summary.empty:
            training_trend = result.yearly_summary.set_index("year")[
                ["avg_training_hours", "avg_training_count", "trained_share", "certified_share"]
            ]
            st.line_chart(training_trend)

    with right_col:
        st.subheader("Learning & performance trend")
        if not result.yearly_summary.empty:
            score_trend = result.yearly_summary.set_index("year")[
                ["avg_learning_index", "avg_quick_review_score", "avg_cold_impact_score", "avg_performance_score"]
            ]
            st.line_chart(score_trend)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Training hours vs EAE performance")
        scatter_perf = _display_top_table(result.scatter_training_performance, n=5000)
        if scatter_perf.empty:
            st.info("No records with both training hours and EAE performance score.")
        else:
            st.scatter_chart(
                scatter_perf,
                x="training_hours",
                y="performance_score",
                use_container_width=True,
            )
            st.caption(f"Points shown: {len(scatter_perf)} employee-year observations.")

    with c2:
        st.subheader("Training hours vs cold-impact score")
        scatter_impact = _display_top_table(result.scatter_training_impact, n=5000)
        if scatter_impact.empty:
            st.info("No records with both training hours and cold impact score.")
        else:
            st.scatter_chart(
                scatter_impact,
                x="training_hours",
                y="cold_impact_score",
                use_container_width=True,
            )
            st.caption(f"Points shown: {len(scatter_impact)} employee-year observations.")

    st.subheader("Top learning entities (latest year)")
    st.dataframe(_display_top_table(result.entity_learning, n=20), use_container_width=True, hide_index=True)

    _render_insight_box(summarize_kpi3(result))


def _render_kpi4() -> None:
    with st.sidebar:
        st.markdown('<div class="sidebar-tag">KPI 4 inputs</div>', unsafe_allow_html=True)
        with st.expander("Data sources", expanded=False):
            panel_path = st.text_input("Panel file (Data.xlsx)", value=str(KPI4_DEFAULT_PANEL_PATH), key="kpi4_panel")
            finance_path = st.text_input(
                "Finance file (PL/FTE workbook)",
                value=str(DEFAULT_FINANCE_PATH),
                key="kpi4_finance",
            )
            finance_scope = st.selectbox(
                "Finance scope for HCVA / FTE",
                options=["group", "europe"],
                format_func=lambda s: "Toutes Filiales conso" if s == "group" else "o/w Europe",
                key="kpi4_scope",
            )
            absence_paths_text = st.text_area(
                "Absence files (one path per line)",
                value="\n".join(str(path) for path in KPI4_DEFAULT_ABSENCE_PATHS),
                height=120,
                key="kpi4_absence",
            )
        run = st.button("Compute KPI 4", key="kpi4_run", type="primary", use_container_width=True)

    _render_hero(
        "KPI 04",
        "Absence Productivity Drag",
        "Translating absenteeism into lost productive capacity and value",
    )

    with st.expander("Method & formulas", expanded=False):
        st.markdown(
            """
            - `Total Absence Days = SUM(Jours Ouvrés Absence)`
            - `Lost FTE = Total Absence Days / 220`
            - `Absence Days per Employee = Total Absence Days / Number of Employees`
            - `Absence Productivity Drag = Lost FTE / Average FTE`
            - `Estimated Value Lost = Lost FTE × HCVA per FTE`

            *Yearly drag ratio uses average FTE from the finance workbook;
            monthly drag uses panel active employees as the denominator proxy.*
            """
        )

    if run:
        _run_kpi4(panel_path, finance_path, finance_scope, absence_paths_text)

    if st.session_state["kpi4_error"]:
        st.error(st.session_state["kpi4_error"])
        return

    result = st.session_state["kpi4_result"]
    if result is None:
        st.info("Click **Compute KPI 4** in the sidebar (or **Run all KPIs**) to compute outputs.")
        return

    _render_metric_row(_kpi4_headline_metrics(result))

    latest_year = int(result.yearly_drag["year"].max()) if not result.yearly_drag.empty else None

    st.subheader("Yearly absence-drag summary")
    st.dataframe(_display_top_table(result.yearly_drag, n=20), use_container_width=True, hide_index=True)

    left_col, right_col = st.columns(2)
    with left_col:
        st.subheader("Monthly absence trend")
        if not result.monthly_drag.empty:
            monthly_trend = result.monthly_drag.set_index("period")[
                ["total_absence_days", "lost_fte", "absence_days_per_employee"]
            ]
            st.line_chart(monthly_trend)

    with right_col:
        st.subheader("Monthly drag ratios")
        if not result.monthly_drag.empty:
            ratio_trend = result.monthly_drag.set_index("period")[
                ["employees_with_absence_share", "absence_productivity_drag_proxy"]
            ]
            st.line_chart(ratio_trend)

    c1, c2 = st.columns(2)
    with c1:
        title = f"Top entities by drag — {latest_year}" if latest_year is not None else "Top entities by drag"
        st.subheader(title)
        entity_cols = [
            "year",
            "entity",
            "total_absence_days",
            "affected_employees",
            "avg_active_employees",
            "absence_days_per_employee",
            "lost_fte",
            "absence_drag_proxy",
            "estimated_value_lost",
        ]
        st.dataframe(
            _display_top_table(result.latest_year_entity_drag.loc[:, entity_cols], n=30),
            use_container_width=True,
            hide_index=True,
        )

    with c2:
        title = f"Top reason groups — {latest_year}" if latest_year is not None else "Top reason groups"
        st.subheader(title)
        reason_group_cols = [
            "year",
            "reason_group",
            "total_absence_days",
            "affected_employees",
            "lost_fte",
            "estimated_value_lost",
        ]
        st.dataframe(
            _display_top_table(result.latest_year_reason_group_drag.loc[:, reason_group_cols], n=30),
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("Top reason details (latest year)")
    reason_detail_cols = [
        "year",
        "reason_detail",
        "total_absence_days",
        "affected_employees",
        "lost_fte",
        "estimated_value_lost",
    ]
    st.dataframe(
        _display_top_table(result.latest_year_reason_detail_drag.loc[:, reason_detail_cols], n=40),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Highest employee-month absence loads")
    employee_cols = [
        "employee_id",
        "period",
        "country",
        "entity",
        "job",
        "reason_group",
        "reason_detail",
        "total_absence_days",
    ]
    top_employee_month = result.employee_month_entity_reason.sort_values(
        "total_absence_days", ascending=False
    ).reset_index(drop=True)
    st.dataframe(
        _display_top_table(top_employee_month.loc[:, employee_cols], n=200),
        use_container_width=True,
        hide_index=True,
    )

    _render_insight_box(summarize_kpi4(result))


def _render_kpi5() -> None:
    with st.sidebar:
        st.markdown('<div class="sidebar-tag">KPI 5 inputs</div>', unsafe_allow_html=True)
        with st.expander("Data sources", expanded=False):
            panel_path = st.text_input(
                "Panel file (Data.xlsx > Sheet1)",
                value=str(KPI5_DEFAULT_PANEL_PATH),
                key="kpi5_panel",
            )
            compensation_path = st.text_input(
                "Compensation file (Data.xlsx > Compensation FR/LU)",
                value=str(DEFAULT_COMPENSATION_PATH),
                key="kpi5_comp",
            )
            eae_path = st.text_input("EAE file", value=str(KPI5_DEFAULT_EAE_PATH), key="kpi5_eae")
        run = st.button("Compute KPI 5", key="kpi5_run", type="primary", use_container_width=True)

    _render_hero(
        "KPI 05",
        "Role Cost Efficiency Index",
        "Whether role compensation cost is aligned with performance",
    )

    with st.expander("Method & formulas", expanded=False):
        st.markdown(
            """
            - `Average Total Compensation = Avg Fixed Salary + Avg Variable Salary`
            - `Variable Pay Ratio = Avg Variable Salary / Avg Total Compensation`
            - `Role Compensation Index = Avg Total Comp / Median Avg Total Comp (same country-year)`
            - `Average Role Performance = AVG(EAE Performance Score)` by role/year/country
            - `Role Cost Efficiency = Normalized Avg Role Performance / Role Compensation Index`

            **Quadrants** — High cost + high perf · High cost + low perf (efficiency risk) ·
            Low cost + high perf (retention risk) · Low cost + low perf

            *Compensation data is a role-level benchmark (FR/LU), not individual employee salary.*
            """
        )

    if run:
        _run_kpi5(panel_path, compensation_path, eae_path)

    if st.session_state["kpi5_error"]:
        st.error(st.session_state["kpi5_error"])
        return

    result = st.session_state["kpi5_result"]
    if result is None:
        st.info("Click **Compute KPI 5** in the sidebar (or **Run all KPIs**) to compute outputs.")
        return

    _render_metric_row(_kpi5_headline_metrics(result))

    latest_year = int(result.latest_year_table["year"].max()) if not result.latest_year_table.empty else None

    st.subheader("Compensation join coverage (panel → benchmark)")
    st.dataframe(_display_top_table(result.join_coverage, n=20), use_container_width=True, hide_index=True)

    st.subheader("Country-year KPI summary")
    st.dataframe(_display_top_table(result.country_year_summary, n=50), use_container_width=True, hide_index=True)

    left_col, right_col = st.columns(2)
    with left_col:
        st.subheader("Compensation & efficiency trend")
        trend_comp = result.country_year_summary.pivot(
            index="year", columns="country", values="avg_role_compensation_index"
        )
        trend_eff = result.country_year_summary.pivot(
            index="year", columns="country", values="avg_role_cost_efficiency"
        )
        if not trend_comp.empty:
            st.caption("Compensation index (avg by country)")
            st.line_chart(trend_comp)
        if not trend_eff.empty:
            st.caption("Role cost efficiency (avg by country)")
            st.line_chart(trend_eff)

    with right_col:
        st.subheader("Performance & risk shares")
        trend_perf = result.country_year_summary.pivot(
            index="year", columns="country", values="avg_normalized_role_performance"
        )
        trend_eff_risk = result.country_year_summary.pivot(
            index="year", columns="country", values="efficiency_risk_share"
        )
        trend_ret_risk = result.country_year_summary.pivot(
            index="year", columns="country", values="retention_risk_share"
        )
        if not trend_perf.empty:
            st.caption("Normalized role performance (avg by country)")
            st.line_chart(trend_perf)
        if not trend_eff_risk.empty:
            st.caption("Efficiency-risk share (high cost + low perf)")
            st.line_chart(trend_eff_risk)
        if not trend_ret_risk.empty:
            st.caption("Retention-risk share (low cost + high perf)")
            st.line_chart(trend_ret_risk)

    if latest_year is not None:
        st.subheader(f"Role cost table — {latest_year}")
        role_cols = [
            "country",
            "job",
            "employees_panel",
            "average_total_compensation",
            "variable_pay_ratio",
            "role_compensation_index",
            "average_role_performance",
            "normalized_average_role_performance",
            "role_cost_efficiency",
            "quadrant",
        ]
        st.dataframe(
            _display_top_table(result.latest_year_table.loc[:, role_cols], n=300),
            use_container_width=True,
            hide_index=True,
        )

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Cost vs performance scatter (latest year)")
        plot_df = result.latest_year_table.dropna(
            subset=["role_compensation_index", "normalized_average_role_performance"]
        )
        if plot_df.empty:
            st.info("No role records with both compensation and performance metrics.")
        else:
            st.scatter_chart(
                plot_df,
                x="role_compensation_index",
                y="normalized_average_role_performance",
                use_container_width=True,
            )
            st.caption(
                "Reference thresholds: cost index = 1 and normalized performance = 1 "
                "(country-year median levels)."
            )

    with c2:
        st.subheader("Quadrant split (latest year)")
        st.dataframe(_display_top_table(result.quadrant_summary, n=20), use_container_width=True, hide_index=True)

    c3, c4 = st.columns(2)
    with c3:
        st.subheader("Top efficiency-risk roles")
        risk_cols = [
            "country",
            "job",
            "employees_panel",
            "role_compensation_index",
            "normalized_average_role_performance",
            "role_cost_efficiency",
        ]
        st.dataframe(
            _display_top_table(result.efficiency_risk_roles.loc[:, risk_cols], n=30),
            use_container_width=True,
            hide_index=True,
        )

    with c4:
        st.subheader("Top retention-risk roles")
        retention_cols = [
            "country",
            "job",
            "employees_panel",
            "role_compensation_index",
            "normalized_average_role_performance",
            "role_cost_efficiency",
        ]
        st.dataframe(
            _display_top_table(result.retention_risk_roles.loc[:, retention_cols], n=30),
            use_container_width=True,
            hide_index=True,
        )

    _render_insight_box(summarize_kpi5(result))


# ---------------------------------------------------------------------------
# AI Lab — Deliverable 3 evolved prototype
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner=False)
def _cached_ailab(
    panel_path: str,
    eae_path: str,
    training_path: str,
    absence_paths: tuple[str, ...],
    finance_path: str,
    finance_scope: str,
    n_clusters: int,
    source_mtimes: tuple[float, ...],
) -> Any:
    _ = source_mtimes
    kpi2 = build_kpi2_result(
        KPI2Config(
            panel_path=Path(panel_path),
            eae_path=Path(eae_path),
            training_path=Path(training_path),
            absence_paths=tuple(Path(p) for p in absence_paths),
        )
    )
    kpi1 = build_kpi1_table(
        KPI1Config(file_path=Path(finance_path), scope=finance_scope)
    )
    kpi4 = build_kpi4_result(
        KPI4Config(
            panel_path=Path(panel_path),
            finance_path=Path(finance_path),
            finance_scope=finance_scope,
            absence_paths=tuple(Path(p) for p in absence_paths),
        )
    )
    latest_finance = kpi1.sort_values("year").iloc[-1]
    hcva_per_fte_eur = float(latest_finance["hcva_per_fte"]) * 1000.0  # source is k EUR
    avg_fte = float(latest_finance["avg_fte"])
    latest_drag_row = kpi4.yearly_drag.sort_values("year").iloc[-1]
    drag_pct = float(latest_drag_row["absence_productivity_drag"])

    return run_evolved_prototype(
        risk_table=kpi2.risk_table,
        hcva_per_fte=hcva_per_fte_eur,
        avg_fte=avg_fte,
        absence_drag_pct=drag_pct,
        n_clusters=int(n_clusters),
    )


def _run_ailab(
    panel_path: str,
    eae_path: str,
    training_path: str,
    absence_text: str,
    finance_path: str,
    finance_scope: str,
    n_clusters: int,
) -> None:
    paths = [Path(panel_path), Path(eae_path), Path(training_path), Path(finance_path)]
    absence_paths = _parse_absence_paths(absence_text)
    paths.extend(absence_paths)
    missing = _missing_paths(paths)
    if missing:
        _set_result("ailab", None, "Missing file(s):\n- " + "\n- ".join(missing))
        return
    try:
        result = _cached_ailab(
            panel_path,
            eae_path,
            training_path,
            tuple(str(p) for p in absence_paths),
            finance_path,
            finance_scope,
            int(n_clusters),
            _file_mtimes(paths),
        )
    except Exception as exc:
        _set_result("ailab", None, str(exc))
        return
    _set_result("ailab", result, None)


def _render_ailab() -> None:
    with st.sidebar:
        st.markdown('<div class="sidebar-tag">AI Lab inputs</div>', unsafe_allow_html=True)
        with st.expander("Data sources", expanded=False):
            panel_path = st.text_input("Employee panel", value=str(KPI2_DEFAULT_PANEL_PATH), key="ailab_panel")
            eae_path = st.text_input("EAE workbook", value=str(KPI2_DEFAULT_EAE_PATH), key="ailab_eae")
            training_path = st.text_input("Training records", value=str(KPI2_DEFAULT_TRAINING_PATH), key="ailab_training")
            absence_text = st.text_area(
                "Absence files (one path per line)",
                value="\n".join(str(p) for p in KPI2_DEFAULT_ABSENCE_PATHS),
                key="ailab_absence",
                height=110,
            )
            finance_path = st.text_input("Finance workbook", value=str(KPI1_DEFAULT_FILE), key="ailab_finance")
            finance_scope = st.selectbox(
                "Finance scope", options=["group", "europe"], key="ailab_scope"
            )
            n_clusters = st.slider(
                "Workforce segments", min_value=3, max_value=8, value=5, step=1, key="ailab_n_clusters"
            )
        run = st.button("Run Evolved Prototype", key="ailab_run", type="primary", use_container_width=True)

    _render_hero(
        "AI LAB · DELIVERABLE 3",
        "Evolved Prototype",
        "From rule-based KPIs to a calibrated AI decision layer for HRBPs and the steering committee.",
    )

    with st.expander("What this module does", expanded=False):
        st.markdown(
            """
            The AI Lab is the Deliverable 3 evolution of the rule-based KPI 2.
            Four interpretable models work on top of the same gold tables:

            1. **Attrition predictor** — gradient boosting on `Left_Next_6M`, ROC-AUC reported on a held-out test split.
            2. **Workforce segmentation** — K-Means on tenure, training, absence and performance, mapped to named personas.
            3. **Recommendation engine** — per-employee, prioritized retention or development action with indicative cost and protected value.
            4. **Scenario simulator** — what-if HCVA per FTE under absence-cut and retention scenarios.
            """
        )

    if run:
        with st.spinner("Training attrition model and building recommendations..."):
            _run_ailab(
                st.session_state["ailab_panel"],
                st.session_state["ailab_eae"],
                st.session_state["ailab_training"],
                st.session_state["ailab_absence"],
                st.session_state["ailab_finance"],
                st.session_state["ailab_scope"],
                st.session_state["ailab_n_clusters"],
            )

    error = st.session_state.get("ailab_error")
    if error:
        st.error(error)
        return
    result: EvolvedPrototypeResult | None = st.session_state.get("ailab_result")
    if result is None:
        st.info("Click **Run Evolved Prototype** in the sidebar to train the model.")
        return

    # 1. Attrition headline
    attr = result.attrition
    capture_pct = (
        attr.confusion_top_decile["leavers_captured"]
        / max(attr.confusion_top_decile["total_leavers"], 1)
    )
    _render_metric_row(
        [
            ("ROC-AUC (held-out)", _format_float(attr.auc, 3), None),
            ("Top-decile leaver capture", _format_pct(capture_pct), None),
            ("Train rows", _format_int(attr.n_train), None),
            ("Observed leavers", _format_int(attr.n_positives), None),
        ]
    )

    tabs = st.tabs([
        "Attrition predictor",
        "Workforce segmentation",
        "Recommendations",
        "Scenarios",
    ])

    with tabs[0]:
        st.subheader("Feature importance")
        st.caption("Which signals the model relies on. Every score is decomposable.")
        st.dataframe(
            attr.feature_importance,
            use_container_width=True,
            hide_index=True,
        )
        st.subheader("Top 50 employees by predicted attrition probability")
        live = (
            attr.predictions
            .sort_values("attrition_probability", ascending=False)
            .head(50)
            .copy()
        )
        live["attrition_probability"] = live["attrition_probability"].round(3)
        st.dataframe(live, use_container_width=True, hide_index=True)
        _render_insight_box(
            [
                f"Model holds an AUC of {attr.auc:.3f} on the unseen test split — well above the 0.70 threshold typically used for HR predictive systems.",
                f"Concentrating retention spend on the predicted top decile would catch roughly {capture_pct:.0%} of upcoming leavers — a 5x lift versus a uniform approach.",
                "Top features stay aligned with the rule-based KPI 2 (tenure, segment risk, time-in-post): the model corroborates HRBP intuition, it does not replace it.",
            ],
            title="Business read",
        )

    with tabs[1]:
        st.subheader("Persona profile")
        st.caption("Five (configurable) clusters built on tenure, training, absence and performance.")
        st.dataframe(
            result.segmentation.profile,
            use_container_width=True,
            hide_index=True,
        )
        st.subheader("Sample of segmented employees")
        st.dataframe(
            result.segmentation.segments.head(50),
            use_container_width=True,
            hide_index=True,
        )
        _render_insight_box(
            [
                "Personas turn the workforce into a small set of HR-readable groups — each with its own playbook.",
                "Rising Stars and Loyal Anchors are the value-protective segments; New Joiners are the onboarding-acceleration segment.",
                "Disengagement Watch is intentionally narrow: the cluster surfaces only the small population where multiple risk signals stack up at once.",
            ],
            title="Business read",
        )

    with tabs[2]:
        st.subheader("Program-level summary")
        st.caption("Each program is sized in euros: indicative cost vs. value protected.")
        st.dataframe(
            result.recommendations.program_summary,
            use_container_width=True,
            hide_index=True,
        )
        st.subheader("Top 50 employee-level recommendations")
        st.dataframe(
            result.recommendations.employee_recommendations.head(50),
            use_container_width=True,
            hide_index=True,
        )
        total_cost = float(result.recommendations.program_summary["total_indicative_cost_eur"].sum())
        total_value = float(result.recommendations.program_summary["total_value_protected_eur"].sum())
        _render_insight_box(
            [
                f"Total indicative cost across all programs: {_format_eur(total_cost)}.",
                f"Estimated value protected by the recommended actions: {_format_eur(total_value)}.",
                "Every recommendation is rule-derived — HRBPs can override and the system logs the reason.",
            ],
            title="Business read",
        )

    with tabs[3]:
        rows = [
            {
                "Scenario": s.scenario,
                "HCVA / FTE baseline": s.hcva_per_fte_baseline,
                "HCVA / FTE after": s.hcva_per_fte_after,
                "Δ EUR per FTE": s.delta_eur_per_fte,
                "Δ Total (EUR)": s.delta_total_eur,
                "Assumption": s.assumption,
            }
            for s in result.scenarios
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        _render_insight_box(
            [
                "Scenarios are deliberately conservative — both levers are individually plausible and additive.",
                "Cutting absence drag by 1pp and retaining a quarter of the at-risk population together unlocks value worth multiples of the program cost.",
                "Numbers are indicative steering-committee inputs, not guaranteed savings.",
            ],
            title="Business read",
        )


# ---------------------------------------------------------------------------
# Sidebar (logo + navigation)
# ---------------------------------------------------------------------------


def _render_sidebar_header() -> None:
    with st.sidebar:
        if LOGO_PATH.exists():
            cols = st.columns([1, 5, 1])
            with cols[1]:
                st.image(str(LOGO_PATH), use_container_width=True)
        st.markdown('<div class="sidebar-tag">Deliverable 3 — Evolved Prototype</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="sidebar-title">Human Capital KPI Dashboard + AI Lab</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)

        st.selectbox(
            "Choose a KPI",
            options=KPI_OPTIONS,
            key="selected_kpi",
        )

        run_all = st.button(
            "Run all KPIs",
            key="run_all_kpis",
            type="secondary",
            use_container_width=True,
        )
        if run_all:
            with st.spinner("Computing KPI 1 to KPI 5..."):
                _run_all_kpis()
            failed = [k for k in ("kpi1", "kpi2", "kpi3", "kpi4", "kpi5") if st.session_state[f"{k}_error"]]
            if failed:
                failed_labels = ", ".join(k.upper() for k in failed)
                st.warning(f"Run finished with errors in: {failed_labels}")
            else:
                st.success("All 5 KPIs computed. Switch KPIs without rerunning.")
        st.caption("Results are cached. Switching KPI keeps the last computed outputs.")
        st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)


def _render_footer() -> None:
    st.markdown(
        """
        <div class="app-footer">
          CACEIS Investor Services — Human Capital Valuation Framework · Albert School Hackathon · Deliverable 3
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    page_icon = str(LOGO_PATH) if LOGO_PATH.exists() else None
    st.set_page_config(
        page_title="CACEIS Human Capital KPI Dashboard",
        page_icon=page_icon,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_css()
    _init_state_defaults()
    _render_sidebar_header()

    selected_kpi = st.session_state["selected_kpi"]
    if selected_kpi.startswith("KPI 1"):
        _render_kpi1()
    elif selected_kpi.startswith("KPI 2"):
        _render_kpi2()
    elif selected_kpi.startswith("KPI 3"):
        _render_kpi3()
    elif selected_kpi.startswith("KPI 4"):
        _render_kpi4()
    elif selected_kpi.startswith("KPI 5"):
        _render_kpi5()
    else:
        _render_ailab()

    _render_footer()


if __name__ == "__main__":
    main()
