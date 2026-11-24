# © Terra Vol. All rights reserved. Proprietary and confidential — see LICENSE.
# Terra Vol Global — section 90_project_file: Project restore function and the project file content.
# Runs in the shared namespace of app.py, in file-name order (see app.py).
def _apply_project_data(_data):
    """Restore a saved project (file or scenario snapshot) into the session; caller reruns."""
    st.session_state["_loaded_project_values"] = _data["values"]
    if _data.get("usd_eur"):
        st.session_state["usd_eur"] = float(_data["usd_eur"])
    if _data.get("shipments") is not None:
        st.session_state["msp_shipments"] = _records_df(_data["shipments"], date_cols=("ETD", "ETA"))
        st.session_state["msp_lines"] = _records_df(_data.get("shipment_lines", []))
        for _k in ("msp_shipments_editor", "msp_lines_editor"):
            st.session_state.pop(_k, None)
    if _data.get("permit_template") and _data.get("document_library") is not None:
        _tk = _data["permit_template"]
        st.session_state[f"doclib_{_tk}"] = _records_df(_data["document_library"], date_cols=("Valid Until",))
        st.session_state.pop(f"doclib_{_tk}_editor", None)
        if _data.get("permit_requests") is not None:
            st.session_state[f"permit_req_{_tk}"] = _records_df(_data["permit_requests"], date_cols=("ETA",))
            st.session_state.pop(f"permit_req_{_tk}_editor", None)
    if _data.get("port_rules") is not None:
        st.session_state["port_rules_df"] = _records_df(_data["port_rules"])
        st.session_state.pop("port_rules_editor", None)
    if _data.get("allocation_plan") is not None:
        st.session_state["plan_df"] = _records_df(_data["allocation_plan"])
        st.session_state.pop("plan_editor", None)
    if _data.get("sailings") is not None:
        st.session_state["sail_df"] = _records_df(_data["sailings"], date_cols=("ETD", "ETA", "Valid Until"))
        st.session_state.pop("sail_editor", None)
    if _data.get("bom") is not None:
        st.session_state["bom_df"] = _records_df(_data["bom"])
        st.session_state.pop("bom_editor", None)
    if _data.get("regulatory_checklist"):
        st.session_state["_reg_status"] = _data["regulatory_checklist"]
        for _k in [k for k in st.session_state.keys() if str(k).startswith("reg_checklist_")]:
            st.session_state.pop(_k, None)
    if _data.get("scenarios") is not None:
        st.session_state["_scenarios"] = _data["scenarios"]
    if "budget_baseline" in _data:
        st.session_state["_budget_baseline"] = _data["budget_baseline"]
    if _data.get("actuals") is not None:
        _a = _records_df(_data["actuals"], date_cols=("Date",))
        if len(_a) == 0:
            _a = pd.DataFrame(columns=["Date", "Shipment", "Category", "Supplier", "Invoice No.", "Currency", "Amount",
                                       "Paid", "Final", "Notes"])
        st.session_state["actuals_df"] = _a
        st.session_state.pop("actuals_editor", None)
    if _data.get("site_checklist") is not None:
        _sc = _records_df(_data["site_checklist"], date_cols=("Due",))
        if len(_sc):
            st.session_state["site_check_df"] = _sc
            st.session_state.pop("site_check_editor", None)
    if _data.get("suppliers") is not None:
        _s = _records_df(_data["suppliers"], date_cols=("EXW Ready",))
        if len(_s):
            st.session_state["sup_df"] = _s
            st.session_state.pop("sup_editor", None)


st.sidebar.markdown("---")
st.sidebar.markdown("### 💾 Save / Load Project")
_project_file = {
    "app": "Terra Vol Global",
    "file_version": 1,
    "saved_at": date.today().isoformat(),
    "project_name": project_name,
    "usd_eur": st.session_state.get("usd_eur"),
    "values": _SAVED,
    "shipments": _df_records(edited_shipments),
    "shipment_lines": _df_records(edited_lines),
    "regulatory_checklist": reg_status_now,
    "bom": _df_records(bom_edit),
    "sailings": _df_records(sail_edit),
    "port_rules": _df_records(port_rules_edit),
    "allocation_plan": _df_records(plan_edit),
    "permit_template": tmpl_key,
    "document_library": _df_records(lib_edit),
    "permit_requests": _df_records(req_edit),
    "budget_baseline": st.session_state.get("_budget_baseline"),
    "actuals": _df_records(act_edit),
    "suppliers": _df_records(sup_edit),
    "site_checklist": _df_records(site_check),
}
