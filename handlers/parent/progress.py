# handlers/parent/progress.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from datetime import datetime
import database.queries as db
from keyboards.all_keyboards import (
    get_parent_main_menu, get_parent_children_keyboard,
    get_back_keyboard
)
import os
from config import EXPORTS_DIR
import csv

router = Router()

async def get_parent_context(state: FSMContext) -> dict:
    data = await state.get_data()
    telegram_id = data.get('telegram_id', 0)
    parent = await db.get_user_by_telegram_id(telegram_id) if telegram_id else None
    if not parent:
        return {'parent': None, 'parent_id': None, 'children': []}
    children = await db.get_children_for_parent(parent['id'])
    return {'parent': parent, 'parent_id': parent['id'], 'children': children}

@router.message(F.text == "📊 Progress")
async def progress_menu(message: Message, state: FSMContext):
    """Show progress monitoring menu"""
    ctx = await get_parent_context(state)
    children = ctx.get('children', [])

    if not children:
        await message.answer(
            "👶 No children linked to your account.",
            reply_markup=get_parent_main_menu()
        )
        return

    await message.answer(
        "📊 **Progress Monitoring**\n\nSelect your child:",
        reply_markup=get_parent_children_keyboard(children)
    )

@router.callback_query(F.data.startswith("parent_child_"))
async def view_child_progress_menu(callback: CallbackQuery, state: FSMContext):
    """Show child progress menu"""
    child_id = int(callback.data.replace("parent_child_", ""))
    child = await db.get_user_by_id(child_id)

    if not child:
        await callback.answer("Child not found", show_alert=True)
        return

    await state.update_data(viewing_child_id=child_id)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 Unit Progress", callback_data=f"pp_unit_progress_{child_id}")],
        [InlineKeyboardButton(text="📝 Quiz Results", callback_data=f"pp_quiz_results_{child_id}")],
        [InlineKeyboardButton(text="📋 Homework Status", callback_data=f"pp_homework_status_{child_id}")],
        [InlineKeyboardButton(text="🏆 Competitions", callback_data=f"pp_competitions_{child_id}")],
        [InlineKeyboardButton(text="📊 Full Report", callback_data=f"pp_full_report_{child_id}")],
        [InlineKeyboardButton(text="📥 Download Report", callback_data=f"pp_download_report_{child_id}")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="pp_back")]
    ])

    text = f"📊 **Progress: {child['full_name']}**\n\n"
    text += "Select what you'd like to view:"

    await callback.message.edit_text(text, reply_markup=keyboard)

# ========================
# UNIT-BY-UNIT PROGRESS
# ========================

@router.callback_query(F.data.startswith("pp_unit_progress_"))
async def view_unit_progress(callback: CallbackQuery, state: FSMContext):
    """View child's unit-by-unit progress"""
    child_id = int(callback.data.replace("pp_unit_progress_", ""))

    units = await db.get_units_for_student(child_id)

    if not units:
        await callback.message.edit_text(
            "📚 No units available yet.",
            reply_markup=get_back_keyboard(f"parent_child_{child_id}")
        )
        return

    text = f"📚 **Unit-by-Unit Progress**\n\n"

    for unit in units:
        progress = unit.get('completion_percent', 0)
        bar = generate_progress_bar(progress)
        status = "✅" if unit.get('is_completed') else "📖" if progress > 0 else "🔒"

        text += f"{status} **Unit {unit['unit_number']}: {unit['title']}**\n"
        text += f"  [{bar}] {progress}%\n"

        if unit.get('class_name'):
            text += f"  🏫 {unit['class_name']}\n"
        text += "\n"

    # Overall completion
    total_progress = sum(u.get('completion_percent', 0) for u in units)
    overall = total_progress / len(units) if units else 0
    text += f"📊 **Overall:** {overall:.1f}% complete\n"

    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard(f"parent_child_{child_id}")
    )

def generate_progress_bar(percentage: float, length: int = 10) -> str:
    """Generate a text progress bar"""
    filled = int(percentage / 100 * length)
    empty = length - filled
    return "▓" * filled + "░" * empty

# ========================
# QUIZ RESULTS
# ========================

@router.callback_query(F.data.startswith("pp_quiz_results_"))
async def view_quiz_results(callback: CallbackQuery, state: FSMContext):
    """View child's quiz results"""
    child_id = int(callback.data.replace("pp_quiz_results_", ""))

    results = await db.get_student_quiz_results(child_id, 50)

    if not results:
        await callback.message.edit_text(
            "📝 No quiz results yet.",
            reply_markup=get_back_keyboard(f"parent_child_{child_id}")
        )
        return

    text = f"📝 **Quiz Results**\n\n"

    # Summary stats
    total = len(results)
    passed = sum(1 for r in results if r.get('passed'))
    pass_rate = (passed / total * 100) if total > 0 else 0

    # Calculate average score
    total_score = sum(r['score'] for r in results)
    total_max = sum(r.get('max_score', 100) for r in results)
    avg_percentage = (total_score / total_max * 100) if total_max > 0 else 0

    text += f"📊 **Summary:**\n"
    text += f"  • Total Quizzes: {total}\n"
    text += f"  • Passed: {passed}\n"
    text += f"  • Pass Rate: {pass_rate:.1f}%\n"
    text += f"  • Average Score: {avg_percentage:.1f}%\n\n"

    text += "**Recent Results:**\n"
    for result in results[:20]:
        passed_icon = "✅" if result.get('passed') else "❌"
        percentage = (result['score'] / result.get('max_score', 100) * 100) if result.get('max_score', 0) > 0 else 0
        date = result.get('completed_at', '')
        if date and len(date) >= 10:
            date = date[:10]

        text += f"{passed_icon} **{result.get('quiz_title', 'Quiz')}**\n"
        text += f"  Score: {result['score']}/{result.get('max_score', 100)} ({percentage:.1f}%)\n"
        if result.get('class_name'):
            text += f"  Class: {result['class_name']}\n"
        text += f"  Date: {date}\n"
        text += "\n"

    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard(f"parent_child_{child_id}")
    )

# ========================
# HOMEWORK STATUS
# ========================

@router.callback_query(F.data.startswith("pp_homework_status_"))
async def view_homework_status(callback: CallbackQuery, state: FSMContext):
    """View child's homework status"""
    child_id = int(callback.data.replace("pp_homework_status_", ""))

    homework_list = await db.get_homework_for_student(child_id)

    if not homework_list:
        await callback.message.edit_text(
            "📋 No homework assigned yet.",
            reply_markup=get_back_keyboard(f"parent_child_{child_id}")
        )
        return

    # Separate by status
    pending = [h for h in homework_list if not h.get('submission_id')]
    submitted = [h for h in homework_list if h.get('submission_id') and not h.get('is_graded')]
    graded = [h for h in homework_list if h.get('is_graded')]

    text = f"📋 **Homework Status**\n\n"
    text += f"📊 Total: {len(homework_list)} | Pending: {len(pending)} | Graded: {len(graded)}\n\n"

    if pending:
        text += "⏳ **Pending:**\n"
        for hw in pending:
            deadline = hw.get('deadline', '')
            if isinstance(deadline, str) and len(deadline) >= 10:
                deadline = deadline[:10]
            days_left = (datetime.fromisoformat(deadline) - datetime.now()).days if deadline else 0
            urgency = "🔴" if days_left < 0 else "🟡" if days_left <= 2 else "🟢"

            text += f"{urgency} {hw['title']}\n"
            text += f"  📅 Due: {deadline} ({days_left} days)\n"
            if hw.get('description'):
                text += f"  📄 {hw['description'][:100]}\n"
            text += f"  ⭐ Max: {hw.get('max_score', 100)} pts\n\n"

    if submitted:
        text += "📤 **Submitted (Awaiting Grade):**\n"
        for hw in submitted:
            text += f"  • {hw['title']}\n"
            text += f"    Submitted: {hw.get('submitted_at', 'N/A')[:10]}\n\n"

    if graded:
        text += "✅ **Graded:**\n"
        for hw in graded:
            percentage = (hw['score'] / hw.get('max_score', 100) * 100) if hw.get('max_score', 0) > 0 else 0
            text += f"  • {hw['title']}\n"
            text += f"    Score: {hw['score']}/{hw.get('max_score', 100)} ({percentage:.1f}%)\n"
            if hw.get('feedback'):
                text += f"    💬 {hw['feedback'][:100]}\n"
            text += "\n"

    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard(f"parent_child_{child_id}")
    )

# ========================
# COMPETITION RANKINGS
# ========================

@router.callback_query(F.data.startswith("pp_competitions_"))
async def view_competitions(callback: CallbackQuery, state: FSMContext):
    """View child's competition results"""
    child_id = int(callback.data.replace("pp_competitions_", ""))
    child = await db.get_user_by_id(child_id)

    if not child:
        await callback.answer("Child not found", show_alert=True)
        return

    # Get classes for child
    classes = await db.get_classes_for_student(child_id)

    if not classes:
        await callback.message.edit_text(
            "🏆 No competition data available.",
            reply_markup=get_back_keyboard(f"parent_child_{child_id}")
        )
        return

    center_id = classes[0].get('center_id')

    # Get competitions
    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT c.*, cp.rank, cp.points_earned
            FROM competitions c
            JOIN competition_participants cp ON c.id = cp.competition_id
            WHERE cp.student_id = ?
            ORDER BY c.end_date DESC
            LIMIT 20
        """, (child_id,))
        competitions = [dict(row) for row in await cursor.fetchall()]

    if not competitions:
        await callback.message.edit_text(
            "🏆 No competition participation yet.",
            reply_markup=get_back_keyboard(f"parent_child_{child_id}")
        )
        return

    text = f"🏆 **Competition History: {child['full_name']}**\n\n"

    for comp in competitions:
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        rank = comp.get('rank', '?')
        medal = medals.get(rank, f"#{rank}")

        text += f"**{comp['title']}**\n"
        text += f"  📅 {comp['start_date'][:10]} - {comp['end_date'][:10]}\n"
        text += f"  {medal} Rank: #{rank}\n"
        text += f"  ⭐ Points: {comp.get('points_earned', 0)}\n"

        # Get leaderboard for context
        leaderboard = await db.get_competition_leaderboard(comp['id'], 5)
        top_3 = leaderboard[:3]
        if top_3 and rank and rank <= 3:
            text += f"  🎉 Top 3 Finish!\n"

        text += "\n"

    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard(f"parent_child_{child_id}")
    )

# ========================
# FULL REPORT
# ========================

@router.callback_query(F.data.startswith("pp_full_report_"))
async def view_full_report(callback: CallbackQuery, state: FSMContext):
    """View comprehensive child report"""
    child_id = int(callback.data.replace("pp_full_report_", ""))
    child = await db.get_user_by_id(child_id)

    if not child:
        await callback.answer("Child not found", show_alert=True)
        return

    # Gather all data
    classes = await db.get_classes_for_student(child_id)
    class_info = classes[0] if classes else None
    points = await db.get_student_points_and_streak(child_id)
    badges = await db.get_student_badges(child_id)
    certificates = await db.get_student_certificates(child_id)
    attendance = await db.get_student_attendance_stats(child_id)
    quiz_results = await db.get_student_quiz_results(child_id, 50)
    homework = await db.get_homework_for_student(child_id)
    units = await db.get_units_for_student(child_id)

    text = f"📊 **Full Progress Report**\n"
    text += f"👶 Child: **{child['full_name']}**\n"
    text += "══════════════════════════════\n\n"

    # Profile
    text += "👤 **Profile:**\n"
    if class_info:
        text += f"  🏫 Class: {class_info['name']} ({class_info['level']})\n"
    text += f"  ⭐ Points: {points['total_points']}\n"
    text += f"  🔥 Streak: {points['current_streak']} days\n"
    text += f"  🏅 Badges: {len(badges)}\n"
    text += f"  📜 Certificates: {len(certificates)}\n\n"

    # Attendance
    if attendance:
        total_sessions = attendance.get('total_sessions', 0)
        present = attendance.get('present_count', 0)
        absent = attendance.get('absent_count', 0)
        late = attendance.get('late_count', 0)
        rate = (present / total_sessions * 100) if total_sessions > 0 else 0

        text += "📅 **Attendance:**\n"
        text += f"  ✅ Present: {present} | ❌ Absent: {absent} | ⏰ Late: {late}\n"
        text += f"  📊 Rate: {rate:.1f}%\n\n"

    # Unit Progress
    if units:
        overall = sum(u.get('completion_percent', 0) for u in units) / len(units)
        text += f"📚 **Unit Progress:** {overall:.1f}%\n"
        for unit in units[:5]:
            progress = unit.get('completion_percent', 0)
            bar = generate_progress_bar(progress, 5)
            text += f"  [{bar}] Unit {unit['unit_number']}: {progress}%\n"
        text += "\n"

    # Quiz Performance
    if quiz_results:
        total = len(quiz_results)
        passed = sum(1 for r in quiz_results if r.get('passed'))
        pass_rate = (passed / total * 100) if total > 0 else 0
        text += f"📝 **Quiz Performance:**\n"
        text += f"  Total: {total} | Passed: {passed} | Rate: {pass_rate:.1f}%\n\n"

    # Homework
    if homework:
        pending = sum(1 for h in homework if not h.get('submission_id'))
        graded = sum(1 for h in homework if h.get('is_graded'))
        text += f"📋 **Homework:**\n"
        text += f"  Total: {len(homework)} | Pending: {pending} | Graded: {graded}\n\n"

    await callback.message.edit_text(
        text[:4000],
        reply_markup=get_back_keyboard(f"parent_child_{child_id}")
    )

# ========================
# DOWNLOAD REPORT
# ========================

@router.callback_query(F.data.startswith("pp_download_report_"))
async def download_progress_report(callback: CallbackQuery, state: FSMContext):
    """Generate and send downloadable progress report"""
    child_id = int(callback.data.replace("pp_download_report_", ""))
    child = await db.get_user_by_id(child_id)

    if not child:
        await callback.answer("Child not found", show_alert=True)
        return

    await callback.message.edit_text("📥 **Generating report...**")

    # Generate CSV report
    filename = f"progress_report_{child['full_name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(EXPORTS_DIR, filename)
    os.makedirs(EXPORTS_DIR, exist_ok=True)

    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)

        # Header
        writer.writerow(['Progress Report'])
        writer.writerow(['Child', child['full_name']])
        writer.writerow(['Generated', datetime.now().strftime('%Y-%m-%d %H:%M')])
        writer.writerow([])

        # Points and Streaks
        points = await db.get_student_points_and_streak(child_id)
        writer.writerow(['Points & Streaks'])
        writer.writerow(['Total Points', points['total_points']])
        writer.writerow(['Current Streak', f"{points['current_streak']} days"])
        writer.writerow(['Longest Streak', f"{points['longest_streak']} days"])
        writer.writerow([])

        # Unit Progress
        units = await db.get_units_for_student(child_id)
        writer.writerow(['Unit Progress'])
        writer.writerow(['Unit', 'Title', 'Completion %', 'Status'])
        for unit in units:
            writer.writerow([
                unit['unit_number'],
                unit['title'],
                unit.get('completion_percent', 0),
                'Completed' if unit.get('is_completed') else 'In Progress'
            ])
        writer.writerow([])

        # Quiz Results
        quiz_results = await db.get_student_quiz_results(child_id, 100)
        writer.writerow(['Quiz Results'])
        writer.writerow(['Quiz', 'Score', 'Max', 'Percentage', 'Passed', 'Date'])
        for result in quiz_results:
            percentage = (result['score'] / result.get('max_score', 100) * 100) if result.get('max_score', 0) > 0 else 0
            writer.writerow([
                result.get('quiz_title', ''),
                result['score'],
                result.get('max_score', 100),
                f"{percentage:.1f}%",
                'Yes' if result.get('passed') else 'No',
                result.get('completed_at', '')[:10] if result.get('completed_at') else ''
            ])
        writer.writerow([])

        # Homework
        homework = await db.get_homework_for_student(child_id)
        writer.writerow(['Homework Status'])
        writer.writerow(['Title', 'Due Date', 'Submitted', 'Score', 'Max Score', 'Graded'])
        for hw in homework:
            writer.writerow([
                hw.get('title', ''),
                hw.get('deadline', '')[:10] if hw.get('deadline') else '',
                'Yes' if hw.get('submission_id') else 'No',
                hw.get('score', '-') if hw.get('is_graded') else '-',
                hw.get('max_score', '') if hw.get('is_graded') else '',
                'Yes' if hw.get('is_graded') else 'No'
            ])
        writer.writerow([])

        # Attendance
        attendance = await db.get_student_attendance_stats(child_id)
        history = await db.get_student_attendance_history(child_id, 100)
        writer.writerow(['Attendance'])
        writer.writerow(['Total Sessions', attendance.get('total_sessions', 0)])
        writer.writerow(['Present', attendance.get('present_count', 0)])
        writer.writerow(['Late', attendance.get('late_count', 0)])
        writer.writerow(['Absent', attendance.get('absent_count', 0)])
        writer.writerow(['Excused', attendance.get('excused_count', 0)])
        writer.writerow([])
        writer.writerow(['Date', 'Status', 'Class'])
        for record in history:
            writer.writerow([
                record.get('session_date', ''),
                record.get('status', ''),
                record.get('class_name', '')
            ])

    document = FSInputFile(filepath)
    await callback.message.answer_document(
        document=document,
        caption=f"📊 Progress Report: {child['full_name']}\n📅 {datetime.now().strftime('%Y-%m-%d')}"
    )

    await callback.message.edit_text(
        "✅ Report generated and sent!",
        reply_markup=get_back_keyboard(f"parent_child_{child_id}")
    )

@router.callback_query(F.data == "pp_back")
async def back_to_progress_menu(callback: CallbackQuery, state: FSMContext):
    """Back to progress menu"""
    await progress_menu(callback.message, state)
