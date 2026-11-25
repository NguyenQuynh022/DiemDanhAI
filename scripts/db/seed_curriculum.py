"""
scripts/db/seed_curriculum.py — Seed chương trình đào tạo 6 học kỳ
Chạy: python scripts/db/seed_curriculum.py
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import random
import unicodedata
from collections import defaultdict
from datetime import date, time, timedelta

from app import create_app
from extensions import db
from models.attendance  import Attendance
from models.class_model import Class
from models.enrollment  import Enrollment
from models.grade       import Grade
from models.session     import Session
from models.user        import User

app = create_app()

# ═══════════════════════════════════════════════════════════════════════════════
# HELPER — tên tiếng Việt → username ASCII
# ═══════════════════════════════════════════════════════════════════════════════

def vn_slug(name: str) -> str:
    name = name.replace('đ', 'd').replace('Đ', 'd')
    nfkd = unicodedata.normalize('NFKD', name)
    return nfkd.encode('ascii', 'ignore').decode('ascii').lower().replace(' ', '.')


# ═══════════════════════════════════════════════════════════════════════════════
# A. GV DATA — 12 giảng viên
# ═══════════════════════════════════════════════════════════════════════════════

GV_DATA: list[tuple] = [
    ("gv_nguyenvan",  "Nguyễn Văn An",    "nguyenvanan@edu.vn",  "0901234567", "TS CNTT, chuyên AI và Lập trình"),
    ("gv_lethithu",   "Lê Thị Thu",       "lethithu@edu.vn",     "0912345678", "ThS, chuyên CSDL và Web"),
    ("gv_tranvanb",   "Trần Văn Bình",    "tranvanbinh@edu.vn",  "0923456789", "TS Toán ứng dụng và Vật lý"),
    ("gv_phamlan",    "Phạm Thị Lan",     "phamlan@edu.vn",      "0934567890", "ThS Mạng máy tính và Hệ thống"),
    ("gv_hoangnam",   "Hoàng Văn Nam",    "hoangnam@edu.vn",     "0945678901", "ThS Công nghệ phần mềm"),
    ("gv_vuthanhh",   "Vũ Thanh Hà",      "vuthanhha@edu.vn",    "0956789012", "ThS Tiếng Anh chuyên ngành IT"),
    ("gv_ngoclinh",   "Nguyễn Ngọc Linh", "ngoclinh@edu.vn",     "0967890123", "TS Kiến trúc máy tính và HĐH"),
    ("gv_minhquang",  "Trần Minh Quang",  "minhquang@edu.vn",    "0978901234", "ThS Lập trình di động và Mạng"),
    ("gv_thuyhoa",    "Lê Thùy Hoa",      "thuyhoa@edu.vn",      "0989012345", "ThS Đồ án và Thực tập"),
    ("gv_anhduc",     "Phạm Anh Đức",     "anhduc@edu.vn",       "0990123456", "ThS Lý luận Mác-Lênin"),
    ("gv_kimchi",     "Nguyễn Kim Chi",   "kimchi@edu.vn",       "0901234568", "ThS Giải tích và Đại số"),
    ("gv_thanhtam",   "Lê Thanh Tâm",     "thanhtam@edu.vn",     "0912345679", "ThS Xác suất và Toán rời rạc"),
]

# ═══════════════════════════════════════════════════════════════════════════════
# B. CURRICULUM
# ═══════════════════════════════════════════════════════════════════════════════

CURRICULUM: dict[str, list[tuple]] = {
    "HK1-2023": [
        ("Tiếng Anh 1",                "AE101", "P.A10", [5, 4, 3, 1],    3),
        ("Lập trình cơ bản",           "CS101", "P.B20", [0, 4, 6, 7],    3),
        ("Lập trình hướng đối tượng",  "CS102", "P.B20", [1, 3, 4, 6],    3),
        ("Cơ sở dữ liệu",              "CS201", "P.B30", [1, 3, 6, 7],    3),
        ("Tiếng Anh chuyên ngành 1 IT","AE201", "P.A10", [5, 4, 3, 2],    2),
        ("Giải tích 1",                "MA101", "K.A10", [10, 11, 2, 3],  2),
    ],
    "HK2-2023": [
        ("Đại số tuyến tính",                 "MA102",  "K.A10", [10, 11, 2, 3],   3),
        ("Khởi nghiệp và đổi mới sáng tạo",  "EI101",  "P.C10", [4, 8, 7, 2],     2),
        ("Tiếng Anh 2",                       "AE102",  "P.A10", [5, 4, 3, 9],     3),
        ("Tiếng Anh chuyên ngành 2",          "AE202",  "P.A10", [5, 3, 4, 9],     2),
        ("Lập trình Java",                    "CS203",  "P.B20", [0, 4, 7, 6],     3),
        ("Nhập môn ngành và kỹ năng mềm IT",  "IT101",  "P.C20", [4, 8, 7, 2],     2),
        ("Cấu trúc dữ liệu và giải thuật",    "CS204",  "P.B30", [1, 6, 0, 2],     3),
        ("Đồ án cơ sở 1",                     "PRJ101", "Lab.",  [8, 3, 2, 6],     2),
        ("Thiết kế web",                      "CS301",  "P.B20", [7, 1, 6, 2],     3),
    ],
    "HK1-2024": [
        ("Vật lý",                          "PH101",  "K.A10", [2, 10, 11, 9],   3),
        ("Giải tích 2",                     "MA103",  "K.A10", [10, 11, 2, 9],   3),
        ("Kiến trúc máy tính",              "CS302",  "P.B30", [6, 3, 7, 0],     3),
        ("Tiếng Anh 3",                     "AE103",  "P.A10", [5, 4, 3, 9],     2),
        ("Nguyên lý hệ điều hành",          "CS303",  "P.B30", [6, 7, 3, 0],     3),
        ("Phân tích và thiết kế hệ thống",  "CS401",  "P.B30", [3, 4, 1, 0],     3),
        ("Tiếng Anh nâng cao 1",            "AE301",  "P.A10", [5, 4, 3, 9],     2),
        ("Công nghệ và lập trình web",      "CS402",  "Lab.",  [7, 4, 0, 1],     3),
        ("Đồ án cơ sở 2",                   "PRJ201", "Lab.",  [8, 2, 9, 10],    2),
    ],
    "HK2-2024": [
        ("Xác suất thống kê",          "MA201",  "K.A10", [11, 10, 2, 9],   3),
        ("Vi điều khiển",              "CS403",  "Lab.",  [6, 7, 3, 0],     3),
        ("Tiếng Anh nâng cao 2",       "AE302",  "P.A10", [5, 4, 3, 9],     2),
        ("Mạng máy tính",              "CS404",  "P.B30", [3, 6, 7, 0],     3),
        ("Toán rời rạc",               "MA202",  "K.A10", [11, 10, 2, 9],   3),
        ("Công nghệ phần mềm",         "CS501",  "P.B30", [4, 3, 0, 1],     2),
        ("Chuyên đề 1 (IT)",           "IT401",  "P.C30", [0, 4, 1, 2],     2),
        ("Lập trình di động",          "CS502",  "Lab.",  [7, 4, 0, 2],     3),
        ("Đồ án cơ sở 3 IT",           "PRJ301", "Lab.",  [8, 2, 9, 10],    2),
    ],
    "HK1-2025": [
        ("Lập trình mạng",         "CS503",  "P.B30", [7, 3, 6, 4],     3),
        ("Kho dữ liệu",            "CS601",  "P.B30", [2, 1, 0, 3],     3),
        ("Triết học Mác-Lênin",    "PL101",  "K.C10", [9, 10, 11, 2],   2),
        ("Pháp luật đại cương",    "PL201",  "K.C10", [9, 10, 11, 2],   2),
        ("Trí tuệ nhân tạo",       "CS602",  "Lab.",  [0, 1, 6, 7],     3),
        ("Thực tập thực tế (IT)",  "IT501",  "Lab.",  [8, 3, 7, 2],     2),
        ("Đồ án cơ sở 4 IT",       "PRJ401", "Lab.",  [8, 3, 2, 9],     3),
    ],
    "HK2-2025": [
        # 8 môn × 7 lớp | T2-T7 | Jan→Jun/2026 | skip tháng 2 (Tết)
        ("Kinh tế chính trị Mác-Lênin",             "PL102",  "K.C10", [9, 10, 11, 2],   2),
        ("Lịch sử Đảng Cộng sản Việt Nam",          "PL103",  "K.C20", [9, 10, 11, 2],   2),
        ("Tư tưởng Hồ Chí Minh",                    "PL104",  "K.C10", [9, 10, 11, 2],   2),
        ("Học sâu",                                  "CS701",  "V.A21", [0, 1, 6, 7],     3),
        ("Phân tích và thiết kế giải thuật",         "CS702",  "K.A10", [3, 1, 4, 0],     2),
        ("Đảm bảo chất lượng và kiểm thử phần mềm", "CS703",  "V.A20", [4, 1, 0, 3],     3),
        ("Chuyên đề 2 (IT)",                         "IT601",  "K.A11", [2, 6, 7, 3],     3),
        ("Đồ án chuyên ngành 1 (IT)",                "PRJ501", "Lab.",  [8, 4, 11, 3],    2),
    ],
}

# ═══════════════════════════════════════════════════════════════════════════════
# C. CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

N_CLASSES_PER_SUBJECT          = 7
MAX_CLASSES_PER_GV_PER_SUBJECT = 3
GV_MAX_WEEKLY   = 10
GV_MAX_SUBJECTS = 4
GV_MIN_SUBJECTS = 3

SEM_START: dict[str, date] = {
    "HK1-2023": date(2023,  9,  4),
    "HK2-2023": date(2024,  1,  8),
    "HK1-2024": date(2024,  9,  2),
    "HK2-2024": date(2025,  1,  6),
    "HK1-2025": date(2025,  9,  1),
    "HK2-2025": date(2026,  1,  5),   # Thứ 2, 05/01/2026
}

CURRENT_SEM      = "HK2-2025"
DEFAULT_SESSIONS = 15
SEM_TOTAL_SESSIONS: dict[str, int] = {
    # 22 buổi: Jan(4) + Mar(5) + Apr(4) + May(5) + Jun(4) = 22 → hết 30/6/2026
    "HK2-2025": 22,
}
HK2_2025_SKIP_MONTHS: set[int] = {2}
HK2_2025_END: date = date(2026, 6, 30)

TIET_TIME: dict[int, tuple[time, time]] = {
    1:  (time(7,  30), time(8,  20)),
    2:  (time(8,  30), time(9,  20)),
    3:  (time(9,  30), time(10, 20)),
    4:  (time(10, 30), time(11, 20)),
    5:  (time(11, 30), time(12, 20)),
    6:  (time(13,  0), time(13, 50)),
    7:  (time(14,  0), time(14, 50)),
    8:  (time(15,  0), time(15, 50)),
    9:  (time(16,  0), time(16, 50)),
    10: (time(17,  0), time(17, 50)),
}

CREDITS: dict[str, int] = {
    "PRJ": 4, "AE": 3, "CS": 3, "MA": 3,
    "PH":  2, "EI": 2, "IT": 3, "PL":  2,
}

# WEEKDAYS 0=T2 .. 5=T7 (KHÔNG bao giờ có 6=CN)
TIET_BLOCKS: list[int]  = [1, 3, 6, 8]
WEEKDAYS:    list[int]  = list(range(6))   # 0=T2 .. 5=T7
ALL_SLOTS: list[tuple]  = [
    (wd, ts) for wd in WEEKDAYS for ts in TIET_BLOCKS
]   # 24 slots, max wd = 5 (T7)

DAY_NAMES = ["T2", "T3", "T4", "T5", "T6", "T7"]

# ═══════════════════════════════════════════════════════════════════════════════
# D. SV DATA — 30 sinh viên  (username = vn_slug(tên))
# ═══════════════════════════════════════════════════════════════════════════════

SV_DATA = [
    ("Nguyễn Văn An",    "23ITB001", "sv001@edu.vn", "0900000001"),
    ("Trần Thị Bình",    "23ITB002", "sv002@edu.vn", "0900000002"),
    ("Lê Văn Cường",     "23ITB003", "sv003@edu.vn", "0900000003"),
    ("Phạm Thị Dung",    "23ITB004", "sv004@edu.vn", "0900000004"),
    ("Hoàng Văn Em",     "23ITB005", "sv005@edu.vn", "0900000005"),
    ("Vũ Thị Phương",    "23ITB006", "sv006@edu.vn", "0900000006"),
    ("Đặng Văn Giang",   "23ITB007", "sv007@edu.vn", "0900000007"),
    ("Bùi Thị Hoa",      "23ITB008", "sv008@edu.vn", "0900000008"),
    ("Đỗ Văn Inh",       "23ITB009", "sv009@edu.vn", "0900000009"),
    ("Ngô Thị Kim",      "23ITB010", "sv010@edu.vn", "0900000010"),
    ("Lý Văn Long",      "23AI011",  "sv011@edu.vn", "0900000011"),
    ("Mai Thị Mỹ",       "23AI012",  "sv012@edu.vn", "0900000012"),
    ("Tô Văn Nam",       "23AI013",  "sv013@edu.vn", "0900000013"),
    ("Huỳnh Thị Oanh",   "23AI014",  "sv014@edu.vn", "0900000014"),
    ("Trịnh Văn Phúc",   "23AI015",  "sv015@edu.vn", "0900000015"),
    ("Cao Thị Quỳnh",    "23AI016",  "sv016@edu.vn", "0900000016"),
    ("Đinh Văn Rồng",    "23AI017",  "sv017@edu.vn", "0900000017"),
    ("Lưu Thị Sen",      "23AI018",  "sv018@edu.vn", "0900000018"),
    ("Phan Văn Tuấn",    "23AI019",  "sv019@edu.vn", "0900000019"),
    ("Kiều Thị Uyên",    "23AI020",  "sv020@edu.vn", "0900000020"),
    ("Hà Văn Vinh",      "23SE021",  "sv021@edu.vn", "0900000021"),
    ("Lã Thị Xuân",      "23SE022",  "sv022@edu.vn", "0900000022"),
    ("Mạc Văn Yên",      "23SE023",  "sv023@edu.vn", "0900000023"),
    ("Nông Thị Zara",    "23SE024",  "sv024@edu.vn", "0900000024"),
    ("Ông Văn Anh",      "23SE025",  "sv025@edu.vn", "0900000025"),
    ("Quách Thị Bảo",    "23CE026",  "sv026@edu.vn", "0900000026"),
    ("Rạng Văn Châu",    "23CE027",  "sv027@edu.vn", "0900000027"),
    ("Sầm Thị Diệu",     "23CE028",  "sv028@edu.vn", "0900000028"),
    ("Tăng Văn Đạt",     "23CE029",  "sv029@edu.vn", "0900000029"),
    ("Ung Thị Em",       "23CE030",  "sv030@edu.vn", "0900000030"),
]

# ═══════════════════════════════════════════════════════════════════════════════
# E. SCHEDULER ENGINE — v3  (4-level priority: GV + cls_num spread)
# ═══════════════════════════════════════════════════════════════════════════════

class SchedulerError(Exception):
    pass


class SemesterScheduler:
    """
    Scheduler v3: 4-level slot priority để đảm bảo:
      1. Mỗi NHÓM SV (cls_num 1-7) có lịch trải đều T2-T7 qua các môn.
      2. Mỗi GV cá nhân cũng trải đều T2-T7, không bị dồn vào 2-3 ngày.

    Priority khi chọn slot (wd, ts) cho GV g của lớp cls_num:
      P1: wd chưa dùng cho cls_num  AND  wd chưa dùng cho GV g   ← tốt nhất
      P2: wd chưa dùng cho cls_num  AND  wd đã dùng cho GV g
      P3: wd đã dùng cho cls_num    AND  wd chưa dùng cho GV g
      P4: wd đã dùng cho cls_num    AND  wd đã dùng cho GV g     ← fallback
    """

    def __init__(self, sem_id: str) -> None:
        self.sem_id          = sem_id
        self.gv_workload:    dict[int, int] = defaultdict(int)
        self.gv_subjects:    dict[int, set] = defaultdict(set)
        self.gv_used_slots:  dict[int, set] = defaultdict(set)
        self.room_used:      set            = set()
        self.cls_pos_wd_used: dict[int, set] = defaultdict(set)  # spread nhóm SV
        self.conflicts_prevented = 0

    # ── helpers ──────────────────────────────────────────────────────────────

    def _can_take_subject(self, gv: int, code: str) -> bool:
        already = code in self.gv_subjects[gv]
        return ((len(self.gv_subjects[gv]) < GV_MAX_SUBJECTS or already)
                and self.gv_workload[gv] < GV_MAX_WEEKLY)

    def _build_slot_order(
        self,
        gv:          int,
        cls_num:     int,
        tmp_gv_wd:   set,   # weekdays GV đã dùng trong batch này
        tmp_cls_wd:  set,   # weekdays cls_num đã dùng trong batch này
    ) -> list[tuple]:
        """
        4-level priority:
          P1: new day for BOTH cls_num AND GV   ← lý tưởng nhất
          P2: new day for cls_num, used by GV
          P3: used day for cls_num, new day for GV
          P4: fallback (used by both)
        """
        committed_cls_wd = self.cls_pos_wd_used[cls_num]
        committed_gv_wd  = {s[0] for s in self.gv_used_slots[gv]}

        cls_used = committed_cls_wd | tmp_cls_wd
        gv_used  = committed_gv_wd  | tmp_gv_wd

        p1, p2, p3, p4 = [], [], [], []
        for wd, ts in ALL_SLOTS:
            cls_fresh = wd not in cls_used
            gv_fresh  = wd not in gv_used
            if   cls_fresh and gv_fresh:  p1.append((wd, ts))
            elif cls_fresh and not gv_fresh: p2.append((wd, ts))
            elif not cls_fresh and gv_fresh: p3.append((wd, ts))
            else:                            p4.append((wd, ts))
        return p1 + p2 + p3 + p4

    # ── public API ────────────────────────────────────────────────────────────

    def assign_subject(
        self,
        name:         str,
        code:         str,
        base_room:    str,
        eligible_gvs: list[int],
        num_tiet:     int,
    ) -> list[tuple]:
        n     = N_CLASSES_PER_SUBJECT
        rooms = [f"{base_room}{i}" for i in range(1, n + 1)]

        # ── Bước 1: Plan GV assignment ────────────────────────────────────────
        eligible_sorted = sorted(
            eligible_gvs,
            key=lambda g: (self.gv_workload[g], len(self.gv_subjects[g]))
        )
        plan: list[tuple[int, int]] = []
        cls_per_gv: dict[int, int]  = defaultdict(int)

        for cls_num in range(1, n + 1):
            assigned = False
            for gv in eligible_sorted:
                if (self._can_take_subject(gv, code)
                        and cls_per_gv[gv] < MAX_CLASSES_PER_GV_PER_SUBJECT):
                    plan.append((gv, cls_num))
                    cls_per_gv[gv] += 1
                    assigned = True
                    eligible_sorted = sorted(
                        eligible_gvs,
                        key=lambda g: (self.gv_workload[g] + cls_per_gv[g],
                                       len(self.gv_subjects[g]))
                    )
                    break
            if not assigned:
                raise SchedulerError(
                    f"Môn {code}: không assign được lớp {cls_num} "
                    f"(eligible={eligible_gvs}, "
                    f"workloads={dict((g, self.gv_workload[g]) for g in eligible_gvs)})"
                )

        # ── Bước 2: Find slot — 4-level priority ──────────────────────────────
        result:        list[tuple]    = []
        tmp_gv_slots:  dict[int, set] = defaultdict(set)   # (wd,ts) per GV
        tmp_gv_wd:     dict[int, set] = defaultdict(set)   # weekdays per GV
        tmp_room_used: set            = set()
        tmp_cls_wd:    dict[int, set] = defaultdict(set)   # weekdays per cls_num

        for gv, cls_num in plan:
            room         = rooms[cls_num - 1]
            slot_order   = self._build_slot_order(
                gv, cls_num, tmp_gv_wd[gv], tmp_cls_wd[cls_num]
            )

            found = False
            for wd, ts in slot_order:
                slot     = (wd, ts)
                room_key = (room, wd, ts)

                if slot in self.gv_used_slots[gv]:   continue
                if slot in tmp_gv_slots[gv]:          continue
                if room_key in self.room_used:
                    self.conflicts_prevented += 1;    continue
                if room_key in tmp_room_used:          continue

                tmp_gv_slots[gv].add(slot)
                tmp_gv_wd[gv].add(wd)
                tmp_room_used.add(room_key)
                tmp_cls_wd[cls_num].add(wd)
                result.append((gv, f"{code}-{cls_num:02d}", room, wd, ts))
                found = True
                break

            if not found:
                raise SchedulerError(
                    f"Môn {code} lớp {cls_num:02d}: GV{gv} [{GV_DATA[gv][1]}] "
                    f"hết slot (room={room})"
                )

        # ── Commit ────────────────────────────────────────────────────────────
        for gv, class_name, room, wd, ts in result:
            self.gv_used_slots[gv].add((wd, ts))
            self.room_used.add((room, wd, ts))
            self.gv_workload[gv] += 1
            self.gv_subjects[gv].add(code)
            cls_num_i = int(class_name.split("-")[-1])
            self.cls_pos_wd_used[cls_num_i].add(wd)

        return result

    def summary(self) -> dict:
        return {
            "gv_workload"  : dict(self.gv_workload),
            "gv_subjects"  : {g: len(s) for g, s in self.gv_subjects.items()},
            "gv_slots"     : {g: sorted(s) for g, s in self.gv_used_slots.items()},
            "cls_pos_wd"   : {k: sorted(v) for k, v in self.cls_pos_wd_used.items()},
            "conflicts_prev": self.conflicts_prevented,
        }

    def gv_day_spread(self, gv: int) -> list[str]:
        """Trả về danh sách ngày trong tuần GV này có lịch."""
        days = sorted({s[0] for s in self.gv_used_slots[gv]})
        return [DAY_NAMES[d] for d in days]


# ═══════════════════════════════════════════════════════════════════════════════
# F. HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def get_credits(code: str) -> int:
    for prefix, c in CREDITS.items():
        if code.startswith(prefix):
            return c
    return 3


def build_sessions(
    cls_id: int, sem_id: str, sem_start: date,
    weekday: int, tiet_start: int, num_tiet: int, room: str,
) -> list[tuple]:
    """
    Tạo buổi học.  weekday: 0=T2..5=T7 (KHÔNG bao giờ là 6=CN).
    HK2-2025: skip tháng 2, cap 30/06/2026, target 22 buổi.
    """
    n_sess  = SEM_TOTAL_SESSIONS.get(sem_id, DEFAULT_SESSIONS)
    start_t = TIET_TIME[tiet_start][0]
    end_t   = TIET_TIME[min(tiet_start + num_tiet - 1, 10)][1]

    # Đảm bảo weekday không phải CN
    assert 0 <= weekday <= 5, f"weekday={weekday} phải trong [0..5]"

    result: list[tuple] = []
    cnt = woff = 0
    while cnt < n_sess:
        sess_date = sem_start + timedelta(weeks=woff) + timedelta(days=weekday)
        woff += 1
        if woff > 60:
            break
        # Safety: bỏ qua nếu vô tình ra CN (không nên xảy ra)
        if sess_date.weekday() == 6:
            continue
        if sem_id == CURRENT_SEM and sess_date.month in HK2_2025_SKIP_MONTHS:
            continue
        if sem_id == CURRENT_SEM and sess_date > HK2_2025_END:
            break
        s = Session(class_id=cls_id, session_date=sess_date,
                    start_time=start_t, end_time=end_t,
                    room=room, status="scheduled")
        result.append((s, sess_date))
        cnt += 1
    return result


def session_status(sd: date, past_sem: bool, today: date) -> str:
    if past_sem:    return "completed"
    if sd > today:  return "scheduled"
    if sd == today: return "ongoing"
    return "completed"


# ═══════════════════════════════════════════════════════════════════════════════
# G. PRE-RUN VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def pre_validate() -> bool:
    print("\n" + "═" * 62)
    print("  PRE-RUN VALIDATION")
    print("═" * 62)
    ok = True

    for sem_id, rows in CURRICULUM.items():
        for name, code, room, eligible, ntiet in rows:
            if len(eligible) < 3:
                print(f"  ❌ {sem_id}/{code}: chỉ {len(eligible)} GV (cần ≥3)"); ok = False
            for gv in eligible:
                if gv >= len(GV_DATA):
                    print(f"  ❌ {sem_id}/{code}: GV idx {gv} ngoài range"); ok = False
        codes = [r[1] for r in rows]; seen: set[str] = set()
        for c in codes:
            if c in seen:
                print(f"  ❌ {sem_id}: môn {c} duplicate"); ok = False
            seen.add(c)

    print("  Dry-run scheduler 6 kỳ + kiểm tra GV day-spread...")
    for sem_id, rows in CURRICULUM.items():
        sched = SemesterScheduler(sem_id)
        for name, code, base_room, eligible, num_tiet in rows:
            try:
                sched.assign_subject(name, code, base_room, eligible, num_tiet)
            except SchedulerError as e:
                print(f"  ❌ DRY-RUN [{sem_id}/{code}]: {e}"); ok = False

        if sem_id == CURRENT_SEM:
            summ = sched.summary()
            # Kiểm tra GV spread
            gv_spread_issues = []
            for gv, slots in summ["gv_slots"].items():
                days = sorted({s[0] for s in slots})
                if len(days) < 3:
                    gv_spread_issues.append(f"GV{gv}({GV_DATA[gv][1][:10]}): {[DAY_NAMES[d] for d in days]}")
            if gv_spread_issues:
                print(f"  ⚠️  HK2-2025 GV spread <3 ngày: {gv_spread_issues}")
            else:
                print(f"  ✅ HK2-2025 mọi GV đều có lịch ≥3 ngày khác nhau/tuần")

            # Kiểm tra không có weekday=6 (CN)
            all_wds = {s[0] for slots in sched.gv_used_slots.values() for s in slots}
            if 6 in all_wds:
                print(f"  ❌ HK2-2025: có weekday=6 (CN) trong dữ liệu!"); ok = False
            else:
                print(f"  ✅ HK2-2025: không có weekday=6 (CN) — max={max(all_wds) if all_wds else '?'}")

    if ok:
        print("  ✅ Tất cả 6 kỳ dry-run OK")
    return ok


# ═══════════════════════════════════════════════════════════════════════════════
# H. POST-RUN VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def post_validate(
    schedulers:       dict[str, SemesterScheduler],
    hk2_cls_sessions: dict[int, list[date]],
    sv_course_cls:    dict,
    total_cls: int, total_sess: int, total_att: int, total_grades: int,
) -> None:
    print("\n" + "═" * 62)
    print("  POST-RUN VALIDATION")
    print("═" * 62)

    subj_ok = load_ok = True
    for sem_id, sched in schedulers.items():
        for gv, s in sched.gv_subjects.items():
            if len(s) > GV_MAX_SUBJECTS:
                print(f"  ❌ {sem_id} GV{gv}: {len(s)} môn > {GV_MAX_SUBJECTS}"); subj_ok = False
        for gv, l in sched.gv_workload.items():
            if l > GV_MAX_WEEKLY:
                print(f"  ❌ {sem_id} GV{gv}: {l} lớp > {GV_MAX_WEEKLY}"); load_ok = False
    print(f"  {'✅' if subj_ok else '❌'} Max {GV_MAX_SUBJECTS} môn/kỳ/GV")
    print(f"  {'✅' if load_ok else '❌'} Max {GV_MAX_WEEKLY} lớp/tuần/GV")
    print("  ✅ Không slot/room conflict (enforced by set)")

    sv_ok = True
    for sv_id, code_cls in sv_course_cls.items():
        for code, cls_list in code_cls.items():
            if len(cls_list) > 1:
                print(f"  ❌ SV{sv_id} thuộc {len(cls_list)} lớp {code}"); sv_ok = False
    print(f"  {'✅' if sv_ok else '❌'} 1 SV/1 lớp/môn")

    hk2_dates = [d for dates in hk2_cls_sessions.values() for d in dates]
    if hk2_dates:
        months   = sorted(set(d.month for d in hk2_dates))
        max_date = max(hk2_dates)
        print(f"  {'✅' if 2 not in months else '❌'} HK2-2025 không có buổi tháng 2")
        print(f"  {'✅' if max_date.month >= 6 else '❌'} HK2-2025 có lịch tới tháng 6 (latest={max_date})")
        print(f"  {'✅' if max_date <= HK2_2025_END else '❌'} HK2-2025 không vượt {HK2_2025_END}")
        # Không được có CN
        has_sunday = any(d.weekday() == 6 for d in hk2_dates)
        print(f"  {'❌ CÓ buổi CN!' if has_sunday else '✅ Không có buổi CN'}")

    # GV day-spread cho HK2-2025
    hk2_sched = schedulers.get(CURRENT_SEM)
    if hk2_sched:
        min_days = min(
            len({s[0] for s in slots})
            for slots in hk2_sched.gv_used_slots.values()
            if slots
        ) if hk2_sched.gv_used_slots else 0
        print(f"  {'✅' if min_days >= 3 else '❌'} GV spread: mỗi GV có lịch ≥3 ngày/tuần (min={min_days})")

    n_target = SEM_TOTAL_SESSIONS[CURRENT_SEM]
    too_few  = sum(1 for d in hk2_cls_sessions.values() if len(d) < n_target - 2)
    print(f"  {'✅' if too_few == 0 else '❌'} Mỗi lớp HK2-2025 ≥{n_target-2} buổi"
          + (f" — {too_few} lớp thiếu" if too_few else ""))

    print("\n" + "═" * 62)
    print("  OUTPUT SUMMARY")
    print("═" * 62)
    print(f"  Tổng lớp      : {total_cls}")
    print(f"  Tổng buổi     : {total_sess}")
    print(f"  Tổng att      : {total_att}")
    print(f"  Tổng grades   : {total_grades}")
    if hk2_dates:
        print(f"  HK2-2025 sessions: {len(hk2_dates)}")
        print(f"  Latest session   : {max_date}")
        print(f"  Tháng HK2-2025   : {months}")
    print(f"  Conflicts blocked: {sum(s.conflicts_prevented for s in schedulers.values())}")


# ═══════════════════════════════════════════════════════════════════════════════
# I. MAIN SEED
# ═══════════════════════════════════════════════════════════════════════════════

if not pre_validate():
    print("\n❌ Pre-validation thất bại — dừng lại.")
    exit(1)

with app.app_context():
    today = date.today()
    random.seed(42)

    db.session.execute(db.text("SET FOREIGN_KEY_CHECKS=0"))
    for tbl in ["audit_logs", "notifications", "attendance", "face_data",
                "grades", "enrollments", "sessions", "classes", "users"]:
        db.session.execute(db.text(f"DELETE FROM `{tbl}`"))
    db.session.execute(db.text("SET FOREIGN_KEY_CHECKS=1"))
    db.session.commit()
    print("\n✅ Đã xóa dữ liệu cũ")

    admin = User(username="admin", full_name="Quản trị viên",
                 role="admin", email="admin@edu.vn", status="active")
    admin.set_password("admin123")
    db.session.add(admin)

    gv_objs: list[User] = []
    for uname, fname, email, phone, bio in GV_DATA:
        u = User(username=uname, full_name=fname, role="lecturer",
                 email=email, phone=phone, bio=bio, status="active")
        u.set_password("gv123456")
        db.session.add(u)
        gv_objs.append(u)

    sv_objs: list[User] = []
    for fname, scode, email, phone in SV_DATA:
        u = User(username=vn_slug(fname), full_name=fname, role="student",
                 student_code=scode, email=email, phone=phone, status="active")
        u.set_password("sv123456")
        db.session.add(u)
        sv_objs.append(u)

    db.session.commit()
    print(f"✅ Tạo 1 admin + {len(gv_objs)} GV + {len(sv_objs)} SV")
    for sv in sv_objs[:4]:
        print(f"   {sv.username:30s} ← {sv.full_name}")

    total_cls = total_sess = total_att = total_grades = 0
    schedulers:       dict[str, SemesterScheduler] = {}
    hk2_cls_sessions: dict[int, list[date]]        = {}
    hk2_class_info:   list[tuple]                  = []
    sv_course_cls = defaultdict(lambda: defaultdict(list))
    gv_sample: dict[int, dict] = {}
    sv_sample:  dict[int, list] = {}

    for sem_id, subjects in CURRICULUM.items():
        sem_start  = SEM_START[sem_id]
        cls_status = "active" if sem_id == CURRENT_SEM else "closed"
        past_sem   = sem_id != CURRENT_SEM
        n_sessions = SEM_TOTAL_SESSIONS.get(sem_id, DEFAULT_SESSIONS)

        print(f"\n{'─'*55}")
        print(f"📚 {sem_id} | {len(subjects)} môn × {N_CLASSES_PER_SUBJECT} lớp "
              f"| {n_sessions} buổi | {'đang học' if not past_sem else 'kết thúc'}")

        sched = SemesterScheduler(sem_id)
        schedulers[sem_id] = sched

        sv_shuffled = sv_objs.copy()
        random.shuffle(sv_shuffled)
        sv_groups: list[list[User]] = [
            sv_shuffled[0:5],  sv_shuffled[5:10],
            sv_shuffled[10:14], sv_shuffled[14:18],
            sv_shuffled[18:22], sv_shuffled[22:26],
            sv_shuffled[26:30],
        ]

        for name, code, base_room, eligible_gvs, num_tiet in subjects:
            credits = get_credits(code)
            try:
                assignments = sched.assign_subject(name, code, base_room, eligible_gvs, num_tiet)
            except SchedulerError as e:
                print(f"\n  ❌ SCHEDULER ERROR [{sem_id}/{code}]: {e}")
                exit(1)

            for i, (gv_idx, class_name, room, weekday, tiet_start) in enumerate(assignments):
                lect     = gv_objs[gv_idx]
                sv_group = sv_groups[i]

                cls = Class(
                    class_name    = class_name,
                    course_name   = name,
                    course_code   = code,
                    lecturer_id   = lect.id,
                    semester      = sem_id,
                    room          = room,
                    schedule_info = {
                        "day": weekday,          # 0=T2..5=T7, KHÔNG bao giờ 6
                        "tiet_start": tiet_start,
                        "num_tiet": num_tiet,
                        "credits": credits,
                    },
                    formula_config = {
                        "attendance": 0.10, "assignment": 0.10,
                        "midterm":    0.30, "final":      0.50,
                    },
                    status=cls_status,
                )
                db.session.add(cls)
                db.session.flush()
                total_cls += 1

                for sv in sv_group:
                    db.session.add(Enrollment(
                        student_id=sv.id, class_id=cls.id,
                        enrolled_by=lect.id, status="enrolled"))
                    sv_course_cls[sv.id][code].append(class_name)

                sess_list = build_sessions(
                    cls.id, sem_id, sem_start,
                    weekday, tiet_start, num_tiet, room)
                for s, sd in sess_list:
                    s.status = session_status(sd, past_sem, today)
                    db.session.add(s)
                total_sess += len(sess_list)

                if sem_id == CURRENT_SEM:
                    hk2_cls_sessions[cls.id] = [sd for _, sd in sess_list]
                    hk2_class_info.append(
                        (cls.id, class_name, name, gv_idx, weekday, tiet_start, room))

                db.session.flush()

                att_rate = random.uniform(0.75, 0.95)
                for s, sd in sess_list:
                    if not past_sem and sd >= today:
                        continue
                    for sv in sv_group:
                        r  = random.random()
                        st = ("present" if r < att_rate * 0.88
                              else ("late" if r < att_rate else "absent"))
                        m  = "face" if r < 0.65 else "manual"
                        db.session.add(Attendance(
                            student_id=sv.id, class_id=cls.id,
                            session_id=s.id, session_date=sd,
                            status=st, method=m,
                            face_score=(round(random.uniform(0.82, 0.98), 4)
                                        if m == "face" else None)))
                        total_att += 1

                if past_sem:
                    for sv in sv_group:
                        g = Grade(
                            student_id=sv.id, class_id=cls.id,
                            attendance_score=round(random.uniform(7.0, 10.0), 1),
                            assignment=round(random.uniform(6.0, 10.0), 1),
                            midterm=round(random.uniform(5.5, 9.5), 1),
                            final=round(random.uniform(5.0, 9.5), 1),
                            updated_by=lect.id)
                        g.calc_total(cls.formula_config)
                        db.session.add(g)
                        total_grades += 1

                if sem_id == CURRENT_SEM:
                    if gv_idx not in gv_sample:
                        gv_sample[gv_idx] = {"name": GV_DATA[gv_idx][1],
                                             "classes": [], "slots": set()}
                    gv_sample[gv_idx]["classes"].append(class_name)
                    gv_sample[gv_idx]["slots"].add((weekday, tiet_start))
                    if sv_group:
                        sv0 = sv_group[0]
                        if sv0.id not in sv_sample:
                            sv_sample[sv0.id] = []
                        sv_sample[sv0.id].append((class_name, name, weekday, tiet_start))

        db.session.commit()
        summ   = sched.summary()
        wl_str = ", ".join(f"GV{g}={l}b" for g, l in sorted(summ["gv_workload"].items()))
        print(f"  ✅ Done | {wl_str}")

        if sem_id == CURRENT_SEM:
            print("  📅 GV day-spread:")
            for gv in sorted(summ["gv_slots"]):
                days = sorted({s[0] for s in summ["gv_slots"][gv]})
                print(f"     GV{gv:02d} {GV_DATA[gv][1][:14]:14s}: "
                      f"{' '.join(DAY_NAMES[d] for d in days)}")

    # ─────────────────────────────────────────────────────────────────────────
    post_validate(
        schedulers=schedulers, hk2_cls_sessions=hk2_cls_sessions,
        sv_course_cls=sv_course_cls,
        total_cls=total_cls, total_sess=total_sess,
        total_att=total_att, total_grades=total_grades,
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # J. SAMPLE LỊCH GV & SV
    # ═══════════════════════════════════════════════════════════════════════════

    cur_sched = schedulers.get(CURRENT_SEM)

    print("\n" + "═" * 62)
    print(f"  LỊCH GIẢNG VIÊN — {CURRENT_SEM}")
    print("═" * 62)
    for gv_idx in sorted(gv_sample)[:6]:
        info  = gv_sample[gv_idx]
        slots = cur_sched.gv_used_slots.get(gv_idx, set()) if cur_sched else set()
        days  = sorted({s[0] for s in slots})
        subjs = cur_sched.gv_subjects.get(gv_idx, set()) if cur_sched else set()
        print(f"  {info['name']:20s} | {len(subjs)} môn | "
              f"ngày: {', '.join(DAY_NAMES[d] for d in days)}")

    print("\n" + "═" * 62)
    print(f"  LỊCH SINH VIÊN — {CURRENT_SEM}")
    print("═" * 62)
    printed = 0
    for sv_id, entries in sv_sample.items():
        if printed >= 3: break
        sv_obj = next((s for s in sv_objs if s.id == sv_id), None)
        if not sv_obj: continue
        days = sorted(set(wd for _, _, wd, _ in entries))
        print(f"\n  {sv_obj.full_name} | {sv_obj.username}")
        print(f"  Ngày: {', '.join(DAY_NAMES[d] for d in days)} ({len(days)}/6)")
        for class_name, course, wd, ts in sorted(entries, key=lambda x: (x[2], x[3])):
            print(f"    {DAY_NAMES[wd]} T{ts:02d} | {class_name:<14} {course}")
        printed += 1

    # ═══════════════════════════════════════════════════════════════════════════
    # K. THỜI KHÓA BIỂU & PHÂN BỐ THÁNG
    # ═══════════════════════════════════════════════════════════════════════════

    slot_classes: dict[tuple, list[str]] = defaultdict(list)
    for cls_id, cname, _, gv_idx, wd, ts, room in hk2_class_info:
        slot_classes[(wd, ts)].append(cname)

    print("\n" + "═" * 70)
    print("  THỜI KHÓA BIỂU TUẦN — HK2-2025 (T2-T7, KHÔNG có CN)")
    print("═" * 70)
    hdr = f"  {'Tiết':<15}"
    for d in DAY_NAMES:
        hdr += f"  {d:<10}"
    print(hdr)
    print("  " + "─" * 78)
    for ts in TIET_BLOCKS:
        t_s = TIET_TIME[ts][0].strftime("%H:%M")
        t_e = TIET_TIME[min(ts+2, 10)][1].strftime("%H:%M")
        row = f"  T{ts:02d} {t_s}-{t_e}  "
        for wd in range(6):
            items = slot_classes.get((wd, ts), [])
            cc: dict[str, int] = defaultdict(int)
            for e in items: cc[e.split("-")[0]] += 1
            cell = " ".join(f"{c}×{n}" for c, n in sorted(cc.items())) or "—"
            row += f"  {cell:<10}"
        print(row)

    all_hk2_dates = [d for dates in hk2_cls_sessions.values() for d in dates]
    if all_hk2_dates:
        mc: dict[int, int] = defaultdict(int)
        for d in all_hk2_dates: mc[d.month] += 1
        total_hk2 = sum(mc.values())
        ml = {1:"Tháng 1",3:"Tháng 3",4:"Tháng 4",5:"Tháng 5",6:"Tháng 6"}
        print(f"\n  PHÂN BỐ THEO THÁNG:")
        for m in sorted(mc):
            bar  = "█" * max(1, mc[m]*30//total_hk2)
            note = " ← hết HK" if m==6 else ""
            print(f"  {ml.get(m,f'T{m}'):10s} {mc[m]:5d} lượt  {bar}{note}")
        print(f"\n  Từ {min(all_hk2_dates).strftime('%d/%m/%Y')} → {max(all_hk2_dates).strftime('%d/%m/%Y')}")
        print(f"  Tháng: {sorted(set(d.month for d in all_hk2_dates))}  (tháng 2 bỏ Tết)")
        print(f"  Ngày học: T2 T3 T4 T5 T6 T7 (KHÔNG có CN)")

    print("\n" + "═" * 62)
    print("  ✅ SEED HOÀN TẤT")
    print("═" * 62)
    print("\n  Tài khoản demo:")
    for sv in sv_objs[:5]:
        print(f"    {sv.username:30s} / sv123456")
    print("  GV  : gv_nguyenvan / gv123456")
    print("  ADM : admin / admin123")
