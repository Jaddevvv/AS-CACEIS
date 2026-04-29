# KPI 3 Deliverable (Streamlit + Python Pipeline)

This implementation covers **KPI 3: Learning-to-Performance Index** from `KPI_PLAN.txt`.

## Files

- `kpi3_pipeline.py`: data extraction, aggregation, scoring, trained vs non-trained comparison, and interpretation.
- `streamlit_kpi3_app.py`: interactive Streamlit dashboard for KPI 3 outputs.

## Data Sources

- `Sujet Alberthon/HR Data/Data.xlsx` (`Sheet1`) for employee-year population
- `Sujet Alberthon/Training/Training_Records_Unnamed.xlsx` (`Final_CSV`) for training hours/count/certification
- `Sujet Alberthon/Training/Quick_Review_Unnamed.xlsx` (`Data`) for quick review score
- `Sujet Alberthon/Training/Cold_Review_Unnamed.xlsx` (`Data`) for cold impact score
- `Sujet Alberthon/HR Data/20250218 - Stats CACEIS EAE EP 18-02-2025 Version Définitive cloture.xlsx` (`Database`) for EAE performance score

## Mapping to KPI_PLAN Steps

1. **Aggregate training records by employee-year** (`aggregate_training_records`)
2. **Aggregate quick and cold review scores** (`aggregate_quick_reviews`, `aggregate_cold_reviews`)
3. **Join with EAE performance scores** (`build_learning_performance_table`)
4. **Compare trained vs non-trained employees** (`build_kpi3_result`)
5. **Plot training hours vs performance / impact score** (`streamlit_kpi3_app.py`)

## KPI 3 Formulas Implemented

- `Training_Hours = SUM(Total_Training_Hours)`
- `Training_Count = COUNT(Session_ID)`
- `Quick_Review_Score = AVG(Note générale)`
- `Cold_Impact_Score = average converted cold-review answers`

Cold review mapping:

- `Oui, tout à fait` or `Oui` -> `1.0`
- `Oui, en partie` -> `0.5`
- `Non*` -> `0.0`

Main KPI:

- `Learning-to-Performance Index`
- `= 0.40 * Normalized Training Hours`
- `+ 0.30 * Normalized Cold Impact Score`
- `+ 0.20 * Normalized Quick Review Score`
- `+ 0.10 * Certification Flag`

## Notes

- Training aggregation keeps completed/effective records (`Réalisé` status, or positive hours with empty status).
- Training-hours normalization uses year-level P95 clipping to limit outlier influence.
- EAE performance coverage in available files is annual and mostly year 2024.

## Run

```bash
rtk python -m pip install -r requirements.txt
rtk streamlit run streamlit_kpi3_app.py
```
