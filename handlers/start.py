# handlers/start.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database.queries as db
from keyboards.all_keyboards import (
    get_language_keyboard, get_role_switch_keyboard,
    get_super_admin_main_menu, get_center_admin_main_menu,
    get_teacher_main_menu, get_student_main_menu,
    get_parent_main_menu
)

router = Router()

class RegistrationStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_language = State()

ROLE_MENUS = {
    'super_admin': get_super_admin_main_menu,
    'center_admin': get_center_admin_main_menu,
    'teacher': get_teacher_main_menu,
    'student': get_student_main_menu,
    'parent': get_parent_main_menu,
}

WELCOME_MESSAGES = {
    'super_admin': "👑 Welcome, Super Admin!\n\nYou have full platform access. Use the menu below to manage all centers, users, and settings.",
    'center_admin': "🏢 Welcome, Center Admin!\n\nManage your study center - users, classes, materials, and more.",
    'teacher': "👨‍🏫 Welcome, Teacher!\n\nAccess your classes, manage students, create quizzes, and track progress.",
    'student': "🎓 Welcome, Student!\n\nAccess your lessons, take quizzes, complete homework, and track your achievements!",
    'parent': "👪 Welcome, Parent!\n\nMonitor your child's progress, attendance, and stay connected with teachers.",
}

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command - user registration and role-based routing"""
    telegram_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name
    
    # Check if user exists
    user = await db.get_user_by_telegram_id(telegram_id)
    
    if not user:
        # New user registration
        user_id = await db.create_user(
            telegram_id=telegram_id,
            full_name=full_name,
            username=username,
            language='uz'
        )
        
        if user_id:
            # Assign default student role
            await db.assign_role(user_id, 'student')
            
            # Ask for language preference
            await message.answer(
                "🌍 Welcome! Please select your preferred language:\n\n"
                "🌍 Xush kelibsiz! Iltimos, tilni tanlang:\n\n"
                "🌍 Добро пожаловать! Пожалуйста, выберите язык:",
                reply_markup=get_language_keyboard()
            )
            await state.set_state(RegistrationStates.waiting_for_language)
            await state.update_data(user_id=user_id, is_new_user=True)
        else:
            await message.answer("❌ Registration failed. Please try again later.")
    else:
        # Existing user - show role selection or main menu
        await handle_existing_user(message, state, user)

async def handle_existing_user(message: Message, state: FSMContext, user: dict):
    """Handle existing user login"""
    user_id = user['id']
    
    # Update last active
    await db.execute("UPDATE users SET last_active = CURRENT_TIMESTAMP, last_login = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
    
    # Get all roles for this user
    roles = await db.get_user_roles(user_id)
    
    if not roles:
        await message.answer("❌ No roles assigned. Please contact support.")
        return
    
    await state.update_data(user_id=user_id, roles=roles)
    
    if len(roles) == 1:
        # Single role - show that role's menu directly
        await show_role_menu(message, state, roles[0])
    else:
        # Multiple roles - ask user to choose
        role_text = "\n".join([f"• {role.replace('_', ' ').title()}" for role in roles])
        await message.answer(
            f"👋 Welcome back, {user['full_name']}!\n\n"
            f"You have multiple roles:\n{role_text}\n\n"
            "Please select which role to use:",
            reply_markup=get_role_switch_keyboard(roles)
        )

async def show_role_menu(message: Message, state: FSMContext, role: str, center_id: int = None):
    """Show the appropriate menu for a given role"""
    await state.update_data(current_role=role, current_center_id=center_id)
    
    menu_func = ROLE_MENUS.get(role)
    welcome = WELCOME_MESSAGES.get(role, f"Welcome! Role: {role}")
    
    if menu_func:
        await message.answer(welcome, reply_markup=menu_func())
    else:
        await message.answer(welcome, reply_markup=get_student_main_menu())

@router.callback_query(F.data.startswith("switch_role_"))
async def handle_role_switch(callback: CallbackQuery, state: FSMContext):
    """Handle role switching"""
    role = callback.data.replace("switch_role_", "")
    
    # Get center context if needed
    data = await state.get_data()
    user_id = data.get('user_id')
    
    # If switching to center-specific role, get center_id
    center_id = None
    if role in ['center_admin', 'teacher', 'student', 'parent']:
        # Get first available center for this user
        roles = await db.get_user_roles(user_id)
        for r in roles:
            if r == role:
                # Find center_id from user_roles table
                cursor = await db.execute(
                    "SELECT center_id FROM user_roles WHERE user_id = ? AND role = ? LIMIT 1",
                    (user_id, role)
                )
                row = await cursor.fetchone()
                if row:
                    center_id = row['center_id'] if hasattr(row, 'center_id') else row[0]
                break
    
    await state.update_data(current_role=role, current_center_id=center_id)
    await callback.message.delete()
    await show_role_menu(callback.message, state, role, center_id)
    await callback.answer(f"Switched to {role.replace('_', ' ').title()} role")

@router.callback_query(F.data.startswith("lang_"))
async def handle_language_selection(callback: CallbackQuery, state: FSMContext):
    """Handle language selection"""
    language = callback.data.replace("lang_", "")
    data = await state.get_data()
    user_id = data.get('user_id')
    
    # Update user language
    await db.execute("UPDATE users SET language = ? WHERE id = ?", (language, user_id))
    
    # Update state
    await state.update_data(language=language)
    
    # Get roles and show appropriate menu
    roles = await db.get_user_roles(user_id)
    
    await callback.message.delete()
    
    if len(roles) == 1:
        await show_role_menu(callback.message, state, roles[0])
    else:
        role_text = "\n".join([f"• {role.replace('_', ' ').title()}" for role in roles])
        await callback.message.answer(
            f"✅ Language set!\n\n"
            f"You have multiple roles:\n{role_text}\n\n"
            "Please select which role to use:",
            reply_markup=get_role_switch_keyboard(roles)
        )

@router.message(F.text == "🔙 Switch Role")
async def handle_switch_role_button(message: Message, state: FSMContext):
    """Handle switch role button press"""
    data = await state.get_data()
    roles = data.get('roles', [])
    
    if len(roles) > 1:
        await message.answer(
            "Select role to switch to:",
            reply_markup=get_role_switch_keyboard(roles)
        )
    else:
        await message.answer("You only have one role assigned.")
