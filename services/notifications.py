# services/notifications.py
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import BOT_TOKEN
from typing import Optional
import logging

logger = logging.getLogger(__name__)
bot = Bot(token=BOT_TOKEN)

async def send_attendance_notification(
    student_telegram_id: int,
    class_name: str,
    date: str,
    status: str
):
    """Send attendance result to a student/parent"""
    status_emoji = {
        "present": "✅",
        "late": "⏰",
        "absent": "❌",
        "excused": "📝"
    }
    emoji = status_emoji.get(status, "❓")

    text = (
        f"📋 **Attendance Update**\n\n"
        f"🏫 Class: {class_name}\n"
        f"📅 Date: {date}\n"
        f"{emoji} Status: {status.title()}"
    )

    try:
        await bot.send_message(student_telegram_id, text)
        logger.info(f"Attendance notification sent to {student_telegram_id}")
    except Exception as e:
        logger.error(f"Failed to send attendance notification: {e}")

async def send_grade_notification(
    student_telegram_id: int,
    homework_title: str,
    score: int,
    max_score: int,
    feedback: Optional[str] = None
):
    """Send grade notification to student"""
    percentage = (score / max_score * 100) if max_score > 0 else 0

    text = (
        f"📊 **Homework Graded!**\n\n"
        f"📝 {homework_title}\n"
        f"⭐ Score: {score}/{max_score} ({percentage:.1f}%)\n"
    )

    if feedback:
        text += f"💬 Feedback: {feedback}\n"

    try:
        await bot.send_message(student_telegram_id, text)
        logger.info(f"Grade notification sent to {student_telegram_id}")
    except Exception as e:
        logger.error(f"Failed to send grade notification: {e}")

async def send_payment_notification(
    student_telegram_id: int,
    amount: float,
    date: str,
    notes: Optional[str] = None
):
    """Send payment confirmation to student/parent"""
    text = (
        f"💰 **Payment Recorded**\n\n"
        f"Amount: {amount:,.0f} UZS\n"
        f"📅 Date: {date}\n"
    )

    if notes:
        text += f"📝 Note: {notes}\n"

    try:
        await bot.send_message(student_telegram_id, text)
        logger.info(f"Payment notification sent to {student_telegram_id}")
    except Exception as e:
        logger.error(f"Failed to send payment notification: {e}")

async def send_homework_reminder(
    student_telegram_id: int,
    homework_title: str,
    deadline: str,
    days_left: int
):
    """Send homework deadline reminder"""
    urgency = "🔴" if days_left <= 0 else "🟡" if days_left <= 2 else "🟢"

    text = (
        f"{urgency} **Homework Reminder**\n\n"
        f"📝 {homework_title}\n"
        f"📅 Due: {deadline}\n"
        f"⏰ {'**OVERDUE!**' if days_left <= 0 else f'{days_left} days left'}\n\n"
        f"Please submit your homework as soon as possible."
    )

    try:
        await bot.send_message(student_telegram_id, text)
        logger.info(f"Homework reminder sent to {student_telegram_id}")
    except Exception as e:
        logger.error(f"Failed to send homework reminder: {e}")

async def send_competition_notification(
    student_telegram_id: int,
    competition_title: str,
    rank: int,
    points: int
):
    """Send competition result notification"""
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    medal = medals.get(rank, f"#{rank}")

    text = (
        f"🏆 **Competition Update**\n\n"
        f"📋 {competition_title}\n"
        f"{medal} Your Rank: #{rank}\n"
        f"⭐ Points Earned: {points}\n\n"
        f"Great job! Keep up the good work! 🎉"
    )

    try:
        await bot.send_message(student_telegram_id, text)
        logger.info(f"Competition notification sent to {student_telegram_id}")
    except Exception as e:
        logger.error(f"Failed to send competition notification: {e}")

async def send_announcement_to_users(
    user_ids: list,
    title: str,
    content: str,
    target_role: str = "all"
):
    """Send announcement to multiple users"""
    sent_count = 0
    failed_count = 0

    for user_id in user_ids:
        try:
            text = f"📢 **{title}**\n\n{content}"
            await bot.send_message(user_id, text)
            sent_count += 1
        except Exception as e:
            failed_count += 1
            logger.error(f"Failed to send announcement to {user_id}: {e}")

    return {"sent": sent_count, "failed": failed_count}

async def send_badge_notification(
    student_telegram_id: int,
    badge_name: str,
    badge_icon: str,
    badge_description: str,
    points_awarded: int
):
    """Send badge earned notification"""
    text = (
        f"🎖 **Badge Earned!**\n\n"
        f"{badge_icon} {badge_name}\n"
        f"📄 {badge_description}\n"
        f"⭐ +{points_awarded} points\n\n"
        f"Congratulations! 🎉"
    )

    try:
        await bot.send_message(student_telegram_id, text)
        logger.info(f"Badge notification sent to {student_telegram_id}")
    except Exception as e:
        logger.error(f"Failed to send badge notification: {e}")

async def send_message_to_user(
    user_id: int,
    message_text: str,
    from_name: str = "System"
):
    """Send a direct message to a user"""
    text = f"💬 **Message from {from_name}**\n\n{message_text}"

    try:
        await bot.send_message(user_id, text)
        return True
    except Exception as e:
        logger.error(f"Failed to send message to {user_id}: {e}")
        return False
