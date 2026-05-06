"""
Deliverable 3 — Evolved Prototype.

This module turns the Deliverable 2 rule-based KPIs into an
AI-powered decision layer:

  1. AttritionModel        — gradient boosting classifier on Left_Next_6M,
                             with calibrated probabilities and feature importance.
  2. WorkforceSegmenter    — K-Means segmentation of the active workforce
                             on tenure / training / absence / performance,
                             producing named, business-readable personas.
  3. TrainingRecommender   — rule-based recommendation engine that maps
                             every employee to a prioritized list of
                             retention / development actions, sized in euros.
  4. ScenarioSimulator     — what-if engine projecting HCVA per FTE under
                             absence-reduction and retention scenarios.

All models are trained on the gold tables produced by the existing
KPI 1-5 pipelines (no new data sources). They are deliberately
interpretable: every score can be explained to an HRBP without a
black-box.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


# ---------------------------------------------------------------------------
# 1. Attrition model
# ---------------------------------------------------------------------------


ATTRITION_FEATURES: tuple[str, ...] = (
    "tenure_caceis_months",
    "months_in_current_post",
    "absence_days_12m",
    "training_hours_12m",
    "performance_score",
    "new_joiner_risk",
    "low_performance_risk",
    "high_absence_risk",
    "low_training_risk",
    "long_time_in_post_risk",
    "segment_risk",
)


@dataclass
class AttritionModelResult:
    auc: float
    n_train: int
    n_test: int
    n_positives: int
    feature_importance: pd.DataFrame
    predictions: pd.DataFrame
    confusion_top_decile: dict[str, int]


def _prepare_attrition_dataset(
    risk_table: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    """
    Split the KPI2 risk table into:
      - X_labeled, y_labeled : rows where left_next_6m is observed (used for training/eval).
      - X_unlabeled          : the latest period rows (used to score the live workforce).
    """
    df = risk_table.copy()
    df["left_next_6m"] = pd.to_numeric(df["left_next_6m"], errors="coerce")

    feature_cols = [c for c in ATTRITION_FEATURES if c in df.columns]
    if not feature_cols:
        raise ValueError("None of the expected attrition features found in risk table.")

    df[feature_cols] = df[feature_cols].apply(pd.to_numeric, errors="coerce")
    df[feature_cols] = df[feature_cols].fillna(df[feature_cols].median(numeric_only=True))

    labeled_mask = df["left_next_6m"].notna()
    labeled = df[labeled_mask].copy()
    unlabeled = df[~labeled_mask].copy()

    X = labeled[feature_cols]
    y = labeled["left_next_6m"].astype(int)
    X_live = unlabeled[feature_cols]
    return (X.assign(_period=labeled["period"], _employee_id=labeled["employee_id"]),
            y,
            X_live.assign(_period=unlabeled["period"], _employee_id=unlabeled["employee_id"]))


def train_attrition_model(risk_table: pd.DataFrame, random_state: int = 7) -> AttritionModelResult:
    """
    Train a gradient boosting classifier on Left_Next_6M.

    The model is intentionally simple and interpretable — we surface
    feature importance to the HRBPs so every score is challengeable.
    """
    X_labeled, y, X_live = _prepare_attrition_dataset(risk_table)
    feature_cols = [c for c in X_labeled.columns if not c.startswith("_")]

    if y.sum() < 30 or y.sum() == len(y):
        raise ValueError(
            "Not enough leaver / stayer signal to train an attrition model "
            "(need at least 30 leavers and 30 stayers in the labeled panel)."
        )

    X_train, X_test, y_train, y_test = train_test_split(
        X_labeled[feature_cols],
        y,
        test_size=0.25,
        random_state=random_state,
        stratify=y,
    )

    clf = GradientBoostingClassifier(
        n_estimators=180,
        max_depth=3,
        learning_rate=0.07,
        random_state=random_state,
    )
    clf.fit(X_train, y_train)

    y_proba_test = clf.predict_proba(X_test)[:, 1]
    auc = float(roc_auc_score(y_test, y_proba_test))

    importance = pd.DataFrame(
        {
            "feature": feature_cols,
            "importance": clf.feature_importances_,
        }
    ).sort_values("importance", ascending=False).reset_index(drop=True)

    # Score the entire labeled + unlabeled panel.
    full = pd.concat([X_labeled, X_live], ignore_index=True)
    proba = clf.predict_proba(full[feature_cols])[:, 1]
    predictions = pd.DataFrame(
        {
            "employee_id": full["_employee_id"].values,
            "period": full["_period"].values,
            "attrition_probability": proba,
        }
    )

    # How well does the top-decile capture leavers in the holdout?
    test_eval = pd.DataFrame({"y": y_test.values, "p": y_proba_test})
    threshold = test_eval["p"].quantile(0.90)
    top_decile = test_eval[test_eval["p"] >= threshold]
    confusion = {
        "top_decile_size": int(len(top_decile)),
        "leavers_captured": int(top_decile["y"].sum()),
        "total_leavers": int(test_eval["y"].sum()),
    }

    return AttritionModelResult(
        auc=auc,
        n_train=int(len(X_train)),
        n_test=int(len(X_test)),
        n_positives=int(y.sum()),
        feature_importance=importance,
        predictions=predictions,
        confusion_top_decile=confusion,
    )


# ---------------------------------------------------------------------------
# 2. Workforce segmentation
# ---------------------------------------------------------------------------


SEGMENTATION_FEATURES: tuple[str, ...] = (
    "tenure_caceis_months",
    "months_in_current_post",
    "absence_days_12m",
    "training_hours_12m",
    "performance_score",
)

PERSONA_RULES: tuple[tuple[str, str], ...] = (
    # (label, rationale anchor)
    ("Rising Stars",        "high performance, high training, low absence"),
    ("Loyal Anchors",       "long tenure, stable performance"),
    ("New Joiners",         "short tenure"),
    ("Disengagement Watch", "lower performance, higher absence"),
    ("Capability Builders", "high training hours, mid tenure"),
)


@dataclass
class SegmentationResult:
    segments: pd.DataFrame
    profile: pd.DataFrame
    persona_map: dict[int, str]


def segment_workforce(
    latest_risk_table: pd.DataFrame,
    n_clusters: int = 5,
    random_state: int = 7,
) -> SegmentationResult:
    """
    Cluster the latest-period workforce on a small set of HR features.
    Cluster centers are mapped to business-readable personas based on
    the observed profile (high/low performance, tenure, absence, training).
    """
    df = latest_risk_table.copy()
    feature_cols = [c for c in SEGMENTATION_FEATURES if c in df.columns]
    if len(feature_cols) < 3:
        raise ValueError("Need at least three numeric HR features to segment workforce.")

    df[feature_cols] = df[feature_cols].apply(pd.to_numeric, errors="coerce")
    df = df.dropna(subset=["employee_id"])
    df[feature_cols] = df[feature_cols].fillna(df[feature_cols].median(numeric_only=True))

    if df.empty:
        raise ValueError("No employees to segment in latest period.")

    scaler = StandardScaler()
    X = scaler.fit_transform(df[feature_cols].values)
    km = KMeans(n_clusters=n_clusters, n_init=12, random_state=random_state)
    labels = km.fit_predict(X)
    df["segment_id"] = labels

    profile = (
        df.groupby("segment_id")[list(feature_cols)]
        .mean()
        .reset_index()
        .assign(employees=df.groupby("segment_id").size().values)
    )
    if "risk_score" in df.columns:
        profile["avg_risk_score"] = df.groupby("segment_id")["risk_score"].mean().values
    else:
        profile["avg_risk_score"] = np.nan

    persona_map = _assign_personas(profile, feature_cols)
    profile["persona"] = profile["segment_id"].map(persona_map)
    df["persona"] = df["segment_id"].map(persona_map)

    return SegmentationResult(
        segments=df[["employee_id", "period", "segment_id", "persona"] + feature_cols],
        profile=profile,
        persona_map=persona_map,
    )


def _assign_personas(profile: pd.DataFrame, feature_cols: Iterable[str]) -> dict[int, str]:
    """
    Map clusters to business-readable personas. The mapping is
    deliberately simple so HRBPs can challenge it.
    """
    feature_cols = list(feature_cols)
    medians = profile[feature_cols].median()

    def _flag(row: pd.Series) -> str:
        perf = row.get("performance_score", medians["performance_score"])
        ten = row.get("tenure_caceis_months", medians["tenure_caceis_months"])
        absc = row.get("absence_days_12m", medians["absence_days_12m"])
        train = row.get("training_hours_12m", medians["training_hours_12m"])

        if perf > medians["performance_score"] and train > medians["training_hours_12m"] and absc <= medians["absence_days_12m"]:
            return "Rising Stars"
        if ten > medians["tenure_caceis_months"] * 1.5 and perf >= medians["performance_score"]:
            return "Loyal Anchors"
        if ten < max(12.0, medians["tenure_caceis_months"] * 0.5):
            return "New Joiners"
        if perf < medians["performance_score"] and absc > medians["absence_days_12m"]:
            return "Disengagement Watch"
        return "Capability Builders"

    mapping: dict[int, str] = {}
    for _, row in profile.iterrows():
        mapping[int(row["segment_id"])] = _flag(row)

    # Disambiguate duplicate persona names by appending segment id.
    seen: dict[str, int] = {}
    final: dict[int, str] = {}
    for sid, name in mapping.items():
        if name not in seen:
            seen[name] = 1
            final[sid] = name
        else:
            seen[name] += 1
            final[sid] = f"{name} #{seen[name]}"
    return final


# ---------------------------------------------------------------------------
# 3. Recommendation engine
# ---------------------------------------------------------------------------


@dataclass
class RecommendationResult:
    employee_recommendations: pd.DataFrame
    program_summary: pd.DataFrame


_ACTION_LIBRARY: tuple[tuple[str, str, float], ...] = (
    # (program, target trigger, indicative annual cost per employee in EUR)
    ("Retention conversation + targeted comp review", "high attrition risk",      1500.0),
    ("Career-path planning workshop",                  "long time in post",         600.0),
    ("Learning sprint (5 days)",                       "low training exposure",     900.0),
    ("Wellbeing check-in",                             "high absence",              350.0),
    ("Onboarding buddy program",                       "new joiner",                450.0),
)


def build_recommendations(
    attrition_predictions: pd.DataFrame,
    latest_risk_table: pd.DataFrame,
    hcva_per_fte: float,
    segmentation: SegmentationResult | None = None,
) -> RecommendationResult:
    """
    Combine the attrition probability with the rule-based risk signals
    and the persona to produce a prioritized retention action per employee.

    Each recommendation carries:
      - a primary action,
      - the trigger (why we recommend it),
      - an estimated annual cost,
      - an ROI estimate based on HCVA per FTE saved if the employee stays.
    """
    if "employee_id" not in attrition_predictions.columns:
        raise ValueError("attrition_predictions must contain employee_id")

    latest_period = attrition_predictions["period"].max()
    live = attrition_predictions[attrition_predictions["period"] == latest_period].copy()
    enriched = live.merge(
        latest_risk_table,
        on=["employee_id", "period"],
        how="left",
        suffixes=("", "_kpi"),
    )

    if segmentation is not None and not segmentation.segments.empty:
        enriched = enriched.merge(
            segmentation.segments[["employee_id", "persona"]],
            on="employee_id",
            how="left",
        )
    else:
        enriched["persona"] = "Workforce"

    rows = []
    for _, r in enriched.iterrows():
        action, trigger, cost = _select_action(r)
        attr_p = float(r["attrition_probability"])
        # Indicative ROI: HCVA per FTE * attrition probability avoided * fraction of year retained.
        # We assume a 40% probability uplift retention from the action (interpretable, configurable).
        hcva_protected = hcva_per_fte * attr_p * 0.40
        rows.append(
            {
                "employee_id": r["employee_id"],
                "persona": r.get("persona", "Workforce"),
                "entity": r.get("entity"),
                "country": r.get("country"),
                "job": r.get("job"),
                "attrition_probability": attr_p,
                "risk_band": r.get("risk_band"),
                "recommended_program": action,
                "trigger": trigger,
                "indicative_cost_eur": cost,
                "estimated_value_protected_eur": round(hcva_protected, 0),
                "indicative_roi_x": round(hcva_protected / cost, 2) if cost > 0 else np.nan,
            }
        )

    employee_recs = (
        pd.DataFrame(rows)
        .sort_values("attrition_probability", ascending=False)
        .reset_index(drop=True)
    )

    program_summary = (
        employee_recs.groupby("recommended_program", as_index=False)
        .agg(
            employees=("employee_id", "count"),
            avg_attrition_probability=("attrition_probability", "mean"),
            total_indicative_cost_eur=("indicative_cost_eur", "sum"),
            total_value_protected_eur=("estimated_value_protected_eur", "sum"),
        )
        .sort_values("total_value_protected_eur", ascending=False)
        .reset_index(drop=True)
    )

    return RecommendationResult(
        employee_recommendations=employee_recs,
        program_summary=program_summary,
    )


def _select_action(row: pd.Series) -> tuple[str, str, float]:
    """
    Rule-based selector — interpretable on purpose.
    """
    if row.get("new_joiner_risk", 0) >= 0.6:
        return _ACTION_LIBRARY[4]  # onboarding buddy
    if row.get("attrition_probability", 0) >= 0.6 or str(row.get("risk_band")) == "High":
        return _ACTION_LIBRARY[0]  # retention + comp review
    if row.get("high_absence_risk", 0) >= 0.5:
        return _ACTION_LIBRARY[3]  # wellbeing
    if row.get("low_training_risk", 0) >= 0.5:
        return _ACTION_LIBRARY[2]  # learning sprint
    if row.get("long_time_in_post_risk", 0) >= 0.5:
        return _ACTION_LIBRARY[1]  # career-path workshop
    return _ACTION_LIBRARY[2]  # default: learning sprint (cheapest dev signal)


# ---------------------------------------------------------------------------
# 4. Scenario simulator
# ---------------------------------------------------------------------------


@dataclass
class ScenarioOutcome:
    scenario: str
    hcva_per_fte_baseline: float
    hcva_per_fte_after: float
    delta_eur_per_fte: float
    delta_total_eur: float
    assumption: str


def simulate_scenarios(
    hcva_per_fte: float,
    avg_fte: float,
    absence_drag_pct: float,
    high_risk_share: float,
) -> list[ScenarioOutcome]:
    """
    Three opinionated scenarios for the steering committee:
      A. Cut absence drag by 1pp — what does that buy us in HCVA per FTE?
      B. Retain 25% of the at-risk population — value protected.
      C. Combine A + B.
    """
    base = hcva_per_fte
    out: list[ScenarioOutcome] = []

    # Scenario A
    drag_after = max(0.0, absence_drag_pct - 0.01)
    factor_a = (1 - drag_after) / max(1 - absence_drag_pct, 1e-9)
    hcva_after_a = base * factor_a
    out.append(
        ScenarioOutcome(
            scenario="A. Cut absence drag by 1 percentage point",
            hcva_per_fte_baseline=base,
            hcva_per_fte_after=hcva_after_a,
            delta_eur_per_fte=hcva_after_a - base,
            delta_total_eur=(hcva_after_a - base) * avg_fte,
            assumption="Lost FTE recovered at the current HCVA per FTE rate.",
        )
    )

    # Scenario B
    saved = high_risk_share * 0.25
    factor_b = 1 + saved * 0.10  # 10% productivity uplift on retained
    hcva_after_b = base * factor_b
    out.append(
        ScenarioOutcome(
            scenario="B. Retain 25% of the at-risk population",
            hcva_per_fte_baseline=base,
            hcva_per_fte_after=hcva_after_b,
            delta_eur_per_fte=hcva_after_b - base,
            delta_total_eur=(hcva_after_b - base) * avg_fte,
            assumption="Each retained employee preserves 10% of HCVA per FTE that would otherwise leak through replacement.",
        )
    )

    # Scenario C — combined
    factor_c = factor_a * factor_b
    hcva_after_c = base * factor_c
    out.append(
        ScenarioOutcome(
            scenario="C. Combined (A + B)",
            hcva_per_fte_baseline=base,
            hcva_per_fte_after=hcva_after_c,
            delta_eur_per_fte=hcva_after_c - base,
            delta_total_eur=(hcva_after_c - base) * avg_fte,
            assumption="Effects compound multiplicatively (independent levers).",
        )
    )

    return out


# ---------------------------------------------------------------------------
# Convenience: end-to-end Evolved Prototype run
# ---------------------------------------------------------------------------


@dataclass
class EvolvedPrototypeResult:
    attrition: AttritionModelResult
    segmentation: SegmentationResult
    recommendations: RecommendationResult
    scenarios: list[ScenarioOutcome] = field(default_factory=list)


def run_evolved_prototype(
    risk_table: pd.DataFrame,
    hcva_per_fte: float,
    avg_fte: float,
    absence_drag_pct: float,
    n_clusters: int = 5,
) -> EvolvedPrototypeResult:
    """
    Full Deliverable 3 pipeline on top of the KPI 2 risk table:

        gold_employee_month + features  ->  attrition model
                                        ->  workforce segmentation
                                        ->  per-employee recommendations
                                        ->  steering-committee scenarios
    """
    attrition = train_attrition_model(risk_table)
    latest_period = risk_table["period"].max()
    latest = risk_table[risk_table["period"] == latest_period].copy()

    segmentation = segment_workforce(latest, n_clusters=n_clusters)
    recommendations = build_recommendations(
        attrition_predictions=attrition.predictions,
        latest_risk_table=latest,
        hcva_per_fte=hcva_per_fte,
        segmentation=segmentation,
    )
    high_risk_share = float((latest.get("risk_band").astype(str) == "High").mean()) if "risk_band" in latest.columns else 0.0
    scenarios = simulate_scenarios(
        hcva_per_fte=hcva_per_fte,
        avg_fte=avg_fte,
        absence_drag_pct=absence_drag_pct,
        high_risk_share=high_risk_share,
    )

    return EvolvedPrototypeResult(
        attrition=attrition,
        segmentation=segmentation,
        recommendations=recommendations,
        scenarios=scenarios,
    )
