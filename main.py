#!/usr/bin/env python3
# ================================================================
#   DEV-RAW CORE BOT v2.0 — SECURITY HARDENED EDITION
#   Upgraded by DEV-RAW Panel | Production-Ready
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
import resource
import signal
from datetime import datetime, timedelta
from threading import Thread
from collections import defaultdict, deque

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
                                   "--break-system-packages"], check=True)

import psutil
import telebot
from telebot import types
import requests
from flask import Flask, request as flask_request, abort

# ================================================================
#   SECURITY CONFIGURATION
# ================================================================

# Rate limiting: max messages per user per window
RATE_LIMIT_MESSAGES  = 15     # max 15 messages
RATE_LIMIT_WINDOW    = 60     # per 60 seconds
RATE_LIMIT_FILE_MSGS = 3      # max 3 file uploads
RATE_LIMIT_FILE_WIN  = 60     # per 60 seconds
FLOOD_AUTO_BAN_THRESHOLD = 40 # auto-ban after N violations in window

# File security
MAX_FILE_SIZE_MB     = 5      # max upload size in MB
ALLOWED_EXTENSIONS   = {'.py', '.js'}
BLOCKED_CONTENT_PATTERNS = [  # regex patterns to reject in uploaded files
    r'os\.system\s*\(',
    r'subprocess\.call\s*\([^)]*shell\s*=\s*True',
    r'eval\s*\(.*input',
    r'exec\s*\(.*input',
    r'__import__\s*\(["\']os["\']\)',
    r'open\s*\(["\']\/etc\/',
    r'open\s*\(["\']\/proc\/',
    r'chmod\s*\(["\']\/etc',
]

# Process resource limits (soft limits per user process)
PROC_MAX_MEMORY_MB   = 256    # 256 MB RAM per child process
PROC_MAX_CPU_SECONDS = 3600   # 1 hour CPU time
PROC_MAX_OPEN_FILES  = 100    # max file descriptors

# Auto-ban suspicious patterns
SUSPICIOUS_CMD_PATTERNS = [
    r'^\/?(passwd|shadow|hosts|cron)',
    r'\.\.\/',        # directory traversal
    r'rm\s+-rf',
    r'chmod\s+777',
    r'curl\s+.*\|\s*sh',
    r'wget\s+.*\|\s*sh',
]

# ================================================================
#   FLASK KEEP-ALIVE (hardened)
# ================================================================
_flask_app = Flask('')

@_flask_app.before_request
def _flask_security():
    # Block non-GET methods on keep-alive endpoint
    if flask_request.endpoint == 'home' and flask_request.method != 'GET':
        abort(405)

@_flask_app.route('/')
def home():
    return "⚡ DEV-RAW Core v2.0 — Secure Edition", 200

def _run_flask():
    port = int(os.environ.get("PORT", os.environ.get("BOT_PORT", 5000)))
    _flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def keep_alive():
    t = Thread(target=_run_flask)
    t.daemon = True
    t.start()
    print("🟣 Flask Keep-Alive started (hardened).")

# ================================================================
#   BOT CONFIGURATION (env-first, fallback for dev only)
# ================================================================
TOKEN          = os.environ.get("BOT_TOKEN")
OWNER_ID       = int(os.environ.get("OWNER_ID", 0))
ADMIN_ID       = int(os.environ.get("ADMIN_ID",  OWNER_ID))
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", '@admin')

if not TOKEN:
    print("❌ BOT_TOKEN environment variable not set. Exiting.")
    sys.exit(1)
if OWNER_ID == 0:
    print("⚠️ OWNER_ID not set via env — defaulting to 0 (owner checks may fail).")

DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'devraw_bot.db')

DEFAULT_FORCE_CHANNEL_IDS = []
DEFAULT_FORCE_GROUP_ID    = 0
DEFAULT_CHANNEL_LINKS     = {}
DEFAULT_GROUP_LINK        = ""

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
#   LOGGING (structured, rotating)
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
bot_scripts         = {}        # script_key -> process info
bot_scripts_lock    = threading.Lock()
user_subscriptions  = {}        # user_id -> {'expiry': datetime, 'file_limit': int}
user_files          = {}        # user_id -> list of (file_name, file_type, file_path)
active_users        = set()
admin_ids           = set()
banned_users        = set()
bot_locked          = False
broadcast_messages  = {}
force_join_enabled  = True
FREE_USER_LIMIT     = 1
force_channel_ids   = list(DEFAULT_FORCE_CHANNEL_IDS)
force_group_id      = DEFAULT_FORCE_GROUP_ID
invite_links        = {}
conn                = None

# ================================================================
#   RATE LIMITER
# ================================================================
class RateLimiter:
    """Thread-safe per-user rate limiter with auto-ban escalation."""
    def __init__(self):
        self._lock      = threading.Lock()
        self._windows   = defaultdict(lambda: deque())  # user_id -> deque of timestamps
        self._violations= defaultdict(int)              # user_id -> violation count
        self._file_wins = defaultdict(lambda: deque())  # for file uploads

    def is_allowed(self, user_id: int, is_file: bool = False) -> bool:
        if user_id in admin_ids:
            return True
        now = time.monotonic()
        limit = RATE_LIMIT_FILE_MSGS if is_file else RATE_LIMIT_MESSAGES
        window = RATE_LIMIT_FILE_WIN  if is_file else RATE_LIMIT_WINDOW
        q = self._file_wins[user_id] if is_file else self._windows[user_id]
        with self._lock:
            # Evict old timestamps
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                self._violations[user_id] += 1
                security_logger.warning(
                    f"RATE_LIMIT uid={user_id} violations={self._violations[user_id]}"
                )
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
        """)

        default_settings = {
            "free_user_limit":   str(FREE_USER_LIMIT),
            "force_join_enabled": "1",
            "force_channel_ids":  ",".join(map(str, DEFAULT_FORCE_CHANNEL_IDS)),
            "force_group_id":     str(DEFAULT_FORCE_GROUP_ID),
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
        logger.info("✅ Database initialised (WAL mode).")
    except Exception as e:
        logger.critical(f"❌ DB init failed: {e}", exc_info=True)
        sys.exit(1)

def load_data():
    global user_subscriptions, user_files, active_users, admin_ids, banned_users
    global FREE_USER_LIMIT, force_join_enabled, force_channel_ids, force_group_id
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
    """Remove all path separators and non-ASCII chars from filename."""
    name = os.path.basename(name)
    name = re.sub(r'[^\w.\-]', '_', name)
    name = name.lstrip('.')
    if not name:
        name = "uploaded_file"
    return name[:120]

def validate_file_content(file_bytes: bytes, ext: str) -> tuple[bool, str]:
    """Return (ok, reason). Scans file for dangerous patterns."""
    try:
        text = file_bytes.decode('utf-8', errors='replace')
    except Exception:
        return False, "ဖိုင် decode မဖတ်နိုင်"
    for pattern in BLOCKED_CONTENT_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return False, f"ကာကွယ်ထားသောကုဒ်ပါဝင်: `{pattern}`"
    return True, ""

def is_safe_path(base_dir: str, path: str) -> bool:
    """Prevent directory traversal: path must be under base_dir."""
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
    """Auto-ban users who exceed flood threshold."""
    if user_id in admin_ids:
        return
    violations = rate_limiter.violation_count(user_id)
    if violations >= FLOOD_AUTO_BAN_THRESHOLD and user_id not in banned_users:
        _ban_user_internal(user_id)
        log_security_event(user_id, "AUTO_BAN", f"violations={violations}")
        logger.warning(f"🚨 Auto-banned uid={user_id} (violations={violations})")
        try:
            bot.send_message(user_id, "🚫 Flood/Spam ကြောင့် Auto-Ban ခံရပါသည်။")
        except Exception:
            pass

# ================================================================
#   GATE DECORATOR — used on every handler
# ================================================================
def secure_handler(is_file_upload=False):
    """Decorator: ban check → rate limit → suspicious input → proceed."""
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
                        bot.send_message(message_or_call.chat.id,
                                         "🚫 Ban ခံထားရသောကြောင့် အသုံးပြု၍မရပါ။")
                except Exception:
                    pass
                return

            if not rate_limiter.is_allowed(user_id, is_file=is_file_upload):
                auto_ban_check(user_id)
                try:
                    if hasattr(message_or_call, 'chat'):
                        bot.send_message(message_or_call.chat.id,
                                         "⚠️ မြန်နှုန်းကန့်သတ်ချက်ကျော်လွန်သည်။ ခေတ္တစောင့်ပါ။")
                except Exception:
                    pass
                return

            if text and check_suspicious_input(text):
                log_security_event(user_id, "SUSPICIOUS_INPUT", text[:200])
                try:
                    if hasattr(message_or_call, 'chat'):
                        bot.send_message(message_or_call.chat.id,
                                         "⛔ ခွင့်မပြုသော command ပါဝင်သည်။")
                except Exception:
                    pass
                return

            return fn(message_or_call, *args, **kwargs)
        wrapper.__name__ = fn.__name__
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
        return False, "❌ Admin/ပိုင်ရှင်ကို ban မလုပ်နိုင်ပါ။"
    _ban_user_internal(user_id)
    log_security_event(user_id, "MANUAL_BAN")
    return True, f"✅ User <code>{user_id}</code> ban လိုက်ပါပြီ။"

def unban_user(user_id):
    if user_id not in banned_users:
        return False, "⚠️ ဤ user ban မခံထားရပါ။"
    conn.execute("UPDATE users SET banned=0 WHERE user_id=?", (user_id,))
    conn.commit()
    banned_users.discard(user_id)
    rate_limiter.reset(user_id)
    log_security_event(user_id, "MANUAL_UNBAN")
    return True, f"✅ User <code>{user_id}</code> unban ပြီးပါပြီ။"

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
    if user_id == OWNER_ID: return "👑 ပိုင်ရှင်"
    if user_id in admin_ids: return "🛡️ အယ်မင်း"
    if is_premium_user(user_id): return "✨ ပရိုမ်း"
    return "🎯 အခြေခံ"

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

def verify_membership(user_id):
    if user_id in admin_ids: return True
    try:
        for ch_id in force_channel_ids:
            m = bot.get_chat_member(ch_id, user_id)
            if m.status not in ('member', 'administrator', 'creator'):
                return False
        if force_group_id:
            gm = bot.get_chat_member(force_group_id, user_id)
            if gm.status not in ('member', 'administrator', 'creator'):
                return False
        if not is_user_verified(user_id):
            set_user_verified(user_id)
        return True
    except Exception as e:
        logger.error(f"Membership check error uid={user_id}: {e}")
    return False

# ================================================================
#   FORCE-JOIN UI
# ================================================================
def get_channel_name(chat_id):
    try:
        return f"<b>{bot.get_chat(chat_id).title}</b>"
    except Exception:
        return f"ID: {chat_id}"

def get_group_name(chat_id):
    try:
        return f"<b>{bot.get_chat(chat_id).title}</b>"
    except Exception:
        return f"ID: {chat_id}"

def get_or_create_invite_link(chat_id):
    if chat_id in invite_links:
        return invite_links[chat_id]
    try:
        link = bot.export_chat_invite_link(chat_id)
        invite_links[chat_id] = link
        return link
    except Exception:
        return DEFAULT_CHANNEL_LINKS.get(chat_id) or (DEFAULT_GROUP_LINK if chat_id == DEFAULT_FORCE_GROUP_ID else None)

def create_force_join_message():
    chs = [get_channel_name(cid) for cid in force_channel_ids[:3]]
    while len(chs) < 3:
        chs.append("❌")
    return f"""
╔══════════════════════════╗
║   🔐 <b>အဖွဲ့ဝင်ဖြစ်ရန် လိုအပ်</b>   ║
╚══════════════════════════╝

✨ <b>အောက်ပါချန်နယ်များနှင့် အုပ်စုသို့ ဝင်ပါ</b>

📣 <b>ချန်နယ်များ</b>
├─ {chs[0]}
├─ {chs[1]}
└─ {chs[2]}
👥 <b>အုပ်စု</b>
└─ {get_group_name(force_group_id) if force_group_id else '❌'}

📋 <b>လမ်းညွှန်:</b>
1️⃣ အောက်ပါခလုတ်များကို နှိပ်ပါ
2️⃣ စက္ကန့် 50 စောင့်ပါ
3️⃣ "✅ အဖွဲ့ဝင်စစ်ဆေးပါ" ကိုနှိပ်ပါ

🎁 <b>အကျိုးကျေးဇူး:</b> Python/JS scripts 24/7 run နိုင်သည်
    """

def create_force_join_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    for ch_id in force_channel_ids:
        link = get_or_create_invite_link(ch_id)
        btn_text = f"📣 {get_channel_name(ch_id)}"
        markup.add(types.InlineKeyboardButton(btn_text, url=link) if link
                   else types.InlineKeyboardButton(btn_text, callback_data='no_link'))
    if force_group_id:
        gl = get_or_create_invite_link(force_group_id)
        markup.add(types.InlineKeyboardButton("👥 အုပ်စုသို့ဝင်ရန်", url=gl) if gl
                   else types.InlineKeyboardButton("👥 အုပ်စုသို့ဝင်ရန်", callback_data='no_link'))
    markup.add(types.InlineKeyboardButton("✅ အဖွဲ့ဝင်စစ်ဆေးပါ", callback_data='check_membership'))
    return markup

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
    # Sanitise key input
    key_value = re.sub(r'[^A-Z0-9\-]', '', key_value.strip().upper())
    c = conn.cursor()
    c.execute("SELECT days_valid,max_uses,used_count,file_limit FROM subscription_keys WHERE key_value=?", (key_value,))
    row = c.fetchone()
    if not row:
        return False, "❌ Key မမှန်ပါ"
    days_valid, max_uses, used_count, file_limit = row
    if used_count >= max_uses:
        return False, "❌ Key ကို အခြားသူ အသုံးပြုပြီးပါပြီ"
    c.execute("SELECT COUNT(*) FROM key_usage WHERE key_value=? AND user_id=?", (key_value, user_id))
    if c.fetchone()[0] > 0:
        return False, "❌ Key ကို အသုံးပြုပြီးသားဖြစ်သည်"

    current_expiry = user_subscriptions.get(user_id, {}).get('expiry', datetime.now())
    if current_expiry < datetime.now():
        current_expiry = datetime.now()
    new_expiry = datetime(9999,12,31,23,59,59) if days_valid == -1 else current_expiry + timedelta(days=days_valid)
    save_subscription(user_id, new_expiry, file_limit)

    conn.execute("UPDATE subscription_keys SET used_count=used_count+1 WHERE key_value=?", (key_value,))
    conn.execute("INSERT INTO key_usage(key_value,user_id) VALUES(?,?)", (key_value, user_id))
    conn.commit()

    limit_display = "အကန့်အသတ်မဲ့" if file_limit == 0 else str(file_limit)
    days_display  = "တစ်သက်တာ" if days_valid == -1 else f"{days_valid} ရက်"
    exp_display   = "တစ်သက်တာ" if days_valid == -1 else new_expiry.strftime('%Y-%m-%d %H:%M')
    return True, (
        f"✨ <b>Key အသက်ဝင်ပါပြီ</b> ✨\n"
        f"🔑 <b>Key:</b> <code>{key_value}</code>\n"
        f"📅 <b>ကာလ:</b> {days_display}\n"
        f"📁 <b>ဖိုင်အကန့်အသတ်:</b> {limit_display}\n"
        f"⏳ <b>ကုန်ဆုံး:</b> {exp_display}"
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
#   PROCESS MANAGEMENT (with resource limits)
# ================================================================
def _set_child_limits():
    """Called in child process to set resource limits."""
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

def patch_script_for_replit(script_path, user_folder):
    try:
        with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        patched = []
        for line in lines:
            if ('pip' in line and 'install' in line and '--break-system-packages' not in line
                    and ('subprocess' in line or 'check_call' in line)):
                bp = line.rstrip('\n').rfind(']')
                if bp != -1:
                    line = line.rstrip('\n')[:bp] + ", '--break-system-packages'" + line.rstrip('\n')[bp:] + '\n'
            patched.append(line)
        base = os.path.splitext(os.path.basename(script_path))[0]
        patched_path = os.path.join(user_folder, f"{base}_patched.py")
        if not is_safe_path(user_folder, patched_path):
            return script_path
        with open(patched_path, 'w', encoding='utf-8', errors='ignore') as f:
            f.writelines(patched)
        return patched_path
    except Exception:
        return script_path

PACKAGE_MAP = {
    'telegram': 'python-telegram-bot', 'cv2': 'opencv-python',
    'sklearn': 'scikit-learn', 'PIL': 'Pillow', 'bs4': 'beautifulsoup4',
    'dotenv': 'python-dotenv', 'yaml': 'pyyaml', 'Crypto': 'pycryptodome',
}
COMMONJS_FALLBACK = {'node-telegram-bot-api': '0.66.0'}

def run_python_script(script_path, script_owner_id, user_folder, file_name, message_obj, attempt=1):
    max_attempts = 3
    if attempt > max_attempts:
        bot.reply_to(message_obj, f"❌ <code>{html_module.escape(file_name)}</code> စတင်ရာတွင် အမှား (max attempts reached)", parse_mode='HTML')
        return
    script_key = f"{script_owner_id}_{file_name}"
    log_file = None
    try:
        if not os.path.exists(script_path) or not is_safe_path(UPLOAD_BOTS_DIR, script_path):
            bot.reply_to(message_obj, "❌ ဖိုင်မတွေ့ပါ သို့မဟုတ် လမ်းကြောင်းမမှန်ပါ")
            return
        log_file_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        if not is_safe_path(user_folder, log_file_path):
            bot.reply_to(message_obj, "❌ Log လမ်းကြောင်းမမှန်ပါ")
            return
        log_file = open(log_file_path, 'w', encoding='utf-8', errors='ignore')
        run_env = os.environ.copy()
        run_env['PIP_BREAK_SYSTEM_PACKAGES'] = '1'
        # Remove sensitive env vars from child process
        for sk in ('BOT_TOKEN', 'OWNER_ID', 'ADMIN_ID', 'DATABASE_URL', 'SESSION_SECRET'):
            run_env.pop(sk, None)
        patched = patch_script_for_replit(script_path, user_folder)
        process = subprocess.Popen(
            [sys.executable, patched],
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
            install_pkg = None; uninstall_pkg = None
            m1 = re.search(r"ModuleNotFoundError: No module named '([^']+)'", log_content)
            if m1:
                install_pkg = PACKAGE_MAP.get(m1.group(1).split('.')[0], m1.group(1).split('.')[0])
            if not install_pkg:
                m2 = re.search(r"ImportError: cannot import name '.+?' from '([^']+)'", log_content)
                if m2:
                    wp = m2.group(1).split('.')[0]
                    if wp in PACKAGE_MAP:
                        install_pkg = PACKAGE_MAP[wp]; uninstall_pkg = wp
            if not install_pkg:
                m3 = re.search(r"ImportError: No module named '([^']+)'", log_content)
                if m3:
                    install_pkg = PACKAGE_MAP.get(m3.group(1).split('.')[0], m3.group(1).split('.')[0])
            if install_pkg and attempt < max_attempts:
                with bot_scripts_lock:
                    bot_scripts.pop(script_key, None)
                if uninstall_pkg:
                    subprocess.run([sys.executable,'-m','pip','uninstall',uninstall_pkg,'-y','--break-system-packages'],
                                   capture_output=True, timeout=60)
                bot.reply_to(message_obj, f"🔧 <code>{install_pkg}</code> တပ်ဆင်နေသည်...", parse_mode='HTML')
                res = subprocess.run([sys.executable,'-m','pip','install',install_pkg,'--break-system-packages','--timeout','60'],
                                     capture_output=True, text=True, timeout=120)
                if res.returncode == 0:
                    threading.Thread(target=run_python_script,
                                     args=(script_path, script_owner_id, user_folder, file_name, message_obj, attempt+1)).start()
                else:
                    bot.reply_to(message_obj, f"❌ တပ်ဆင်မှုမအောင်မြင်: {html_module.escape(res.stderr[:500])}", parse_mode='HTML')
                return
            with bot_scripts_lock:
                bot_scripts.pop(script_key, None)
            safe_preview = html_module.escape(log_content[-800:]) if log_content else ''
            bot.reply_to(message_obj,
                         f"❌ <code>{html_module.escape(file_name)}</code> error:\n<pre>{safe_preview}</pre>",
                         parse_mode='HTML')
            return
        bot.reply_to(message_obj,
                     f"✅ <code>{html_module.escape(file_name)}</code> (Python) စတင်ပြီ (PID: {process.pid})",
                     parse_mode='HTML')
    except Exception as e:
        if log_file and not log_file.closed:
            log_file.close()
        bot.reply_to(message_obj, f"❌ <code>{html_module.escape(file_name)}</code> အမှား: {str(e)}", parse_mode='HTML')
        with bot_scripts_lock:
            bot_scripts.pop(script_key, None)

def run_js_script(script_path, script_owner_id, user_folder, file_name, message_obj, attempt=1):
    max_attempts = 3
    if attempt > max_attempts:
        bot.reply_to(message_obj, f"❌ <code>{html_module.escape(file_name)}</code> စတင်ရာတွင် အမှား", parse_mode='HTML')
        return
    script_key = f"{script_owner_id}_{file_name}"
    if not shutil.which("node"):
        bot.reply_to(message_obj, "❌ Node.js မရှိပါ။"); return
    if not shutil.which("npm"):
        bot.reply_to(message_obj, "❌ npm မရှိပါ။"); return
    log_file = None
    try:
        if not os.path.exists(script_path) or not is_safe_path(UPLOAD_BOTS_DIR, script_path):
            bot.reply_to(message_obj, "❌ ဖိုင်မတွေ့ပါ"); return
        with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        required = {m.group(1) for m in re.finditer(r"require\(['\"]([^'\"./][^'\"]*)['\"]", content)}
        missing  = [m for m in required if not os.path.exists(os.path.join(user_folder, 'node_modules', m))]
        if missing:
            bot.reply_to(message_obj, f"📦 Installing: <code>{', '.join(missing)}</code>...", parse_mode='HTML')
            subprocess.run(["npm", "install", "--save"] + missing, cwd=user_folder, check=False, timeout=120)
            time.sleep(1)
        log_file_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        if not is_safe_path(user_folder, log_file_path):
            bot.reply_to(message_obj, "❌ Log လမ်းကြောင်းမမှန်ပါ"); return
        log_file = open(log_file_path, 'w', encoding='utf-8', errors='ignore')
        run_env = os.environ.copy()
        for sk in ('BOT_TOKEN', 'OWNER_ID', 'ADMIN_ID', 'DATABASE_URL', 'SESSION_SECRET'):
            run_env.pop(sk, None)
        process = subprocess.Popen(
            ["node", script_path], cwd=user_folder, stdout=log_file, stderr=log_file,
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
                for pkg, ver in COMMONJS_FALLBACK.items():
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
                     f"✅ <code>{html_module.escape(file_name)}</code> (Node.js) စတင်ပြီ (PID: {process.pid})",
                     parse_mode='HTML')
    except Exception as e:
        if log_file and not log_file.closed:
            log_file.close()
        bot.reply_to(message_obj, f"❌ <code>{html_module.escape(file_name)}</code> အမှား: {str(e)}", parse_mode='HTML')
        with bot_scripts_lock:
            bot_scripts.pop(script_key, None)

def send_log_file(user_id, file_name, chat_id):
    folder = get_user_folder(user_id)
    log_path = os.path.join(folder, f"{os.path.splitext(file_name)[0]}.log")
    if not is_safe_path(folder, log_path):
        return False
    if os.path.exists(log_path):
        with open(log_path, 'rb') as f:
            bot.send_document(chat_id, f, caption=f"📋 {file_name} — Log")
        return True
    bot.send_message(chat_id, f"📭 <code>{html_module.escape(file_name)}</code> Log မရှိပါ", parse_mode='HTML')
    return False

# ================================================================
#   UI KEYBOARDS
# ================================================================
def create_main_menu_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = ['📤 ဖိုင်တင်ရန်','📁 ကျွန်ုပ်၏ဖိုင်များ','🔑 Key ဖြည့်ရန်',
               '✨ အဆင့်မြှင့်ရန်','👤 ကိုယ်ရေးအချက်အလက်','📊 အခြေအနေ']
    if user_id in admin_ids:
        buttons.append('⚙️ အယ်မင်းအကန့်')
    for i in range(0, len(buttons), 2):
        row = [buttons[i], buttons[i+1]] if i+1 < len(buttons) else [buttons[i]]
        markup.row(*row)
    return markup

def create_manage_files_keyboard(user_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    files = user_files.get(user_id, [])
    if not files:
        markup.add(types.InlineKeyboardButton("📭 ဖိုင်မရှိပါ", callback_data='no_files'))
    else:
        for fn, ft, fp in files:
            status = "🟢" if is_bot_running(user_id, fn) else "🔴"
            markup.add(types.InlineKeyboardButton(f"{status} {fn}", callback_data=f'file_{user_id}_{fn}'))
    markup.add(types.InlineKeyboardButton("⬅️ နောက်သို့", callback_data='back_to_main'))
    return markup

def create_file_management_buttons(user_id, file_name, is_running=True):
    markup = types.InlineKeyboardMarkup(row_width=2)
    if is_running:
        markup.row(
            types.InlineKeyboardButton("⏸️ ခေတ္တရပ်ရန်", callback_data=f'stop_{user_id}_{file_name}'),
            types.InlineKeyboardButton("🔄 ပြန်စတင်ရန်", callback_data=f'restart_{user_id}_{file_name}')
        )
    else:
        markup.row(types.InlineKeyboardButton("▶️ စတင်ရန်", callback_data=f'start_{user_id}_{file_name}'))
    markup.row(
        types.InlineKeyboardButton("🗑️ ဖျက်ရန်", callback_data=f'delete_{user_id}_{file_name}'),
        types.InlineKeyboardButton("📋 Log", callback_data=f'logs_{user_id}_{file_name}')
    )
    markup.add(types.InlineKeyboardButton("📥 ဒေါင်းလုပ်", callback_data=f'download_{user_id}_{file_name}'))
    markup.add(types.InlineKeyboardButton("⬅️ နောက်သို့", callback_data='manage_files'))
    return markup

def create_admin_panel_keyboard(user_id=None):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = ['📊 စာရင်းအင်းများ','👥 အသုံးပြုသူများ','✨ Pro အသုံးပြုသူများ','🔄 လည်ပတ်နေသည့်များ',
               '📢 အသိပေးစာ','🔑 Key ထုတ်ရန်','🗑️ Key ဖျက်ရန်','🔢 Key များ',
               '📈 အကန့်အသတ်','💎 Premium စီမံရန်','⚙️ ဆက်တင်များ','🔗 Force Join စီမံရန်',
               '🚫 Ban User','✅ Unban User','🛡️ Security Logs']
    if user_id == OWNER_ID:
        buttons = ['➕ အယ်မင်းထည့်ရန်','➖ အယ်မင်းဖယ်ရှားရန်'] + buttons
    for i in range(0, len(buttons), 2):
        row = [buttons[i], buttons[i+1]] if i+1 < len(buttons) else [buttons[i]]
        markup.row(*row)
    markup.row('⬅️ နောက်သို့')
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
        f"👋 မင်္ဂလာပါ <b>{html_module.escape(message.from_user.first_name)}</b>!\n\n"
        f"🤖 <b>DEV-RAW Core v2.0</b>\n"
        f"🛡️ Python & JS Bot Hosting Platform\n\n"
        f"📊 <b>အဆင့်:</b> {get_user_status(user_id)}"
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
        bot.send_message(message.chat.id, "🔒 ပြုပြင်ထိန်းသိမ်းချိန်ဖြစ်ပါသည်။")
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
        bot.reply_to(message, "🔒 ပြုပြင်ထိန်းသိမ်းချိန်"); return
    if not check_force_join_and_access(user_id):
        bot.send_message(message.chat.id, create_force_join_message(),
                         reply_markup=create_force_join_keyboard(), parse_mode='HTML'); return

    file_limit = get_user_file_limit(user_id)
    current   = get_user_file_count(user_id)
    if file_limit != float('inf') and current >= file_limit:
        bot.reply_to(message, f"❌ ဖိုင်အကန့်အသတ် {int(file_limit)} ပြည့်သွားပါပြီ။"); return

    doc = message.document
    # --- Size check ---
    if doc.file_size and doc.file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        bot.reply_to(message, f"❌ ဖိုင်အရွယ်အစား {MAX_FILE_SIZE_MB}MB ထက် မကျော်ရပါ။"); return

    raw_name = doc.file_name or "uploaded_file.py"
    file_name = sanitize_filename(raw_name)
    file_ext  = os.path.splitext(file_name)[1].lower()
    if file_ext not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(f"<code>{e}</code>" for e in SUPPORTED_EXTENSIONS)
        bot.reply_to(message, f"❌ ခွင့်မပြုသောဖိုင်အမျိုးအစား\nခွင့်ပြုချက်: {supported}", parse_mode='HTML'); return

    try:
        file_info     = bot.get_file(doc.file_id)
        downloaded    = bot.download_file(file_info.file_path)
    except Exception as e:
        bot.reply_to(message, f"❌ ဖိုင်ဒေါင်းလုပ် မအောင်မြင်: {e}"); return

    # --- Content security scan ---
    ok, reason = validate_file_content(downloaded, file_ext)
    if not ok:
        log_security_event(user_id, "BLOCKED_UPLOAD", reason)
        bot.reply_to(message, f"🛡️ ဖိုင်ကို ဘေးကင်းရေးစစ်ဆေးမှုတွင် ပယ်ချလိုက်သည်:\n{reason}", parse_mode='HTML')
        return

    file_hash   = sha256_file(downloaded)
    user_folder = get_user_folder(user_id)
    file_path   = os.path.join(user_folder, file_name)

    # --- Path traversal check ---
    if not is_safe_path(user_folder, file_path):
        log_security_event(user_id, "PATH_TRAVERSAL", file_name)
        bot.reply_to(message, "❌ ဖိုင်လမ်းကြောင်း မမှန်ကန်ပါ။"); return

    with open(file_path, 'wb') as f:
        f.write(downloaded)

    file_type = SUPPORTED_EXTENSIONS[file_ext]
    save_user_file(user_id, file_name, file_type, file_path, file_hash)

    try:
        bot.forward_message(OWNER_ID, message.chat.id, message.message_id)
        bot.send_message(OWNER_ID,
                         f"📤 ဖိုင်အသစ်\n👤 {html_module.escape(message.from_user.first_name)} (ID: {user_id})\n"
                         f"📄 <code>{html_module.escape(file_name)}</code>\n🔐 SHA256: <code>{file_hash[:16]}…</code>",
                         parse_mode='HTML')
    except Exception:
        pass

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📁 ဖိုင်များသို့", callback_data='manage_files'))
    bot.reply_to(message,
                 f"✅ <code>{html_module.escape(file_name)}</code> တင်ပြီးပါပြီ\n"
                 f"📦 {file_type}\n🔐 Hash: <code>{file_hash[:16]}…</code>",
                 reply_markup=markup, parse_mode='HTML')

@bot.message_handler(func=lambda m: True)
@secure_handler()
def handle_text_messages(message):
    user_id = message.from_user.id
    if bot_locked and user_id not in admin_ids:
        bot.send_message(message.chat.id, "🔒 ပြုပြင်ထိန်းသိမ်းချိန်"); return
    if not check_force_join_and_access(user_id):
        bot.send_message(message.chat.id, create_force_join_message(),
                         reply_markup=create_force_join_keyboard(), parse_mode='HTML'); return
    text = message.text or ''
    dispatch = {
        '📤 ဖိုင်တင်ရန်':    lambda: bot.send_message(message.chat.id, "📤 <code>.py</code> သို့မဟုတ် <code>.js</code> ဖိုင် တင်ပါ", parse_mode='HTML'),
        '📁 ကျွန်ုပ်၏ဖိုင်များ': lambda: handle_manage_files(message),
        '🔑 Key ဖြည့်ရန်':   lambda: bot.register_next_step_handler(
                                        bot.send_message(message.chat.id, "🔑 Key ထည့်ပါ (DEVRAW-XXXXXXXXXXXX):"),
                                        process_redeem_key),
        '✨ အဆင့်မြှင့်ရန်':  lambda: handle_upgrade(message),
        '👤 ကိုယ်ရေးအချက်အလက်': lambda: handle_my_info(message),
        '📊 အခြေအနေ':       lambda: handle_status(message),
        '⬅️ နောက်သို့':      lambda: bot.send_message(message.chat.id, "🏠 ပင်မစာမျက်နှာ",
                                                        reply_markup=create_main_menu_keyboard(user_id)),
    }
    admin_dispatch = {
        '⚙️ အယ်မင်းအကန့်':   lambda: handle_admin_panel(message),
        '📊 စာရင်းအင်းများ':  lambda: handle_stats(message),
        '👥 အသုံးပြုသူများ':  lambda: handle_all_users(message),
        '✨ Pro အသုံးပြုသူများ': lambda: handle_premium_users(message),
        '🔄 လည်ပတ်နေသည့်များ': lambda: handle_running_scripts(message),
        '📢 အသိပေးစာ':       lambda: bot.register_next_step_handler(
                                        bot.send_message(message.chat.id, "📢 အသိပေးစာထည့်ပါ:"),
                                        process_broadcast),
        '🔑 Key ထုတ်ရန်':    lambda: handle_generate_key(message),
        '🗑️ Key ဖျက်ရန်':   lambda: handle_delete_key(message),
        '🔢 Key များ':        lambda: handle_list_keys(message),
        '📈 အကန့်အသတ်':      lambda: handle_set_limit(message),
        '💎 Premium စီမံရန်':  lambda: handle_premium_plan_management(message),
        '⚙️ ဆက်တင်များ':     lambda: handle_settings(message),
        '🔗 Force Join စီမံရန်': lambda: handle_force_join_management(message),
        '🚫 Ban User':        lambda: bot.register_next_step_handler(
                                        bot.send_message(message.chat.id, "🚫 Ban လုပ်ရန် User ID ထည့်ပါ:"),
                                        process_ban_user),
        '✅ Unban User':      lambda: bot.register_next_step_handler(
                                        bot.send_message(message.chat.id, "✅ Unban လုပ်ရန် User ID ထည့်ပါ:"),
                                        process_unban_user),
        '🛡️ Security Logs':  lambda: handle_security_logs(message),
    }
    owner_dispatch = {
        '➕ အယ်မင်းထည့်ရန်':  lambda: bot.register_next_step_handler(
                                        bot.send_message(message.chat.id, "👤 Admin User ID ထည့်ပါ:"),
                                        process_add_admin),
        '➖ အယ်မင်းဖယ်ရှားရန်': lambda: bot.register_next_step_handler(
                                        bot.send_message(message.chat.id, "👤 ဖယ်ရှားမည့် Admin User ID ထည့်ပါ:"),
                                        process_remove_admin),
    }
    if text in dispatch:
        dispatch[text]()
    elif text in admin_dispatch and user_id in admin_ids:
        admin_dispatch[text]()
    elif text in owner_dispatch and user_id == OWNER_ID:
        owner_dispatch[text]()
    else:
        bot.send_message(message.chat.id, "❌ မသိသော command ဖြစ်ပါသည်")

# ================================================================
#   ADMIN HANDLERS
# ================================================================
def handle_admin_panel(message):
    if message.from_user.id not in admin_ids: return
    bot.send_message(message.chat.id, "⚙️ <b>အယ်မင်းထိန်းချုပ်မှုအကန့်</b>",
                     reply_markup=create_admin_panel_keyboard(message.from_user.id), parse_mode='HTML')

def process_add_admin(message):
    try:
        new_id = int(message.text.strip())
        if new_id in admin_ids:
            bot.send_message(message.chat.id, "⚠️ ထို user သည် admin ဖြစ်ပြီးသားပါ။"); return
        admin_ids.add(new_id)
        conn.execute("INSERT OR IGNORE INTO admins(user_id) VALUES(?)", (new_id,))
        conn.commit()
        bot.send_message(message.chat.id, f"✅ Admin <code>{new_id}</code> ထည့်ပြီးပါပြီ။", parse_mode='HTML')
    except Exception:
        bot.send_message(message.chat.id, "❌ မှန်ကန်သော User ID ထည့်ပါ။")

def process_remove_admin(message):
    try:
        aid = int(message.text.strip())
        if aid == OWNER_ID:
            bot.send_message(message.chat.id, "❌ ပိုင်ရှင်ကို ဖယ်ရှား၍မရပါ။"); return
        if aid not in admin_ids:
            bot.send_message(message.chat.id, "⚠️ ထို user သည် admin မဟုတ်ပါ။"); return
        admin_ids.discard(aid)
        conn.execute("DELETE FROM admins WHERE user_id=?", (aid,))
        conn.commit()
        bot.send_message(message.chat.id, f"✅ Admin <code>{aid}</code> ဖယ်ရှားပြီးပါပြီ။", parse_mode='HTML')
    except Exception:
        bot.send_message(message.chat.id, "❌ မှန်ကန်သော User ID ထည့်ပါ။")

def process_ban_user(message):
    try:
        target = int(message.text.strip())
        success, msg = ban_user(target)
        bot.send_message(message.chat.id, msg, parse_mode='HTML')
    except Exception:
        bot.send_message(message.chat.id, "❌ မှန်ကန်သော User ID ထည့်ပါ။")

def process_unban_user(message):
    try:
        target = int(message.text.strip())
        success, msg = unban_user(target)
        bot.send_message(message.chat.id, msg, parse_mode='HTML')
    except Exception:
        bot.send_message(message.chat.id, "❌ မှန်ကန်သော User ID ထည့်ပါ။")

def handle_generate_key(message):
    msg = bot.send_message(message.chat.id, "📅 ရက်အရေအတွက် (-1=တစ်သက်တာ, 1-365):")
    bot.register_next_step_handler(msg, process_key_days)

def process_key_days(message):
    try:
        days = int(message.text.strip())
        if days < -1 or days > 365:
            bot.send_message(message.chat.id, "❌ -1 သို့မဟုတ် 1-365 ထည့်ပါ"); return
        msg = bot.send_message(message.chat.id, "📁 ဖိုင်အကန့်အသတ် (0=အကန့်အသတ်မဲ့):")
        bot.register_next_step_handler(msg, process_key_file_limit, days)
    except Exception:
        bot.send_message(message.chat.id, "❌ ဂဏန်းထည့်ပါ")

def process_key_file_limit(message, days):
    try:
        val = message.text.strip()
        file_limit = 0 if val.lower() in ('unlimited','∞','0') else int(val)
        if file_limit < 0:
            bot.send_message(message.chat.id, "❌ 0 သို့မဟုတ် အပေါင်းကိန်းထည့်ပါ"); return
        key = generate_subscription_key(days, file_limit)
        ld  = "အကန့်အသတ်မဲ့" if file_limit == 0 else str(file_limit)
        dd  = "တစ်သက်တာ" if days == -1 else f"{days} ရက်"
        bot.send_message(message.chat.id,
                         f"✅ <b>Key ထုတ်လုပ်ပြီး</b>\n\n🔑 <code>{key}</code>\n📅 {dd}\n📁 {ld} ဖိုင်",
                         parse_mode='HTML')
    except Exception:
        bot.send_message(message.chat.id, "❌ ဂဏန်းထည့်ပါ")

def handle_delete_key(message):
    keys = get_all_subscription_keys()
    if not keys:
        bot.send_message(message.chat.id, "📭 Key မရှိပါ"); return
    text = "🗑️ <b>ရှိသော Key များ:</b>\n\n"
    for k in keys:
        ld = "∞" if k['file_limit']==0 else str(k['file_limit'])
        dd = "တစ်သက်တာ" if k['days_valid']==-1 else f"{k['days_valid']}ရက်"
        text += f"• <code>{k['key_value']}</code> — {dd}, {k['used_count']}/{k['max_uses']}, file:{ld}\n"
    text += "\nဖျက်လိုသော Key ထည့်ပါ:"
    bot.send_message(message.chat.id, text, parse_mode='HTML')
    msg = bot.send_message(message.chat.id, "🔑 Key value:")
    bot.register_next_step_handler(msg, process_delete_key)

def process_delete_key(message):
    key = re.sub(r'[^A-Z0-9\-]', '', message.text.strip().upper())
    delete_subscription_key(key)
    bot.send_message(message.chat.id, f"✅ <code>{key}</code> ဖျက်ပြီး", parse_mode='HTML')

def handle_list_keys(message):
    keys = get_all_subscription_keys()
    if not keys:
        bot.send_message(message.chat.id, "📭 Key မရှိပါ"); return
    text = "🔢 <b>Key များ:</b>\n\n"
    for k in keys:
        ld = "∞" if k['file_limit']==0 else str(k['file_limit'])
        dd = "တစ်သက်တာ" if k['days_valid']==-1 else f"{k['days_valid']}ရက်"
        text += f"• <code>{k['key_value']}</code> — {dd}, {k['used_count']}/{k['max_uses']}, file:{ld}\n"
    bot.send_message(message.chat.id, text, parse_mode='HTML')

def handle_set_limit(message):
    msg = bot.send_message(message.chat.id, f"📈 လက်ရှိ: {FREE_USER_LIMIT}\nအသစ် (1-100):")
    bot.register_next_step_handler(msg, process_set_limit)

def process_set_limit(message):
    try:
        n = int(message.text.strip())
        if 1 <= n <= 100:
            update_file_limit(n)
            bot.send_message(message.chat.id, f"✅ ဖိုင်အကန့်အသတ်: {n}")
        else:
            bot.send_message(message.chat.id, "❌ 1-100 ကြားထည့်ပါ")
    except Exception:
        bot.send_message(message.chat.id, "❌ ဂဏန်းထည့်ပါ")

def handle_settings(message):
    sys_stats = get_system_stats()
    text = (
        f"⚙️ <b>ဆက်တင်များ</b>\n\n"
        f"🔒 Bot: {'🔒 သော့ခတ်' if bot_locked else '🔓 ဖွင့်'}\n"
        f"🔰 Force Join: {'✅ ဖွင့်' if force_join_enabled else '❌ ပိတ်'}\n"
        f"📁 Free Limit: {FREE_USER_LIMIT}\n"
        f"🖥 CPU: {sys_stats['cpu']}%\n"
        f"💾 RAM: {sys_stats['ram_percent']}% ({sys_stats['ram_used']}/{sys_stats['ram_total']} MB)"
    )
    markup = types.InlineKeyboardMarkup()
    if message.from_user.id == OWNER_ID:
        markup.add(types.InlineKeyboardButton("🔒 သော့ခတ်" if not bot_locked else "🔓 ဖွင့်",
                                              callback_data='lock_bot' if not bot_locked else 'unlock_bot'))
        markup.add(types.InlineKeyboardButton("❌ Force Join ပိတ်" if force_join_enabled else "✅ Force Join ဖွင့်",
                                              callback_data='disable_force_join' if force_join_enabled else 'enable_force_join'))
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode='HTML')

def handle_force_join_management(message):
    if message.from_user.id not in admin_ids: return
    current = ", ".join(map(str, force_channel_ids)) or "မရှိ"
    info = (f"🔗 <b>Force Join စီမံမှု</b>\n"
            f"📣 Channel IDs: <code>{current}</code>\n"
            f"👥 Group ID: <code>{force_group_id}</code>\n\n"
            f"Channel IDs (comma ခြား) ထည့်ပါ:")
    msg = bot.send_message(message.chat.id, info, parse_mode='HTML')
    bot.register_next_step_handler(msg, process_force_join_channels)

def process_force_join_channels(message):
    try:
        ids = [int(x.strip()) for x in message.text.split(',') if x.strip().lstrip('-').isdigit()]
        if not ids:
            bot.send_message(message.chat.id, "❌ မှန်ကန်သော ID ထည့်ပါ"); return
        msg = bot.send_message(message.chat.id, "👥 Group ID ထည့်ပါ:")
        bot.register_next_step_handler(msg, process_force_join_group, ids)
    except Exception:
        bot.send_message(message.chat.id, "❌ ဂဏန်းများသာ ထည့်ပါ")

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
        invite_links.clear()
        bot.send_message(message.chat.id, f"✅ Force Join အပ်ဒိတ်ပြီး\nChannels: {force_channel_ids}\nGroup: {force_group_id}")
    except Exception:
        bot.send_message(message.chat.id, "❌ မှန်ကန်သော Group ID ထည့်ပါ")

def handle_running_scripts(message):
    if message.from_user.id not in admin_ids: return
    with bot_scripts_lock:
        sc = dict(bot_scripts)
    if not sc:
        bot.send_message(message.chat.id, "🔄 လည်ပတ်နေသော script မရှိပါ"); return
    text = "<b>🔄 လည်ပတ်နေသော Scripts:</b>\n\n"
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

def handle_security_logs(message):
    if message.from_user.id not in admin_ids: return
    c = conn.cursor()
    c.execute("SELECT user_id,event,detail,ts FROM security_events ORDER BY id DESC LIMIT 30")
    rows = c.fetchall()
    if not rows:
        bot.send_message(message.chat.id, "📭 Security log မရှိပါ"); return
    text = "🛡️ <b>Security Events (နောက်ဆုံး 30):</b>\n\n"
    for row in rows:
        uid, ev, det, ts = row
        text += f"[{ts}] {ev} uid={uid}\n{det[:80]}\n\n"
    bot.send_message(message.chat.id, text[:4000], parse_mode='HTML')

def handle_premium_plan_management(message):
    plans = get_all_premium_plans()
    text  = "💎 <b>Premium Plan များ</b>\n\n"
    for p in plans:
        dd = "တစ်သက်တာ" if p['days']==-1 else f"{p['days']}ရက်"
        fd = "∞" if p['file_limit']==0 else p['file_limit']
        text += f"• ID:{p['id']} {p['name']} | {dd} | {p['price']}Ks | file:{fd}\n"
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("➕ ထည့်ရန်", callback_data='add_premium_plan'),
               types.InlineKeyboardButton("➖ ဖျက်ရန်", callback_data='delete_premium_plan'))
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode='HTML')

@bot.callback_query_handler(func=lambda c: c.data == 'add_premium_plan')
def callback_add_premium_plan(call):
    if call.from_user.id not in admin_ids:
        safe_answer_callback(call, "❌ ခွင့်မပြု"); return
    msg = bot.send_message(call.message.chat.id, "💎 Plan အမည်:")
    bot.register_next_step_handler(msg, process_plan_name)

def process_plan_name(message):
    name = message.text.strip()[:50]
    msg = bot.send_message(message.chat.id, "📅 ရက်(-1=တစ်သက်တာ):")
    bot.register_next_step_handler(msg, process_plan_days, name)

def process_plan_days(message, name):
    try:
        days = int(message.text.strip())
        msg = bot.send_message(message.chat.id, "💰 စျေးနှုန်း(ကျပ်):")
        bot.register_next_step_handler(msg, process_plan_price, name, days)
    except Exception:
        bot.send_message(message.chat.id, "❌ ဂဏန်းထည့်ပါ")

def process_plan_price(message, name, days):
    try:
        price = int(message.text.strip())
        msg = bot.send_message(message.chat.id, "📁 File limit(0=∞):")
        bot.register_next_step_handler(msg, process_plan_filelimit, name, days, price)
    except Exception:
        bot.send_message(message.chat.id, "❌ ဂဏန်းထည့်ပါ")

def process_plan_filelimit(message, name, days, price):
    try:
        fl = int(message.text.strip())
        if fl < 0:
            bot.send_message(message.chat.id, "❌ 0 သို့မဟုတ် အပေါင်းကိန်း"); return
        add_premium_plan(name, days, price, fl)
        bot.send_message(message.chat.id, f"✅ Plan '{name}' ထည့်ပြီး")
    except Exception:
        bot.send_message(message.chat.id, "❌ ဂဏန်းထည့်ပါ")

@bot.callback_query_handler(func=lambda c: c.data == 'delete_premium_plan')
def callback_delete_premium_plan(call):
    if call.from_user.id not in admin_ids:
        safe_answer_callback(call, "❌ ခွင့်မပြု"); return
    plans = get_all_premium_plans()
    if not plans:
        safe_answer_callback(call, "ဖျက်ရန် plan မရှိပါ", show_alert=True); return
    pl = "\n".join(f"ID:{p['id']} {p['name']}" for p in plans)
    msg = bot.send_message(call.message.chat.id, f"💎 Plan ID:\n{pl}\n\nID ထည့်ပါ:")
    bot.register_next_step_handler(msg, process_delete_plan_id)

def process_delete_plan_id(message):
    try:
        pid = int(message.text.strip())
        delete_premium_plan(pid)
        bot.send_message(message.chat.id, f"✅ Plan ID {pid} ဖျက်ပြီး")
    except Exception:
        bot.send_message(message.chat.id, "❌ မှန်ကန်သော Plan ID ထည့်ပါ")

# ================================================================
#   COMMON HANDLERS
# ================================================================
def get_bot_statistics():
    total_users = len(active_users)
    total_files = sum(len(f) for f in user_files.values())
    with bot_scripts_lock:
        active_files = len(bot_scripts)
    premium_users = sum(1 for uid in active_users if is_premium_user(uid))
    return {'total_users': total_users, 'total_files': total_files,
            'active_files': active_files, 'premium_users': premium_users}

def handle_stats(message):
    stats     = get_bot_statistics()
    sys_stats = get_system_stats()
    text = (
        f"📊 <b>စနစ်စာရင်းအင်းများ</b>\n\n"
        f"👥 အသုံးပြုသူ: <code>{stats['total_users']}</code>\n"
        f"✨ Pro: <code>{stats['premium_users']}</code>\n"
        f"🚫 Banned: <code>{len(banned_users)}</code>\n"
        f"📁 ဖိုင်များ: <code>{stats['total_files']}</code>\n"
        f"🟢 လည်ပတ်နေသည်: <code>{stats['active_files']}</code>\n\n"
        f"🖥 <b>Server</b>\n"
        f"├ CPU: {sys_stats['cpu']}%\n"
        f"├ RAM: {sys_stats['ram_percent']}% ({sys_stats['ram_used']}/{sys_stats['ram_total']} MB)\n"
        f"└ ⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    bot.send_message(message.chat.id, text, parse_mode='HTML')

def handle_all_users(message):
    c = conn.cursor()
    c.execute("SELECT user_id,username,first_name,banned FROM users LIMIT 50")
    rows = c.fetchall()
    if not rows:
        bot.send_message(message.chat.id, "📭 အသုံးပြုသူမရှိပါ"); return
    text = "👥 <b>အသုံးပြုသူများ:</b>\n\n"
    for row in rows:
        uid, uname, fname, banned = row
        status = "✨" if is_premium_user(uid) else "🎯"
        ban    = " [🚫]" if banned else ""
        text  += f"• {status} {html_module.escape(fname or 'Unknown')} (@{uname or '-'}){ban}\n"
    bot.send_message(message.chat.id, text, parse_mode='HTML')

def handle_premium_users(message):
    prems = [(uid, s) for uid, s in user_subscriptions.items() if s['expiry'] > datetime.now()]
    if not prems:
        bot.send_message(message.chat.id, "📭 Premium user မရှိပါ"); return
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

def handle_upgrade(message):
    plans = get_all_premium_plans()
    if not plans:
        bot.send_message(message.chat.id, "💎 Premium plan မရှိသေးပါ။ Admin ထံဆက်သွယ်ပါ။"); return
    text = "💎 <b>Premium Plan များ</b>\n\n"
    for p in plans:
        dd = "တစ်သက်တာ" if p['days']==-1 else f"{p['days']}ရက်"
        fd = "∞" if p['file_limit']==0 else p['file_limit']
        text += f"• <b>{p['name']}</b>: {p['price']}Ks | {dd} | File:{fd}\n"
    text += f"\n💳 KPAY/WAVE | 📲 {ADMIN_USERNAME}"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💳 ဆက်သွယ်ရန်", url=f"https://t.me/{ADMIN_USERNAME.lstrip('@')}"))
    markup.add(types.InlineKeyboardButton("🔑 Key ရှိပြီးသား", callback_data='redeem_key'))
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
        exp_str = f"\n⏳ Expiry: {sub['expiry'].strftime('%Y-%m-%d')}"
    sys_stats = get_system_stats()
    text = (
        f"👤 <b>ကိုယ်ရေးအချက်အလက်</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"👤 အမည်: {html_module.escape(message.from_user.first_name)}\n"
        f"📊 အဆင့်: {get_user_status(user_id)}{exp_str}\n\n"
        f"📁 <b>ဖိုင်</b>\n"
        f"├ စုစုပေါင်း: {fc}/{ls}\n"
        f"├ 🟢 လည်ပတ်: {running}\n"
        f"└ 🔴 ရပ်ထား: {fc - running}\n\n"
        f"🖥 CPU:{sys_stats['cpu']}% RAM:{sys_stats['ram_percent']}%"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📁 ဖိုင်များ", callback_data='manage_files'))
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode='HTML')

def handle_status(message):
    handle_my_info(message)

def handle_manage_files(message):
    user_id = message.from_user.id
    files   = user_files.get(user_id, [])
    if not files:
        bot.send_message(message.chat.id, "📭 ဖိုင်မရှိပါ"); return
    text = "📁 <b>သင့်ဖိုင်များ:</b>\n\n"
    for fn, ft, fp in files:
        status = "🟢" if is_bot_running(user_id, fn) else "🔴"
        text  += f"{status} <code>{html_module.escape(fn)}</code>\n"
    markup = create_manage_files_keyboard(user_id)
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode='HTML')

def process_redeem_key(message):
    user_id = message.from_user.id
    key     = re.sub(r'[^A-Z0-9\-]', '', message.text.strip().upper())
    if not key.startswith('DEVRAW-'):
        bot.reply_to(message, "❌ ပုံစံ: <code>DEVRAW-XXXXXXXXXXXX</code>", parse_mode='HTML'); return
    success, msg = redeem_subscription_key(key, user_id)
    bot.reply_to(message, msg, parse_mode='HTML')

# ================================================================
#   BROADCAST
# ================================================================
def process_broadcast(message):
    bcast = message.text
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ ပို့ရန်", callback_data=f'confirm_broadcast_{message.message_id}'),
               types.InlineKeyboardButton("❌ ပယ်ဖျက်", callback_data='cancel_broadcast'))
    broadcast_messages[message.message_id] = bcast
    bot.send_message(message.chat.id, f"📢 <b>Preview:</b>\n\n{bcast}\n\nPost?",
                     reply_markup=markup, parse_mode='HTML')

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

@bot.callback_query_handler(func=lambda c: c.data not in ('add_premium_plan','delete_premium_plan'))
def handle_callbacks(call):
    user_id = call.from_user.id
    if is_user_banned(user_id):
        safe_answer_callback(call, "🚫 Ban ခံထားရသည်", show_alert=True); return
    if not rate_limiter.is_allowed(user_id):
        safe_answer_callback(call, "⚠️ မြန်နှုန်းကန့်သတ်", show_alert=True)
        auto_ban_check(user_id); return

    data = call.data

    if data == 'check_membership':
        if verify_membership(user_id):
            safe_answer_callback(call, "✅ အတည်ပြုပြီး")
            show_main_menu(call.message, user_id)
        else:
            safe_answer_callback(call, "❌ ချန်နယ်/အုပ်စုအားလုံးဝင်ပါ", show_alert=True)
    elif data == 'manage_files':   handle_manage_files_callback(call)
    elif data == 'back_to_main':   show_main_menu(call.message, user_id)
    elif data.startswith('file_'): handle_file_click(call)
    elif data.startswith('start_'): handle_start_file(call)
    elif data.startswith('stop_'):  handle_stop_file(call)
    elif data.startswith('restart_'): handle_restart_file(call)
    elif data.startswith('delete_'): handle_delete_file_callback(call)
    elif data.startswith('logs_'):  handle_logs_callback(call)
    elif data.startswith('download_'): handle_download_callback(call)
    elif data == 'redeem_key':
        msg = bot.send_message(call.message.chat.id, "🔑 Key ထည့်ပါ:")
        bot.register_next_step_handler(msg, process_redeem_key)
    elif data.startswith('confirm_broadcast_'): handle_confirm_broadcast(call)
    elif data == 'cancel_broadcast':
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception: pass
        safe_answer_callback(call, "ပယ်ဖျက်ပြီး")
    elif data == 'lock_bot' and user_id == OWNER_ID:
        global bot_locked
        bot_locked = True
        safe_answer_callback(call, "🔒 သော့ခတ်ထား")
        handle_settings(call.message)
    elif data == 'unlock_bot' and user_id == OWNER_ID:
        bot_locked = False
        safe_answer_callback(call, "🔓 ဖွင့်ထား")
        handle_settings(call.message)
    elif data == 'enable_force_join' and user_id == OWNER_ID:
        update_force_join_status(True)
        safe_answer_callback(call, "✅ Force Join ဖွင့်")
        handle_settings(call.message)
    elif data == 'disable_force_join' and user_id == OWNER_ID:
        update_force_join_status(False)
        safe_answer_callback(call, "❌ Force Join ပိတ်")
        handle_settings(call.message)
    elif data == 'admin_back':
        handle_admin_panel(call.message)

def handle_manage_files_callback(call):
    user_id = call.from_user.id
    if not check_force_join_and_access(user_id):
        safe_answer_callback(call, "⛔ ဝင်ခွင့်မရှိပါ", show_alert=True); return
    files = user_files.get(user_id, [])
    if not files:
        safe_answer_callback(call, "📭 ဖိုင်မရှိပါ", show_alert=True); return
    text = "📁 <b>သင့်ဖိုင်များ:</b>\n\n"
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
        if target_id is None: safe_answer_callback(call, "❌ ဒေတာမှား", show_alert=True); return
        if call.from_user.id != target_id and call.from_user.id not in admin_ids:
            log_security_event(call.from_user.id, "UNAUTHORIZED_FILE_ACCESS", f"target={target_id} file={file_name}")
            safe_answer_callback(call, "❌ ငြင်းပယ်သည်", show_alert=True); return
        is_running = is_bot_running(target_id, file_name)
        icon = "🐍" if file_name.endswith('.py') else "🟨"
        text = f"{icon} <b>{html_module.escape(file_name)}</b>\n\n📊 {'🟢 လည်ပတ်နေသည်' if is_running else '🔴 ရပ်ထားသည်'}"
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
        if user_id is None: safe_answer_callback(call, "❌ ဒေတာမှား", show_alert=True); return
        if call.from_user.id != user_id and call.from_user.id not in admin_ids:
            safe_answer_callback(call, "❌ ငြင်းပယ်သည်", show_alert=True); return
        file_path = next((fp for fn,ft,fp in user_files.get(user_id,[]) if fn==file_name), None)
        if not file_path or not os.path.exists(file_path) or not is_safe_path(UPLOAD_BOTS_DIR, file_path):
            safe_answer_callback(call, "❌ ဖိုင်မတွေ့ပါ", show_alert=True); return
        ufolder = get_user_folder(user_id)
        ext = os.path.splitext(file_name)[1].lower()
        runner = run_python_script if ext == '.py' else run_js_script if ext == '.js' else None
        if not runner: safe_answer_callback(call, "❌ မသိ ဖိုင်အမျိုးအစား", show_alert=True); return
        threading.Thread(target=runner, args=(file_path, user_id, ufolder, file_name, call.message)).start()
        safe_answer_callback(call, "🚀 စတင်နေသည်...")
        time.sleep(4)
        call.data = f'file_{user_id}_{file_name}'
        handle_file_click(call)
    except Exception as e:
        safe_answer_callback(call, f"❌ {e}")

def handle_stop_file(call):
    try:
        user_id, file_name = parse_callback_data(call.data, 'stop_')
        if user_id is None: safe_answer_callback(call, "❌ ဒေတာမှား", show_alert=True); return
        key = f"{user_id}_{file_name}"
        with bot_scripts_lock:
            info = bot_scripts.get(key)
        if info: kill_process_tree(info)
        with bot_scripts_lock:
            bot_scripts.pop(key, None)
        safe_answer_callback(call, "⏸️ ရပ်နားပြီး")
        time.sleep(1)
        call.data = f'file_{user_id}_{file_name}'
        handle_file_click(call)
    except Exception as e:
        safe_answer_callback(call, f"❌ {e}")

def handle_restart_file(call):
    try:
        user_id, file_name = parse_callback_data(call.data, 'restart_')
        if user_id is None: safe_answer_callback(call, "❌ ဒေတာမှား", show_alert=True); return
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
            runner  = run_python_script if ext=='.py' else run_js_script if ext=='.js' else None
            if runner:
                threading.Thread(target=runner, args=(fp, user_id, ufolder, file_name, call.message)).start()
                safe_answer_callback(call, "🔄 ပြန်စတင်နေသည်...")
        else:
            safe_answer_callback(call, "❌ ဖိုင်မတွေ့ပါ", show_alert=True)
        time.sleep(4)
        call.data = f'file_{user_id}_{file_name}'
        handle_file_click(call)
    except Exception as e:
        safe_answer_callback(call, f"❌ {e}")

def handle_delete_file_callback(call):
    try:
        user_id, file_name = parse_callback_data(call.data, 'delete_')
        if user_id is None: safe_answer_callback(call, "❌ ဒေတာမှား", show_alert=True); return
        if call.from_user.id != user_id and call.from_user.id not in admin_ids:
            safe_answer_callback(call, "❌ ငြင်းပယ်သည်", show_alert=True); return
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
        safe_answer_callback(call, "🗑️ ဖျက်ပြီး")
        handle_manage_files_callback(call)
    except Exception as e:
        safe_answer_callback(call, f"❌ {e}")

def handle_logs_callback(call):
    try:
        user_id, file_name = parse_callback_data(call.data, 'logs_')
        if user_id is None: safe_answer_callback(call, "❌ ဒေတာမှား", show_alert=True); return
        if call.from_user.id != user_id and call.from_user.id not in admin_ids:
            safe_answer_callback(call, "❌ ငြင်းပယ်သည်", show_alert=True); return
        if send_log_file(user_id, file_name, call.message.chat.id):
            safe_answer_callback(call, "📋 Log ပို့ပြီး")
        else:
            safe_answer_callback(call, "📭 Log မရှိပါ", show_alert=True)
    except Exception as e:
        safe_answer_callback(call, f"❌ {e}")

def handle_download_callback(call):
    try:
        user_id, file_name = parse_callback_data(call.data, 'download_')
        if user_id is None: safe_answer_callback(call, "❌ ဒေတာမှား", show_alert=True); return
        if call.from_user.id != user_id and call.from_user.id not in admin_ids:
            log_security_event(call.from_user.id, "UNAUTHORIZED_DOWNLOAD", f"target={user_id} file={file_name}")
            safe_answer_callback(call, "❌ ငြင်းပယ်သည်", show_alert=True); return
        fp = next((p for n,t,p in user_files.get(user_id,[]) if n==file_name), None)
        if not fp or not os.path.exists(fp) or not is_safe_path(UPLOAD_BOTS_DIR, fp):
            safe_answer_callback(call, "❌ ဖိုင်မတွေ့ပါ", show_alert=True); return
        with open(fp, 'rb') as f:
            bot.send_document(call.message.chat.id, f, caption=f"📥 {html_module.escape(file_name)}")
        safe_answer_callback(call, "📥 ဖိုင်ပို့ပြီး")
    except Exception as e:
        safe_answer_callback(call, f"❌ {e}")

def handle_confirm_broadcast(call):
    if call.from_user.id not in admin_ids:
        safe_answer_callback(call, "❌ Admin သာ", show_alert=True); return
    try:
        msg_id = int(call.data.split('_')[-1])
        text   = broadcast_messages.get(msg_id, "")
        if not text: safe_answer_callback(call, "❌ စာမတွေ့ပါ"); return
        sent = failed = 0
        for uid in list(active_users):
            if is_user_banned(uid): continue
            try:
                bot.send_message(uid, text, parse_mode='HTML')
                sent += 1
                time.sleep(0.05)
            except Exception:
                failed += 1
        safe_answer_callback(call, f"✅ {sent} | ❌ {failed}")
        try: bot.edit_message_text(f"📢 ပြီးဆုံးပါပြီ\n✅ {sent}\n❌ {failed}",
                                   call.message.chat.id, call.message.message_id)
        except Exception: pass
        broadcast_messages.pop(msg_id, None)
    except Exception as e:
        safe_answer_callback(call, f"❌ {e}")

# ================================================================
#   PROCESS MONITOR (background thread)
# ================================================================
def _monitor_processes():
    """Periodically clean up dead processes and check resource abuse."""
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
                        # Kill if memory abuse
                        mem_mb = p.memory_info().rss / 1024 / 1024
                        if mem_mb > PROC_MAX_MEMORY_MB * 1.5:
                            uid = info.get('script_owner_id')
                            logger.warning(f"⚠️ Memory abuse: uid={uid} key={key} mem={mem_mb:.0f}MB — killing")
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
    logger.warning("🛑 Bot shutting down — cleaning up processes...")
    with bot_scripts_lock:
        for info in list(bot_scripts.values()):
            kill_process_tree(info)
        bot_scripts.clear()
    if conn:
        conn.close()
    logger.info("✅ Cleanup complete.")

atexit.register(cleanup)

# ================================================================
#   MAIN ENTRY POINT
# ================================================================
if __name__ == '__main__':
    logger.info("🚀 DEV-RAW Core v2.0 (Security Hardened) starting...")
    init_db()
    load_data()
    keep_alive()
    node_ok = install_nodejs()
    if not node_ok:
        logger.warning("⚠️ Node.js/npm not available — JS scripts disabled.")
    # Pre-fetch invite links
    for ch in force_channel_ids:
        get_or_create_invite_link(ch)
    if force_group_id:
        get_or_create_invite_link(force_group_id)
    # Start background monitor
    threading.Thread(target=_monitor_processes, daemon=True).start()
    logger.info("✅ Bot ready — polling started.")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=30, allowed_updates=['message','callback_query'])
        except Exception as e:
            logger.error(f"Polling error: {e}", exc_info=True)
            time.sleep(5)
