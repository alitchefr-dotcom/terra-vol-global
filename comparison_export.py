# © Terra Vol. All rights reserved. Proprietary and confidential — see LICENSE.
"""Offer comparison report (Excel) for Terra Vol Global."""
import io
from datetime import date

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

NAVY = "1F3A5F"
GOOD = "E3F4E8"
BAD = "FBE5E5"
THIN = Side(style="thin", color="B7C4D4")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _page(ws):
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.page_margins.left = ws.page_margins.right = 0.3


def _title(ws, text, sub=None):
    ws.cell(row=1, column=1, value=text).font = Font(bold=True, size=16, color=NAVY)
    if sub:
        ws.cell(row=2, column=1, value=sub).font = Font(italic=True, color="5A6B7F")


def _table(ws, row, headers, rows, money_cols=(), fills=None, widths=None):
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=row, column=i, value=h)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=NAVY)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BOX
    ws.row_dimensions[row].height = 32
    for j, r in enumerate(rows, 1):
        for i, h in enumerate(headers, 1):
            v = r.get(h, "")
            c = ws.cell(row=row + j, column=i, value=v)
            c.border = BOX
            c.alignment = Alignment(vertical="top", wrap_text=True)
            if h in money_cols and isinstance(v, (int, float)):
                c.number_format = "#,##0"
            if fills and fills[j - 1]:
                c.fill = PatternFill("solid", fgColor=fills[j - 1])
    if widths:
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
    return row + len(rows) + 2


def build_comparison_xlsx(meta, comparison_rows, comparison_headers, money_cols, fills,
                          breakdown_rows, breakdown_headers, basis_lines):
    wb = Workbook()
    ws = wb.active
    ws.title = "Comparison"
    _page(ws)
    _title(ws, f"Offer Comparison — {meta['project']}",
           f"Prepared {date.today().strftime('%d/%m/%Y')} · amounts in {meta['currency']} · "
           f"{meta['units_text']}")
    _w = {"Rank": 6, "Transit": 8, "Free days": 8, "Days late": 8, "Risk flags": 40, "Compliance": 30,
          "Offered by": 16, "Carrier": 16, "Vessel": 18, "POD": 18, "Terms": 18}
    widths = [_w.get(h, 13) for h in comparison_headers]
    r = _table(ws, 4, comparison_headers, comparison_rows, money_cols, fills, widths)
    ws.cell(row=r, column=1, value="Green = recommended (cheapest eligible / fastest eligible / best including the cost of delay). Red = does not meet the "
                                   "project requirements.").font = Font(italic=True, color="5A6B7F")

    wb2 = wb.create_sheet("Charge breakdown")
    _page(wb2)
    _title(wb2, "Charges per unit as offered", "‘not stated’ = filled with the highest value stated in the other offers")
    _table(wb2, 4, breakdown_headers, breakdown_rows, widths=[30] + [20] * (len(breakdown_headers) - 1))

    wb3 = wb.create_sheet("Basis & method")
    _page(wb3)
    _title(wb3, "Basis of comparison")
    wb3.column_dimensions["A"].width = 120
    for i, line in enumerate(basis_lines, 3):
        c = wb3.cell(row=i, column=1, value=line)
        c.alignment = Alignment(wrap_text=True, vertical="top")

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
