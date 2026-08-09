#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
django.setup()

from apps.users.models import User, UserRole

print("Creating test credentials...\n")

# Admin User
admin_phone = '03001234567'
if not User.objects.filter(phone=admin_phone).exists():
    User.objects.create_user(
        phone=admin_phone,
        password='Admin@123',
        full_name='Admin User',
        user_role=UserRole.ADMIN,
        is_staff=True
    )
    print("[OK] ADMIN Created")
else:
    print("[OK] ADMIN already exists")

# Operator User
operator_phone = '03009876543'
if not User.objects.filter(phone=operator_phone).exists():
    User.objects.create_user(
        phone=operator_phone,
        password='Operator@123',
        full_name='Operator User',
        user_role=UserRole.OPERATOR
    )
    print("[OK] OPERATOR Created")
else:
    print("[OK] OPERATOR already exists")

# Customer User
customer_phone = '03005555555'
if not User.objects.filter(phone=customer_phone).exists():
    User.objects.create_user(
        phone=customer_phone,
        password='Customer@123',
        full_name='Customer User',
        user_role=UserRole.USER
    )
    print("[OK] CUSTOMER Created")
else:
    print("[OK] CUSTOMER already exists")

print("\n" + "="*60)
print("[OK] All test credentials ready!")
print("="*60)
