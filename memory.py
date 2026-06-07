"""
نظام الذاكرة - Memory System
يخزن تفضيلات المستخدمين لكل محادثة
"""

import json
import os
import logging
from typing import Dict, Optional, Any
from datetime import datetime

from config import DATA_DIR, USERS_FILE

logger = logging.getLogger(__name__)


def _ensure_data_dir():
    """التأكد من وجود مجلد البيانات"""
    os.makedirs(DATA_DIR, exist_ok=True)


def _load_all_users() -> Dict:
    """تحميل بيانات كل المستخدمين"""
    _ensure_data_dir()
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Error loading users data: {e}")
    return {}


def _save_all_users(data: Dict):
    """حفظ بيانات كل المستخدمين"""
    _ensure_data_dir()
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.error(f"Error saving users data: {e}")


def get_user(user_id: int) -> Dict:
    """
    الحصول على بيانات مستخدم
    يرجع بيانات افتراضية لو المستخدم جديد
    """
    all_users = _load_all_users()
    uid = str(user_id)

    if uid not in all_users:
        # مستخدم جديد - بيانات افتراضية
        all_users[uid] = {
            "language": "ar",
            "news_time": "09:00",
            "sources": [],
            "created_at": datetime.now().isoformat(),
            "last_interaction": datetime.now().isoformat(),
            "commands_used": 0,
            "chat_count": 0,
        }
        _save_all_users(all_users)

    return all_users[uid]


def update_user(user_id: int, updates: Dict[str, Any]):
    """
    تحديث بيانات مستخدم
    """
    all_users = _load_all_users()
    uid = str(user_id)

    if uid not in all_users:
        get_user(user_id)  # إنشاء المستخدم لو مش موجود
        all_users = _load_all_users()

    for key, value in updates.items():
        all_users[uid][key] = value

    all_users[uid]["last_interaction"] = datetime.now().isoformat()
    _save_all_users(all_users)


def get_language(user_id: int) -> str:
    """الحصول على لغة المستخدم"""
    user = get_user(user_id)
    return user.get("language", "ar")


def set_language(user_id: int, language: str):
    """تعيين لغة المستخدم"""
    update_user(user_id, {"language": language})


def get_news_time(user_id: int) -> str:
    """الحصول على وقت الأخبار"""
    user = get_user(user_id)
    return user.get("news_time", "09:00")


def set_news_time(user_id: int, time_str: str):
    """تعيين وقت الأخبار"""
    update_user(user_id, {"news_time": time_str})


def get_sources(user_id: int) -> list:
    """الحصول على المصادر المفضلة"""
    user = get_user(user_id)
    return user.get("sources", [])


def set_sources(user_id: int, sources: list):
    """تعيين المصادر المفضلة"""
    update_user(user_id, {"sources": sources})


def increment_command_count(user_id: int):
    """زيادة عداد الأوامر"""
    user = get_user(user_id)
    update_user(user_id, {"commands_used": user.get("commands_used", 0) + 1})


def increment_chat_count(user_id: int):
    """زيادة عداد المحادثات"""
    user = get_user(user_id)
    update_user(user_id, {"chat_count": user.get("chat_count", 0) + 1})
