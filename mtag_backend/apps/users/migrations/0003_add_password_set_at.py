from django.db import migrations, models


def backfill(apps, schema_editor):
    """Anyone who has successfully logged in demonstrably knows their password.

    Without this, every existing account starts as "never set a password", and the app would
    send a verification code to people who have been signing in for months.

    `last_login_at` is the evidence: it is written only by LoginSerializer, and only after a
    successful `authenticate()`. Booth-created accounts nobody has ever signed into stay
    NULL — which is exactly the set that needs the setup flow.
    """
    User = apps.get_model('users', 'User')
    User.objects.filter(last_login_at__isnull=False).update(
        password_set_at=models.F('last_login_at')
    )


def unbackfill(apps, schema_editor):
    apps.get_model('users', 'User').objects.update(password_set_at=None)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_phoneotp'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='password_set_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill, unbackfill),
    ]
