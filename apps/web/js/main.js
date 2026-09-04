/* VEHDiag marketing site — shared interactions */
(function () {
  'use strict';

  /* ---------- theme ---------- */
  const themeKey = 'vehdiag-theme';
  function applyTheme(t) {
    if (t === 'dark') document.documentElement.setAttribute('data-theme', 'dark');
    else document.documentElement.removeAttribute('data-theme');
    try { localStorage.setItem(themeKey, t); } catch (e) {}
    const btn = document.querySelector('[data-theme-toggle]');
    if (btn) {
      btn.setAttribute('aria-label', t === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
      btn.innerHTML = t === 'dark'
        ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4m11.4-11.4 1.4-1.4"/></svg>'
        : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/></svg>';
    }
  }
  let saved = null;
  try { saved = localStorage.getItem(themeKey); } catch (e) {}
  if (!saved) {
    saved = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  applyTheme(saved);
  document.addEventListener('click', function (e) {
    const t = e.target.closest('[data-theme-toggle]');
    if (!t) return;
    const cur = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    applyTheme(cur);
  });

  /* ---------- mobile nav ---------- */
  const nav = document.getElementById('site-nav');
  const toggle = document.querySelector('[data-nav-toggle]');
  if (nav && toggle) {
    toggle.addEventListener('click', function () {
      nav.classList.toggle('open');
      toggle.setAttribute('aria-expanded', nav.classList.contains('open') ? 'true' : 'false');
    });
  }

  /* ---------- footer year ---------- */
  document.querySelectorAll('[data-year]').forEach(function (el) { el.textContent = new Date().getFullYear(); });

  /* ---------- toast helper (global) ---------- */
  window.vehToast = function (msg, kind, title) {
    kind = kind || 'info';
    let stack = document.querySelector('.toast-stack');
    if (!stack) { stack = document.createElement('div'); stack.className = 'toast-stack'; stack.setAttribute('aria-live', 'polite'); document.body.appendChild(stack); }
    const el = document.createElement('div');
    el.className = 'toast ' + kind;
    el.setAttribute('role', kind === 'err' ? 'alert' : 'status');
    el.innerHTML = '<span class="pulse-dot"></span><div><strong>' + (title || 'VEHDiag') + '</strong><br>' + msg + '</div>';
    stack.appendChild(el);
    setTimeout(function () { el.style.opacity = '0'; el.style.transition = 'opacity .3s'; setTimeout(function () { el.remove(); }, 320); }, 4200);
  };

  /* ---------- Android download nudge ---------- */
  if (/android/i.test(navigator.userAgent)) {
    document.querySelectorAll('[data-android-nudge]').forEach(function (el) { el.hidden = false; });
  }

  /* ---------- generic form validation (login/register/contact) ---------- */
  document.querySelectorAll('form[data-validate]').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      let ok = true;
      form.querySelectorAll('[required]').forEach(function (inp) {
        const err = inp.closest('.field') ? inp.closest('.field').querySelector('.field-error') : null;
        const bad = !inp.value.trim() || (inp.type === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(inp.value));
        if (inp.type === 'password' && inp.minLength && inp.value.length < inp.minLength) { if (err) { err.textContent = 'Minimum ' + inp.minLength + ' characters'; err.classList.add('show'); inp.setAttribute('aria-invalid','true'); ok = false; return; } }
        if (bad) { if (err) { err.classList.add('show'); inp.setAttribute('aria-invalid','true'); } ok = false; }
        else { if (err) err.classList.remove('show'); inp.removeAttribute('aria-invalid'); }
      });
      if (!ok) e.preventDefault();
    });
  });
})();
