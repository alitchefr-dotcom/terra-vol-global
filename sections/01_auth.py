# © Terra Vol. All rights reserved. Proprietary and confidential — see LICENSE.
# Terra Vol Global — section 01_auth: login gate. Runs before everything else is shown.
import time as _time
import auth as _auth_mod
importlib.reload(_auth_mod)


@st.cache_resource
def _auth_guard():
    return _auth_mod.Guard()


AUTH_GUARD = _auth_guard()
AUTH_USERS = _auth_mod.load_users(st.secrets)


def _hash_tool(where):
    with where.expander("🔑 Create password hash (for a new user)"):
        _pw = st.text_input("New password:", type="password", key="_hash_pw")
        if _pw:
            _probs = _auth_mod.password_problems(_pw)
            if _probs:
                st.warning("Use " + ", ".join(_probs) + ".")
            else:
                _h = _auth_mod.hash_password(_pw)
                st.caption("Copy into the app Secrets (replace the username and details):")
                st.code(f'[auth_users.username]\npassword_hash = "{_h}"\nname = "Full Name"\ncompany = "Company"\n'
                        f'role = "user"\nai = true\nai_daily_limit = 30', language="toml")


current_user = st.session_state.get("_auth_user")
if current_user and _time.time() - st.session_state.get("_auth_last", 0) > _auth_mod.IDLE_HOURS * 3600:
    st.session_state.pop("_auth_user", None)
    current_user = None
    st.session_state["_auth_msg"] = "Your session expired. Please log in again."

if not AUTH_USERS:
    # no users configured yet: the app stays open, but the AI import is disabled
    current_user = None
    st.sidebar.warning("🔓 Login is not set up — anyone with the link can open the app. "
                       "Add users in the app Secrets (see README).")
    _hash_tool(st.sidebar)
elif not current_user:
    _lc = st.columns([1, 2, 1])
    with _lc[1]:
        if os.path.exists("logo.png"):
            st.image("logo.png", width=160)
        st.markdown("## Terra Vol Global")
        st.caption("BESS project logistics, cost & compliance")
        if st.session_state.get("_auth_msg"):
            st.info(st.session_state.pop("_auth_msg"))
        _u = st.text_input("Username:", key="_login_user")
        _p = st.text_input("Password:", type="password", key="_login_pw")
        if st.button("Log in", type="primary", key="_login_btn"):
            _rec, _msg = _auth_mod.check_login(AUTH_USERS, AUTH_GUARD, _u, _p)
            if _rec:
                st.session_state["_auth_user"] = _rec
                st.session_state["_auth_last"] = _time.time()
                st.session_state.pop("_login_pw", None)
                st.rerun()
            else:
                st.error(_msg)
        st.caption("Access is by invitation. Contact Terra Vol for an account.")
        st.caption(f"© {date.today().year} Terra Vol. All rights reserved.")
    st.stop()
else:
    # refresh the user's rights from the secrets (a disabled or removed user is logged out)
    _live = AUTH_USERS.get(current_user["username"])
    if not _live or _live.get("disabled"):
        st.session_state.pop("_auth_user", None)
        st.session_state["_auth_msg"] = "Your access has been changed. Please log in again."
        st.rerun()
    current_user = dict(_live, username=current_user["username"])
    st.session_state["_auth_user"] = current_user
    st.session_state["_auth_last"] = _time.time()
    st.sidebar.markdown(f"👤 **{current_user['name']}**" + (f" — {current_user['company']}" if current_user['company'] else ""))
    if st.sidebar.button("Log out", key="_logout_btn"):
        for _k in ("_auth_user", "_auth_last"):
            st.session_state.pop(_k, None)
        st.rerun()
    if current_user["role"] == "admin":
        _hash_tool(st.sidebar)


def ai_allowance():
    """(allowed, message, remaining) for the AI offer import."""
    if not current_user:
        return False, "AI import is available to logged-in users only. Set up the login in the app Secrets.", 0
    if not current_user.get("ai"):
        return False, "AI import is not enabled for your account.", 0
    left = current_user["ai_daily_limit"] - AUTH_GUARD.ai_used_today(current_user["username"])
    if left <= 0:
        return False, f"Daily AI limit reached ({current_user['ai_daily_limit']} reads). It resets tomorrow.", 0
    return True, "", left
