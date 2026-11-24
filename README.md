# Terra-Vol-Global
End-to-end supply chain &amp; financial control software for BESS and solar energy developers, EPCs, and IPPs


## Code structure

| File | Purpose |
|---|---|
| `app.py` | Streamlit entry point — runs the files in `sections/` in name order, in one shared namespace |
| `sections/00_setup.py` | Imports, constants, helpers (project save/load wrapper, geo, surcharge table), page style |
| `sections/05_sidebar_and_tabs.py` | Sidebar settings, header, tab layout |
| `sections/10_…` – `34_…` | One file per tab (Project Brief, Offers Received, Equipment … Cash Flow, Budget vs Actual) |
| `sections/90_project_file.py` | Project restore function and project-file content |
| `sections/91_scenarios.py` | Scenarios tab |
| `sections/99_save_load_footer.py` | Save / load buttons, footer |
| `calc.py` | Cost engine (landed cost, multi-shipment plan, TEU / container sizes) |
| `comparison_export.py`, `rfq_export.py` | Excel exports (offer comparison, RFQ response template) |
| `baf_rates.json` | Monthly fuel-surcharge table, updated by a scheduled task |

Order matters: a section can use variables defined in earlier sections. Keep the two-digit prefixes when adding files.

### Carbon footprint & dashboard
- `carbon.py` — route-based transport emissions (GLEC Framework / ISO 14083, WTW): estimated sea distance via Suez or the Cape, road distance from the site GPS, editable factors.
- `sections/89_dashboard.py` — Project Dashboard (first tab): KPIs, MWh by status, key dates, open alerts.
