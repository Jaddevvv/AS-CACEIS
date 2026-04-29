# KPI 5 Deliverable (Streamlit + Python Pipeline)

This implementation covers **KPI 5: Role Cost Efficiency Index** from `KPI_PLAN.txt`.

## Files

- `kpi5_pipeline.py`: compensation transformation, role-level joins, KPI calculations, quadrant tagging, and interpretation.
- `streamlit_kpi5_app.py`: interactive Streamlit dashboard for KPI 5 outputs.

## Data Sources

- `Sujet Alberthon/HR Data/Data.xlsx`
  - `Compensation Data FR`
  - `Compensation Data LU`
  - `Sheet1` (employee job/country/year alignment)
- `Sujet Alberthon/HR Data/20250218 - Stats CACEIS EAE EP 18-02-2025 Version Définitive cloture.xlsx` (`Database`) for EAE performance

## Mapping to KPI_PLAN Steps

1. **Transform compensation FR/LU sheets into clean long format** (`load_compensation_long`)
2. **Join compensation benchmark to employee job/country/year** (`build_employee_year_roles`, `build_role_cost_table`)
3. **Aggregate EAE performance by job/country/year** (`aggregate_role_performance`)
4. **Calculate role compensation index and role cost efficiency** (`build_role_cost_table`)
5. **Build cost-performance quadrant chart** (`streamlit_kpi5_app.py`)

## KPI 5 Formulas Implemented

- `Average Total Compensation = Average Fixed Salary + Average Variable Salary`
- `Variable Pay Ratio = Average Variable Salary / Average Total Compensation`
- `Role Compensation Index = Average Total Compensation / Median Average Total Compensation (same country-year)`
- `Average Role Performance = AVG(EAE Performance Score) by role/year/country`
- `Role Cost Efficiency = Normalized Average Role Performance / Role Compensation Index`

Quadrants:

- `High cost + high performance` -> strategic high-value role
- `High cost + low performance` -> efficiency risk
- `Low cost + high performance` -> retention risk
- `Low cost + low performance` -> low-impact role

## Notes

- Compensation input is a **role-level benchmark**, not employee-level salary.
- EAE country mapping uses `FR -> France` and `INT -> Luxembourg` for this dataset layout.
- Normalized role performance is centered by country-year median (fallback to 1-5 scaled normalization when needed).

## Run

```bash
rtk python -m pip install -r requirements.txt
rtk streamlit run streamlit_kpi5_app.py
```
