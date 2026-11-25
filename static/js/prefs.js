/* EduPortal user preferences: theme, accent, font size, compact sidebar, chatbot visibility */
(function () {
  var KEY = 'edu_prefs';
  var DEF = { theme: 'light', accent: 'default', font: 'md', compact: false, chatbot: true };

  function load() {
    try { return Object.assign({}, DEF, JSON.parse(localStorage.getItem(KEY) || '{}')); }
    catch (e) { return Object.assign({}, DEF); }
  }
  function save(p) { try { localStorage.setItem(KEY, JSON.stringify(p)); } catch (e) {} }
  function resolveTheme(t) {
    if (t === 'auto') return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    return t;
  }
  function apply(p) {
    var h = document.documentElement;
    h.setAttribute('data-theme', resolveTheme(p.theme));
    h.setAttribute('data-accent', p.accent);
    h.setAttribute('data-fs', p.font);
    h.setAttribute('data-chatbot', p.chatbot ? 'on' : 'off');
  }

  var prefs = load();
  apply(prefs);   // run immediately (in <head>) to avoid a flash of the wrong theme

  function applyCompact() {
    if (!document.body) return;
    if (window.innerWidth > 992) document.body.classList.toggle('sidebar-collapsed', !!prefs.compact);
  }

  function syncUI() {
    document.querySelectorAll('[data-theme-opt]').forEach(function (b) {
      b.classList.toggle('active', b.dataset.themeOpt === prefs.theme);
    });
    document.querySelectorAll('[data-accent-opt]').forEach(function (b) {
      b.classList.toggle('active', b.dataset.accentOpt === prefs.accent);
    });
    document.querySelectorAll('[data-font-opt]').forEach(function (b) {
      b.classList.toggle('active', b.dataset.fontOpt === prefs.font);
    });
    var c = document.getElementById('pref-compact');
    var b = document.getElementById('pref-chatbot');
    if (c) c.checked = !!prefs.compact;
    if (b) b.checked = !!prefs.chatbot;
  }

  function set(key, val) {
    prefs[key] = val;
    save(prefs);
    apply(prefs);
    if (key === 'compact') applyCompact();
    syncUI();
  }

  window.openSettings = function () {
    var r = document.getElementById('settings-root');
    if (r) { r.classList.add('open'); syncUI(); }
  };
  window.closeSettings = function () {
    var r = document.getElementById('settings-root');
    if (r) r.classList.remove('open');
  };
  window.resetPrefs = function () {
    prefs = Object.assign({}, DEF);
    save(prefs);
    apply(prefs);
    if (document.body) document.body.classList.remove('sidebar-collapsed');
    syncUI();
  };
  window.confirmLogout = function (e, href) {
    if (e && e.preventDefault) e.preventDefault();
    var targetUrl = href || (e && e.currentTarget && e.currentTarget.getAttribute('href')) || '/logout';
    window.eduConfirm({
      title: 'Đăng xuất hệ thống',
      message: 'Bạn có chắc muốn đăng xuất khỏi phiên làm việc hiện tại?',
      confirmText: 'Đăng xuất',
      danger: true,
      onConfirm: function () { window.location.href = targetUrl; }
    });
    return false;
  };

  function ensureDialogEl() {
    var el = document.getElementById('edu-dialog-root');
    if (el) return el;
    el = document.createElement('div');
    el.id = 'edu-dialog-root';
    el.className = 'edu-dialog-backdrop';
    el.innerHTML =
      '<div class="edu-dialog-card" role="dialog" aria-modal="true">' +
        '<div class="edu-dialog-head">' +
          '<div class="edu-dialog-icon" id="edu-dlg-icon">🔔</div>' +
          '<div class="edu-dialog-title" id="edu-dlg-title">Thông báo hệ thống</div>' +
        '</div>' +
        '<div class="edu-dialog-body" id="edu-dlg-msg"></div>' +
        '<div class="edu-dialog-foot">' +
          '<button type="button" class="btn btn-outline btn-sm" id="edu-dlg-cancel">Hủy bỏ</button>' +
          '<button type="button" class="btn btn-primary btn-sm" id="edu-dlg-ok">Đồng ý</button>' +
        '</div>' +
      '</div>';
    el.addEventListener('click', function (ev) {
      if (ev.target === el) closeEduDialog(false);
    });
    document.body.appendChild(el);
    return el;
  }

  var _dlgResolve = null;
  var _dlgCallback = null;

  function closeEduDialog(accepted) {
    var el = document.getElementById('edu-dialog-root');
    if (el) el.classList.remove('open');
    var cb = _dlgCallback;
    var rs = _dlgResolve;
    _dlgCallback = null;
    _dlgResolve = null;
    if (accepted && typeof cb === 'function') cb();
    if (typeof rs === 'function') rs(!!accepted);
  }

  window.eduConfirm = function (opts) {
    if (typeof opts === 'string') opts = { message: opts };
    opts = opts || {};
    return new Promise(function (resolve) {
      var el = ensureDialogEl();
      _dlgResolve = resolve;
      _dlgCallback = opts.onConfirm || null;
      document.getElementById('edu-dlg-icon').textContent = opts.danger ? '⚠️' : 'ℹ️';
      document.getElementById('edu-dlg-title').textContent = opts.title || 'Xác nhận thao tác';
      document.getElementById('edu-dlg-msg').textContent = opts.message || '';
      var cancelBtn = document.getElementById('edu-dlg-cancel');
      var okBtn = document.getElementById('edu-dlg-ok');
      cancelBtn.style.display = opts.alertOnly ? 'none' : '';
      cancelBtn.textContent = opts.cancelText || 'Hủy bỏ';
      okBtn.textContent = opts.confirmText || 'Xác nhận';
      okBtn.className = 'btn btn-sm ' + (opts.danger ? 'btn-danger-solid' : 'btn-primary');
      cancelBtn.onclick = function () { closeEduDialog(false); };
      okBtn.onclick = function () { closeEduDialog(true); };
      el.classList.add('open');
      setTimeout(function () { okBtn.focus(); }, 30);
    });
  };

  window.eduAlert = function (message, title) {
    return window.eduConfirm({
      title: title || 'Thông báo',
      message: message,
      confirmText: 'Đã hiểu',
      alertOnly: true
    });
  };

  window.eduConfirmForm = function (e, form, message, title, confirmText) {
    if (form && form.dataset.eduConfirmed === '1') {
      form.dataset.eduConfirmed = '';
      return true;
    }
    if (e && e.preventDefault) e.preventDefault();
    window.eduConfirm({
      title: title || 'Xác nhận thao tác',
      message: message || 'Bạn có chắc chắn muốn thực hiện thao tác này?',
      confirmText: confirmText || 'Xác nhận',
      danger: true,
      onConfirm: function () {
        if (form) {
          form.dataset.eduConfirmed = '1';
          form.submit();
        }
      }
    });
    return false;
  };

  document.addEventListener('DOMContentLoaded', function () {
    applyCompact();
    syncUI();
    document.addEventListener('click', function (e) {
      var t = e.target.closest('[data-theme-opt],[data-accent-opt],[data-font-opt]');
      if (!t) return;
      if (t.dataset.themeOpt) set('theme', t.dataset.themeOpt);
      if (t.dataset.accentOpt) set('accent', t.dataset.accentOpt);
      if (t.dataset.fontOpt) set('font', t.dataset.fontOpt);
    });
    var c = document.getElementById('pref-compact');
    var b = document.getElementById('pref-chatbot');
    if (c) c.addEventListener('change', function () { set('compact', c.checked); });
    if (b) b.addEventListener('change', function () { set('chatbot', b.checked); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        closeSettings();
        closeEduDialog(false);
      }
    });
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () {
      if (prefs.theme === 'auto') apply(prefs);
    });
  });
})();
