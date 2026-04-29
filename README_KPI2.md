# KPI 2 Deliverable (Streamlit + Python Pipeline)

This implementation covers **KPI 2: Workforce Value-at-Risk** from `KPI_PLAN.txt`.

## Files

- `kpi2_pipeline.py`: employee-month table build, leave-label logic, feature engineering, risk scoring, and summaries.
- `streamlit_kpi2_app.py`: interactive Streamlit dashboard for KPI 2 outputs.

## Data Sources

- `Sujet Alberthon/HR Data/Data.xlsx` (`Sheet1`) for employee-month base panel
- `Sujet Alberthon/HR Data/20250218 - Stats CACEIS EAE EP 18-02-2025 Version Définitive cloture.xlsx` (`Database`) for performance
- `Sujet Alberthon/Training/Training_Records_Unnamed.xlsx` (`Final_CSV`) for training
- Absence files:
  - `Sujet Alberthon/HR Data/Absentéisme_-_détail_affectation_-_Bilan_social.xlsx`
  - `Sujet Alberthon/HR Data/Absentéisme_-_détail_affectation_-_Bilan_social (1).xlsx`
  - `Sujet Alberthon/HR Data/20260121 - Absentéisme_-_détail_affectation_-_Bilan_social 2025.xlsx`

## Mapping to KPI_PLAN Steps

1. **Build employee-month table** (`build_employee_month_table`)
2. **Detect employees who disappear from panel** (`detect_left_next_6m`)
3. **Join EAE, training, and absence features** (`enrich_kpi2_features`)
4. **Create risk score** (`compute_risk_scores`)
5. **Show top-risk entities/jobs/segments** (`build_kpi2_result`, `streamlit_kpi2_app.py`)

## KPI 2 Formulas Implemented

- `Left_Next_6M = 1` if employee has no presence in next 6 panel months, else `0`
- `Tenure_CACEIS_Months = PERIOD - DATE_ENTRY_CACEIS`
- `Months_In_Current_Post = PERIOD - DATE_ENTRY_POSTE`
- `Absence_Days_12M = trailing 12-month sum of absence days`
- `Training_Hours_12M = trailing 12-month sum of training hours`

Risk score weights:

- `0.25 * New Joiner Risk`
- `+ 0.20 * Low Performance Risk`
- `+ 0.20 * High Absence Risk`
- `+ 0.15 * Low Training Risk`
- `+ 0.10 * Long Time In Post Risk`
- `+ 0.10 * Segment Risk`

## Notes

- Absence loader auto-detects sheet/header layout differences across the 2023/2024/2025 files.
- Last 6 months in the panel have no observable `Left_Next_6M` label (right-censoring).

## Run

```bash
rtk python -m pip install -r requirements.txt
rtk streamlit run streamlit_kpi2_app.py
```
