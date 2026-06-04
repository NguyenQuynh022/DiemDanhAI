from datetime import datetime

def get_all_semesters():
    """Trả về danh sách học kỳ từ HK1-2023 đến học kỳ hiện tại"""
    now = datetime.now()
    current_sem = f"HK1-{now.year}" if now.month <= 6 else f"HK2-{now.year}"
    semesters = []
    for year in range(2023, now.year + 2):
        for hk in ["HK1", "HK2"]:
            s = f"{hk}-{year}"
            semesters.append(s)
            if s == current_sem:
                return semesters
    return semesters

def get_current_semester():
    now = datetime.now()
    return f"HK1-{now.year}" if now.month <= 6 else f"HK2-{now.year}"
