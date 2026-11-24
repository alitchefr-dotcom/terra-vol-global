# © Terra Vol. All rights reserved. Proprietary and confidential — see LICENSE.
# Terra Vol Global — section 88_guide: step-by-step guide shown above the tabs in the "Guided" view.
# Runs after the tabs so it can read their results; it writes into the container created before the tabs.

if _guide_box is not None:
    _demo = not st.session_state.get("_empty_project")
    _real_offers = [r for r in sail_results if not str(r["Carrier"] or "").startswith("Sample")]
    _steps = [
        ("1. Project & equipment", "📝 Project Brief & BOM",
         "Name the project, set the dates and enter the equipment list (BOM).",
         bool(bom_rows) and project_name.strip() not in ("", "New BESS Project")),
        ("2. Offers received", "⛴️ Offers Received",
         "Add the forwarders' offers — type them, import the Excel template or read PDFs / e-mails with AI.",
         bool(_real_offers)),
        ("3. Compare", "⚖️ Offer Comparison",
         "See the offers like-for-like, with the charges they leave out and the cost of delay.",
         bool(_real_offers) and any(r["eligible"] for r in _real_offers)),
        ("4. Shipment plan", "⛴️ Offers Received → 🧩 Multi-Shipment Planner",
         "Split the equipment between the vessels you choose and send the plan to the planner.",
         bool(plan["coverage_ok"] and any(r["units"] for r in plan["shipments"])) and not _demo),
        ("5. Dashboard", "🏠 Dashboard", "Costs, dates, emissions and open alerts in one page.", False),
    ]
    _done = sum(1 for s in _steps[:4] if s[3])
    _steps[4] = _steps[4][:3] + (_done == 4,)
    with _guide_box:
        if _demo:
            st.info("👋 You are looking at a **demo project**. Explore freely, then press **🆕 Start an empty project** "
                    "in the sidebar to enter your own. Choose another **View** in the sidebar to see the tabs for "
                    "your role (Finance, Logistics, Country project manager, ESG, Procurement).")
        st.progress(_done / 4.0, text=f"Your project: {_done} of 4 steps done")
        _cols = st.columns(5)
        for _c, (title, tab, hint, ok) in zip(_cols, _steps):
            with _c:
                st.markdown(f"{'✅' if ok else '⬜'} **{title}**  \n<span style='font-size:0.8em'>{tab}</span>",
                            unsafe_allow_html=True)
        _next = next((s for s in _steps if not s[3]), None)
        if _next:
            st.caption(f"**Next:** {_next[2]} → tab **{_next[1]}**")
