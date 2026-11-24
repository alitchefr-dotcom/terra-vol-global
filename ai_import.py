# © Terra Vol. All rights reserved. Proprietary and confidential — see LICENSE.
"""AI import of forwarder / carrier offers from PDF, e-mail, image, spreadsheet or pasted text (Claude API).

The model is forced to answer through one tool (`record_offers`) whose schema mirrors the Offers Received table,
so the result is structured and every list field is limited to the values the app accepts. Nothing is added to the
project automatically: the app shows the extracted lines for review first.
"""
import base64
import email
import io
import json
from datetime import date
from email import policy

import pandas as pd
import requests

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-5-5"
PRICE_IN, PRICE_OUT = 2.0, 10.0          # USD per million tokens (Claude Sonnet 5.5 list price)
MAX_FILE_MB = 20

# json key -> (app column, schema)
_NUM = {"type": ["number", "null"]}
_STR = {"type": ["string", "null"]}
FIELDS = {
    "offered_by": ("Offered By", _STR), "quote_ref": ("Quote Ref", _STR), "carrier": ("Carrier", _STR),
    "vessel": ("Vessel", _STR),
    "vessel_type": ("Vessel Type", {"enum": ["Container vessel", "MPP vessel", "Charter (dedicated)"]}),
    "pol": ("POL", _STR), "pod": ("POD", None), "etd": ("ETD", _STR), "eta": ("ETA", _STR),
    "direct": ("Direct", {"type": ["boolean", "null"]}), "transshipment_port": ("Transshipment Port", _STR),
    "routing": ("Routing", {"enum": ["Cape of Good Hope", "Suez Canal / Red Sea", "Other"]}),
    "capacity_units": ("Capacity (units)", _NUM), "max_gross_per_box_t": ("Max Gross / Box (t)", _NUM),
    "currency": ("Currency", {"enum": ["USD", "EUR"]}),
    "freight_20ft": ("Freight / 20ft", _NUM), "freight_40ft": ("Freight / 40ft", _NUM),
    "baf_per_teu": ("BAF / TEU (if not incl.)", _NUM), "dg_surcharge_per_unit": ("DG Surcharge / Unit", _NUM),
    "heavy_lift_per_unit": ("Heavy-Lift / Unit", _NUM), "dg_yard_origin_per_unit": ("DG Yard Origin / Unit", _NUM),
    "lashing_per_unit": ("Lashing / Unit", _NUM), "origin_local_per_unit": ("Origin Local / Unit", _NUM),
    "dest_local_per_unit": ("Dest. Local / Unit", _NUM),
    "price_basis": ("Price Basis", {"enum": ["Per unit", "Lump sum"]}), "lump_sum": ("Lump Sum", _NUM),
    "lump_sum_units": ("Lump Sum Units", _NUM),
    "terms": ("Terms", {"enum": ["Liner terms", "FIO", "FILO", "LIFO", "FIOS"]}),
    "loading_cost_per_unit": ("Loading Cost / Unit", _NUM), "discharge_cost_per_unit": ("Discharge Cost / Unit", _NUM),
    "war_risk_other_per_unit": ("War Risk & Other / Unit", _NUM),
    "dg_acceptance": ("DG Acceptance", {"enum": ["Confirmed", "Pending", "Refused", "Not stated"]}),
    "stowage": ("Stowage", {"enum": ["Under deck", "On deck", "Mixed", "TBC"]}),
    "hot_work_d_rings": ("Hot Work / D-rings", {"enum": ["Included", "By shipper", "Not required", "TBC"]}),
    "load_terminal": ("Load Terminal", _STR), "discharge_terminal": ("Discharge Terminal", _STR),
    "free_days": ("Free Days", _NUM), "valid_until": ("Valid Until", _STR),
    "review_notes": ("AI Notes", _STR),
}
DATE_COLS = ("ETD", "ETA", "Valid Until")

SYSTEM = """You extract ocean-freight offers for BESS / energy-equipment projects from forwarder and carrier quotations
(PDF, e-mail, spreadsheet, screenshot). Record every offered option with the record_offers tool: one line per
vessel / sailing / option. If one quote offers several sailings, routings or vessel types, make one line for each.

Charges rule (very important): put a NUMBER when the charge is quoted separately, 0 when the quote says it is
included in the freight, and null when the quote does not mention it or says it is excluded / at cost / subject to.
Charges are per unit (one container or one piece). Freight per 20ft / 40ft is per container. If the offer is one
total amount for the whole parcel or charter, use price_basis "Lump sum" with lump_sum and lump_sum_units.
Never invent values. Dates as YYYY-MM-DD; if only a week or month is given, use the first day and say so in
review_notes. Convert nothing: keep the quoted amounts; currency must be USD or EUR — if another currency is used,
keep the amounts and say so in review_notes. Use review_notes (English, short) for anything the buyer must check:
assumptions, conditions, "subject to" clauses, missing information, validity conditions, DG approval status."""


def _tool(pod_options):
    props = {}
    for k, (_, schema) in FIELDS.items():
        props[k] = {"enum": list(pod_options) + ["Other / not listed"]} if k == "pod" else dict(schema)
    props["pod_as_written"] = {"type": ["string", "null"]}
    return {
        "name": "record_offers",
        "description": "Record all freight offers found in the documents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "offers": {"type": "array", "items": {"type": "object", "properties": props,
                                                      "required": ["carrier", "vessel_type", "pod", "currency"]}},
                "document_summary": {"type": "string"},
            },
            "required": ["offers"],
        },
    }


def file_to_blocks(name, data):
    """Turn one uploaded file into Claude content blocks. Returns (blocks, warnings)."""
    n = name.lower()
    if len(data) > MAX_FILE_MB * 1024 * 1024:
        return [], [f"{name}: larger than {MAX_FILE_MB} MB, skipped."]
    b64 = lambda d: base64.standard_b64encode(d).decode()
    if n.endswith(".pdf"):
        return [{"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": b64(data)},
                 "title": name}], []
    for ext, mt in ((".png", "image/png"), (".jpg", "image/jpeg"), (".jpeg", "image/jpeg"), (".webp", "image/webp"),
                    (".gif", "image/gif")):
        if n.endswith(ext):
            return [{"type": "text", "text": f"Image: {name}"},
                    {"type": "image", "source": {"type": "base64", "media_type": mt, "data": b64(data)}}], []
    if n.endswith((".xlsx", ".xls", ".csv")):
        try:
            if n.endswith(".csv"):
                sheets = {"csv": pd.read_csv(io.BytesIO(data), header=None)}
            else:
                sheets = pd.read_excel(io.BytesIO(data), sheet_name=None, header=None)
            txt = "\n\n".join(f"Sheet: {s}\n{df.dropna(how='all').to_csv(index=False, header=False)}"
                              for s, df in sheets.items())
            return [{"type": "text", "text": f"Spreadsheet {name}:\n{txt[:150000]}"}], []
        except Exception as e:
            return [], [f"{name}: could not read the spreadsheet ({e})."]
    if n.endswith(".eml"):
        msg = email.message_from_bytes(data, policy=policy.default)
        head = f"E-mail {name}\nFrom: {msg.get('From')}\nDate: {msg.get('Date')}\nSubject: {msg.get('Subject')}\n"
        body = msg.get_body(preferencelist=("plain", "html"))
        blocks = [{"type": "text", "text": head + "\n" + (body.get_content() if body else "")[:100000]}]
        warns = []
        for part in msg.iter_attachments():
            fn = part.get_filename() or "attachment"
            sub, w = file_to_blocks(fn, part.get_payload(decode=True) or b"")
            blocks += sub
            warns += [x for x in w if "not supported" not in x]
        return blocks, warns
    if n.endswith((".txt", ".html", ".htm")):
        return [{"type": "text", "text": f"{name}:\n{data.decode('utf-8', errors='replace')[:150000]}"}], []
    if n.endswith(".msg"):
        return [], [f"{name}: Outlook .msg is not supported — in Outlook use File › Save As › .eml or print to PDF."]
    return [], [f"{name}: file type not supported."]


def _to_row(o, pod_options):
    row = {}
    for k, (col, _) in FIELDS.items():
        v = o.get(k)
        if col in DATE_COLS:
            try:
                v = date.fromisoformat(str(v)[:10]) if v else None
            except ValueError:
                v = None
        row[col] = v
    if row.get("POD") not in pod_options:
        written = o.get("pod_as_written") or ""
        row["POD"] = pod_options[0] if pod_options else None
        row["AI Notes"] = (f"POD '{written}' is not in the port list — check. " + (row.get("AI Notes") or "")).strip()
    return row


def extract_offers(api_key, blocks, pod_options, context="", model=MODEL, timeout=180):
    """Call Claude and return (rows, summary, usage dict). Raises RuntimeError with a readable message."""
    if not blocks:
        raise RuntimeError("Nothing to read.")
    content = list(blocks) + [{"type": "text", "text":
                               "Project context (for reference only, do not copy into offers):\n" + context +
                               "\n\nExtract every offer with the record_offers tool."}]
    payload = {"model": model, "max_tokens": 16000, "system": SYSTEM,
               "tools": [_tool(pod_options)], "tool_choice": {"type": "tool", "name": "record_offers"},
               "messages": [{"role": "user", "content": content}]}
    try:
        r = requests.post(API_URL, json=payload, timeout=timeout,
                          headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                                   "content-type": "application/json"})
    except requests.RequestException as e:
        raise RuntimeError(f"Could not reach the AI service: {e}")
    if r.status_code != 200:
        try:
            msg = r.json().get("error", {}).get("message", r.text)
        except ValueError:
            msg = r.text
        raise RuntimeError(f"AI service error {r.status_code}: {msg[:300]}")
    res = r.json()
    tool = next((c for c in res.get("content", []) if c.get("type") == "tool_use"), None)
    if not tool:
        raise RuntimeError("The AI did not return any offers.")
    data = tool.get("input") or {}
    if isinstance(data, str):
        data = json.loads(data)
    rows = [_to_row(o, pod_options) for o in data.get("offers", [])]
    u = res.get("usage", {})
    tin = u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
    tout = u.get("output_tokens", 0)
    usage = {"input_tokens": tin, "output_tokens": tout,
             "cost_usd": tin / 1e6 * PRICE_IN + tout / 1e6 * PRICE_OUT, "stop_reason": res.get("stop_reason")}
    return rows, data.get("document_summary", ""), usage
