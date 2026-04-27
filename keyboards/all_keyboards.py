# keyboards/all_keyboards.py
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove
)
from typing import List, Dict

# ========================
# COMMON KEYBOARDS
# ========================

def get_language_keyboard() -> InlineKeyboardMarkup:
    """Language selection keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇺🇿 O'zbek tili", callback_data="lang_uz")],
        [InlineKeyboardButton(text="🇷🇺 Русский язык", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")]
    ])

def get_role_switch_keyboard(roles: List[str]) -> InlineKeyboardMarkup:
    """Role switching keyboard for users with multiple roles"""
    role_icons = {
        'super_admin': '👑 Super Admin',
        'center_admin': '🏢 Center Admin',
        'teacher': '👨‍🏫 Teacher',
        'student': '🎓 Student',
        'parent': '👪 Parent'
    }
    buttons = []
    for role in roles:
        icon = role_icons.get(role, role)
        buttons.append([InlineKeyboardButton(text=icon, callback_data=f"switch_role_{role}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Cancel operation keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")]
    ])

def get_confirm_keyboard(yes_callback: str = "confirm_yes", no_callback: str = "confirm_no") -> InlineKeyboardMarkup:
    """Confirmation keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Yes", callback_data=yes_callback),
            InlineKeyboardButton(text="❌ No", callback_data=no_callback)
        ]
    ])

def get_back_keyboard(callback_data: str = "back") -> InlineKeyboardMarkup:
    """Back button keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back", callback_data=callback_data)]
    ])

def get_pagination_keyboard(current_page: int, total_pages: int, prefix: str) -> InlineKeyboardMarkup:
    """Pagination keyboard"""
    buttons = []
    if current_page > 0:
        buttons.append(InlineKeyboardButton(text="⬅️ Previous", callback_data=f"{prefix}_page_{current_page-1}"))
    buttons.append(InlineKeyboardButton(text=f"{current_page+1}/{total_pages}", callback_data="noop"))
    if current_page < total_pages - 1:
        buttons.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"{prefix}_page_{current_page+1}"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons])

# ========================
# SUPER ADMIN KEYBOARDS
# ========================

def get_super_admin_main_menu() -> ReplyKeyboardMarkup:
    """Super admin main menu"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏢 Centers"), KeyboardButton(text="👥 Users")],
            [KeyboardButton(text="💰 Subscriptions"), KeyboardButton(text="📊 Analytics")],
            [KeyboardButton(text="🤝 Support"), KeyboardButton(text="⚙️ System")],
            [KeyboardButton(text="🔐 Security"), KeyboardButton(text="💾 Backup")],
            [KeyboardButton(text="🔙 Switch Role")]
        ],
        resize_keyboard=True
    )

def get_super_admin_centers_menu() -> InlineKeyboardMarkup:
    """Super admin centers management menu"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Create Center", callback_data="sa_create_center")],
        [InlineKeyboardButton(text="📋 View All Centers", callback_data="sa_list_centers")],
        [InlineKeyboardButton(text="🔍 Search Centers", callback_data="sa_search_centers")],
        [InlineKeyboardButton(text="⏸️ Suspend Center", callback_data="sa_suspend_center")],
        [InlineKeyboardButton(text="▶️ Activate Center", callback_data="sa_activate_center")],
        [InlineKeyboardButton(text="🗑️ Delete Center", callback_data="sa_delete_center")],
        [InlineKeyboardButton(text="📊 Center Analytics", callback_data="sa_center_analytics")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")]
    ])

def get_super_admin_subscriptions_menu() -> InlineKeyboardMarkup:
    """Super admin subscriptions management menu"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 View All Plans", callback_data="sa_list_plans")],
        [InlineKeyboardButton(text="➕ Create Plan", callback_data="sa_create_plan")],
        [InlineKeyboardButton(text="✏️ Edit Plan", callback_data="sa_edit_plan")],
        [InlineKeyboardButton(text="🗑️ Delete Plan", callback_data="sa_delete_plan")],
        [InlineKeyboardButton(text="📋 View Subscriptions", callback_data="sa_list_subscriptions")],
        [InlineKeyboardButton(text="⚠️ Expiring Soon", callback_data="sa_expiring_soon")],
        [InlineKeyboardButton(text="💰 Revenue Report", callback_data="sa_revenue_report")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")]
    ])

# ========================
# CENTER ADMIN KEYBOARDS
# ========================

def get_center_admin_main_menu() -> ReplyKeyboardMarkup:
    """Center admin main menu"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Users"), KeyboardButton(text="🏫 Classes")],
            [KeyboardButton(text="📚 Units"), KeyboardButton(text="📝 Quizzes")],
            [KeyboardButton(text="📋 Homework"), KeyboardButton(text="📅 Attendance")],
            [KeyboardButton(text="💰 Payments"), KeyboardButton(text="🏆 Competitions")],
            [KeyboardButton(text="💬 Communication"), KeyboardButton(text="📊 Reports")],
            [KeyboardButton(text="⚙️ Settings"), KeyboardButton(text="🤝 Support")],
            [KeyboardButton(text="🔙 Switch Role")]
        ],
        resize_keyboard=True
    )

def get_center_admin_users_menu() -> InlineKeyboardMarkup:
    """Center admin user management menu"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍🏫 Add Teacher", callback_data="ca_add_teacher")],
        [InlineKeyboardButton(text="🎓 Add Student", callback_data="ca_add_student")],
        [InlineKeyboardButton(text="👪 Add Parent", callback_data="ca_add_parent")],
        [InlineKeyboardButton(text="📋 View All Users", callback_data="ca_list_users")],
        [InlineKeyboardButton(text="🔍 Search Users", callback_data="ca_search_users")],
        [InlineKeyboardButton(text="✏️ Edit User", callback_data="ca_edit_user")],
        [InlineKeyboardButton(text="🗑️ Remove User", callback_data="ca_remove_user")],
        [InlineKeyboardButton(text="👪 Link Parent-Child", callback_data="ca_link_parent")],
        [InlineKeyboardButton(text="📥 Import Users", callback_data="ca_import_users")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="ca_back")]
    ])

def get_center_admin_classes_menu() -> InlineKeyboardMarkup:
    """Center admin class management menu"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Create Class", callback_data="ca_create_class")],
        [InlineKeyboardButton(text="✏️ Edit Class", callback_data="ca_edit_class")],
        [InlineKeyboardButton(text="🗑️ Delete Class", callback_data="ca_delete_class")],
        [InlineKeyboardButton(text="📋 View All Classes", callback_data="ca_list_classes")],
        [InlineKeyboardButton(text="👨‍🏫 Assign Teacher", callback_data="ca_assign_teacher")],
        [InlineKeyboardButton(text="📅 Set Schedule", callback_data="ca_set_schedule")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="ca_back")]
    ])

# ========================
# TEACHER KEYBOARDS
# ========================

def get_teacher_main_menu() -> ReplyKeyboardMarkup:
    """Teacher main menu"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏫 My Classes"), KeyboardButton(text="👥 Students")],
            [KeyboardButton(text="📚 Units"), KeyboardButton(text="📝 Quizzes")],
            [KeyboardButton(text="📋 Homework"), KeyboardButton(text="📅 Attendance")],
            [KeyboardButton(text="💰 Record Payment"), KeyboardButton(text="🏆 Competitions")],
            [KeyboardButton(text="💬 Communication"), KeyboardButton(text="📊 Reports")],
            [KeyboardButton(text="🗣 Topic Bank"), KeyboardButton(text="👤 Profile")],
            [KeyboardButton(text="🔙 Switch Role")]
        ],
        resize_keyboard=True
    )

def get_teacher_classes_menu() -> InlineKeyboardMarkup:
    """Teacher class management menu"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 View My Classes", callback_data="t_my_classes")],
        [InlineKeyboardButton(text="📊 Class Details", callback_data="t_class_details")],
        [InlineKeyboardButton(text="👥 Class Roster", callback_data="t_class_roster")],
        [InlineKeyboardButton(text="📅 View Schedule", callback_data="t_view_schedule")],
        [InlineKeyboardButton(text="📌 Set Current Lesson", callback_data="t_set_current_lesson")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="t_back")]
    ])

def get_teacher_quiz_menu() -> InlineKeyboardMarkup:
    """Teacher quiz management menu"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Create Quiz", callback_data="t_create_quiz")],
        [InlineKeyboardButton(text="✏️ Edit Quiz", callback_data="t_edit_quiz")],
        [InlineKeyboardButton(text="🗑️ Delete Quiz", callback_data="t_delete_quiz")],
        [InlineKeyboardButton(text="➕ Add Question", callback_data="t_add_question")],
        [InlineKeyboardButton(text="✏️ Edit Question", callback_data="t_edit_question")],
        [InlineKeyboardButton(text="📊 View Results", callback_data="t_quiz_results")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="t_back")]
    ])

def get_question_type_keyboard() -> InlineKeyboardMarkup:
    """Question type selection keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Multiple Choice", callback_data="qtype_mcq")],
        [InlineKeyboardButton(text="✍️ Short Answer", callback_data="qtype_short_answer")],
        [InlineKeyboardButton(text="🔤 Fill Gap", callback_data="qtype_fill_gap")],
        [InlineKeyboardButton(text="🎧 Listening", callback_data="qtype_listening")],
        [InlineKeyboardButton(text="🔨 Sentence Building", callback_data="qtype_sentence_building")],
        [InlineKeyboardButton(text="🔍 Error Detection", callback_data="qtype_error_detection")],
        [InlineKeyboardButton(text="🔗 Matching Pairs", callback_data="qtype_matching_pairs")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="t_back")]
    ])

def get_attendance_keyboard() -> InlineKeyboardMarkup:
    """Attendance marking keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Present", callback_data="att_present"),
            InlineKeyboardButton(text="⏰ Late", callback_data="att_late")
        ],
        [
            InlineKeyboardButton(text="❌ Absent", callback_data="att_absent"),
            InlineKeyboardButton(text="📝 Excused", callback_data="att_excused")
        ],
        [InlineKeyboardButton(text="💾 Save & Exit", callback_data="att_save_exit")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="t_back")]
    ])

# ========================
# STUDENT KEYBOARDS
# ========================

def get_student_main_menu() -> ReplyKeyboardMarkup:
    """Student main menu"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 My Lessons"), KeyboardButton(text="📝 Quizzes")],
            [KeyboardButton(text="📋 Homework"), KeyboardButton(text="📅 Attendance")],
            [KeyboardButton(text="🏆 Leaderboard"), KeyboardButton(text="🎖 Achievements")],
            [KeyboardButton(text="💬 Messages"), KeyboardButton(text="👤 Profile")],
            [KeyboardButton(text="🗣 Speaking Partner"), KeyboardButton(text="❓ Help")],
            [KeyboardButton(text="🔙 Switch Role")]
        ],
        resize_keyboard=True
    )

def get_student_lessons_menu() -> InlineKeyboardMarkup:
    """Student lessons menu"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Current Lesson", callback_data="s_current_lesson")],
        [InlineKeyboardButton(text="📚 All Units", callback_data="s_all_units")],
        [InlineKeyboardButton(text="📊 My Progress", callback_data="s_my_progress")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="s_back")]
    ])

def get_quiz_start_keyboard(quiz_id: int) -> InlineKeyboardMarkup:
    """Start quiz keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Start Quiz", callback_data=f"start_quiz_{quiz_id}")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="s_back")]
    ])

def get_mcq_answer_keyboard(options: List[Dict], question_index: int, total_questions: int) -> InlineKeyboardMarkup:
    """MCQ answer keyboard"""
    buttons = []
    for opt in options:
        buttons.append([InlineKeyboardButton(
            text=opt['option_text'][:50],
            callback_data=f"mcq_answer_{opt['id']}_{question_index}"
        )])
    buttons.append([InlineKeyboardButton(
        text=f"Question {question_index+1}/{total_questions} | Skip >>",
        callback_data=f"skip_question_{question_index}"
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ========================
# PARENT KEYBOARDS
# ========================

def get_parent_main_menu() -> ReplyKeyboardMarkup:
    """Parent main menu"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👶 My Children"), KeyboardButton(text="📊 Progress")],
            [KeyboardButton(text="📅 Attendance"), KeyboardButton(text="💰 Payments")],
            [KeyboardButton(text="📋 Reports"), KeyboardButton(text="💬 Messages")],
            [KeyboardButton(text="⚙️ Settings"), KeyboardButton(text="🔔 Notifications")],
            [KeyboardButton(text="🔙 Switch Role")]
        ],
        resize_keyboard=True
    )

def get_parent_children_keyboard(children: List[Dict]) -> InlineKeyboardMarkup:
    """Parent children selection keyboard"""
    buttons = []
    for child in children:
        buttons.append([InlineKeyboardButton(
            text=f"👶 {child['full_name']} ({child.get('level', 'N/A')})",
            callback_data=f"parent_child_{child['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="p_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_parent_child_menu(child_id: int) -> InlineKeyboardMarkup:
    """Parent child detail menu"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 View Progress", callback_data=f"p_child_progress_{child_id}")],
        [InlineKeyboardButton(text="📝 Quiz Results", callback_data=f"p_child_quizzes_{child_id}")],
        [InlineKeyboardButton(text="📋 Homework Status", callback_data=f"p_child_homework_{child_id}")],
        [InlineKeyboardButton(text="📅 Attendance", callback_data=f"p_child_attendance_{child_id}")],
        [InlineKeyboardButton(text="💰 Payment History", callback_data=f"p_child_payments_{child_id}")],
        [InlineKeyboardButton(text="💬 Contact Teacher", callback_data=f"p_contact_teacher_{child_id}")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="p_back")]
    ])