"""Auth surface tests for the consumer app: self-profile scope and registration gating."""
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from .models import User, UserRole, UserStatus


class SelfProfileUpdateTest(TestCase):
    """PATCH /auth/me/ must not be a route to becoming an admin."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            phone='03001112233', password='holderpass123', full_name='Tag Holder'
        )
        self.client.force_authenticate(user=self.user)

    def test_updates_name_and_cnic(self):
        response = self.client.patch(
            '/api/v1/auth/me/',
            {'full_name': 'Tag Holder Jr', 'cnic': '42101-1234567-1'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, 'Tag Holder Jr')
        self.assertEqual(self.user.cnic, '42101-1234567-1')

    def test_cannot_escalate_own_role(self):
        response = self.client.patch(
            '/api/v1/auth/me/', {'user_role': UserRole.ADMIN}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.user_role, UserRole.USER)
        self.assertEqual(response.json()['data']['user_role'], UserRole.USER)

    def test_cannot_unblock_self(self):
        self.user.status = UserStatus.BLOCKED
        self.user.save(update_fields=['status'])
        self.client.patch('/api/v1/auth/me/', {'status': UserStatus.ACTIVE}, format='json')
        self.user.refresh_from_db()
        self.assertEqual(self.user.status, UserStatus.BLOCKED)

    def test_cannot_change_own_phone(self):
        """phone is USERNAME_FIELD — rewriting it takes over login identity."""
        self.client.patch('/api/v1/auth/me/', {'phone': '03009998877'}, format='json')
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone, '03001112233')

    def test_admin_can_still_change_a_users_role(self):
        admin = User.objects.create_user(
            phone='03007776655', password='adminpass123', full_name='Admin',
            user_role=UserRole.ADMIN, is_staff=True,
        )
        client = APIClient()
        client.force_authenticate(user=admin)
        response = client.patch(
            f'/api/v1/auth/admin/users/{self.user.id}/',
            {'user_role': UserRole.OPERATOR},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.user_role, UserRole.OPERATOR)


class RegistrationGatingTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_anonymous_registration_is_refused_by_default(self):
        response = self.client.post(
            '/api/v1/auth/register/',
            {'full_name': 'Walk In', 'phone': '03211112222', 'password': 'somepass123'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(User.objects.filter(phone='03211112222').exists())

    @override_settings(USER_SELF_REGISTRATION_ENABLED=True)
    def test_anonymous_registration_allowed_when_flag_is_on(self):
        response = self.client.post(
            '/api/v1/auth/register/',
            {'full_name': 'Walk In', 'phone': '03211112222', 'password': 'somepass123'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(phone='03211112222').exists())

    def test_operator_can_still_register_a_consumer(self):
        """The booth portal creates the tag holder while fitting the tag."""
        operator = User.objects.create_user(
            phone='03007776655', password='oppass123456', full_name='Booth Operator',
            user_role=UserRole.OPERATOR,
        )
        self.client.force_authenticate(user=operator)
        response = self.client.post(
            '/api/v1/auth/register/',
            {'full_name': 'Walk In', 'phone': '03211112222', 'cnic': '42101-7654321-9'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(phone='03211112222').exists())


class UserLookupAccessTest(TestCase):
    """GET /auth/admin/users/ backs the operator's owner lookup at registration."""

    URL = '/api/v1/auth/admin/users/'

    def setUp(self):
        self.client = APIClient()
        self.holder = User.objects.create_user(
            phone='03211112222', password='holderpass123', full_name='Tag Holder'
        )
        # Created last, so it is the newest row: the old unfiltered list put it
        # first and the registration page took it as the match.
        self.other = User.objects.create_user(
            phone='03339998888', password='otherpass123', full_name='Someone Else'
        )
        self.operator = User.objects.create_user(
            phone='03007776655', password='oppass123456', full_name='Booth Operator',
            user_role=UserRole.OPERATOR,
        )

    def test_operator_search_returns_only_the_matching_user(self):
        self.client.force_authenticate(user=self.operator)
        response = self.client.get(self.URL, {'search': '03211112222'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        phones = [u['phone'] for u in response.json()['data']]
        self.assertEqual(phones, ['03211112222'])

    def test_operator_cannot_list_everyone(self):
        self.client.force_authenticate(user=self.operator)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_consumer_is_refused_even_with_a_search(self):
        self.client.force_authenticate(user=self.holder)
        response = self.client.get(self.URL, {'search': '03339998888'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_lists_all_and_can_filter_by_role(self):
        admin = User.objects.create_user(
            phone='03001234567', password='adminpass123', full_name='Admin',
            user_role=UserRole.ADMIN, is_staff=True,
        )
        self.client.force_authenticate(user=admin)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()['data']), 4)

        response = self.client.get(self.URL, {'role': UserRole.OPERATOR})
        phones = [u['phone'] for u in response.json()['data']]
        self.assertEqual(phones, ['03007776655'])


class LoginResponseShapeTest(TestCase):
    """The consumer app depends on these exact shapes; pin them."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            phone='03001112233', password='holderpass123', full_name='Tag Holder'
        )

    def test_tokens_arrive_as_cookies_not_in_the_body(self):
        response = self.client.post(
            '/api/v1/auth/login/',
            {'phone': '03001112233', 'password': 'holderpass123'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()['data']
        self.assertNotIn('access', body)
        self.assertNotIn('refresh', body)
        self.assertIn('access_token', response.cookies)
        self.assertIn('refresh_token', response.cookies)
        self.assertTrue(response.cookies['access_token']['httponly'])

    def test_bad_credentials_land_in_non_field_errors(self):
        response = self.client.post(
            '/api/v1/auth/login/',
            {'phone': '03001112233', 'password': 'wrong'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('non_field_errors', response.json()['errors'])

    def test_blocked_account_message_is_stable(self):
        """The app renders this as its own dead-end state with a support number,
        so the wording is part of the contract."""
        self.user.status = UserStatus.BLOCKED
        self.user.save(update_fields=['status'])
        response = self.client.post(
            '/api/v1/auth/login/',
            {'phone': '03001112233', 'password': 'holderpass123'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn(
            'Account is blocked. Contact support.',
            response.json()['errors']['non_field_errors'],
        )
