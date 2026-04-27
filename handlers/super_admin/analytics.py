# handlers/super_admin/analytics.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
import database.queries as db
from keyboards.all_keyboards import (
    get_super_admin_main_menu, get_back_keyboard
)
import json
import os
from config import EXPORTS_DIR

router = Router()

@router.message(F.text == "📊 Analytics")
async def analytics_main_menu(message: Message, state: FSMContext):
    """Show analytics main menu"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Platform Dashboard", callback_data="sa_platform_dashboard")],
        [InlineKeyboardButton(text="📈 Growth Charts", callback_data="sa_growth_charts")],
        [InlineKeyboardButton(text="💰 Revenue Analytics", callback_data="sa_revenue_analytics")],
        [InlineKeyboardButton(text="🏢 Center Comparison", callback_data="sa_center_comparison")],
        [InlineKeyboardButton(text="👥 User Analytics", callback_data="sa_user_analytics")],
        [InlineKeyboardButton(text="📝 Content Analytics", callback_data="sa_content_analytics")],
        [InlineKeyboardButton(text="📥 Export Full Report", callback_data="sa_export_full_report")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")]
    ])

    text = "📊 **Platform Analytics**\n\n"
    text += "Comprehensive analytics and reporting for the entire platform.\n"
    text += "Select a report to view:"

    await message.answer(text, reply_markup=keyboard)

# ========================
# PLATFORM DASHBOARD
# ========================

@router.callback_query(F.data == "sa_platform_dashboard")
async def platform_dashboard(callback: CallbackQuery, state: FSMContext):
    """Show comprehensive platform dashboard"""
    await callback.message.edit_text("📊 **Loading dashboard...**")

    stats = await gather_platform_stats()

    text = "📊 **Platform Dashboard**\n\n"
    text += "══════════════════════════════\n\n"

    text += "🏢 **Centers:**\n"
    text += f"  • Total: **{stats['centers']['total']}**\n"
    text += f"  • Active: **{stats['centers']['active']}**\n"
    text += f"  • Suspended: **{stats['centers']['suspended']}**\n"
    text += f"  • Trial: **{stats['centers']['trial']}**\n"
    text += f"  • New (30d): **{stats['centers']['new_30d']}**\n\n"

    text += "👥 **Users:**\n"
    text += f"  • Total: **{stats['users']['total']}**\n"
    text += f"  • Super Admins: **{stats['users']['super_admins']}**\n"
    text += f"  • Center Admins: **{stats['users']['center_admins']}**\n"
    text += f"  • Teachers: **{stats['users']['teachers']}**\n"
    text += f"  • Students: **{stats['users']['students']}**\n"
    text += f"  • Parents: **{stats['users']['parents']}**\n"
    text += f"  • Blocked: **{stats['users']['blocked']}**\n"
    text += f"  • New (7d): **{stats['users']['new_7d']}**\n\n"

    text += "📚 **Content:**\n"
    text += f"  • Active Classes: **{stats['content']['classes']}**\n"
    text += f"  • Active Quizzes: **{stats['content']['quizzes']}**\n"
    text += f"  • Total Units: **{stats['content']['units']}**\n"
    text += f"  • Questions: **{stats['content']['questions']}**\n\n"

    text += "📝 **Activity:**\n"
    text += f"  • Quiz Attempts: **{stats['activity']['quiz_attempts']}**\n"
    text += f"  • Homework Submissions: **{stats['activity']['homework_submissions']}**\n"
    text += f"  • Attendance Sessions: **{stats['activity']['attendance_sessions']}**\n"
    text += f"  • Messages Sent: **{stats['activity']['messages']}**\n"
    text += f"  • Speaking Sessions: **{stats['activity']['speaking_sessions']}**\n\n"

    text += "💰 **Revenue:**\n"
    text += f"  • Total Revenue: **{stats['revenue']['total']:,.0f} UZS**\n"
    text += f"  • This Month: **{stats['revenue']['month']:,.0f} UZS**\n"
    text += f"  • This Year: **{stats['revenue']['year']:,.0f} UZS**\n"
    text += f"  • Avg per Center: **{stats['revenue']['avg_per_center']:,.0f} UZS**\n\n"

    text += "💾 **System:**\n"
    text += f"  • Database Size: **{stats['system']['db_size_mb']:.2f} MB**\n"
    text += f"  • Backup Count: **{stats['system']['backups']}**\n"
    text += f"  • Error Count (7d): **{stats['system']['errors_7d']}**\n"
    text += f"  • Support Tickets: **{stats['system']['open_tickets']}** open\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Refresh", callback_data="sa_platform_dashboard")],
        [InlineKeyboardButton(text="📥 Export Dashboard", callback_data="sa_export_dashboard")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)

async def gather_platform_stats() -> dict:
    """Gather all platform statistics"""
    stats = {
        'centers': {},
        'users': {},
        'content': {},
        'activity': {},
        'revenue': {},
        'system': {}
    }

    async with db.get_db() as conn:
        # Centers
        cursor = await conn.execute("SELECT COUNT(*) FROM centers")
        stats['centers']['total'] = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(*) FROM centers WHERE is_active = 1 AND is_suspended = 0")
        stats['centers']['active'] = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(*) FROM centers WHERE is_suspended = 1")
        stats['centers']['suspended'] = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(*) FROM centers WHERE trial_ends_at > datetime('now')")
        stats['centers']['trial'] = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(*) FROM centers WHERE created_at >= datetime('now', '-30 days')")
        stats['centers']['new_30d'] = (await cursor.fetchone())[0]

        # Users
        cursor = await conn.execute("SELECT COUNT(*) FROM users")
        stats['users']['total'] = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(DISTINCT user_id) FROM user_roles WHERE role = 'super_admin'")
        stats['users']['super_admins'] = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(DISTINCT user_id) FROM user_roles WHERE role = 'center_admin'")
        stats['users']['center_admins'] = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(DISTINCT user_id) FROM user_roles WHERE role = 'teacher'")
        stats['users']['teachers'] = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(DISTINCT user_id) FROM user_roles WHERE role = 'student'")
        stats['users']['students'] = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(DISTINCT user_id) FROM user_roles WHERE role = 'parent'")
        stats['users']['parents'] = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(*) FROM users WHERE is_blocked = 1")
        stats['users']['blocked'] = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', '-7 days')")
        stats['users']['new_7d'] = (await cursor.fetchone())[0]

        # Content
        cursor = await conn.execute("SELECT COUNT(*) FROM classes WHERE is_archived = 0")
        stats['content']['classes'] = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(*) FROM quizzes WHERE is_active = 1")
        stats['content']['quizzes'] = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(*) FROM units WHERE is_active = 1")
        stats['content']['units'] = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(*) FROM quiz_questions")
        stats['content']['questions'] = (await cursor.fetchone())[0]

        # Activity
        cursor = await conn.execute("SELECT COUNT(*) FROM quiz_attempts WHERE completed_at IS NOT NULL")
        stats['activity']['quiz_attempts'] = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(*) FROM homework_submissions")
        stats['activity']['homework_submissions'] = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(*) FROM attendance_sessions")
        stats['activity']['attendance_sessions'] = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(*) FROM messages")
        stats['activity']['messages'] = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(*) FROM speaking_sessions WHERE ended_at IS NOT NULL")
        stats['activity']['speaking_sessions'] = (await cursor.fetchone())[0]

        # Revenue
        cursor = await conn.execute("SELECT COALESCE(SUM(amount), 0) FROM payments")
        stats['revenue']['total'] = (await cursor.fetchone())[0]

        cursor = await conn.execute("""
            SELECT COALESCE(SUM(amount), 0) FROM payments
            WHERE payment_date >= datetime('now', 'start of month')
        """)
        stats['revenue']['month'] = (await cursor.fetchone())[0]

        cursor = await conn.execute("""
            SELECT COALESCE(SUM(amount), 0) FROM payments
            WHERE payment_date >= datetime('now', 'start of year')
        """)
        stats['revenue']['year'] = (await cursor.fetchone())[0]

        total_centers = stats['centers']['total'] or 1
        stats['revenue']['avg_per_center'] = stats['revenue']['total'] / total_centers

        # System
        import os
        from config import DB_PATH
        db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
        stats['system']['db_size_mb'] = db_size / (1024 * 1024)

        cursor = await conn.execute("SELECT COUNT(*) FROM backups")
        stats['system']['backups'] = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(*) FROM system_logs WHERE level = 'ERROR' AND created_at >= datetime('now', '-7 days')")
        stats['system']['errors_7d'] = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(*) FROM support_tickets WHERE status = 'open'")
        stats['system']['open_tickets'] = (await cursor.fetchone())[0]

    return stats

# ========================
# GROWTH CHARTS
# ========================

@router.callback_query(F.data == "sa_growth_charts")
async def growth_charts(callback: CallbackQuery, state: FSMContext):
    """Show growth charts and trends"""

    # Get monthly growth data
    async with db.get_db() as conn:
        # Centers growth
        cursor = await conn.execute("""
            SELECT strftime('%Y-%m', created_at) as month, COUNT(*) as count
            FROM centers
            WHERE created_at >= datetime('now', '-12 months')
            GROUP BY strftime('%Y-%m', created_at)
            ORDER BY month
        """)
        center_growth = [dict(row) for row in await cursor.fetchall()]

        # Users growth
        cursor = await conn.execute("""
            SELECT strftime('%Y-%m', created_at) as month, COUNT(*) as count
            FROM users
            WHERE created_at >= datetime('now', '-12 months')
            GROUP BY strftime('%Y-%m', created_at)
            ORDER BY month
        """)
        user_growth = [dict(row) for row in await cursor.fetchall()]

        # Revenue growth
        cursor = await conn.execute("""
            SELECT strftime('%Y-%m', payment_date) as month, COALESCE(SUM(amount), 0) as total
            FROM payments
            WHERE payment_date >= datetime('now', '-12 months')
            GROUP BY strftime('%Y-%m', payment_date)
            ORDER BY month
        """)
        revenue_growth = [dict(row) for row in await cursor.fetchall()]

    text = "📈 **Growth Charts (12 Months)**\n\n"

    text += "🏢 **Center Growth:**\n"
    if center_growth:
        for cg in center_growth:
            bar = "█" * min(cg['count'], 50)
            text += f"  {cg['month']}: {bar} ({cg['count']})\n"
    else:
        text += "  No data yet\n"
    text += "\n"

    text += "👥 **User Growth:**\n"
    if user_growth:
        for ug in user_growth:
            bar = "█" * min(ug['count'], 50)
            text += f"  {ug['month']}: {bar} ({ug['count']})\n"
    else:
        text += "  No data yet\n"
    text += "\n"

    text += "💰 **Revenue Growth:**\n"
    if revenue_growth:
        for rg in revenue_growth:
            total = int(rg['total'])
            bar = "█" * min(total // 100000, 50)
            text += f"  {rg['month']}: {bar} ({total:,.0f} UZS)\n"
    else:
        text += "  No data yet\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Refresh", callback_data="sa_growth_charts")],
        [InlineKeyboardButton(text="📥 Export Data", callback_data="sa_export_growth")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)

# ========================
# REVENUE ANALYTICS
# ========================

@router.callback_query(F.data == "sa_revenue_analytics")
async def revenue_analytics(callback: CallbackQuery, state: FSMContext):
    """Show detailed revenue analytics"""

    async with db.get_db() as conn:
        # Total stats
        cursor = await conn.execute("""
            SELECT
                COALESCE(SUM(amount), 0) as total,
                COUNT(*) as transactions,
                AVG(amount) as avg_transaction,
                MAX(amount) as max_transaction
            FROM payments
        """)
        overall = dict(await cursor.fetchone())

        # Monthly breakdown
        cursor = await conn.execute("""
            SELECT strftime('%Y-%m', payment_date) as month,
                   COALESCE(SUM(amount), 0) as total,
                   COUNT(*) as count
            FROM payments
            WHERE payment_date >= datetime('now', '-12 months')
            GROUP BY strftime('%Y-%m', payment_date)
            ORDER BY month DESC
        """)
        monthly = [dict(row) for row in await cursor.fetchall()]

        # Top paying centers
        cursor = await conn.execute("""
            SELECT c.name, COALESCE(SUM(p.amount), 0) as total
            FROM centers c
            LEFT JOIN payments p ON c.id = p.center_id
            GROUP BY c.id
            ORDER BY total DESC
            LIMIT 10
        """)
        top_centers = [dict(row) for row in await cursor.fetchall()]

        # Payment methods breakdown
        cursor = await conn.execute("""
            SELECT payment_method, COUNT(*) as count, COALESCE(SUM(amount), 0) as total
            FROM payments
            GROUP BY payment_method
        """)
        methods = [dict(row) for row in await cursor.fetchall()]

    text = "💰 **Revenue Analytics**\n\n"
    text += "══════════════════════════════\n\n"

    text += "📊 **Overall:**\n"
    text += f"  • Total Revenue: **{overall['total']:,.0f} UZS**\n"
    text += f"  • Total Transactions: **{overall['transactions']}**\n"
    text += f"  • Average Transaction: **{overall['avg_transaction']:,.0f} UZS**\n"
    text += f"  • Largest Transaction: **{overall['max_transaction']:,.0f} UZS**\n\n"

    text += "📅 **Monthly Breakdown:**\n"
    for month in monthly[:12]:
        text += f"  {month['month']}: {month['total']:,.0f} UZS ({month['count']} transactions)\n"
    text += "\n"

    text += "🏢 **Top Centers by Revenue:**\n"
    for i, center in enumerate(top_centers, 1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"#{i}")
        text += f"  {medal} {center['name']}: {center['total']:,.0f} UZS\n"
    text += "\n"

    text += "💳 **Payment Methods:**\n"
    for method in methods:
        text += f"  • {method['payment_method'].title()}: {method['total']:,.0f} UZS ({method['count']})\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Export Revenue Report", callback_data="sa_export_revenue")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)

# ========================
# CENTER COMPARISON
# ========================

@router.callback_query(F.data == "sa_center_comparison")
async def center_comparison(callback: CallbackQuery, state: FSMContext):
    """Compare centers performance"""

    centers = await db.get_all_centers(include_suspended=True)

    if not centers:
        await callback.message.edit_text(
            "No centers to compare.",
            reply_markup=get_back_keyboard("sa_back")
        )
        return

    text = "🏢 **Center Comparison**\n\n"
    text += "══════════════════════════════════════════════════\n\n"

    center_stats = []
    for center in centers:
        stats = await get_center_detailed_stats(center['id'])
        stats['center'] = center
        center_stats.append(stats)

    # Sort by total students
    center_stats.sort(key=lambda x: x.get('students', 0), reverse=True)

    for i, stats in enumerate(center_stats[:20], 1):
        center = stats['center']
        status = "🟢" if center['is_active'] and not center['is_suspended'] else "🔴" if center['is_suspended'] else "🟡"

        text += f"{status} **{center['name']}**\n"
        text += f"  📊 Plan: {center.get('subscription_plan', 'basic').title()}\n"
        text += f"  👥 Students: {stats.get('students', 0)} | Teachers: {stats.get('teachers', 0)}\n"
        text += f"  🏫 Classes: {stats.get('classes', 0)} | Quizzes: {stats.get('quizzes', 0)}\n"
        text += f"  📅 Attendance: {stats.get('attendance_rate', 0):.1f}%\n"
        text += f"  💰 Revenue: {stats.get('revenue', 0):,.0f} UZS\n"
        text += f"  ⭐ Avg Points: {stats.get('avg_points', 0)}\n"
        text += "\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Export Comparison", callback_data="sa_export_comparison")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)

async def get_center_detailed_stats(center_id: int) -> dict:
    """Get detailed statistics for a single center"""
    stats = {}

    async with db.get_db() as conn:
        cursor = await conn.execute("SELECT COUNT(DISTINCT user_id) FROM user_roles WHERE center_id = ? AND role = 'teacher'", (center_id,))
        stats['teachers'] = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(DISTINCT user_id) FROM user_roles WHERE center_id = ? AND role = 'student'", (center_id,))
        stats['students'] = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(*) FROM classes WHERE center_id = ? AND is_archived = 0", (center_id,))
        stats['classes'] = (await cursor.fetchone())[0]

        cursor = await conn.execute("""
            SELECT COUNT(*) FROM quizzes q
            JOIN units u ON q.unit_id = u.id
            JOIN classes c ON u.class_id = c.id
            WHERE c.center_id = ? AND q.is_active = 1
        """, (center_id,))
        stats['quizzes'] = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE center_id = ?", (center_id,))
        stats['revenue'] = (await cursor.fetchone())[0]

        # Attendance rate
        cursor = await conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN ar.status = 'present' OR ar.status = 'late' THEN 1 ELSE 0 END) as present
            FROM attendance_records ar
            JOIN attendance_sessions a ON ar.session_id = a.id
            JOIN classes c ON a.class_id = c.id
            WHERE c.center_id = ?
        """, (center_id,))
        att = await cursor.fetchone()
        if att and att['total'] > 0:
            stats['attendance_rate'] = (att['present'] / att['total']) * 100
        else:
            stats['attendance_rate'] = 0

        # Average points
        cursor = await conn.execute("""
            SELECT AVG(u.total_points) FROM users u
            JOIN user_roles ur ON u.id = ur.user_id
            WHERE ur.center_id = ? AND ur.role = 'student'
        """, (center_id,))
        avg = await cursor.fetchone()
        stats['avg_points'] = round(avg[0], 1) if avg and avg[0] else 0

    return stats

# ========================
# USER ANALYTICS
# ========================

@router.callback_query(F.data == "sa_user_analytics")
async def user_analytics(callback: CallbackQuery, state: FSMContext):
    """Show user analytics"""

    async with db.get_db() as conn:
        # Active users by day
        cursor = await conn.execute("""
            SELECT date(last_active) as day, COUNT(*) as count
            FROM users
            WHERE last_active >= datetime('now', '-30 days')
            GROUP BY date(last_active)
            ORDER BY day DESC
        """)
        daily_active = [dict(row) for row in await cursor.fetchall()]

        # User retention
        cursor = await conn.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN last_active >= datetime('now', '-7 days') THEN 1 END) as active_7d,
                COUNT(CASE WHEN last_active >= datetime('now', '-30 days') THEN 1 END) as active_30d,
                COUNT(CASE WHEN last_active >= datetime('now', '-90 days') THEN 1 END) as active_90d
            FROM users
        """)
        retention = dict(await cursor.fetchone())

        # Top active students
        cursor = await conn.execute("""
            SELECT u.full_name, u.total_points, u.current_streak, u.longest_streak
            FROM users u
            JOIN user_roles ur ON u.id = ur.user_id
            WHERE ur.role = 'student'
            ORDER BY u.total_points DESC
            LIMIT 20
        """)
        top_students = [dict(row) for row in await cursor.fetchall()]

        # Streak distribution
        cursor = await conn.execute("""
            SELECT
                CASE
                    WHEN current_streak = 0 THEN '0 days'
                    WHEN current_streak <= 3 THEN '1-3 days'
                    WHEN current_streak <= 7 THEN '4-7 days'
                    WHEN current_streak <= 14 THEN '8-14 days'
                    WHEN current_streak <= 30 THEN '15-30 days'
                    ELSE '30+ days'
                END as streak_range,
                COUNT(*) as count
            FROM users
            WHERE current_streak > 0
            GROUP BY streak_range
            ORDER BY MIN(current_streak)
        """)
        streak_dist = [dict(row) for row in await cursor.fetchall()]

    text = "👥 **User Analytics**\n\n"
    text += "══════════════════════════════\n\n"

    text += "📊 **Retention:**\n"
    total = retention['total'] or 1
    text += f"  • 7-day active: **{retention['active_7d']}** ({retention['active_7d']/total*100:.1f}%)\n"
    text += f"  • 30-day active: **{retention['active_30d']}** ({retention['active_30d']/total*100:.1f}%)\n"
    text += f"  • 90-day active: **{retention['active_90d']}** ({retention['active_90d']/total*100:.1f}%)\n\n"

    text += "🔥 **Streak Distribution:**\n"
    for sd in streak_dist:
        bar = "█" * min(sd['count'], 30)
        text += f"  {sd['streak_range']}: {bar} ({sd['count']})\n"
    text += "\n"

    text += "⭐ **Top Students:**\n"
    for i, student in enumerate(top_students[:10], 1):
        text += f"  {i}. {student['full_name']}: {student['total_points']} pts | 🔥 {student['current_streak']} days\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Export User Report", callback_data="sa_export_users")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)

# ========================
# CONTENT ANALYTICS
# ========================

@router.callback_query(F.data == "sa_content_analytics")
async def content_analytics(callback: CallbackQuery, state: FSMContext):
    """Show content analytics"""

    async with db.get_db() as conn:
        # Quiz statistics
        cursor = await conn.execute("""
            SELECT
                COUNT(*) as total_quizzes,
                COUNT(DISTINCT q.unit_id) as units_with_quizzes,
                AVG(q.passing_score) as avg_passing_score,
                AVG(q.max_attempts) as avg_max_attempts
            FROM quizzes q
            WHERE q.is_active = 1
        """)
        quiz_stats = dict(await cursor.fetchone())

        # Most attempted quizzes
        cursor = await conn.execute("""
            SELECT q.title, COUNT(qa.id) as attempts,
                   AVG(CAST(qa.score AS FLOAT) / CAST(qa.max_score AS FLOAT) * 100) as avg_score
            FROM quizzes q
            JOIN quiz_attempts qa ON q.id = qa.quiz_id
            WHERE qa.completed_at IS NOT NULL
            GROUP BY q.id
            ORDER BY attempts DESC
            LIMIT 10
        """)
        popular_quizzes = [dict(row) for row in await cursor.fetchall()]

        # Question type distribution
        cursor = await conn.execute("""
            SELECT question_type, COUNT(*) as count
            FROM quiz_questions
            GROUP BY question_type
            ORDER BY count DESC
        """)
        question_types = [dict(row) for row in await cursor.fetchall()]

        # Homework statistics
        cursor = await conn.execute("""
            SELECT
                COUNT(*) as total_homework,
                COUNT(DISTINCT class_id) as classes_with_homework,
                AVG(max_score) as avg_max_score
            FROM homework
            WHERE is_active = 1
        """)
        hw_stats = dict(await cursor.fetchone())

        # Submission rate
        cursor = await conn.execute("""
            SELECT
                COUNT(DISTINCT h.id) as total_assigned,
                COUNT(DISTINCT hs.homework_id) as submitted,
                COUNT(DISTINCT CASE WHEN hs.is_graded = 1 THEN hs.homework_id END) as graded
            FROM homework h
            LEFT JOIN homework_submissions hs ON h.id = hs.homework_id
        """)
        submission_stats = dict(await cursor.fetchone())

    text = "📝 **Content Analytics**\n\n"
    text += "══════════════════════════════\n\n"

    text += "📊 **Quiz Statistics:**\n"
    text += f"  • Total Active Quizzes: **{quiz_stats['total_quizzes']}**\n"
    text += f"  • Units with Quizzes: **{quiz_stats['units_with_quizzes']}**\n"
    text += f"  • Avg Passing Score: **{quiz_stats['avg_passing_score']:.1f}%**\n"
    text += f"  • Avg Max Attempts: **{quiz_stats['avg_max_attempts']:.1f}**\n\n"

    text += "🔥 **Most Popular Quizzes:**\n"
    for i, q in enumerate(popular_quizzes, 1):
        text += f"  {i}. {q['title'][:40]}: {q['attempts']} attempts (Avg: {q['avg_score']:.1f}%)\n"
    text += "\n"

    text += "📋 **Question Types:**\n"
    for qt in question_types:
        text += f"  • {qt['question_type']}: {qt['count']}\n"
    text += "\n"

    text += "📄 **Homework Statistics:**\n"
    text += f"  • Total Assignments: **{hw_stats['total_homework']}**\n"
    text += f"  • Classes with HW: **{hw_stats['classes_with_homework']}**\n"
    text += f"  • Avg Max Score: **{hw_stats['avg_max_score']:.1f}**\n\n"

    text += "📥 **Submission Rate:**\n"
    total = submission_stats['total_assigned'] or 1
    text += f"  • Submitted: **{submission_stats['submitted']}** ({submission_stats['submitted']/total*100:.1f}%)\n"
    text += f"  • Graded: **{submission_stats['graded']}** ({submission_stats['graded']/total*100:.1f}%)\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Export Content Report", callback_data="sa_export_content")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)

# ========================
# EXPORT FUNCTIONS
# ========================

@router.callback_query(F.data == "sa_export_full_report")
async def export_full_report(callback: CallbackQuery, state: FSMContext):
    """Export comprehensive platform report"""
    await callback.message.edit_text("📥 **Generating full report...**")

    stats = await gather_platform_stats()

    filename = f"platform_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = os.path.join(EXPORTS_DIR, filename)
    os.makedirs(EXPORTS_DIR, exist_ok=True)

    # Add timestamp
    report = {
        'generated_at': datetime.now().isoformat(),
        'platform_name': 'StudyCenter Bot',
        'statistics': stats
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    document = FSInputFile(filepath)
    await callback.message.answer_document(
        document=document,
        caption=f"📊 Full Platform Report\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )

    await callback.message.edit_text(
        "✅ Report exported successfully!",
        reply_markup=get_back_keyboard("sa_back")
    )

@router.callback_query(F.data == "sa_export_dashboard")
async def export_dashboard(callback: CallbackQuery, state: FSMContext):
    """Export dashboard data"""
    stats = await gather_platform_stats()

    filename = f"dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = os.path.join(EXPORTS_DIR, filename)
    os.makedirs(EXPORTS_DIR, exist_ok=True)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2, default=str)

    document = FSInputFile(filepath)
    await callback.message.answer_document(
        document=document,
        caption="📊 Dashboard Export"
    )

    await callback.answer("✅ Dashboard exported!")

@router.callback_query(F.data == "sa_export_growth")
async def export_growth_data(callback: CallbackQuery, state: FSMContext):
    """Export growth data"""
    filename = f"growth_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(EXPORTS_DIR, filename)
    os.makedirs(EXPORTS_DIR, exist_ok=True)

    import csv
    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT strftime('%Y-%m', created_at) as month,
                   COUNT(CASE WHEN table_name = 'centers' THEN 1 END) as centers,
                   COUNT(CASE WHEN table_name = 'users' THEN 1 END) as users
            FROM (
                SELECT created_at, 'centers' as table_name FROM centers
                UNION ALL
                SELECT created_at, 'users' as table_name FROM users
            )
            WHERE created_at >= datetime('now', '-12 months')
            GROUP BY strftime('%Y-%m', created_at)
            ORDER BY month
        """)

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Month', 'New Centers', 'New Users'])
            for row in await cursor.fetchall():
                writer.writerow(row)

    document = FSInputFile(filepath)
    await callback.message.answer_document(
        document=document,
        caption="📈 Growth Data Export"
    )

    await callback.answer("✅ Growth data exported!")

@router.callback_query(F.data == "sa_export_revenue")
async def export_revenue_report(callback: CallbackQuery, state: FSMContext):
    """Export revenue report"""
    from services.export_service import ExportService

    filepath = await ExportService.export_payments_to_csv(None)  # All centers

    if filepath:
        document = FSInputFile(filepath)
        await callback.message.answer_document(
            document=document,
            caption="💰 Revenue Report Export"
        )
        await callback.answer("✅ Revenue report exported!")
    else:
        await callback.answer("❌ Failed to export", show_alert=True)

@router.callback_query(F.data == "sa_export_comparison")
async def export_comparison(callback: CallbackQuery, state: FSMContext):
    """Export center comparison"""
    filename = f"center_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(EXPORTS_DIR, filename)
    os.makedirs(EXPORTS_DIR, exist_ok=True)

    import csv
    centers = await db.get_all_centers(include_suspended=True)

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Center', 'Plan', 'Status', 'Students', 'Teachers', 'Classes', 'Revenue'])

        for center in centers:
            stats = await get_center_detailed_stats(center['id'])
            status = 'Active' if center['is_active'] and not center['is_suspended'] else 'Suspended'
            writer.writerow([
                center['name'],
                center.get('subscription_plan', 'basic'),
                status,
                stats.get('students', 0),
                stats.get('teachers', 0),
                stats.get('classes', 0),
                stats.get('revenue', 0)
            ])

    document = FSInputFile(filepath)
    await callback.message.answer_document(
        document=document,
        caption="🏢 Center Comparison Export"
    )

    await callback.answer("✅ Comparison exported!")
