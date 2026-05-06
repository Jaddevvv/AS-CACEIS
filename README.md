# Human Capital Valuation at CACEIS

This repository contains our CACEIS hackathon project to value human capital as a measurable business asset, not only as an operating cost.

The project combines:
- a conceptual framework and data architecture,
- a production-style KPI analytics pipeline,
- an explainable AI prototype for risk prediction, workforce segmentation, and scenario simulation.

## Deliverables

| Deliverable | File | Purpose |
|---|---|---|
| Deliverable 1 | `Deliverable1.txt` | Concept paper: ideal data ecosystem, architecture, governance, and KPI framework for human capital valuation. |
| Deliverable 2 | `CACEIS_Deliverable2.pptx` | Executive presentation of the 5-KPI valuation framework and business narrative. |
| Deliverable 3 | `CACEIS_Deliverable3_Final.pptx` | Final report deck with KPI results, AI layer, governance, and implementation roadmap. |

## What Is Implemented in Code

### 5 KPI pipelines

- `kpi1_pipeline.py` - HCVA / HCROI per FTE (financial value creation)
- `kpi2_pipeline.py` - Workforce Value-at-Risk (forward-looking attrition risk)
- `kpi3_pipeline.py` - Learning-to-Performance Index (training effectiveness)
- `kpi4_pipeline.py` - Absence Productivity Drag (lost capacity and value)
- `kpi5_pipeline.py` - Role Cost Efficiency Index (cost vs performance alignment)

### AI evolved prototype (Deliverable 3)

- `ai_module.py`
  - attrition prediction model,
  - workforce persona segmentation,
  - training/retention recommendation engine,
  - HCVA what-if scenario simulator.

### Unified dashboard

- `streamlit_app.py` - single Streamlit application to run and visualize all KPIs + AI Lab.

## Repository Structure

```text
.
├── Deliverable1.txt
├── CACEIS_Deliverable2.pptx
├── CACEIS_Deliverable3_Final.pptx
├── streamlit_app.py
├── ai_module.py
├── kpi1_pipeline.py
├── kpi2_pipeline.py
├── kpi3_pipeline.py
├── kpi4_pipeline.py
├── kpi5_pipeline.py
├── requirements.txt
└── Sujet Alberthon/           # source datasets (HR, Finance, Training)
```

## Quick Start

### 1) Install dependencies

```bash
rtk python -m pip install -r requirements.txt
```

### 2) Launch the app

```bash
rtk streamlit run streamlit_app.py
```

Then open the local Streamlit URL (usually `http://localhost:8501`).

## Data Dependencies

The pipelines expect Excel source files under `Sujet Alberthon/` (HR, Finance, Training), including:

- `Sujet Alberthon/Finance/AlbertSchool_CACEIS_PL-FTE_22-25_Sent.xlsx`
- `Sujet Alberthon/HR Data/Data.xlsx`
- `Sujet Alberthon/HR Data/20250218 - Stats CACEIS EAE EP 18-02-2025 Version Définitive cloture.xlsx`
- `Sujet Alberthon/Training/Training_Records_Unnamed.xlsx`
- related absence/quick review/cold review files referenced in KPI modules.

Default paths are preconfigured in the pipeline modules and in `streamlit_app.py`. If data is moved, update file paths in the app sidebar inputs.

## KPI Summary

1. **KPI 1 - HCVA / HCROI per FTE**: measures workforce financial productivity and return on personnel cost.
2. **KPI 2 - Workforce Value-at-Risk**: scores near-term attrition/value-loss risk using tenure, performance, absence, training, and segment signals.
3. **KPI 3 - Learning-to-Performance Index**: links L&D investment quality to observed performance impact.
4. **KPI 4 - Absence Productivity Drag**: converts absence days into lost FTE and estimated value lost.
5. **KPI 5 - Role Cost Efficiency Index**: benchmarks role-level compensation against role-level performance.

## Governance and Design Principles

- explainable metrics and models (business-readable drivers),
- role-level compensation benchmarking only (no individual salary scoring),
- privacy-aware analytics approach aligned with HR governance expectations,
- CFO/CHRO-ready outputs in financial units where possible.

## Team

Project contributors:
- Mohamed Jad KABBAJ
- Femi FACIA
- Jean-Baptiste BRUN
- Ilyes KABBOUR

