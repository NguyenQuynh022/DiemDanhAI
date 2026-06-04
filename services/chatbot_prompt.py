"""
services/chatbot_prompt.py
System prompt builder cho EduPortal AI Chatbot
"""

from datetime import date

from models.user import User
from models.class_model import Class
from models.enrollment import Enrollment
from models.grade import Grade
from models.attendance import Attendance
from models.session import Session
from models.notification import Notification

from extensions import db


# =========================================================
# HỌC KỲ HIỆN TẠI
# =========================================================

CURRENT_SEM = "HK2-2025"


# =========================================================
# LABEL HỌC KỲ
# =========================================================

SEM_LABELS = {
    "HK1-2023": "HK1 năm học 2023-2024",
    "HK2-2023": "HK2 năm học 2023-2024",
    "HK1-2024": "HK1 năm học 2024-2025",
    "HK2-2024": "HK2 năm học 2024-2025",
    "HK1-2025": "HK1 năm học 2025-2026",
    "HK2-2025": "HK2 năm học 2025-2026",
}


# =========================================================
# THỨ TRONG TUẦN
# =========================================================

DAY_NAMES = {
    0: "Thứ 2",
    1: "Thứ 3",
    2: "Thứ 4",
    3: "Thứ 5",
    4: "Thứ 6",
    5: "Thứ 7",
    6: "Chủ nhật",
}


# =========================================================
# TIẾT HỌC
# =========================================================

TIET_LABEL = {
    1: "07:30",
    2: "08:30",
    3: "09:30",
    4: "10:30",
    5: "11:30",
    6: "13:00",
    7: "14:00",
    8: "15:00",
    9: "16:00",
    10: "17:00",
}


# =========================================================
# HELPERS
# =========================================================

def _sem_label(sem_id: str) -> str:
    return SEM_LABELS.get(sem_id, sem_id)


def _grade_letter(total) -> str:

    if total is None:
        return "—"

    if total >= 9.0:
        return "A+"

    if total >= 8.5:
        return "A"

    if total >= 8.0:
        return "B+"

    if total >= 7.0:
        return "B"

    if total >= 6.5:
        return "C+"

    if total >= 5.5:
        return "C"

    if total >= 5.0:
        return "D+"

    if total >= 4.0:
        return "D"

    return "F"


def _pass_fail(total) -> str:

    if total is None:
        return "Chưa có điểm"

    return "Đạt" if total >= 4.0 else "Không đạt"


def _schedule_str(info: dict) -> str:

    if not info:
        return "Chưa có lịch"

    day = DAY_NAMES.get(info.get("day", -1), "?")

    tiet = info.get("tiet_start", "?")

    ntiet = info.get("num_tiet", "?")

    t_str = TIET_LABEL.get(tiet, f"tiết {tiet}")

    return f"{day}, {t_str}, {ntiet} tiết"


def _gpa10(grades_list):

    vals = [
        g.total
        for g in grades_list
        if g.total is not None
    ]

    if not vals:
        return "Chưa có"

    return f"{sum(vals)/len(vals):.2f}"


# =========================================================
# BASE PROMPT
# =========================================================

_BASE_RULES = """
Bạn là trợ lý AI của hệ thống quản lý đào tạo EduPortal.

=== QUY TẮC NĂM HỌC & HỌC KỲ ===
- HK1 bắt đầu tháng 9.
- HK2 bắt đầu tháng 1 năm sau.
- HK2 năm học 2025-2026 học các tháng:
  1, 3, 4, 5, 6 năm 2026.
- Nghỉ toàn bộ tháng 2 do Tết.
- Mỗi học phần gồm 15 buổi học.
- HK2-2025 gồm 18 buổi vì kéo dài tới tháng 6.

=== CẤU TRÚC LỚP HỌC PHẦN ===
- Mỗi học phần mở đúng 7 lớp.
- Ví dụ: CS101-01 đến CS101-07.
- 7 lớp được phân bổ cho 2-3 giảng viên.
- Mỗi lớp có 30-40 sinh viên.
- Mỗi sinh viên chỉ thuộc 1 lớp của mỗi môn.

=== QUY TẮC GIẢNG VIÊN ===
- Mỗi giảng viên dạy 3-4 môn/kỳ.
- Tổng 5-10 buổi/tuần.
- Không trùng lịch.
- Không trùng phòng.

=== PHÂN QUYỀN ===

Sinh viên KHÔNG được:
- Xem điểm người khác.
- Xem lớp không thuộc mình.
- Xem lịch giảng viên khác.

Giảng viên KHÔNG được:
- Xem lớp không phụ trách.
- Sửa dữ liệu học kỳ cũ.
- Xem dữ liệu ngoài quyền.

=== CÁCH TRẢ LỜI ===
- Trả lời bằng tiếng Việt.
- Ngắn gọn, rõ ràng.
- Dùng dữ liệu thật trong context.
- Không bịa dữ liệu.
""".strip()


# =========================================================
# STUDENT PROMPT
# =========================================================

def build_student_prompt(user: User) -> str:

    today = date.today()

    lines = [
        _BASE_RULES,
        "",
        "=== THÔNG TIN SINH VIÊN ===",
    ]

    lines.append(f"Tên: {user.full_name}")

    lines.append(
        f"MSSV: {user.student_code or 'Chưa cập nhật'}"
    )

    lines.append(
        f"Email: {user.email or '—'}"
    )

    lines.append(
        f"Ngày hôm nay: "
        f"{today.strftime('%d/%m/%Y')} "
        f"({DAY_NAMES.get(today.weekday(), '?')})"
    )

    lines.append(
        f"Học kỳ hiện tại: {_sem_label(CURRENT_SEM)}"
    )

    # =====================================================
    # LỚP ĐANG HỌC
    # =====================================================

    current_enrolls = (
        db.session.query(Enrollment, Class)
        .join(Class, Class.id == Enrollment.class_id)
        .filter(
            Enrollment.student_id == user.id,
            Enrollment.status == "enrolled",
            Class.semester == CURRENT_SEM,
        )
        .all()
    )

    lines.append("")
    lines.append(
        f"=== LỚP ĐANG HỌC ({_sem_label(CURRENT_SEM)}) ==="
    )

    if current_enrolls:

        for enroll, cls in current_enrolls:

            lect_name = (
                cls.lecturer.full_name
                if cls.lecturer
                else "—"
            )

            sched = _schedule_str(
                cls.schedule_info or {}
            )

            lines.append(
                f"- {cls.class_name} | "
                f"{cls.course_name} "
                f"({cls.course_code}) | "
                f"Phòng: {cls.room} | "
                f"{sched} | "
                f"GV: {lect_name}"
            )

    else:
        lines.append("- Không có lớp nào.")

    # =====================================================
    # LỊCH HỌC HÔM NAY
    # =====================================================

    today_sessions = (
        db.session.query(Session, Class)
        .join(Class, Class.id == Session.class_id)
        .join(
            Enrollment,
            (
                Enrollment.class_id == Class.id
            )
            & (
                Enrollment.student_id == user.id
            )
        )
        .filter(
            Session.session_date == today,
            Session.status.in_(
                ["scheduled", "ongoing"]
            ),
            Enrollment.status == "enrolled",
        )
        .all()
    )

    lines.append("")
    lines.append(
        f"=== LỊCH HỌC HÔM NAY "
        f"({today.strftime('%d/%m/%Y')}) ==="
    )

    if today_sessions:

        for sess, cls in today_sessions:

            lines.append(
                f"- {cls.course_name} "
                f"({cls.class_name}) | "
                f"Phòng: {sess.room} | "
                f"{sess.start_time.strftime('%H:%M')}"
                f"-"
                f"{sess.end_time.strftime('%H:%M')} | "
                f"{sess.status}"
            )

    else:
        lines.append("- Không có lịch học hôm nay.")

    # =====================================================
    # BẢNG ĐIỂM
    # =====================================================

    all_grades = (
        db.session.query(Grade, Class)
        .join(Class, Class.id == Grade.class_id)
        .filter(Grade.student_id == user.id)
        .order_by(Class.semester)
        .all()
    )

    sem_grades = {}

    for g, cls in all_grades:
        sem_grades.setdefault(
            cls.semester,
            []
        ).append((g, cls))

    lines.append("")
    lines.append("=== BẢNG ĐIỂM ===")

    if sem_grades:

        for sem_id in sorted(sem_grades.keys()):

            entries = sem_grades[sem_id]

            gpa = _gpa10(
                [g for g, _ in entries]
            )

            lines.append("")
            lines.append(
                f"{_sem_label(sem_id)} "
                f"(GPA: {gpa})"
            )

            for g, cls in entries:

                total_str = (
                    f"{g.total:.1f}"
                    if g.total is not None
                    else "—"
                )

                lines.append(
                    f"- {cls.course_name} "
                    f"({cls.class_name}) → "
                    f"{total_str} | "
                    f"{_grade_letter(g.total)} | "
                    f"{_pass_fail(g.total)}"
                )

    else:
        lines.append("- Chưa có điểm.")

    # =====================================================
    # GPA TÍCH LŨY
    # =====================================================

    all_totals = [
        g.total
        for g, _ in all_grades
        if g.total is not None
    ]

    if all_totals:

        gpa_cum = (
            sum(all_totals)
            / len(all_totals)
        )

        lines.append("")
        lines.append(
            f"GPA tích lũy: "
            f"{gpa_cum:.2f} | "
            f"{_grade_letter(gpa_cum)}"
        )

    # =====================================================
    # ĐIỂM DANH
    # =====================================================

    lines.append("")
    lines.append(
        f"=== ĐIỂM DANH "
        f"{_sem_label(CURRENT_SEM)} ==="
    )

    if current_enrolls:

        for enroll, cls in current_enrolls:

            att_records = (
                Attendance.query.filter_by(
                    student_id=user.id,
                    class_id=cls.id
                ).all()
            )

            total_att = len(att_records)

            present = sum(
                1
                for a in att_records
                if a.status in ["present", "late"]
            )

            absent = sum(
                1
                for a in att_records
                if a.status == "absent"
            )

            rate = (
                f"{present/total_att*100:.0f}%"
                if total_att
                else "—"
            )

            lines.append(
                f"- {cls.class_name} | "
                f"{cls.course_name} | "
                f"Đã học: {total_att} | "
                f"Có mặt: {present} | "
                f"Vắng: {absent} | "
                f"Tỷ lệ: {rate}"
            )

    else:
        lines.append("- Không có dữ liệu điểm danh.")

    # =====================================================
    # THÔNG BÁO
    # =====================================================

    unread_count = (
        Notification.query.filter_by(
            user_id=user.id,
            is_read=False
        ).count()
    )

    if unread_count:

        lines.append("")

        lines.append(
            f"⚠️ Bạn có "
            f"{unread_count} "
            f"thông báo chưa đọc."
        )

    return "\n".join(lines)


# =========================================================
# LECTURER PROMPT
# =========================================================

def build_lecturer_prompt(user: User) -> str:

    today = date.today()

    lines = [
        _BASE_RULES,
        "",
        "=== THÔNG TIN GIẢNG VIÊN ===",
    ]

    lines.append(f"Tên: {user.full_name}")

    lines.append(
        f"Email: {user.email or '—'}"
    )

    lines.append(
        f"Ngày hôm nay: "
        f"{today.strftime('%d/%m/%Y')} "
        f"({DAY_NAMES.get(today.weekday(), '?')})"
    )

    lines.append(
        f"Học kỳ hiện tại: {_sem_label(CURRENT_SEM)}"
    )

    # =====================================================
    # LỚP ĐANG DẠY
    # =====================================================

    current_classes = (
        Class.query.filter_by(
            lecturer_id=user.id,
            semester=CURRENT_SEM,
            status="active"
        ).all()
    )

    lines.append("")
    lines.append(
        f"=== LỚP ĐANG DẠY "
        f"({_sem_label(CURRENT_SEM)}) ==="
    )

    if current_classes:

        for cls in current_classes:

            enrolled = (
                Enrollment.query.filter_by(
                    class_id=cls.id,
                    status="enrolled"
                ).count()
            )

            sched = _schedule_str(
                cls.schedule_info or {}
            )

            lines.append(
                f"- {cls.class_name} | "
                f"{cls.course_name} "
                f"({cls.course_code}) | "
                f"Phòng: {cls.room} | "
                f"{sched} | "
                f"Sĩ số: {enrolled}"
            )

    else:
        lines.append("- Không có lớp.")

    # =====================================================
    # BUỔI GIẢNG HÔM NAY
    # =====================================================

    today_sessions = (
        db.session.query(Session, Class)
        .join(Class, Class.id == Session.class_id)
        .filter(
            Class.lecturer_id == user.id,
            Session.session_date == today,
            Session.status.in_(
                ["scheduled", "ongoing"]
            ),
        )
        .all()
    )

    lines.append("")
    lines.append(
        f"=== BUỔI GIẢNG HÔM NAY "
        f"({today.strftime('%d/%m/%Y')}) ==="
    )

    if today_sessions:

        for sess, cls in today_sessions:

            enrolled = (
                Enrollment.query.filter_by(
                    class_id=cls.id,
                    status="enrolled"
                ).count()
            )

            present = (
                Attendance.query.filter_by(
                    class_id=cls.id,
                    session_id=sess.id,
                    status="present"
                ).count()
            )

            lines.append(
                f"- {cls.course_name} "
                f"({cls.class_name}) | "
                f"Phòng: {sess.room} | "
                f"{sess.start_time.strftime('%H:%M')}"
                f"-"
                f"{sess.end_time.strftime('%H:%M')} | "
                f"Điểm danh: "
                f"{present}/{enrolled}"
            )

    else:
        lines.append("- Không có buổi giảng.")

    return "\n".join(lines)