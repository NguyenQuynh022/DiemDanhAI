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


from utils.timetable import get_current_semester_id, format_semester_label

# =========================================================
# HỌC KỲ HIỆN TẠI (ĐỘNG THEO THÁNG: HK1 T8-T12, HK2 T2-T5)
# =========================================================

def _get_current_sem() -> str:
    return get_current_semester_id()


# =========================================================
# LABEL HỌC KỲ
# =========================================================

def _sem_label(sem_id: str) -> str:
    try:
        return format_semester_label(sem_id)
    except Exception:
        return sem_id


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
- Học kỳ 1 (HK1) bắt đầu vào tháng 8 và kết thúc vào tháng 12 cùng năm.
- Học kỳ 2 (HK2) bắt đầu vào tháng 2 và kết thúc vào tháng 5 năm sau.
- Lịch học chính khóa diễn ra từ Thứ 2 đến Thứ 6 (không học cuối tuần).

=== CẤU TRÚC ĐĂNG KÝ TÍN CHỈ & LỚP HỌC PHẦN ===
- Admin (Phòng Đào tạo) mở cổng đăng ký tín chỉ và tạo các lớp học phần.
- Sinh viên đăng ký tối thiểu 3 môn và tối đa 7 môn mỗi học kỳ (trung bình 2 tín chỉ/môn).
- Không học trùng lặp môn (cùng mã học phần) trong cùng 1 học kỳ.
- Không trùng lịch học (Thứ & Tiết) giữa các lớp học phần.
- Mã số sinh viên (MSSV) tối đa 8 ký tự gồm chữ IN HOA và số, 2 số đầu là Khóa tuyển sinh (ví dụ: 23ITB185).

=== QUY TẮC GIẢNG VIÊN ===
- Lịch giảng dạy của giảng viên do Admin sắp xếp hợp lý từ Thứ 2 đến Thứ 6, không trùng ca dạy và không trùng phòng học.

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
    cur_sem = _get_current_sem()

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
        f"Học kỳ hiện tại: {_sem_label(cur_sem)}"
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
            Class.semester == cur_sem,
        )
        .all()
    )

    lines.append("")
    lines.append(
        f"=== LỚP ĐANG HỌC ({_sem_label(cur_sem)}) ==="
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
        f"{_sem_label(cur_sem)} ==="
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
    cur_sem = _get_current_sem()

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
        f"Học kỳ hiện tại: {_sem_label(cur_sem)}"
    )

    # =====================================================
    # LỚP ĐANG DẠY
    # =====================================================

    current_classes = (
        Class.query.filter_by(
            lecturer_id=user.id,
            semester=cur_sem,
            status="active"
        ).all()
    )

    lines.append("")
    lines.append(
        f"=== LỚP ĐANG DẠY "
        f"({_sem_label(cur_sem)}) ==="
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