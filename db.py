import os
import json
import time
import asyncio
import logging
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "messages.db")

def init_all_databases():
    """Barcha jadvallarni bitta markaziy SQLite bazasida initsializatsiya qiladi."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            # 1. Anti-Delete: o'chirilgan xabarlar va medialar
            conn.execute("""
                CREATE TABLE IF NOT EXISTS saved_messages (
                    msg_id INTEGER,
                    chat_id INTEGER,
                    sender_id INTEGER,
                    sender_name TEXT,
                    text TEXT,
                    media_type TEXT,
                    media_path TEXT,
                    created_at TEXT,
                    PRIMARY KEY (msg_id, chat_id)
                )
            """)

            # 2. Reminders: eslatmalar jadvali
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER,
                    reminder_text TEXT,
                    target_time TEXT,
                    created_at TEXT,
                    is_sent INTEGER DEFAULT 0
                )
            """)

            # 3. Known Users: birinchi marta yozgan foydalanuvchilar
            conn.execute("""
                CREATE TABLE IF NOT EXISTS known_users (
                    user_id TEXT PRIMARY KEY,
                    first_seen TEXT
                )
            """)

            # 4. Replied Users: avto-javob berilgan foydalanuvchilar (cooldown uchun)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS replied_users (
                    user_id TEXT PRIMARY KEY,
                    last_replied REAL
                )
            """)

            # 5. Spy Watchlist: gumondorlar ro'yxati va korrelyatsiya statistikasi
            conn.execute("""
                CREATE TABLE IF NOT EXISTS spy_watchlist (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    name TEXT,
                    online_hits INTEGER DEFAULT 0,
                    total_checks INTEGER DEFAULT 0,
                    added_at TEXT
                )
            """)

            # Migratsiya: saved_messages jadvaliga yangi ustunlar kerak bo'lsa qo'shish
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(saved_messages)")
            columns = [col[1] for col in cursor.fetchall()]
            if "media_type" not in columns:
                conn.execute("ALTER TABLE saved_messages ADD COLUMN media_type TEXT")
            if "media_path" not in columns:
                conn.execute("ALTER TABLE saved_messages ADD COLUMN media_path TEXT")

            conn.commit()
            logger.info("Markaziy SQLite ma'lumotlar bazasi muvaffaqiyatli initsializatsiya qilindi.")

        # Eski JSON fayllar bo'lsa ma'lumotlarni bazaga migratsiya qilamiz
        migrate_legacy_json_caches()

    except Exception as e:
        logger.error(f"Ma'lumotlar bazasini initsializatsiya qilishda xatolik: {e}")

def migrate_legacy_json_caches():
    """Eski known_users.json va replied_users.json ma'lumotlarini SQLite bazasiga ko'chiradi."""
    known_json = os.path.join(BASE_DIR, "known_users.json")
    replied_json = os.path.join(BASE_DIR, "replied_users.json")

    try:
        with sqlite3.connect(DB_FILE) as conn:
            if os.path.exists(known_json):
                try:
                    with open(known_json, "r", encoding="utf-8") as f:
                        users = json.load(f)
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    for uid in users:
                        conn.execute(
                            "INSERT OR IGNORE INTO known_users (user_id, first_seen) VALUES (?, ?)",
                            (str(uid), now_str)
                        )
                    conn.commit()
                    os.rename(known_json, known_json + ".migrated.bak")
                    logger.info("known_users.json SQLite bazasiga migratsiya qilindi.")
                except Exception as e:
                    logger.warning(f"known_users.json migratsiyasida ogohlantirish: {e}")

            if os.path.exists(replied_json):
                try:
                    with open(replied_json, "r", encoding="utf-8") as f:
                        replied = json.load(f)
                    for uid, ts in replied.items():
                        conn.execute(
                            "INSERT OR REPLACE INTO replied_users (user_id, last_replied) VALUES (?, ?)",
                            (str(uid), float(ts))
                        )
                    conn.commit()
                    os.rename(replied_json, replied_json + ".migrated.bak")
                    logger.info("replied_users.json SQLite bazasiga migratsiya qilindi.")
                except Exception as e:
                    logger.warning(f"replied_users.json migratsiyasida ogohlantirish: {e}")

    except Exception as e:
        logger.error(f"JSON fayllarni migratsiya qilishda xatolik: {e}")

# ==========================================
# Known Users asinxron boshqaruvi
# ==========================================
def _sync_load_known_users() -> set:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM known_users")
            return {row[0] for row in cursor.fetchall()}
    except Exception as e:
        logger.error(f"known_users ni o'qishda xatolik: {e}")
        return set()

def _sync_save_known_user(user_id: str):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                "INSERT OR IGNORE INTO known_users (user_id, first_seen) VALUES (?, ?)",
                (user_id, now_str)
            )
            conn.commit()
    except Exception as e:
        logger.error(f"known_user ni saqlashda xatolik: {e}")

async def db_load_known_users() -> set:
    return await asyncio.to_thread(_sync_load_known_users)

async def db_save_known_user(user_id: str):
    await asyncio.to_thread(_sync_save_known_user, user_id)

# ==========================================
# Replied Users asinxron boshqaruvi
# ==========================================
def _sync_load_replied_users() -> dict[str, float]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, last_replied FROM replied_users")
            return {row[0]: float(row[1]) for row in cursor.fetchall()}
    except Exception as e:
        logger.error(f"replied_users ni o'qishda xatolik: {e}")
        return {}

def _sync_save_replied_user(user_id: str, timestamp: float):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO replied_users (user_id, last_replied) VALUES (?, ?)",
                (user_id, timestamp)
            )
            conn.commit()
    except Exception as e:
        logger.error(f"replied_user ni saqlashda xatolik: {e}")

def _sync_clean_expired_replied_users(cutoff: float):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("DELETE FROM replied_users WHERE last_replied < ?", (cutoff,))
            conn.commit()
    except Exception as e:
        logger.error(f"Eski replied_users ni tozalashda xatolik: {e}")

async def db_load_replied_users() -> dict[str, float]:
    return await asyncio.to_thread(_sync_load_replied_users)

async def db_save_replied_user(user_id: str, timestamp: float):
    await asyncio.to_thread(_sync_save_replied_user, user_id, timestamp)

async def db_clean_expired_replied_users(cutoff: float):
    await asyncio.to_thread(_sync_clean_expired_replied_users, cutoff)

# ==========================================
# Spy Watchlist asinxron boshqaruvi
# ==========================================
def _sync_add_spy_suspect(user_id: int, username: str, name: str) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO spy_watchlist (user_id, username, name, added_at)
                VALUES (?, ?, ?, datetime('now'))
            """, (user_id, username, name))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Suspect saqlashda xatolik: {e}")
        return False

def _sync_remove_spy_suspect(user_id: int) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("DELETE FROM spy_watchlist WHERE user_id = ?", (user_id,))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Suspect o'chirishda xatolik: {e}")
        return False

def _sync_get_spy_suspects() -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, username, name, online_hits, total_checks, added_at FROM spy_watchlist")
            return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Suspects ro'yxatini olishda xatolik: {e}")
        return []

def _sync_clear_spy_suspects() -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("DELETE FROM spy_watchlist")
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Suspects tozalashda xatolik: {e}")
        return False

def _sync_record_spy_hit(user_id: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("UPDATE spy_watchlist SET online_hits = online_hits + 1 WHERE user_id = ?", (user_id,))
            conn.commit()
    except Exception as e:
        logger.error(f"Spy hit yozishda xatolik: {e}")

def _sync_increment_spy_checks(user_ids: list[int]):
    if not user_ids:
        return
    try:
        with sqlite3.connect(DB_FILE) as conn:
            placeholders = ",".join("?" for _ in user_ids)
            conn.execute(f"UPDATE spy_watchlist SET total_checks = total_checks + 1 WHERE user_id IN ({placeholders})", user_ids)
            conn.commit()
    except Exception as e:
        logger.error(f"Spy checks oshirishda xatolik: {e}")

async def db_add_spy_suspect(user_id: int, username: str, name: str) -> bool:
    return await asyncio.to_thread(_sync_add_spy_suspect, user_id, username, name)

async def db_remove_spy_suspect(user_id: int) -> bool:
    return await asyncio.to_thread(_sync_remove_spy_suspect, user_id)

async def db_get_spy_suspects() -> list[dict]:
    return await asyncio.to_thread(_sync_get_spy_suspects)

async def db_clear_spy_suspects() -> bool:
    return await asyncio.to_thread(_sync_clear_spy_suspects)

async def db_record_spy_hit(user_id: int):
    await asyncio.to_thread(_sync_record_spy_hit, user_id)

async def db_increment_spy_checks(user_ids: list[int]):
    await asyncio.to_thread(_sync_increment_spy_checks, user_ids)

# Modul yuklanganda bazani initsializatsiya qilamiz
init_all_databases()
