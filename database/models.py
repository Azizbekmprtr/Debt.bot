# database/models.py
import aiosqlite
from datetime import datetime
from config import DB_PATH
from typing import Optional

async def init_db():
    """Initialize complete database schema with all tables"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode=WAL")
        
        # ========================
        # PLATFORM & CENTER TABLES
        # ========================
        
        # Centers (study centers)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS centers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                logo_url TEXT,
                brand_color TEXT DEFAULT '#2196F3',
                subscription_plan TEXT DEFAULT 'basic',
                plan_expires_at TIMESTAMP,
                trial_ends_at TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                is_suspended BOOLEAN DEFAULT FALSE,
                suspended_at TIMESTAMP,
                suspended_reason TEXT,
                max_students INTEGER DEFAULT 50,
                max_teachers INTEGER DEFAULT 5,
                max_classes INTEGER DEFAULT 10,
                timezone TEXT DEFAULT 'Asia/Tashkent',
                language TEXT DEFAULT 'uz',
                contact_email TEXT,
                contact_phone TEXT,
                address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Center settings (white-label, customization)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS center_settings (
                center_id INTEGER PRIMARY KEY,
                bot_name TEXT,
                welcome_message TEXT,
                allow_student_registration BOOLEAN DEFAULT TRUE,
                require_approval BOOLEAN DEFAULT FALSE,
                max_file_upload_size INTEGER DEFAULT 20971520,
                notification_email TEXT,
                sms_enabled BOOLEAN DEFAULT FALSE,
                data_retention_days INTEGER DEFAULT 365,
                custom_css TEXT,
                FOREIGN KEY (center_id) REFERENCES centers(id) ON DELETE CASCADE
            )
        """)
        
        # Feature flags per center
        await db.execute("""
            CREATE TABLE IF NOT EXISTS center_features (
                center_id INTEGER NOT NULL,
                feature_name TEXT NOT NULL,
                is_enabled BOOLEAN DEFAULT TRUE,
                PRIMARY KEY (center_id, feature_name),
                FOREIGN KEY (center_id) REFERENCES centers(id) ON DELETE CASCADE
            )
        """)
        
        # ========================
        # USERS TABLE (Multi-role)
        # ========================
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                username TEXT,
                full_name TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                password_hash TEXT,
                avatar_url TEXT,
                is_blocked BOOLEAN DEFAULT FALSE,
                blocked_reason TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                last_active TIMESTAMP,
                last_login TIMESTAMP,
                language TEXT DEFAULT 'uz',
                timezone TEXT DEFAULT 'Asia/Tashkent',
                total_points INTEGER DEFAULT 0,
                current_streak INTEGER DEFAULT 0,
                longest_streak INTEGER DEFAULT 0,
                last_activity_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # User roles (many-to-many)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_roles (
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('super_admin', 'center_admin', 'teacher', 'student', 'parent')),
                center_id INTEGER,
                granted_by INTEGER,
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, role, center_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (center_id) REFERENCES centers(id) ON DELETE CASCADE,
                FOREIGN KEY (granted_by) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        
        # Parent-Child relationships
        await db.execute("""
            CREATE TABLE IF NOT EXISTS parent_child (
                parent_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                relationship TEXT DEFAULT 'parent',
                is_primary BOOLEAN DEFAULT TRUE,
                can_view_grades BOOLEAN DEFAULT TRUE,
                can_view_attendance BOOLEAN DEFAULT TRUE,
                can_view_payments BOOLEAN DEFAULT TRUE,
                can_communicate BOOLEAN DEFAULT TRUE,
                linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (parent_id, student_id),
                FOREIGN KEY (parent_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # ========================
        # CLASSES & SCHEDULES
        # ========================
        await db.execute("""
            CREATE TABLE IF NOT EXISTS classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                center_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                level TEXT NOT NULL,
                description TEXT,
                price INTEGER DEFAULT 0,
                currency TEXT DEFAULT 'UZS',
                max_students INTEGER DEFAULT 30,
                is_active BOOLEAN DEFAULT TRUE,
                is_archived BOOLEAN DEFAULT FALSE,
                archived_at TIMESTAMP,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (center_id) REFERENCES centers(id) ON DELETE CASCADE,
                FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS class_enrollments (
                student_id INTEGER NOT NULL,
                class_id INTEGER NOT NULL,
                enrolled_by INTEGER,
                enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                unenrolled_at TIMESTAMP,
                PRIMARY KEY (student_id, class_id),
                FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE,
                FOREIGN KEY (enrolled_by) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS class_teachers (
                class_id INTEGER NOT NULL,
                teacher_id INTEGER NOT NULL,
                assigned_by INTEGER,
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_primary BOOLEAN DEFAULT FALSE,
                PRIMARY KEY (class_id, teacher_id),
                FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE,
                FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (assigned_by) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id INTEGER NOT NULL,
                day_of_week INTEGER NOT NULL CHECK(day_of_week BETWEEN 0 AND 6),
                start_time TIME NOT NULL,
                end_time TIME NOT NULL,
                room TEXT,
                subject TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE
            )
        """)
        
        # ========================
        # UNITS & MATERIALS
        # ========================
        await db.execute("""
            CREATE TABLE IF NOT EXISTS units (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                unit_number INTEGER NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                is_current BOOLEAN DEFAULT FALSE,
                video_url TEXT,
                audio_url TEXT,
                pdf_url TEXT,
                additional_materials TEXT,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE,
                FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
                UNIQUE(class_id, unit_number)
            )
        """)
        
        # ========================
        # QUIZ SYSTEM
        # ========================
        await db.execute("""
            CREATE TABLE IF NOT EXISTS quizzes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unit_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                quiz_type TEXT NOT NULL CHECK(quiz_type IN (
                    'mcq', 'short_answer', 'fill_gap', 'listening', 
                    'sentence_building', 'error_detection', 'matching_pairs'
                )),
                passing_score INTEGER DEFAULT 60,
                time_limit_minutes INTEGER,
                max_attempts INTEGER DEFAULT 1,
                is_active BOOLEAN DEFAULT TRUE,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (unit_id) REFERENCES units(id) ON DELETE CASCADE,
                FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS quiz_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_id INTEGER NOT NULL,
                question_type TEXT NOT NULL,
                question_text TEXT NOT NULL,
                explanation TEXT,
                points INTEGER DEFAULT 1,
                order_number INTEGER NOT NULL,
                media_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS question_options (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL,
                option_text TEXT NOT NULL,
                is_correct BOOLEAN DEFAULT FALSE,
                order_number INTEGER NOT NULL,
                FOREIGN KEY (question_id) REFERENCES quiz_questions(id) ON DELETE CASCADE
            )
        """)
        
        # Fill-gap answers
        await db.execute("""
            CREATE TABLE IF NOT EXISTS fill_gap_answers (
                question_id INTEGER PRIMARY KEY,
                correct_answer TEXT NOT NULL,
                acceptable_answers TEXT,
                case_sensitive BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (question_id) REFERENCES quiz_questions(id) ON DELETE CASCADE
            )
        """)
        
        # Matching pairs
        await db.execute("""
            CREATE TABLE IF NOT EXISTS matching_pairs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL,
                left_item TEXT NOT NULL,
                right_item TEXT NOT NULL,
                order_number INTEGER NOT NULL,
                FOREIGN KEY (question_id) REFERENCES quiz_questions(id) ON DELETE CASCADE
            )
        """)
        
        # ========================
        # HOMEWORK SYSTEM
        # ========================
        await db.execute("""
            CREATE TABLE IF NOT EXISTS homework (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id INTEGER NOT NULL,
                quiz_id INTEGER,
                title TEXT NOT NULL,
                description TEXT,
                deadline TIMESTAMP NOT NULL,
                max_score INTEGER DEFAULT 100,
                allow_late_submission BOOLEAN DEFAULT FALSE,
                late_penalty_percent INTEGER DEFAULT 10,
                is_active BOOLEAN DEFAULT TRUE,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE,
                FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE SET NULL,
                FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS homework_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                homework_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                file_id TEXT,
                file_name TEXT,
                file_type TEXT,
                file_size INTEGER,
                text_content TEXT,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_late BOOLEAN DEFAULT FALSE,
                is_graded BOOLEAN DEFAULT FALSE,
                score INTEGER,
                max_score INTEGER DEFAULT 100,
                feedback TEXT,
                graded_by INTEGER,
                graded_at TIMESTAMP,
                can_resubmit BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (homework_id) REFERENCES homework(id) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (graded_by) REFERENCES users(id) ON DELETE SET NULL,
                UNIQUE(homework_id, student_id)
            )
        """)
        
        # ========================
        # QUIZ ATTEMPTS & RESULTS
        # ========================
        await db.execute("""
            CREATE TABLE IF NOT EXISTS quiz_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                score INTEGER DEFAULT 0,
                max_score INTEGER DEFAULT 0,
                passed BOOLEAN DEFAULT FALSE,
                attempt_number INTEGER DEFAULT 1,
                FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS quiz_answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attempt_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                answer_text TEXT,
                selected_option_id INTEGER,
                is_correct BOOLEAN,
                points_earned INTEGER DEFAULT 0,
                answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (attempt_id) REFERENCES quiz_attempts(id) ON DELETE CASCADE,
                FOREIGN KEY (question_id) REFERENCES quiz_questions(id) ON DELETE CASCADE,
                FOREIGN KEY (selected_option_id) REFERENCES question_options(id) ON DELETE SET NULL
            )
        """)
        
        # ========================
        # ATTENDANCE SYSTEM
        # ========================
        await db.execute("""
            CREATE TABLE IF NOT EXISTS attendance_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id INTEGER NOT NULL,
                session_date DATE NOT NULL,
                taken_by INTEGER,
                taken_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_finalized BOOLEAN DEFAULT FALSE,
                notes TEXT,
                FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE,
                FOREIGN KEY (taken_by) REFERENCES users(id) ON DELETE SET NULL,
                UNIQUE(class_id, session_date)
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS attendance_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('present', 'late', 'absent', 'excused')),
                arrival_time TIME,
                notes TEXT,
                parent_notified BOOLEAN DEFAULT FALSE,
                notified_at TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES attendance_sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(session_id, student_id)
            )
        """)
        
        # ========================
        # PAYMENTS SYSTEM
        # ========================
        await db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                currency TEXT DEFAULT 'UZS',
                payment_method TEXT DEFAULT 'cash',
                payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                payment_for_month TEXT,
                notes TEXT,
                recorded_by INTEGER NOT NULL,
                center_id INTEGER NOT NULL,
                invoice_number TEXT,
                is_verified BOOLEAN DEFAULT FALSE,
                verified_by INTEGER,
                verified_at TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (recorded_by) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (center_id) REFERENCES centers(id) ON DELETE CASCADE,
                FOREIGN KEY (verified_by) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        
        # ========================
        # COMPETITIONS SYSTEM
        # ========================
        await db.execute("""
            CREATE TABLE IF NOT EXISTS competitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                center_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                competition_type TEXT CHECK(competition_type IN ('daily', 'weekly', 'monthly')),
                scope_type TEXT CHECK(scope_type IN ('class', 'level', 'center')),
                scope_value TEXT,
                start_date TIMESTAMP NOT NULL,
                end_date TIMESTAMP NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (center_id) REFERENCES centers(id) ON DELETE CASCADE,
                FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS competition_participants (
                competition_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                points_earned INTEGER DEFAULT 0,
                rank INTEGER,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (competition_id, student_id),
                FOREIGN KEY (competition_id) REFERENCES competitions(id) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # ========================
        # ACHIEVEMENTS & BADGES
        # ========================
        await db.execute("""
            CREATE TABLE IF NOT EXISTS badges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                icon TEXT,
                category TEXT,
                criteria TEXT,
                points_awarded INTEGER DEFAULT 0
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS student_badges (
                student_id INTEGER NOT NULL,
                badge_id INTEGER NOT NULL,
                earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (student_id, badge_id),
                FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (badge_id) REFERENCES badges(id) ON DELETE CASCADE
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS certificates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                level TEXT,
                issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                issued_by INTEGER,
                certificate_data TEXT,
                FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (issued_by) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        
        # ========================
        # LEADERBOARD SYSTEM
        # ========================
        await db.execute("""
            CREATE TABLE IF NOT EXISTS leaderboard_entries (
                student_id INTEGER NOT NULL,
                center_id INTEGER NOT NULL,
                class_id INTEGER,
                level TEXT,
                total_points INTEGER DEFAULT 0,
                weekly_points INTEGER DEFAULT 0,
                monthly_points INTEGER DEFAULT 0,
                rank_global INTEGER,
                rank_class INTEGER,
                rank_level INTEGER,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (student_id, center_id),
                FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (center_id) REFERENCES centers(id) ON DELETE CASCADE,
                FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE SET NULL
            )
        """)
        
        # ========================
        # SPEAKING PARTNER SYSTEM
        # ========================
        await db.execute("""
            CREATE TABLE IF NOT EXISTS speaking_topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                center_id INTEGER NOT NULL,
                topic_text TEXT NOT NULL,
                level TEXT,
                category TEXT,
                created_by INTEGER,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (center_id) REFERENCES centers(id) ON DELETE CASCADE,
                FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS speaking_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student1_id INTEGER NOT NULL,
                student2_id INTEGER NOT NULL,
                topic_id INTEGER,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                duration_minutes INTEGER,
                FOREIGN KEY (student1_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (student2_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (topic_id) REFERENCES speaking_topics(id) ON DELETE SET NULL
            )
        """)
        
        # ========================
        # COMMUNICATION SYSTEM
        # ========================
        await db.execute("""
            CREATE TABLE IF NOT EXISTS announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                center_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                target_role TEXT CHECK(target_role IN ('all', 'teachers', 'students', 'parents')),
                target_class_id INTEGER,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (center_id) REFERENCES centers(id) ON DELETE CASCADE,
                FOREIGN KEY (target_class_id) REFERENCES classes(id) ON DELETE SET NULL,
                FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                receiver_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                is_read BOOLEAN DEFAULT FALSE,
                read_at TIMESTAMP,
                parent_message_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (parent_message_id) REFERENCES messages(id) ON DELETE SET NULL
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                quiz_id INTEGER,
                rating INTEGER CHECK(rating BETWEEN 1 AND 5),
                comment TEXT,
                is_anonymous BOOLEAN DEFAULT FALSE,
                teacher_response TEXT,
                responded_by INTEGER,
                responded_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE SET NULL,
                FOREIGN KEY (responded_by) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        
        # ========================
        # SUPPORT TICKETS
        # ========================
        await db.execute("""
            CREATE TABLE IF NOT EXISTS support_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                center_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                description TEXT NOT NULL,
                priority TEXT DEFAULT 'normal' CHECK(priority IN ('urgent', 'high', 'normal', 'low')),
                status TEXT DEFAULT 'open' CHECK(status IN ('open', 'in_progress', 'resolved', 'closed')),
                assigned_to INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP,
                FOREIGN KEY (center_id) REFERENCES centers(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (assigned_to) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ticket_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ticket_id) REFERENCES support_tickets(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # ========================
        # SUBSCRIPTIONS & BILLING
        # ========================
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscription_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                description TEXT,
                max_students INTEGER,
                max_teachers INTEGER,
                max_classes INTEGER,
                features TEXT,
                price_monthly DECIMAL(10,2),
                price_yearly DECIMAL(10,2),
                trial_days INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscription_invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                center_id INTEGER NOT NULL,
                plan_id INTEGER NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                period TEXT CHECK(period IN ('monthly', 'yearly', 'trial')),
                start_date TIMESTAMP NOT NULL,
                end_date TIMESTAMP NOT NULL,
                status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'paid', 'cancelled', 'overdue')),
                paid_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (center_id) REFERENCES centers(id) ON DELETE CASCADE,
                FOREIGN KEY (plan_id) REFERENCES subscription_plans(id) ON DELETE CASCADE
            )
        """)
        
        # ========================
        # AUDIT LOGS & SECURITY
        # ========================
        await db.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                center_id INTEGER,
                action TEXT NOT NULL,
                entity_type TEXT,
                entity_id INTEGER,
                old_values TEXT,
                new_values TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY (center_id) REFERENCES centers(id) ON DELETE SET NULL
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS login_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER,
                ip_address TEXT,
                user_agent TEXT,
                is_successful BOOLEAN DEFAULT FALSE,
                failure_reason TEXT,
                attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # ========================
        # BACKUP & SYSTEM HEALTH
        # ========================
        await db.execute("""
            CREATE TABLE IF NOT EXISTS backups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                center_id INTEGER,
                backup_type TEXT CHECK(backup_type IN ('center', 'platform')),
                file_path TEXT NOT NULL,
                file_size INTEGER,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (center_id) REFERENCES centers(id) ON DELETE CASCADE,
                FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                component TEXT,
                message TEXT NOT NULL,
                error_trace TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # ========================
        # INDEXES
        # ========================
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_users_telegram ON users(telegram_id)",
            "CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone)",
            "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
            "CREATE INDEX IF NOT EXISTS idx_user_roles_user ON user_roles(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_user_roles_center ON user_roles(center_id)",
            "CREATE INDEX IF NOT EXISTS idx_classes_center ON classes(center_id)",
            "CREATE INDEX IF NOT EXISTS idx_class_enrollments_class ON class_enrollments(class_id)",
            "CREATE INDEX IF NOT EXISTS idx_class_enrollments_student ON class_enrollments(student_id)",
            "CREATE INDEX IF NOT EXISTS idx_units_class ON units(class_id)",
            "CREATE INDEX IF NOT EXISTS idx_quizzes_unit ON quizzes(unit_id)",
            "CREATE INDEX IF NOT EXISTS idx_homework_class ON homework(class_id)",
            "CREATE INDEX IF NOT EXISTS idx_homework_submissions_hw ON homework_submissions(homework_id)",
            "CREATE INDEX IF NOT EXISTS idx_attendance_sessions_class_date ON attendance_sessions(class_id, session_date)",
            "CREATE INDEX IF NOT EXISTS idx_payments_student ON payments(student_id)",
            "CREATE INDEX IF NOT EXISTS idx_payments_center ON payments(center_id)",
            "CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_id)",
            "CREATE INDEX IF NOT EXISTS idx_messages_receiver ON messages(receiver_id)",
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_center ON audit_logs(center_id)",
            "CREATE INDEX IF NOT EXISTS idx_quiz_attempts_student ON quiz_attempts(student_id)",
            "CREATE INDEX IF NOT EXISTS idx_leaderboard_points ON leaderboard_entries(total_points DESC)",
        ]
        
        for index in indexes:
            await db.execute(index)
        
        await db.commit()
        print("✅ Complete database schema initialized with all tables and indexes")

async def create_default_data():
    """Create default subscription plans and badges"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Default subscription plans
        plans = [
            ('Basic', 'basic', 'Free plan for small centers', 50, 5, 10, 
             '["attendance","homework","quizzes"]', 0, 0, 14),
            ('Pro', 'pro', 'Professional plan for growing centers', 200, 20, 50,
             '["attendance","homework","quizzes","competitions","leaderboard","payments"]', 29.99, 299.99, 14),
            ('Enterprise', 'enterprise', 'Unlimited plan for large centers', 1000, 100, 200,
             '["all"]', 99.99, 999.99, 30)
        ]
        
        for plan in plans:
            await db.execute("""
                INSERT OR IGNORE INTO subscription_plans 
                (name, slug, description, max_students, max_teachers, max_classes, features, price_monthly, price_yearly, trial_days)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, plan)
        
        # Default badges
        badges = [
            ('First Steps', 'Complete your first quiz', '🌟', 'learning', 'complete_1_quiz', 10),
            ('Quiz Master', 'Complete 10 quizzes', '🏆', 'learning', 'complete_10_quizzes', 50),
            ('Perfect Score', 'Get 100% on a quiz', '💯', 'achievement', 'perfect_quiz', 100),
            ('Streak 7', '7-day login streak', '🔥', 'streak', 'streak_7', 30),
            ('Streak 30', '30-day login streak', '⚡', 'streak', 'streak_30', 200),
            ('Helping Hand', 'Help another student', '🤝', 'social', 'help_student', 50),
            ('Top Performer', 'Rank #1 in class', '👑', 'leaderboard', 'rank_1_class', 500),
            ('Early Bird', 'Submit homework before deadline', '🐦', 'homework', 'early_submission', 20),
            ('Attendance Star', '100% attendance this month', '⭐', 'attendance', 'perfect_attendance', 100),
            ('Polyglot', 'Complete all levels', '🌍', 'achievement', 'all_levels_complete', 1000),
        ]
        
        for badge in badges:
            await db.execute("""
                INSERT OR IGNORE INTO badges (name, description, icon, category, criteria, points_awarded)
                VALUES (?, ?, ?, ?, ?, ?)
            """, badge)
        
        await db.commit()
        print("✅ Default data created (subscription plans, badges)")
