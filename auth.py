# © Terra Vol. All rights reserved. Proprietary and confidential — see LICENSE.
"""Username / password login for Terra Vol Global.

Users are kept in the app secrets (never in the code):

    [auth_users.alitche]
    password_hash = "pbkdf2_sha256$310000$...$..."   # made with the "Create password hash" tool in the app
    name = "Alitche"
    company = "Terra Vol"
    role = "admin"          # admin | user
    ai = true               # may use the AI offer import
    ai_daily_limit = 50     # AI reads per day

Passwords are stored only as salted PBKDF2-SHA256 hashes. Failed logins are counted per username for the whole
server: after MAX_FAILS failures the username is locked for LOCK_MINUTES.
"""
import base64
import hashlib
import hmac
import os
import threading
import time
from datetime import date

ITERATIONS = 310_000
MAX_FAILS = 5
LOCK_MINUTES = 15
IDLE_HOURS = 8
MIN_PASSWORD_LEN = 10


def hash_password(password, iterations=ITERATIONS):
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(iterations, base64.b64encode(salt).decode(), base64.b64encode(dk).decode())


def verify_password(password, stored):
    try:
        algo, it, salt_b64, hash_b64 = str(stored).split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), base64.b64decode(salt_b64), int(it))
        return hmac.compare_digest(dk, base64.b64decode(hash_b64))
    except (ValueError, TypeError):
        return False


def password_problems(password):
    p = []
    if len(password) < MIN_PASSWORD_LEN:
        p.append(f"at least {MIN_PASSWORD_LEN} characters")
    if password.lower() == password or password.upper() == password:
        p.append("upper- and lower-case letters")
    if not any(c.isdigit() for c in password):
        p.append("a digit")
    return p


class Guard:
    """Server-wide failed-login and AI-usage counters (shared by all sessions of one app process)."""

    def __init__(self):
        self._lock = threading.Lock()
        self.fails = {}       # username -> [count, first_fail_ts, locked_until_ts]
        self.ai_use = {}      # (username, iso date) -> count

    def locked_for(self, user):
        with self._lock:
            f = self.fails.get(user)
            if f and f[2] > time.time():
                return int((f[2] - time.time()) // 60) + 1
            return 0

    def register_fail(self, user):
        with self._lock:
            now = time.time()
            f = self.fails.get(user)
            if not f or now - f[1] > LOCK_MINUTES * 60:
                f = [0, now, 0.0]
            f[0] += 1
            if f[0] >= MAX_FAILS:
                f[2] = now + LOCK_MINUTES * 60
                f[0], f[1] = 0, now
            self.fails[user] = f

    def register_ok(self, user):
        with self._lock:
            self.fails.pop(user, None)

    def ai_used_today(self, user):
        with self._lock:
            return self.ai_use.get((user, date.today().isoformat()), 0)

    def ai_add(self, user):
        with self._lock:
            k = (user, date.today().isoformat())
            self.ai_use[k] = self.ai_use.get(k, 0) + 1
            return self.ai_use[k]


def load_users(secrets):
    """Return {username: dict} from st.secrets['auth_users'] (empty if not configured)."""
    try:
        raw = secrets.get("auth_users") or {}
    except Exception:
        return {}
    users = {}
    for uname, cfg in dict(raw).items():
        cfg = dict(cfg)
        if not cfg.get("password_hash"):
            continue
        users[str(uname).strip().lower()] = {
            "name": cfg.get("name") or uname, "company": cfg.get("company") or "",
            "role": "admin" if str(cfg.get("role", "user")).lower() == "admin" else "user",
            "ai": bool(cfg.get("ai", False)), "ai_daily_limit": int(cfg.get("ai_daily_limit", 30) or 0),
            "password_hash": cfg["password_hash"], "disabled": bool(cfg.get("disabled", False)),
        }
    return users


def check_login(users, guard, username, password):
    """Return (user dict or None, message)."""
    u = (username or "").strip().lower()
    mins = guard.locked_for(u)
    if mins:
        return None, f"Too many failed attempts. Try again in {mins} minute(s)."
    rec = users.get(u)
    # verify against a dummy hash for unknown users, so timing does not reveal which usernames exist
    ok = verify_password(password or "", rec["password_hash"] if rec else _DUMMY)
    if not rec or not ok or rec.get("disabled"):
        guard.register_fail(u)
        return None, "Wrong username or password."
    guard.register_ok(u)
    return dict(rec, username=u), ""


_DUMMY = hash_password("not-a-real-password")
