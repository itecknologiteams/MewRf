"""Fare matrix: (from_plaza, to_plaza, category_index) -> fare.

Fares become operator-editable data instead of code. TollRate is intentionally
left in place by this migration — dropping a table that still holds fare history
should be a deliberate, separate step once FareMatrix is populated and verified.
"""
import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tolls', '0008_tollrate_fare_classes'),
        ('vehicles', '0010_vehiclecategory'),
    ]

    operations = [
        migrations.CreateModel(
            name='FareMatrix',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False,
                                        primary_key=True, serialize=False)),
                ('fare', models.DecimalField(decimal_places=2, max_digits=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('from_plaza', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='fares_from', to='tolls.plaza')),
                ('to_plaza', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='fares_to', to='tolls.plaza')),
                ('category', models.ForeignKey(
                    db_column='category_index',
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='fares',
                    to='vehicles.vehiclecategory',
                    to_field='category_index')),
            ],
            options={
                'db_table': 'fare_matrix',
                'verbose_name_plural': 'fare matrix',
            },
        ),
        migrations.AddIndex(
            model_name='farematrix',
            index=models.Index(fields=['from_plaza', 'to_plaza', 'category'],
                               name='idx_fare_from_to_cat'),
        ),
        migrations.AlterUniqueTogether(
            name='farematrix',
            unique_together={('from_plaza', 'to_plaza', 'category')},
        ),
    ]
