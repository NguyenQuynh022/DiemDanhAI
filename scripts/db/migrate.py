"""
scripts/db/migrate.py — Thêm tất cả cột mới và bảng mới vào DB.
Chạy: python scripts/db/migrate.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app import create_app
from extensions import db

app = create_app()

COLUMN_MIGRATIONS = [
    ("users",                "bio",              "TEXT DEFAULT NULL AFTER student_code"),
    ("classes",              "formula_config",   "JSON DEFAULT NULL AFTER schedule_info"),
    ("grades",               "attendance_score", "DECIMAL(4,2) DEFAULT NULL AFTER class_id"),
    ("registration_configs", "open_from",        "DATETIME DEFAULT NULL AFTER is_open"),
    ("registration_configs", "open_until",       "DATETIME DEFAULT NULL AFTER open_from"),
    ("face_data",            "liveness_score",   "DECIMAL(5,4) DEFAULT NULL AFTER confidence"),
    ("face_data",            "is_trained",       "TINYINT(1) NOT NULL DEFAULT 0 AFTER liveness_score"),
]

def column_exists(conn, table, column):
    r = conn.execute(db.text(
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:t AND COLUMN_NAME=:c"
    ), {"t": table, "c": column})
    return r.scalar() > 0

def table_exists(conn, table):
    r = conn.execute(db.text(
        "SELECT COUNT(*) FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:t"
    ), {"t": table})
    return r.scalar() > 0

with app.app_context():
    with db.engine.connect() as conn:
        # Column migrations
        for table, column, definition in COLUMN_MIGRATIONS:
            if column_exists(conn, table, column):
                print(f"  ✓ {table}.{column} — đã tồn tại")
            else:
                conn.execute(db.text(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {definition}"))
                conn.commit()
                print(f"  ✅ {table}.{column} — đã thêm!")

        # Create face_data table if not exists
        if not table_exists(conn, 'face_data'):
            conn.execute(db.text("""
                CREATE TABLE face_data (
                    id INT NOT NULL AUTO_INCREMENT,
                    student_id INT NOT NULL,
                    embedding LONGBLOB NOT NULL,
                    embedding_model VARCHAR(50) DEFAULT 'face_recognition',
                    image_count INT DEFAULT 1,
                    confidence DECIMAL(5,4) DEFAULT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (id),
                    UNIQUE KEY uq_face_student (student_id),
                    CONSTRAINT fk_face_student FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))
            conn.commit()
            print("  ✅ face_data table — đã tạo!")
        else:
            print("  ✓ face_data table — đã tồn tại")

        # Create announcements table if not exists
        if not table_exists(conn, 'announcements'):
            conn.execute(db.text("""
                CREATE TABLE announcements (
                    id INT NOT NULL AUTO_INCREMENT,
                    title VARCHAR(300) NOT NULL,
                    content TEXT DEFAULT NULL,
                    category ENUM('academic','finance','general','scholarship','exam') NOT NULL DEFAULT 'academic',
                    is_new TINYINT(1) DEFAULT 1,
                    is_pinned TINYINT(1) DEFAULT 0,
                    is_published TINYINT(1) DEFAULT 1,
                    author_id INT DEFAULT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (id),
                    CONSTRAINT fk_ann_author FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))
            conn.commit()
            print("  ✅ announcements table — đã tạo!")
        else:
            print("  ✓ announcements table — đã tồn tại")

        # Create registration_configs table if not exists
        if not table_exists(conn, 'registration_configs'):
            conn.execute(db.text("""
                CREATE TABLE registration_configs (
                    id INT NOT NULL AUTO_INCREMENT,
                    semester VARCHAR(20) NOT NULL,
                    is_open TINYINT(1) NOT NULL DEFAULT 0,
                    min_courses INT NOT NULL DEFAULT 3,
                    max_courses INT NOT NULL DEFAULT 7,
                    note VARCHAR(300) DEFAULT NULL,
                    updated_by INT DEFAULT NULL,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (id),
                    UNIQUE KEY uq_reg_semester (semester),
                    CONSTRAINT fk_reg_actor FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))
            conn.commit()
            print("  ✅ registration_configs table — đã tạo!")
        else:
            print("  ✓ registration_configs table — đã tồn tại")

        # Create face_samples table if not exists
        if not table_exists(conn, 'face_samples'):
            conn.execute(db.text("""
                CREATE TABLE face_samples (
                    id INT NOT NULL AUTO_INCREMENT,
                    student_id INT NOT NULL,
                    pose_label VARCHAR(30) DEFAULT 'frontal',
                    embedding LONGBLOB NOT NULL,
                    quality_score DECIMAL(5,4) DEFAULT 0.9500,
                    image_path VARCHAR(255) DEFAULT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (id),
                    KEY idx_face_sample_student (student_id),
                    CONSTRAINT fk_face_sample_student FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))
            conn.commit()
            print("  ✅ face_samples table — đã tạo!")
        else:
            print("  ✓ face_samples table — đã tồn tại")

    print("\n✅ Migration hoàn tất!")
