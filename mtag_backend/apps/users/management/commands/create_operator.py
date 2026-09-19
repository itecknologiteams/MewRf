"""Create a booth operator account for the web portal.

Operators sign in to the portal with phone + password and see only the ME-Tag
Registration page. There is no UI for making one, so this is the way to do it on
any machine — local, master or booth:

    python manage.py create_operator --phone 03001234567 --name "Ali Khan"

The password is prompted for (twice) so it stays out of shell history. Pass
--password only for scripts.

`password_set_at` is deliberately left unset: it records a password the user
chose themselves (see User.password_set_at), and this one was chosen for them.
The portal login does not consult it.
"""

import getpass
import re

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.users.models import User, UserRole
from apps.users.otp_service import normalize_phone

PHONE_RE = re.compile(r'^03\d{9}$')


class Command(BaseCommand):
    help = 'Create an operator account (phone + password login for the web portal).'

    def add_arguments(self, parser):
        parser.add_argument('--phone', required=True, help='Login phone, e.g. 03001234567.')
        parser.add_argument('--name', required=True, help='Full name shown in the portal.')
        parser.add_argument(
            '--password',
            help='Password. Omit to be prompted, which keeps it out of shell history.',
        )

    def handle(self, *args, **options):
        phone = normalize_phone(options['phone'])
        if not PHONE_RE.match(phone):
            raise CommandError(
                f'"{options["phone"]}" is not a valid phone number. Use 03XXXXXXXXX '
                '(the portal login rejects any other format).'
            )

        name = options['name'].strip()
        if not name:
            raise CommandError('--name cannot be blank.')

        existing = User.objects.filter(phone=phone).first()
        if existing:
            raise CommandError(
                f'{phone} already belongs to {existing.full_name} (role: {existing.user_role}). '
                'Change their role from the admin User Management page instead.'
            )

        password = options['password']
        if password is None:
            password = getpass.getpass('Password: ')
            if password != getpass.getpass('Password (again): '):
                raise CommandError('Passwords did not match.')

        try:
            validate_password(password, User(phone=phone, full_name=name))
        except ValidationError as exc:
            raise CommandError('Password rejected: ' + ' '.join(exc.messages))

        User.objects.create_user(
            phone=phone,
            password=password,
            full_name=name,
            user_role=UserRole.OPERATOR,
        )
        self.stdout.write(self.style.SUCCESS(f'Operator created: {name} ({phone})'))
        self.stdout.write('They can now sign in to the portal with that phone and password.')
