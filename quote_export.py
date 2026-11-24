"""Client quote export (Excel) for Terra Vol Global.

Builds a formatted workbook with a summary sheet and one sheet per sailing option.
Only SELL prices (cost + markup) are written — internal costs never leave the app.
"""
import io
from datetime import date

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

NAVY = "1F3A5F"
LIGHT = "EAF0F7"
THIN = Side(style="thin", color="B7C4D4")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

CHARGE_ITEMS = [
    ("freight", "Ocean freight"),
    ("baf", "BAF / bunker surcharge"),
    ("dg", "Dangerous goods surcharge (Class 9)"),
    ("heavy", "Heavy-lift / overweight surcharge"),
    ("dg_yard", "DG yard storage at port of loading"),
    ("lashing", "Lashing & securing"),
    ("origin", "Local charges at origin"),
    ("dest", "Local charges at destination"),
]


def _fmt_date(d):
    return d.strftime("%d/%m/%Y") if isinstance(d, date) else ""


def _title(ws, text, row=1):
    ws.cell(row=row, column=1, value=text).font = Font(bold=True, size=16, color=NAVY)


def _kv(ws, row, key, value, bold_value=False, span=5):
    ws.cell(row=row, column=1, value=key).font = Font(bold=True, color=NAVY)
    c = ws.cell(row=row, column=2, value=value)
    c.alignment = Alignment(wrap_text=True, vertical="top")
    if bold_value:
        c.font = Font(bold=True)
    ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=1 + span)
    return row + 1


def _page(ws):
    """Landscape, fit all columns on one page width."""
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.print_options.horizontalCentered = True
    ws.page_margins.left = ws.page_margins.right = 0.4


def _header(ws, row, headers):
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=row, column=i, value=h)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=NAVY)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BOX
    return row + 1


def _widths(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def build_quote_xlsx(meta, options, logo_path=None):
    """
    meta: dict with project, client, quote_ref, quote_date, valid_until, currency, incoterm_basis,
          cargo_lines [ {item, model, qty, container, weight_t, dg} ], special_handling, insurance_excluded,
          notes [str], requirements {direct_only, no_red_sea}
    options: list of dicts with option, carrier, vessel, vessel_type, pol, pod, etd, eta, transit_days, routing,
             direct, transshipment, free_days, valid_until,
             units [ {type, qty, charges: {key: sell_amount_per_unit}} ]   (qty may be None = rates only)
    """
    cur = meta["currency"]
    money = f'#,##0 "{cur}"'
    wb = Workbook()

    # ------------------------------------------------------------------ Summary
    ws = wb.active
    ws.title = "Summary"
    _page(ws)
    _widths(ws, [34, 22, 26, 13, 13, 17, 19, 16, 11, 20])
    if logo_path:
        try:
            from openpyxl.drawing.image import Image as XLImage
            img = XLImage(logo_path)
            img.height, img.width = 60, 60
            ws.add_image(img, "I1")
        except Exception:
            pass
    _title(ws, "Ocean Freight Quotation — BESS Project Logistics")
    r = 3
    r = _kv(ws, r, "Project", meta["project"], True)
    if meta.get("client"):
        r = _kv(ws, r, "Client", meta["client"])
    r = _kv(ws, r, "Quote reference", meta["quote_ref"])
    r = _kv(ws, r, "Quote date", _fmt_date(meta["quote_date"]))
    r = _kv(ws, r, "Valid until", _fmt_date(meta["valid_until"]), True)
    r = _kv(ws, r, "Currency", cur)
    r = _kv(ws, r, "Basis", meta["incoterm_basis"])
    r += 1

    ws.cell(row=r, column=1, value="Cargo").font = Font(bold=True, size=12, color=NAVY)
    r += 1
    r = _header(ws, r, ["Item", "Model", "Qty", "Container", "Gross weight / unit (t)", "Classification"])
    for c in meta["cargo_lines"]:
        for i, v in enumerate([c["item"], c["model"], c["qty"], c["container"], c["weight_t"], c["dg"] or "—"], 1):
            cell = ws.cell(row=r, column=i, value=v)
            cell.border = BOX
        r += 1
    r += 1

    ws.cell(row=r, column=1, value="Options overview").font = Font(bold=True, size=12, color=NAVY)
    r += 1
    r = _header(ws, r, ["Option / vessel", "Carrier", "Port of discharge", "ETD", "ETA", "Transit (days)",
                        "Routing", "Direct", "Free days", "Total for allocated units"])
    grand = 0.0
    for o in options:
        total = sum((u["qty"] or 0) * sum(u["charges"].values()) for u in o["units"])
        grand += total
        vals = [f'{o["option"]} — {o["vessel"]}', o["carrier"], o["pod"], _fmt_date(o["etd"]), _fmt_date(o["eta"]),
                o["transit_days"], o["routing"], "Yes" if o["direct"] else f'No ({o["transshipment"] or "transshipment"})',
                o["free_days"], total if total else "Rates per unit"]
        for i, v in enumerate(vals, 1):
            cell = ws.cell(row=r, column=i, value=v)
            cell.border = BOX
            if i == 10 and isinstance(v, (int, float)):
                cell.number_format = money
        r += 1
    if grand:
        ws.cell(row=r, column=9, value="Total").font = Font(bold=True)
        c = ws.cell(row=r, column=10, value=grand)
        c.font = Font(bold=True)
        c.number_format = money
        r += 1
    r += 1

    ws.cell(row=r, column=1, value="Confirmations & terms").font = Font(bold=True, size=12, color=NAVY)
    r += 1
    for line in meta["notes"]:
        c = ws.cell(row=r, column=1, value="• " + line)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=10)
        ws.row_dimensions[r].height = 15 * (1 + len(line) // 150)
        r += 1

    # ------------------------------------------------------------ One sheet per option
    for o in options:
        name = f'{o["option"]} {o["pod"].split(",")[0]}'[:31]
        for ch in "[]:*?/\\":
            name = name.replace(ch, " ")
        s = wb.create_sheet(name)
        _page(s)
        _widths(s, [40, 18, 18, 18, 18, 18])
        _title(s, f'Option {o["option"]} — {o["vessel"]}')
        r = 3
        r = _kv(s, r, "Carrier", o["carrier"])
        r = _kv(s, r, "Vessel / type", f'{o["vessel"]} ({o["vessel_type"]})')
        r = _kv(s, r, "Port of loading", o["pol"])
        r = _kv(s, r, "Port of discharge", o["pod"], True)
        r = _kv(s, r, "ETD / ETA", f'{_fmt_date(o["etd"])}  →  {_fmt_date(o["eta"])}  ({o["transit_days"]} days)')
        r = _kv(s, r, "Routing", o["routing"])
        r = _kv(s, r, "Direct sailing", "Yes — no transshipment" if o["direct"]
                else f'No — transshipment at {o["transshipment"] or "intermediate port"}')
        r = _kv(s, r, "Free time at destination", f'{o["free_days"]} days')
        r = _kv(s, r, "Rates valid until", _fmt_date(o["valid_until"]))
        r += 1

        types = [u["type"] for u in o["units"]]
        r = _header(s, r, ["Charge (per unit)"] + types)
        for key, label in CHARGE_ITEMS:
            if not any(u["charges"].get(key) for u in o["units"]):
                continue
            s.cell(row=r, column=1, value=label).border = BOX
            for i, u in enumerate(o["units"], 2):
                c = s.cell(row=r, column=i, value=u["charges"].get(key, 0) or 0)
                c.number_format = money
                c.border = BOX
            r += 1
        s.cell(row=r, column=1, value="Total per unit").font = Font(bold=True)
        for i, u in enumerate(o["units"], 2):
            c = s.cell(row=r, column=i, value=sum(u["charges"].values()))
            c.font = Font(bold=True)
            c.number_format = money
            c.fill = PatternFill("solid", fgColor=LIGHT)
        r += 1
        if any(u["qty"] for u in o["units"]):
            s.cell(row=r, column=1, value="Allocated units")
            for i, u in enumerate(o["units"], 2):
                s.cell(row=r, column=i, value=u["qty"] or 0)
            r += 1
            s.cell(row=r, column=1, value="Total").font = Font(bold=True)
            tot = 0.0
            for i, u in enumerate(o["units"], 2):
                v = (u["qty"] or 0) * sum(u["charges"].values())
                tot += v
                c = s.cell(row=r, column=i, value=v)
                c.number_format = money
                c.font = Font(bold=True)
            r += 1
            s.cell(row=r, column=1, value="Option total").font = Font(bold=True, color=NAVY)
            c = s.cell(row=r, column=2, value=tot)
            c.number_format = money
            c.font = Font(bold=True, color=NAVY)
            r += 1
        r += 1
        if meta.get("special_handling"):
            hc = s.cell(row=r, column=1, value="Handling")
            hc.font = Font(bold=True, color=NAVY)
            hc.alignment = Alignment(vertical="top")
            c = s.cell(row=r, column=2, value=meta["special_handling"])
            c.alignment = Alignment(wrap_text=True, vertical="top")
            s.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
            s.row_dimensions[r].height = 45

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
