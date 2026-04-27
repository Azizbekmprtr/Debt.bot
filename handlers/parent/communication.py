# handlers/parent/communication.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database.queries as db
from keyboards.all_keyboards import (
    get_parent_main_menu, get_parent_children_keyboard,
    get_cancel_keyboard, get_back_keyboard
)

router = Router()

class ParentMessageStates(StatesGroup):
    composing_message = State()
    selecting_recipient = State()

async def get_parent_context(state: FSMContext) -> dict:
    data = await state.get_data()
    telegram_id = data.get('telegram_id', 0)
    parent = await db.get_user_by_telegram_id(telegram_id) if telegram_id else None
    if not parent:
        return {'parent': None, 'parent_id': None, 'children': []}
    children = await db.get_children_for_parent(parent['id'])
    return {'parent': parent, 'parent_id': parent['id'], 'children': children}

@router.message(F.text == "💬 Messages")
async def communication_menu(message: Message, state: FSMContext):
    """Show communication menu"""
    ctx = await get_parent_context(state)
    parent = ctx.get('parent')

    if not parent:
        await message.answer("❌ Parent account not found.")
        return

    # Get unread messages
    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT COUNT(*) FROM messages WHERE receiver_id = ? AND is_read = 0
        """, (parent['id'],))
        unread = (await cursor.fetchone())[0]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍🏫 Contact Teacher", callback_data="pc_contact_teacher")],
        [InlineKeyboardButton(text="🏢 Contact Admin", callback_data="pc_contact_admin")],
        [InlineKeyboardButton(text=f"📨 Messages ({unread} unread)", callback_data="pc_view_messages")],
        [InlineKeyboardButton(text="📢 Announcements", callback_data="pc_announcements")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="p_back")]
    ])

    text = "💬 **Communication**\n\n"
    text += f"📨 Unread Messages: **{unread}**\n\n"
    text += "Select action:"

    await message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data == "pc_contact_teacher")
async def contact_teacher_start(callback: CallbackQuery, state: FSMContext):
    """Start contacting a teacher"""
    ctx = await get_parent_context(state)
    children = ctx.get('children', [])

    if not children:
        await callback.answer("No children linked", show_alert=True)
        return

    # Get all teachers for all children's classes
    teachers_seen = set()
    teacher_list = []

    for child in children:
        classes = await db.get_classes_for_student(child['id'])
        for cls in classes:
            teachers = await db.get_teachers_for_class(cls['id'])
            for teacher in teachers:
                if teacher['id'] not in teachers_seen:
                    teachers_seen.add(teacher['id'])
                    teacher['class_name'] = cls['name']
                    teacher['child_name'] = child['full_name']
                    teacher_list.append(teacher)

    if not teacher_list:
        await callback.message.edit_text(
            "No teachers assigned to your children's classes.",
            reply_markup=get_back_keyboard("pc_back")
        )
        return

    buttons = []
    for teacher in teacher_list:
        buttons.append([InlineKeyboardButton(
            text=f"👨‍🏫 {teacher['full_name']} ({teacher['class_name']})",
            callback_data=f"pc_msg_teacher_{teacher['id']}_{teacher.get('child_name', '')[:20]}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="pc_back")])

    await callback.message.edit_text(
        "👨‍🏫 **Contact Teacher**\n\nSelect teacher to message:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@router.callback_query(F.data.startswith("pc_msg_teacher_"))
async def compose_teacher_message(callback: CallbackQuery, state: FSMContext):
    """Compose message to teacher"""
    parts = callback.data.replace("pc_msg_teacher_", "").split("_")
    teacher_id = int(parts[0])

    await state.update_data(msg_receiver_id=teacher_id)

    await callback.message.edit_text(
        "💬 **Compose Message**\n\n"
        "Type your message below:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(ParentMessageStates.composing_message)

@router.callback_query(F.data == "pc_contact_admin")
async def contact_admin_start(callback: CallbackQuery, state: FSMContext):
    """Start contacting center admin"""
    ctx = await get_parent_context(state)
    children = ctx.get('children', [])

    if not children:
        await callback.answer("No children linked", show_alert=True)
        return

    # Get center admins for children's centers
    admin_list = []
    admin_seen = set()

    for child in children:
        classes = await db.get_classes_for_student(child['id'])
        for cls in classes:
            center_id = cls.get('center_id')
            if center_id and center_id not in admin_seen:
                async with db.get_db() as conn:
                    cursor = await conn.execute("""
                        SELECT u.* FROM users u
                        JOIN user_roles ur ON u.id = ur.user_id
                        WHERE ur.center_id = ? AND ur.role = 'center_admin'
                    """, (center_id,))
                    admins = [dict(row) for row in await cursor.fetchall()]
                    for admin in admins:
                        if admin['id'] not in admin_seen:
                            admin_seen.add(admin['id'])
                            admin_list.append(admin)

    if not admin_list:
        await callback.message.edit_text(
            "No center admins available.",
            reply_markup=get_back_keyboard("pc_back")
        )
        return

    buttons = []
    for admin in admin_list:
        buttons.append([InlineKeyboardButton(
            text=f"🏢 {admin['full_name']}",
            callback_data=f"pc_msg_user_{admin['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="pc_back")])

    await callback.message.edit_text(
        "🏢 **Contact Center Admin**\n\nSelect admin to message:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@router.callback_query(F.data.startswith("pc_msg_user_"))
async def compose_user_message(callback: CallbackQuery, state: FSMContext):
    """Compose message to any user"""
    user_id = int(callback.data.replace("pc_msg_user_", ""))

    await state.update_data(msg_receiver_id=user_id)

    await callback.message.edit_text(
        "💬 **Compose Message**\n\n"
        "Type your message below:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(ParentMessageStates.composing_message)

@router.message(ParentMessageStates.composing_message, F.text)
async def send_message(message: Message, state: FSMContext):
    """Send composed message"""
    ctx = await get_parent_context(state)
    parent_id = ctx['parent_id']
    data = await state.get_data()
    receiver_id = data.get('msg_receiver_id')

    if not receiver_id:
        await message.answer("❌ Error: No recipient selected.")
        await state.clear()
        return

    msg_id = await db.send_message(
        sender_id=parent_id,
        receiver_id=receiver_id,
        content=message.text.strip()
    )

    if msg_id:
        await message.answer(
            "✅ **Message Sent!**\n\n"
            "You will be notified when they respond.",
            reply_markup=get_parent_main_menu()
        )
    else:
        await message.answer(
            "❌ Failed to send message.",
            reply_markup=get_parent_main_menu()
        )

    await state.clear()

@router.callback_query(F.data == "pc_view_messages")
async def view_messages(callback: CallbackQuery, state: FSMContext):
    """View recent messages"""
    ctx = await get_parent_context(state)
    parent_id = ctx['parent_id']

    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT m.*, u.full_name as sender_name, u2.full_name as receiver_name
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            JOIN users u2 ON m.receiver_id = u2.id
            WHERE m.sender_id = ? OR m.receiver_id = ?
            ORDER BY m.created_at DESC
            LIMIT 30
        """, (parent_id, parent_id))
        messages = [dict(row) for row in await cursor.fetchall()]

    if not messages:
        await callback.message.edit_text(
            "📨 No messages yet.",
            reply_markup=get_back_keyboard("pc_back")
        )
        return

    text = "📨 **Messages**\n\n"

    for msg in messages:
        is_sent = msg['sender_id'] == parent_id
        direction = "📤 To:" if is_sent else "📥 From:"
        other_person = msg['receiver_name'] if is_sent else msg['sender_name']
        read_status = "" if is_sent else (" ✅" if msg['is_read'] else " 🔵")

        text += f"{direction} **{other_person}**{read_status}\n"
        text += f"  {msg['content'][:100]}\n"
        text += f"  {msg['created_at'][:19] if msg.get('created_at') else 'N/A'}\n\n"

    # Mark messages as read
    await db.mark_messages_read(parent_id)

    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard("pc_back")
    )

@router.callback_query(F.data == "pc_announcements")
async def view_announcements(callback: CallbackQuery, state: FSMContext):
    """View announcements"""
    ctx = await get_parent_context(state)
    children = ctx.get('children', [])

    if not children:
        await callback.answer("No children linked", show_alert=True)
        return

    all_announcements = []
    for child in children:
        classes = await db.get_classes_for_student(child['id'])
        for cls in classes:
            announcements = await db.get_announcements_for_class(cls['id'])
            for ann in announcements:
                ann['class_name'] = cls['name']
                all_announcements.append(ann)

    # Remove duplicates
    seen = set()
    unique_announcements = []
    for ann in all_announcements:
        if ann['id'] not in seen:
            seen.add(ann['id'])
            unique_announcements.append(ann)

    if not unique_announcements:
        await callback.message.edit_text(
            "📢 No announcements yet.",
            reply_markup=get_back_keyboard("pc_back")
        )
        return

    text = "📢 **Announcements**\n\n"

    for ann in unique_announcements[:15]:
        text += f"📌 **{ann['title']}**\n"
        if ann.get('class_name'):
            text += f"  🏫 {ann['class_name']}\n"
        text += f"  {ann['content'][:200]}\n"
        text += f"  📅 {ann['created_at'][:10] if ann.get('created_at') else 'N/A'}\n\n"

    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard("pc_back")
    )

@router.callback_query(F.data == "pc_back")
async def back_to_communication_menu(callback: CallbackQuery, state: FSMContext):
    """Back to communication menu"""
    await communication_menu(callback.message, state)
