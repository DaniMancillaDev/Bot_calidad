from html.parser import HTMLParser
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
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


CHECKS = r"""
const assert = (value, message) => { if (!value) throw Error(message); };
try {
  const form = document.getElementById('login-form');
  const username = document.getElementById('id_username');
  const password = document.getElementById('id_password');
  const toggle = document.getElementById('password-toggle');
  const submit = document.getElementById('login-submit');
  const serverError = document.getElementById('login-errors');
  if (document.body.dataset.scenario === 'missing-password') {
    assert(document.activeElement === password, 'Server field error receives focus');
    assert(username.value === 'operador_prueba', 'Username retained');
    assert(!serverError.hidden && password.getAttribute('aria-invalid') === 'true', 'Server errors accessible');
  }
  let submissions = 0;
  form.addEventListener('submit', event => { if (!event.defaultPrevented) submissions++; event.preventDefault(); });
  username.value = ''; password.value = '';
  submit.click();
  assert(submissions === 0 && !submit.disabled, 'Empty submit blocked without loading lock');
  assert(!serverError.hidden && document.activeElement === username, 'Inline errors and first invalid focus');
  assert(!document.getElementById('username-error').hidden && !document.getElementById('password-error').hidden, 'Both missing fields explained');
  username.value = 'operador_prueba'; username.dispatchEvent(new Event('input'));
  password.value = 'synthetic'; password.dispatchEvent(new Event('input'));
  toggle.click();
  assert(password.type === 'text' && password.value === 'synthetic' && toggle.getAttribute('aria-pressed') === 'true', 'Reveal without changing secret');
  toggle.click(); assert(password.type === 'password', 'Hide again');
  const rect = toggle.getBoundingClientRect();
  assert(rect.width >= 44 && rect.height >= 44, 'Comfortable touch target');
  submit.click();
  assert(submissions === 1 && submit.disabled && form.getAttribute('aria-busy') === 'true', 'Valid submit has loading state');
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
            html = html.replace('<body>', f'<body data-scenario="{scenario}">').replace('</body>', '<script>' + CHECKS + '</script></body>')
            for width, height in [(1440, 1000), (390, 844), (320, 568)]:
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
