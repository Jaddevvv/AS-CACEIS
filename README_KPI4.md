# KPI 4 Deliverable (Streamlit + Python Pipeline)

This implementation covers **KPI 4: Absence Productivity Drag** from `KPI_PLAN.txt`.

## Files

- `kpi4_pipeline.py`: absence data loading/standardization, monthly and yearly drag computation, entity/reason analysis, and interpretation.
- `streamlit_kpi4_app.py`: interactive Streamlit dashboard for KPI 4 outputs.

## Data Sources

- `Sujet Alberthon/HR Data/Data.xlsx` (`Sheet1`) for employee-month population and segmentation.
- Absence files:
  - `Sujet Alberthon/HR Data/Absentéisme_-_détail_affectation_-_Bilan_social.xlsx` (2023)
  - `Sujet Alberthon/HR Data/Absentéisme_-_détail_affectation_-_Bilan_social (1).xlsx` (2024)
  - `Sujet Alberthon/HR Data/20260121 - Absentéisme_-_détail_affectation_-_Bilan_social 2025.xlsx` (2025)
- `Sujet Alberthon/Finance/AlbertSchool_CACEIS_PL-FTE_22-25_Sent.xlsx` for yearly `Average FTE` and `HCVA per FTE` (via KPI 1 logic).

## Mapping to KPI_PLAN Steps

1. **Load absence files for 2023, 2024, 2025** (`load_absence_standardized`)
2. **Standardize employee ID, month, reason, absence days** (`_read_absence_rows`, `load_absence_standardized`)
3. **Aggregate by month, entity, reason, employee** (`aggregate_employee_month_entity_reason`)
4. **Convert absence days into lost FTE** (`compute_monthly_drag`)
5. **Multiply lost FTE by HCVA per FTE** (`compute_yearly_drag`, entity/reason yearly outputs)

## KPI 4 Formulas Implemented

- `Total Absence Days = SUM(Jours Ouvrés Absence)`
- `Lost FTE = Total Absence Days / 220`
- `Absence Days per Employee = Total Absence Days / Number of Employees`
- `Absence Productivity Drag = Lost FTE / Average FTE`
- `Estimated Value Lost = Lost FTE * HCVA per FTE`

## Notes

- Absence loader auto-detects sheet/header variations across the 2023/2024/2025 files.
- Employee counts for monthly ratios come from the HR panel (`Data.xlsx`); yearly drag denominator uses finance `Average FTE`.
- Finance scope (`group` vs `europe`) is configurable in the Streamlit app.

## Run

```bash
rtk python -m pip install -r requirements.txt
rtk streamlit run streamlit_kpi4_app.py
```
