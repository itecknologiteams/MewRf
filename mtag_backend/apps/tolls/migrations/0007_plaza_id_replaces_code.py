"""
Replace Plaza.code (CharField) with Plaza.plaza_id (unique integer).

Existing rows have no integer to migrate from, so the data step below assigns
one — but deliberately NOT a low number. The operator's real numbering starts at
001 (Shahfaisal Main) and 002 (Kathor Main); if the pre-existing Malir seed rows
took 1..6 here, creating the real plazas afterwards would fail on the unique
constraint. So every pre-existing row is renumbered into a 9000+ LEGACY range,
ordered by its old code for determinism (identical on master and on every booth).

Those legacy rows are then removed by `manage.py load_plazas`, which installs the
real plaza list. Assigning rather than deleting them here keeps this migration
purely mechanical — it never destroys operator data on its own.
"""
from django.db import migrations, models

# Kept in sync with apps/tolls/plaza_registry.LEGACY_PLAZA_ID_BASE. Duplicated as
# a literal because migrations must not import application code — a later edit to
# the registry must never retroactively change what this migration did.
LEGACY_PLAZA_ID_BASE = 9000


def assign_plaza_ids(apps, schema_editor):
    """Give every existing plaza a unique legacy number, ordered by old code.

    Uses queryset .update() rather than model.save(update_fields=...): Django 6.0
    raises Model.NotUpdated when a save with update_fields matches no rows, which
    would abort the whole migration if a row were removed mid-run. .update() is
    also one statement per row instead of a full-model write.
    """
    Plaza = apps.get_model('tolls', 'Plaza')
    pks = list(
        Plaza.objects.filter(plaza_id__isnull=True)
        .order_by('code')
        .values_list('pk', flat=True)
    )
    for offset, pk in enumerate(pks, start=1):
        Plaza.objects.filter(pk=pk).update(plaza_id=LEGACY_PLAZA_ID_BASE + offset)


def restore_codes(apps, schema_editor):
    """Reverse of assign_plaza_ids.

    The original codes cannot be recovered from an integer, so each row gets a
    synthesised placeholder. Every row must end up non-null because the reverse
    of the following AlterField makes `code` NOT NULL again. This reverse exists
    to keep the migration runnable backwards, not to restore the old codes
    faithfully — take a dump before migrating if you need them back.
    """
    Plaza = apps.get_model('tolls', 'Plaza')
    for pk, plaza_id in Plaza.objects.values_list('pk', 'plaza_id'):
        Plaza.objects.filter(pk=pk).update(code=f"P{plaza_id}"[:10])


class Migration(migrations.Migration):

    dependencies = [
        ('tolls', '0006_sync_log_and_trip_updated_at'),
    ]

    operations = [
        # Nullable to start — existing rows have nothing to put here yet.
        migrations.AddField(
            model_name='plaza',
            name='plaza_id',
            field=models.IntegerField(null=True, unique=True),
        ),
        # Make `code` nullable before removing it, so the reverse of the
        # RemoveField below can re-add the column on a non-empty table
        # (re-adding a NOT NULL column with no default would fail).
        migrations.AlterField(
            model_name='plaza',
            name='code',
            field=models.CharField(max_length=10, null=True, unique=True),
        ),
        migrations.RunPython(assign_plaza_ids, restore_codes),
        # Now that every row has a value, enforce NOT NULL.
        migrations.AlterField(
            model_name='plaza',
            name='plaza_id',
            field=models.IntegerField(unique=True),
        ),
        migrations.RemoveField(
            model_name='plaza',
            name='code',
        ),
    ]
