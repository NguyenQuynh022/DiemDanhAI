"""
migrate.py — Thêm tất cả cột mới và bảng mới vào DB.
Chạy: python migrate.py
"""
from app import create_app
from extensions import db

app = create_app()

COLUMN_MIGRATIONS = [
    ("users",   "bio",             "TEXT DEFAULT NULL AFTER student_code"),
    ("classes", "formula_config",  "JSON DEFAULT NULL AFTER schedule_info"),
    ("grades",  "attendance_score","DECIMAL(4,2) DEFAULT NULL AFTER class_id"),
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

    print("\n✅ Migration hoàn tất!")
