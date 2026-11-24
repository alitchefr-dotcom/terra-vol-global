"""RFQ response template (Excel) — forwarders fill one row per vessel / sailing; the file is imported back."""
import io

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

NAVY = "1F3A5F"

# column -> (guidance shown in row 2, list of allowed values or None, width)
RESPONSE_COLUMNS = {
    "Offered By": ("Your company", None, 18),
    "Quote Ref": ("Your quote reference", None, 14),
    "Carrier": ("Shipping line / owner", None, 16),
    "Vessel": ("Vessel name", None, 18),
    "Vessel Type": ("Container vessel / MPP vessel / Charter (dedicated)",
                    ["Container vessel", "MPP vessel", "Charter (dedicated)"], 18),
    "POL": ("Port of loading", None, 12),
    "POD": ("Port of discharge", None, 22),
    "ETD": ("dd/mm/yyyy", None, 12),
    "ETA": ("dd/mm/yyyy", None, 12),
    "Direct": ("Yes = no transshipment", ["Yes", "No"], 9),
    "Transshipment Port": ("If not direct", None, 14),
    "Routing": ("Cape of Good Hope / Suez Canal / Red Sea / Other",
                ["Cape of Good Hope", "Suez Canal / Red Sea", "Other"], 18),
    "Capacity (units)": ("Units you can load on this sailing", None, 10),
    "Max Gross / Box (t)": ("Heaviest box accepted (t)", None, 10),
    "Currency": ("USD / EUR", ["USD", "EUR"], 8),
    "Price Basis": ("Per unit / Lump sum", ["Per unit", "Lump sum"], 10),
    "Freight / 20ft": ("Per unit", None, 11),
    "Freight / 40ft": ("Per unit", None, 11),
    "Lump Sum": ("Total, if lump sum", None, 12),
    "Lump Sum Units": ("Units covered by the lump sum", None, 10),
    "Terms": ("Liner terms / FIO / FILO / LIFO / FIOS", ["Liner terms", "FIO", "FILO", "LIFO", "FIOS"], 10),
    "Loading Cost / Unit": ("If not in the terms", None, 10),
    "Discharge Cost / Unit": ("If not in the terms", None, 10),
    "BAF / TEU (if not incl.)": ("0 if included", None, 10),
    "DG Surcharge / Unit": ("0 if included", None, 10),
    "Heavy-Lift / Unit": ("0 if included", None, 10),
    "DG Yard Origin / Unit": ("0 if included", None, 10),
    "Lashing / Unit": ("0 if included", None, 10),
    "War Risk & Other / Unit": ("0 if none", None, 10),
    "Origin Local / Unit": ("0 if included", None, 10),
    "Dest. Local / Unit": ("0 if included", None, 10),
    "DG Acceptance": ("Confirmed / Pending / Refused", ["Confirmed", "Pending", "Refused"], 11),
    "Stowage": ("Under deck / On deck / Mixed / TBC", ["Under deck", "On deck", "Mixed", "TBC"], 11),
    "Hot Work / D-rings": ("Included / By shipper / Not required / TBC",
                           ["Included", "By shipper", "Not required", "TBC"], 12),
    "Load Terminal": ("Terminal at POL", None, 14),
    "Discharge Terminal": ("Terminal at POD", None, 14),
    "Free Days": ("Free time at POD (days)", None, 8),
    "Valid Until": ("dd/mm/yyyy", None, 12),
    "Notes": ("Anything else", None, 24),
}


def build_response_template(project, rfq_ref, pods, instructions):
    wb = Workbook()
    ws = wb.active
    ws.title = "Offer"
    cols = list(RESPONSE_COLUMNS)
    for i, col in enumerate(cols, 1):
        guidance, allowed, width = RESPONSE_COLUMNS[col]
        h = ws.cell(row=1, column=i, value=col)
        h.font = Font(bold=True, color="FFFFFF")
        h.fill = PatternFill("solid", fgColor=NAVY)
        h.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        g = ws.cell(row=2, column=i, value=guidance)
        g.font = Font(italic=True, color="5A6B7F", size=9)
        g.alignment = Alignment(wrap_text=True, vertical="top")
        g.fill = PatternFill("solid", fgColor="EEF2F7")
        ws.column_dimensions[get_column_letter(i)].width = width
        options = allowed or (pods if col == "POD" and pods else None)
        if options:
            dv = DataValidation(type="list", formula1='"' + ",".join(o.replace(",", " -") for o in options) + '"',
                                allow_blank=True)
            ws.add_data_validation(dv)
            dv.add(f"{get_column_letter(i)}3:{get_column_letter(i)}200")
    ws.row_dimensions[1].height = 42
    ws.row_dimensions[2].height = 42
    ws.freeze_panes = "C3"

    info = wb.create_sheet("Instructions")
    info.column_dimensions["A"].width = 110
    info.cell(row=1, column=1, value=f"Offer response — {project} — RFQ {rfq_ref}").font = Font(bold=True, size=14, color=NAVY)
    for i, line in enumerate(instructions, 3):
        c = info.cell(row=i, column=1, value=line)
        c.alignment = Alignment(wrap_text=True, vertical="top")
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def read_response(file_bytes):
    """Read a filled response template → DataFrame with the Offers Received columns (guidance row skipped)."""
    df = pd.read_excel(io.BytesIO(file_bytes), sheet_name="Offer", header=0, skiprows=[1])
    df = df.dropna(how="all")
    df = df[[c for c in df.columns if c in RESPONSE_COLUMNS]]
    for c in ("ETD", "ETA", "Valid Until"):
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True).dt.date
    if "Direct" in df.columns:
        df["Direct"] = df["Direct"].astype(str).str.strip().str.lower().isin(["yes", "y", "true", "1"])
    if "POD" in df.columns:
        df["POD"] = df["POD"].astype(str).str.replace(" - ", ", ", regex=False)
    return df.drop(columns=[c for c in ("Notes",) if c in df.columns])
