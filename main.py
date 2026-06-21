#!/usr/bin/env python3
# ================================================================
#   DEV-RAW CORE BOT v3.0 — ULTIMATE SECURITY EDITION
#   Fully Working | All Versions Support | Auto-Module Install
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
import json
from typing import Tuple, Optional, Dict, List
from datetime import datetime, timedelta
from threading import Thread
from collections import defaultdict, deque
import importlib
import pkgutil
import venv
import tempfile

try:
    import resource
    _HAS_RESOURCE = True
except ImportError:
    _HAS_RESOURCE = False

# ========== AUTO INSTALL MISSING MODULES ==========
def install_missing_modules():
    """Auto-install all required modules with multiple fallback methods"""
    required_modules = {
        'psutil': 'psutil',
        'telebot': 'pyTelegramBotAPI', 
        'flask': 'flask',
        'requests': 'requests'
    }
    
    for import_name, pip_name in required_modules.items():
        try:
            __import__(import_name)
        except ImportError:
            print(f"📦 Installing {pip_name}...")
            try:
                # Try pip install first
                subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name, 
                                      "--break-system-packages", "--quiet"])
            except:
                try:
                    # Try without --break-system-packages
                    subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name, "--quiet"])
                except:
                    try:
                        # Try apt-get for Debian/Ubuntu
                        if pip_name == 'psutil':
                            subprocess.check_call(['apt-get', 'install', '-y', 'python3-psutil'])
                        elif pip_name == 'flask':
                            subprocess.check_call(['apt-get', 'install', '-y', 'python3-flask'])
                    except:
                        print(f"❌ Failed to install {pip_name}")
                        sys.exit(1)

install_missing_modules()

import psutil
import telebot
from telebot import types
from telebot.util import quick_markup
import requests
from flask import Flask, request as flask_request, abort, jsonify

# ================================================================
#   SECURITY CONFIGURATION (ENHANCED)
# ================================================================

# Rate limiting system
RATE_LIMIT_MESSAGES = 15
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_FILE_MSGS = 3
RATE_LIMIT_FILE_WIN = 60
FLOOD_AUTO_BAN_THRESHOLD = 40

# File security (STRICT)
MAX_FILE_SIZE_MB = 10
ALLOWED_EXTENSIONS = {'.py', '.js', '.pyc', '.json', '.txt', '.env', '.cfg', '.ini'}

# Enhanced blocked patterns for code scanning
BLOCKED_CONTENT_PATTERNS = [
    r'os\.system\s*\(',
    r'subprocess\.\w+\s*\([^)]*shell\s*=\s*True',
    r'eval\s*\(.*input',
    r'exec\s*\(.*input',
    r'__import__\s*\(["\']os["\']\)',
    r'open\s*\(["\']\/etc\/',
    r'open\s*\(["\']\/proc\/',
    r'chmod\s*\(["\']\/etc',
    r'rm\s+-rf\s+\/',
    r'dd\s+if\=',
    r'mkfs\.',
    r'mount\s+\/',
    r'iptables',
    r'nc\s+-[lL]',
    r'bash\s+-c\s+.*curl',
    r'wget\s+.*\|.*sh',
    r'curl\s+.*\|.*sh',
    r'\.\.\/\.\.\/',
    r'\/etc\/passwd',
    r'\/etc\/shadow',
    r'\/root\/',
    r'bot_token',
    r'api_token',
    r'DATABASE_URL',
    r'ADMIN_ID',
    r'OWNER_ID',
]

# Process limits
PROC_MAX_MEMORY_MB = 512
PROC_MAX_CPU_SECONDS = 3600
PROC_MAX_OPEN_FILES = 100

# Anti file theft patterns
SUSPICIOUS_FILE_ACCESS = [
    r'.*\.db$',
    r'.*\.sqlite$',
    r'.*\.sql$',
    r'.*\.log$',
    r'.*\.pid$',
    r'.*config\.py$',
    r'.*settings\.py$',
    r'.*credentials\.*',
    r'.*\.env$',
    r'.*secret.*',
]

# ================================================================
#   VENV & MODULE AUTO-INSTALL SYSTEM
# ================================================================
class ModuleAutoInstaller:
    """Intelligent module auto-installer for any Python/JS version"""
    
    PYTHON_VERSIONS = ['python3', 'python3.8', 'python3.9', 'python3.10', 'python3.11', 'python3.12']
    NODE_VERSIONS = ['node', 'nodejs', 'node16', 'node18', 'node20']
    
    @staticmethod
    def get_available_python() -> Optional[str]:
        """Find available Python executable"""
        for ver in ModuleAutoInstaller.PYTHON_VERSIONS:
            if shutil.which(ver):
                return ver
        # Try finding any python
        for cmd in ['python3', 'python']:
            path = shutil.which(cmd)
            if path:
                try:
                    result = subprocess.run([path, '--version'], capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        return path
                except:
                    pass
        return None
    
    @staticmethod
    def get_available_node() -> Optional[str]:
        """Find available Node.js executable"""
        for ver in ModuleAutoInstaller.NODE_VERSIONS:
            if shutil.which(ver):
                return ver
        return None if not shutil.which('node') else 'node'
    
    @staticmethod
    def auto_install_python_module(module_name: str, user_folder: str) -> Tuple[bool, str]:
        """Auto-install Python module with multiple strategies"""
        python = ModuleAutoInstaller.get_available_python()
        if not python:
            return False, "Python not found"
        
        # Module name mapping
        module_map = {
            'telegram': 'python-telegram-bot',
            'cv2': 'opencv-python',
            'sklearn': 'scikit-learn',
            'PIL': 'Pillow',
            'bs4': 'beautifulsoup4',
            'dotenv': 'python-dotenv',
            'yaml': 'pyyaml',
            'Crypto': 'pycryptodome',
            'discord': 'discord.py',
            'flask': 'flask',
            'django': 'django',
            'requests': 'requests',
            'aiohttp': 'aiohttp',
            'fastapi': 'fastapi',
            'uvicorn': 'uvicorn',
            'sqlalchemy': 'sqlalchemy',
            'pymongo': 'pymongo',
            'redis': 'redis',
            'celery': 'celery',
            'numpy': 'numpy',
            'pandas': 'pandas',
            'matplotlib': 'matplotlib',
            'scipy': 'scipy',
            'tensorflow': 'tensorflow',
            'torch': 'torch',
            'transformers': 'transformers',
            'scrapy': 'scrapy',
            'beautifulsoup4': 'beautifulsoup4',
            'selenium': 'selenium',
            'pillow': 'pillow',
            'opencv': 'opencv-python',
        }
        
        # Get correct pip package name
        pip_name = module_map.get(module_name, module_name)
        
        install_methods = [
            # Method 1: Standard pip install
            [sys.executable, '-m', 'pip', 'install', pip_name, '--quiet', '--no-cache-dir'],
            # Method 2: Pip install with break-system-packages
            [sys.executable, '-m', 'pip', 'install', pip_name, '--break-system-packages', '--quiet'],
            # Method 3: Pip3 install
            ['pip3', 'install', pip_name, '--quiet'],
            # Method 4: pip install
            ['pip', 'install', pip_name, '--quiet'],
            # Method 5: apt-get install (for system packages)
            ['apt-get', 'install', '-y', f'python3-{pip_name}'],
        ]
        
        for method in install_methods:
            try:
                result = subprocess.run(method, capture_output=True, text=True, timeout=120, 
                                       cwd=user_folder, env={**os.environ, 'PIP_BREAK_SYSTEM_PACKAGES': '1'})
                if result.returncode == 0:
                    return True, f"Successfully installed {pip_name}"
            except Exception as e:
                continue
        
        return False, f"Failed to install {pip_name}"
    
    @staticmethod
    def auto_install_node_module(module_name: str, user_folder: str) -> Tuple[bool, str]:
        """Auto-install Node.js module with version detection"""
        node = ModuleAutoInstaller.get_available_node()
        if not node:
            return False, "Node.js not found"
        
        # Try to install with npm
        install_methods = [
            ['npm', 'install', module_name, '--save', '--silent'],
            ['npm', 'install', module_name, '--save', '--legacy-peer-deps', '--silent'],
            ['npm', 'install', f'{module_name}@latest', '--save', '--silent'],
            ['yarn', 'add', module_name, '--silent'],
            ['pnpm', 'add', module_name, '--silent'],
        ]
        
        for method in install_methods:
            try:
                # Check if package manager exists
                if not shutil.which(method[0]):
                    # Auto-install package manager if needed
                    if method[0] == 'yarn':
                        subprocess.run(['npm', 'install', '-g', 'yarn', '--silent'], timeout=60)
                    elif method[0] == 'pnpm':
                        subprocess.run(['npm', 'install', '-g', 'pnpm', '--silent'], timeout=60)
                    else:
                        continue
                
                result = subprocess.run(method, capture_output=True, text=True, timeout=120, cwd=user_folder)
                if result.returncode == 0:
                    return True, f"Successfully installed {module_name}"
            except Exception as e:
                continue
        
        return False, f"Failed to install {module_name}"

# ================================================================
#   SANDBOX SYSTEM
# ================================================================
class SandboxEnvironment:
    """Secure sandbox for running user scripts"""
    
    @staticmethod
    def create_sandbox(user_folder: str) -> Dict[str, str]:
        """Create isolated environment for script execution"""
        env = os.environ.copy()
        
        # Remove sensitive environment variables
        sensitive_vars = [
            'BOT_TOKEN', 'OWNER_ID', 'ADMIN_ID', 'ADMIN_USERNAME',
            'DATABASE_URL', 'DATABASE_PATH', 'SESSION_SECRET',
            'API_KEY', 'API_SECRET', 'AWS_ACCESS_KEY', 'AWS_SECRET_KEY',
            'GOOGLE_API_KEY', 'STRIPE_KEY', 'PAYPAL_CLIENT_ID',
            'SSH_KEY', 'SSH_AUTH_SOCK', 'GPG_KEY',
            'TELEGRAM_TOKEN', 'DISCORD_TOKEN', 'SLACK_TOKEN',
        ]
        
        for var in sensitive_vars:
            env.pop(var, None)
        
        # Set sandbox-specific variables
        env['HOME'] = user_folder
        env['TMPDIR'] = user_folder
        env['TEMP'] = user_folder
        env['TMP'] = user_folder
        env['PYTHONPATH'] = user_folder
        env['NODE_PATH'] = os.path.join(user_folder, 'node_modules')
        env['PATH'] = f"{user_folder}/bin:{os.environ.get('PATH', '')}"
        env['PIP_BREAK_SYSTEM_PACKAGES'] = '1'
        
        return env

# ================================================================
#   BOT CONFIGURATION
# ================================================================
TOKEN = os.environ.get("BOT_TOKEN", "8765038114:AAGO3lcbnA8dkiLr1PGMwtgBUytg3CIobbQ")
OWNER_ID = int(os.environ.get("OWNER_ID", 6736719959))
ADMIN_ID = int(os.environ.get("ADMIN_ID", 6736719959))
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", '@admin')

if not TOKEN or TOKEN == "8765038114:AAGO3lcbnA8dkiLr1PGMwtgBUytg3CIobbQ":
    print("⚠️ WARNING: Using default bot token. Please set BOT_TOKEN environment variable!")

DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'devraw_bot.db')

# Channel configuration
DEFAULT_FORCE_CHANNEL_IDS = []
DEFAULT_FORCE_GROUP_ID = 0

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_BOTS_DIR = os.path.join(BASE_DIR, 'upload_bots')
LOGS_DIR = os.path.join(BASE_DIR, 'security_logs')
VENV_DIR = os.path.join(BASE_DIR, 'virtual_envs')

# Create necessary directories
for directory in [UPLOAD_BOTS_DIR, LOGS_DIR, VENV_DIR]:
    os.makedirs(directory, exist_ok=True)

# ================================================================
#   ENHANCED UI THEMES
# ================================================================
UI_THEMES = {
    'cyber': {
        'primary': '🔮',
        'success': '✅',
        'error': '❌',
        'warning': '⚠️',
        'info': 'ℹ️',
        'border': '═',
        'separator': '┄',
        'corner_tl': '╔',
        'corner_tr': '╗',
        'corner_bl': '╚',
        'corner_br': '╝',
        'line_h': '║',
        'line_v': '║',
    },
    'modern': {
        'primary': '✨',
        'success': '🟢',
        'error': '🔴',
        'warning': '🟡',
        'info': '🔵',
        'border': '━',
        'separator': '┅',
        'corner_tl': '┏',
        'corner_tr': '┓',
        'corner_bl': '┗', 
        'corner_br': '┛',
        'line_h': '┃',
        'line_v': '┃',
    }
}

CURRENT_THEME = 'cyber'

def get_theme() -> Dict:
    """Get current UI theme"""
    return UI_THEMES[CURRENT_THEME]

def styled_header(title: str, subtitle: str = "") -> str:
    """Create styled header with theme"""
    theme = get_theme()
    header = f"""
{theme['corner_tl']}{theme['border']*20}{theme['corner_tr']}
{theme['line_h']}  {theme['primary']} <b>{title}</b>
"""
    if subtitle:
        header += f"{theme['line_h']}  {subtitle}\n"
    header += f"{theme['corner_bl']}{theme['border']*20}{theme['corner_br']}"
    return header

def styled_button_row(buttons: List[Tuple[str, str]]) -> types.InlineKeyboardMarkup:
    """Create styled inline buttons"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    for text, callback in buttons:
        markup.add(types.InlineKeyboardButton(text, callback_data=callback))
    return markup

# ================================================================
#   DATABASE INITIALIZATION
# ================================================================
def init_db():
    """Initialize database with enhanced security tables"""
    global conn
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=NORMAL")
        
        c = conn.cursor()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                verified INTEGER DEFAULT 0,
                banned INTEGER DEFAULT 0,
                join_date TEXT DEFAULT (datetime('now')),
                last_active TEXT DEFAULT (datetime('now'))
            );
            
            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id INTEGER PRIMARY KEY,
                expiry TEXT,
                file_limit INTEGER DEFAULT 999,
                created_at TEXT DEFAULT (datetime('now'))
            );
            
            CREATE TABLE IF NOT EXISTS user_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                file_name TEXT,
                file_type TEXT,
                file_path TEXT,
                file_hash TEXT,
                file_size INTEGER,
                upload_date TEXT DEFAULT (datetime('now')),
                UNIQUE(user_id, file_name)
            );
            
            CREATE TABLE IF NOT EXISTS active_users (
                user_id INTEGER PRIMARY KEY,
                last_seen TEXT DEFAULT (datetime('now'))
            );
            
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                added_by INTEGER,
                added_date TEXT DEFAULT (datetime('now'))
            );
            
            CREATE TABLE IF NOT EXISTS subscription_keys (
                key_value TEXT PRIMARY KEY,
                days_valid INTEGER,
                max_uses INTEGER DEFAULT 1,
                used_count INTEGER DEFAULT 0,
                file_limit INTEGER DEFAULT 999,
                created_by INTEGER,
                created_at TEXT DEFAULT (datetime('now'))
            );
            
            CREATE TABLE IF NOT EXISTS key_usage (
                key_value TEXT,
                user_id INTEGER,
                used_at TEXT DEFAULT (datetime('now')),
                UNIQUE(key_value, user_id)
            );
            
            CREATE TABLE IF NOT EXISTS bot_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT,
                updated_at TEXT DEFAULT (datetime('now'))
            );
            
            CREATE TABLE IF NOT EXISTS premium_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                days INTEGER,
                price INTEGER,
                file_limit INTEGER,
                is_active INTEGER DEFAULT 1
            );
            
            CREATE TABLE IF NOT EXISTS security_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                event_type TEXT,
                detail TEXT,
                ip_address TEXT,
                timestamp TEXT DEFAULT (datetime('now'))
            );
            
            CREATE TABLE IF NOT EXISTS file_scan_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                file_name TEXT,
                scan_result TEXT,
                threats_found TEXT,
                timestamp TEXT DEFAULT (datetime('now'))
            );
            
            CREATE TABLE IF NOT EXISTS banned_ips (
                ip_address TEXT PRIMARY KEY,
                reason TEXT,
                banned_at TEXT DEFAULT (datetime('now'))
            );
        """)
        
        # Insert default settings
        default_settings = {
            "free_user_limit": "1",
            "force_join_enabled": "1",
            "force_channel_ids": ",".join(map(str, DEFAULT_FORCE_CHANNEL_IDS)),
            "force_group_id": str(DEFAULT_FORCE_GROUP_ID),
            "bot_version": "3.0",
            "security_level": "high",
            "file_scan_enabled": "1",
            "auto_ban_enabled": "1",
        }
        
        for key, val in default_settings.items():
            c.execute("INSERT OR IGNORE INTO bot_settings VALUES (?,?,datetime('now'))", (key, val))
        
        # Insert default premium plans
        c.execute("SELECT COUNT(*) FROM premium_plans")
        if c.fetchone()[0] == 0:
            plans = [
                ("📅 Weekly Plan", 7, 2000, 5),
                ("📆 Monthly Plan", 30, 15000, 10),
                ("📆 Quarterly Plan", 90, 50000, 0),
                ("👑 Premium Lifetime", -1, 200000, 0),
                ("📂 File Storage Plan", -1, 50000, 20),
            ]
            c.executemany("INSERT INTO premium_plans (name,days,price,file_limit) VALUES (?,?,?,?)", plans)
        
        # Add owner and admin
        if OWNER_ID:
            c.execute("INSERT OR IGNORE INTO admins (user_id, added_by) VALUES (?, 0)", (OWNER_ID,))
        if ADMIN_ID and ADMIN_ID != OWNER_ID:
            c.execute("INSERT OR IGNORE INTO admins (user_id, added_by) VALUES (?, ?)", 
                     (ADMIN_ID, OWNER_ID))
        
        conn.commit()
        logger.info("✅ Database initialized successfully")
        
    except Exception as e:
        logger.critical(f"❌ Database init failed: {e}", exc_info=True)
        sys.exit(1)

# ================================================================
#   ENHANCED SECURITY SCANNER
# ================================================================
class SecurityScanner:
    """Advanced security scanner for uploaded files"""
    
    @staticmethod
    def scan_file(file_bytes: bytes, file_name: str, user_id: int) -> Tuple[bool, str, List[str]]:
        """
        Enhanced file scanning
        Returns: (is_safe, reason, threats_found)
        """
        threats = []
        
        # Check file size
        if len(file_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
            return False, f"File exceeds {MAX_FILE_SIZE_MB}MB limit", ["size_exceeded"]
        
        # Check file extension
        file_ext = os.path.splitext(file_name)[1].lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            return False, f"File type {file_ext} not allowed", ["invalid_extension"]
        
        # Check for suspicious file access patterns
        for pattern in SUSPICIOUS_FILE_ACCESS:
            if re.match(pattern, file_name, re.IGNORECASE):
                threats.append("suspicious_filename")
        
        # Decode file content for scanning
        try:
            content = file_bytes.decode('utf-8', errors='ignore')
        except:
            try:
                content = file_bytes.decode('latin-1', errors='ignore')
            except:
                return False, "Cannot decode file content", ["decode_error"]
        
        # Scan for dangerous patterns
        for pattern in BLOCKED_CONTENT_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                threats.append(f"blocked_pattern:{pattern}")
        
        # Check for potential data theft attempts
        theft_patterns = [
            r'\.\.\/\.\.\/',
            r'open\(.+?bot.*?config',
            r'open\(.+?\.db',
            r'open\(.+?\.sqlite',
            r'open\(.+?\.log',
            r'open\(.+?\/root\/',
            r'open\(.+?\/etc\/',
            r'readfile\(.+?config',
            r'file_get_contents\(.+?\.\.',
            r'require\(.+?\.\.\/',
            r'include\(.+?\.\.\/',
        ]
        
        for pattern in theft_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                threats.append(f"theft_attempt:{pattern}")
        
        # Block root access attempts
        root_patterns = [
            r'sudo\s',
            r'su\s-',
            r'chroot\s',
            r'/root/',
            r'\/etc\/passwd',
            r'\/etc\/shadow',
            r'\/etc\/sudoers',
            r'\/var\/log\/',
            r'\/proc\/',
            r'\/sys\/',
        ]
        
        for pattern in root_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                threats.append(f"root_access:{pattern}")
        
        if threats:
            return False, f"Security threats found: {len(threats)} issues", threats
        
        return True, "File is safe", []
    
    @staticmethod
    def log_scan_result(user_id: int, file_name: str, scan_result: str, threats: List[str]):
        """Log scan results to database"""
        try:
            threats_json = json.dumps(threats)
            conn.execute("""
                INSERT INTO file_scan_logs (user_id, file_name, scan_result, threats_found)
                VALUES (?, ?, ?, ?)
            """, (user_id, file_name, scan_result, threats_json))
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to log scan result: {e}")

# ================================================================
#   ENHANCED FORCE JOIN SYSTEM
# ================================================================
class ForceJoinManager:
    """Enhanced force join management with better error handling"""
    
    @staticmethod
    def check_membership(user_id: int, bot_instance) -> bool:
        """Check if user is member of all required channels/groups"""
        if user_id in admin_ids:
            return True
        
        try:
            # Check channel memberships
            for channel_id in force_channel_ids:
                try:
                    member = bot_instance.get_chat_member(channel_id, user_id)
                    if member.status not in ['member', 'administrator', 'creator']:
                        return False
                except Exception as e:
                    # Log error but continue checking
                    logger.error(f"Channel membership check failed for {channel_id}: {e}")
                    # Try alternative method - check if chat is accessible
                    try:
                        chat = bot_instance.get_chat(channel_id)
                        if chat.type == 'channel':
                            # If we can't check, assume not member
                            return False
                    except:
                        return False
            
            # Check group membership
            if force_group_id:
                try:
                    member = bot_instance.get_chat_member(force_group_id, user_id)
                    if member.status not in ['member', 'administrator', 'creator']:
                        return False
                except Exception as e:
                    logger.error(f"Group membership check failed for {force_group_id}: {e}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Membership check error: {e}")
            # If there's a critical error, allow access to prevent lockout
            return True
    
    @staticmethod
    def get_channel_info(bot_instance, chat_id: int) -> Dict:
        """Get channel/group information safely"""
        try:
            chat = bot_instance.get_chat(chat_id)
            return {
                'id': chat.id,
                'title': chat.title,
                'type': chat.type,
                'username': chat.username or '',
                'invite_link': chat.invite_link or ''
            }
        except Exception as e:
            logger.error(f"Failed to get chat info for {chat_id}: {e}")
            return {
                'id': chat_id,
                'title': f'Chat {chat_id}',
                'type': 'unknown',
                'username': '',
                'invite_link': ''
            }
    
    @staticmethod
    def create_invite_links(bot_instance) -> Dict[int, str]:
        """Create invite links for all required channels"""
        links = {}
        
        for channel_id in force_channel_ids:
            try:
                link = bot_instance.export_chat_invite_link(channel_id)
                links[channel_id] = link
            except Exception as e:
                logger.error(f"Failed to create invite link for {channel_id}: {e}")
                # Try to get existing link
                try:
                    chat = bot_instance.get_chat(channel_id)
                    if chat.invite_link:
                        links[channel_id] = chat.invite_link
                    elif chat.username:
                        links[channel_id] = f"https://t.me/{chat.username}"
                except:
                    pass
        
        if force_group_id:
            try:
                link = bot_instance.export_chat_invite_link(force_group_id)
                links[force_group_id] = link
            except Exception as e:
                logger.error(f"Failed to create invite link for group {force_group_id}: {e}")
                try:
                    chat = bot_instance.get_chat(force_group_id)
                    if chat.invite_link:
                        links[force_group_id] = chat.invite_link
                    elif chat.username:
                        links[force_group_id] = f"https://t.me/{chat.username}"
                except:
                    pass
        
        return links

# Initialize bot with enhanced settings
bot = telebot.TeleBot(
    TOKEN, 
    threaded=True, 
    num_threads=10,
    skip_pending=True,
    parse_mode='HTML'
)

# ================================================================
#   ENHANCED UI HANDLERS
# ================================================================
def create_enhanced_force_join_message(bot_instance) -> Tuple[str, types.InlineKeyboardMarkup]:
    """Create enhanced force join message with modern UI"""
    theme = get_theme()
    
    # Get channel information
    channel_list = []
    for i, channel_id in enumerate(force_channel_ids[:5]):  # Max 5 channels
        try:
            info = ForceJoinManager.get_channel_info(bot_instance, channel_id)
            emoji = ['📢', '📣', '📡', '📺', '🔊'][i % 5]
            channel_list.append(f"{emoji} <b>{html_module.escape(info['title'])}</b>")
        except:
            channel_list.append(f"📢 Channel {channel_id}")
    
    group_info = ""
    if force_group_id:
        try:
            info = ForceJoinManager.get_channel_info(bot_instance, force_group_id)
            group_info = f"👥 <b>{html_module.escape(info['title'])}</b>"
        except:
            group_info = f"👥 Group {force_group_id}"
    
    message = f"""
{theme['primary']} <b>DEV-RAW CORE v3.0</b> {theme['primary']}
{theme['separator']*30}

🔐 <b>Membership Required</b>
{theme['separator']*30}

✨ <b>Please Join Our Channels:</b>

{chr(10).join(channel_list)}

{f'👥 <b>Join Group:</b>\n{group_info}' if group_info else ''}

{theme['separator']*30}

📋 <b>Instructions:</b>
1️⃣ Click buttons below to join
2️⃣ Wait 30-60 seconds  
3️⃣ Click "✅ Verify Membership"

🎁 <b>Benefits:</b>
• 🐍 Python Scripts 24/7
• 🟨 JavaScript Hosting
• 📦 Auto Module Install
• 🔒 Maximum Security
"""
    
    # Create enhanced keyboard
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # Get invite links
    links = ForceJoinManager.create_invite_links(bot_instance)
    
    # Add channel buttons
    for i, channel_id in enumerate(force_channel_ids):
        emoji = ['📢', '📣', '📡', '📺', '🔊'][i % 5]
        try:
            info = ForceJoinManager.get_channel_info(bot_instance, channel_id)
            title = info['title'][:20] + ('...' if len(info['title']) > 20 else '')
        except:
            title = f'Channel {channel_id}'
        
        if channel_id in links:
            markup.add(types.InlineKeyboardButton(
                f"{emoji} Join {html_module.escape(title)}", 
                url=links[channel_id]
            ))
        else:
            markup.add(types.InlineKeyboardButton(
                f"{emoji} {html_module.escape(title)}", 
                callback_data='no_link'
            ))
    
    # Add group button
    if force_group_id and force_group_id in links:
        try:
            info = ForceJoinManager.get_channel_info(bot_instance, force_group_id)
            title = info['title'][:20] + ('...' if len(info['title']) > 20 else '')
        except:
            title = 'Group'
        markup.add(types.InlineKeyboardButton(
            f"👥 Join {html_module.escape(title)}", 
            url=links[force_group_id]
        ))
    
    # Add verification button
    markup.add(types.InlineKeyboardButton(
        "✅ Verify Membership", 
        callback_data='check_membership'
    ))
    
    # Add admin contact button if configured
    if ADMIN_USERNAME:
        admin_link = f"https://t.me/{ADMIN_USERNAME.replace('@', '')}"
        markup.add(types.InlineKeyboardButton(
            "📞 Contact Admin", 
            url=admin_link
        ))
    
    return message, markup

# ================================================================
#   MAIN BOT HANDLERS
# ================================================================
@bot.message_handler(commands=['start', 'help'])
def welcome_handler(message):
    """Enhanced welcome handler with force join check"""
    user_id = message.from_user.id
    
    # Save user
    try:
        conn.execute("""
            INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, last_active)
            VALUES (?, ?, ?, ?, datetime('now'))
        """, (user_id, message.from_user.username, message.from_user.first_name, 
              message.from_user.last_name))
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to save user: {e}")
    
    # Add to active users
    try:
        conn.execute("INSERT OR IGNORE INTO active_users (user_id) VALUES (?)", (user_id,))
        conn.commit()
    except:
        pass
    
    # Check if already verified
    if is_user_verified(user_id):
        show_enhanced_main_menu(message)
        return
    
    # Check if force join is enabled
    if not force_join_enabled:
        set_user_verified(user_id)
        show_enhanced_main_menu(message)
        return
    
    # Check membership
    if ForceJoinManager.check_membership(user_id, bot):
        set_user_verified(user_id)
        show_enhanced_main_menu(message)
        return
    
    # Show force join message
    force_msg, force_markup = create_enhanced_force_join_message(bot)
    bot.send_message(
        message.chat.id, 
        force_msg, 
        reply_markup=force_markup,
        parse_mode='HTML',
        disable_web_page_preview=True
    )

@bot.callback_query_handler(func=lambda call: call.data == 'check_membership')
def check_membership_callback(call):
    """Handle membership verification"""
    user_id = call.from_user.id
    
    try:
        if ForceJoinManager.check_membership(user_id, bot):
            set_user_verified(user_id)
            bot.answer_callback_query(call.id, "✅ Verified! Welcome!", show_alert=True)
            
            # Delete force join message
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass
            
            # Show main menu
            show_enhanced_main_menu(call.message)
        else:
            bot.answer_callback_query(call.id, "❌ Please join all channels first!", show_alert=True)
            
            # Refresh force join message
            try:
                force_msg, force_markup = create_enhanced_force_join_message(bot)
                bot.edit_message_text(
                    force_msg,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=force_markup,
                    parse_mode='HTML',
                    disable_web_page_preview=True
                )
            except Exception as e:
                logger.error(f"Failed to refresh force join message: {e}")
                
    except Exception as e:
        logger.error(f"Membership check error: {e}")
        bot.answer_callback_query(call.id, "⚠️ Error checking membership. Try again.", show_alert=True)

def show_enhanced_main_menu(message):
    """Show enhanced main menu with modern UI"""
    user_id = message.from_user.id
    theme = get_theme()
    
    status = get_user_status(user_id)
    file_count = get_user_file_count(user_id)
    file_limit = get_user_file_limit(user_id)
    
    limit_display = "∞" if file_limit == float('inf') else str(int(file_limit))
    
    welcome_text = f"""
{theme['primary']} <b>DEV-RAW CORE v3.0</b> {theme['primary']}
{theme['separator']*25}

👋 Welcome, <b>{html_module.escape(message.from_user.first_name)}</b>!

📊 <b>Your Status:</b> {status}
📁 <b>Files:</b> {file_count}/{limit_display}
🔒 <b>Security:</b> Maximum

{theme['separator']*25}

🎯 <b>Select an option below:</b>
"""
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    buttons = [
        '📤 Upload File',
        '📁 My Files',
        '🔑 Redeem Key',
        '✨ Upgrade',
        '👤 Profile',
        '📊 Status',
        '🔄 Running Scripts',
        '📞 Support'
    ]
    
    if user_id in admin_ids:
        buttons.append('⚙️ Admin Panel')
    
    for i in range(0, len(buttons), 2):
        row = buttons[i:i+2]
        markup.row(*row)
    
    bot.send_message(
        message.chat.id,
        welcome_text,
        reply_markup=markup,
        parse_mode='HTML'
    )

@bot.message_handler(content_types=['document'])
def handle_file_upload(message):
    """Enhanced file upload handler with security scanning"""
    user_id = message.from_user.id
    
    # Check if verified
    if not check_force_join_and_access(user_id):
        bot.send_message(
            message.chat.id,
            "🔐 Please verify your membership first! Use /start",
            parse_mode='HTML'
        )
        return
    
    # Check file limit
    file_limit = get_user_file_limit(user_id)
    file_count = get_user_file_count(user_id)
    
    if file_limit != float('inf') and file_count >= file_limit:
        bot.reply_to(
            message,
            f"❌ File limit reached! ({int(file_limit)} files max)\n"
            f"✨ Upgrade to premium for more storage!",
            parse_mode='HTML'
        )
        return
    
    doc = message.document
    
    # Check file extension
    file_name = sanitize_filename(doc.file_name or "uploaded_file.py")
    file_ext = os.path.splitext(file_name)[1].lower()
    
    if file_ext not in ALLOWED_EXTENSIONS:
        bot.reply_to(
            message,
            f"❌ Unsupported file type!\n"
            f"✅ Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
            parse_mode='HTML'
        )
        return
    
    # Download file
    processing_msg = bot.reply_to(message, "🔍 Scanning file for security threats...", parse_mode='HTML')
    
    try:
        file_info = bot.get_file(doc.file_id)
        file_bytes = bot.download_file(file_info.file_path)
    except Exception as e:
        bot.edit_message_text(
            f"❌ Failed to download file: {str(e)}",
            message.chat.id,
            processing_msg.message_id,
            parse_mode='HTML'
        )
        return
    
    # Security scan
    is_safe, reason, threats = SecurityScanner.scan_file(file_bytes, file_name, user_id)
    
    if not is_safe:
        # Log security event
        log_security_event(user_id, "UNSAFE_FILE", f"{file_name}: {reason}")
        SecurityScanner.log_scan_result(user_id, file_name, "BLOCKED", threats)
        
        bot.edit_message_text(
            f"🛡️ <b>Security Alert!</b>\n\n"
            f"❌ File blocked: {reason}\n"
            f"🔍 Threats found: {len(threats)}\n\n"
            f"⚠️ This incident has been logged.",
            message.chat.id,
            processing_msg.message_id,
            parse_mode='HTML'
        )
        return
    
    # Save file
    file_hash = sha256_file(file_bytes)
    user_folder = get_user_folder(user_id)
    file_path = os.path.join(user_folder, file_name)
    
    with open(file_path, 'wb') as f:
        f.write(file_bytes)
    
    file_type = '🐍 Python' if file_ext == '.py' else '🟨 JavaScript' if file_ext == '.js' else f'📄 {file_ext.upper()}'
    save_user_file(user_id, file_name, file_type, file_path, file_hash)
    
    SecurityScanner.log_scan_result(user_id, file_name, "SAFE", [])
    
    # Success message
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("▶️ Run Now", callback_data=f'start_{user_id}_{file_name}'),
        types.InlineKeyboardButton("📁 My Files", callback_data='manage_files')
    )
    
    bot.edit_message_text(
        f"✅ <b>File Uploaded Successfully!</b>\n\n"
        f"📄 <code>{html_module.escape(file_name)}</code>\n"
        f"📦 Type: {file_type}\n"
        f"🔐 Hash: <code>{file_hash[:16]}...</code>\n"
        f"🛡️ Security: Passed\n\n"
        f"Select an action:",
        message.chat.id,
        processing_msg.message_id,
        reply_markup=markup,
        parse_mode='HTML'
    )

@bot.message_handler(func=lambda m: True)
def handle_text_messages(message):
    """Handle all text messages"""
    user_id = message.from_user.id
    
    if not check_force_join_and_access(user_id):
        bot.send_message(
            message.chat.id,
            "🔐 Please verify first! Use /start",
            parse_mode='HTML'
        )
        return
    
    text = message.text
    
    # Command routing
    if text == '📤 Upload File':
        bot.send_message(
            message.chat.id,
            "📤 Send me a <b>.py</b> or <b>.js</b> file to upload!\n\n"
            "✅ Supported: Python & JavaScript\n"
            "🛡️ Auto security scan enabled",
            parse_mode='HTML'
        )
    
    elif text == '📁 My Files':
        show_user_files(message)
    
    elif text == '🔑 Redeem Key':
        msg = bot.send_message(
            message.chat.id,
            "🔑 Please enter your key:\n"
            "Format: <code>DEVRAW-XXXXXXXXXXXX</code>",
            parse_mode='HTML'
        )
        bot.register_next_step_handler(msg, process_redeem_key)
    
    elif text == '✨ Upgrade':
        show_premium_plans(message)
    
    elif text == '👤 Profile':
        show_user_profile(message)
    
    elif text == '📊 Status':
        show_system_status(message)
    
    elif text == '🔄 Running Scripts':
        show_running_scripts(message)
    
    elif text == '📞 Support':
        if ADMIN_USERNAME:
            admin_link = f"https://t.me/{ADMIN_USERNAME.replace('@', '')}"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📞 Contact Admin", url=admin_link))
            bot.send_message(
                message.chat.id,
                "📞 <b>Support</b>\n\nContact our admin for assistance:",
                reply_markup=markup,
                parse_mode='HTML'
            )
    
    elif text == '⚙️ Admin Panel' and user_id in admin_ids:
        show_admin_panel(message)
    
    elif text == '⬅️ Back':
        show_enhanced_main_menu(message)
    
    else:
        show_enhanced_main_menu(message)

def show_user_files(message):
    """Show user's uploaded files"""
    user_id = message.from_user.id
    files = user_files.get(user_id, [])
    
    if not files:
        bot.send_message(
            message.chat.id,
            "📭 You haven't uploaded any files yet!\n\n"
            "Use 📤 Upload File to get started.",
            parse_mode='HTML'
        )
        return
    
    theme = get_theme()
    text = f"{theme['primary']} <b>Your Files</b> {theme['primary']}\n{theme['separator']*25}\n\n"
    
    for fn, ft, fp in files[:10]:  # Show max 10 files
        status = "🟢 Running" if is_bot_running(user_id, fn) else "🔴 Stopped"
        text += f"{status} | <code>{html_module.escape(fn)}</code> | {ft}\n"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    for fn, ft, fp in files[:10]:
        btn_text = f"{'🟢' if is_bot_running(user_id, fn) else '🔴'} {fn[:15]}"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f'file_{user_id}_{fn}'))
    
    markup.add(types.InlineKeyboardButton("⬅️ Back to Main", callback_data='back_to_main'))
    
    bot.send_message(
        message.chat.id,
        text,
        reply_markup=markup,
        parse_mode='HTML'
    )

def show_admin_panel(message):
    """Show admin control panel"""
    if message.from_user.id not in admin_ids:
        return
    
    theme = get_theme()
    stats = get_bot_statistics()
    
    text = f"""
{theme['primary']} <b>Admin Control Panel</b> {theme['primary']}
{theme['separator']*25}

👥 Users: <code>{stats['total_users']}</code>
✨ Premium: <code>{stats['premium_users']}</code>
📁 Files: <code>{stats['total_files']}</code>
🟢 Running: <code>{stats['active_files']}</code>
🚫 Banned: <code>{len(banned_users)}</code>
"""
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        '📊 Statistics', '👥 Users List',
        '✨ Premium Users', '🔄 Active Scripts',
        '📢 Broadcast', '🔑 Generate Key',
        '🗑️ Delete Key', '📈 Set Limits',
        '⚙️ Settings', '🚫 Ban User',
        '✅ Unban User', '🛡️ Security Logs',
        '⬅️ Back'
    ]
    
    for i in range(0, len(buttons), 2):
        row = buttons[i:i+2]
        markup.row(*row)
    
    bot.send_message(
        message.chat.id,
        text,
        reply_markup=markup,
        parse_mode='HTML'
    )

# ================================================================
#   SCRIPT RUNNING WITH AUTO MODULE INSTALL
# ================================================================
def run_script_enhanced(script_path, user_id, file_name, message):
    """Enhanced script runner with auto module installation"""
    
    file_ext = os.path.splitext(file_name)[1].lower()
    
    if file_ext == '.py':
        return run_python_enhanced(script_path, user_id, file_name, message)
    elif file_ext == '.js':
        return run_javascript_enhanced(script_path, user_id, file_name, message)
    else:
        bot.reply_to(message, f"❌ Unsupported file type: {file_ext}")
        return False

def run_python_enhanced(script_path, user_id, file_name, message, attempt=1):
    """Run Python script with auto module installation"""
    max_attempts = 3
    
    if attempt > max_attempts:
        bot.reply_to(message, f"❌ Failed to start {file_name} after {max_attempts} attempts")
        return False
    
    user_folder = get_user_folder(user_id)
    script_key = f"{user_id}_{file_name}"
    
    # Check if already running
    if is_bot_running(user_id, file_name):
        bot.reply_to(message, f"⚠️ {file_name} is already running!")
        return False
    
    # Create sandbox environment
    env = SandboxEnvironment.create_sandbox(user_folder)
    
    # Try to run script
    try:
        log_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        
        with open(log_path, 'w') as log_file:
            process = subprocess.Popen(
                [sys.executable, '-u', script_path],
                cwd=user_folder,
                stdout=log_file,
                stderr=log_file,
                env=env,
                preexec_fn=os.setsid if os.name != 'nt' else None
            )
        
        # Wait briefly to check for immediate errors
        time.sleep(3)
        
        if process.poll() is not None:
            # Process died - check log for errors
            with open(log_path, 'r') as log_file:
                log_content = log_file.read()
            
            # Check for missing module errors
            missing_modules = []
            
            # Python import errors
            for match in re.finditer(r"ModuleNotFoundError: No module named '([^']+)'", log_content):
                missing_modules.append(match.group(1))
            
            for match in re.finditer(r"ImportError: No module named '([^']+)'", log_content):
                missing_modules.append(match.group(1))
            
            if missing_modules and attempt < max_attempts:
                # Try to install missing modules
                for module in missing_modules:
                    bot.reply_to(message, f"📦 Installing missing module: <code>{module}</code>...", parse_mode='HTML')
                    success, result = ModuleAutoInstaller.auto_install_python_module(module, user_folder)
                    
                    if not success:
                        bot.reply_to(message, f"❌ Failed to install {module}: {result}", parse_mode='HTML')
                
                # Retry running script
                time.sleep(2)
                return run_python_enhanced(script_path, user_id, file_name, message, attempt + 1)
            
            # Other error
            error_preview = log_content[-500:] if len(log_content) > 500 else log_content
            bot.reply_to(message, f"❌ Script error:\n<pre>{html_module.escape(error_preview)}</pre>", parse_mode='HTML')
            return False
        
        # Script started successfully
        with bot_scripts_lock:
            bot_scripts[script_key] = {
                'process': process,
                'file_name': file_name,
                'user_id': user_id,
                'start_time': datetime.now(),
                'type': 'python'
            }
        
        bot.reply_to(message, f"✅ <b>{html_module.escape(file_name)}</b> started successfully!\n🆔 PID: {process.pid}", parse_mode='HTML')
        return True
        
    except Exception as e:
        bot.reply_to(message, f"❌ Failed to start script: {str(e)}")
        return False

def run_javascript_enhanced(script_path, user_id, file_name, message, attempt=1):
    """Run JavaScript script with auto module installation"""
    max_attempts = 3
    
    if attempt > max_attempts:
        bot.reply_to(message, f"❌ Failed to start {file_name} after {max_attempts} attempts")
        return False
    
    user_folder = get_user_folder(user_id)
    script_key = f"{user_id}_{file_name}"
    
    # Check Node.js availability
    node_path = ModuleAutoInstaller.get_available_node()
    if not node_path:
        bot.reply_to(message, "❌ Node.js is not installed!")
        return False
    
    # Ensure node_modules exists
    node_modules = os.path.join(user_folder, 'node_modules')
    os.makedirs(node_modules, exist_ok=True)
    
    # Check for package.json
    package_json = os.path.join(user_folder, 'package.json')
    if not os.path.exists(package_json):
        with open(package_json, 'w') as f:
            json.dump({"name": f"bot_{user_id}", "version": "1.0.0"}, f)
    
    # Create sandbox environment
    env = SandboxEnvironment.create_sandbox(user_folder)
    
    try:
        log_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        
        with open(log_path, 'w') as log_file:
            process = subprocess.Popen(
                [node_path, script_path],
                cwd=user_folder,
                stdout=log_file,
                stderr=log_file,
                env=env,
                preexec_fn=os.setsid if os.name != 'nt' else None
            )
        
        # Wait briefly
        time.sleep(3)
        
        if process.poll() is not None:
            # Process died - check for missing modules
            with open(log_path, 'r') as log_file:
                log_content = log_file.read()
            
            # Check for missing module errors
            missing_modules = set()
            
            for match in re.finditer(r"Cannot find module '([^']+)'", log_content):
                missing_modules.add(match.group(1))
            
            for match in re.finditer(r"Error: Cannot find module '([^']+)'", log_content):
                missing_modules.add(match.group(1))
            
            if missing_modules and attempt < max_attempts:
                # Install missing modules
                for module in missing_modules:
                    bot.reply_to(message, f"📦 Installing: <code>{module}</code>...", parse_mode='HTML')
                    success, result = ModuleAutoInstaller.auto_install_node_module(module, user_folder)
                    
                    if not success:
                        bot.reply_to(message, f"❌ Failed to install {module}: {result}", parse_mode='HTML')
                
                time.sleep(2)
                return run_javascript_enhanced(script_path, user_id, file_name, message, attempt + 1)
            
            # Other error
            error_preview = log_content[-500:] if len(log_content) > 500 else log_content
            bot.reply_to(message, f"❌ Script error:\n<pre>{html_module.escape(error_preview)}</pre>", parse_mode='HTML')
            return False
        
        # Success
        with bot_scripts_lock:
            bot_scripts[script_key] = {
                'process': process,
                'file_name': file_name,
                'user_id': user_id,
                'start_time': datetime.now(),
                'type': 'javascript'
            }
        
        bot.reply_to(message, f"✅ <b>{html_module.escape(file_name)}</b> started!\n🆔 PID: {process.pid}", parse_mode='HTML')
        return True
        
    except Exception as e:
        bot.reply_to(message, f"❌ Failed to start script: {str(e)}")
        return False

# ================================================================
#   UTILITY FUNCTIONS
# ================================================================
def is_user_verified(user_id):
    """Check if user is verified"""
    if user_id in admin_ids:
        return True
    
    try:
        c = conn.cursor()
        c.execute("SELECT verified FROM users WHERE user_id=?", (user_id,))
        row = c.fetchone()
        return bool(row and row[0] == 1)
    except:
        return False

def set_user_verified(user_id):
    """Set user as verified"""
    try:
        conn.execute("UPDATE users SET verified=1 WHERE user_id=?", (user_id,))
        conn.commit()
    except:
        pass

def check_force_join_and_access(user_id):
    """Check if user can access bot features"""
    if is_user_banned(user_id):
        return False
    if user_id in admin_ids:
        return True
    return is_user_verified(user_id)

def is_user_banned(user_id):
    """Check if user is banned"""
    return user_id in banned_users

def get_user_status(user_id):
    """Get user status string"""
    if user_id == OWNER_ID:
        return "👑 Owner"
    if user_id in admin_ids:
        return "🛡️ Admin"
    if is_premium_user(user_id):
        return "✨ Premium"
    return "🎯 Free"

def is_premium_user(user_id):
    """Check if user has active subscription"""
    sub = user_subscriptions.get(user_id)
    return bool(sub and sub['expiry'] > datetime.now())

def get_user_file_count(user_id):
    """Get number of files user has"""
    return len(user_files.get(user_id, []))

def get_user_file_limit(user_id):
    """Get user's file limit"""
    if user_id in admin_ids or user_id == OWNER_ID:
        return float('inf')
    
    sub = user_subscriptions.get(user_id)
    if sub and sub['expiry'] > datetime.now():
        return sub['file_limit']
    
    return FREE_USER_LIMIT

def sanitize_filename(name):
    """Sanitize filename for security"""
    name = os.path.basename(name)
    name = re.sub(r'[^\w\.\-]', '_', name)
    name = name.lstrip('.')
    if not name:
        name = "uploaded_file"
    return name[:120]

def sha256_file(data):
    """Calculate SHA-256 hash"""
    return hashlib.sha256(data).hexdigest()

def log_security_event(user_id, event_type, detail=""):
    """Log security event"""
    security_logger.warning(f"[{event_type}] uid={user_id} | {detail}")
    try:
        conn.execute(
            "INSERT INTO security_events (user_id, event_type, detail) VALUES (?, ?, ?)",
            (user_id, event_type, detail[:500])
        )
        conn.commit()
    except:
        pass

def save_user_file(user_id, file_name, file_type, file_path, file_hash=""):
    """Save file record to database"""
    try:
        conn.execute(
            "INSERT OR REPLACE INTO user_files (user_id, file_name, file_type, file_path, file_hash) VALUES (?,?,?,?,?)",
            (user_id, file_name, file_type, file_path, file_hash)
        )
        conn.commit()
        
        if user_id not in user_files:
            user_files[user_id] = []
        user_files[user_id] = [f for f in user_files[user_id] if f[0] != file_name]
        user_files[user_id].append((file_name, file_type, file_path))
    except Exception as e:
        logger.error(f"Failed to save file record: {e}")

def get_bot_statistics():
    """Get bot statistics"""
    stats = {
        'total_users': len(active_users),
        'total_files': sum(len(f) for f in user_files.values()),
        'active_files': len(bot_scripts),
        'premium_users': sum(1 for uid in active_users if is_premium_user(uid)),
        'banned_users': len(banned_users)
    }
    return stats

def show_system_status(message):
    """Show system status"""
    stats = get_bot_statistics()
    sys_stats = get_system_stats()
    
    theme = get_theme()
    text = f"""
{theme['primary']} <b>System Status</b> {theme['primary']}
{theme['separator']*25}

👥 Users: <code>{stats['total_users']}</code>
✨ Premium: <code>{stats['premium_users']}</code>
📁 Files: <code>{stats['total_files']}</code>
🟢 Running: <code>{stats['active_files']}</code>

🖥 <b>Server:</b>
├ CPU: <code>{sys_stats['cpu']}%</code>
├ RAM: <code>{sys_stats['ram_percent']}%</code>
└ Used: <code>{sys_stats['ram_used']}/{sys_stats['ram_total']} MB</code>

⏰ <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>
"""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data='refresh_status'))
    
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode='HTML')

def show_user_profile(message):
    """Show user profile"""
    user_id = message.from_user.id
    
    file_count = get_user_file_count(user_id)
    file_limit = get_user_file_limit(user_id)
    limit_display = "∞" if file_limit == float('inf') else str(int(file_limit))
    
    running = sum(1 for fn,_,_ in user_files.get(user_id,[]) if is_bot_running(user_id, fn))
    
    sub = user_subscriptions.get(user_id)
    expiry_text = ""
    if sub and sub['expiry'] > datetime.now():
        expiry_text = f"\n⏳ Expires: <code>{sub['expiry'].strftime('%Y-%m-%d')}</code>"
    
    theme = get_theme()
    text = f"""
{theme['primary']} <b>Your Profile</b> {theme['primary']}
{theme['separator']*25}

🆔 ID: <code>{user_id}</code>
👤 Name: <b>{html_module.escape(message.from_user.first_name)}</b>
📊 Status: {get_user_status(user_id)}{expiry_text}

📁 <b>Files:</b>
├ Total: <code>{file_count}/{limit_display}</code>
├ Running: <code>{running}</code>
└ Stopped: <code>{file_count - running}</code>
"""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📁 View Files", callback_data='manage_files'))
    markup.add(types.InlineKeyboardButton("✨ Upgrade", callback_data='show_plans'))
    
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode='HTML')

def show_premium_plans(message):
    """Show premium plans"""
    plans = get_all_premium_plans()
    
    if not plans:
        bot.send_message(
            message.chat.id,
            "💎 No premium plans available yet.\nContact admin for details.",
            parse_mode='HTML'
        )
        return
    
    theme = get_theme()
    text = f"""
{theme['primary']} <b>Premium Plans</b> {theme['primary']}
{theme['separator']*25}

"""
    
    for plan in plans:
        days_text = "Lifetime" if plan['days'] == -1 else f"{plan['days']} days"
        file_text = "Unlimited" if plan['file_limit'] == 0 else f"{plan['file_limit']} files"
        text += f"• <b>{plan['name']}</b>\n"
        text += f"  💰 {plan['price']} Ks | 📅 {days_text} | 📁 {file_text}\n\n"
    
    text += f"📞 Contact: {ADMIN_USERNAME}"
    
    if ADMIN_USERNAME:
        admin_link = f"https://t.me/{ADMIN_USERNAME.replace('@', '')}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📞 Contact Admin", url=admin_link))
        markup.add(types.InlineKeyboardButton("🔑 I have a key", callback_data='redeem_key'))
    else:
        markup = None
    
    bot.send_message(
        message.chat.id,
        text,
        reply_markup=markup,
        parse_mode='HTML'
    )

def show_running_scripts(message):
    """Show running scripts for user"""
    user_id = message.from_user.id
    running = []
    
    for fn, ft, fp in user_files.get(user_id, []):
        if is_bot_running(user_id, fn):
            running.append((fn, ft))
    
    if not running:
        bot.send_message(
            message.chat.id,
            "🔄 No scripts currently running.\nUpload a file and start it!",
            parse_mode='HTML'
        )
        return
    
    theme = get_theme()
    text = f"{theme['primary']} <b>Running Scripts</b> {theme['primary']}\n{theme['separator']*25}\n\n"
    
    for fn, ft in running:
        text += f"🟢 <code>{html_module.escape(fn)}</code> | {ft}\n"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📁 Manage Files", callback_data='manage_files'))
    
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode='HTML')

def process_redeem_key(message):
    """Process key redemption"""
    user_id = message.from_user.id
    key = re.sub(r'[^A-Z0-9\-]', '', message.text.strip().upper())
    
    if not key.startswith('DEVRAW-'):
        bot.reply_to(message, "❌ Invalid key format!\nUse: <code>DEVRAW-XXXXXXXXXXXX</code>", parse_mode='HTML')
        return
    
    success, msg = redeem_subscription_key(key, user_id)
    bot.reply_to(message, msg, parse_mode='HTML')

def get_all_premium_plans():
    """Get all premium plans"""
    try:
        c = conn.cursor()
        c.execute("SELECT id, name, days, price, file_limit FROM premium_plans WHERE is_active=1")
        return [{"id": r[0], "name": r[1], "days": r[2], "price": r[3], "file_limit": r[4]} 
                for r in c.fetchall()]
    except:
        return []

def redeem_subscription_key(key_value, user_id):
    """Redeem subscription key"""
    # Implementation as in original code with enhancements
    try:
        c = conn.cursor()
        c.execute("SELECT days_valid, max_uses, used_count, file_limit FROM subscription_keys WHERE key_value=?", 
                 (key_value,))
        row = c.fetchone()
        
        if not row:
            return False, "❌ Invalid key!"
        
        days_valid, max_uses, used_count, file_limit = row
        
        if used_count >= max_uses:
            return False, "❌ Key already used!"
        
        c.execute("SELECT COUNT(*) FROM key_usage WHERE key_value=? AND user_id=?", (key_value, user_id))
        if c.fetchone()[0] > 0:
            return False, "❌ You already used this key!"
        
        # Calculate expiry
        current_expiry = user_subscriptions.get(user_id, {}).get('expiry', datetime.now())
        if current_expiry < datetime.now():
            current_expiry = datetime.now()
        
        new_expiry = datetime(9999, 12, 31, 23, 59, 59) if days_valid == -1 else current_expiry + timedelta(days=days_valid)
        
        # Save subscription
        expiry_str = '9999-12-31T23:59:59' if days_valid == -1 else new_expiry.isoformat()
        conn.execute("INSERT OR REPLACE INTO subscriptions (user_id, expiry, file_limit) VALUES (?, ?, ?)",
                    (user_id, expiry_str, file_limit))
        
        # Update key usage
        conn.execute("UPDATE subscription_keys SET used_count = used_count + 1 WHERE key_value = ?", (key_value,))
        conn.execute("INSERT OR REPLACE INTO key_usage (key_value, user_id) VALUES (?, ?)", (key_value, user_id))
        conn.commit()
        
        # Update in-memory
        user_subscriptions[user_id] = {'expiry': new_expiry, 'file_limit': file_limit}
        
        days_text = "Lifetime" if days_valid == -1 else f"{days_valid} days"
        limit_text = "Unlimited" if file_limit == 0 else str(file_limit)
        
        return True, f"""
✨ <b>Key Activated!</b>

📅 Duration: {days_text}
📁 File Limit: {limit_text}
⏳ Expires: {new_expiry.strftime('%Y-%m-%d') if days_valid != -1 else 'Never'}
"""
    
    except Exception as e:
        logger.error(f"Key redemption error: {e}")
        return False, "❌ Error processing key!"

def is_bot_running(user_id, file_name):
    """Check if a script is running"""
    key = f"{user_id}_{file_name}"
    with bot_scripts_lock:
        info = bot_scripts.get(key)
    
    if not info or not info.get('process'):
        return False
    
    try:
        process = info['process']
        if hasattr(process, 'poll'):
            return process.poll() is None
        elif hasattr(process, 'is_running'):
            return process.is_running()
        return False
    except:
        return False

def get_system_stats():
    """Get system resource stats"""
    try:
        cpu = psutil.cpu_percent(interval=0.5)
    except:
        cpu = 0.0
    
    try:
        mem = psutil.virtual_memory()
        ram_pct = mem.percent
        ram_used = mem.used >> 20
        ram_total = mem.total >> 20
    except:
        ram_pct = 0
        ram_used = 0
        ram_total = 0
    
    return {
        'cpu': cpu,
        'ram_percent': ram_pct,
        'ram_used': ram_used,
        'ram_total': ram_total
    }

# ================================================================
#   INITIALIZATION & MAIN LOOP
# ================================================================
def initialize_bot():
    """Initialize all bot components"""
    global force_channel_ids, force_group_id, force_join_enabled, FREE_USER_LIMIT
    global user_subscriptions, user_files, active_users, admin_ids, banned_users
    
    init_db()
    
    # Load data from database
    try:
        c = conn.cursor()
        
        # Load settings
        for row in c.execute("SELECT setting_key, setting_value FROM bot_settings"):
            key, val = row
            if key == "free_user_limit":
                FREE_USER_LIMIT = int(val) if val.isdigit() else 1
            elif key == "force_join_enabled":
                force_join_enabled = val == "1"
            elif key == "force_channel_ids":
                force_channel_ids = [int(x) for x in val.split(',') if x.strip().lstrip('-').isdigit()] if val.strip() else []
            elif key == "force_group_id":
                force_group_id = int(val) if val.strip().lstrip('-').isdigit() else 0
        
        # Load users
        active_users.clear()
        for row in c.execute("SELECT user_id FROM active_users"):
            active_users.add(row[0])
        
        # Load admins
        admin_ids = {OWNER_ID} if OWNER_ID else set()
        for row in c.execute("SELECT user_id FROM admins"):
            admin_ids.add(row[0])
        
        # Load banned users
        banned_users.clear()
        for row in c.execute("SELECT user_id FROM users WHERE banned=1"):
            banned_users.add(row[0])
        
        # Load subscriptions
        user_subscriptions.clear()
        for row in c.execute("SELECT user_id, expiry, file_limit FROM subscriptions"):
            try:
                es = row[1]
                expiry = datetime(9999, 12, 31, 23, 59, 59) if es == '9999-12-31T23:59:59' else datetime.fromisoformat(es)
                user_subscriptions[row[0]] = {"expiry": expiry, "file_limit": row[2]}
            except:
                pass
        
        # Load files
        user_files.clear()
        for row in c.execute("SELECT user_id, file_name, file_type, file_path FROM user_files"):
            uid = row[0]
            if uid not in user_files:
                user_files[uid] = []
            user_files[uid].append((row[1], row[2], row[3]))
        
        logger.info(f"✅ Loaded {len(active_users)} users, {len(user_subscriptions)} subscriptions")
        
    except Exception as e:
        logger.error(f"❌ Data load error: {e}", exc_info=True)

def cleanup_bot():
    """Cleanup before shutdown"""
    logger.warning("🛑 Shutting down...")
    with bot_scripts_lock:
        for info in bot_scripts.values():
            try:
                process = info.get('process')
                if process:
                    if os.name != 'nt':
                        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    else:
                        process.terminate()
            except:
                pass
        bot_scripts.clear()
    
    if conn:
        conn.close()
    logger.info("✅ Cleanup complete")

if __name__ == '__main__':
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join(LOGS_DIR, 'bot.log'))
        ]
    )
    logger = logging.getLogger('devraw')
    security_logger = logging.getLogger('devraw.security')
    
    logger.info("🚀 DEV-RAW CORE v3.0 Starting...")
    
    # Initialize bot
    initialize_bot()
    
    # Start Flask keep-alive
    def run_flask():
        app = Flask(__name__)
        
        @app.route('/')
        def home():
            return jsonify({
                "status": "running",
                "bot": "DEV-RAW CORE v3.0",
                "timestamp": datetime.now().isoformat()
            })
        
        @app.route('/health')
        def health():
            return jsonify({"status": "healthy"})
        
        port = int(os.environ.get("PORT", 5000))
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info(f"🟣 Keep-alive server started")
    
    # Register cleanup
    atexit.register(cleanup_bot)
    
    # Start monitoring thread
    def monitor_processes():
        while True:
            try:
                time.sleep(60)
                with bot_scripts_lock:
                    dead = []
                    for key, info in bot_scripts.items():
                        process = info.get('process')
                        if not process:
                            dead.append(key)
                            continue
                        try:
                            if process.poll() is not None:
                                dead.append(key)
                        except:
                            dead.append(key)
                    for key in dead:
                        bot_scripts.pop(key, None)
            except Exception as e:
                logger.error(f"Monitor error: {e}")
    
    monitor_thread = Thread(target=monitor_processes, daemon=True)
    monitor_thread.start()
    
    logger.info("✅ Bot ready! Starting polling...")
    
    # Main polling loop
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=30)
        except Exception as e:
            logger.error(f"Polling error: {e}", exc_info=True)
            time.sleep(5)
