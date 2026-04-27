# database/queries_extended.py
"""
Extended query functions needed by various handlers
"""
import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from config import DB_PATH

async def get_db():
    """Get database connection"""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db

# ========== ADDITIONAL USER QUERIES ==========

async def get_user_by_username(username: str) -> Optional[Dict]:
    """Get user by username"""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def update_user_field(user_id: int, field: str, value: Any) -> bool:
    """Update a specific user field"""
    allowed_fields = ['full_name', 'phone', 'email', 'language', 'timezone',
                      'avatar_url', 'subscription_plan']
    if field not in allowed_fields:
        return False

    async with get_db() as db:
        await db.execute(f"UPDATE users SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (value, user_id))
        await db.commit()
        return True

async def block_user(user_id: int, reason: str = None) -> bool:
    """Block a user"""
    async with get_db() as db:
        await db.execute("UPDATE users SET is_blocked = 1, blocked_reason = ? WHERE id = ?",
                        (reason, user_id))
        await db.commit()
        return True

async def unblock_user(user_id: int) -> bool:
    """Unblock a user"""
    async with get_db() as db:
        await db.execute("UPDATE users SET is_blocked = 0, blocked_reason = NULL WHERE id = ?",
                        (user_id,))
        await db.commit()
        return True

async def delete_user(user_id: int) -> bool:
    """Delete a user and all associated data"""
    async with get_db() as db:
        # Cascading delete handles most related data
        await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        await db.commit()
        return True

# ========== STUDENT-SPECIFIC QUERIES ==========

async def get_students_for_center(center_id: int) -> List[Dict]:
    """Get all students in a center"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT DISTINCT u.* FROM users u
            JOIN user_roles ur ON u.id = ur.user_id
            WHERE ur.center_id = ? AND ur.role = 'student'
            ORDER BY u.full_name
        """, (center_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_students_in_class(class_id: int) -> List[Dict]:
    """Get all students enrolled in a class"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT u.*, ce.enrolled_at
            FROM class_enrollments ce
            JOIN users u ON ce.student_id = u.id
            WHERE ce.class_id = ? AND ce.is_active = 1
            ORDER BY u.full_name
        """, (class_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_teachers_for_class(class_id: int) -> List[Dict]:
    """Get all teachers assigned to a class"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT u.*, ct.is_primary
            FROM class_teachers ct
            JOIN users u ON ct.teacher_id = u.id
            WHERE ct.class_id = ?
            ORDER BY ct.is_primary DESC, u.full_name
        """, (class_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_center_users(center_id: int, role: str = None) -> List[Dict]:
    """Get all users in a center, optionally filtered by role"""
    async with get_db() as db:
        if role:
            cursor = await db.execute("""
                SELECT DISTINCT u.*, GROUP_CONCAT(DISTINCT ur2.role) as roles
                FROM users u
                JOIN user_roles ur ON u.id = ur.user_id
                LEFT JOIN user_roles ur2 ON u.id = ur2.user_id AND ur2.center_id = ?
                WHERE ur.center_id = ? AND ur.role = ?
                GROUP BY u.id
                ORDER BY u.full_name
            """, (center_id, center_id, role))
        else:
            cursor = await db.execute("""
                SELECT DISTINCT u.*, GROUP_CONCAT(DISTINCT ur.role) as roles
                FROM users u
                JOIN user_roles ur ON u.id = ur.user_id
                WHERE ur.center_id = ?
                GROUP BY u.id
                ORDER BY u.full_name
            """, (center_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

# ========== ATTENDANCE QUERIES ==========

async def get_students_for_attendance(class_id: int) -> List[Dict]:
    """Get students for attendance marking"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT u.id, u.full_name, u.phone, u.telegram_id
            FROM class_enrollments ce
            JOIN users u ON ce.student_id = u.id
            WHERE ce.class_id = ? AND ce.is_active = 1
            ORDER BY u.full_name
        """, (class_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_todays_attendance_session(class_id: int) -> Optional[Dict]:
    """Get today's attendance session for a class"""
    today = datetime.now().strftime("%Y-%m-%d")
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT * FROM attendance_sessions
            WHERE class_id = ? AND session_date = ?
            ORDER BY id DESC LIMIT 1
        """, (class_id, today))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def create_attendance_session(class_id: int, session_date: str, taken_by: int) -> int:
    """Create a new attendance session"""
    async with get_db() as db:
        cursor = await db.execute("""
            INSERT INTO attendance_sessions (class_id, session_date, taken_by)
            VALUES (?, ?, ?)
        """, (class_id, session_date, taken_by))
        await db.commit()
        return cursor.lastrowid

async def mark_attendance(session_id: int, student_id: int, status: str) -> bool:
    """Mark a student's attendance"""
    async with get_db() as db:
        await db.execute("""
            INSERT OR REPLACE INTO attendance_records (session_id, student_id, status)
            VALUES (?, ?, ?)
        """, (session_id, student_id, status))
        await db.commit()
        return True

async def finalize_attendance_session(session_id: int) -> bool:
    """Mark attendance session as finalized"""
    async with get_db() as db:
        await db.execute("""
            UPDATE attendance_sessions SET is_finalized = 1 WHERE id = ?
        """, (session_id,))
        await db.commit()
        return True

async def get_attendance_summary(session_id: int) -> Dict:
    """Get summary of an attendance session"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) as present,
                SUM(CASE WHEN status = 'late' THEN 1 ELSE 0 END) as late,
                SUM(CASE WHEN status = 'absent' THEN 1 ELSE 0 END) as absent,
                SUM(CASE WHEN status = 'excused' THEN 1 ELSE 0 END) as excused
            FROM attendance_records
            WHERE session_id = ?
        """, (session_id,))
        summary = dict(await cursor.fetchone())

        cursor = await db.execute("""
            SELECT ar.status, u.full_name as name
            FROM attendance_records ar
            JOIN users u ON ar.student_id = u.id
            WHERE ar.session_id = ?
            ORDER BY u.full_name
        """, (session_id,))
        records = [dict(row) for row in await cursor.fetchall()]

        cursor = await db.execute("""
            SELECT a.*, c.name as class_name
            FROM attendance_sessions a
            JOIN classes c ON a.class_id = c.id
            WHERE a.id = ?
        """, (session_id,))
        session = dict(await cursor.fetchone()) if await cursor.fetchone() else {}

        return {'summary': summary, 'records': records, 'session': session}

async def get_student_attendance_history(student_id: int, limit: int = 30) -> List[Dict]:
    """Get attendance history for a student"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT a.session_date, ar.status, c.name as class_name
            FROM attendance_records ar
            JOIN attendance_sessions a ON ar.session_id = a.id
            JOIN classes c ON a.class_id = c.id
            WHERE ar.student_id = ?
            ORDER BY a.session_date DESC
            LIMIT ?
        """, (student_id, limit))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

# ========== QUIZ QUERIES ==========

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

async def get_quizzes_for_unit(unit_id: int) -> List[Dict]:
    """Get quizzes for a specific unit"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT * FROM quizzes WHERE unit_id = ? AND is_active = 1
            ORDER BY title
        """, (unit_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_student_quiz_attempts(student_id: int, quiz_id: int) -> List[Dict]:
    """Get a student's attempts for a specific quiz"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT * FROM quiz_attempts
            WHERE student_id = ? AND quiz_id = ? AND completed_at IS NOT NULL
            ORDER BY completed_at DESC
        """, (student_id, quiz_id))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

# ========== HOMEWORK QUERIES ==========

async def get_homework_for_class(class_id: int) -> List[Dict]:
    """Get all homework for a class"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT * FROM homework
            WHERE class_id = ? AND is_active = 1
            ORDER BY deadline DESC
        """, (class_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_pending_submissions_for_class(class_id: int) -> List[Dict]:
    """Get pending submissions for a class"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT hs.*, h.title as homework_title, u.full_name as student_name,
                   h.max_score
            FROM homework_submissions hs
            JOIN homework h ON hs.homework_id = h.id
            JOIN users u ON hs.student_id = u.id
            WHERE h.class_id = ? AND hs.is_graded = 0
            ORDER BY hs.submitted_at ASC
        """, (class_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_submission_by_id(submission_id: int) -> Optional[Dict]:
    """Get a submission by ID"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT hs.*, h.title as homework_title, h.max_score,
                   u.full_name as student_name, u.id as student_id
            FROM homework_submissions hs
            JOIN homework h ON hs.homework_id = h.id
            JOIN users u ON hs.student_id = u.id
            WHERE hs.id = ?
        """, (submission_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def get_homework_by_id(homework_id: int) -> Optional[Dict]:
    """Get homework by ID"""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM homework WHERE id = ?", (homework_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

# ========== SUBSCRIPTION QUERIES ==========

async def get_all_subscription_plans() -> List[Dict]:
    """Get all subscription plans"""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM subscription_plans WHERE is_active = 1 ORDER BY price_monthly")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_subscription_plan_by_id(plan_id: int) -> Optional[Dict]:
    """Get plan by ID"""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM subscription_plans WHERE id = ?", (plan_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def get_subscription_plan_by_slug(slug: str) -> Optional[Dict]:
    """Get plan by slug"""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM subscription_plans WHERE slug = ?", (slug,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def create_subscription_plan(name: str, slug: str, description: str, max_students: int,
                                   max_teachers: int, max_classes: int, price_monthly: float,
                                   price_yearly: float, trial_days: int, features: str) -> int:
    """Create a new subscription plan"""
    async with get_db() as db:
        cursor = await db.execute("""
            INSERT INTO subscription_plans (name, slug, description, max_students, max_teachers,
                                          max_classes, price_monthly, price_yearly, trial_days, features)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, slug, description, max_students, max_teachers, max_classes,
              price_monthly, price_yearly, trial_days, features))
        await db.commit()
        return cursor.lastrowid

async def update_center_subscription(center_id: int, plan_slug: str, max_students: int,
                                     max_teachers: int, max_classes: int) -> bool:
    """Update a center's subscription"""
    async with get_db() as db:
        await db.execute("""
            UPDATE centers SET subscription_plan = ?, max_students = ?, max_teachers = ?, max_classes = ?
            WHERE id = ?
        """, (plan_slug, max_students, max_teachers, max_classes, center_id))
        await db.commit()
        return True

async def update_center_expiry(center_id: int, new_expiry: datetime) -> bool:
    """Update center's plan expiry date"""
    async with get_db() as db:
        await db.execute("UPDATE centers SET plan_expires_at = ? WHERE id = ?",
                        (new_expiry.isoformat(), center_id))
        await db.commit()
        return True

async def create_subscription_invoice(center_id: int, plan_id: int, amount: float,
                                      period: str, start_date: datetime, end_date: datetime) -> int:
    """Create a subscription invoice"""
    async with get_db() as db:
        cursor = await db.execute("""
            INSERT INTO subscription_invoices (center_id, plan_id, amount, period, start_date, end_date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (center_id, plan_id, amount, period, start_date.isoformat(), end_date.isoformat()))
        await db.commit()
        return cursor.lastrowid

# ========== SETTINGS QUERIES ==========

async def get_setting(teacher_id: Optional[int], key: str, default: Any = None) -> Any:
    """Get a setting value"""
    async with get_db() as db:
        if teacher_id:
            cursor = await db.execute(
                "SELECT value FROM teacher_settings WHERE teacher_id = ? AND key = ?",
                (teacher_id, key)
            )
        else:
            cursor = await db.execute(
                "SELECT value FROM teacher_settings WHERE teacher_id IS NULL AND key = ?",
                (key,)
            )
        row = await cursor.fetchone()
        return row[0] if row else default

async def set_setting(teacher_id: Optional[int], key: str, value: str) -> bool:
    """Set a setting value"""
    async with get_db() as db:
        if teacher_id:
            await db.execute("""
                INSERT OR REPLACE INTO teacher_settings (teacher_id, key, value, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (teacher_id, key, value))
        else:
            await db.execute("""
                INSERT OR REPLACE INTO teacher_settings (teacher_id, key, value, updated_at)
                VALUES (NULL, ?, ?, CURRENT_TIMESTAMP)
            """, (key, value))
        await db.commit()
        return True

# ========== PARENT NOTIFICATION SETTINGS ==========

async def get_parent_notification_settings(parent_id: int) -> Dict:
    """Get parent notification settings"""
    settings = {
        'attendance': True,
        'payments': True,
        'competitions': True,
        'exams': True
    }

    async with get_db() as db:
        cursor = await db.execute("""
            SELECT key, value FROM teacher_settings
            WHERE teacher_id = ? AND key LIKE 'notify_%'
        """, (parent_id,))
        rows = await cursor.fetchall()

        for row in rows:
            key = row[0].replace('notify_', '')
            settings[key] = row[1] == 'true'

    return settings

async def toggle_parent_notification(parent_id: int, setting: str) -> bool:
    """Toggle a parent notification setting"""
    current = await get_parent_notification_settings(parent_id)
    new_value = not current.get(setting, True)

    async with get_db() as db:
        await db.execute("""
            INSERT OR REPLACE INTO teacher_settings (teacher_id, key, value, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, (parent_id, f'notify_{setting}', str(new_value).lower()))
        await db.commit()

    return True

# ========== FEEDBACK & MESSAGES ==========

async def submit_feedback(student_id: int, quiz_id: int = None, rating: int = None,
                          comment: str = None, is_anonymous: bool = False) -> int:
    """Submit feedback"""
    async with get_db() as db:
        cursor = await db.execute("""
            INSERT INTO feedback (student_id, quiz_id, rating, comment, is_anonymous)
            VALUES (?, ?, ?, ?, ?)
        """, (student_id, quiz_id, rating, comment, is_anonymous))
        await db.commit()
        return cursor.lastrowid

async def mark_messages_read(user_id: int) -> bool:
    """Mark all messages as read for a user"""
    async with get_db() as db:
        await db.execute("""
            UPDATE messages SET is_read = 1, read_at = CURRENT_TIMESTAMP
            WHERE receiver_id = ? AND is_read = 0
        """, (user_id,))
        await db.commit()
        return True

async def get_announcements_for_class(class_id: int) -> List[Dict]:
    """Get announcements for a specific class"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT * FROM announcements
            WHERE (target_class_id = ? OR target_class_id IS NULL) AND is_active = 1
            ORDER BY created_at DESC
            LIMIT 20
        """, (class_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

# ========== COMPETITION QUERIES ==========

async def delete_class(class_id: int) -> bool:
    """Delete a class and all related data"""
    async with get_db() as db:
        await db.execute("DELETE FROM classes WHERE id = ?", (class_id,))
        await db.commit()
        return True

async def get_schedules_for_class(class_id: int) -> List[Dict]:
    """Get schedule for a class"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT * FROM schedules WHERE class_id = ? AND is_active = 1
            ORDER BY day_of_week, start_time
        """, (class_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_unit_by_id(unit_id: int) -> Optional[Dict]:
    """Get unit by ID"""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM units WHERE id = ?", (unit_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def get_student_points_history(student_id: int, limit: int = 30) -> List[Dict]:
    """Get points history for a student"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT * FROM audit_logs
            WHERE user_id = ? AND action = 'points_awarded'
            ORDER BY created_at DESC
            LIMIT ?
        """, (student_id, limit))
        rows = await cursor.fetchall()
        results = []
        for row in rows:
            data = dict(row)
            try:
                import json
                new_values = json.loads(data.get('new_values', '{}'))
                data['points'] = new_values.get('points', 0)
                data['reason'] = new_values.get('reason', '')
            except:
                data['points'] = 0
                data['reason'] = ''
            results.append(data)
        return results

async def get_all_badges() -> List[Dict]:
    """Get all available badges"""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM badges ORDER BY points_awarded")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def add_to_ip_blacklist(ip: str) -> bool:
    """Add IP to blacklist"""
    blacklist = await get_setting(None, 'ip_blacklist', '[]')
    import json
    ips = json.loads(blacklist) if isinstance(blacklist, str) else blacklist
    if ip not in ips:
        ips.append(ip)
        await set_setting(None, 'ip_blacklist', json.dumps(ips))
    return True

async def search_centers(search_term: str) -> List[Dict]:
    """Search centers by name, ID, or slug"""
    async with get_db() as db:
        try:
            center_id = int(search_term)
            cursor = await db.execute("SELECT * FROM centers WHERE id = ?", (center_id,))
        except ValueError:
            cursor = await db.execute("""
                SELECT * FROM centers
                WHERE name LIKE ? OR slug LIKE ?
                LIMIT 20
            """, (f'%{search_term}%', f'%{search_term}%'))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def update_ticket_status(ticket_id: int, status: str) -> bool:
    """Update support ticket status"""
    async with get_db() as db:
        if status in ('resolved', 'closed'):
            await db.execute("""
                UPDATE support_tickets SET status = ?, resolved_at = CURRENT_TIMESTAMP WHERE id = ?
            """, (status, ticket_id))
        else:
            await db.execute("UPDATE support_tickets SET status = ? WHERE id = ?", (status, ticket_id))
        await db.commit()
        return True

async def update_ticket_priority(ticket_id: int, priority: str) -> bool:
    """Update support ticket priority"""
    async with get_db() as db:
        await db.execute("UPDATE support_tickets SET priority = ? WHERE id = ?", (priority, ticket_id))
        await db.commit()
        return True

async def add_ticket_response(ticket_id: int, user_id: int, message: str) -> int:
    """Add a response to a support ticket"""
    async with get_db() as db:
        cursor = await db.execute("""
            INSERT INTO ticket_responses (ticket_id, user_id, message)
            VALUES (?, ?, ?)
        """, (ticket_id, user_id, message))
        await db.commit()
        return cursor.lastrowid

async def delete_ticket(ticket_id: int) -> bool:
    """Delete a support ticket"""
    async with get_db() as db:
        await db.execute("DELETE FROM support_tickets WHERE id = ?", (ticket_id,))
        await db.commit()
        return True
