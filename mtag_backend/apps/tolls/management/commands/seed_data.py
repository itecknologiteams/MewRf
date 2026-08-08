from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Seed dev data: canonical plazas, PLACEHOLDER rates, test vehicles/tags'

    def handle(self, *args, **kwargs):
        from apps.users.models import User
        from apps.vehicles.models import Vehicle, Tag
        from apps.accounts.models import Account
        from apps.tolls.models import Plaza, TollLane

        self.stdout.write('Seeding data...')

        # ── Users ─────────────────────────────────────────────────────────────
        if not User.objects.filter(phone='03001234567').exists():
            User.objects.create_superuser(
                phone='03001234567', password='Admin@1234', full_name='System Admin'
            )
            self.stdout.write(self.style.SUCCESS('Admin created: 03001234567 / Admin@1234'))

        operator, created = User.objects.get_or_create(
            phone='03009999999',
            defaults={'full_name': 'Plaza Operator', 'user_role': 'operator'}
        )
        if created:
            operator.set_password('Operator@1234')
            operator.save()
            self.stdout.write(self.style.SUCCESS('Operator created: 03009999999 / Operator@1234'))

        user, created = User.objects.get_or_create(
            phone='03111111111',
            defaults={'full_name': 'Test User', 'cnic': '3520112345671'}
        )
        if created:
            user.set_password('Test@1234')
            user.save()

        # ── Plazas — from the canonical operator list ─────────────────────────
        # Shared with `manage.py load_plazas` via plaza_registry so the two can
        # never disagree about which number is which plaza.
        from apps.tolls.plaza_registry import PLAZAS, format_plaza_id

        plazas = []
        for plaza_id, name in PLAZAS:
            p, _ = Plaza.objects.update_or_create(
                plaza_id=plaza_id, defaults={'name': name, 'is_active': True}
            )
            plazas.append(p)
            for lane_no in (1, 2, 3):
                TollLane.objects.get_or_create(plaza=p, lane_number=lane_no)

        self.stdout.write(self.style.SUCCESS(
            f'Plazas ready: {", ".join(format_plaza_id(p.plaza_id) for p in plazas)}'
        ))

        # ── Categories + fares — DEV PLACEHOLDER ONLY ────────────────────────
        # Pricing reads fare_matrix (see services._cached_rate), so seeding the
        # old toll_rates table would leave dev with no usable fares at all.
        #
        # The notified Partial-Length rate is applied FLAT to every plaza pair,
        # because the Partial/Full zone split is still unknown (see
        # fare_registry.SEGMENT). Correct per vehicle class, wrong for any trip
        # that crosses Quaidabad — hence dev only. `load_fares`, the production
        # path, refuses to run until the real zones and Full column are supplied.
        from apps.vehicles.models import VehicleCategory
        from apps.tolls.models import FareMatrix
        from apps.tolls.fare_registry import CATEGORIES, TARIFF as PARTIAL_LENGTH

        categories = {}
        for index, code, cname, cdesc in CATEGORIES:
            cat, _ = VehicleCategory.objects.update_or_create(
                category_index=index,
                defaults={'code': code, 'name': cname,
                          'description': cdesc, 'is_active': True},
            )
            categories[index] = cat

        fare_count = 0
        for entry in plazas:
            for exit_ in plazas:
                if entry.pk == exit_.pk:
                    continue
                for index, cat in categories.items():
                    FareMatrix.objects.update_or_create(
                        from_plaza=entry, to_plaza=exit_, category=cat,
                        defaults={'fare': PARTIAL_LENGTH[index]},
                    )
                    fare_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'{len(categories)} vehicle categories ready'
        ))
        self.stdout.write(self.style.WARNING(
            f'{fare_count} PLACEHOLDER fare_matrix rows (Partial rates applied flat — dev only)'
        ))

        # ── Test vehicles ──────────────────────────────────────────────────────
        from datetime import date
        # NB: tag/account creation is NOT inside `if created:` any more. It used
        # to be, so a re-run against a DB that already had these plates left the
        # vehicle with no tag and no account at all.
        for plate, serial in [('KHI-1001', 'MTAG000001'), ('KHI-1002', 'MTAG000002')]:
            v, _ = Vehicle.objects.get_or_create(
                plate_number=plate,
                defaults={'vehicle_type': 'car', 'owner': user}
            )
            Account.objects.get_or_create(
                vehicle=v, defaults={'user': user, 'balance': '5000.00'}
            )
            tag, _ = Tag.objects.get_or_create(
                tag_serial=serial,
                defaults={'vehicle': v, 'expiry_date': date(2099, 12, 31)},
            )
            # A tag with no tid can never open a barrier — the gate matches on
            # tid, not tag_serial. Give the dev tags a plausible one.
            changed = False
            if tag.vehicle_id is None:
                tag.vehicle = v; changed = True
            if not tag.tid:
                tag.tid = ('E28011' + serial)[:24]; changed = True
            if changed:
                tag.save()

        self.stdout.write(self.style.SUCCESS('Seed complete!'))
        self.stdout.write('')
        self.stdout.write('── Plazas ───────────────────────────────────────')
        for plaza_id, name in PLAZAS:
            self.stdout.write(f'  {format_plaza_id(plaza_id)}  {name}')
        self.stdout.write('')
        self.stdout.write('── Rates ────────────────────────────────────────')
        for index, code, cname, _ in CATEGORIES:
            self.stdout.write(f'  {index}  {cname:<28} {PARTIAL_LENGTH[index]}')
        self.stdout.write('  NOT the operator fare matrix. Do not use on master.')
        self.stdout.write('')
        self.stdout.write('── Credentials ──────────────────────────────────')
        self.stdout.write('  Admin:    03001234567 / Admin@1234')
        self.stdout.write('  Operator: 03009999999 / Operator@1234')
        self.stdout.write('  Test:     03111111111 / Test@1234')
        self.stdout.write('  Tags:     MTAG000001 (KHI-1001), MTAG000002 (KHI-1002)')
