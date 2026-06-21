#!/usr/bin/env python3
# ================================================================
#   DEV-RAW CORE BOT v2.5 — ULTIMATE SECURE & SMART EDITION
#   Force‑Join Fixed | Any Interpreter | Auto‑Install All Modules
# ================================================================

import subprocess
import sys
import os
import sqlite3
import threading
import time
import re
import html as html_module
import atexit
import random
import string
import logging
import shutil
import hashlib
import functools
from typing import Tuple, Optional
from datetime import datetime, timedelta
from threading import Thread
from collections import defaultdict, deque

try:
    import resource
    _HAS_RESOURCE = True
except ImportError:
    _HAS_RESOURCE = False

# ========== AUTO INSTALL MISSING MODULES ==========
required_modules = ['psutil', 'pyTelegramBotAPI', 'flask', 'requests']
for module in required_modules:
    try:
        __import__(module)
    except ImportError:
        print(f"📦 Installing {module}...")
        if module == 'psutil' and os.path.exists('/data/data/com.termux'):
            subprocess.check_call(['pkg', 'install', 'python-psutil', '-y'])
        else:
            subprocess.check_call([sys.executable, "-m", "pip", "install", module,
                                   "--break-system-packages"])

import psutil
import telebot
from telebot import types
import requests
from flask import Flask, request as flask_request, abort

# ================================================================
#   SECURITY CONFIGURATION
# ================================================================
RATE_LIMIT_MESSAGES  = 15
RATE_LIMIT_WINDOW    = 60
RATE_LIMIT_FILE_MSGS = 3
RATE_LIMIT_FILE_WIN  = 60
FLOOD_AUTO_BAN_THRESHOLD = 40

MAX_FILE_SIZE_MB     = 5
ALLOWED_EXTENSIONS   = {'.py', '.js'}
BLOCKED_CONTENT_PATTERNS = [
    r'os\.system\s*\(',
    r'subprocess\.call\s*\([^)]*shell\s*=\s*True',
    r'eval\s*\(.*input',
    r'exec\s*\(.*input',
    r'__import__\s*\(["\']os["\']\)',
    r'open\s*\(["\']\/etc\/',
    r'open\s*\(["\']\/proc\/',
    r'chmod\s*\(["\']\/etc',
]

PROC_MAX_MEMORY_MB   = 256
PROC_MAX_CPU_SECONDS = 3600
PROC_MAX_OPEN_FILES  = 100

SUSPICIOUS_CMD_PATTERNS = [
    r'^\/?(passwd|shadow|hosts|cron)',
    r'\.\.\/',
    r'rm\s+-rf',
    r'chmod\s+777',
    r'curl\s+.*\|\s*sh',
    r'wget\s+.*\|\s*sh',
]

# ================================================================
#   FLASK KEEP-ALIVE
# ================================================================
_flask_app = Flask(__name__)

@_flask_app.before_request
def _flask_security():
    if flask_request.endpoint == 'home' and flask_request.method != 'GET':
        abort(405)

@_flask_app.route('/')
def home():
    return "⚡ DEV-RAW Core v2.5 — Ultimate Edition", 200

def _run_flask():
    port = int(os.environ.get("PORT", os.environ.get("BOT_PORT", 5000)))
    _flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def keep_alive():
    t = Thread(target=_run_flask)
    t.daemon = True
    t.start()
    print("🟣 Flask Keep-Alive started.")

# ================================================================
#   BOT CONFIGURATION
# ================================================================
TOKEN          = os.environ.get("BOT_TOKEN", "8765038114:AAGO3lcbnA8dkiLr1PGMwtgBUytg3CIobbQ")
OWNER_ID       = int(os.environ.get("OWNER_ID", 6736719959))
ADMIN_ID       = int(os.environ.get("ADMIN_ID",  6736719959))
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", '@admin')

if not TOKEN:
    print("❌ BOT_TOKEN missing. Exiting.")
    sys.exit(1)

DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'devraw_bot.db')

BASE_DIR        = os.path.abspath(os.path.dirname(__file__))
UPLOAD_BOTS_DIR = os.path.join(BASE_DIR, 'upload_bots')
LOGS_DIR        = os.path.join(BASE_DIR, 'security_logs')
os.makedirs(UPLOAD_BOTS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

PREMIUM_USER_LIMIT = 999
ADMIN_LIMIT        = 999
OWNER_LIMIT        = float('inf')

SUPPORTED_EXTENSIONS = {
    '.py': '🐍 Python',
    '.js': '🟨 JavaScript (Node.js)'
}

# ================================================================
#   LOGGING
# ================================================================
import logging.handlers

_log_formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(name)s — %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
_file_handler = logging.handlers.RotatingFileHandler(
    os.path.join(LOGS_DIR, 'bot.log'), maxBytes=5*1024*1024, backupCount=5, encoding='utf-8'
)
_file_handler.setFormatter(_log_formatter)
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_log_formatter)

logger = logging.getLogger('devraw')
logger.setLevel(logging.INFO)
logger.addHandler(_file_handler)
logger.addHandler(_console_handler)

security_logger = logging.getLogger('devraw.security')
security_logger.setLevel(logging.WARNING)
_sec_handler = logging.handlers.RotatingFileHandler(
    os.path.join(LOGS_DIR, 'security.log'), maxBytes=5*1024*1024, backupCount=10, encoding='utf-8'
)
_sec_handler.setFormatter(_log_formatter)
security_logger.addHandler(_sec_handler)

# ================================================================
#   IN-MEMORY STATE
# ================================================================
bot_scripts         = {}
bot_scripts_lock    = threading.Lock()
user_subscriptions  = {}
user_files          = {}
active_users        = set()
admin_ids           = set()
banned_users        = set()
bot_locked          = False
broadcast_messages  = {}
force_join_enabled  = True
FREE_USER_LIMIT     = 1
force_channel_ids   = []
force_group_id      = 0
# Store custom invite links per chat_id (set by admin)
custom_invite_links = {}   # chat_id -> link
conn                = None

# ---- Global interpreter overrides (set by admin) ----
PYTHON_CMD = sys.executable   # default
NODE_CMD   = shutil.which("node") or "node"

# ================================================================
#   RATE LIMITER
# ================================================================
class RateLimiter:
    def __init__(self):
        self._lock      = threading.Lock()
        self._windows   = defaultdict(lambda: deque())
        self._violations= defaultdict(int)
        self._file_wins = defaultdict(lambda: deque())

    def is_allowed(self, user_id: int, is_file: bool = False) -> bool:
        if user_id in admin_ids:
            return True
        now = time.monotonic()
        limit = RATE_LIMIT_FILE_MSGS if is_file else RATE_LIMIT_MESSAGES
        window = RATE_LIMIT_FILE_WIN  if is_file else RATE_LIMIT_WINDOW
        q = self._file_wins[user_id] if is_file else self._windows[user_id]
        with self._lock:
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                self._violations[user_id] += 1
                security_logger.warning(f"RATE_LIMIT uid={user_id} violations={self._violations[user_id]}")
                return False
            q.append(now)
            return True

    def violation_count(self, user_id: int) -> int:
        with self._lock:
            return self._violations[user_id]

    def reset(self, user_id: int):
        with self._lock:
            self._windows[user_id].clear()
            self._file_wins[user_id].clear()
            self._violations[user_id] = 0

rate_limiter = RateLimiter()

# ================================================================
#   BOT INIT
# ================================================================
bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=10)

# ================================================================
#   DATABASE INIT
# ================================================================
def init_db():
    global conn
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        c = conn.cursor()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id   INTEGER PRIMARY KEY,
                username  TEXT,
                first_name TEXT,
                last_name  TEXT,
                verified   INTEGER DEFAULT 0,
                banned     INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id    INTEGER PRIMARY KEY,
                expiry     TEXT,
                file_limit INTEGER DEFAULT 999
            );
            CREATE TABLE IF NOT EXISTS user_files (
                user_id   INTEGER,
                file_name TEXT,
                file_type TEXT,
                file_path TEXT,
                file_hash TEXT,
                UNIQUE(user_id, file_name)
            );
            CREATE TABLE IF NOT EXISTS active_users (
                user_id INTEGER PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS subscription_keys (
                key_value  TEXT PRIMARY KEY,
                days_valid INTEGER,
                max_uses   INTEGER DEFAULT 1,
                used_count INTEGER DEFAULT 0,
                file_limit INTEGER DEFAULT 999
            );
            CREATE TABLE IF NOT EXISTS key_usage (
                key_value TEXT,
                user_id   INTEGER,
                UNIQUE(key_value, user_id)
            );
            CREATE TABLE IF NOT EXISTS bot_settings (
                setting_key   TEXT PRIMARY KEY,
                setting_value TEXT
            );
            CREATE TABLE IF NOT EXISTS premium_plans (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT,
                days       INTEGER,
                price      INTEGER,
                file_limit INTEGER
            );
            CREATE TABLE IF NOT EXISTS security_events (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   INTEGER,
                event     TEXT,
                detail    TEXT,
                ts        TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
            );
            CREATE TABLE IF NOT EXISTS force_links (
                chat_id     INTEGER PRIMARY KEY,
                invite_link TEXT
            );
        """)

        default_settings = {
            "free_user_limit":   str(FREE_USER_LIMIT),
            "force_join_enabled": "1",
            "force_channel_ids":  "",
            "force_group_id":     "0",
            "python_cmd":         PYTHON_CMD,
            "node_cmd":           NODE_CMD,
        }
        for key, val in default_settings.items():
            c.execute("INSERT OR IGNORE INTO bot_settings VALUES (?,?)", (key, val))

        c.execute("SELECT COUNT(*) FROM premium_plans")
        if c.fetchone()[0] == 0:
            plans = [
                ("📅 Weekly",    7,  2000,  2),
                ("📆 Monthly",  30, 15000,  5),
                ("📆 Quarterly",90, 50000,  0),
                ("💼 Admin",    -1, 200000, 0),
                ("📂 Bot File", -1, 50000,  0),
            ]
            c.executemany("INSERT INTO premium_plans (name,days,price,file_limit) VALUES (?,?,?,?)", plans)

        if OWNER_ID:
            c.execute("INSERT OR IGNORE INTO admins VALUES (?)", (OWNER_ID,))
        if ADMIN_ID and ADMIN_ID != OWNER_ID:
            c.execute("INSERT OR IGNORE INTO admins VALUES (?)", (ADMIN_ID,))

        conn.commit()
        logger.info("✅ Database initialised.")
    except Exception as e:
        logger.critical(f"❌ DB init failed: {e}", exc_info=True)
        sys.exit(1)

def load_data():
    global user_subscriptions, user_files, active_users, admin_ids, banned_users
    global FREE_USER_LIMIT, force_join_enabled, force_channel_ids, force_group_id
    global PYTHON_CMD, NODE_CMD, custom_invite_links
    try:
        c = conn.cursor()
        user_subscriptions.clear()
        for row in c.execute("SELECT user_id,expiry,file_limit FROM subscriptions"):
            try:
                es = row[1]
                expiry = datetime(9999,12,31,23,59,59) if es == '9999-12-31T23:59:59' else datetime.fromisoformat(es)
                user_subscriptions[row[0]] = {"expiry": expiry, "file_limit": row[2]}
            except:
                pass

        user_files.clear()
        for row in c.execute("SELECT user_id,file_name,file_type,file_path FROM user_files"):
            uid = row[0]
            user_files.setdefault(uid, []).append((row[1], row[2], row[3]))

        active_users.clear()
        for row in c.execute("SELECT user_id FROM active_users"):
            active_users.add(row[0])

        admin_ids = {OWNER_ID} if OWNER_ID else set()
        for row in c.execute("SELECT user_id FROM admins"):
            admin_ids.add(row[0])

        banned_users.clear()
        for row in c.execute("SELECT user_id FROM users WHERE banned=1"):
            banned_users.add(row[0])

        for row in c.execute("SELECT setting_key,setting_value FROM bot_settings"):
            key, val = row
            if key == "free_user_limit":
                FREE_USER_LIMIT = int(val) if val.isdigit() else 1
            elif key == "force_join_enabled":
                force_join_enabled = val == "1"
            elif key == "force_channel_ids":
                force_channel_ids = [int(x) for x in val.split(',') if x.strip().lstrip('-').isdigit()] if val.strip() else []
            elif key == "force_group_id":
                force_group_id = int(val) if val.strip().lstrip('-').isdigit() else 0
            elif key == "python_cmd":
                PYTHON_CMD = val if val else sys.executable
            elif key == "node_cmd":
                NODE_CMD = val if val else shutil.which("node") or "node"

        # Load custom invite links
        custom_invite_links.clear()
        for row in c.execute("SELECT chat_id, invite_link FROM force_links"):
            custom_invite_links[row[0]] = row[1]

        logger.info(f"📊 Data loaded: {len(active_users)} users, {len(user_subscriptions)} subs.")
    except Exception as e:
        logger.error(f"❌ Data load error: {e}", exc_info=True)

# ================================================================
#   SECURITY HELPERS
# ================================================================
def log_security_event(user_id: int, event: str, detail: str = ""):
    security_logger.warning(f"[{event}] uid={user_id} | {detail}")
    try:
        conn.execute("INSERT INTO security_events(user_id,event,detail) VALUES(?,?,?)",
                     (user_id, event, detail[:500]))
        conn.commit()
    except Exception:
        pass

def sanitize_filename(name: str) -> str:
    name = os.path.basename(name)
    name = re.sub(r'[^\w.\-]', '_', name)
    name = name.lstrip('.')
    if not name:
        name = "uploaded_file"
    return name[:120]

def validate_file_content(file_bytes: bytes, ext: str) -> Tuple[bool, str]:
    try:
        text = file_bytes.decode('utf-8', errors='replace')
    except Exception:
        return False, "File cannot be decoded"
    for pattern in BLOCKED_CONTENT_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return False, f"Dangerous pattern found: `{pattern}`"
    return True, ""

def is_safe_path(base_dir: str, path: str) -> bool:
    base = os.path.realpath(base_dir)
    target = os.path.realpath(path)
    return target.startswith(base + os.sep) or target == base

def sha256_file(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def check_suspicious_input(text: str) -> bool:
    for pattern in SUSPICIOUS_CMD_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

def auto_ban_check(user_id: int):
    if user_id in admin_ids:
        return
    violations = rate_limiter.violation_count(user_id)
    if violations >= FLOOD_AUTO_BAN_THRESHOLD and user_id not in banned_users:
        _ban_user_internal(user_id)
        log_security_event(user_id, "AUTO_BAN", f"violations={violations}")
        logger.warning(f"🚨 Auto-banned uid={user_id}")
        try:
            bot.send_message(user_id, "🚫 Auto-ban due to flood/spam.")
        except Exception:
            pass

# ================================================================
#   GATE DECORATOR
# ================================================================
def secure_handler(is_file_upload=False):
    def decorator(fn):
        def wrapper(message_or_call, *args, **kwargs):
            if hasattr(message_or_call, 'from_user'):
                user_id = message_or_call.from_user.id
                text    = getattr(message_or_call, 'text', '') or ''
            else:
                user_id = message_or_call.id
                text    = ''

            if is_user_banned(user_id):
                try:
                    if hasattr(message_or_call, 'chat'):
                        bot.send_message(message_or_call.chat.id, "🚫 You are banned.")
                except Exception:
                    pass
                return

            if not rate_limiter.is_allowed(user_id, is_file=is_file_upload):
                auto_ban_check(user_id)
                try:
                    if hasattr(message_or_call, 'chat'):
                        bot.send_message(message_or_call.chat.id, "⚠️ Rate limit exceeded. Please wait.")
                except Exception:
                    pass
                return

            if text and check_suspicious_input(text):
                log_security_event(user_id, "SUSPICIOUS_INPUT", text[:200])
                try:
                    if hasattr(message_or_call, 'chat'):
                        bot.send_message(message_or_call.chat.id, "⛔ Suspicious command blocked.")
                except Exception:
                    pass
                return

            return fn(message_or_call, *args, **kwargs)
        functools.update_wrapper(wrapper, fn)
        return wrapper
    return decorator

# ================================================================
#   NODE.JS AUTO-INSTALL
# ================================================================
def install_nodejs():
    if shutil.which("node") and shutil.which("npm"):
        return True
    logger.info("🔧 Installing Node.js...")
    try:
        if os.path.exists('/data/data/com.termux'):
            subprocess.check_call(['pkg', 'install', 'nodejs', '-y'])
        else:
            try:
                subprocess.check_call(['sudo', 'apt-get', 'update', '-q'])
                subprocess.check_call(['sudo', 'apt-get', 'install', '-y', 'nodejs', 'npm'])
            except Exception:
                subprocess.check_call(['apt-get', 'update', '-q'])
                subprocess.check_call(['apt-get', 'install', '-y', 'nodejs', 'npm'])
        return bool(shutil.which("node") and shutil.which("npm"))
    except Exception as e:
        logger.error(f"❌ Node.js install failed: {e}")
        return False

# ================================================================
#   SYSTEM STATS
# ================================================================
def get_system_stats():
    try:
        cpu = psutil.cpu_percent(interval=0.5)
    except Exception:
        cpu = 0.0
    try:
        m = psutil.virtual_memory()
        ram_pct = m.percent; ram_used = m.used >> 20; ram_total = m.total >> 20
    except Exception:
        ram_pct = 0; ram_used = 0; ram_total = 0
    return {'cpu': cpu, 'ram_percent': ram_pct, 'ram_used': ram_used, 'ram_total': ram_total}

# ================================================================
#   BAN SYSTEM
# ================================================================
def is_user_banned(user_id):
    return user_id in banned_users

def _ban_user_internal(user_id):
    conn.execute("UPDATE users SET banned=1 WHERE user_id=?", (user_id,))
    conn.commit()
    banned_users.add(user_id)
    stop_user_bots(user_id)
    active_users.discard(user_id)
    conn.execute("DELETE FROM active_users WHERE user_id=?", (user_id,))
    conn.commit()

def ban_user(user_id):
    if user_id in admin_ids:
        return False, "❌ Cannot ban admin/owner."
    _ban_user_internal(user_id)
    log_security_event(user_id, "MANUAL_BAN")
    return True, f"✅ User <code>{user_id}</code> has been banned."

def unban_user(user_id):
    if user_id not in banned_users:
        return False, "⚠️ User is not banned."
    conn.execute("UPDATE users SET banned=0 WHERE user_id=?", (user_id,))
    conn.commit()
    banned_users.discard(user_id)
    rate_limiter.reset(user_id)
    log_security_event(user_id, "MANUAL_UNBAN")
    return True, f"✅ User <code>{user_id}</code> unbanned."

def stop_user_bots(user_id):
    with bot_scripts_lock:
        keys = [k for k in bot_scripts if k.startswith(f"{user_id}_")]
        for k in keys:
            kill_process_tree(bot_scripts[k])
            del bot_scripts[k]

# ================================================================
#   PREMIUM PLANS
# ================================================================
def get_all_premium_plans():
    c = conn.cursor()
    c.execute("SELECT id,name,days,price,file_limit FROM premium_plans ORDER BY id")
    return [{"id": r[0], "name": r[1], "days": r[2], "price": r[3], "file_limit": r[4]} for r in c.fetchall()]

def add_premium_plan(name, days, price, file_limit):
    conn.execute("INSERT INTO premium_plans(name,days,price,file_limit) VALUES(?,?,?,?)",
                 (name, days, price, file_limit))
    conn.commit()

def delete_premium_plan(plan_id):
    conn.execute("DELETE FROM premium_plans WHERE id=?", (int(plan_id),))
    conn.commit()

# ================================================================
#   USER VERIFICATION
# ================================================================
def is_premium_user(user_id):
    sub = user_subscriptions.get(user_id)
    return bool(sub and sub['expiry'] > datetime.now())

def get_user_status(user_id):
    if user_id == OWNER_ID: return "👑 Owner"
    if user_id in admin_ids: return "🛡️ Admin"
    if is_premium_user(user_id): return "✨ Premium"
    return "🎯 Free"

def is_user_verified(user_id):
    if user_id in admin_ids: return True
    c = conn.cursor()
    c.execute("SELECT verified FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    return bool(row and row[0] == 1)

def set_user_verified(user_id):
    conn.execute("UPDATE users SET verified=1 WHERE user_id=?", (user_id,))
    conn.commit()

def check_force_join_and_access(user_id):
    if is_user_banned(user_id): return False
    if user_id in admin_ids: return True
    return is_user_verified(user_id)

# ================================================================
#   FORCE‑JOIN ENHANCED
# ================================================================
def get_channel_name(chat_id):
    try:
        return bot.get_chat(chat_id).title
    except Exception:
        return f"Channel {chat_id}"

def get_group_name(chat_id):
    try:
        return bot.get_chat(chat_id).title
    except Exception:
        return f"Group {chat_id}"

def get_invite_link(chat_id):
    # 1) custom link from DB
    link = custom_invite_links.get(chat_id)
    if link:
        return link
    # 2) try to generate via bot
    try:
        link = bot.export_chat_invite_link(chat_id)
        # cache in memory
        custom_invite_links[chat_id] = link
        return link
    except Exception:
        return None

def save_custom_invite_link(chat_id, link):
    conn.execute("INSERT OR REPLACE INTO force_links(chat_id, invite_link) VALUES(?,?)", (chat_id, link))
    conn.commit()
    custom_invite_links[chat_id] = link

def create_force_join_message():
    lines = [
        "╔══════════════════════════╗",
        "║   🔐 JOIN REQUIRED       ║",
        "╚══════════════════════════╝",
        "",
        "✨ Please join the following channels/group:",
        ""
    ]
    for cid in force_channel_ids:
        name = get_channel_name(cid)
        lines.append(f"📣 {name}")
    if force_group_id:
        lines.append(f"👥 {get_group_name(force_group_id)}")
    lines.append("")
    lines.append("📋 Steps:")
    lines.append("1️⃣ Click buttons below")
    lines.append("2️⃣ Wait 30 seconds")
    lines.append("3️⃣ Press ✅ Verify Membership")
    return "\n".join(lines)

def create_force_join_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    for cid in force_channel_ids:
        link = get_invite_link(cid)
        btn_text = f"📣 {get_channel_name(cid)}"
        if link:
            markup.add(types.InlineKeyboardButton(btn_text, url=link))
        else:
            markup.add(types.InlineKeyboardButton(btn_text + " (no link)", callback_data='no_link'))
    if force_group_id:
        gl = get_invite_link(force_group_id)
        if gl:
            markup.add(types.InlineKeyboardButton(f"👥 {get_group_name(force_group_id)}", url=gl))
        else:
            markup.add(types.InlineKeyboardButton(f"👥 {get_group_name(force_group_id)} (no link)", callback_data='no_link'))
    markup.add(types.InlineKeyboardButton("✅ Verify Membership", callback_data='check_membership'))
    return markup

def verify_membership(user_id):
    if user_id in admin_ids: return True, ""
    missing = []
    for ch_id in force_channel_ids:
        try:
            m = bot.get_chat_member(ch_id, user_id)
            if m.status not in ('member', 'administrator', 'creator'):
                missing.append(f"📣 {get_channel_name(ch_id)}")
        except Exception:
            missing.append(f"📣 {get_channel_name(ch_id)} (bot error)")
    if force_group_id:
        try:
            gm = bot.get_chat_member(force_group_id, user_id)
            if gm.status not in ('member', 'administrator', 'creator'):
                missing.append(f"👥 {get_group_name(force_group_id)}")
        except Exception:
            missing.append(f"👥 {get_group_name(force_group_id)} (bot error)")

    if not missing:
        if not is_user_verified(user_id):
            set_user_verified(user_id)
        return True, ""
    else:
        msg = "❌ You haven't joined:\n" + "\n".join(missing)
        return False, msg

# ================================================================
#   STORAGE HELPERS
# ================================================================
def get_user_folder(user_id):
    folder = os.path.join(UPLOAD_BOTS_DIR, str(int(user_id)))
    os.makedirs(folder, exist_ok=True)
    return folder

def get_user_file_count(user_id):
    return len(user_files.get(user_id, []))

def get_user_file_limit(user_id):
    if user_id == OWNER_ID or user_id in admin_ids:
        return float('inf')
    if is_premium_user(user_id):
        sub = user_subscriptions.get(user_id, {})
        lim = sub.get('file_limit', PREMIUM_USER_LIMIT)
        return float('inf') if lim == 0 else lim
    return FREE_USER_LIMIT

# ================================================================
#   KEY MANAGEMENT
# ================================================================
def generate_subscription_key(days, file_limit):
    code = ''.join(random.SystemRandom().choices(string.ascii_uppercase + string.digits, k=12))
    key  = f"DEVRAW-{code}"
    conn.execute("INSERT INTO subscription_keys(key_value,days_valid,max_uses,used_count,file_limit) VALUES(?,?,1,0,?)",
                 (key, days, file_limit))
    conn.commit()
    return key

def redeem_subscription_key(key_value, user_id):
    key_value = re.sub(r'[^A-Z0-9\-]', '', key_value.strip().upper())
    c = conn.cursor()
    c.execute("SELECT days_valid,max_uses,used_count,file_limit FROM subscription_keys WHERE key_value=?", (key_value,))
    row = c.fetchone()
    if not row:
        return False, "❌ Invalid key."
    days_valid, max_uses, used_count, file_limit = row
    if used_count >= max_uses:
        return False, "❌ Key already used."
    c.execute("SELECT COUNT(*) FROM key_usage WHERE key_value=? AND user_id=?", (key_value, user_id))
    if c.fetchone()[0] > 0:
        return False, "❌ You already used this key."

    current_expiry = user_subscriptions.get(user_id, {}).get('expiry', datetime.now())
    if current_expiry < datetime.now():
        current_expiry = datetime.now()
    new_expiry = datetime(9999,12,31,23,59,59) if days_valid == -1 else current_expiry + timedelta(days=days_valid)
    save_subscription(user_id, new_expiry, file_limit)

    conn.execute("UPDATE subscription_keys SET used_count=used_count+1 WHERE key_value=?", (key_value,))
    conn.execute("INSERT INTO key_usage(key_value,user_id) VALUES(?,?)", (key_value, user_id))
    conn.commit()

    limit_display = "Unlimited" if file_limit == 0 else str(file_limit)
    days_display  = "Lifetime" if days_valid == -1 else f"{days_valid} days"
    exp_display   = "Lifetime" if days_valid == -1 else new_expiry.strftime('%Y-%m-%d %H:%M')
    return True, (
        f"✨ <b>Key Activated!</b>\n"
        f"🔑 <code>{key_value}</code>\n"
        f"📅 {days_display}\n"
        f"📁 File limit: {limit_display}\n"
        f"⏳ Expires: {exp_display}"
    )

def save_subscription(user_id, expiry, file_limit):
    es = '9999-12-31T23:59:59' if expiry >= datetime(9999,12,31,23,59,59) else expiry.isoformat()
    conn.execute("INSERT OR REPLACE INTO subscriptions(user_id,expiry,file_limit) VALUES(?,?,?)",
                 (user_id, es, file_limit))
    conn.commit()
    user_subscriptions[user_id] = {'expiry': expiry, 'file_limit': file_limit}

def delete_subscription_key(key_value):
    c = conn.cursor()
    c.execute("SELECT user_id FROM key_usage WHERE key_value=?", (key_value,))
    for row in c.fetchall():
        uid = row[0]
        conn.execute("DELETE FROM subscriptions WHERE user_id=?", (uid,))
        user_subscriptions.pop(uid, None)
    conn.execute("DELETE FROM subscription_keys WHERE key_value=?", (key_value,))
    conn.execute("DELETE FROM key_usage WHERE key_value=?", (key_value,))
    conn.commit()

def get_all_subscription_keys():
    c = conn.cursor()
    c.execute("SELECT key_value,days_valid,max_uses,used_count,file_limit FROM subscription_keys")
    return [{"key_value": r[0], "days_valid": r[1], "max_uses": r[2], "used_count": r[3], "file_limit": r[4]}
            for r in c.fetchall()]

# ================================================================
#   PROCESS MANAGEMENT (resource limits + custom interpreters)
# ================================================================
def _set_child_limits():
    if not _HAS_RESOURCE:
        return
    try:
        mem_bytes = PROC_MAX_MEMORY_MB * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
    except Exception:
        pass
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (PROC_MAX_CPU_SECONDS, PROC_MAX_CPU_SECONDS))
    except Exception:
        pass
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (PROC_MAX_OPEN_FILES, PROC_MAX_OPEN_FILES))
    except Exception:
        pass

def is_bot_running(script_owner_id, file_name):
    key = f"{script_owner_id}_{file_name}"
    with bot_scripts_lock:
        info = bot_scripts.get(key)
    if info and info.get('process'):
        try:
            p = psutil.Process(info['process'].pid)
            return p.is_running() and p.status() != psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            pass
    return False

def kill_process_tree(process_info):
    try:
        proc = process_info.get('process')
        if proc and hasattr(proc, 'pid'):
            try:
                parent = psutil.Process(proc.pid)
                for child in parent.children(recursive=True):
                    try: child.kill()
                    except Exception: pass
                parent.kill()
                parent.wait(timeout=5)
            except Exception:
                pass
            lf = process_info.get('log_file')
            if lf:
                try: lf.close()
                except Exception: pass
    except Exception as e:
        logger.error(f"kill_process_tree error: {e}")

PACKAGE_MAP = {
    'telegram': 'python-telegram-bot', 'cv2': 'opencv-python',
    'sklearn': 'scikit-learn', 'PIL': 'Pillow', 'bs4': 'beautifulsoup4',
    'dotenv': 'python-dotenv', 'yaml': 'pyyaml', 'Crypto': 'pycryptodome',
    'pandas': 'pandas', 'numpy': 'numpy', 'requests': 'requests',
    'flask': 'flask', 'django': 'django'
}

def run_python_script(script_path, script_owner_id, user_folder, file_name, message_obj, attempt=1):
    max_attempts = 3
    if attempt > max_attempts:
        bot.reply_to(message_obj, f"❌ Failed to start {html_module.escape(file_name)} after {max_attempts} attempts.", parse_mode='HTML')
        return
    script_key = f"{script_owner_id}_{file_name}"
    log_file = None
    try:
        if not os.path.exists(script_path) or not is_safe_path(UPLOAD_BOTS_DIR, script_path):
            bot.reply_to(message_obj, "❌ File not found or path insecure.")
            return
        log_file_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        if not is_safe_path(user_folder, log_file_path):
            bot.reply_to(message_obj, "❌ Log path insecure.")
            return
        log_file = open(log_file_path, 'w', encoding='utf-8', errors='ignore')
        run_env = os.environ.copy()
        run_env['PIP_BREAK_SYSTEM_PACKAGES'] = '1'
        for sk in ('BOT_TOKEN', 'OWNER_ID', 'ADMIN_ID', 'DATABASE_URL', 'SESSION_SECRET'):
            run_env.pop(sk, None)
        python_exe = PYTHON_CMD if shutil.which(PYTHON_CMD) else sys.executable
        process = subprocess.Popen(
            [python_exe, script_path],
            cwd=user_folder, stdout=log_file, stderr=log_file,
            stdin=subprocess.PIPE, encoding='utf-8', errors='ignore', bufsize=1,
            env=run_env, preexec_fn=_set_child_limits
        )
        with bot_scripts_lock:
            bot_scripts[script_key] = {
                'process': process, 'log_file': log_file, 'file_name': file_name,
                'chat_id': message_obj.chat.id, 'script_owner_id': script_owner_id,
                'start_time': datetime.now(), 'user_folder': user_folder,
                'type': 'py', 'script_key': script_key
            }
        time.sleep(3)
        if process.poll() is not None:
            log_file.flush()
            try:
                with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as lf:
                    log_content = lf.read()
            except Exception:
                log_content = ''
            install_pkg = None
            m1 = re.search(r"ModuleNotFoundError: No module named '([^']+)'", log_content)
            if m1:
                install_pkg = PACKAGE_MAP.get(m1.group(1).split('.')[0], m1.group(1).split('.')[0])
            if not install_pkg:
                m2 = re.search(r"ImportError: No module named '([^']+)'", log_content)
                if m2:
                    install_pkg = PACKAGE_MAP.get(m2.group(1).split('.')[0], m2.group(1).split('.')[0])
            if install_pkg and attempt < max_attempts:
                with bot_scripts_lock:
                    bot_scripts.pop(script_key, None)
                bot.reply_to(message_obj, f"🔧 Installing <code>{install_pkg}</code>...", parse_mode='HTML')
                res = subprocess.run([sys.executable,'-m','pip','install',install_pkg,'--break-system-packages','--timeout','120'],
                                     capture_output=True, text=True, timeout=120)
                if res.returncode == 0:
                    threading.Thread(target=run_python_script,
                                     args=(script_path, script_owner_id, user_folder, file_name, message_obj, attempt+1)).start()
                else:
                    bot.reply_to(message_obj, f"❌ Install failed: {html_module.escape(res.stderr[:300])}", parse_mode='HTML')
                return
            with bot_scripts_lock:
                bot_scripts.pop(script_key, None)
            safe_preview = html_module.escape(log_content[-800:]) if log_content else ''
            bot.reply_to(message_obj,
                         f"❌ <code>{html_module.escape(file_name)}</code> error:\n<pre>{safe_preview}</pre>",
                         parse_mode='HTML')
            return
        bot.reply_to(message_obj,
                     f"✅ <code>{html_module.escape(file_name)}</code> (Python) started (PID: {process.pid})",
                     parse_mode='HTML')
    except Exception as e:
        if log_file and not log_file.closed:
            log_file.close()
        bot.reply_to(message_obj, f"❌ Error: {str(e)}", parse_mode='HTML')
        with bot_scripts_lock:
            bot_scripts.pop(script_key, None)

def run_js_script(script_path, script_owner_id, user_folder, file_name, message_obj, attempt=1):
    max_attempts = 3
    if attempt > max_attempts:
        bot.reply_to(message_obj, f"❌ Failed to start {html_module.escape(file_name)}", parse_mode='HTML')
        return
    script_key = f"{script_owner_id}_{file_name}"
    node_exe = NODE_CMD if shutil.which(NODE_CMD) else "node"
    if not shutil.which(node_exe):
        bot.reply_to(message_obj, "❌ Node.js not found."); return
    log_file = None
    try:
        if not os.path.exists(script_path) or not is_safe_path(UPLOAD_BOTS_DIR, script_path):
            bot.reply_to(message_obj, "❌ File not found"); return
        with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        required = {m.group(1) for m in re.finditer(r"require\(['\"]([^'\"./][^'\"]*)['\"]", content)}
        missing  = [m for m in required if not os.path.exists(os.path.join(user_folder, 'node_modules', m))]
        if missing:
            bot.reply_to(message_obj, f"📦 Installing: <code>{', '.join(missing)}</code>...", parse_mode='HTML')
            subprocess.run([shutil.which("npm") or "npm", "install", "--save"] + missing, cwd=user_folder, check=False, timeout=120)
            time.sleep(1)
        log_file_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        if not is_safe_path(user_folder, log_file_path):
            bot.reply_to(message_obj, "❌ Log path insecure"); return
        log_file = open(log_file_path, 'w', encoding='utf-8', errors='ignore')
        run_env = os.environ.copy()
        for sk in ('BOT_TOKEN', 'OWNER_ID', 'ADMIN_ID', 'DATABASE_URL', 'SESSION_SECRET'):
            run_env.pop(sk, None)
        process = subprocess.Popen(
            [node_exe, script_path], cwd=user_folder, stdout=log_file, stderr=log_file,
            stdin=subprocess.PIPE, encoding='utf-8', errors='ignore', bufsize=1,
            env=run_env, preexec_fn=_set_child_limits
        )
        with bot_scripts_lock:
            bot_scripts[script_key] = {
                'process': process, 'log_file': log_file, 'file_name': file_name,
                'chat_id': message_obj.chat.id, 'script_owner_id': script_owner_id,
                'start_time': datetime.now(), 'user_folder': user_folder,
                'type': 'js', 'script_key': script_key
            }
        time.sleep(2)
        if process.poll() is not None:
            log_file.flush()
            try:
                with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as lf:
                    log_content = lf.read()
            except Exception:
                log_content = ''
            if 'ERR_PACKAGE_PATH_NOT_EXPORTED' in log_content:
                # try to fix commonjs fallback
                for pkg, ver in {'node-telegram-bot-api': '0.66.0'}.items():
                    if pkg in log_content:
                        with bot_scripts_lock:
                            bot_scripts.pop(script_key, None)
                        subprocess.run(["npm","install",f"{pkg}@{ver}","--save"], cwd=user_folder, timeout=120)
                        threading.Thread(target=run_js_script,
                                         args=(script_path, script_owner_id, user_folder, file_name, message_obj, attempt+1)).start()
                        return
            with bot_scripts_lock:
                bot_scripts.pop(script_key, None)
            bot.reply_to(message_obj,
                         f"❌ <code>{html_module.escape(file_name)}</code> JS error:\n<pre>{html_module.escape(log_content[-800:])}</pre>",
                         parse_mode='HTML')
            return
        bot.reply_to(message_obj,
                     f"✅ <code>{html_module.escape(file_name)}</code> (Node.js) started (PID: {process.pid})",
                     parse_mode='HTML')
    except Exception as e:
        if log_file and not log_file.closed:
            log_file.close()
        bot.reply_to(message_obj, f"❌ Error: {str(e)}", parse_mode='HTML')
        with bot_scripts_lock:
            bot_scripts.pop(script_key, None)

def send_log_file(user_id, file_name, chat_id):
    folder = get_user_folder(user_id)
    log_path = os.path.join(folder, f"{os.path.splitext(file_name)[0]}.log")
    if not is_safe_path(folder, log_path):
        return False
    if os.path.exists(log_path):
        with open(log_path, 'rb') as f:
            bot.send_document(chat_id, f, caption=f"📋 Log for {file_name}")
        return True
    bot.send_message(chat_id, f"📭 No log for <code>{html_module.escape(file_name)}</code>", parse_mode='HTML')
    return False

# ================================================================
#   UI KEYBOARDS
# ================================================================
def create_main_menu_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = ['📤 Upload File','📁 My Files','🔑 Redeem Key',
               '✨ Upgrade','👤 Profile','📊 Status']
    if user_id in admin_ids:
        buttons.append('⚙️ Admin Panel')
    for i in range(0, len(buttons), 2):
        row = [buttons[i], buttons[i+1]] if i+1 < len(buttons) else [buttons[i]]
        markup.row(*row)
    return markup

def create_manage_files_keyboard(user_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    files = user_files.get(user_id, [])
    if not files:
        markup.add(types.InlineKeyboardButton("📭 No files", callback_data='no_files'))
    else:
        for fn, ft, fp in files:
            status = "🟢" if is_bot_running(user_id, fn) else "🔴"
            markup.add(types.InlineKeyboardButton(f"{status} {fn}", callback_data=f'file_{user_id}_{fn}'))
    markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data='back_to_main'))
    return markup

def create_file_management_buttons(user_id, file_name, is_running=True):
    markup = types.InlineKeyboardMarkup(row_width=2)
    if is_running:
        markup.row(
            types.InlineKeyboardButton("⏸️ Stop", callback_data=f'stop_{user_id}_{file_name}'),
            types.InlineKeyboardButton("🔄 Restart", callback_data=f'restart_{user_id}_{file_name}')
        )
    else:
        markup.row(types.InlineKeyboardButton("▶️ Start", callback_data=f'start_{user_id}_{file_name}'))
    markup.row(
        types.InlineKeyboardButton("🗑️ Delete", callback_data=f'delete_{user_id}_{file_name}'),
        types.InlineKeyboardButton("📋 Log", callback_data=f'logs_{user_id}_{file_name}')
    )
    markup.add(types.InlineKeyboardButton("📥 Download", callback_data=f'download_{user_id}_{file_name}'))
    markup.add(types.InlineKeyboardButton("⬅️ Back to files", callback_data='manage_files'))
    return markup

def create_admin_panel_keyboard(user_id=None):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = ['📊 Stats','👥 All Users','✨ Pro Users','🔄 Running',
               '📢 Broadcast','🔑 Gen Key','🗑️ Del Key','🔢 List Keys',
               '📈 Limit','💎 Plans','⚙️ Settings','🔗 Force Join',
               '🚫 Ban','✅ Unban','🛡️ Security Logs']
    if user_id == OWNER_ID:
        buttons = ['➕ Add Admin','➖ Remove Admin'] + buttons
    for i in range(0, len(buttons), 2):
        row = [buttons[i], buttons[i+1]] if i+1 < len(buttons) else [buttons[i]]
        markup.row(*row)
    markup.row('⬅️ Back')
    return markup

# ================================================================
#   DATABASE UTILS
# ================================================================
def safe_answer_callback(call, text, show_alert=False):
    try:
        bot.answer_callback_query(call.id, text, show_alert=show_alert)
    except Exception:
        pass

def save_user(user_id, username, first_name, last_name):
    conn.execute("INSERT OR REPLACE INTO users(user_id,username,first_name,last_name) VALUES(?,?,?,?)",
                 (user_id, username, first_name, last_name))
    conn.commit()

def save_user_file(user_id, file_name, file_type, file_path, file_hash=""):
    conn.execute("INSERT OR REPLACE INTO user_files(user_id,file_name,file_type,file_path,file_hash) VALUES(?,?,?,?,?)",
                 (user_id, file_name, file_type, file_path, file_hash))
    conn.commit()
    user_files.setdefault(user_id, [])
    user_files[user_id] = [f for f in user_files[user_id] if f[0] != file_name]
    user_files[user_id].append((file_name, file_type, file_path))

def remove_user_file_db(user_id, file_name):
    conn.execute("DELETE FROM user_files WHERE user_id=? AND file_name=?", (user_id, file_name))
    conn.commit()
    if user_id in user_files:
        user_files[user_id] = [f for f in user_files[user_id] if f[0] != file_name]

def add_active_user(user_id):
    active_users.add(user_id)
    conn.execute("INSERT OR IGNORE INTO active_users(user_id) VALUES(?)", (user_id,))
    conn.commit()

def update_file_limit(new_limit):
    global FREE_USER_LIMIT
    FREE_USER_LIMIT = new_limit
    conn.execute("INSERT OR REPLACE INTO bot_settings(setting_key,setting_value) VALUES('free_user_limit',?)",
                 (str(new_limit),))
    conn.commit()

def update_force_join_status(enabled):
    global force_join_enabled
    force_join_enabled = enabled
    conn.execute("INSERT OR REPLACE INTO bot_settings(setting_key,setting_value) VALUES('force_join_enabled',?)",
                 ('1' if enabled else '0',))
    conn.commit()

def show_main_menu(message, user_id):
    welcome = (
        f"╔══════════════════════╗\n"
        f"║  🤖 DEV-RAW Core v2.5  ║\n"
        f"╚══════════════════════╝\n\n"
        f"👋 Hello <b>{html_module.escape(message.from_user.first_name)}</b>!\n"
        f"🛡️ Secure Python & JS Hosting\n\n"
        f"📊 Status: {get_user_status(user_id)}"
    )
    bot.send_message(message.chat.id, welcome, reply_markup=create_main_menu_keyboard(user_id), parse_mode='HTML')

# ================================================================
#   BOT HANDLERS
# ================================================================
@bot.message_handler(commands=['start', 'help'])
@secure_handler()
def command_send_welcome(message):
    user_id = message.from_user.id
    if bot_locked and user_id not in admin_ids:
        bot.send_message(message.chat.id, "🔒 Bot under maintenance.")
        return
    save_user(user_id, message.from_user.username, message.from_user.first_name, message.from_user.last_name)
    add_active_user(user_id)
    if is_user_verified(user_id):
        show_main_menu(message, user_id)
        return
    if not force_join_enabled:
        set_user_verified(user_id)
        show_main_menu(message, user_id)
        return
    bot.send_message(message.chat.id, create_force_join_message(),
                     reply_markup=create_force_join_keyboard(), parse_mode='HTML')

@bot.message_handler(content_types=['document'])
@secure_handler(is_file_upload=True)
def handle_document(message):
    user_id = message.from_user.id
    if bot_locked and user_id not in admin_ids:
        bot.reply_to(message, "🔒 Under maintenance"); return
    if not check_force_join_and_access(user_id):
        bot.send_message(message.chat.id, create_force_join_message(),
                         reply_markup=create_force_join_keyboard(), parse_mode='HTML'); return

    file_limit = get_user_file_limit(user_id)
    current   = get_user_file_count(user_id)
    if file_limit != float('inf') and current >= file_limit:
        bot.reply_to(message, f"❌ File limit reached ({int(file_limit)})."); return

    doc = message.document
    if doc.file_size and doc.file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        bot.reply_to(message, f"❌ File too large (max {MAX_FILE_SIZE_MB}MB)."); return

    raw_name = doc.file_name or "uploaded_file.py"
    file_name = sanitize_filename(raw_name)
    file_ext  = os.path.splitext(file_name)[1].lower()
    if file_ext not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(f"<code>{e}</code>" for e in SUPPORTED_EXTENSIONS)
        bot.reply_to(message, f"❌ Unsupported type. Allowed: {supported}", parse_mode='HTML'); return

    try:
        file_info     = bot.get_file(doc.file_id)
        downloaded    = bot.download_file(file_info.file_path)
    except Exception as e:
        bot.reply_to(message, f"❌ Download failed: {e}"); return

    ok, reason = validate_file_content(downloaded, file_ext)
    if not ok:
        log_security_event(user_id, "BLOCKED_UPLOAD", reason)
        bot.reply_to(message, f"🛡️ File blocked:\n{reason}", parse_mode='HTML')
        return

    file_hash   = sha256_file(downloaded)
    user_folder = get_user_folder(user_id)
    file_path   = os.path.join(user_folder, file_name)

    if not is_safe_path(user_folder, file_path):
        log_security_event(user_id, "PATH_TRAVERSAL", file_name)
        bot.reply_to(message, "❌ Invalid path."); return

    with open(file_path, 'wb') as f:
        f.write(downloaded)

    file_type = SUPPORTED_EXTENSIONS[file_ext]
    save_user_file(user_id, file_name, file_type, file_path, file_hash)

    try:
        bot.forward_message(OWNER_ID, message.chat.id, message.message_id)
        bot.send_message(OWNER_ID,
                         f"📤 New file\n👤 {html_module.escape(message.from_user.first_name)} (ID: {user_id})\n"
                         f"📄 <code>{html_module.escape(file_name)}</code>\n🔐 SHA256: <code>{file_hash[:16]}…</code>",
                         parse_mode='HTML')
    except Exception:
        pass

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📁 My Files", callback_data='manage_files'))
    bot.reply_to(message,
                 f"✅ <code>{html_module.escape(file_name)}</code> uploaded\n📦 {file_type}\n🔐 Hash: <code>{file_hash[:16]}…</code>",
                 reply_markup=markup, parse_mode='HTML')

@bot.message_handler(func=lambda m: True)
@secure_handler()
def handle_text_messages(message):
    user_id = message.from_user.id
    if bot_locked and user_id not in admin_ids:
        bot.send_message(message.chat.id, "🔒 Maintenance"); return
    if not check_force_join_and_access(user_id):
        bot.send_message(message.chat.id, create_force_join_message(),
                         reply_markup=create_force_join_keyboard(), parse_mode='HTML'); return
    text = message.text or ''
    # Main menu dispatch
    if text == '📤 Upload File':
        bot.send_message(message.chat.id, "📤 Send a <code>.py</code> or <code>.js</code> file.", parse_mode='HTML')
    elif text == '📁 My Files':
        handle_manage_files(message)
    elif text == '🔑 Redeem Key':
        msg = bot.send_message(message.chat.id, "🔑 Enter key (DEVRAW-XXXXXXXXXXXX):")
        bot.register_next_step_handler(msg, process_redeem_key)
    elif text == '✨ Upgrade':
        handle_upgrade(message)
    elif text == '👤 Profile':
        handle_my_info(message)
    elif text == '📊 Status':
        handle_status(message)
    elif text == '⬅️ Back':
        bot.send_message(message.chat.id, "🏠 Main menu", reply_markup=create_main_menu_keyboard(user_id))
    elif text == '⚙️ Admin Panel' and user_id in admin_ids:
        bot.send_message(message.chat.id, "⚙️ Admin panel", reply_markup=create_admin_panel_keyboard(user_id))
    elif text in ('📊 Stats','👥 All Users','✨ Pro Users','🔄 Running',
                 '📢 Broadcast','🔑 Gen Key','🗑️ Del Key','🔢 List Keys',
                 '📈 Limit','💎 Plans','⚙️ Settings','🔗 Force Join',
                 '🚫 Ban','✅ Unban','🛡️ Security Logs') and user_id in admin_ids:
        handle_admin_command(message, text)
    elif text in ('➕ Add Admin','➖ Remove Admin') and user_id == OWNER_ID:
        handle_owner_command(message, text)
    else:
        bot.send_message(message.chat.id, "❌ Unknown command. Use the menu.")

def handle_admin_command(message, cmd):
    user_id = message.from_user.id
    if cmd == '📊 Stats': handle_stats(message)
    elif cmd == '👥 All Users': handle_all_users(message)
    elif cmd == '✨ Pro Users': handle_premium_users(message)
    elif cmd == '🔄 Running': handle_running_scripts(message)
    elif cmd == '📢 Broadcast':
        msg = bot.send_message(message.chat.id, "📢 Enter broadcast message:")
        bot.register_next_step_handler(msg, process_broadcast)
    elif cmd == '🔑 Gen Key': handle_generate_key(message)
    elif cmd == '🗑️ Del Key': handle_delete_key(message)
    elif cmd == '🔢 List Keys': handle_list_keys(message)
    elif cmd == '📈 Limit': handle_set_limit(message)
    elif cmd == '💎 Plans': handle_premium_plan_management(message)
    elif cmd == '⚙️ Settings': handle_settings(message)
    elif cmd == '🔗 Force Join': handle_force_join_management(message)
    elif cmd == '🚫 Ban':
        msg = bot.send_message(message.chat.id, "🚫 Enter user ID to ban:")
        bot.register_next_step_handler(msg, process_ban_user)
    elif cmd == '✅ Unban':
        msg = bot.send_message(message.chat.id, "✅ Enter user ID to unban:")
        bot.register_next_step_handler(msg, process_unban_user)
    elif cmd == '🛡️ Security Logs': handle_security_logs(message)

def handle_owner_command(message, cmd):
    if cmd == '➕ Add Admin':
        msg = bot.send_message(message.chat.id, "👤 Enter user ID to add as admin:")
        bot.register_next_step_handler(msg, process_add_admin)
    elif cmd == '➖ Remove Admin':
        msg = bot.send_message(message.chat.id, "👤 Enter user ID to remove from admin:")
        bot.register_next_step_handler(msg, process_remove_admin)

# ---- Admin action implementations (keep as before but with UI polish) ----
def process_add_admin(message):
    try:
        new_id = int(message.text.strip())
        if new_id in admin_ids:
            bot.send_message(message.chat.id, "⚠️ Already admin."); return
        admin_ids.add(new_id)
        conn.execute("INSERT OR IGNORE INTO admins(user_id) VALUES(?)", (new_id,))
        conn.commit()
        bot.send_message(message.chat.id, f"✅ Admin <code>{new_id}</code> added.", parse_mode='HTML')
    except Exception:
        bot.send_message(message.chat.id, "❌ Invalid ID.")

def process_remove_admin(message):
    try:
        aid = int(message.text.strip())
        if aid == OWNER_ID:
            bot.send_message(message.chat.id, "❌ Cannot remove owner."); return
        if aid not in admin_ids:
            bot.send_message(message.chat.id, "⚠️ Not an admin."); return
        admin_ids.discard(aid)
        conn.execute("DELETE FROM admins WHERE user_id=?", (aid,))
        conn.commit()
        bot.send_message(message.chat.id, f"✅ Admin <code>{aid}</code> removed.", parse_mode='HTML')
    except Exception:
        bot.send_message(message.chat.id, "❌ Invalid ID.")

def process_ban_user(message):
    try:
        target = int(message.text.strip())
        success, msg = ban_user(target)
        bot.send_message(message.chat.id, msg, parse_mode='HTML')
    except Exception:
        bot.send_message(message.chat.id, "❌ Invalid ID.")

def process_unban_user(message):
    try:
        target = int(message.text.strip())
        success, msg = unban_user(target)
        bot.send_message(message.chat.id, msg, parse_mode='HTML')
    except Exception:
        bot.send_message(message.chat.id, "❌ Invalid ID.")

def handle_generate_key(message):
    msg = bot.send_message(message.chat.id, "📅 Days (-1 = lifetime, 1-365):")
    bot.register_next_step_handler(msg, process_key_days)

def process_key_days(message):
    try:
        days = int(message.text.strip())
        if days < -1 or days > 365:
            bot.send_message(message.chat.id, "❌ Invalid."); return
        msg = bot.send_message(message.chat.id, "📁 File limit (0 = unlimited):")
        bot.register_next_step_handler(msg, process_key_file_limit, days)
    except Exception:
        bot.send_message(message.chat.id, "❌ Number required.")

def process_key_file_limit(message, days):
    try:
        val = message.text.strip()
        file_limit = 0 if val.lower() in ('unlimited','∞','0') else int(val)
        if file_limit < 0:
            bot.send_message(message.chat.id, "❌ Invalid."); return
        key = generate_subscription_key(days, file_limit)
        ld  = "∞" if file_limit == 0 else str(file_limit)
        dd  = "Lifetime" if days == -1 else f"{days} days"
        bot.send_message(message.chat.id,
                         f"✅ Key generated:\n🔑 <code>{key}</code>\n📅 {dd}\n📁 {ld} files",
                         parse_mode='HTML')
    except Exception:
        bot.send_message(message.chat.id, "❌ Number required.")

def handle_delete_key(message):
    keys = get_all_subscription_keys()
    if not keys:
        bot.send_message(message.chat.id, "📭 No keys."); return
    text = "🗑️ <b>Existing Keys:</b>\n\n"
    for k in keys:
        ld = "∞" if k['file_limit']==0 else str(k['file_limit'])
        dd = "Lifetime" if k['days_valid']==-1 else f"{k['days_valid']}d"
        text += f"• <code>{k['key_value']}</code> — {dd}, used {k['used_count']}/{k['max_uses']}, file:{ld}\n"
    text += "\nEnter key to delete:"
    bot.send_message(message.chat.id, text, parse_mode='HTML')
    msg = bot.send_message(message.chat.id, "🔑 Key:")
    bot.register_next_step_handler(msg, process_delete_key)

def process_delete_key(message):
    key = re.sub(r'[^A-Z0-9\-]', '', message.text.strip().upper())
    delete_subscription_key(key)
    bot.send_message(message.chat.id, f"✅ Deleted <code>{key}</code>", parse_mode='HTML')

def handle_list_keys(message):
    keys = get_all_subscription_keys()
    if not keys:
        bot.send_message(message.chat.id, "📭 No keys."); return
    text = "🔢 <b>All Keys:</b>\n\n"
    for k in keys:
        ld = "∞" if k['file_limit']==0 else str(k['file_limit'])
        dd = "Lifetime" if k['days_valid']==-1 else f"{k['days_valid']}d"
        text += f"• <code>{k['key_value']}</code> — {dd}, {k['used_count']}/{k['max_uses']}, file:{ld}\n"
    bot.send_message(message.chat.id, text, parse_mode='HTML')

def handle_set_limit(message):
    msg = bot.send_message(message.chat.id, f"📈 Current free limit: {FREE_USER_LIMIT}\nNew limit (1-100):")
    bot.register_next_step_handler(msg, process_set_limit)

def process_set_limit(message):
    try:
        n = int(message.text.strip())
        if 1 <= n <= 100:
            update_file_limit(n)
            bot.send_message(message.chat.id, f"✅ Free limit set to {n}")
        else:
            bot.send_message(message.chat.id, "❌ 1-100 only.")
    except Exception:
        bot.send_message(message.chat.id, "❌ Number required.")

def handle_settings(message):
    sys_stats = get_system_stats()
    text = (
        f"⚙️ <b>Settings</b>\n\n"
        f"🔒 Bot: {'🔒 Locked' if bot_locked else '🔓 Unlocked'}\n"
        f"🔰 Force Join: {'✅ On' if force_join_enabled else '❌ Off'}\n"
        f"📁 Free Limit: {FREE_USER_LIMIT}\n"
        f"🖥 CPU: {sys_stats['cpu']}%\n"
        f"💾 RAM: {sys_stats['ram_percent']}% ({sys_stats['ram_used']}/{sys_stats['ram_total']} MB)\n\n"
        f"🐍 Python: <code>{PYTHON_CMD}</code>\n"
        f"🟩 Node: <code>{NODE_CMD}</code>"
    )
    markup = types.InlineKeyboardMarkup()
    if message.from_user.id == OWNER_ID:
        markup.add(types.InlineKeyboardButton("🔒 Lock" if not bot_locked else "🔓 Unlock",
                                              callback_data='lock_bot' if not bot_locked else 'unlock_bot'))
        markup.add(types.InlineKeyboardButton("❌ Disable FJ" if force_join_enabled else "✅ Enable FJ",
                                              callback_data='disable_force_join' if force_join_enabled else 'enable_force_join'))
        markup.add(types.InlineKeyboardButton("🐍 Set Python", callback_data='set_python_cmd'),
                   types.InlineKeyboardButton("🟩 Set Node", callback_data='set_node_cmd'))
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode='HTML')

def handle_force_join_management(message):
    if message.from_user.id not in admin_ids: return
    current = ", ".join(map(str, force_channel_ids)) or "none"
    info = (f"🔗 <b>Force Join Management</b>\n"
            f"📣 Channels: <code>{current}</code>\n"
            f"👥 Group: <code>{force_group_id}</code>\n\n"
            f"Enter channel IDs (comma separated):")
    msg = bot.send_message(message.chat.id, info, parse_mode='HTML')
    bot.register_next_step_handler(msg, process_force_join_channels)

def process_force_join_channels(message):
    try:
        ids = [int(x.strip()) for x in message.text.split(',') if x.strip().lstrip('-').isdigit()]
        if not ids:
            bot.send_message(message.chat.id, "❌ No valid IDs."); return
        msg = bot.send_message(message.chat.id, "👥 Group ID (0 for none):")
        bot.register_next_step_handler(msg, process_force_join_group, ids)
    except Exception:
        bot.send_message(message.chat.id, "❌ Invalid input.")

def process_force_join_group(message, channel_ids):
    try:
        gid = int(message.text.strip())
        global force_channel_ids, force_group_id
        force_channel_ids = channel_ids; force_group_id = gid
        conn.execute("INSERT OR REPLACE INTO bot_settings(setting_key,setting_value) VALUES('force_channel_ids',?)",
                     (','.join(map(str, force_channel_ids)),))
        conn.execute("INSERT OR REPLACE INTO bot_settings(setting_key,setting_value) VALUES('force_group_id',?)",
                     (str(force_group_id),))
        conn.commit()
        # Optionally let admin set invite links now
        bot.send_message(message.chat.id,
            f"✅ Force Join updated.\n\nNow set invite links for each:\n"
            f"Use /setlink chat_id link  (e.g., /setlink -100123456 https://t.me/...)")
    except Exception:
        bot.send_message(message.chat.id, "❌ Invalid group ID.")

# Command to set custom invite link
@bot.message_handler(commands=['setlink'])
@secure_handler()
def cmd_setlink(message):
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, "❌ Admin only."); return
    parts = message.text.split()
    if len(parts) != 3:
        bot.reply_to(message, "Usage: /setlink chat_id link"); return
    try:
        chat_id = int(parts[1])
        link = parts[2].strip()
        save_custom_invite_link(chat_id, link)
        bot.reply_to(message, f"✅ Invite link for {chat_id} saved.")
    except Exception:
        bot.reply_to(message, "❌ Invalid chat_id.")

# Set python / node commands
@bot.callback_query_handler(func=lambda c: c.data in ('set_python_cmd','set_node_cmd'))
def callback_set_interpreter(call):
    if call.from_user.id != OWNER_ID:
        safe_answer_callback(call, "❌ Owner only", show_alert=True); return
    if call.data == 'set_python_cmd':
        msg = bot.send_message(call.message.chat.id, "Enter Python command (e.g., python2, /usr/bin/python3.10):")
        bot.register_next_step_handler(msg, process_set_python)
    else:
        msg = bot.send_message(call.message.chat.id, "Enter Node command (e.g., node, /usr/local/bin/node):")
        bot.register_next_step_handler(msg, process_set_node)

def process_set_python(message):
    global PYTHON_CMD
    cmd = message.text.strip()
    if shutil.which(cmd) or os.path.exists(cmd):
        PYTHON_CMD = cmd
        conn.execute("INSERT OR REPLACE INTO bot_settings VALUES('python_cmd',?)", (cmd,))
        conn.commit()
        bot.send_message(message.chat.id, f"✅ Python interpreter set to <code>{cmd}</code>", parse_mode='HTML')
    else:
        bot.send_message(message.chat.id, "❌ Command not found.")

def process_set_node(message):
    global NODE_CMD
    cmd = message.text.strip()
    if shutil.which(cmd) or os.path.exists(cmd):
        NODE_CMD = cmd
        conn.execute("INSERT OR REPLACE INTO bot_settings VALUES('node_cmd',?)", (cmd,))
        conn.commit()
        bot.send_message(message.chat.id, f"✅ Node interpreter set to <code>{cmd}</code>", parse_mode='HTML')
    else:
        bot.send_message(message.chat.id, "❌ Command not found.")

# ... (rest of handlers: stats, all_users, premium_users, running, broadcast, upgrade, my_info, status, manage_files, callback handlers remain similar with UI enhancements)

def handle_stats(message):
    stats     = get_bot_statistics()
    sys_stats = get_system_stats()
    text = (
        f"╔══════════════════════╗\n"
        f"║   📊 SYSTEM STATS     ║\n"
        f"╚══════════════════════╝\n\n"
        f"👥 Users: <code>{stats['total_users']}</code>\n"
        f"✨ Premium: <code>{stats['premium_users']}</code>\n"
        f"🚫 Banned: <code>{len(banned_users)}</code>\n"
        f"📁 Total files: <code>{stats['total_files']}</code>\n"
        f"🟢 Active: <code>{stats['active_files']}</code>\n\n"
        f"🖥 CPU: {sys_stats['cpu']}%\n"
        f"💾 RAM: {sys_stats['ram_used']}/{sys_stats['ram_total']} MB ({sys_stats['ram_percent']}%)\n"
        f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    bot.send_message(message.chat.id, text, parse_mode='HTML')

def get_bot_statistics():
    total_users = len(active_users)
    total_files = sum(len(f) for f in user_files.values())
    with bot_scripts_lock:
        active_files = len(bot_scripts)
    premium_users = sum(1 for uid in active_users if is_premium_user(uid))
    return {'total_users': total_users, 'total_files': total_files,
            'active_files': active_files, 'premium_users': premium_users}

def handle_all_users(message):
    c = conn.cursor()
    c.execute("SELECT user_id,username,first_name,banned FROM users LIMIT 50")
    rows = c.fetchall()
    if not rows:
        bot.send_message(message.chat.id, "📭 No users."); return
    text = "👥 <b>Recent Users:</b>\n\n"
    for row in rows:
        uid, uname, fname, banned = row
        status = "✨" if is_premium_user(uid) else "🎯"
        ban    = " [🚫]" if banned else ""
        text  += f"• {status} {html_module.escape(fname or 'Unknown')} (@{uname or '-'}){ban}\n"
    bot.send_message(message.chat.id, text, parse_mode='HTML')

def handle_premium_users(message):
    prems = [(uid, s) for uid, s in user_subscriptions.items() if s['expiry'] > datetime.now()]
    if not prems:
        bot.send_message(message.chat.id, "📭 No premium users."); return
    text = "✨ <b>Premium Users:</b>\n\n"
    for uid, sub in prems[:30]:
        c = conn.cursor()
        c.execute("SELECT username,first_name FROM users WHERE user_id=?", (uid,))
        row = c.fetchone()
        name = (row[1] or 'Unknown') if row else str(uid)
        uname = f"@{row[0]}" if row and row[0] else '-'
        exp  = sub['expiry'].strftime('%Y-%m-%d')
        fd   = "∞" if sub['file_limit']==0 else str(sub['file_limit'])
        text += f"• {html_module.escape(name)} ({uname}) — {exp} | file:{fd}\n"
    bot.send_message(message.chat.id, text, parse_mode='HTML')

def handle_running_scripts(message):
    with bot_scripts_lock:
        sc = dict(bot_scripts)
    if not sc:
        bot.send_message(message.chat.id, "🔄 No running scripts."); return
    text = "🔄 <b>Running Scripts:</b>\n\n"
    for key, info in sc.items():
        uid  = info['script_owner_id']; fname = info['file_name']
        pid  = info['process'].pid if info.get('process') else '?'
        icon = '🐍' if info.get('type')=='py' else '🟨'
        try:
            p    = psutil.Process(pid)
            mem  = round(p.memory_info().rss / 1024 / 1024, 1)
            cpu  = p.cpu_percent(interval=0.1)
            res  = f"RAM:{mem}MB CPU:{cpu}%"
        except Exception:
            res = "stats N/A"
        text += f"• {icon} <code>{html_module.escape(fname)}</code> (uid:{uid} PID:{pid} {res})\n"
    bot.send_message(message.chat.id, text, parse_mode='HTML')

def process_broadcast(message):
    bcast = message.text
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Send", callback_data=f'confirm_broadcast_{message.message_id}'),
               types.InlineKeyboardButton("❌ Cancel", callback_data='cancel_broadcast'))
    broadcast_messages[message.message_id] = bcast
    bot.send_message(message.chat.id, f"📢 <b>Preview:</b>\n\n{bcast}\n\nSend?",
                     reply_markup=markup, parse_mode='HTML')

def handle_confirm_broadcast(call):
    if call.from_user.id not in admin_ids:
        safe_answer_callback(call, "❌ Admin only", show_alert=True); return
    try:
        msg_id = int(call.data.split('_')[-1])
        text   = broadcast_messages.get(msg_id, "")
        if not text: safe_answer_callback(call, "❌ Message not found"); return
        sent = failed = 0
        for uid in list(active_users):
            if is_user_banned(uid): continue
            try:
                bot.send_message(uid, text, parse_mode='HTML')
                sent += 1
                time.sleep(0.05)
            except Exception:
                failed += 1
        safe_answer_callback(call, f"✅ {sent} sent, ❌ {failed} failed")
        try: bot.edit_message_text(f"📢 Broadcast done\n✅ {sent} | ❌ {failed}",
                                   call.message.chat.id, call.message.message_id)
        except Exception: pass
        broadcast_messages.pop(msg_id, None)
    except Exception as e:
        safe_answer_callback(call, f"❌ {e}")

def handle_upgrade(message):
    plans = get_all_premium_plans()
    if not plans:
        bot.send_message(message.chat.id, "💎 No plans yet. Contact admin."); return
    text = "💎 <b>Premium Plans</b>\n\n"
    for p in plans:
        dd = "Lifetime" if p['days']==-1 else f"{p['days']}d"
        fd = "∞" if p['file_limit']==0 else p['file_limit']
        text += f"• <b>{p['name']}</b>: {p['price']}Ks | {dd} | File:{fd}\n"
    text += f"\n💳 Payment: {ADMIN_USERNAME}"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💳 Contact", url=f"https://t.me/{ADMIN_USERNAME.lstrip('@')}"))
    markup.add(types.InlineKeyboardButton("🔑 I have a key", callback_data='redeem_key'))
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode='HTML')

def handle_my_info(message):
    user_id = message.from_user.id
    fc = get_user_file_count(user_id)
    fl = get_user_file_limit(user_id)
    ls = "∞" if fl == float('inf') else str(int(fl))
    running = sum(1 for fn,_,_ in user_files.get(user_id,[]) if is_bot_running(user_id, fn))
    sub = user_subscriptions.get(user_id)
    exp_str = ""
    if sub and sub['expiry'] > datetime.now():
        exp_str = f"\n⏳ Expires: {sub['expiry'].strftime('%Y-%m-%d')}"
    sys_stats = get_system_stats()
    text = (
        f"╔══════════════════════╗\n"
        f"║   👤 YOUR PROFILE     ║\n"
        f"╚══════════════════════╝\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"👤 Name: {html_module.escape(message.from_user.first_name)}\n"
        f"📊 Status: {get_user_status(user_id)}{exp_str}\n\n"
        f"📁 Files: {fc}/{ls}\n"
        f"🟢 Running: {running}\n"
        f"🔴 Stopped: {fc - running}\n\n"
        f"🖥 CPU:{sys_stats['cpu']}% RAM:{sys_stats['ram_percent']}%"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📁 My Files", callback_data='manage_files'))
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode='HTML')

def handle_status(message):
    handle_my_info(message)

def handle_manage_files(message):
    user_id = message.from_user.id
    files   = user_files.get(user_id, [])
    if not files:
        bot.send_message(message.chat.id, "📭 No files."); return
    text = "📁 <b>Your Files:</b>\n\n"
    for fn, ft, fp in files:
        status = "🟢" if is_bot_running(user_id, fn) else "🔴"
        text  += f"{status} <code>{html_module.escape(fn)}</code>\n"
    markup = create_manage_files_keyboard(user_id)
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode='HTML')

def process_redeem_key(message):
    user_id = message.from_user.id
    key     = re.sub(r'[^A-Z0-9\-]', '', message.text.strip().upper())
    if not key.startswith('DEVRAW-'):
        bot.reply_to(message, "❌ Format: <code>DEVRAW-XXXXXXXXXXXX</code>", parse_mode='HTML'); return
    success, msg = redeem_subscription_key(key, user_id)
    bot.reply_to(message, msg, parse_mode='HTML')

# ================================================================
#   CALLBACK HANDLER
# ================================================================
def parse_callback_data(data, prefix):
    try:
        rest = data[len(prefix):]
        idx  = rest.index('_')
        return int(rest[:idx]), rest[idx+1:]
    except Exception:
        return None, None

@bot.callback_query_handler(func=lambda c: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    if is_user_banned(user_id):
        safe_answer_callback(call, "🚫 Banned", show_alert=True); return
    if not rate_limiter.is_allowed(user_id):
        safe_answer_callback(call, "⚠️ Slow down", show_alert=True)
        auto_ban_check(user_id); return

    data = call.data

    if data == 'check_membership':
        ok, msg = verify_membership(user_id)
        if ok:
            safe_answer_callback(call, "✅ Verified!")
            show_main_menu(call.message, user_id)
        else:
            safe_answer_callback(call, msg, show_alert=True)
    elif data == 'manage_files':   handle_manage_files_callback(call)
    elif data == 'back_to_main':   show_main_menu(call.message, user_id)
    elif data == 'no_link':
        safe_answer_callback(call, "⚠️ No invite link available. Please ask admin.", show_alert=True)
    elif data.startswith('file_'): handle_file_click(call)
    elif data.startswith('start_'): handle_start_file(call)
    elif data.startswith('stop_'):  handle_stop_file(call)
    elif data.startswith('restart_'): handle_restart_file(call)
    elif data.startswith('delete_'): handle_delete_file_callback(call)
    elif data.startswith('logs_'):  handle_logs_callback(call)
    elif data.startswith('download_'): handle_download_callback(call)
    elif data == 'redeem_key':
        msg = bot.send_message(call.message.chat.id, "🔑 Enter key:")
        bot.register_next_step_handler(msg, process_redeem_key)
    elif data.startswith('confirm_broadcast_'): handle_confirm_broadcast(call)
    elif data == 'cancel_broadcast':
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception: pass
        safe_answer_callback(call, "Cancelled")
    elif data == 'lock_bot' and user_id == OWNER_ID:
        global bot_locked
        bot_locked = True
        safe_answer_callback(call, "🔒 Locked")
        handle_settings(call.message)
    elif data == 'unlock_bot' and user_id == OWNER_ID:
        bot_locked = False
        safe_answer_callback(call, "🔓 Unlocked")
        handle_settings(call.message)
    elif data == 'enable_force_join' and user_id == OWNER_ID:
        update_force_join_status(True)
        safe_answer_callback(call, "✅ Force Join enabled")
        handle_settings(call.message)
    elif data == 'disable_force_join' and user_id == OWNER_ID:
        update_force_join_status(False)
        safe_answer_callback(call, "❌ Force Join disabled")
        handle_settings(call.message)
    elif data in ('set_python_cmd','set_node_cmd'):
        pass  # handled by separate callback handler above
    elif data == 'add_premium_plan':
        if call.from_user.id not in admin_ids: safe_answer_callback(call, "❌"); return
        msg = bot.send_message(call.message.chat.id, "💎 Plan name:")
        bot.register_next_step_handler(msg, process_plan_name)
    elif data == 'delete_premium_plan':
        if call.from_user.id not in admin_ids: safe_answer_callback(call, "❌"); return
        plans = get_all_premium_plans()
        if not plans:
            safe_answer_callback(call, "No plans", show_alert=True); return
        pl = "\n".join(f"ID:{p['id']} {p['name']}" for p in plans)
        msg = bot.send_message(call.message.chat.id, f"💎 Plans:\n{pl}\n\nEnter ID to delete:")
        bot.register_next_step_handler(msg, process_delete_plan_id)

def handle_manage_files_callback(call):
    user_id = call.from_user.id
    if not check_force_join_and_access(user_id):
        safe_answer_callback(call, "⛔ Access denied", show_alert=True); return
    files = user_files.get(user_id, [])
    if not files:
        safe_answer_callback(call, "📭 No files", show_alert=True); return
    text = "📁 <b>Your Files:</b>\n\n"
    for fn, ft, fp in files:
        status = "🟢" if is_bot_running(user_id, fn) else "🔴"
        text  += f"{status} <code>{html_module.escape(fn)}</code>\n"
    markup = create_manage_files_keyboard(user_id)
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='HTML')
    except Exception:
        bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode='HTML')

def handle_file_click(call):
    try:
        target_id, file_name = parse_callback_data(call.data, 'file_')
        if target_id is None: safe_answer_callback(call, "❌ Bad data", show_alert=True); return
        if call.from_user.id != target_id and call.from_user.id not in admin_ids:
            log_security_event(call.from_user.id, "UNAUTHORIZED_FILE_ACCESS", f"target={target_id} file={file_name}")
            safe_answer_callback(call, "❌ Denied", show_alert=True); return
        is_running = is_bot_running(target_id, file_name)
        icon = "🐍" if file_name.endswith('.py') else "🟨"
        text = f"{icon} <b>{html_module.escape(file_name)}</b>\n\n📊 {'🟢 Running' if is_running else '🔴 Stopped'}"
        markup = create_file_management_buttons(target_id, file_name, is_running)
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='HTML')
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode='HTML')
    except Exception as e:
        safe_answer_callback(call, f"❌ {e}")

def handle_start_file(call):
    try:
        user_id, file_name = parse_callback_data(call.data, 'start_')
        if user_id is None: safe_answer_callback(call, "❌", show_alert=True); return
        if call.from_user.id != user_id and call.from_user.id not in admin_ids:
            safe_answer_callback(call, "❌", show_alert=True); return
        file_path = next((fp for fn,ft,fp in user_files.get(user_id,[]) if fn==file_name), None)
        if not file_path or not os.path.exists(file_path) or not is_safe_path(UPLOAD_BOTS_DIR, file_path):
            safe_answer_callback(call, "❌ File not found", show_alert=True); return
        ufolder = get_user_folder(user_id)
        ext = os.path.splitext(file_name)[1].lower()
        runner = run_python_script if ext == '.py' else run_js_script
        threading.Thread(target=runner, args=(file_path, user_id, ufolder, file_name, call.message)).start()
        safe_answer_callback(call, "🚀 Starting...")
        time.sleep(4)
        call.data = f'file_{user_id}_{file_name}'
        handle_file_click(call)
    except Exception as e:
        safe_answer_callback(call, f"❌ {e}")

def handle_stop_file(call):
    try:
        user_id, file_name = parse_callback_data(call.data, 'stop_')
        if user_id is None: safe_answer_callback(call, "❌", show_alert=True); return
        key = f"{user_id}_{file_name}"
        with bot_scripts_lock:
            info = bot_scripts.get(key)
        if info: kill_process_tree(info)
        with bot_scripts_lock:
            bot_scripts.pop(key, None)
        safe_answer_callback(call, "⏸️ Stopped")
        time.sleep(1)
        call.data = f'file_{user_id}_{file_name}'
        handle_file_click(call)
    except Exception as e:
        safe_answer_callback(call, f"❌ {e}")

def handle_restart_file(call):
    try:
        user_id, file_name = parse_callback_data(call.data, 'restart_')
        if user_id is None: safe_answer_callback(call, "❌", show_alert=True); return
        key = f"{user_id}_{file_name}"
        with bot_scripts_lock:
            info = bot_scripts.get(key)
        if info: kill_process_tree(info)
        with bot_scripts_lock:
            bot_scripts.pop(key, None)
        time.sleep(1)
        fp = next((p for n,t,p in user_files.get(user_id,[]) if n==file_name), None)
        if fp and os.path.exists(fp) and is_safe_path(UPLOAD_BOTS_DIR, fp):
            ufolder = get_user_folder(user_id)
            ext     = os.path.splitext(file_name)[1].lower()
            runner  = run_python_script if ext=='.py' else run_js_script
            threading.Thread(target=runner, args=(fp, user_id, ufolder, file_name, call.message)).start()
            safe_answer_callback(call, "🔄 Restarting...")
        else:
            safe_answer_callback(call, "❌ File not found", show_alert=True)
        time.sleep(4)
        call.data = f'file_{user_id}_{file_name}'
        handle_file_click(call)
    except Exception as e:
        safe_answer_callback(call, f"❌ {e}")

def handle_delete_file_callback(call):
    try:
        user_id, file_name = parse_callback_data(call.data, 'delete_')
        if user_id is None: safe_answer_callback(call, "❌", show_alert=True); return
        if call.from_user.id != user_id and call.from_user.id not in admin_ids:
            safe_answer_callback(call, "❌ Denied", show_alert=True); return
        key = f"{user_id}_{file_name}"
        with bot_scripts_lock:
            info = bot_scripts.get(key)
        if info: kill_process_tree(info)
        with bot_scripts_lock:
            bot_scripts.pop(key, None)
        fp = next((p for n,t,p in user_files.get(user_id,[]) if n==file_name), None)
        if fp and os.path.exists(fp) and is_safe_path(UPLOAD_BOTS_DIR, fp):
            os.remove(fp)
        remove_user_file_db(user_id, file_name)
        safe_answer_callback(call, "🗑️ Deleted")
        handle_manage_files_callback(call)
    except Exception as e:
        safe_answer_callback(call, f"❌ {e}")

def handle_logs_callback(call):
    try:
        user_id, file_name = parse_callback_data(call.data, 'logs_')
        if user_id is None: safe_answer_callback(call, "❌", show_alert=True); return
        if call.from_user.id != user_id and call.from_user.id not in admin_ids:
            safe_answer_callback(call, "❌ Denied", show_alert=True); return
        if send_log_file(user_id, file_name, call.message.chat.id):
            safe_answer_callback(call, "📋 Log sent")
        else:
            safe_answer_callback(call, "📭 No log", show_alert=True)
    except Exception as e:
        safe_answer_callback(call, f"❌ {e}")

def handle_download_callback(call):
    try:
        user_id, file_name = parse_callback_data(call.data, 'download_')
        if user_id is None: safe_answer_callback(call, "❌", show_alert=True); return
        if call.from_user.id != user_id and call.from_user.id not in admin_ids:
            log_security_event(call.from_user.id, "UNAUTHORIZED_DOWNLOAD", f"target={user_id} file={file_name}")
            safe_answer_callback(call, "❌ Denied", show_alert=True); return
        fp = next((p for n,t,p in user_files.get(user_id,[]) if n==file_name), None)
        if not fp or not os.path.exists(fp) or not is_safe_path(UPLOAD_BOTS_DIR, fp):
            safe_answer_callback(call, "❌ File not found", show_alert=True); return
        with open(fp, 'rb') as f:
            bot.send_document(call.message.chat.id, f, caption=f"📥 {html_module.escape(file_name)}")
        safe_answer_callback(call, "📥 Sent")
    except Exception as e:
        safe_answer_callback(call, f"❌ {e}")

# ================================================================
#   PROCESS MONITOR
# ================================================================
def _monitor_processes():
    while True:
        try:
            time.sleep(60)
            with bot_scripts_lock:
                dead = []
                for key, info in bot_scripts.items():
                    proc = info.get('process')
                    if not proc:
                        dead.append(key); continue
                    try:
                        p = psutil.Process(proc.pid)
                        if not p.is_running() or p.status() == psutil.STATUS_ZOMBIE:
                            dead.append(key); continue
                        mem_mb = p.memory_info().rss / 1024 / 1024
                        if mem_mb > PROC_MAX_MEMORY_MB * 1.5:
                            uid = info.get('script_owner_id')
                            logger.warning(f"Memory abuse uid={uid} key={key} mem={mem_mb:.0f}MB — killing")
                            log_security_event(uid or 0, "MEMORY_ABUSE", f"mem={mem_mb:.0f}MB file={info.get('file_name')}")
                            kill_process_tree(info)
                            dead.append(key)
                    except psutil.NoSuchProcess:
                        dead.append(key)
                for k in dead:
                    bot_scripts.pop(k, None)
        except Exception as e:
            logger.error(f"Monitor error: {e}")

# ================================================================
#   CLEANUP
# ================================================================
def cleanup():
    logger.warning("🛑 Shutting down — cleaning up...")
    with bot_scripts_lock:
        for info in list(bot_scripts.values()):
            kill_process_tree(info)
        bot_scripts.clear()
    if conn:
        conn.close()
    logger.info("✅ Cleanup complete.")

atexit.register(cleanup)

# ================================================================
#   MAIN
# ================================================================
if __name__ == '__main__':
    logger.info("🚀 DEV-RAW Core v2.5 (Ultimate Edition) starting...")
    init_db()
    load_data()
    keep_alive()
    node_ok = install_nodejs()
    if not node_ok:
        logger.warning("⚠️ Node.js not available — JS disabled.")
    # Pre-fetch invite links (will use custom or generate)
    for ch in force_channel_ids:
        get_invite_link(ch)
    if force_group_id:
        get_invite_link(force_group_id)
    threading.Thread(target=_monitor_processes, daemon=True).start()
    logger.info("✅ Bot ready.")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=30, allowed_updates=['message','callback_query'])
        except Exception as e:
            logger.error(f"Polling error: {e}", exc_info=True)
            time.sleep(5)
