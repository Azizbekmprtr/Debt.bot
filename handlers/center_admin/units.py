# handlers/center_admin/units.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
import database.queries as db
from keyboards.all_keyboards import (
    get_center_admin_main_menu, get_cancel_keyboard,
    get_confirm_keyboard, get_back_keyboard
)

router = Router()


# ========================
# UNIT MANAGEMENT STATES
# ========================

class CreateUnitStates(StatesGroup):
    selecting_class = State()
    entering_title = State()
    entering_number = State()
    entering_description = State()
    entering_video_url = State()
    entering_audio_url = State()
    entering_pdf_url = State()
    confirm = State()


class EditUnitStates(StatesGroup):
    selecting_unit = State()
    selecting_field = State()
    entering_value = State()


# ========================
# HELPER
# ========================

async def get_center_context(state: FSMContext) -> dict:
    data = await state.get_data()
    center_id = data.get('current_center_id')
    center = await db.get_center_by_id(center_id) if center_id else None
    return {'center_id': center_id, 'center': center}


# ========================
# UNITS MAIN MENU
# ========================

@router.message(F.text == "📚 Units")
async def units_main_menu(message: Message, state: FSMContext):
    """Show units management main menu"""
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    if not center_id:
        await message.answer("❌ No center context found.")
        return

    # Get stats
    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT COUNT(*) FROM units u
            JOIN classes c ON u.class_id = c.id
            WHERE c.center_id = ? AND u.is_active = 1
        """, (center_id,))
        unit_count = (await cursor.fetchone())[0]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Create Unit", callback_data="ca_create_unit")],
        [InlineKeyboardButton(text="📋 View All Units", callback_data="ca_list_units")],
        [InlineKeyboardButton(text="✏️ Edit Unit", callback_data="ca_edit_unit")],
        [InlineKeyboardButton(text="📌 Set Current Unit", callback_data="ca_set_current_unit")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="ca_back")]
    ])

    text = "📚 **Unit & Material Management**\n\n"
    text += f"📊 Total Active Units: **{unit_count}**\n\n"
    text += "Manage lesson units, videos, audio, and PDFs."

    await message.answer(text, reply_markup=keyboard)


# ========================
# CREATE UNIT
# ========================

@router.callback_query(F.data == "ca_create_unit")
async def create_unit_start(callback: CallbackQuery, state: FSMContext):
    """Start creating a new unit"""
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    classes = await db.get_classes_for_center(center_id)

    if not classes:
        await callback.message.edit_text(
            "❌ No classes found. Create a class first.",
            reply_markup=get_back_keyboard("ca_back")
        )
        return

    buttons = []
    for cls in classes:
        buttons.append([InlineKeyboardButton(
            text=f"{cls['name']} ({cls['level']})",
            callback_data=f"unit_class_{cls['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="ca_back")])

    await callback.message.edit_text(
        "📚 **Create New Unit**\n\n"
        "Select the class for this unit:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await state.set_state(CreateUnitStates.selecting_class)


@router.callback_query(CreateUnitStates.selecting_class, F.data.startswith("unit_class_"))
async def process_unit_class(callback: CallbackQuery, state: FSMContext):
    """Process class selection"""
    class_id = int(callback.data.replace("unit_class_", ""))
    await state.update_data(unit_class_id=class_id)

    await callback.message.edit_text(
        "Enter unit title:\n"
        "Example: 'Unit 1: Introduction to Present Tense'",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreateUnitStates.entering_title)


@router.message(CreateUnitStates.entering_title, F.text)
async def process_unit_title(message: Message, state: FSMContext):
    """Process unit title"""
    title = message.text.strip()

    if len(title) < 3 or len(title) > 200:
        await message.answer("❌ Title must be between 3 and 200 characters.")
        return

    await state.update_data(unit_title=title)

    await message.answer(
        f"✅ Title: **{title}**\n\n"
        "Enter unit number (e.g., 1, 2, 3):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreateUnitStates.entering_number)


@router.message(CreateUnitStates.entering_number, F.text)
async def process_unit_number(message: Message, state: FSMContext):
    """Process unit number"""
    try:
        unit_number = int(message.text.strip())
        if unit_number < 1:
            raise ValueError
    except ValueError:
        await message.answer("❌ Please enter a positive number:")
        return

    await state.update_data(unit_number=unit_number)

    await message.answer(
        "Enter unit description (optional, type 'skip'):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreateUnitStates.entering_description)


@router.message(CreateUnitStates.entering_description, F.text)
async def process_unit_description(message: Message, state: FSMContext):
    """Process unit description"""
    desc = message.text.strip()
    if desc.lower() == 'skip':
        desc = None

    await state.update_data(unit_description=desc)

    await message.answer(
        "Enter video URL (YouTube, etc.) - optional, type 'skip':",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreateUnitStates.entering_video_url)


@router.message(CreateUnitStates.entering_video_url, F.text)
async def process_unit_video(message: Message, state: FSMContext):
    """Process video URL"""
    url = message.text.strip()
    if url.lower() == 'skip':
        url = None

    await state.update_data(unit_video_url=url)

    await message.answer(
        "Enter audio URL (optional, type 'skip'):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreateUnitStates.entering_audio_url)


@router.message(CreateUnitStates.entering_audio_url, F.text)
async def process_unit_audio(message: Message, state: FSMContext):
    """Process audio URL"""
    url = message.text.strip()
    if url.lower() == 'skip':
        url = None

    await state.update_data(unit_audio_url=url)

    await message.answer(
        "Enter PDF/document URL (optional, type 'skip'):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreateUnitStates.entering_pdf_url)


@router.message(CreateUnitStates.entering_pdf_url, F.text)
async def process_unit_pdf(message: Message, state: FSMContext):
    """Process PDF URL and confirm"""
    url = message.text.strip()
    if url.lower() == 'skip':
        url = None

    await state.update_data(unit_pdf_url=url)

    data = await state.get_data()

    text = "📚 **Confirm Unit Creation**\n\n"
    text += f"📌 **Title:** {data['unit_title']}\n"
    text += f"🔢 **Number:** {data['unit_number']}\n"
    if data.get('unit_description'):
        text += f"📄 **Description:** {data['unit_description']}\n"
    if data.get('unit_video_url'):
        text += f"🎥 **Video:** {data['unit_video_url'][:50]}...\n"
    if data.get('unit_audio_url'):
        text += f"🎧 **Audio:** {data['unit_audio_url'][:50]}...\n"
    if data.get('unit_pdf_url'):
        text += f"📎 **PDF:** {data['unit_pdf_url'][:50]}...\n"
    text += "\nCreate this unit?"

    await message.answer(text, reply_markup=get_confirm_keyboard("confirm_create_unit", "cancel"))
    await state.set_state(CreateUnitStates.confirm)


@router.callback_query(CreateUnitStates.confirm, F.data == "confirm_create_unit")
async def confirm_create_unit(callback: CallbackQuery, state: FSMContext):
    """Finalize unit creation"""
    data = await state.get_data()

    unit_id = await db.create_unit(
        class_id=data['unit_class_id'],
        title=data['unit_title'],
        unit_number=data['unit_number'],
        description=data.get('unit_description'),
        video_url=data.get('unit_video_url'),
        audio_url=data.get('unit_audio_url'),
        pdf_url=data.get('unit_pdf_url'),
        created_by=callback.from_user.id
    )

    if unit_id:
        await db.log_audit(
            user_id=callback.from_user.id,
            action='create_unit',
            entity_type='unit',
            entity_id=unit_id,
            new_values={'title': data['unit_title'], 'unit_number': data['unit_number']}
        )

        await callback.message.edit_text(
            f"✅ **Unit Created!**\n\n"
            f"📌 {data['unit_title']}\n"
            f"🔢 Unit #{data['unit_number']}\n"
            f"🆔 ID: {unit_id}",
            reply_markup=get_back_keyboard("ca_list_units")
        )
    else:
        await callback.message.edit_text(
            "❌ Failed to create unit. Unit number might already exist.",
            reply_markup=get_back_keyboard("ca_back")
        )

    await state.clear()


# ========================
# VIEW ALL UNITS
# ========================

@router.callback_query(F.data == "ca_list_units")
async def list_all_units(callback: CallbackQuery, state: FSMContext):
    """List all units organized by class"""
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    classes = await db.get_classes_for_center(center_id)

    if not classes:
        await callback.message.edit_text(
            "📋 No classes found.",
            reply_markup=get_back_keyboard("ca_back")
        )
        return

    text = "📚 **All Units**\n\n"
    buttons = []

    for cls in classes:
        units = await db.get_units_for_class(cls['id'])
        text += f"🏫 **{cls['name']}** ({cls['level']})\n"

        if units:
            for unit in units:
                current = " 📌" if unit.get('is_current') else ""
                text += f"  • Unit {unit['unit_number']}: {unit['title']}{current}\n"
        else:
            text += "  No units yet\n"

        text += "\n"
        buttons.append([InlineKeyboardButton(
            text=f"📚 View {cls['name']} Units",
            callback_data=f"ca_class_units_{cls['id']}"
        )])

    buttons.append([InlineKeyboardButton(text="➕ Create Unit", callback_data="ca_create_unit")])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="ca_back")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data.startswith("ca_class_units_"))
async def view_class_units(callback: CallbackQuery, state: FSMContext):
    """View units for a specific class"""
    class_id = int(callback.data.replace("ca_class_units_", ""))

    class_info = await db.get_class_by_id(class_id)
    units = await db.get_units_for_class(class_id)

    if not class_info:
        await callback.answer("Class not found", show_alert=True)
        return

    text = f"📚 **{class_info['name']} - Units**\n\n"

    if units:
        for unit in units:
            current = " 📌 CURRENT" if unit.get('is_current') else ""
            text += f"**Unit {unit['unit_number']}: {unit['title']}**{current}\n"
            if unit.get('description'):
                text += f"  {unit['description'][:100]}\n"
            if unit.get('video_url'):
                text += f"  🎥 Video available\n"
            if unit.get('audio_url'):
                text += f"  🎧 Audio available\n"
            if unit.get('pdf_url'):
                text += f"  📎 PDF available\n"
            text += f"  📝 Quizzes: {unit.get('quiz_count', 0)}\n"
            text += "\n"
    else:
        text += "No units created yet.\n"

    buttons = []
    for unit in units:
        buttons.append([InlineKeyboardButton(
            text=f"{'📌 ' if unit.get('is_current') else ''}Unit {unit['unit_number']}: {unit['title'][:30]}",
            callback_data=f"ca_unit_detail_{unit['id']}"
        )])

    buttons.append([InlineKeyboardButton(text="➕ Add Unit", callback_data="ca_create_unit")])
    buttons.append([InlineKeyboardButton(text="📌 Set Current Unit", callback_data=f"ca_set_current_{class_id}")])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="ca_list_units")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


# ========================
# SET CURRENT UNIT
# ========================

@router.callback_query(F.data.startswith("ca_set_current_"))
async def set_current_unit_start(callback: CallbackQuery, state: FSMContext):
    """Set the current active unit for a class"""
    class_id = int(callback.data.replace("ca_set_current_", ""))
    units = await db.get_units_for_class(class_id)

    if not units:
        await callback.answer("No units in this class", show_alert=True)
        return

    buttons = []
    for unit in units:
        current = "✅ " if unit.get('is_current') else ""
        buttons.append([InlineKeyboardButton(
            text=f"{current}Unit {unit['unit_number']}: {unit['title'][:40]}",
            callback_data=f"set_current_unit_{unit['id']}_{class_id}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data=f"ca_class_units_{class_id}")])

    await callback.message.edit_text(
        "📌 **Set Current Unit**\n\n"
        "Select which unit is currently being taught:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data.startswith("set_current_unit_"))
async def set_current_unit_execute(callback: CallbackQuery, state: FSMContext):
    """Execute setting current unit"""
    parts = callback.data.replace("set_current_unit_", "").split("_")
    unit_id = int(parts[0])
    class_id = int(parts[1])

    await db.set_current_unit(unit_id, class_id)

    unit = await db.get_unit_by_id(unit_id)

    await callback.answer(f"✅ Set: {unit['title']}")
    await view_class_units(callback, state)