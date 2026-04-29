# KPI 1 Deliverable (Streamlit + Python Pipeline)

This implementation covers **KPI 1: HCVA / HCROI per FTE** from `KPI_PLAN.txt`.

## Files

- `kpi1_pipeline.py`: data extraction, transformation, KPI calculations, and trend interpretation.
- `streamlit_kpi1_app.py`: interactive Streamlit dashboard for KPI 1.

## Data Source

- `Sujet Alberthon/Finance/AlbertSchool_CACEIS_PL-FTE_22-25_Sent.xlsx`
  - Sheet `Synthese_PL`
  - Sheet `Synthese_ETP`

## Mapping to KPI_PLAN Steps

1. **Extract yearly P&L rows** (`extract_pl_rows`)
   - Rows used: `Net Banking Income (PNB)`, `Other Operating Costs`, `Total Personnel Costs`
2. **Extract yearly average FTE** (`extract_avg_fte`)
   - From `ETP moyen période` columns in `Synthese_ETP`
3. **Build yearly KPI table** (`build_kpi1_table`)
   - Years: 2022, 2023, 2024, 2025
4. **Plot KPI visuals** (`streamlit_kpi1_app.py`)
   - HCVA per FTE
   - HCROI
   - Revenue per FTE
5. **Business interpretation** (`summarize_trend`)
   - Automatic trend commentary from first-to-last year movement

## KPI Formulas Implemented

- `HCVA = PNB - Other Operating Costs`
- `HCVA per FTE = HCVA / Average FTE`
- `HCROI = HCVA / Total Personnel Costs`
- `Revenue per FTE = PNB / Average FTE`

Note: cost rows are negative in the source file. The pipeline converts them to positive cost amounts before KPI calculations.

## Run

```bash
rtk python -m pip install pandas openpyxl streamlit
rtk streamlit run streamlit_kpi1_app.py
```

