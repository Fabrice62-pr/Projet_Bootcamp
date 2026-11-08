"""
Tests du Core sur ses points de contact avec les microservices.
Lances par la CI (GitHub Actions) avant tout deploiement.
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings


@override_settings(EVENTS_STORAGE_CONNECTION_STRING='')
class HealthTests(TestCase):
    def test_health_is_public_and_reports_database(self):
        r = self.client.get('/health/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {'service': 'core', 'status': 'ok', 'database': 'ok'})


@override_settings(REPORTING_SERVICE_KEY='cle-de-test')
class InternalApiTests(TestCase):
    url = '/api/internal/planning-report/?week_start=2026-11-18'

    def test_requires_service_key(self):
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.get(self.url, HTTP_X_SERVICE_KEY='mauvaise').status_code, 403)

    def test_returns_week_aligned_on_monday(self):
        r = self.client.get(self.url, HTTP_X_SERVICE_KEY='cle-de-test')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data['week_start'], '2026-11-16')
        self.assertEqual(data['week_end'], '2026-11-22')
        self.assertEqual(set(data), {'week_start', 'week_end', 'shifts', 'staff', 'managers'})

    @override_settings(REPORTING_SERVICE_KEY='')
    def test_disabled_when_no_key_configured(self):
        self.assertEqual(self.client.get(self.url, HTTP_X_SERVICE_KEY='').status_code, 403)


@override_settings(
    ENGINE_URL='http://127.0.0.1:9',       # port ferme : moteur injoignable
    ENGINE_TIMEOUT_SECONDS=2,
    REPORTING_URL='http://127.0.0.1:9',
    REPORTING_TIMEOUT_SECONDS=2,
    EVENTS_STORAGE_CONNECTION_STRING='',
)
class MicroserviceOutageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('planif', password='mot-de-passe-test')

    def test_api_requires_authentication(self):
        self.assertEqual(self.client.get('/api/staff/').status_code, 403)

    def test_generation_returns_503_when_engine_is_down(self):
        self.client.force_login(self.user)
        r = self.client.post('/api/plannings/generate/', {'week_start': date.today().isoformat()},
                             content_type='application/json')
        self.assertEqual(r.status_code, 503)
        self.assertIn('injoignable', r.json()['error'])

    def test_pdf_requires_login(self):
        r = self.client.get('/planning/pdf/?week_start=2026-11-16')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/login/', r['Location'])

    def test_pdf_returns_503_when_reporting_is_down(self):
        self.client.force_login(self.user)
        monday = date.today() - timedelta(days=date.today().weekday())
        r = self.client.get(f'/planning/pdf/?week_start={monday.isoformat()}')
        self.assertEqual(r.status_code, 503)
