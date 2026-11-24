# Terra Vol Global — section 99_save_load_footer: Sidebar save / load buttons and page footer.
# Runs in the shared namespace of app.py, in file-name order (see app.py).
_slug = _re.sub(r"[^A-Za-z0-9]+", "_", project_name).strip("_") or "project"
st.sidebar.download_button(
    "⬇️ Save project file",
    data=json.dumps(_project_file, ensure_ascii=False, indent=1, default=str),
    file_name=f"{_slug}.terravol.json",
    mime="application/json",
    help="Downloads all inputs, shipments and permits of this project. Load it later or send it to a partner.",
)
_upload = st.sidebar.file_uploader("⬆️ Load project file", type=["json"], key="project_upload")
if _upload is not None:
    _upload_id = f"{_upload.name}-{_upload.size}"
    if st.session_state.get("_loaded_upload_id") != _upload_id:
        try:
            _data = json.loads(_upload.getvalue().decode("utf-8"))
            if _data.get("app") != "Terra Vol Global" or "values" not in _data:
                raise ValueError("not a Terra Vol project file")
            _apply_project_data(_data)
            st.session_state["_loaded_upload_id"] = _upload_id
            st.session_state["_loaded_project_name"] = _data.get("project_name", "")
            st.rerun()
        except Exception as _e:
            st.sidebar.error(f"Could not load this file: {_e}")
if st.session_state.get("_loaded_project_name"):
    st.sidebar.success(f"Loaded: {st.session_state['_loaded_project_name']}")

st.markdown("---")
st.caption(f"© {date.today().year} Terra Vol. Advanced Renewable Energy & Infrastructure Venture.")
