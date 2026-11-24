# Terra-Vol-Global
End-to-end supply chain &amp; financial control software for BESS and solar energy developers, EPCs, and IPPs

**Proprietary software — © Terra Vol. All rights reserved.** No licence is granted to use, copy, modify or distribute this code. See [LICENSE](LICENSE).


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
- `supplier_compare.py` + `sections/35_supplier_comparison.py` — Supplier Comparison: delivered-to-site cost per kWh for competing BESS suppliers on the same project and route.
- `ai_import.py` — AI import of offers from PDF / e-mail / image / spreadsheet / text (Claude API, key in the `ANTHROPIC_API_KEY` secret); lines are reviewed before they are added.

- `interim.py` + `sections/36_site_readiness.py` — Site Readiness & Interim Storage: site-ready date, no-go months, site checklist; per shipment compares factory hold, port, interim yard (bonded or not) and site pad.
- Private yard rates (admin only) can be kept in the Secrets as `[rate_library.<name>]` with currency, haul_bess, haul_other, lift, day_bess, day_other, ins_permille, ins_cap, extra_permit.

## Users & login
Login is configured in the app **Secrets** (Streamlit Cloud › App settings › Secrets), never in the code:

```toml
ANTHROPIC_API_KEY = "sk-ant-..."      # optional, for the AI offer import

[auth_users.alitche]                  # username (lower-case)
password_hash = "pbkdf2_sha256$..."   # from the "Create password hash" tool in the sidebar
name = "Alitche"
company = "Terra Vol"
role = "admin"                        # admin | user (admins see the hash tool)
ai = true                             # may use the AI offer import
ai_daily_limit = 50                   # AI reads per day
default_country = "Israel"            # optional: country shown at login
default_currency = "USD"              # optional: EUR or USD
# disabled = true                     # blocks the user at the next click
```
- Without any `[auth_users.*]` the app stays open and the AI import is disabled.
- 5 wrong passwords lock the username for 15 minutes; sessions end after 8 idle hours or on browser refresh.
- Passwords: at least 10 characters, upper- and lower-case letters and a digit; stored only as salted PBKDF2 hashes.
