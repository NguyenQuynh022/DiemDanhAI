"""
Tiết học map — chuẩn Việt Nam
HK1: tháng 8 → tháng 12
HK2: tháng 12 → tháng 5
"""
from datetime import time, date

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

def get_all_semesters():
    """
    HK1-YYYY: tháng 8 năm YYYY
    HK2-YYYY: tháng 12 năm YYYY (kết thúc tháng 5 năm YYYY+1)
    Từ HK1-2023 đến học kỳ hiện tại
    """
    now = date.today()
    result = []
    for year in range(2023, now.year + 2):
        # HK1: Aug-Dec of year
        hk1_id = f"HK1-{year}"
        result.append((hk1_id, "Học kỳ 1", str(year), date(year, 8, 1)))
        if now.year == year and now.month < 8:
            return result

        # HK2: Dec of year - May of year+1
        hk2_id = f"HK2-{year}"
        result.append((hk2_id, "Học kỳ 2", str(year), date(year, 12, 1)))
        if now.year == year and now.month < 12:
            return result
        if now.year == year + 1 and now.month <= 5:
            return result

    return result

def get_semester_start(sem_id):
    """Trả về ngày bắt đầu học kỳ (thứ 2 đầu tiên của tháng)"""
    from datetime import timedelta
    parts = sem_id.split('-')
    hk    = parts[0]   # HK1 or HK2
    year  = int(parts[1])
    if hk == 'HK1':
        d = date(year, 8, 1)
    else:
        d = date(year, 12, 1)
    # Lấy thứ 2 đầu tiên
    if d.weekday() != 0:
        d = d + timedelta(days=(7 - d.weekday()) % 7)
    return d
