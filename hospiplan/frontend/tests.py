"""Parcours d'authentification : inscription, compte en attente, mot de passe oublie."""

import re
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

PASSWORD = 'Planning-Hopital-2026'


@override_settings(EVENTS_STORAGE_CONNECTION_STRING='', SITE_URL='https://hospiplan.test')
class RegistrationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('chef', 'chef@hopital.fr', PASSWORD)

    def _register(self, **overrides):
        data = {'first_name': 'Jean', 'last_name': 'Dupont', 'email': 'Jean.Dupont@Hopital.fr',
                'username': 'jdupont', 'password1': PASSWORD, 'password2': PASSWORD, **overrides}
        return self.client.post('/register/', data)

    def test_login_page_links_to_register_and_reset(self):
        html = self.client.get('/login/').content.decode()
        self.assertIn('href="/register/"', html)
        self.assertIn('href="/password-reset/"', html)

    @patch('hospiplan.events.publish_event')
    def test_registration_creates_inactive_account_and_alerts_admins(self, publish):
        r = self._register()
        self.assertRedirects(r, '/register/done/')
        user = User.objects.get(username='jdupont')
        self.assertFalse(user.is_active)
        self.assertEqual(user.email, 'jean.dupont@hopital.fr')
        event_type, data = publish.call_args.args
        self.assertEqual(event_type, 'account.requested')
        self.assertEqual(data['recipients'][0]['email'], 'chef@hopital.fr')
        self.assertTrue(data['review_url'].endswith(f'/admin/auth/user/{user.pk}/change/'))

    @patch('hospiplan.events.publish_event')
    def test_honeypot_creates_nothing(self, publish):
        r = self._register(website='http://spam.example')
        self.assertRedirects(r, '/register/done/')
        self.assertFalse(User.objects.filter(username='jdupont').exists())
        publish.assert_not_called()

    def test_duplicate_email_and_weak_password_are_rejected(self):
        r = self._register(email='CHEF@hopital.fr', password1='123456', password2='123456')
        self.assertEqual(r.status_code, 200)
        errors = r.context['form'].errors
        self.assertIn('email', errors)
        self.assertIn('password2', errors)

    def test_pending_account_gets_explicit_message_only_with_right_password(self):
        User.objects.create_user('attente', 'a@hopital.fr', PASSWORD, is_active=False)
        r = self.client.post('/login/', {'username': 'attente', 'password': PASSWORD})
        self.assertContains(r, 'en attente de validation')
        r = self.client.post('/login/', {'username': 'attente', 'password': 'mauvais'})
        self.assertContains(r, 'Identifiant ou mot de passe incorrect')
        self.assertNotContains(r, 'en attente de validation')

    @patch('frontend.signals.publish_event')
    def test_admin_action_activates_and_notifies(self, publish):
        pending = User.objects.create_user('attente', 'a@hopital.fr', PASSWORD, is_active=False)
        self.client.force_login(self.admin)
        self.client.post('/admin/auth/user/', {
            'action': 'activate_accounts', '_selected_action': [pending.pk],
        })
        pending.refresh_from_db()
        self.assertTrue(pending.is_active)
        event_type, data = publish.call_args.args
        self.assertEqual(event_type, 'account.activated')
        self.assertEqual(data['login_url'], 'https://hospiplan.test/login/')
        self.assertEqual(data['recipients'][0]['email'], 'a@hopital.fr')

    @patch('frontend.signals.publish_event')
    def test_saving_an_active_account_does_not_notify(self, publish):
        self.admin.first_name = 'Chef'
        self.admin.save()
        publish.assert_not_called()


@override_settings(EVENTS_STORAGE_CONNECTION_STRING='', PASSWORD_RESET_TIMEOUT=7200)
class PasswordResetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('alice', 'alice@hopital.fr', 'Ancien-Mot-2026', first_name='Alice')

    @patch('hospiplan.events.publish_event')
    def test_full_reset_flow(self, publish):
        r = self.client.post('/password-reset/', {'email': 'ALICE@hopital.fr'})
        self.assertRedirects(r, '/password-reset/done/')
        event_type, data = publish.call_args.args
        self.assertEqual(event_type, 'password.reset_requested')
        self.assertEqual(data['expires_hours'], 2)
        recipient = data['recipients'][0]
        self.assertEqual(recipient['email'], 'alice@hopital.fr')
        path = re.sub(r'^https?://[^/]+', '', recipient['reset_url'])
        self.assertRegex(path, r'^/reset/[^/]+/[^/]+/$')

        # Le lien redirige vers l'URL de saisie (le jeton est garde en session).
        r = self.client.get(path, follow=True)
        self.assertContains(r, 'Nouveau mot de passe')
        form_url = r.redirect_chain[-1][0]
        r = self.client.post(form_url, {'new_password1': PASSWORD, 'new_password2': PASSWORD})
        self.assertRedirects(r, '/reset/done/')
        self.assertTrue(self.client.login(username='alice', password=PASSWORD))

        # Un lien ne sert qu'une fois.
        self.client.logout()
        r = self.client.get(path, follow=True)
        self.assertContains(r, 'Lien invalide ou expiré')

    @patch('hospiplan.events.publish_event')
    def test_unknown_or_inactive_email_sends_nothing_but_looks_the_same(self, publish):
        User.objects.create_user('attente', 'attente@hopital.fr', PASSWORD, is_active=False)
        for email in ('inconnu@hopital.fr', 'attente@hopital.fr'):
            r = self.client.post('/password-reset/', {'email': email})
            self.assertRedirects(r, '/password-reset/done/')
        publish.assert_not_called()
