"""Add consumer-app demo data on top of `seed_data`.

`seed_data` gives the test holder two healthy vehicles, which exercises the happy path and
nothing else. This adds the states the M-Tag User App is actually designed around, so every
screen has something real to show:

  * a THIRD vehicle below the Rs. 50 entry minimum -> the urgent "cannot enter" banner
  * a FOURTH vehicle with no tag at all            -> the "No tag fitted" row
  * a toll taken at an OFFLINE booth               -> the "synced from booth" note
  * a transaction with a NULL source               -> the parser's fallback path
  * a completed trip and an ACTIVE one             -> the live trip card
  * a pending top-up                               -> the pending-top-ups panel

Idempotent: safe to re-run.

    python manage.py seed_consumer_demo
"""

from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import (
    Account, Transaction, TransactionSource, TransactionStatus, TransactionType,
)
from apps.payments.models import TopupRequest, TopupStatus
from apps.tolls.models import Plaza, TollTrip, TripStatus
from apps.users.models import User
from apps.vehicles.models import Tag, TagStatus, Vehicle

CONSUMER_PHONE = '03111111111'


class Command(BaseCommand):
    help = 'Add low-balance / no-tag / offline-sync / live-trip demo data for the app.'

    def handle(self, *args, **options):
        try:
            user = User.objects.get(phone=CONSUMER_PHONE)
        except User.DoesNotExist:
            self.stderr.write(
                f'No consumer {CONSUMER_PHONE}. Run `manage.py seed_data` first.'
            )
            return

        plazas = list(Plaza.objects.order_by('plaza_id')[:2])
        if len(plazas) < 2:
            self.stderr.write('Need at least two plazas. Run `manage.py seed_data`.')
            return
        entry, exit_plaza = plazas[0], plazas[1]

        # ── A vehicle the barrier will REFUSE ────────────────────────────────
        # Rs. 42 is below settings.MINIMUM_ACCOUNT_BALANCE, so the app shows the urgent
        # banner naming this plate.
        blocked, _ = Vehicle.objects.get_or_create(
            plate_number='KHI1003',
            defaults={'vehicle_type': 'truck_2axle', 'owner': user},
        )
        blocked_account, _ = Account.objects.get_or_create(
            vehicle=blocked, defaults={'user': user, 'balance': Decimal('42.00')}
        )
        blocked_tag, _ = Tag.objects.get_or_create(
            tag_serial='MTAG000003',
            defaults={
                'vehicle': blocked,
                'expiry_date': date(2099, 12, 31),
                'status': TagStatus.ACTIVE,
            },
        )
        if not blocked_tag.tid:
            blocked_tag.tid = 'E28011MTAG000003'
            blocked_tag.save(update_fields=['tid'])

        # A tag expiring inside the 30-day warning window.
        soon, _ = Vehicle.objects.get_or_create(
            plate_number='KHI1004',
            defaults={'vehicle_type': 'wagon', 'owner': user},
        )
        Account.objects.get_or_create(
            vehicle=soon, defaults={'user': user, 'balance': Decimal('180.00')}
        )
        soon_tag, _ = Tag.objects.get_or_create(
            tag_serial='MTAG000004',
            defaults={
                'vehicle': soon,
                'expiry_date': timezone.localdate() + timedelta(days=12),
                'status': TagStatus.ACTIVE,
            },
        )
        if not soon_tag.tid:
            soon_tag.tid = 'E28011MTAG000004'
            soon_tag.save(update_fields=['tid'])

        # ── A vehicle with NO TAG — a reissue in progress ────────────────────
        # The app shows this as an explicit "No tag fitted" row rather than dropping it.
        untagged, _ = Vehicle.objects.get_or_create(
            plate_number='KHI1005',
            defaults={'vehicle_type': 'car', 'owner': user},
        )
        Account.objects.get_or_create(
            vehicle=untagged, defaults={'user': user, 'balance': Decimal('760.00')}
        )

        # ── Transaction history on the main vehicle ──────────────────────────
        main = Vehicle.objects.filter(owner=user, plate_number='KHI1001').first()
        if main is None:
            main = Vehicle.objects.filter(owner=user).exclude(pk=blocked.pk).first()
        account = Account.objects.filter(vehicle=main).first()
        tag = Tag.objects.filter(vehicle=main).first()

        if account and not account.transactions.exists():
            balance = account.balance
            rows = [
                # (type, amount, source, days_ago)
                (TransactionType.TOPUP, '2000.00', TransactionSource.TOPUP_JAZZCASH, 9),
                (TransactionType.TOLL_DEDUCTION, '150.00', TransactionSource.ONLINE_EXIT, 7),
                # Charged at a booth that was offline and reached the server later — the
                # row the "synced from booth" note exists for.
                (TransactionType.TOLL_DEDUCTION, '250.00',
                 TransactionSource.OFFLINE_EXIT_SYNC, 5),
                (TransactionType.TOPUP, '1000.00', TransactionSource.TOPUP_CASH, 3),
                # source deliberately NULL — several server paths create these.
                (TransactionType.REFUND, '150.00', None, 2),
                (TransactionType.TOLL_DEDUCTION, '100.00',
                 TransactionSource.OFFLINE_EXIT_SYNC, 1),
                (TransactionType.TOLL_DEDUCTION, '150.00', TransactionSource.ONLINE_EXIT, 0),
            ]
            # Walk backwards so balance_before/after form a consistent chain ending at the
            # account's current balance.
            running = balance
            built = []
            for txn_type, amount, source, days_ago in reversed(rows):
                amt = Decimal(amount)
                after = running
                before = after + amt if txn_type == TransactionType.TOLL_DEDUCTION \
                    else after - amt
                built.append((txn_type, amt, source, days_ago, before, after))
                running = before

            for txn_type, amt, source, days_ago, before, after in reversed(built):
                txn = Transaction.objects.create(
                    account=account,
                    tag_serial=tag.tag_serial if tag else '',
                    transaction_type=txn_type,
                    amount=amt,
                    balance_before=before,
                    balance_after=after,
                    status=TransactionStatus.SUCCESS,
                    source=source,
                )
                # processed_at is auto_now_add, so it has to be backdated afterwards.
                Transaction.objects.filter(pk=txn.pk).update(
                    processed_at=timezone.now() - timedelta(days=days_ago, hours=3)
                )

        # ── Trips ────────────────────────────────────────────────────────────
        if account and tag and not TollTrip.objects.filter(vehicle=main).exists():
            completed = TollTrip.objects.create(
                vehicle=main, tag=tag, account=account,
                entry_plaza=entry, exit_plaza=exit_plaza,
                exit_time=timezone.now() - timedelta(days=1, minutes=-42),
                charge_amount=Decimal('150.00'),
                balance_before=account.balance + Decimal('150.00'),
                balance_after=account.balance,
                status=TripStatus.COMPLETED,
            )
            TollTrip.objects.filter(pk=completed.pk).update(
                entry_time=timezone.now() - timedelta(days=1)
            )

        # An ACTIVE trip on the blocked vehicle: entered, not yet exited. Renders as the
        # live card, with null exit/charge fields that are valid data rather than gaps.
        blocked_has_trip = TollTrip.objects.filter(vehicle=blocked).exists()
        if not blocked_has_trip:
            live = TollTrip.objects.create(
                vehicle=blocked, tag=blocked_tag, account=blocked_account,
                entry_plaza=entry, status=TripStatus.ACTIVE,
            )
            TollTrip.objects.filter(pk=live.pk).update(
                entry_time=timezone.now() - timedelta(minutes=37)
            )

        # ── A pending top-up ─────────────────────────────────────────────────
        if account and not TopupRequest.objects.filter(account=account).exists():
            TopupRequest.objects.create(
                account=account, user=user,
                amount=Decimal('500.00'), status=TopupStatus.PENDING,
            )

        self.stdout.write(self.style.SUCCESS('Consumer demo data ready.'))
        self.stdout.write('')
        self.stdout.write(f'  Sign in as:  {CONSUMER_PHONE}  /  Test@1234')
        self.stdout.write('')
        for vehicle in Vehicle.objects.filter(owner=user).order_by('plate_number'):
            acct = Account.objects.filter(vehicle=vehicle).first()
            vtag = Tag.objects.filter(vehicle=vehicle).first()
            self.stdout.write(
                f'  {vehicle.plate_number:<10} '
                f'Rs.{acct.balance if acct else "—":>9}  '
                f'{"tag " + vtag.tag_serial if vtag else "NO TAG"}'
            )
