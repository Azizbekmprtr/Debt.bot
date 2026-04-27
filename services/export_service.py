# services/export_service.py
import os
import csv
import json
from datetime import datetime
from typing import Dict, List, Optional
import database.queries as db
from config import EXPORTS_DIR

class ExportService:
    """Service for exporting various data formats"""

    @staticmethod
    async def export_attendance_to_csv(center_id: int, class_id: Optional[int] = None) -> str:
        """Export attendance data to CSV"""
        filename = f"attendance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join(EXPORTS_DIR, filename)
        os.makedirs(EXPORTS_DIR, exist_ok=True)

        async with db.get_db() as conn:
            if class_id:
                cursor = await conn.execute("""
                    SELECT a.session_date, c.name as class_name, u.full_name, ar.status, ar.notes
                    FROM attendance_records ar
                    JOIN attendance_sessions a ON ar.session_id = a.id
                    JOIN classes c ON a.class_id = c.id
                    JOIN users u ON ar.student_id = u.id
                    WHERE a.class_id = ?
                    ORDER BY a.session_date DESC, u.full_name
                """, (class_id,))
            else:
                cursor = await conn.execute("""
                    SELECT a.session_date, c.name as class_name, u.full_name, ar.status, ar.notes
                    FROM attendance_records ar
                    JOIN attendance_sessions a ON ar.session_id = a.id
                    JOIN classes c ON a.class_id = c.id
                    JOIN users u ON ar.student_id = u.id
                    WHERE c.center_id = ?
                    ORDER BY a.session_date DESC, c.name, u.full_name
                """, (center_id,))

            rows = await cursor.fetchall()

        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['Date', 'Class', 'Student', 'Status', 'Notes'])
            for row in rows:
                writer.writerow(row)

        return filepath

    @staticmethod
    async def export_payments_to_csv(center_id: int) -> str:
        """Export payment data to CSV"""
        filename = f"payments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join(EXPORTS_DIR, filename)
        os.makedirs(EXPORTS_DIR, exist_ok=True)

        async with db.get_db() as conn:
            cursor = await conn.execute("""
                SELECT p.payment_date, u.full_name as student_name, p.amount,
                       p.payment_method, p.notes, p.payment_for_month,
                       u2.full_name as recorded_by
                FROM payments p
                JOIN users u ON p.student_id = u.id
                JOIN users u2 ON p.recorded_by = u2.id
                WHERE p.center_id = ?
                ORDER BY p.payment_date DESC
            """, (center_id,))
            rows = await cursor.fetchall()

        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['Date', 'Student', 'Amount', 'Method', 'Notes', 'Month', 'Recorded By'])
            for row in rows:
                writer.writerow(row)

        return filepath

    @staticmethod
    async def export_quiz_results_to_csv(quiz_id: int) -> str:
        """Export quiz results to CSV"""
        filename = f"quiz_results_{quiz_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join(EXPORTS_DIR, filename)
        os.makedirs(EXPORTS_DIR, exist_ok=True)

        async with db.get_db() as conn:
            cursor = await conn.execute("""
                SELECT u.full_name, qa.score, qa.max_score,
                       ROUND(CAST(qa.score AS FLOAT) / CAST(qa.max_score AS FLOAT) * 100, 1) as percentage,
                       CASE WHEN qa.passed = 1 THEN 'Yes' ELSE 'No' END as passed,
                       qa.attempt_number, qa.completed_at
                FROM quiz_attempts qa
                JOIN users u ON qa.student_id = u.id
                WHERE qa.quiz_id = ? AND qa.completed_at IS NOT NULL
                ORDER BY qa.score DESC
            """, (quiz_id,))
            rows = await cursor.fetchall()

        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['Student', 'Score', 'Max Score', 'Percentage', 'Passed', 'Attempt', 'Completed'])
            for row in rows:
                writer.writerow(row)

        return filepath

    @staticmethod
    async def export_students_to_csv(center_id: int) -> str:
        """Export student list to CSV"""
        filename = f"students_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join(EXPORTS_DIR, filename)
        os.makedirs(EXPORTS_DIR, exist_ok=True)

        students = await db.get_center_users(center_id, 'student')

        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['Full Name', 'Phone', 'Telegram ID', 'Points', 'Streak', 'Joined'])

            for student in students:
                writer.writerow([
                    student.get('full_name', ''),
                    student.get('phone', ''),
                    student.get('telegram_id', ''),
                    student.get('total_points', 0),
                    student.get('current_streak', 0),
                    student.get('created_at', '')[:10] if student.get('created_at') else ''
                ])

        return filepath

    @staticmethod
    async def export_class_roster_to_csv(class_id: int) -> str:
        """Export class roster to CSV"""
        filename = f"roster_class_{class_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join(EXPORTS_DIR, filename)
        os.makedirs(EXPORTS_DIR, exist_ok=True)

        async with db.get_db() as conn:
            cursor = await conn.execute("""
                SELECT u.full_name, u.phone, u.telegram_id, ce.enrolled_at
                FROM class_enrollments ce
                JOIN users u ON ce.student_id = u.id
                WHERE ce.class_id = ? AND ce.is_active = 1
                ORDER BY u.full_name
            """, (class_id,))
            rows = await cursor.fetchall()

        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['Student Name', 'Phone', 'Telegram ID', 'Enrolled Date'])
            for row in rows:
                writer.writerow(row)

        return filepath

    @staticmethod
    async def export_center_report(center_id: int) -> str:
        """Export comprehensive center report as JSON"""
        filename = f"center_report_{center_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(EXPORTS_DIR, filename)
        os.makedirs(EXPORTS_DIR, exist_ok=True)

        center = await db.get_center_by_id(center_id)
        classes = await db.get_classes_for_center(center_id)

        report = {
            'export_date': datetime.now().isoformat(),
            'center': center,
            'statistics': {},
            'classes': []
        }

        # Get statistics
        from .queries import get_center_statistics
        report['statistics'] = await get_center_statistics(center_id)

        # Get class details
        for cls in classes:
            units = await db.get_units_for_class(cls['id'])
            students = await db.get_students_in_class(cls['id'])
            teachers = await db.get_teachers_for_class(cls['id'])

            class_data = {
                **cls,
                'units_count': len(units),
                'students_count': len(students),
                'teachers': [t['full_name'] for t in teachers]
            }
            report['classes'].append(class_data)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)

        return filepath
