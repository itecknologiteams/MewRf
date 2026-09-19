"""manage.py create_operator — the only way to make a portal operator account."""
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from .models import User, UserRole

PASSWORD = 'Booth-Desk-2026!'


class CreateOperatorCommandTest(TestCase):
    def run_command(self, **options):
        call_command('create_operator', stdout=StringIO(), **options)

    def test_creates_an_operator_who_can_log_in(self):
        self.run_command(phone='0300 123-4567', name='Ali Khan', password=PASSWORD)

        user = User.objects.get(phone='03001234567')
        self.assertEqual(user.user_role, UserRole.OPERATOR)
        self.assertEqual(user.full_name, 'Ali Khan')
        # A password picked for them, not by them — see User.password_set_at.
        self.assertIsNone(user.password_set_at)

        response = APIClient().post(
            '/api/v1/auth/login/',
            {'phone': '03001234567', 'password': PASSWORD},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['data']['role'], UserRole.OPERATOR)

    def test_prompts_for_the_password_when_not_given(self):
        with mock.patch('getpass.getpass', side_effect=[PASSWORD, PASSWORD]):
            self.run_command(phone='03001234567', name='Ali Khan')
        self.assertTrue(User.objects.get(phone='03001234567').check_password(PASSWORD))

    def test_mismatched_prompt_creates_nothing(self):
        with mock.patch('getpass.getpass', side_effect=[PASSWORD, 'something-else']):
            with self.assertRaisesMessage(CommandError, 'did not match'):
                self.run_command(phone='03001234567', name='Ali Khan')
        self.assertFalse(User.objects.filter(phone='03001234567').exists())

    def test_rejects_a_phone_the_portal_cannot_log_in_with(self):
        with self.assertRaisesMessage(CommandError, 'not a valid phone number'):
            self.run_command(phone='12345', name='Ali Khan', password=PASSWORD)

    def test_rejects_a_weak_password(self):
        with self.assertRaisesMessage(CommandError, 'Password rejected'):
            self.run_command(phone='03001234567', name='Ali Khan', password='password')
        self.assertFalse(User.objects.filter(phone='03001234567').exists())

    def test_refuses_to_touch_an_existing_account(self):
        User.objects.create_user(phone='03001234567', password='x', full_name='Tag Holder')
        with self.assertRaisesMessage(CommandError, 'already belongs to Tag Holder'):
            self.run_command(phone='03001234567', name='Ali Khan', password=PASSWORD)
        self.assertEqual(User.objects.get(phone='03001234567').user_role, UserRole.USER)
