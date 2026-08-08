"""
Replace the generic bus/truck vehicle types with the notification's fare classes.

The toll notification prices 7 distinct classes; the model had 4 (car,
motorcycle, truck, bus). A Large Bus (250) and a Wagon (150) both stored as
'bus' had to share one rate, under- or over-billing every one of them.

Safe to run as a pure AlterField: at the time of writing master holds only
`car` vehicles (verified), and the legacy bus/truck TOLL RATES belong to the old
Malir plaza rows that `manage.py load_plazas --drop-legacy` removes.

If any deployment DOES still hold a 'bus' or 'truck' vehicle, note that choices
are validated by forms/serializers, not by the database — the row survives and
keeps working, but it will not match any rate. Find them with:

    SELECT plate_number, vehicle_type FROM vehicles
     WHERE vehicle_type IN ('bus', 'truck');
"""
from django.db import migrations, models


def warn_on_legacy_types(apps, schema_editor):
    """Fail loudly rather than silently leaving unbillable vehicles behind."""
    Vehicle = apps.get_model('vehicles', 'Vehicle')
    stale = list(
        Vehicle.objects.filter(vehicle_type__in=['bus', 'truck'])
        .values_list('plate_number', 'vehicle_type')[:20]
    )
    if stale:
        raise RuntimeError(
            "Cannot apply 0009: vehicles are still registered as the removed "
            f"generic types: {stale}. Reclassify them into the notification's "
            "fare classes (wagon / coach / large_bus / truck_2axle / "
            "truck_3axle / truck_4axle) first, then re-run migrate."
        )


def noop(apps, schema_editor):
    pass


CHOICES = [
    ('car', 'Car / Jeep / Taxi / Pickup'),
    ('wagon', 'Wagon / Hiace'),
    ('coach', 'Coach / Coaster / Mini Bus'),
    ('large_bus', 'Large Bus'),
    ('truck_2axle', '2 Axle Truck'),
    ('truck_3axle', '3 Axle Truck'),
    ('truck_4axle', '4 or More Axle Truck'),
    ('motorcycle', 'Motorcycle'),
]


class Migration(migrations.Migration):

    dependencies = [
        ('vehicles', '0008_unregisteredinventory_boothinventoryassignment_and_more'),
    ]

    operations = [
        migrations.RunPython(warn_on_legacy_types, noop),
        migrations.AlterField(
            model_name='vehicle',
            name='vehicle_type',
            field=models.CharField(max_length=20, choices=CHOICES),
        ),
        migrations.AlterField(
            model_name='unregisteredinventory',
            name='vehicle_type',
            field=models.CharField(max_length=20, choices=CHOICES, default='car'),
        ),
    ]
