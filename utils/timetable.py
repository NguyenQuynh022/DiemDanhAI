"""
utils/timetable.py — Chuẩn hóa tiết học, lịch năm học & kiểm tra trùng lịch

Quy tắc năm học:
  - Học kỳ 1 (HK1-YYYY): Bắt đầu tháng 8 năm YYYY → Kết thúc tháng 12 năm YYYY
  - Học kỳ 2 (HK2-YYYY): Bắt đầu tháng 2 năm YYYY+1 → Kết thúc tháng 5 năm YYYY+1
  - Lịch học chính khóa: Thứ 2 (day=0) đến Thứ 6 (day=4)
"""
from datetime import time, date, timedelta
import calendar

TIET_MAP = {
    1:  (time(7, 30),  time(8, 20)),
    2:  (time(8, 30),  time(9, 20)),
    3:  (time(9, 30),  time(10, 20)),
    4:  (time(10, 30), time(11, 20)),
    5:  (time(11, 30), time(12, 20)),
    6:  (time(13, 0),  time(13, 50)),
    7:  (time(14, 0),  time(14, 50)),
    8:  (time(15, 0),  time(15, 50)),
    9:  (time(16, 0),  time(16, 50)),
    10: (time(17, 0),  time(17, 50)),
}

WEEKDAY_LABELS = {
    0: 'Thứ 2',
    1: 'Thứ 3',
    2: 'Thứ 4',
    3: 'Thứ 5',
    4: 'Thứ 6',
    5: 'Thứ 7',
    6: 'Chủ nhật',
}


def time_to_tiet(t):
    for tiet, (start, end) in TIET_MAP.items():
        if start <= t <= end:
            return tiet
    for tiet, (start, end) in TIET_MAP.items():
        if t <= start:
            return tiet
    return 1


def tiet_span(start_t, end_t):
    t_start = time_to_tiet(start_t)
    t_end   = time_to_tiet(end_t)
    if t_end < t_start:
        t_end = t_start
    return t_start, max(1, t_end - t_start + 1)


def first_monday(year: int, month: int) -> date:
    """Trả về ngày Thứ Hai đầu tiên của tháng."""
    d = date(year, month, 1)
    if d.weekday() != 0:
        d += timedelta(days=(7 - d.weekday()) % 7)
    return d


def get_semester_bounds(sem_id: str) -> tuple[date, date]:
    """
    Trả về (start_date, end_date) chuẩn của học kỳ:
      - HK1-YYYY: Thứ 2 đầu tiên tháng 8/YYYY -> 31/12/YYYY
      - HK2-YYYY: Thứ 2 đầu tiên tháng 2/(YYYY+1) -> 31/05/(YYYY+1)
    """
    parts = sem_id.split('-')
    hk    = parts[0].upper()
    year  = int(parts[1])

    if hk == 'HK1':
        start_d = first_monday(year, 8)
        end_d   = date(year, 12, 31)
    else:
        next_yr = year + 1
        start_d = first_monday(next_yr, 2)
        last_day = calendar.monthrange(next_yr, 5)[1]
        end_d   = date(next_yr, 5, last_day)

    return start_d, end_d


def get_semester_start(sem_id: str) -> date:
    """Trả về ngày Thứ 2 bắt đầu học kỳ."""
    return get_semester_bounds(sem_id)[0]


def get_semester_end(sem_id: str) -> date:
    """Trả về ngày kết thúc học kỳ."""
    return get_semester_bounds(sem_id)[1]


def get_current_semester_id(ref_date: date | None = None) -> str:
    """
    Xác định mã học kỳ hiện tại theo ngày thực tế:
      - Tháng 8 → Tháng 12 năm Y: HK1-Y (năm học Y - Y+1)
      - Tháng 1 → Tháng 7 năm Y : HK2-(Y-1) (năm học Y-1 - Y, học chính từ tháng 2→5)
    """
    d = ref_date or date.today()
    if d.month >= 8:
        return f"HK1-{d.year}"
    return f"HK2-{d.year - 1}"


def format_semester_label(sem_id: str) -> str:
    parts = sem_id.split('-')
    hk_num = '1' if parts[0] == 'HK1' else '2'
    yr = int(parts[1])
    return f"Học kỳ {hk_num} - {yr}-{yr + 1}"


def format_semester_heading(sem_id: str) -> str:
    """Trả về chuỗi 'Học kỳ 1, năm học 2026 - 2027' giống giao diện chuẩn."""
    parts = sem_id.split('-')
    hk_num = '1' if parts[0].upper() == 'HK1' else '2'
    yr = int(parts[1])
    return f"Học kỳ {hk_num}, năm học {yr} - {yr + 1}"


SEMESTER_TOTAL_WEEKS = 25


def format_class_weeks_csv(cls, session_dates: list[date] | None = None) -> str:
    """
    Trả về chuỗi liệt kê đầy đủ từng tuần học phân cách bằng dấu phẩy (ví dụ: '2,3,5,6,7,8,9,10,11,12,13,14,15')
    đúng chuẩn trang 'THỜI KHÓA BIỂU - DANH SÁCH LỚP HỌC PHẦN'.
    """
    from models.session import Session

    sem_start = get_semester_start(cls.semester)
    if session_dates is None:
        session_dates = [
            s.session_date
            for s in Session.query.filter_by(class_id=cls.id).filter(Session.status != 'cancelled').order_by(Session.session_date).all()
        ]
    if not session_dates:
        return "1,2,3,4,5,6,7,8,9,10,11,12,13,14,15"

    s_dates = sorted(session_dates)
    if s_dates[0] < sem_start:
        base_mon = s_dates[0] - timedelta(days=s_dates[0].weekday())
    else:
        base_mon = sem_start

    weeks = sorted({max(1, ((d - base_mon).days // 7) + 1) for d in s_dates})
    return ",".join(str(w) for w in weeks)


def format_full_tkb_slot(cls) -> str:
    """Trả về chuỗi 'Thứ Hai | Tiết 6→8' đúng chuẩn cột Thời khóa biểu."""
    DAYS_FULL = ['Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy', 'Chủ Nhật']
    info = cls.schedule_info or {}
    if isinstance(info, dict) and info.get('day') is not None:
        d_idx = int(info.get('day', 0))
        t_st  = int(info.get('tiet_start', 1))
        n_t   = int(info.get('num_tiet', 2))
        t_end = min(10, t_st + n_t - 1)
        d_lbl = DAYS_FULL[d_idx] if 0 <= d_idx < len(DAYS_FULL) else 'Thứ Hai'
        return f"{d_lbl} | Tiết {t_st}→{t_end}"
    return "—"


def format_class_weeks_range(cls) -> str:
    """
    Tính chuỗi tuần học thực tế của lớp học phần theo ngày buổi học (ví dụ: '1→17', '2,3,5→17').
    """
    from models.session import Session

    sem_start = get_semester_start(cls.semester)
    sess_dates = [
        s.session_date
        for s in Session.query.filter_by(class_id=cls.id).filter(Session.status != 'cancelled').order_by(Session.session_date).all()
    ]
    if not sess_dates:
        return "1→15"

    # Nếu buổi học nằm ở lịch cũ trước sem_start, lấy mốc Thứ 2 của buổi đầu tiên
    if sess_dates[0] < sem_start:
        base_mon = sess_dates[0] - timedelta(days=sess_dates[0].weekday())
    else:
        base_mon = sem_start

    weeks = sorted({max(1, ((d - base_mon).days // 7) + 1) for d in sess_dates})
    if len(weeks) == 1:
        return str(weeks[0])

    # Gom các đoạn tuần liên tiếp thành 'a→b', tuần lẻ cách quãng nối bằng dấu phẩy (VD: '2,3,5→17')
    ranges = []
    start_w = prev_w = weeks[0]
    for w in weeks[1:]:
        if w == prev_w + 1:
            prev_w = w
        else:
            ranges.append(f"{start_w}→{prev_w}" if prev_w > start_w + 1 else (f"{start_w},{prev_w}" if prev_w == start_w + 1 else str(start_w)))
            start_w = prev_w = w
    ranges.append(f"{start_w}→{prev_w}" if prev_w > start_w + 1 else (f"{start_w},{prev_w}" if prev_w == start_w + 1 else str(start_w)))
    return ",".join(ranges)


def build_semester_weeks_timetables(selected_sem: str, all_sessions_with_cls: list, total_weeks: int = SEMESTER_TOTAL_WEEKS) -> list[dict]:
    """
    Xây dựng danh sách ĐÚNG 25 tuần của học kỳ (Tuần 1 -> Tuần 25) cho chế độ 'Thời khóa biểu Mở rộng':
      - Tuần nào có buổi học sẽ hiển thị ô môn học tương ứng.
      - Tuần nào không có lịch học sẽ hiển thị bảng lưới 10 tiết để trống giống chuẩn.
      - Mỗi phần tử gồm:
        {
          'week_num': int (Tuần 1 .. Tuần 25),
          'week_start': date (Thứ 2),
          'week_end': date (Chủ nhật),
          'timetable': {(day_idx, tiet_start): (sess, cls, span)},
          'occupied': {(day_idx, tiet)},
          'cancelled_list': [(sess, cls), ...],  # Phục vụ mục 'Báo nghỉ' trong tuần đó
        }
    """
    sem_start, sem_end = get_semester_bounds(selected_sem)

    if all_sessions_with_cls:
        min_d = min(s.session_date for s, _ in all_sessions_with_cls)
        max_d = max(s.session_date for s, _ in all_sessions_with_cls)
        if max_d < sem_start or min_d > sem_end:
            first_mon = min_d - timedelta(days=min_d.weekday())
        else:
            first_mon = min(sem_start, min_d - timedelta(days=min_d.weekday()))
    else:
        first_mon = sem_start

    # Gom session theo ngày Thứ 2 đầu tuần để chạy O(N) cực nhanh
    by_week_monday: dict[date, list] = {}
    for sess, cls in all_sessions_with_cls:
        w_mon = sess.session_date - timedelta(days=sess.session_date.weekday())
        by_week_monday.setdefault(w_mon, []).append((sess, cls))

    weeks_data = []
    for w_idx in range(1, total_weeks + 1):
        cur_mon = first_mon + timedelta(weeks=(w_idx - 1))
        w_end   = cur_mon + timedelta(days=6)
        w_items = by_week_monday.get(cur_mon, [])

        tt = {}
        occ = set()
        cancelled_list = []

        for sess, cls in w_items:
            if sess.status == 'cancelled':
                cancelled_list.append((sess, cls))
                continue
            day_idx = sess.session_date.weekday()
            if day_idx >= 7:
                continue
            t_start, span = tiet_span(sess.start_time, sess.end_time)
            if (day_idx, t_start) not in occ:
                tt[(day_idx, t_start)] = (sess, cls, span)
            for t in range(t_start, t_start + span):
                occ.add((day_idx, t))

        weeks_data.append({
            'week_num': w_idx,
            'week_start': cur_mon,
            'week_end': w_end,
            'timetable': tt,
            'occupied': occ,
            'cancelled_list': cancelled_list,
        })

    return weeks_data


def get_all_semesters(include_next: bool = False):
    """
    Trả về danh sách tuple (sem_id, sem_name, str_year, start_date)
    từ HK1-2023 đến học kỳ hiện tại (và +1 kỳ kế tiếp nếu include_next=True để Admin mở đăng ký sớm).
    """
    today  = date.today()
    cur_id = get_current_semester_id(today)
    result = []
    found_current = False

    for year in range(2023, today.year + 2):
        for hk, label in [('HK1', 'Học kỳ 1'), ('HK2', 'Học kỳ 2')]:
            sem_id = f"{hk}-{year}"
            s_start = get_semester_start(sem_id)
            result.append((sem_id, label, str(year), s_start))
            if found_current:
                return result
            if sem_id == cur_id:
                if not include_next:
                    return result
                found_current = True

    return result


def resolve_viewing_week(selected_sem: str, week_param: str | None, today: date | None = None) -> tuple[date, date, int, int]:
    """
    Tính tuần hiển thị cho Thời khóa biểu:
      - Mặc định (khi người dùng chưa bấm chuyển tuần):
        + Nếu ngày hôm nay nằm trong khoảng học kỳ (hoặc là học kỳ hiện tại đang diễn ra):
          mở ngay đúng TUẦN ĐANG HỌC chứa ngày hôm nay (week_offset = 0).
        + Nếu xem học kỳ cũ đã qua hoặc học kỳ tương lai chưa bắt đầu:
          nhảy tới tuần đầu tiên có buổi học thực tế của học kỳ đó (fallback về sem_start).
      - Trả về: (week_start, week_end, week_offset_from_today, academic_week_num)
    """
    today = today or date.today()
    today_monday = today - timedelta(days=today.weekday())
    sem_start, sem_end = get_semester_bounds(selected_sem)

    anchor_monday = sem_start
    try:
        from extensions import db
        from models.session import Session
        from models.class_model import Class
        from sqlalchemy import func
        first_sess_date = (
            db.session.query(func.min(Session.session_date))
            .join(Class, Class.id == Session.class_id)
            .filter(Class.semester == selected_sem, Session.status != 'cancelled')
            .scalar()
        )
        if first_sess_date:
            anchor_monday = first_sess_date - timedelta(days=first_sess_date.weekday())
    except Exception:
        pass

    if week_param is not None and week_param != '':
        try:
            week_offset = int(week_param)
        except ValueError:
            week_offset = 0
    else:
        if sem_start <= today <= sem_end:
            week_offset = 0
        else:
            week_offset = (anchor_monday - today_monday).days // 7

    base_start = anchor_monday if not (sem_start <= today <= sem_end) else sem_start
    # Giới hạn chuyển tuần nằm gọn trong phạm vi Tuần 1 .. Tuần 25 của học kỳ
    min_offset = (base_start - today_monday).days // 7
    max_offset = min_offset + SEMESTER_TOTAL_WEEKS - 1
    week_offset = max(min_offset, min(week_offset, max_offset))

    week_start = today_monday + timedelta(weeks=week_offset)
    week_end   = week_start + timedelta(days=6)
    week_num   = max(1, min(SEMESTER_TOTAL_WEEKS, ((week_start - base_start).days // 7) + 1))
    return week_start, week_end, week_offset, week_num


def schedules_conflict(info_a: dict | None, info_b: dict | None) -> bool:
    """
    Kiểm tra 2 lịch học cố định có trùng Thứ & giao nhau Tiết học hay không.
    schedule_info = {'day': 0..4, 'tiet_start': 1..10, 'num_tiet': 2..3, 'credits': 2}
    """
    if not info_a or not info_b:
        return False
    day_a = info_a.get('day')
    day_b = info_b.get('day')
    if day_a is None or day_b is None or int(day_a) != int(day_b):
        return False

    st_a  = int(info_a.get('tiet_start', 1))
    end_a = st_a + int(info_a.get('num_tiet', 2)) - 1

    st_b  = int(info_b.get('tiet_start', 1))
    end_b = st_b + int(info_b.get('num_tiet', 2)) - 1

    return not (end_a < st_b or end_b < st_a)


def generate_sessions_for_class(cls, today: date | None = None):
    """
    Sinh toàn bộ các buổi học (Session) cho lớp học phần xuyên suốt học kỳ:
      - HK1: tháng 8 -> tháng 12
      - HK2: tháng 2 -> tháng 5
      - Chỉ học Thứ 2 .. Thứ 6 (day 0..4)
    """
    from models.session import Session

    today = today or date.today()
    info = cls.schedule_info or {}
    weekday    = int(info.get('day', 0))
    tiet_start = int(info.get('tiet_start', 1))
    num_tiet   = int(info.get('num_tiet', 2))
    tiet_end   = min(10, tiet_start + num_tiet - 1)

    start_t = TIET_MAP[tiet_start][0]
    end_t   = TIET_MAP[tiet_end][1]
    sem_start, sem_end = get_semester_bounds(cls.semester)

    sessions = []
    cur_monday = sem_start
    while True:
        sess_date = cur_monday + timedelta(days=weekday)
        if sess_date > sem_end:
            break
        if 0 <= sess_date.weekday() <= 4:
            if cls.status == 'closed' or sess_date < today:
                st = 'completed'
            elif sess_date == today:
                st = 'ongoing'
            else:
                st = 'scheduled'
            sessions.append(Session(
                class_id=cls.id,
                session_date=sess_date,
                start_time=start_t,
                end_time=end_t,
                room=cls.room,
                status=st,
            ))
        cur_monday += timedelta(weeks=1)
    return sessions
