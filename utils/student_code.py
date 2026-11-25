"""
utils/student_code.py — Chuẩn hóa, kiểm tra và cấp phát Mã số sinh viên (MSSV)

Quy chuẩn MSSV:
  - Độ dài: tối đa 8 ký tự (từ 5 đến 8 ký tự), ví dụ: 23ITB185, 24IT001
  - Ký tự hợp lệ: CHỈ gồm chữ cái IN HOA (A-Z) và chữ số (0-9)
  - Cấu trúc bắt buộc: <2 chữ số Khóa><Mã ngành IN HOA><Số thứ tự>
    Ví dụ Khóa 23, ngành ITB, STT 185 -> 23ITB185 (8 ký tự)
"""
import re
from typing import Optional, Tuple

# Regex: 2 số đầu (khóa) + 1-4 chữ in hoa (ngành) + 1-4 chữ số (số thứ tự), tổng độ dài <= 8
MSSV_PATTERN = re.compile(r'^(?=.{5,8}$)(\d{2})([A-Z]{1,4})(\d{1,4})$')

MAJOR_OPTIONS = [
    ('ITB', 'Công nghệ thông tin (Kỹ sư - ITB)'),
    ('IT',  'Công nghệ thông tin (Cử nhân - IT)'),
    ('AI',  'Trí tuệ nhân tạo (AI)'),
    ('CE',  'Kỹ thuật máy tính (CE)'),
    ('SE',  'Kỹ thuật phần mềm (SE)'),
    ('NS',  'An toàn thông tin (NS)'),
    ('BA',  'Quản trị kinh doanh số (BA)'),
]

COHORT_OPTIONS = ['21', '22', '23', '24', '25', '26']


def normalize_student_code(code: Optional[str]) -> str:
    """Chuẩn hóa chuỗi MSSV về chữ in hoa, bỏ khoảng trắng."""
    if not code:
        return ''
    return code.strip().upper()


def validate_student_code(code: Optional[str], expected_cohort: Optional[str] = None) -> Tuple[bool, str]:
    """
    Kiểm tra tính hợp lệ của MSSV:
      - Không rỗng, <= 8 ký tự
      - Có đầy đủ chữ IN HOA và số, đúng cấu trúc <Khóa 2 số><Chữ in hoa><Số>
      - Nếu truyền expected_cohort (VD '23'), 2 số đầu bắt buộc phải khớp '23'
    Trả về: (is_valid, error_message)
    """
    raw = (code or '').strip()
    if not raw:
        return False, 'Vui lòng nhập Mã số sinh viên (MSSV).'

    if len(raw) > 8:
        return False, f'MSSV "{raw}" vượt quá 8 ký tự cho phép (hiện có {len(raw)} ký tự).'

    if raw != raw.upper():
        return False, 'MSSV bắt buộc phải viết IN HOA toàn bộ phần chữ cái (ví dụ: 23ITB185).'

    if not re.match(r'^[A-Z0-9]+$', raw):
        return False, 'MSSV chỉ được chứa chữ cái IN HOA (A-Z) và chữ số (0-9), không chứa ký tự đặc biệt hay dấu.'

    match = MSSV_PATTERN.match(raw)
    if not match:
        return (
            False,
            'MSSV phải dài 5–8 ký tự, bắt đầu bằng 2 số Khóa + chữ IN HOA mã ngành + số thứ tự (VD: 23ITB185).',
        )

    cohort_prefix = match.group(1)
    if expected_cohort:
        exp = str(expected_cohort).strip()
        if len(exp) == 4 and exp.startswith('20'):
            exp = exp[2:]
        if cohort_prefix != exp:
            return (
                False,
                f'Sinh viên thuộc Khóa {exp} nên MSSV bắt buộc phải bắt đầu bằng "{exp}" (ví dụ: {exp}ITB001).',
            )

    return True, ''


def extract_cohort(code: Optional[str]) -> Optional[str]:
    """Trích xuất khóa (VD '23') từ MSSV hợp lệ."""
    if not code:
        return None
    m = re.match(r'^(\d{2})[A-Z]', code.strip().upper())
    if m:
        return m.group(1)
    return None


def generate_next_student_code(cohort: str, major: str = 'ITB') -> str:
    """
    Tự động sinh MSSV tiếp theo chưa tồn tại trong DB theo Khóa + Mã ngành,
    đảm bảo tổng độ dài <= 8 ký tự.
    Ví dụ: cohort='23', major='ITB' -> '23ITB001' .. '23ITB185'
    """
    from models.user import User

    c = str(cohort).strip()
    if len(c) == 4 and c.startswith('20'):
        c = c[2:]
    if not re.match(r'^\d{2}$', c):
        c = '23'

    m = re.sub(r'[^A-Z]', '', (major or 'ITB').upper())[:4] or 'ITB'
    prefix = f"{c}{m}"

    # Số chữ số tối đa dành cho phần STT để tổng độ dài <= 8 (tối thiểu 1 chữ số, ưu tiên 3 chữ số)
    max_seq_len = 8 - len(prefix)
    pad_len = min(3, max_seq_len)

    existing = (
        User.query
        .filter(User.student_code.like(f"{prefix}%"))
        .with_entities(User.student_code)
        .all()
    )

    max_num = 0
    for (scode,) in existing:
        if not scode:
            continue
        tail = scode.upper()[len(prefix):]
        if tail.isdigit():
            max_num = max(max_num, int(tail))

    next_num = max_num + 1
    max_val = (10 ** max_seq_len) - 1
    if next_num > max_val:
        # Tìm lỗ trống nhỏ nhất nếu đã chạm trần
        used_nums = {
            int(s[len(prefix):])
            for (s,) in existing
            if s and s.upper().startswith(prefix) and s[len(prefix):].isdigit()
        }
        next_num = next((i for i in range(1, max_val + 1) if i not in used_nums), 1)

    return f"{prefix}{next_num:0{pad_len}d}"
