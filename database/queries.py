# database/queries.py (PART 1 - Core User & Center Operations)
import aiosqlite
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
from config import DB_PATH

@asynccontextmanager
async def get_db():
    """Async context manager for database connections"""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()

# ========== CENTER MANAGEMENT ==========

async def create_center(name: str, slug: str, admin_id: int, subscription_plan: str = 'basic') -> Optional[int]:
    """Create a new study center"""
    async with get_db() as db:
        cursor = await db.execute("""
            INSERT INTO centers (name, slug, subscription_plan, trial_ends_at)
            VALUES (?, ?, ?, datetime('now', '+14 days'))
        """, (name, slug, subscription_plan))
        center_id = cursor.lastrowid
        
        # Create default settings
        await db.execute("""
            INSERT INTO center_settings (center_id, bot_name, welcome_message)
            VALUES (?, ?, ?)
        """, (center_id, name, f"Welcome to {name}!"))
        
        # Assign admin role to creator
        await db.execute("""
            INSERT INTO user_roles (user_id, role, center_id)
            VALUES (?, 'center_admin', ?)
        """, (admin_id, center_id))
        
        await db.commit()
        return center_id

async def get_center_by_id(center_id: int) -> Optional[Dict]:
    """Get center details by ID"""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM centers WHERE id = ?", (center_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def get_all_centers(include_suspended: bool = False) -> List[Dict]:
    """Get all centers"""
    async with get_db() as db:
        query = "SELECT * FROM centers"
        if not include_suspended:
            query += " WHERE is_suspended = 0"
        query += " ORDER BY created_at DESC"
        cursor = await db.execute(query)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def suspend_center(center_id: int, reason: str) -> bool:
    """Suspend a center"""
    async with get_db() as db:
        await db.execute("""
            UPDATE centers SET is_suspended = 1, suspended_at = CURRENT_TIMESTAMP, suspended_reason = ?
            WHERE id = ?
        """, (reason, center_id))
        await db.commit()
        return True

async def activate_center(center_id: int) -> bool:
    """Reactivate a suspended center"""
    async with get_db() as db:
        await db.execute("""
            UPDATE centers SET is_suspended = 0, suspended_at = NULL, suspended_reason = NULL
            WHERE id = ?
        """, (center_id,))
        await db.commit()
        return True

async def delete_center(center_id: int) -> bool:
    """Delete a center and all associated data"""
    async with get_db() as db:
        await db.execute("DELETE FROM centers WHERE id = ?", (center_id,))
        await db.commit()
        return True

# ========== USER MANAGEMENT (Multi-Role) ==========

async def create_user(telegram_id: Optional[int], full_name: str, phone: Optional[str] = None,
                      email: Optional[str] = None, username: Optional[str] = None, 
                      language: str = 'uz') -> Optional[int]:
    """Create a new user with optional Telegram ID"""
    async with get_db() as db:
        try:
            cursor = await db.execute("""
                INSERT INTO users (telegram_id, full_name, phone, email, username, language)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (telegram_id, full_name, phone, email, username, language))
            await db.commit()
            return cursor.lastrowid
        except aiosqlite.IntegrityError:
            return None

async def get_user_by_telegram_id(telegram_id: int) -> Optional[Dict]:
    """Get user by Telegram ID"""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Get user by internal ID"""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def get_user_roles(user_id: int, center_id: Optional[int] = None) -> List[str]:
    """Get all roles for a user, optionally filtered by center"""
    async with get_db() as db:
        if center_id:
            cursor = await db.execute(
                "SELECT role FROM user_roles WHERE user_id = ? AND (center_id = ? OR center_id IS NULL)",
                (user_id, center_id)
            )
        else:
            cursor = await db.execute(
                "SELECT DISTINCT role FROM user_roles WHERE user_id = ?",
                (user_id,)
            )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

async def assign_role(user_id: int, role: str, center_id: Optional[int] = None, granted_by: Optional[int] = None) -> bool:
    """Assign a role to a user"""
    async with get_db() as db:
        try:
            await db.execute("""
                INSERT OR IGNORE INTO user_roles (user_id, role, center_id, granted_by)
                VALUES (?, ?, ?, ?)
            """, (user_id, role, center_id, granted_by))
            await db.commit()
            return True
        except:
            return False

async def remove_role(user_id: int, role: str, center_id: Optional[int] = None) -> bool:
    """Remove a role from a user"""
    async with get_db() as db:
        if center_id:
            await db.execute(
                "DELETE FROM user_roles WHERE user_id = ? AND role = ? AND center_id = ?",
                (user_id, role, center_id)
            )
        else:
            await db.execute(
                "DELETE FROM user_roles WHERE user_id = ? AND role = ? AND center_id IS NULL",
                (user_id, role)
            )
        await db.commit()
        return True

async def link_parent_to_child(parent_id: int, student_id: int, relationship: str = 'parent') -> bool:
    """Link a parent to a student"""
    async with get_db() as db:
        try:
            await db.execute("""
                INSERT OR IGNORE INTO parent_child (parent_id, student_id, relationship)
                VALUES (?, ?, ?)
            """, (parent_id, student_id, relationship))
            await db.commit()
            return True
        except:
            return False

async def get_parents_for_student(student_id: int) -> List[Dict]:
    """Get all parents linked to a student"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT u.*, pc.relationship, pc.is_primary
            FROM parent_child pc
            JOIN users u ON pc.parent_id = u.id
            WHERE pc.student_id = ?
        """, (student_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_children_for_parent(parent_id: int) -> List[Dict]:
    """Get all children linked to a parent"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT u.*, pc.relationship
            FROM parent_child pc
            JOIN users u ON pc.student_id = u.id
            WHERE pc.parent_id = ?
        """, (parent_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

# ========== CLASS MANAGEMENT ==========

async def create_class(center_id: int, name: str, level: str, price: int = 0, 
                       description: str = None, max_students: int = 30, created_by: int = None) -> Optional[int]:
    """Create a new class"""
    async with get_db() as db:
        cursor = await db.execute("""
            INSERT INTO classes (center_id, name, level, price, description, max_students, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (center_id, name, level, price, description, max_students, created_by))
        await db.commit()
        return cursor.lastrowid

async def enroll_student(student_id: int, class_id: int, enrolled_by: int = None) -> bool:
    """Enroll a student in a class"""
    async with get_db() as db:
        try:
            await db.execute("""
                INSERT INTO class_enrollments (student_id, class_id, enrolled_by)
                VALUES (?, ?, ?)
            """, (student_id, class_id, enrolled_by))
            await db.commit()
            return True
        except:
            return False

async def assign_teacher_to_class(teacher_id: int, class_id: int, is_primary: bool = False, assigned_by: int = None) -> bool:
    """Assign a teacher to a class"""
    async with get_db() as db:
        try:
            await db.execute("""
                INSERT OR IGNORE INTO class_teachers (teacher_id, class_id, is_primary, assigned_by)
                VALUES (?, ?, ?, ?)
            """, (teacher_id, class_id, is_primary, assigned_by))
            await db.commit()
            return True
        except:
            return False

async def get_classes_for_center(center_id: int, include_archived: bool = False) -> List[Dict]:
    """Get all classes for a center"""
    async with get_db() as db:
        query = """
            SELECT c.*, 
                   COUNT(DISTINCT ce.student_id) as student_count,
                   GROUP_CONCAT(DISTINCT u.full_name) as teacher_names
            FROM classes c
            LEFT JOIN class_enrollments ce ON c.id = ce.class_id AND ce.is_active = 1
            LEFT JOIN class_teachers ct ON c.id = ct.class_id
            LEFT JOIN users u ON ct.teacher_id = u.id
            WHERE c.center_id = ?
        """
        if not include_archived:
            query += " AND c.is_archived = 0"
        query += " GROUP BY c.id ORDER BY c.name"
        
        cursor = await db.execute(query, (center_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_classes_for_teacher(teacher_id: int) -> List[Dict]:
    """Get all classes assigned to a teacher"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT c.*, ct.is_primary,
                   COUNT(DISTINCT ce.student_id) as student_count
            FROM classes c
            JOIN class_teachers ct ON c.id = ct.class_id
            LEFT JOIN class_enrollments ce ON c.id = ce.class_id AND ce.is_active = 1
            WHERE ct.teacher_id = ? AND c.is_archived = 0
            GROUP BY c.id
            ORDER BY c.name
        """, (teacher_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_classes_for_student(student_id: int) -> List[Dict]:
    """Get all classes for a student"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT c.*, ce.enrolled_at
            FROM classes c
            JOIN class_enrollments ce ON c.id = ce.class_id
            WHERE ce.student_id = ? AND ce.is_active = 1 AND c.is_archived = 0
            ORDER BY c.name
        """, (student_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

# ========== ATTENDANCE SYSTEM ==========

async def create_attendance_session(class_id: int, session_date: str, taken_by: int) -> int:
    """Create a new attendance session"""
    async with get_db() as db:
        cursor = await db.execute("""
            INSERT OR IGNORE INTO attendance_sessions (class_id, session_date, taken_by)
            VALUES (?, ?, ?)
        """, (class_id, session_date, taken_by))
        await db.commit()
        return cursor.lastrowid

async def mark_attendance(session_id: int, student_id: int, status: str, notes: str = None) -> bool:
    """Mark a student's attendance"""
    async with get_db() as db:
        await db.execute("""
            INSERT OR REPLACE INTO attendance_records (session_id, student_id, status, notes)
            VALUES (?, ?, ?, ?)
        """, (session_id, student_id, status, notes))
        await db.commit()
        return True

async def get_student_attendance_stats(student_id: int, class_id: int = None) -> Dict:
    """Get attendance statistics for a student"""
    async with get_db() as db:
        query = """
            SELECT 
                COUNT(*) as total_sessions,
                SUM(CASE WHEN ar.status = 'present' THEN 1 ELSE 0 END) as present_count,
                SUM(CASE WHEN ar.status = 'late' THEN 1 ELSE 0 END) as late_count,
                SUM(CASE WHEN ar.status = 'absent' THEN 1 ELSE 0 END) as absent_count,
                SUM(CASE WHEN ar.status = 'excused' THEN 1 ELSE 0 END) as excused_count
            FROM attendance_records ar
            JOIN attendance_sessions a ON ar.session_id = a.id
            WHERE ar.student_id = ?
        """
        params = [student_id]
        if class_id:
            query += " AND a.class_id = ?"
            params.append(class_id)
        
        cursor = await db.execute(query, params)
        row = await cursor.fetchone()
        return dict(row) if row else {"total_sessions": 0, "present_count": 0, "late_count": 0, "absent_count": 0, "excused_count": 0}

# ========== POINTS & STREAKS ==========

async def award_points(student_id: int, points: int, reason: str = None) -> int:
    """Award points to a student and update leaderboard"""
    async with get_db() as db:
        await db.execute("""
            UPDATE users SET total_points = total_points + ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (points, student_id))
        
        # Update streak
        today = datetime.now().strftime('%Y-%m-%d')
        await db.execute("""
            UPDATE users SET 
                last_activity_date = ?,
                current_streak = CASE 
                    WHEN last_activity_date = date(?, '-1 day') THEN current_streak + 1
                    WHEN last_activity_date = ? THEN current_streak
                    ELSE 1
                END,
                longest_streak = MAX(longest_streak, current_streak)
            WHERE id = ?
        """, (today, today, today, student_id))
        
        # Log the points transaction
        await db.execute("""
            INSERT INTO audit_logs (user_id, action, entity_type, entity_id, new_values)
            VALUES (?, 'points_awarded', 'user', ?, ?)
        """, (student_id, student_id, json.dumps({"points": points, "reason": reason})))
        
        await db.commit()
        
        # Get updated total
        cursor = await db.execute("SELECT total_points FROM users WHERE id = ?", (student_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0

async def get_student_points_and_streak(student_id: int) -> Dict:
    """Get student's points and streak information"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT total_points, current_streak, longest_streak, last_activity_date
            FROM users WHERE id = ?
        """, (student_id,))
        row = await cursor.fetchone()
        return dict(row) if row else {"total_points": 0, "current_streak": 0, "longest_streak": 0}

# ========== PAYMENT SYSTEM ==========

async def record_payment(student_id: int, amount: float, payment_method: str, recorded_by: int, 
                         center_id: int, notes: str = None, payment_for_month: str = None) -> int:
    """Record a payment for a student"""
    async with get_db() as db:
        cursor = await db.execute("""
            INSERT INTO payments (student_id, amount, payment_method, recorded_by, center_id, notes, payment_for_month)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (student_id, amount, payment_method, recorded_by, center_id, notes, payment_for_month))
        await db.commit()
        return cursor.lastrowid

async def get_student_balance(student_id: int) -> float:
    """Calculate student's current balance"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT COALESCE(SUM(amount), 0) as total_paid
            FROM payments WHERE student_id = ?
        """, (student_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0

async def get_student_payment_history(student_id: int, limit: int = 20) -> List[Dict]:
    """Get payment history for a student"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT p.*, u.full_name as recorded_by_name
            FROM payments p
            JOIN users u ON p.recorded_by = u.id
            WHERE p.student_id = ?
            ORDER BY p.payment_date DESC
            LIMIT ?
        """, (student_id, limit))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

# ========== COMMUNICATION SYSTEM ==========

async def create_announcement(center_id: int, title: str, content: str, target_role: str = 'all',
                              target_class_id: int = None, created_by: int = None) -> int:
    """Create an announcement"""
    async with get_db() as db:
        cursor = await db.execute("""
            INSERT INTO announcements (center_id, title, content, target_role, target_class_id, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (center_id, title, content, target_role, target_class_id, created_by))
        await db.commit()
        return cursor.lastrowid

async def send_message(sender_id: int, receiver_id: int, content: str, parent_message_id: int = None) -> int:
    """Send a message between users"""
    async with get_db() as db:
        cursor = await db.execute("""
            INSERT INTO messages (sender_id, receiver_id, content, parent_message_id)
            VALUES (?, ?, ?, ?)
        """, (sender_id, receiver_id, content, parent_message_id))
        await db.commit()
        return cursor.lastrowid

async def get_messages_between_users(user1_id: int, user2_id: int, limit: int = 50) -> List[Dict]:
    """Get conversation between two users"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT m.*, s.full_name as sender_name, r.full_name as receiver_name
            FROM messages m
            JOIN users s ON m.sender_id = s.id
            JOIN users u r ON m.receiver_id = r.id
            WHERE (m.sender_id = ? AND m.receiver_id = ?) OR (m.sender_id = ? AND m.receiver_id = ?)
            ORDER BY m.created_at DESC
            LIMIT ?
        """, (user1_id, user2_id, user2_id, user1_id, limit))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

# ========== AUDIT LOGGING ==========

async def log_audit(user_id: int, action: str, entity_type: str, entity_id: int = None,
                    old_values: dict = None, new_values: dict = None, center_id: int = None,
                    ip_address: str = None, user_agent: str = None):
    """Log an audit entry"""
    async with get_db() as db:
        await db.execute("""
            INSERT INTO audit_logs (user_id, center_id, action, entity_type, entity_id, old_values, new_values, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, center_id, action, entity_type, entity_id, 
              json.dumps(old_values) if old_values else None,
              json.dumps(new_values) if new_values else None,
              ip_address, user_agent))
        await db.commit()
# database/queries.py (PART 2 - Academic Operations)

# ========== UNIT & MATERIAL MANAGEMENT ==========

async def create_unit(class_id: int, title: str, unit_number: int, description: str = None,
                      video_url: str = None, audio_url: str = None, pdf_url: str = None,
                      created_by: int = None) -> Optional[int]:
    """Create a new unit for a class"""
    async with get_db() as db:
        try:
            cursor = await db.execute("""
                INSERT INTO units (class_id, title, unit_number, description, video_url, audio_url, pdf_url, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (class_id, title, unit_number, description, video_url, audio_url, pdf_url, created_by))
            await db.commit()
            
            # Log audit
            if created_by:
                await log_audit(created_by, 'create_unit', 'unit', cursor.lastrowid,
                              new_values={'title': title, 'unit_number': unit_number})
            
            return cursor.lastrowid
        except aiosqlite.IntegrityError:
            return None

async def get_units_for_class(class_id: int) -> List[Dict]:
    """Get all units for a class ordered by unit_number"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT u.*, 
                   COUNT(DISTINCT q.id) as quiz_count
            FROM units u
            LEFT JOIN quizzes q ON u.id = q.unit_id
            WHERE u.class_id = ? AND u.is_active = 1
            GROUP BY u.id
            ORDER BY u.unit_number
        """, (class_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def set_current_unit(unit_id: int, class_id: int) -> bool:
    """Set a unit as the current active unit for a class"""
    async with get_db() as db:
        # Reset all units in class
        await db.execute("UPDATE units SET is_current = 0 WHERE class_id = ?", (class_id,))
        # Set the specified unit as current
        await db.execute("UPDATE units SET is_current = 1 WHERE id = ? AND class_id = ?", (unit_id, class_id))
        await db.commit()
        return True

async def get_current_unit_for_class(class_id: int) -> Optional[Dict]:
    """Get the current active unit for a class"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT * FROM units WHERE class_id = ? AND is_current = 1 AND is_active = 1
        """, (class_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def get_units_for_student(student_id: int) -> List[Dict]:
    """Get all units for a student's classes with completion status"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT u.*, c.name as class_name, c.level,
                   COALESCE(up.completion_percent, 0) as completion_percent,
                   COALESCE(up.is_completed, 0) as is_completed
            FROM units u
            JOIN classes c ON u.class_id = c.id
            JOIN class_enrollments ce ON c.id = ce.class_id
            LEFT JOIN unit_progress up ON u.id = up.unit_id AND up.student_id = ce.student_id
            WHERE ce.student_id = ? AND ce.is_active = 1 AND c.is_archived = 0 AND u.is_active = 1
            ORDER BY c.name, u.unit_number
        """, (student_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

# ========== QUIZ SYSTEM ==========

async def create_quiz(unit_id: int, title: str, quiz_type: str, description: str = None,
                      passing_score: int = 60, time_limit_minutes: int = None,
                      max_attempts: int = 1, created_by: int = None) -> Optional[int]:
    """Create a new quiz"""
    async with get_db() as db:
        cursor = await db.execute("""
            INSERT INTO quizzes (unit_id, title, quiz_type, description, passing_score, time_limit_minutes, max_attempts, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (unit_id, title, quiz_type, description, passing_score, time_limit_minutes, max_attempts, created_by))
        await db.commit()
        return cursor.lastrowid

async def add_quiz_question(quiz_id: int, question_type: str, question_text: str, points: int = 1,
                            order_number: int = 1, explanation: str = None, media_url: str = None) -> Optional[int]:
    """Add a question to a quiz"""
    async with get_db() as db:
        cursor = await db.execute("""
            INSERT INTO quiz_questions (quiz_id, question_type, question_text, points, order_number, explanation, media_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (quiz_id, question_type, question_text, points, order_number, explanation, media_url))
        await db.commit()
        return cursor.lastrowid

async def add_question_option(question_id: int, option_text: str, is_correct: bool = False, order_number: int = 1) -> int:
    """Add an option to a multiple choice question"""
    async with get_db() as db:
        cursor = await db.execute("""
            INSERT INTO question_options (question_id, option_text, is_correct, order_number)
            VALUES (?, ?, ?, ?)
        """, (question_id, option_text, is_correct, order_number))
        await db.commit()
        return cursor.lastrowid

async def get_quiz_with_questions(quiz_id: int) -> Optional[Dict]:
    """Get a quiz with all its questions and options"""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,))
        quiz_row = await cursor.fetchone()
        if not quiz_row:
            return None
        quiz = dict(quiz_row)
        
        # Get questions
        cursor = await db.execute("""
            SELECT * FROM quiz_questions WHERE quiz_id = ? ORDER BY order_number
        """, (quiz_id,))
        questions = []
        async for q_row in cursor:
            question = dict(q_row)
            
            # Get options if MCQ
            if question['question_type'] == 'mcq':
                opt_cursor = await db.execute("""
                    SELECT * FROM question_options WHERE question_id = ? ORDER BY order_number
                """, (question['id'],))
                question['options'] = [dict(opt) for opt in await opt_cursor.fetchall()]
            
            # Get fill gap answer if applicable
            elif question['question_type'] == 'fill_gap':
                fg_cursor = await db.execute("""
                    SELECT * FROM fill_gap_answers WHERE question_id = ?
                """, (question['id'],))
                fg_row = await fg_cursor.fetchone()
                if fg_row:
                    question['fill_answer'] = dict(fg_row)
            
            # Get matching pairs if applicable
            elif question['question_type'] == 'matching_pairs':
                mp_cursor = await db.execute("""
                    SELECT * FROM matching_pairs WHERE question_id = ? ORDER BY order_number
                """, (question['id'],))
                question['matching_pairs'] = [dict(mp) for mp in await mp_cursor.fetchall()]
            
            questions.append(question)
        
        quiz['questions'] = questions
        return quiz

async def get_quizzes_for_class(class_id: int) -> List[Dict]:
    """Get all quizzes for a class"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT q.*, u.title as unit_title, u.unit_number
            FROM quizzes q
            JOIN units u ON q.unit_id = u.id
            WHERE u.class_id = ? AND q.is_active = 1
            ORDER BY u.unit_number, q.title
        """, (class_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def start_quiz_attempt(quiz_id: int, student_id: int) -> Optional[int]:
    """Start a new quiz attempt for a student"""
    async with get_db() as db:
        # Check max attempts
        quiz = await get_quiz_by_id(quiz_id)
        if not quiz:
            return None
        
        cursor = await db.execute("""
            SELECT COUNT(*) as attempt_count FROM quiz_attempts 
            WHERE quiz_id = ? AND student_id = ?
        """, (quiz_id, student_id))
        row = await cursor.fetchone()
        attempt_count = row['attempt_count'] if row else 0
        
        if attempt_count >= quiz['max_attempts']:
            return -1  # Max attempts reached
        
        attempt_number = attempt_count + 1
        cursor = await db.execute("""
            INSERT INTO quiz_attempts (quiz_id, student_id, attempt_number)
            VALUES (?, ?, ?)
        """, (quiz_id, student_id, attempt_number))
        await db.commit()
        return cursor.lastrowid

async def get_quiz_by_id(quiz_id: int) -> Optional[Dict]:
    """Get quiz by ID"""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def submit_quiz_answer(attempt_id: int, question_id: int, answer_text: str = None,
                            selected_option_id: int = None) -> tuple:
    """Submit an answer for a quiz question and return if correct and points earned"""
    async with get_db() as db:
        # Get question details
        cursor = await db.execute("SELECT * FROM quiz_questions WHERE id = ?", (question_id,))
        question = await cursor.fetchone()
        if not question:
            return (False, 0)
        question = dict(question)
        
        is_correct = False
        points = 0
        
        if question['question_type'] == 'mcq' and selected_option_id:
            cursor = await db.execute("""
                SELECT is_correct FROM question_options WHERE id = ?
            """, (selected_option_id,))
            opt = await cursor.fetchone()
            if opt and opt['is_correct']:
                is_correct = True
                points = question['points']
                # Award points to student
                cursor = await db.execute("""
                    SELECT student_id FROM quiz_attempts WHERE id = ?
                """, (attempt_id,))
                attempt = await cursor.fetchone()
                if attempt:
                    await award_points(attempt['student_id'], points, f"Correct answer on quiz question {question_id}")
        
        elif question['question_type'] == 'fill_gap' and answer_text:
            cursor = await db.execute("""
                SELECT correct_answer, acceptable_answers, case_sensitive 
                FROM fill_gap_answers WHERE question_id = ?
            """, (question_id,))
            fg = await cursor.fetchone()
            if fg:
                correct = fg['correct_answer']
                acceptable = json.loads(fg['acceptable_answers']) if fg['acceptable_answers'] else []
                user_answer = answer_text.strip()
                
                if fg['case_sensitive']:
                    if user_answer == correct or user_answer in acceptable:
                        is_correct = True
                        points = question['points']
                else:
                    if user_answer.lower() == correct.lower() or user_answer.lower() in [a.lower() for a in acceptable]:
                        is_correct = True
                        points = question['points']
        
        elif question['question_type'] in ['short_answer', 'sentence_building'] and answer_text:
            # For these types, auto-grade is limited. Mark as pending manual review.
            is_correct = None  # Requires teacher review
            points = 0
        
        # Save the answer
        await db.execute("""
            INSERT INTO quiz_answers (attempt_id, question_id, answer_text, selected_option_id, is_correct, points_earned)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (attempt_id, question_id, answer_text, selected_option_id, is_correct, points))
        
        # Update attempt score
        if is_correct:
            await db.execute("""
                UPDATE quiz_attempts SET score = score + ?, max_score = max_score + ? WHERE id = ?
            """, (points, question['points'], attempt_id))
        else:
            await db.execute("""
                UPDATE quiz_attempts SET max_score = max_score + ? WHERE id = ?
            """, (question['points'], attempt_id))
        
        await db.commit()
        return (is_correct, points)

async def complete_quiz_attempt(attempt_id: int) -> Dict:
    """Complete a quiz attempt and calculate results"""
    async with get_db() as db:
        # Update completion time
        await db.execute("""
            UPDATE quiz_attempts SET completed_at = CURRENT_TIMESTAMP WHERE id = ?
        """, (attempt_id,))
        
        # Get attempt details
        cursor = await db.execute("""
            SELECT qa.*, q.passing_score, q.title as quiz_title,
                   u.title as unit_title, c.name as class_name
            FROM quiz_attempts qa
            JOIN quizzes q ON qa.quiz_id = q.id
            JOIN units u ON q.unit_id = u.id
            JOIN classes c ON u.class_id = c.id
            WHERE qa.id = ?
        """, (attempt_id,))
        attempt = await cursor.fetchone()
        if not attempt:
            return {}
        attempt = dict(attempt)
        
        # Calculate percentage and pass/fail
        total_score = attempt['score']
        max_score = attempt['max_score']
        percentage = (total_score / max_score * 100) if max_score > 0 else 0
        passed = percentage >= attempt['passing_score']
        
        # Update pass status
        await db.execute("""
            UPDATE quiz_attempts SET passed = ? WHERE id = ?
        """, (passed, attempt_id))
        
        # Update leaderboard
        student_id = attempt['student_id']
        center_id = None
        cursor = await db.execute("""
            SELECT c.center_id FROM classes c
            JOIN units u ON c.id = u.class_id
            JOIN quizzes q ON u.id = q.unit_id
            JOIN quiz_attempts qa ON q.id = qa.quiz_id
            WHERE qa.id = ?
        """, (attempt_id,))
        row = await cursor.fetchone()
        if row:
            center_id = row['center_id']
            await update_leaderboard_entry(student_id, center_id, total_score)
        
        # Check and award badges
        await check_and_award_badges(student_id)
        
        await db.commit()
        
        return {
            'quiz_title': attempt['quiz_title'],
            'unit_title': attempt['unit_title'],
            'class_name': attempt['class_name'],
            'score': total_score,
            'max_score': max_score,
            'percentage': round(percentage, 2),
            'passed': passed,
            'passing_score': attempt['passing_score'],
            'attempt_number': attempt['attempt_number']
        }

async def get_student_quiz_results(student_id: int, limit: int = 20) -> List[Dict]:
    """Get quiz results for a student"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT qa.*, q.title as quiz_title, q.quiz_type,
                   u.title as unit_title, u.unit_number,
                   c.name as class_name, c.level
            FROM quiz_attempts qa
            JOIN quizzes q ON qa.quiz_id = q.id
            JOIN units u ON q.unit_id = u.id
            JOIN classes c ON u.class_id = c.id
            WHERE qa.student_id = ? AND qa.completed_at IS NOT NULL
            ORDER BY qa.completed_at DESC
            LIMIT ?
        """, (student_id, limit))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

# ========== HOMEWORK SYSTEM ==========

async def assign_homework(class_id: int, title: str, deadline: str, description: str = None,
                         quiz_id: int = None, max_score: int = 100, created_by: int = None,
                         allow_late_submission: bool = False, late_penalty_percent: int = 10) -> Optional[int]:
    """Assign homework to a class"""
    async with get_db() as db:
        cursor = await db.execute("""
            INSERT INTO homework (class_id, quiz_id, title, description, deadline, max_score, 
                                 created_by, allow_late_submission, late_penalty_percent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (class_id, quiz_id, title, description, deadline, max_score, 
              created_by, allow_late_submission, late_penalty_percent))
        await db.commit()
        return cursor.lastrowid

async def submit_homework(homework_id: int, student_id: int, file_id: str = None,
                         file_name: str = None, file_type: str = None,
                         text_content: str = None) -> Optional[int]:
    """Submit homework for a student"""
    async with get_db() as db:
        # Check if already submitted
        cursor = await db.execute("""
            SELECT id FROM homework_submissions WHERE homework_id = ? AND student_id = ?
        """, (homework_id, student_id))
        existing = await cursor.fetchone()
        if existing and not existing['can_resubmit']:
            return -1  # Already submitted and can't resubmit
        
        # Check deadline
        cursor = await db.execute("SELECT deadline, allow_late_submission FROM homework WHERE id = ?", (homework_id,))
        hw = await cursor.fetchone()
        if hw:
            deadline = datetime.fromisoformat(hw['deadline']) if isinstance(hw['deadline'], str) else hw['deadline']
            is_late = datetime.now() > deadline and not hw['allow_late_submission']
        else:
            is_late = False
        
        if existing:
            cursor = await db.execute("""
                UPDATE homework_submissions SET file_id = ?, file_name = ?, file_type = ?, 
                    text_content = ?, submitted_at = CURRENT_TIMESTAMP, is_late = ?, is_graded = 0
                WHERE id = ?
            """, (file_id, file_name, file_type, text_content, is_late, existing['id']))
            await db.commit()
            return existing['id']
        else:
            cursor = await db.execute("""
                INSERT INTO homework_submissions (homework_id, student_id, file_id, file_name, file_type, text_content, is_late)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (homework_id, student_id, file_id, file_name, file_type, text_content, is_late))
            await db.commit()
            return cursor.lastrowid

async def grade_homework(submission_id: int, score: int, feedback: str = None, graded_by: int = None) -> bool:
    """Grade a homework submission"""
    async with get_db() as db:
        await db.execute("""
            UPDATE homework_submissions SET is_graded = 1, score = ?, feedback = ?, graded_by = ?, graded_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (score, feedback, graded_by, submission_id))
        await db.commit()
        
        # Award points to student based on score percentage
        cursor = await db.execute("""
            SELECT hs.student_id, hs.score, h.max_score 
            FROM homework_submissions hs
            JOIN homework h ON hs.homework_id = h.id
            WHERE hs.id = ?
        """, (submission_id,))
        row = await cursor.fetchone()
        if row:
            percentage = (row['score'] / row['max_score'] * 100) if row['max_score'] > 0 else 0
            points = int(percentage / 10)  # 10% = 1 point
            if percentage >= 90:
                points += 5  # Bonus for excellent work
            await award_points(row['student_id'], points, "Homework graded")
        
        return True

async def get_homework_for_student(student_id: int) -> List[Dict]:
    """Get all homework assignments for a student"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT h.*, c.name as class_name, c.level,
                   hs.id as submission_id, hs.submitted_at, hs.is_graded, 
                   hs.score, hs.feedback, hs.can_resubmit,
                   q.title as quiz_title
            FROM homework h
            JOIN classes c ON h.class_id = c.id
            JOIN class_enrollments ce ON c.id = ce.class_id
            LEFT JOIN homework_submissions hs ON h.id = hs.homework_id AND hs.student_id = ce.student_id
            LEFT JOIN quizzes q ON h.quiz_id = q.id
            WHERE ce.student_id = ? AND ce.is_active = 1 AND c.is_archived = 0 AND h.is_active = 1
            ORDER BY h.deadline ASC
        """, (student_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_homework_submissions_for_teacher(teacher_id: int, homework_id: int = None) -> List[Dict]:
    """Get homework submissions for a teacher's classes"""
    async with get_db() as db:
        query = """
            SELECT hs.*, h.title as homework_title, h.deadline,
                   u.full_name as student_name, u.telegram_id as student_telegram_id,
                   c.name as class_name, c.level
            FROM homework_submissions hs
            JOIN homework h ON hs.homework_id = h.id
            JOIN users u ON hs.student_id = u.id
            JOIN classes c ON h.class_id = c.id
            JOIN class_teachers ct ON c.id = ct.class_id
            WHERE ct.teacher_id = ?
        """
        params = [teacher_id]
        if homework_id:
            query += " AND h.id = ?"
            params.append(homework_id)
        query += " ORDER BY hs.submitted_at DESC"
        
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

# ========== COMPETITION SYSTEM ==========

async def create_competition(center_id: int, title: str, competition_type: str, scope_type: str,
                            scope_value: str = None, start_date: str = None, end_date: str = None,
                            description: str = None, created_by: int = None) -> Optional[int]:
    """Create a new competition"""
    async with get_db() as db:
        cursor = await db.execute("""
            INSERT INTO competitions (center_id, title, description, competition_type, scope_type, scope_value, start_date, end_date, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (center_id, title, description, competition_type, scope_type, scope_value, start_date, end_date, created_by))
        await db.commit()
        return cursor.lastrowid

async def join_competition(competition_id: int, student_id: int) -> bool:
    """Add a student to a competition"""
    async with get_db() as db:
        try:
            await db.execute("""
                INSERT OR IGNORE INTO competition_participants (competition_id, student_id)
                VALUES (?, ?)
            """, (competition_id, student_id))
            await db.commit()
            return True
        except:
            return False

async def update_competition_ranks(competition_id: int):
    """Update rankings for a competition based on points earned"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT cp.student_id, COALESCE(SUM(qa.score), 0) + cp.points_earned as total_points
            FROM competition_participants cp
            LEFT JOIN quiz_attempts qa ON cp.student_id = qa.student_id
            LEFT JOIN competitions c ON cp.competition_id = c.id
            WHERE cp.competition_id = ? 
              AND qa.completed_at BETWEEN c.start_date AND c.end_date
            GROUP BY cp.student_id
            ORDER BY total_points DESC
        """, (competition_id,))
        rows = await cursor.fetchall()
        
        for rank, row in enumerate(rows, 1):
            await db.execute("""
                UPDATE competition_participants SET rank = ? WHERE competition_id = ? AND student_id = ?
            """, (rank, competition_id, row['student_id']))
        
        await db.commit()

async def get_competition_leaderboard(competition_id: int, limit: int = 10) -> List[Dict]:
    """Get competition leaderboard"""
    async with get_db() as db:
        await update_competition_ranks(competition_id)
        
        cursor = await db.execute("""
            SELECT cp.*, u.full_name, u.avatar_url,
                   c.name as class_name, c.level
            FROM competition_participants cp
            JOIN users u ON cp.student_id = u.id
            LEFT JOIN class_enrollments ce ON u.id = ce.student_id AND ce.is_active = 1
            LEFT JOIN classes c ON ce.class_id = c.id
            WHERE cp.competition_id = ?
            ORDER BY cp.rank
            LIMIT ?
        """, (competition_id, limit))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

# ========== LEADERBOARD SYSTEM ==========

async def update_leaderboard_entry(student_id: int, center_id: int, points: int, class_id: int = None, level: str = None):
    """Update a student's leaderboard entry"""
    async with get_db() as db:
        # Get class and level if not provided
        if not class_id or not level:
            cursor = await db.execute("""
                SELECT c.id as class_id, c.level
                FROM class_enrollments ce
                JOIN classes c ON ce.class_id = c.id
                WHERE ce.student_id = ? AND ce.is_active = 1 AND c.is_archived = 0
                LIMIT 1
            """, (student_id,))
            row = await cursor.fetchone()
            if row:
                class_id = row['class_id']
                level = row['level']
        
        await db.execute("""
            INSERT INTO leaderboard_entries (student_id, center_id, class_id, level, total_points, weekly_points, monthly_points)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(student_id, center_id) DO UPDATE SET
                total_points = total_points + ?,
                weekly_points = weekly_points + ?,
                monthly_points = monthly_points + ?,
                class_id = COALESCE(?, class_id),
                level = COALESCE(?, level),
                updated_at = CURRENT_TIMESTAMP
        """, (student_id, center_id, class_id, level, points, points, points,
              points, points, points, class_id, level))
        
        await db.commit()

async def get_leaderboard(center_id: int, leaderboard_type: str = 'global', class_id: int = None, 
                         level: str = None, limit: int = 20) -> List[Dict]:
    """Get leaderboard entries"""
    async with get_db() as db:
        query = """
            SELECT le.*, u.full_name, u.avatar_url, u.current_streak,
                   ROW_NUMBER() OVER (ORDER BY le.total_points DESC) as rank
            FROM leaderboard_entries le
            JOIN users u ON le.student_id = u.id
            WHERE le.center_id = ?
        """
        params = [center_id]
        
        if leaderboard_type == 'class' and class_id:
            query += " AND le.class_id = ?"
            params.append(class_id)
        elif leaderboard_type == 'level' and level:
            query += " AND le.level = ?"
            params.append(level)
        
        query += " ORDER BY le.total_points DESC LIMIT ?"
        params.append(limit)
        
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_student_rank(student_id: int, center_id: int) -> Dict:
    """Get a student's rank in various leaderboards"""
    async with get_db() as db:
        result = {"global_rank": None, "class_rank": None, "level_rank": None}
        
        # Global rank
        cursor = await db.execute("""
            SELECT COUNT(*) + 1 as rank FROM leaderboard_entries
            WHERE center_id = ? AND total_points > (
                SELECT total_points FROM leaderboard_entries WHERE student_id = ? AND center_id = ?
            )
        """, (center_id, student_id, center_id))
        row = await cursor.fetchone()
        if row:
            result['global_rank'] = row['rank']
        
        # Get class and level for more specific ranks
        cursor = await db.execute("""
            SELECT class_id, level FROM leaderboard_entries WHERE student_id = ? AND center_id = ?
        """, (student_id, center_id))
        entry = await cursor.fetchone()
        if entry:
            # Class rank
            cursor = await db.execute("""
                SELECT COUNT(*) + 1 as rank FROM leaderboard_entries
                WHERE center_id = ? AND class_id = ? AND total_points > (
                    SELECT total_points FROM leaderboard_entries WHERE student_id = ? AND center_id = ?
                )
            """, (center_id, entry['class_id'], student_id, center_id))
            row = await cursor.fetchone()
            if row:
                result['class_rank'] = row['rank']
            
            # Level rank
            cursor = await db.execute("""
                SELECT COUNT(*) + 1 as rank FROM leaderboard_entries
                WHERE center_id = ? AND level = ? AND total_points > (
                    SELECT total_points FROM leaderboard_entries WHERE student_id = ? AND center_id = ?
                )
            """, (center_id, entry['level'], student_id, center_id))
            row = await cursor.fetchone()
            if row:
                result['level_rank'] = row['rank']
        
        return result

# ========== BADGES & ACHIEVEMENTS ==========

async def check_and_award_badges(student_id: int) -> List[Dict]:
    """Check and award any earned badges"""
    async with get_db() as db:
        awarded_badges = []
        
        # Get student stats
        cursor = await db.execute("""
            SELECT 
                (SELECT COUNT(*) FROM quiz_attempts WHERE student_id = ? AND completed_at IS NOT NULL) as quizzes_completed,
                (SELECT COUNT(*) FROM quiz_attempts WHERE student_id = ? AND passed = 1) as quizzes_passed,
                (SELECT MAX(percentage) FROM (
                    SELECT (score * 100.0 / max_score) as percentage FROM quiz_attempts 
                    WHERE student_id = ? AND completed_at IS NOT NULL
                )) as best_percentage,
                current_streak,
                longest_streak
            FROM users WHERE id = ?
        """, (student_id, student_id, student_id, student_id))
        stats = await cursor.fetchone()
        if not stats:
            return []
        stats = dict(stats)
        
        # Get all badges not yet earned
        cursor = await db.execute("""
            SELECT * FROM badges WHERE id NOT IN (
                SELECT badge_id FROM student_badges WHERE student_id = ?
            )
        """, (student_id,))
        available_badges = [dict(row) for row in await cursor.fetchall()]
        
        for badge in available_badges:
            earned = False
            
            if badge['criteria'] == 'complete_1_quiz' and stats['quizzes_completed'] >= 1:
                earned = True
            elif badge['criteria'] == 'complete_10_quizzes' and stats['quizzes_completed'] >= 10:
                earned = True
            elif badge['criteria'] == 'perfect_quiz' and stats['best_percentage'] and stats['best_percentage'] >= 100:
                earned = True
            elif badge['criteria'] == 'streak_7' and stats['current_streak'] >= 7:
                earned = True
            elif badge['criteria'] == 'streak_30' and stats['current_streak'] >= 30:
                earned = True
            
            if earned:
                await db.execute("""
                    INSERT OR IGNORE INTO student_badges (student_id, badge_id) VALUES (?, ?)
                """, (student_id, badge['id']))
                await award_points(student_id, badge['points_awarded'], f"Earned badge: {badge['name']}")
                awarded_badges.append(badge)
        
        await db.commit()
        return awarded_badges

async def get_student_badges(student_id: int) -> List[Dict]:
    """Get all badges earned by a student"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT b.*, sb.earned_at
            FROM student_badges sb
            JOIN badges b ON sb.badge_id = b.id
            WHERE sb.student_id = ?
            ORDER BY sb.earned_at DESC
        """, (student_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def issue_certificate(student_id: int, title: str, level: str = None, issued_by: int = None) -> int:
    """Issue a certificate to a student"""
    async with get_db() as db:
        certificate_data = json.dumps({
            'student_id': student_id,
            'title': title,
            'level': level,
            'issued_at': datetime.now().isoformat(),
            'issued_by': issued_by
        })
        cursor = await db.execute("""
            INSERT INTO certificates (student_id, title, level, issued_by, certificate_data)
            VALUES (?, ?, ?, ?, ?)
        """, (student_id, title, level, issued_by, certificate_data))
        await db.commit()
        
        # Award points for certificate
        await award_points(student_id, 200, f"Received certificate: {title}")
        
        return cursor.lastrowid

async def get_student_certificates(student_id: int) -> List[Dict]:
    """Get all certificates for a student"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT c.*, u.full_name as issued_by_name
            FROM certificates c
            LEFT JOIN users u ON c.issued_by = u.id
            WHERE c.student_id = ?
            ORDER BY c.issued_at DESC
        """, (student_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

# ========== SPEAKING PARTNER ==========

async def add_speaking_topic(center_id: int, topic_text: str, level: str = None, 
                            category: str = None, created_by: int = None) -> int:
    """Add a speaking topic to the topic bank"""
    async with get_db() as db:
        cursor = await db.execute("""
            INSERT INTO speaking_topics (center_id, topic_text, level, category, created_by)
            VALUES (?, ?, ?, ?, ?)
        """, (center_id, topic_text, level, category, created_by))
        await db.commit()
        return cursor.lastrowid

async def get_random_speaking_topic(center_id: int, level: str = None) -> Optional[Dict]:
    """Get a random speaking topic"""
    async with get_db() as db:
        query = "SELECT * FROM speaking_topics WHERE center_id = ? AND is_active = 1"
        params = [center_id]
        if level:
            query += " AND level = ?"
            params.append(level)
        query += " ORDER BY RANDOM() LIMIT 1"
        
        cursor = await db.execute(query, params)
        row = await cursor.fetchone()
        return dict(row) if row else None

async def find_speaking_partner(student_id: int, level: str = None) -> Optional[Dict]:
    """Find a random speaking partner at the same level"""
    async with get_db() as db:
        # Get student's class and level
        cursor = await db.execute("""
            SELECT c.id as class_id, c.level, c.center_id
            FROM class_enrollments ce
            JOIN classes c ON ce.class_id = c.id
            WHERE ce.student_id = ? AND ce.is_active = 1 AND c.is_archived = 0
            LIMIT 1
        """, (student_id,))
        student_class = await cursor.fetchone()
        if not student_class:
            return None
        student_class = dict(student_class)
        
        target_level = level or student_class['level']
        
        # Find another student at same level and center
        cursor = await db.execute("""
            SELECT u.id, u.full_name, c.level as class_level
            FROM users u
            JOIN class_enrollments ce ON u.id = ce.student_id
            JOIN classes c ON ce.class_id = c.id
            WHERE c.center_id = ? AND c.level = ? AND u.id != ? AND ce.is_active = 1
            ORDER BY RANDOM()
            LIMIT 1
        """, (student_class['center_id'], target_level, student_id))
        partner = await cursor.fetchone()
        return dict(partner) if partner else None

async def start_speaking_session(student1_id: int, student2_id: int, topic_id: int = None) -> int:
    """Start a new speaking session"""
    async with get_db() as db:
        cursor = await db.execute("""
            INSERT INTO speaking_sessions (student1_id, student2_id, topic_id)
            VALUES (?, ?, ?)
        """, (student1_id, student2_id, topic_id))
        await db.commit()
        return cursor.lastrowid

async def end_speaking_session(session_id: int) -> bool:
    """End a speaking session"""
    async with get_db() as db:
        await db.execute("""
            UPDATE speaking_sessions SET 
                ended_at = CURRENT_TIMESTAMP,
                duration_minutes = ROUND((JULIANDAY(CURRENT_TIMESTAMP) - JULIANDAY(started_at)) * 24 * 60)
            WHERE id = ?
        """, (session_id,))
        await db.commit()
        return True
