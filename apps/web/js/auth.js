/* VEHDiag auth pages — register/login against the local API */
(function () {
  'use strict';
  var API = '/api/v1';

  function post(path, body) {
    return fetch(API + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF': 'web' },
      body: JSON.stringify(body)
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) {
        if (!r.ok) throw new Error(j.error && j.error.message ? j.error.message : 'Request failed');
        return j.data;
      });
    });
  }

  var loginForm = document.getElementById('login-form');
  if (loginForm) {
    loginForm.addEventListener('submit', function (e) {
      if (loginForm.checkValidity() === false) return;
      e.preventDefault();
      var btn = loginForm.querySelector('button[type=submit]');
      btn.classList.add('loading'); btn.disabled = true;
      post('/auth/login', { email: document.getElementById('email').value, password: document.getElementById('password').value })
        .then(function (d) {
          localStorage.setItem('vehdiag_token', d.token);
          localStorage.setItem('vehdiag_user', JSON.stringify(d.user));
          window.location.href = '/app/';
        })
        .catch(function (err) { window.vehToast(err.message, 'err', 'Login failed'); })
        .finally(function () { btn.classList.remove('loading'); btn.disabled = false; });
    });
    var forgot = document.getElementById('forgot-link');
    if (forgot) forgot.addEventListener('click', function (e) {
      e.preventDefault();
      var email = document.getElementById('email').value;
      if (!email) { window.vehToast('Enter your email first, then press Forgot password.', 'warn'); return; }
      post('/auth/forgot', { email: email })
        .then(function () { window.vehToast('If the account exists, a reset token was generated. (Demo mode: check the API response / server log.)', 'ok', 'Reset started'); })
        .catch(function (err) { window.vehToast(err.message, 'err'); });
    });
  }

  var regForm = document.getElementById('register-form');
  if (regForm) {
    regForm.addEventListener('submit', function (e) {
      if (regForm.checkValidity() === false) return;
      e.preventDefault();
      var btn = regForm.querySelector('button[type=submit]');
      btn.classList.add('loading'); btn.disabled = true;
      post('/auth/register', {
        name: document.getElementById('name').value,
        email: document.getElementById('email').value,
        password: document.getElementById('password').value
      }).then(function (d) {
        window.vehToast('Account created. Welcome, ' + d.user.name + '!', 'ok');
        localStorage.setItem('vehdiag_token', d.token);
        localStorage.setItem('vehdiag_user', JSON.stringify(d.user));
        setTimeout(function () { window.location.href = '/app/'; }, 900);
      }).catch(function (err) { window.vehToast(err.message, 'err', 'Registration failed'); })
        .finally(function () { btn.classList.remove('loading'); btn.disabled = false; });
    });
  }
})();
