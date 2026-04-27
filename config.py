# config.py
import os
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Optional

load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN not found in .env file!")

# Database paths
BASE_DIR = Path(__file__).parent
DB_DIR = BASE_DIR / "database"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "homework_bot.db"
BACKUP_DIR = BASE_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)
EXPORTS_DIR = BASE_DIR / "exports"
EXPORTS_DIR.mkdir(exist_ok=True)

# Redis for caching (optional)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Platform Settings
PLATFORM_NAME = os.getenv("PLATFORM_NAME", "StudyCenter Bot")
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "uz")
SUPPORTED_LANGUAGES = ["uz", "ru", "en"]
DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Asia/Tashkent")

# Super Admin IDs (comma-separated)
super_admin_ids_str = os.getenv("SUPER_ADMIN_IDS", "")
SUPER_ADMIN_IDS: List[int] = [
    int(id.strip()) for id in super_admin_ids_str.split(",") if id.strip().isdigit()
]

# Teacher IDs from env (legacy support)
teacher_ids_str = os.getenv("TEACHER_IDS", "")
TEACHER_IDS: List[int] = [
    int(id.strip()) for id in teacher_ids_str.split(",") if id.strip().isdigit()
]

# File upload limits
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
ALLOWED_EXTENSIONS = ['.pdf', '.doc', '.docx', '.txt', '.jpg', '.png', '.jpeg', '.mp3', '.mp4']

# Payment gateway config
PAYMENT_GATEWAY = os.getenv("PAYMENT_GATEWAY", "manual")  # manual, stripe, payme
STRIPE_API_KEY = os.getenv("STRIPE_API_KEY", "")
PAYME_MERCHANT_ID = os.getenv("PAYME_MERCHANT_ID", "")

# Security
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
IP_WHITELIST = os.getenv("IP_WHITELIST", "").split(",") if os.getenv("IP_WHITELIST") else []
ENABLE_2FA = os.getenv("ENABLE_2FA", "false").lower() == "true"

# Email settings
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

# Rate limiting
RATE_LIMIT_PER_USER = int(os.getenv("RATE_LIMIT_PER_USER", "30"))  # messages per minute
RATE_LIMIT_PER_CENTER = int(os.getenv("RATE_LIMIT_PER_CENTER", "100"))

# Feature flags
FEATURES = {
    "speaking_partner": os.getenv("FEATURE_SPEAKING_PARTNER", "true").lower() == "true",
    "competitions": os.getenv("FEATURE_COMPETITIONS", "true").lower() == "true",
    "achievements": os.getenv("FEATURE_ACHIEVEMENTS", "true").lower() == "true",
    "leaderboard": os.getenv("FEATURE_LEADERBOARD", "true").lower() == "true",
    "payments": os.getenv("FEATURE_PAYMENTS", "true").lower() == "true",
}

# Subscription plans
SUBSCRIPTION_PLANS = {
    "basic": {
        "name": "Basic",
        "max_students": 50,
        "max_teachers": 5,
        "max_classes": 10,
        "features": ["attendance", "homework", "quizzes"],
        "price_monthly": 0,
        "price_yearly": 0,
        "trial_days": 14
    },
    "pro": {
        "name": "Pro",
        "max_students": 200,
        "max_teachers": 20,
        "max_classes": 50,
        "features": ["attendance", "homework", "quizzes", "competitions", "leaderboard", "payments"],
        "price_monthly": 29.99,
        "price_yearly": 299.99,
        "trial_days": 14
    },
    "enterprise": {
        "name": "Enterprise",
        "max_students": 1000,
        "max_teachers": 100,
        "max_classes": 200,
        "features": ["all"],
        "price_monthly": 99.99,
        "price_yearly": 999.99,
        "trial_days": 30
    }
}
