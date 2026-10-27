from html.parser import HTMLParser
import base64
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.sessions.models import Session
from django.template.loader import render_to_string
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse


class LoginMarkup(HTMLParser):
    def __init__(self, body):
        super().__init__()
        self.inputs = {}
        self.html = {}
        self.feed(body)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input':
            self.inputs[attrs.get('name')] = attrs
        if tag == 'html':
            self.html = attrs


class LoginTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='login-test', password='synthetic-login-password')

    def test_get_preserves_csrf_autocomplete_and_required_fields(self):
        response = self.client.get(reverse('login'), {'next': '/operacion/'})
        self.assertEqual(response.status_code, 200)
        markup = LoginMarkup(response.content.decode())
        self.assertIn('csrfmiddlewaretoken', markup.inputs)
        self.assertIn('required', markup.inputs['username'])
        self.assertIn('required', markup.inputs['password'])
        self.assertEqual(markup.inputs['username']['autocomplete'], 'username')
        self.assertEqual(markup.inputs['password']['autocomplete'], 'current-password')
        self.assertEqual(markup.inputs['password']['spellcheck'], 'false')
        self.assertEqual(markup.inputs['password']['autocapitalize'], 'none')
        self.assertNotIn('maxlength', markup.inputs['password'])
        self.assertEqual(markup.inputs['next']['value'], '/operacion/')

    def test_missing_password_has_field_error_and_retains_username(self):
        response = self.client.post(reverse('login'), {'username': self.user.username, 'password': ''})
        self.assertEqual(list(response.context['form'].errors), ['password'])
        markup = LoginMarkup(response.content.decode())
        self.assertEqual(markup.inputs['username']['value'], self.user.username)
        self.assertEqual(markup.inputs['password']['aria-invalid'], 'true')
        self.assertEqual(markup.inputs['password']['aria-describedby'], 'password-error')
        self.assertContains(response, 'role="alert"')
        self.assertNotContains(response, 'No pudimos iniciar sesión.')

    def test_empty_username_has_its_own_error(self):
        response = self.client.post(reverse('login'), {'username': '', 'password': 'synthetic-password'})
        markup = LoginMarkup(response.content.decode())
        self.assertEqual(markup.inputs['username']['aria-invalid'], 'true')
        self.assertNotContains(response, 'synthetic-password')

    def test_invalid_credentials_do_not_reveal_whether_user_exists(self):
        for username in (self.user.username, 'does-not-exist'):
            response = self.client.post(reverse('login'), {'username': username, 'password': 'incorrect-secret'})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].non_field_errors())
            self.assertContains(response, 'No pudimos iniciar sesión. Revisa tu usuario y contraseña.')
            self.assertNotContains(response, 'incorrect-secret')
            self.assertNotIn('value', LoginMarkup(response.content.decode()).inputs['password'])
            self.assertNotIn('_auth_user_id', self.client.session)

    def test_username_is_escaped_and_password_never_reflected(self):
        username = '\"><img src=x onerror=alert(1)>'
        response = self.client.post(reverse('login'), {'username': username, 'password': 'not-reflected-secret'})
        self.assertEqual(LoginMarkup(response.content.decode()).inputs['username']['value'], username)
        self.assertNotContains(response, '<img src=x')
        self.assertNotContains(response, 'not-reflected-secret')

    def test_successful_login_respects_local_next(self):
        response = self.client.post(reverse('login'), {
            'username': self.user.username, 'password': 'synthetic-login-password', 'next': '/operacion/',
        })
        self.assertRedirects(response, '/operacion/', fetch_redirect_response=False)
        self.assertEqual(self.client.session['_auth_user_id'], str(self.user.pk))

    def test_external_next_is_rejected(self):
        response = self.client.post(reverse('login'), {
            'username': self.user.username, 'password': 'synthetic-login-password', 'next': 'https://example.invalid/',
        })
        self.assertRedirects(response, '/', fetch_redirect_response=False)

    def test_csrf_is_still_required(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse('login'), {'username': self.user.username, 'password': 'synthetic-login-password'})
        self.assertEqual(response.status_code, 403)
        self.assertNotIn('_auth_user_id', client.session)

    def test_login_rotates_anonymous_session(self):
        session = self.client.session
        session['synthetic_state'] = 'retained'
        session.save()
        old_key = session.session_key
        self.client.post(reverse('login'), {'username': self.user.username, 'password': 'synthetic-login-password'})
        self.assertNotEqual(self.client.session.session_key, old_key)
        self.assertFalse(Session.objects.filter(session_key=old_key).exists())
        self.assertEqual(self.client.session['synthetic_state'], 'retained')

    def test_authenticated_user_can_return_without_changing_session(self):
        self.client.force_login(self.user)
        key = self.client.session.session_key
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ya tienes una sesión iniciada.')
        self.assertContains(response, 'Volver al panel')
        self.assertEqual(self.client.session.session_key, key)

    def test_logout_requires_post_and_allows_new_login(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)
        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, reverse('login'), fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(self.client.post(reverse('login'), {
            'username': self.user.username, 'password': 'synthetic-login-password',
        }).status_code, 302)

    def test_expired_session_returns_to_login_without_false_cause(self):
        self.client.force_login(self.user)
        session = self.client.session
        session.set_expiry(-1)
        session.save()
        response = self.client.get(reverse('panel_operativo'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/login/?next='))
        response = self.client.get(response.url)
        self.assertContains(response, 'Inicia sesión para continuar.')
        self.assertNotContains(response, 'Sesión expirada')

    def test_inactive_account_uses_the_same_generic_error(self):
        get_user_model().objects.create_user(username='inactive-login-test', password='synthetic-password', is_active=False)
        response = self.client.post(reverse('login'), {'username': 'inactive-login-test', 'password': 'synthetic-password'})
        self.assertContains(response, 'No pudimos iniciar sesión. Revisa tu usuario y contraseña.')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_session_cookie_keeps_framework_protections(self):
        self.client.post(reverse('login'), {'username': self.user.username, 'password': 'synthetic-login-password'})
        from django.conf import settings
        response = self.client.post(reverse('login'), {'username': self.user.username, 'password': 'synthetic-login-password'})
        cookie = response.cookies[settings.SESSION_COOKIE_NAME]
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Lax')
        self.assertEqual(bool(cookie['secure']), settings.SESSION_COOKIE_SECURE)


CHECKS = r"""
const assert = (value, message) => { if (!value) throw Error(message); };
try {
  const form = document.getElementById('login-form');
  const username = document.getElementById('id_username');
  const password = document.getElementById('id_password');
  const toggle = document.getElementById('password-toggle');
  const submit = document.getElementById('login-submit');
  const serverError = document.getElementById('login-errors');
  assert(['initial', 'missing-password'].includes(document.body.dataset.scenario), 'Fixture scenario injected');
  const luminance = color => {
    const values = color.match(/[\d.]+/g).slice(0, 3).map(value => Number(value) / 255)
      .map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4);
    return values[0] * .2126 + values[1] * .7152 + values[2] * .0722;
  };
  const contrast = (first, second) => {
    const values = [luminance(first), luminance(second)].sort((a, b) => a - b);
    return (values[1] + .05) / (values[0] + .05);
  };
  const panelColor = getComputedStyle(document.querySelector('main')).backgroundColor;
  for (const field of [username, password]) {
    const style = getComputedStyle(field);
    const label = document.querySelector(`label[for="${field.id}"]`);
    assert(contrast(style.borderTopColor, panelColor) >= 3, 'Field boundary distinguishable from panel');
    assert(contrast(style.borderTopColor, style.backgroundColor) >= 3, 'Field boundary distinguishable from input');
    assert(contrast(style.color, style.backgroundColor) >= 4.5, 'Typed text readable');
    assert(contrast(getComputedStyle(field, '::placeholder').color, style.backgroundColor) >= 4.5, 'Placeholder readable');
    assert(parseFloat(getComputedStyle(label).fontSize) >= 16, 'Visible 16px labels');
    assert(parseFloat(style.fontSize) >= 16 && field.getBoundingClientRect().height >= 50, 'Readable spacious fields');
    const gap = field.getBoundingClientRect().top - label.getBoundingClientRect().bottom;
    assert(gap >= 0 && gap <= 12, 'Label stays close to its own field');
  }
  assert(contrast(getComputedStyle(submit).color, getComputedStyle(submit).backgroundColor) >= 4.5, 'Primary button text contrast');
  if (document.body.dataset.scenario === 'missing-password') {
    assert(document.activeElement === serverError, 'Server error summary receives focus');
    assert(username.value === 'operador_prueba', 'Username retained');
    assert(!serverError.hidden && password.getAttribute('aria-invalid') === 'true', 'Server errors accessible');
  }
  let submissions = 0;
  form.addEventListener('submit', event => { if (!event.defaultPrevented) submissions++; event.preventDefault(); });
  username.value = ''; password.value = '';
  submit.click();
  assert(submissions === 0 && !submit.disabled, 'Empty submit blocked without loading lock');
  assert(!serverError.hidden && document.activeElement === serverError, 'Error summary receives focus');
  assert(!document.getElementById('username-error').hidden && !document.getElementById('password-error').hidden, 'Both missing fields explained');
  assert(!document.getElementById('login-error-links').hidden && !document.getElementById('username-error-link').hidden && !document.getElementById('password-error-link').hidden, 'Summary links to both invalid fields');
  username.value = 'operador_prueba'; username.dispatchEvent(new Event('input'));
  password.value = 'synthetic'; password.dispatchEvent(new Event('input'));
  toggle.click();
  assert(password.type === 'text' && password.value === 'synthetic' && toggle.getAttribute('aria-pressed') === 'true', 'Reveal without changing secret');
  assert(toggle.getAttribute('aria-label') === 'Mostrar contraseña', 'Toggle name remains stable per APG');
  toggle.click(); assert(password.type === 'password', 'Hide again');
  assert(password.getAttribute('spellcheck') === 'false' && password.getAttribute('autocapitalize') === 'none', 'Reveal does not enable text corrections');
  assert(password.dispatchEvent(new ClipboardEvent('paste', {cancelable: true})), 'Paste not blocked');
  const rect = toggle.getBoundingClientRect();
  assert(rect.width >= 44 && rect.height >= 44, 'Comfortable touch target');
  Object.defineProperty(navigator, 'onLine', {configurable: true, value: false});
  submit.click();
  assert(submissions === 0 && !submit.disabled && serverError.textContent.includes('Sin conexión'), 'Offline feedback without locking or submitting');
  Object.defineProperty(navigator, 'onLine', {configurable: true, value: true});
  toggle.click();
  assert(password.type === 'text', 'Shown password before submit');
  submit.click();
  assert(submissions === 1 && submit.disabled && form.getAttribute('aria-busy') === 'true', 'Valid submit has loading state');
  assert(password.type === 'password' && toggle.getAttribute('aria-pressed') === 'false', 'Password hidden on submission for password managers');
  form.requestSubmit();
  assert(submissions === 1, 'Repeated submit events blocked while pending');
  window.dispatchEvent(new PageTransitionEvent('pageshow', {persisted: true}));
  assert(!submit.disabled && password.type === 'password' && toggle.getAttribute('aria-pressed') === 'false', 'Back navigation restores usable hidden-password state');
  for (const element of document.querySelectorAll('main, input:not([type=hidden]), button, .error-msg')) {
    if (element.hidden) continue;
    const box = element.getBoundingClientRect();
    assert(box.left >= 0 && box.right <= innerWidth, 'No horizontal overflow');
  }
  assert(document.documentElement.scrollWidth <= innerWidth, 'Page fits viewport');
  document.documentElement.dataset.test = 'PASS';
} catch (error) { document.documentElement.dataset.test = 'FAIL: ' + error.message; }
"""


class LoginBrowserTests(SimpleTestCase):
    def test_desktop_mobile_and_server_errors(self):
        cached = list((Path.home() / '.cache/ms-playwright').glob('chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell'))
        browser = os.environ.get('CHROME_BIN') or shutil.which('chromium') or (str(sorted(cached)[-1]) if cached else None)
        if not browser:
            self.skipTest('Chromium unavailable; browser interaction not checked')
        for scenario in ('initial', 'missing-password'):
            form = AuthenticationForm(data={'username': 'operador_prueba', 'password': ''}) if scenario != 'initial' else AuthenticationForm()
            if form.is_bound:
                self.assertFalse(form.is_valid())
            html = render_to_string('calidad/login.html', {'form': form, 'csrf_token': 'synthetic-token', 'next': '/operacion/'})
            logo = Path(__file__).resolve().parents[1] / 'static/img/favicon.svg'
            logo_uri = 'data:image/svg+xml;base64,' + base64.b64encode(logo.read_bytes()).decode('ascii')
            html = html.replace('/static/img/favicon.svg', logo_uri)
            html = html.replace('<body class="login-page">', f'<body class="login-page" data-scenario="{scenario}">').replace('</body>', '<script>' + CHECKS + '</script></body>')
            for width, height in [(1920, 1080), (1440, 900), (1280, 720), (1024, 768), (768, 1024), (390, 844), (320, 568)]:
                with self.subTest(scenario=scenario, width=width), tempfile.TemporaryDirectory(prefix='iqa-login-browser-', dir='/dev/shm') as scratch:
                    page = Path(scratch) / 'test.html'
                    page.write_text(html)
                    screenshot = f'/dev/shm/iqa-login-{scenario}-{width}.png'
                    result = subprocess.run([browser, '--no-sandbox', '--disable-gpu', '--disable-background-networking',
                                             '--no-first-run', '--virtual-time-budget=1500', '--dump-dom',
                                             '--user-data-dir=' + scratch + '/profile', f'--window-size={width},{height}',
                                             '--screenshot=' + screenshot, page.as_uri()], capture_output=True, text=True, timeout=25)
                    self.assertEqual(result.returncode, 0, result.stderr[-1000:])
                    self.assertEqual(LoginMarkup(result.stdout).html.get('data-test'), 'PASS')
