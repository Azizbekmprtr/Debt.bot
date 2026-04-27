# handlers/super_admin/centers.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
import database.queries as db
from keyboards.all_keyboards import (
    get_super_admin_centers_menu, get_super_admin_main_menu,
    get_cancel_keyboard, get_confirm_keyboard, get_back_keyboard,
    get_pagination_keyboard
)
import json
import re

router = Router()

# ========================
# CENTER MANAGEMENT STATES
# ========================

class CreateCenterStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_slug = State()
    waiting_for_plan = State()
    waiting_for_admin_id = State()
    confirm_creation = State()

class EditCenterStates(StatesGroup):
    selecting_center = State()
    selecting_field = State()
    entering_value = State()
    confirm_edit = State()

class SuspendCenterStates(StatesGroup):
    selecting_center = State()
    entering_reason = State()
    confirm_suspend = State()

class DeleteCenterStates(StatesGroup):
    selecting_center = State()
    confirm_delete = State()

# ========================
# MAIN CENTERS MENU
# ========================

@router.message(F.text == "🏢 Centers")
async def centers_main_menu(message: Message, state: FSMContext):
    """Show centers management main menu"""
    await message.answer(
        "🏢 **Centers Management**\n\n"
        "Manage all study centers on the platform.\n"
        "Select an action:",
        reply_markup=get_super_admin_centers_menu()
    )

@router.callback_query(F.data == "sa_back")
async def back_to_sa_main(callback: CallbackQuery, state: FSMContext):
    """Return to super admin main menu"""
    await callback.message.delete()
    await callback.message.answer(
        "👑 Super Admin Panel",
        reply_markup=get_super_admin_main_menu()
    )

# ========================
# VIEW ALL CENTERS
# ========================

@router.callback_query(F.data == "sa_list_centers")
async def list_all_centers(callback: CallbackQuery, state: FSMContext):
    """List all centers with pagination"""
    centers = await db.get_all_centers(include_suspended=True)

    if not centers:
        await callback.message.edit_text(
            "No centers found. Create your first center!",
            reply_markup=get_back_keyboard("sa_back")
        )
        return

    await state.update_data(centers=centers, centers_page=0)
    await display_centers_page(callback.message, state, 0)

async def display_centers_page(message, state: FSMContext, page: int):
    """Display a page of centers"""
    data = await state.get_data()
    centers = data.get('centers', [])
    per_page = 10
    total_pages = (len(centers) + per_page - 1) // per_page
    start = page * per_page
    end = start + per_page
    page_centers = centers[start:end]

    text = "📋 **All Centers**\n\n"

    for center in page_centers:
        status_icon = "🟢" if center['is_active'] and not center['is_suspended'] else "🔴" if center['is_suspended'] else "🟡"
        plan = center.get('subscription_plan', 'basic')
        expires = center.get('plan_expires_at', 'N/A')
        if isinstance(expires, str) and expires != 'N/A':
            expires = expires[:10]

        text += f"{status_icon} **{center['name']}**\n"
        text += f"   ID: {center['id']} | Plan: {plan.title()}\n"
        text += f"   Created: {center['created_at'][:10] if center['created_at'] else 'N/A'}\n"
        text += f"   Expires: {expires}\n"
        text += "─" * 30 + "\n"

    text += f"\nPage {page+1}/{total_pages} | Total: {len(centers)} centers"

    # Build keyboard
    buttons = []

    # Action buttons for each center on this page
    for center in page_centers:
        buttons.append([InlineKeyboardButton(
            text=f"📊 {center['name']} - Details",
            callback_data=f"sa_center_detail_{center['id']}"
        )])

    # Pagination
    pagination_row = []
    if page > 0:
        pagination_row.append(InlineKeyboardButton(text="⬅️ Previous", callback_data=f"sa_centers_page_{page-1}"))
    pagination_row.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        pagination_row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"sa_centers_page_{page+1}"))
    buttons.append(pagination_row)

    # Navigation
    buttons.append([InlineKeyboardButton(text="➕ Create Center", callback_data="sa_create_center")])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await state.update_data(centers_page=page)

    if isinstance(message, Message):
        await message.answer(text, reply_markup=keyboard)
    else:
        await message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("sa_centers_page_"))
async def handle_centers_pagination(callback: CallbackQuery, state: FSMContext):
    """Handle centers list pagination"""
    page = int(callback.data.replace("sa_centers_page_", ""))
    await display_centers_page(callback.message, state, page)

# ========================
# CENTER DETAILS
# ========================

@router.callback_query(F.data.startswith("sa_center_detail_"))
async def view_center_details(callback: CallbackQuery, state: FSMContext):
    """View detailed information about a center"""
    center_id = int(callback.data.replace("sa_center_detail_", ""))
    center = await db.get_center_by_id(center_id)

    if not center:
        await callback.answer("Center not found", show_alert=True)
        return

    # Get statistics
    stats = await get_center_statistics(center_id)

    status = "🟢 Active" if center['is_active'] and not center['is_suspended'] else "🔴 Suspended" if center['is_suspended'] else "🟡 Inactive"

    text = f"🏢 **{center['name']}**\n\n"
    text += f"📋 **Status:** {status}\n"
    text += f"🆔 **ID:** {center['id']}\n"
    text += f"🔗 **Slug:** {center.get('slug', 'N/A')}\n"
    text += f"💰 **Plan:** {center.get('subscription_plan', 'basic').title()}\n"
    text += f"📅 **Created:** {center['created_at'][:10] if center['created_at'] else 'N/A'}\n"
    text += f"⏰ **Expires:** {center.get('plan_expires_at', 'N/A')}\n"
    text += f"🌐 **Language:** {center.get('language', 'uz')}\n"
    text += f"🕐 **Timezone:** {center.get('timezone', 'Asia/Tashkent')}\n"

    if center.get('suspended_reason'):
        text += f"⚠️ **Suspension Reason:** {center['suspended_reason']}\n"

    text += f"\n📊 **Statistics:**\n"
    text += f"👨‍🏫 Teachers: {stats['teacher_count']}\n"
    text += f"🎓 Students: {stats['student_count']}\n"
    text += f"🏫 Classes: {stats['class_count']}\n"
    text += f"📝 Quizzes: {stats['quiz_count']}\n"
    text += f"💰 Total Revenue: {stats['total_revenue']:,.0f} UZS\n"

    # Build action buttons
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Edit Center", callback_data=f"sa_edit_center_{center_id}")],
        [
            InlineKeyboardButton(text="⏸️ Suspend" if not center['is_suspended'] else "▶️ Activate",
                               callback_data=f"sa_toggle_center_{center_id}"),
            InlineKeyboardButton(text="🗑️ Delete", callback_data=f"sa_delete_center_{center_id}")
        ],
        [InlineKeyboardButton(text="💰 Manage Subscription", callback_data=f"sa_center_subscription_{center_id}")],
        [InlineKeyboardButton(text="📊 Full Analytics", callback_data=f"sa_center_analytics_{center_id}")],
        [InlineKeyboardButton(text="🔙 Back to List", callback_data="sa_list_centers")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)

async def get_center_statistics(center_id: int) -> dict:
    """Get comprehensive statistics for a center"""
    stats = {
        'teacher_count': 0,
        'student_count': 0,
        'class_count': 0,
        'quiz_count': 0,
        'total_revenue': 0
    }

    async with db.get_db() as conn:
        # Teacher count
        cursor = await conn.execute("""
            SELECT COUNT(DISTINCT ur.user_id) FROM user_roles ur
            WHERE ur.center_id = ? AND ur.role = 'teacher'
        """, (center_id,))
        row = await cursor.fetchone()
        stats['teacher_count'] = row[0] if row else 0

        # Student count
        cursor = await conn.execute("""
            SELECT COUNT(DISTINCT ur.user_id) FROM user_roles ur
            WHERE ur.center_id = ? AND ur.role = 'student'
        """, (center_id,))
        row = await cursor.fetchone()
        stats['student_count'] = row[0] if row else 0

        # Class count
        cursor = await conn.execute("""
            SELECT COUNT(*) FROM classes WHERE center_id = ? AND is_archived = 0
        """, (center_id,))
        row = await cursor.fetchone()
        stats['class_count'] = row[0] if row else 0

        # Quiz count
        cursor = await conn.execute("""
            SELECT COUNT(*) FROM quizzes q
            JOIN units u ON q.unit_id = u.id
            JOIN classes c ON u.class_id = c.id
            WHERE c.center_id = ? AND q.is_active = 1
        """, (center_id,))
        row = await cursor.fetchone()
        stats['quiz_count'] = row[0] if row else 0

        # Total revenue
        cursor = await conn.execute("""
            SELECT COALESCE(SUM(amount), 0) FROM payments WHERE center_id = ?
        """, (center_id,))
        row = await cursor.fetchone()
        stats['total_revenue'] = row[0] if row else 0

    return stats

# ========================
# CREATE CENTER
# ========================

@router.callback_query(F.data == "sa_create_center")
async def start_create_center(callback: CallbackQuery, state: FSMContext):
    """Start center creation flow"""
    await callback.message.edit_text(
        "🏢 **Create New Center**\n\n"
        "Please enter the center name:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreateCenterStates.waiting_for_name)

@router.message(CreateCenterStates.waiting_for_name, F.text)
async def process_center_name(message: Message, state: FSMContext):
    """Process center name and ask for slug"""
    name = message.text.strip()

    if len(name) < 3 or len(name) > 100:
        await message.answer("❌ Center name must be between 3 and 100 characters. Please try again:")
        return

    # Auto-generate slug suggestion
    slug = re.sub(r'[^a-z0-9-]', '', name.lower().replace(' ', '-'))

    await state.update_data(center_name=name, center_slug=slug)

    await message.answer(
        f"✅ Name: **{name}**\n\n"
        f"Suggested slug: `{slug}`\n\n"
        "Enter the slug (URL-friendly identifier) or type 'use' to accept suggestion:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreateCenterStates.waiting_for_slug)

@router.message(CreateCenterStates.waiting_for_slug, F.text)
async def process_center_slug(message: Message, state: FSMContext):
    """Process center slug and ask for plan"""
    data = await state.get_data()

    if message.text.strip().lower() == 'use':
        slug = data['center_slug']
    else:
        slug = re.sub(r'[^a-z0-9-]', '', message.text.strip().lower())

    if len(slug) < 2:
        await message.answer("❌ Slug must be at least 2 characters. Please try again:")
        return

    # Check if slug is unique
    async with db.get_db() as conn:
        cursor = await conn.execute("SELECT id FROM centers WHERE slug = ?", (slug,))
        if await cursor.fetchone():
            await message.answer("❌ This slug is already taken. Please choose another:")
            return

    await state.update_data(center_slug=slug)

    # Get subscription plans
    plans = await db.get_all_subscription_plans()

    buttons = []
    for plan in plans:
        buttons.append([InlineKeyboardButton(
            text=f"{plan['name']} - ${plan['price_monthly']}/mo",
            callback_data=f"create_center_plan_{plan['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")])

    await message.answer(
        f"✅ Slug: `{slug}`\n\n"
        "Select subscription plan:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await state.set_state(CreateCenterStates.waiting_for_plan)

@router.callback_query(CreateCenterStates.waiting_for_plan, F.data.startswith("create_center_plan_"))
async def process_center_plan(callback: CallbackQuery, state: FSMContext):
    """Process plan selection and ask for admin Telegram ID"""
    plan_id = int(callback.data.replace("create_center_plan_", ""))
    await state.update_data(center_plan_id=plan_id)

    await callback.message.edit_text(
        "Enter the Telegram ID of the center admin:\n\n"
        "This user will have full control over this center.",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreateCenterStates.waiting_for_admin_id)

@router.message(CreateCenterStates.waiting_for_admin_id, F.text)
async def process_admin_id(message: Message, state: FSMContext):
    """Process admin ID and confirm creation"""
    try:
        admin_telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Please enter a valid Telegram ID (numbers only):")
        return

    # Check if user exists, if not create them
    user = await db.get_user_by_telegram_id(admin_telegram_id)

    if not user:
        # Create user placeholder
        user_id = await db.create_user(
            telegram_id=admin_telegram_id,
            full_name=f"Admin_{admin_telegram_id}",
            role='center_admin'
        )
    else:
        user_id = user['id']

    await state.update_data(admin_id=user_id, admin_telegram_id=admin_telegram_id)

    data = await state.get_data()

    # Show confirmation
    plan = await db.get_subscription_plan_by_id(data['center_plan_id'])

    text = "🏢 **Confirm Center Creation**\n\n"
    text += f"📛 **Name:** {data['center_name']}\n"
    text += f"🔗 **Slug:** {data['center_slug']}\n"
    text += f"💰 **Plan:** {plan['name']} (${plan['price_monthly']}/mo)\n"
    text += f"👤 **Admin ID:** {admin_telegram_id}\n\n"
    text += "Create this center?"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Create", callback_data="confirm_create_center"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")
        ]
    ])

    await message.answer(text, reply_markup=keyboard)
    await state.set_state(CreateCenterStates.confirm_creation)

@router.callback_query(CreateCenterStates.confirm_creation, F.data == "confirm_create_center")
async def confirm_create_center(callback: CallbackQuery, state: FSMContext):
    """Finalize center creation"""
    data = await state.get_data()

    center_id = await db.create_center(
        name=data['center_name'],
        slug=data['center_slug'],
        admin_id=data['admin_id'],
        subscription_plan=data.get('center_plan_slug', 'basic')
    )

    if center_id:
        # Log audit
        await db.log_audit(
            user_id=callback.from_user.id,
            action='create_center',
            entity_type='center',
            entity_id=center_id,
            new_values={'name': data['center_name'], 'slug': data['center_slug']}
        )

        await callback.message.edit_text(
            f"✅ **Center Created Successfully!**\n\n"
            f"🏢 **Name:** {data['center_name']}\n"
            f"🆔 **ID:** {center_id}\n"
            f"🔗 **Slug:** {data['center_slug']}\n\n"
            "The center admin can now use /start to access their dashboard.",
            reply_markup=get_back_keyboard("sa_list_centers")
        )
    else:
        await callback.message.edit_text(
            "❌ Failed to create center. Please try again.",
            reply_markup=get_back_keyboard("sa_back")
        )

    await state.clear()

# ========================
# SEARCH CENTERS
# ========================

@router.callback_query(F.data == "sa_search_centers")
async def search_centers_start(callback: CallbackQuery, state: FSMContext):
    """Start center search"""
    await callback.message.edit_text(
        "🔍 **Search Centers**\n\n"
        "Enter search term (name, ID, or slug):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state("search_centers")

@router.message(F.text, state="search_centers")
async def process_center_search(message: Message, state: FSMContext):
    """Process center search"""
    search_term = message.text.strip()

    centers = await db.search_centers(search_term)

    if not centers:
        await message.answer(
            f"No centers found matching '{search_term}'",
            reply_markup=get_back_keyboard("sa_back")
        )
        await state.clear()
        return

    text = f"🔍 **Search Results for '{search_term}'**\n\n"
    buttons = []

    for center in centers[:10]:
        status = "🟢" if center['is_active'] and not center['is_suspended'] else "🔴"
        text += f"{status} {center['name']} (ID: {center['id']})\n"
        buttons.append([InlineKeyboardButton(
            text=f"{center['name']}",
            callback_data=f"sa_center_detail_{center['id']}"
        )])

    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="sa_list_centers")])

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await state.clear()

# ========================
# SUSPEND/ACTIVATE CENTER
# ========================

@router.callback_query(F.data.startswith("sa_toggle_center_"))
async def toggle_center_status(callback: CallbackQuery, state: FSMContext):
    """Toggle center suspension status"""
    center_id = int(callback.data.replace("sa_toggle_center_", ""))
    center = await db.get_center_by_id(center_id)

    if not center:
        await callback.answer("Center not found", show_alert=True)
        return

    if center['is_suspended']:
        # Activate center
        await db.activate_center(center_id)
        await callback.answer("✅ Center activated!")

        # Log audit
        await db.log_audit(
            user_id=callback.from_user.id,
            action='activate_center',
            entity_type='center',
            entity_id=center_id
        )

        await view_center_details(callback, state)
    else:
        # Ask for suspension reason
        await callback.message.edit_text(
            f"⚠️ **Suspend Center: {center['name']}**\n\n"
            "Enter the reason for suspension:",
            reply_markup=get_cancel_keyboard()
        )
        await state.update_data(suspend_center_id=center_id)
        await state.set_state(SuspendCenterStates.entering_reason)

@router.message(SuspendCenterStates.entering_reason, F.text)
async def process_suspension_reason(message: Message, state: FSMContext):
    """Process suspension reason"""
    reason = message.text.strip()
    data = await state.get_data()
    center_id = data['suspend_center_id']

    await db.suspend_center(center_id, reason)

    # Log audit
    await db.log_audit(
        user_id=message.from_user.id,
        action='suspend_center',
        entity_type='center',
        entity_id=center_id,
        new_values={'reason': reason}
    )

    await message.answer(
        f"✅ Center {center_id} has been suspended.\n\n"
        f"Reason: {reason}",
        reply_markup=get_back_keyboard("sa_list_centers")
    )
    await state.clear()

# ========================
# DELETE CENTER
# ========================

@router.callback_query(F.data.startswith("sa_delete_center_"))
async def confirm_delete_center(callback: CallbackQuery, state: FSMContext):
    """Confirm center deletion"""
    center_id = int(callback.data.replace("sa_delete_center_", ""))
    center = await db.get_center_by_id(center_id)

    if not center:
        await callback.answer("Center not found", show_alert=True)
        return

    await state.update_data(delete_center_id=center_id)

    text = "⚠️ **CONFIRM DELETION**\n\n"
    text += f"Are you sure you want to delete **{center['name']}**?\n\n"
    text += "This will permanently delete:\n"
    text += "• All users associated with this center\n"
    text += "• All classes, units, and materials\n"
    text += "• All quizzes and homework\n"
    text += "• All attendance records\n"
    text += "• All payment records\n\n"
    text += "This action **CANNOT** be undone!\n\n"
    text += "Type 'DELETE' to confirm:"

    await callback.message.edit_text(text, reply_markup=get_cancel_keyboard())
    await state.set_state(DeleteCenterStates.confirm_delete)

@router.message(DeleteCenterStates.confirm_delete, F.text)
async def process_delete_center(message: Message, state: FSMContext):
    """Process center deletion"""
    if message.text.strip().upper() != 'DELETE':
        await message.answer("❌ Deletion cancelled. Type 'DELETE' to confirm or cancel.")
        return

    data = await state.get_data()
    center_id = data['delete_center_id']
    center = await db.get_center_by_id(center_id)

    # Log audit before deletion
    await db.log_audit(
        user_id=message.from_user.id,
        action='delete_center',
        entity_type='center',
        entity_id=center_id,
        old_values={'name': center['name'] if center else 'Unknown'}
    )

    await db.delete_center(center_id)

    await message.answer(
        f"✅ Center (ID: {center_id}) has been permanently deleted.",
        reply_markup=get_super_admin_main_menu()
    )
    await state.clear()

# ========================
# CENTER ANALYTICS
# ========================

@router.callback_query(F.data == "sa_center_analytics")
async def show_center_analytics(callback: CallbackQuery, state: FSMContext):
    """Show analytics for all centers"""
    centers = await db.get_all_centers()

    if not centers:
        await callback.message.edit_text(
            "No centers found for analytics.",
            reply_markup=get_back_keyboard("sa_back")
        )
        return

    # Aggregate analytics
    total_students = 0
    total_teachers = 0
    total_classes = 0
    total_revenue = 0.0
    total_quizzes_completed = 0

    for center in centers:
        stats = await get_center_statistics(center['id'])
        total_students += stats['student_count']
        total_teachers += stats['teacher_count']
        total_classes += stats['class_count']
        total_revenue += stats['total_revenue']

    # Get quiz completion stats
    async with db.get_db() as conn:
        cursor = await conn.execute("SELECT COUNT(*) FROM quiz_attempts WHERE completed_at IS NOT NULL")
        row = await cursor.fetchone()
        total_quizzes_completed = row[0] if row else 0

    text = "📊 **Platform-Wide Analytics**\n\n"
    text += f"🏢 **Total Centers:** {len(centers)}\n"
    text += f"👨‍🏫 **Total Teachers:** {total_teachers}\n"
    text += f"🎓 **Total Students:** {total_students}\n"
    text += f"🏫 **Total Classes:** {total_classes}\n"
    text += f"📝 **Total Quizzes Completed:** {total_quizzes_completed}\n"
    text += f"💰 **Total Revenue:** {total_revenue:,.0f} UZS\n\n"

    # Per-center breakdown
    text += "**Per-Center Breakdown:**\n"
    for center in centers[:10]:
        stats = await get_center_statistics(center['id'])
        text += f"\n🏢 **{center['name']}**\n"
        text += f"   Students: {stats['student_count']} | Teachers: {stats['teacher_count']}\n"
        text += f"   Revenue: {stats['total_revenue']:,.0f} UZS\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Export Full Report", callback_data="sa_export_analytics")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)

# ========================
# EDIT CENTER
# ========================

@router.callback_query(F.data.startswith("sa_edit_center_"))
async def edit_center_start(callback: CallbackQuery, state: FSMContext):
    """Start editing a center"""
    center_id = int(callback.data.replace("sa_edit_center_", ""))
    center = await db.get_center_by_id(center_id)

    if not center:
        await callback.answer("Center not found", show_alert=True)
        return

    await state.update_data(edit_center_id=center_id, edit_center=center)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Edit Name", callback_data="sa_edit_field_name")],
        [InlineKeyboardButton(text="🔗 Edit Slug", callback_data="sa_edit_field_slug")],
        [InlineKeyboardButton(text="💰 Change Plan", callback_data=f"sa_center_subscription_{center_id}")],
        [InlineKeyboardButton(text="🎨 Branding", callback_data="sa_edit_field_branding")],
        [InlineKeyboardButton(text="🌐 Language", callback_data="sa_edit_field_language")],
        [InlineKeyboardButton(text="🕐 Timezone", callback_data="sa_edit_field_timezone")],
        [InlineKeyboardButton(text="🔙 Back", callback_data=f"sa_center_detail_{center_id}")]
    ])

    await callback.message.edit_text(
        f"✏️ **Edit Center: {center['name']}**\n\n"
        "Select field to edit:",
        reply_markup=keyboard
    )
