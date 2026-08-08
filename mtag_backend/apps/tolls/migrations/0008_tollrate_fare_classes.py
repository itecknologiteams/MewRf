"""
Widen TollRate.vehicle_type to the notification's 7 fare classes.

Companion to vehicles/0009. TollRate.vehicle_type uses VehicleType.choices, so
it needs the same AlterField or Django reports an unapplied model change forever.

Existing 'bus'/'truck' rate rows belong to the old Malir plazas and are removed
by `manage.py load_plazas --drop-legacy`; this migration deliberately leaves them
alone rather than deleting fare data as a side effect of a schema change.
"""
from django.db import migrations, models

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
        ('tolls', '0007_plaza_id_replaces_code'),
        ('vehicles', '0009_vehicletype_fare_classes'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tollrate',
            name='vehicle_type',
            field=models.CharField(max_length=20, choices=CHOICES),
        ),
    ]
