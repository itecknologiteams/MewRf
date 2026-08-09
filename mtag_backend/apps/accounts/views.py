import logging
from decimal import Decimal, InvalidOperation
from django.db import transaction as db_transaction
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from utils.response import success_response, error_response
from utils.pagination import StandardPagination
from .models import Account, Transaction, TransactionType, TransactionStatus, TransactionSource
from .serializers import AccountSerializer, TransactionSerializer, TransferSerializer
from .services import TransferService
from .printing import print_topup_receipt
from apps.users.permissions import IsAdmin, IsOperator

logger = logging.getLogger(__name__)


def _norm_tid(value: str) -> str:
    return (value or '').strip().replace(' ', '').upper()


def _receipt_no(txn) -> str:
    """Short, human-readable receipt number derived from the topup transaction."""
    return 'TX-' + str(txn.pk).replace('-', '')[:6].upper()


class TopupLookupView(APIView):
    """Scan-then-verify for the cash topup app. Given a chip TID, return the
    consumer's details if the tag is registered, else found=False (operator will
    register on topup)."""
    permission_classes = [IsOperator]

    def post(self, request):
        from apps.vehicles.models import Tag
        tid = _norm_tid(request.data.get('tid'))
        if not tid:
            return error_response("tid is required")
        tag = (Tag.objects.select_related('vehicle__owner', 'vehicle__account')
               .filter(tid=tid).first())
        if tag and tag.vehicle and getattr(tag.vehicle, 'account', None):
            v = tag.vehicle
            o = v.owner
            a = v.account
            return success_response(data={
                'found': True,
                'tid': tag.tid,
                'epc': tag.epc,
                'consumer_name': o.full_name,
                'cnic': o.cnic or '',
                'phone': o.phone,
                'plate': v.plate_number,
                'balance': str(a.balance),
            })
        # Not registered (unknown tag, or unassigned inventory tag) → register flow.
        from apps.vehicles.models import UnregisteredInventory
        data = {'found': False, 'tid': tid, 'epc': tag.epc if tag else ''}
        inv = UnregisteredInventory.objects.filter(tid=tid).first()
        if inv is not None:
            data['inventory_status'] = inv.status
            data['booth_assigned_id'] = inv.booth_assigned_id
        return success_response(data=data)


class CashTopupView(APIView):
    """Cash topup by chip TID.

    - Registered tag  → add `amount` to its balance (records a TOPUP_CASH txn).
    - New/unassigned  → register the consumer (name/cnic/phone) + a vehicle
                        (auto plate) + activate the tag, with `amount` as the
                        opening balance.
    """
    permission_classes = [IsOperator]

    def post(self, request):
        import secrets
        import string
        from datetime import date
        from django.utils import timezone
        from apps.vehicles.models import (
            Tag, TagStatus, Vehicle, UnregisteredInventory,
            UnregisteredInventoryStatus, TagActivation,
        )
        from apps.users.models import User

        tid = _norm_tid(request.data.get('tid'))
        epc = (request.data.get('epc') or '').strip()
        name = (request.data.get('consumer_name') or '').strip()
        cnic = (request.data.get('cnic') or '').strip()
        phone = (request.data.get('phone') or '').strip()
        plate_raw = (request.data.get('vehicle_reg') or '').strip()
        booth_id = request.data.get('activation_booth_id')
        try:
            booth_id = int(booth_id) if booth_id is not None else None
        except (ValueError, TypeError):
            booth_id = None
        if not tid:
            return error_response("tid is required")
        try:
            amount = Decimal(str(request.data.get('amount'))).quantize(Decimal('0.01'))
        except (InvalidOperation, ValueError, TypeError):
            return error_response("Invalid amount")
        if amount <= 0:
            return error_response("Amount must be greater than zero")

        tag = (Tag.objects.select_related('vehicle__account', 'vehicle__owner')
               .filter(tid=tid).first())

        inv = UnregisteredInventory.objects.filter(tid=tid).first()
        do_booth = booth_id is not None and inv is not None
        if do_booth:
            if inv.status == UnregisteredInventoryStatus.ACTIVATED:
                return error_response("Tag already activated.", status_code=400)
            if inv.booth_assigned_id and inv.booth_assigned_id != booth_id:
                return error_response(
                    f"Tag assigned to Booth {inv.booth_assigned_id}, not Booth {booth_id}.",
                    status_code=400,
                )

        operator_name = getattr(request.user, 'full_name', '') or getattr(request.user, 'phone', '')

        with db_transaction.atomic():
            # ── Existing registered tag → simple topup ──────────────────────
            if tag and tag.vehicle and getattr(tag.vehicle, 'account', None):
                account = Account.objects.select_for_update().get(pk=tag.vehicle.account.pk)
                balance_before = account.balance
                account.balance += amount
                account.save(update_fields=['balance', 'balance_updated_at'])
                txn = Transaction.objects.create(
                    account=account, tag_serial=tag.tag_serial,
                    transaction_type=TransactionType.TOPUP, amount=amount,
                    balance_before=balance_before, balance_after=account.balance,
                    status=TransactionStatus.SUCCESS, source=TransactionSource.TOPUP_CASH,
                )
                logger.info("Cash topup — tid:%s amount:%s new_balance:%s", tid, amount, account.balance)
                resp_data = {
                    'registered': False,
                    'consumer_name': tag.vehicle.owner.full_name,
                    'amount_added': str(amount),
                    'new_balance': str(account.balance),
                }
                resp_msg, resp_status = "Cash topup successful", 200
                receipt = {
                    'receipt_no': _receipt_no(txn),
                    'datetime': timezone.localtime(txn.processed_at).strftime('%d/%m/%Y %H:%M:%S')
                    if getattr(txn, 'processed_at', None) else timezone.localtime().strftime('%d/%m/%Y %H:%M:%S'),
                    'consumer_name': tag.vehicle.owner.full_name,
                    'vehicle_reg': tag.vehicle.plate_number,
                    'tid': tag.tid or tid,
                    'amount': str(amount),
                    'balance_before': str(balance_before),
                    'balance_after': str(account.balance),
                    'payment': 'CASH',
                    'operator': operator_name,
                }
            else:
                # ── New / unassigned tag → register consumer + vehicle + activate ─
                if not name or not phone:
                    return error_response("consumer_name and phone are required to register a new tag")
                import re
                plate = re.sub(r'[\s\-]', '', plate_raw).upper()
                if not plate:
                    return error_response("vehicle_reg (registration number) is required to register a new tag")
                if Vehicle.objects.filter(plate_number=plate).exists():
                    return error_response("A vehicle with this registration number already exists", status_code=409)

                owner = User.objects.filter(phone=phone).first()
                if owner is None:
                    pwd = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
                    owner = User.objects.create_user(phone=phone, password=pwd, full_name=name, cnic=cnic or None)

                vehicle = Vehicle.objects.create(plate_number=plate, vehicle_type='car', owner=owner)

                if tag:  # existing Tag row found by tid — assign + activate
                    tag.vehicle = vehicle
                    if epc:
                        tag.epc = epc
                    tag.status = TagStatus.ACTIVE
                    tag.save()
                elif do_booth:  # inventory tag — create Tag with its printed serial
                    tag = Tag.objects.create(
                        tag_serial=inv.tag_serial, tid=tid, epc=epc or inv.epc, vehicle=vehicle,
                        expiry_date=date(2099, 12, 31), status=TagStatus.ACTIVE,
                    )
                else:    # brand-new tag — create with a generated serial
                    sprefix = timezone.localtime().strftime('%d%m%y%H%M')
                    last = (Tag.objects.filter(tag_serial__startswith=sprefix)
                            .order_by('-tag_serial').values_list('tag_serial', flat=True).first())
                    s = 1
                    if last:
                        try:
                            s = int(last[len(sprefix):]) + 1
                        except (ValueError, TypeError):
                            s = Tag.objects.filter(tag_serial__startswith=sprefix).count() + 1
                    serial = f"{sprefix}{s:04d}"
                    while Tag.objects.filter(tag_serial=serial).exists():
                        s += 1
                        serial = f"{sprefix}{s:04d}"
                    tag = Tag.objects.create(
                        tag_serial=serial, tid=tid, epc=epc, vehicle=vehicle,
                        expiry_date=date(2099, 12, 31), status=TagStatus.ACTIVE,
                    )

                account = Account.objects.create(vehicle=vehicle, user=owner, balance=amount)
                txn = Transaction.objects.create(
                    account=account, tag_serial=tag.tag_serial,
                    transaction_type=TransactionType.TOPUP, amount=amount,
                    balance_before=Decimal('0.00'), balance_after=amount,
                    status=TransactionStatus.SUCCESS, source=TransactionSource.TOPUP_CASH,
                )
                if do_booth:
                    inv.status = UnregisteredInventoryStatus.ACTIVATED
                    inv.activated_for_account = account
                    inv.first_activated_booth_id = booth_id
                    inv.first_activated_at = timezone.now()
                    inv.save(update_fields=[
                        'status', 'activated_for_account',
                        'first_activated_booth_id', 'first_activated_at',
                    ])
                    TagActivation.objects.get_or_create(
                        tag_serial=inv.tag_serial,
                        defaults=dict(
                            tid=tid, first_scan_booth_id=booth_id,
                            first_scan_at=timezone.now(),
                            created_account=account, activation_type='auto_created',
                        ),
                    )
                logger.info("Cash topup + register — tid:%s plate:%s amount:%s", tid, plate, amount)
                resp_data = {
                    'registered': True,
                    'consumer_name': name,
                    'plate': plate,
                    'amount_added': str(amount),
                    'new_balance': str(amount),
                }
                resp_msg, resp_status = "Registered and topped up", 201
                receipt = {
                    'receipt_no': _receipt_no(txn),
                    'datetime': timezone.localtime(txn.processed_at).strftime('%d/%m/%Y %H:%M:%S')
                    if getattr(txn, 'processed_at', None) else timezone.localtime().strftime('%d/%m/%Y %H:%M:%S'),
                    'consumer_name': name,
                    'vehicle_reg': plate,
                    'tid': tag.tid or tid,
                    'amount': str(amount),
                    'balance_before': '0.00',
                    'balance_after': str(amount),
                    'payment': 'CASH',
                    'operator': operator_name,
                }

        # ── Topup committed. Print receipt best-effort (never fails the topup). ─
        resp_data['printed'] = print_topup_receipt(receipt)
        resp_data['receipt'] = receipt
        return success_response(data=resp_data, message=resp_msg, status_code=resp_status)


class AccountDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, vehicle_id):
        try:
            account = Account.objects.select_related('vehicle').get(vehicle_id=vehicle_id)
            return success_response(data=AccountSerializer(account).data)
        except Account.DoesNotExist:
            return error_response("Account not found", status_code=404)


class TransactionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, account_id):
        try:
            account = Account.objects.get(id=account_id)
        except Account.DoesNotExist:
            return error_response("Account not found", status_code=404)

        txns = account.transactions.all()
        txn_type = request.query_params.get('type')
        if txn_type:
            txns = txns.filter(transaction_type=txn_type)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(txns, request)
        return paginator.get_paginated_response(TransactionSerializer(page, many=True).data)


class AdminAccountListView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        accounts = Account.objects.select_related('vehicle', 'user').all()
        return success_response(data=AccountSerializer(accounts, many=True).data)


class TransferView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TransferSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Invalid data", errors=serializer.errors)

        d = serializer.validated_data
        result = TransferService.execute(
            user=request.user,
            source_vehicle_id=str(d['source_vehicle_id']),
            target_vehicle_id=str(d['target_vehicle_id']),
            cnic=d['cnic'],
            phone=d['phone'],
            name=d['name'],
        )

        if not result['success']:
            return error_response(
                result['reason'],
                status_code=result.get('status_code', 400)
            )
        return success_response(data=result, message="Balance transferred successfully")


class OperatorTopupView(APIView):
    permission_classes = [IsOperator]

    def post(self, request):
        tag_serial = request.data.get('tag_serial', '').strip()
        amount_raw = request.data.get('amount')
        if not tag_serial or amount_raw is None:
            return error_response("tag_serial and amount are required")
        try:
            amount = Decimal(str(amount_raw)).quantize(Decimal('0.01'))
            if amount <= 0:
                return error_response("Amount must be greater than zero")
        except (InvalidOperation, ValueError):
            return error_response("Invalid amount")

        from apps.vehicles.models import Tag
        try:
            tag = Tag.objects.select_related('vehicle').get(tag_serial=tag_serial)
        except Tag.DoesNotExist:
            return error_response("Tag not found", status_code=404)

        with db_transaction.atomic():
            account = Account.objects.select_for_update().get(vehicle=tag.vehicle)
            balance_before = account.balance
            account.balance += amount
            account.save(update_fields=['balance', 'balance_updated_at'])
            Transaction.objects.create(
                account=account,
                tag_serial=tag_serial,
                transaction_type=TransactionType.TOPUP,
                amount=amount,
                balance_before=balance_before,
                balance_after=account.balance,
                status=TransactionStatus.SUCCESS,
            )

        logger.info("Operator topup — tag: %s amount: %s new_balance: %s", tag_serial, amount, account.balance)
        return success_response(data={
            'plate_number': tag.vehicle.plate_number,
            'amount_added': str(amount),
            'new_balance': str(account.balance),
        }, message="Balance topped up successfully")


class PlateTopupView(APIView):
    permission_classes = [IsOperator]

    def post(self, request):
        import re
        plate_raw = request.data.get('plate_number', '').strip()
        amount_raw = request.data.get('amount')
        if not plate_raw or amount_raw is None:
            return error_response("plate_number and amount are required")

        plate = re.sub(r'[\s\-]', '', plate_raw).upper()

        try:
            amount = Decimal(str(amount_raw)).quantize(Decimal('0.01'))
            if amount <= 0:
                return error_response("Amount must be greater than zero")
        except (InvalidOperation, ValueError):
            return error_response("Invalid amount")

        from apps.vehicles.models import Vehicle
        try:
            vehicle = Vehicle.objects.get(plate_number=plate)
        except Vehicle.DoesNotExist:
            return error_response("Vehicle not found", status_code=404)

        if not Account.objects.filter(vehicle=vehicle).exists():
            return error_response("No account found for this vehicle", status_code=404)

        with db_transaction.atomic():
            account = Account.objects.select_for_update().get(vehicle=vehicle)
            balance_before = account.balance
            account.balance += amount
            account.save(update_fields=['balance', 'balance_updated_at'])
            tag_serial = getattr(getattr(vehicle, 'tag', None), 'tag_serial', '')
            Transaction.objects.create(
                account=account,
                tag_serial=tag_serial,
                transaction_type=TransactionType.TOPUP,
                amount=amount,
                balance_before=balance_before,
                balance_after=account.balance,
                status=TransactionStatus.SUCCESS,
            )

        logger.info("Plate topup — plate: %s amount: %s new_balance: %s", plate, amount, account.balance)
        return success_response(data={
            'plate_number': vehicle.plate_number,
            'vehicle_type': vehicle.vehicle_type,
            'amount_added': str(amount),
            'balance_before': str(balance_before),
            'new_balance': str(account.balance),
        }, message="Balance updated successfully")
