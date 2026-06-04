/**
 * static/js/schedule_calendar.js
 *
 * FIX LỖI: Lịch giảng viên hiển thị sai cột — lớp T7 bị đẩy sang cột CN
 *
 * ═══════════════════════════════════════════════════════════════════
 * NGUYÊN NHÂN:
 *   Seed lưu schedule_info.day theo quy ước:
 *     0 = T2 (Thứ Hai)
 *     1 = T3
 *     2 = T4
 *     3 = T5
 *     4 = T6
 *     5 = T7 (Thứ Bảy)   ← KHÔNG bao giờ có 6 = CN
 *
 *   JavaScript Date.getDay() trả về:
 *     0 = CN (Chủ Nhật)   ← bắt đầu từ CN!
 *     1 = T2
 *     ...
 *     6 = T7 (Thứ Bảy)
 *
 *   Nếu frontend làm: colIndex = new Date(sess.session_date).getDay() - 1
 *   thì T7 (getDay()=6) → colIndex=5 ✓
 *   nhưng T2 (getDay()=1) → colIndex=0 ✓
 *   Tuy nhiên nếu frontend dùng schedule_info.day trực tiếp làm colIndex
 *   và calendar có 7 cột (0=T2..6=CN) thì ngày T7 (day=5) hiển thị đúng.
 *
 *   Bug thực tế trong ảnh: một lớp hiển thị ở cột CN (colIndex=6).
 *   Điều này xảy ra khi frontend render dựa vào session_date thực tế:
 *     const col = new Date(session.session_date).getDay();
 *     // T7 → getDay()=6 → cột index 6 = CN (sai!)
 *
 * ═══════════════════════════════════════════════════════════════════
 * FIX:
 *   Dùng hàm jsDateToColIndex() bên dưới thay cho getDay() trực tiếp.
 * ═══════════════════════════════════════════════════════════════════
 */

"use strict";

// Tên cột hiển thị — index 0..5 = T2..T7 (không có CN)
const COL_NAMES = ["HAI", "BA", "TƯ", "NĂM", "SÁU", "BẢY"];
const N_COLS    = 6;  // T2..T7, KHÔNG có CN

/**
 * Chuyển Date object → chỉ số cột lịch (0=T2 .. 5=T7).
 * Trả -1 nếu là CN (không hiển thị).
 *
 * Lý do cần hàm này:
 *   JS Date.getDay(): 0=CN, 1=T2, 2=T3, 3=T4, 4=T5, 5=T6, 6=T7
 *   Calendar cột:         0=T2, 1=T3, 2=T4, 3=T5, 4=T6, 5=T7
 *
 * @param {Date|string} d
 * @returns {number} 0..5 hoặc -1 (CN)
 */
function jsDateToColIndex(d) {
  const jsDay = (d instanceof Date ? d : new Date(d)).getDay();
  if (jsDay === 0) return -1;   // CN — không có cột
  return jsDay - 1;             // T2(1)→0, T3(2)→1, ..., T7(6)→5
}

/**
 * Chuyển schedule_info.day (0=T2..5=T7) → chỉ số cột.
 * Đây là giá trị lưu trong DB từ seed; đã đúng thứ tự.
 *
 * @param {number} day  0..5
 * @returns {number}    0..5
 */
function seedDayToColIndex(day) {
  if (day < 0 || day > 5) return -1;  // bảo vệ
  return day;
}

// ─────────────────────────────────────────────────────────────────────────────
// RENDER CALENDAR
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Render weekly schedule grid.
 *
 * @param {Array}  sessions   - mảng session objects từ API
 * @param {Object} options
 *   useSessionDate {boolean}  true  → dùng session.session_date để tính cột
 *                             false → dùng session.schedule_day (0=T2..5=T7)
 */
function renderWeekCalendar(sessions, options = {}) {
  const { useSessionDate = false } = options;

  const grid = document.getElementById("schedule-grid");
  if (!grid) return;

  // Xóa cell cũ (giữ header)
  grid.querySelectorAll(".sched-cell").forEach(el => el.remove());

  sessions.forEach(sess => {
    // ── Tính cột (0=T2..5=T7) ──────────────────────────────────────────────
    let colIdx;
    if (useSessionDate && sess.session_date) {
      colIdx = jsDateToColIndex(sess.session_date);
    } else {
      // Ưu tiên dùng schedule_info.day từ DB (đáng tin cậy hơn)
      colIdx = seedDayToColIndex(
        sess.schedule_day ?? sess.schedule_info?.day ?? -1
      );
    }

    if (colIdx < 0 || colIdx >= N_COLS) return; // bỏ qua CN hoặc giá trị lạ

    // ── Tính hàng (tiet) ────────────────────────────────────────────────────
    const tiet      = sess.tiet_start ?? sess.schedule_info?.tiet_start ?? 1;
    const numTiet   = sess.num_tiet   ?? sess.schedule_info?.num_tiet   ?? 3;
    const rowStart  = tiet;
    const rowSpan   = numTiet;

    // ── Tạo cell ────────────────────────────────────────────────────────────
    const cell = document.createElement("div");
    cell.className   = "sched-cell";
    cell.dataset.col = colIdx;
    cell.dataset.row = rowStart;
    cell.style.cssText = `
      grid-column: ${colIdx + 2};
      grid-row: ${rowStart} / span ${rowSpan};
    `;
    cell.innerHTML = `
      <strong>${sess.course_name ?? sess.class_name ?? ""}</strong>
      <span class="room">${sess.room ?? ""}</span>
      <span class="code">${sess.class_name ?? ""}</span>
    `;
    grid.appendChild(cell);
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// WEEK NAVIGATION
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Lấy Thứ Hai (T2) của tuần chứa ngày d.
 * Dùng seed convention: T2=0, CN=6.
 */
function getMondayOfWeek(d) {
  const dt   = new Date(d);
  const jsDay = dt.getDay();                     // 0=CN, 1=T2..6=T7
  const diff  = jsDay === 0 ? -6 : 1 - jsDay;   // offset về T2
  dt.setDate(dt.getDate() + diff);
  dt.setHours(0, 0, 0, 0);
  return dt;
}

/**
 * Trả về mảng 6 ngày trong tuần [T2, T3, T4, T5, T6, T7].
 */
function getWeekDays(monday) {
  return Array.from({ length: 6 }, (_, i) => {
    const d = new Date(monday);
    d.setDate(d.getDate() + i);
    return d;
  });
}

/**
 * Format ngày: Date → "16/05"
 */
function fmtDate(d) {
  return `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}`;
}

/**
 * Cập nhật header cột với ngày thực tế của tuần.
 */
function updateWeekHeaders(monday) {
  const days    = getWeekDays(monday);
  const headers = document.querySelectorAll(".col-header");
  days.forEach((d, i) => {
    if (headers[i]) {
      headers[i].querySelector(".day-name").textContent = COL_NAMES[i];
      headers[i].querySelector(".day-date").textContent = fmtDate(d);
    }
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// EXPORT
// ─────────────────────────────────────────────────────────────────────────────

window.ScheduleCalendar = {
  jsDateToColIndex,
  seedDayToColIndex,
  renderWeekCalendar,
  getMondayOfWeek,
  getWeekDays,
  updateWeekHeaders,
  COL_NAMES,
  N_COLS,
};

/*
 * ═══════════════════════════════════════════════════════════════
 * HƯỚNG DẪN SỬA TRONG FILE TEMPLATE (HTML/Jinja2)
 * ═══════════════════════════════════════════════════════════════
 *
 * Cũ (SAI — gây lớp T7 hiển thị ở cột CN):
 *   const col = new Date(session.session_date).getDay();
 *   //  T7 → getDay()=6 → cột CN ❌
 *
 * Mới (ĐÚNG):
 *   // Option A: dùng session_date
 *   const col = ScheduleCalendar.jsDateToColIndex(session.session_date);
 *   // T7 getDay()=6 → 6-1=5 → cột T7 ✓
 *
 *   // Option B: dùng schedule_info.day từ DB (khuyến nghị)
 *   const col = ScheduleCalendar.seedDayToColIndex(session.schedule_info.day);
 *   // day=5 → 5 → cột T7 ✓
 *
 * ═══════════════════════════════════════════════════════════════
 * Nếu dùng Jinja2 để render server-side:
 *
 *   Cũ (SAI):
 *     {% set col = session.session_date.weekday() + 2 %}
 *     {# T7 weekday()=5 → col=7 → vượt 6 cột ❌ #}
 *
 *   Mới (ĐÚNG):
 *     {% set col = cls.schedule_info.day + 2 %}
 *     {# day=5(T7) → col=7 → grid-column:7 = cột T7 ✓ #}
 *     {# Hoặc dùng session_date.isoweekday()-1+2 = isoweekday()+1 #}
 *     {# Python isoweekday(): 1=T2..6=T7 (KHÔNG có 7=CN nếu seed đúng) #}
 *     {% set col = session.session_date.isoweekday() + 1 %}
 *     {# T2 isoweekday()=1 → col=2 ✓, T7 isoweekday()=6 → col=7 ✓ #}
 * ═══════════════════════════════════════════════════════════════
 */
