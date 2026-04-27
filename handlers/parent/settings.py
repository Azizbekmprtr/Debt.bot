# handlers/parent/settings.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database.queries as db
from keyboards.all_keyboards import (
    get_parent_main_menu, get_cancel_keyboard,
    get_back_keyboard
)

router = Router()

class ParentSettingsStates(StatesGroup):
    editing_phone = State()
    toggling_notifications = State()

async def get_parent_context(state: FSMContext) -> dict:
    data = await state.get_data()
    telegram_id = data.get('telegram_id', 0)
    parent = await db.get_user_by_telegram_id(telegram_id) if telegram_id else None
    if not parent:
        return {'parent': None, 'parent_id': None}
    children = await db.get_children_for_parent(parent['id'])
    return {'parent': parent, 'parent_id': parent['id'], 'children': children}

@router.message(F.text == "⚙️ Settings")
async def parent_settings(message: Message, state: FSMContext):
    """Show parent settings"""
    ctx = await get_parent_context(state)
    parent = ctx.get('parent')

    if not parent:
        await message.answer("❌ Parent account not found.")
        return

    # Get notification preferences
    notifications = await db.get_parent_notification_settings(parent['id'])

    text = "⚙️ **Settings**\n\n"
    text += f"👤 **Account:** {parent['full_name']}\n"
    text += f"📱 **Phone:** {parent.get('phone', 'N/A')}\n\n"

    text += "🔔 **Notification Preferences:**\n"
    text += f"  Attendance Alerts: {'✅' if notifications.get('attendance', True) else '❌'}\n"
    text += f"  Payment Reminders: {'✅' if notifications.get('payments', True) else '❌'}\n"
    text += f"  Competition Alerts: {'✅' if notifications.get('competitions', True) else '❌'}\n"
    text += f"  Exam Reminders: {'✅' if notifications.get('exams', True) else '❌'}\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 Edit Phone", callback_data="ps_edit_phone")],
        [InlineKeyboardButton(text="🔔 Notification Settings", callback_data="ps_notifications")],
        [InlineKeyboardButton(text="👶 Manage Children", callback_data="ps_children")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="p_back")]
    ])

    await message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data == "ps_edit_phone")
async def edit_phone_start(callback: CallbackQuery, state: FSMContext):
    """Start editing phone"""
    await callback.message.edit_text(
        "📞 Enter your new phone number:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(ParentSettingsStates.editing_phone)

@router.message(ParentSettingsStates.editing_phone, F.text)
async def save_phone(message: Message, state: FSMContext):
    """Save new phone"""
    ctx = await get_parent_context(state)
    parent_id = ctx['parent_id']

    from utils.helpers import validate_phone
    is_valid, phone = validate_phone(message.text.strip())

    if not is_valid:
        await message.answer("❌ Invalid phone format.")
        return

    await db.update_user_field(parent_id, 'phone', phone)

    await message.answer(
        "✅ Phone updated!",
        reply_markup=get_parent_main_menu()
    )
    await state.clear()

@router.callback_query(F.data == "ps_notifications")
async def notification_settings(callback: CallbackQuery, state: FSMContext):
    """Manage notification settings"""
    ctx = await get_parent_context(state)
    parent_id = ctx['parent_id']
    notifications = await db.get_parent_notification_settings(parent_id)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"📅 Attendance: {'✅ ON' if notifications.get('attendance', True) else '❌ OFF'}",
            callback_data="ps_toggle_attendance"
        )],
        [InlineKeyboardButton(
            text=f"💰 Payments: {'✅ ON' if notifications.get('payments', True) else '❌ OFF'}",
            callback_data="ps_toggle_payments"
        )],
        [InlineKeyboardButton(
            text=f"🏆 Competitions: {'✅ ON' if notifications.get('competitions', True) else '❌ OFF'}",
            callback_data="ps_toggle_competitions"
        )],
        [InlineKeyboardButton(
            text=f"📝 Exams: {'✅ ON' if notifications.get('exams', True) else '❌ OFF'}",
            callback_data="ps_toggle_exams"
        )],
        [InlineKeyboardButton(text="🔙 Back", callback_data="ps_back")]
    ])

    await callback.message.edit_text(
        "🔔 **Notification Settings**\n\nToggle notifications:",
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("ps_toggle_"))
async def toggle_notification(callback: CallbackQuery, state: FSMContext):
    """Toggle a notification setting"""
    setting = callback.data.replace("ps_toggle_", "")
    ctx = await get_parent_context(state)
    parent_id = ctx['parent_id']

    await db.toggle_parent_notification(parent_id, setting)

    await callback.answer(f"✅ {setting.title()} notifications toggled!")
    await notification_settings(callback, state)

@router.callback_query(F.data == "ps_children")
async def manage_children(callback: CallbackQuery, state: FSMContext):
    """View linked children"""
    ctx = await get_parent_context(state)
    children = ctx.get('children', [])

    if not children:
        await callback.message.edit_text(
            "👶 No children linked to your account.\n"
            "Contact the center admin to link your child.",
            reply_markup=get_back_keyboard("ps_back")
        )
        return

    text = "👶 **Linked Children**\n\n"
    buttons = []

    for child in children:
        classes = await db.get_classes_for_student(child['id'])
        class_info = classes[0] if classes else None

        text += f"**{child['full_name']}**\n"
        if class_info:
            text += f"  🏫 {class_info['name']} ({class_info['level']})\n"
        text += f"  📞 {child.get('phone', 'N/A')}\n"
        text += f"  Relationship: {child.get('relationship', 'Parent')}\n\n"

    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="ps_back")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data == "ps_back")
async def back_to_parent_settings(callback: CallbackQuery, state: FSMContext):
    """Back to parent settings"""
    await parent_settings(callback.message, state)
