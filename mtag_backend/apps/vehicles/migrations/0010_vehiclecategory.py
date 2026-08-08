"""Vehicle billing categories — the notification's Column 2 classes as data."""
import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vehicles', '0009_vehicletype_fare_classes'),
    ]

    operations = [
        migrations.CreateModel(
            name='VehicleCategory',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False,
                                        primary_key=True, serialize=False)),
                ('category_index', models.IntegerField(
                    unique=True,
                    help_text='Stable numeric key referenced by fare_matrix.category_index')),
                ('code', models.CharField(
                    max_length=20, unique=True,
                    help_text="Matches Vehicle.vehicle_type, e.g. 'car', 'truck_2axle'")),
                ('name', models.CharField(max_length=100)),
                ('description', models.CharField(blank=True, default='', max_length=255)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'vehicle_categories',
                'ordering': ['category_index'],
                'verbose_name_plural': 'vehicle categories',
            },
        ),
    ]
