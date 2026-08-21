import csv
import io
import logging
from datetime import date
from django.db import IntegrityError
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser
from utils.response import success_response, error_response
from .models import Vehicle, Tag, TagStatus, UnregisteredInventory, UnregisteredInventoryStatus, TagActivation
from .serializers import (
    VehicleSerializer, VehicleCreateSerializer, TagSerializer, TagReissueSerializer, normalize_plate,
    MyVehicleSerializer,
    UnregisteredInventorySerializer, UnregisteredInventoryListSerializer, BoothAssignmentSerializer,
    TagActivationQuickCreateSerializer, TagActivationLinkExistingSerializer, TagActivationSerializer
)
from apps.users.permissions import IsOperator, IsAdmin, is_privileged, scope_to_owner

logger = logging.getLogger(__name__)


class VehicleListCreateView(APIView):
    permission_classes = [IsOperator]

    def get(self, request):
        vehicles = Vehicle.objects.select_related('tag', 'owner').all().order_by('-registered_at')
        plate = request.query_params.get('plate')
        if plate:
            vehicles = vehicles.filter(plate_number__icontains=normalize_plate(plate))
        return success_response(data=VehicleSerializer(vehicles, many=True).data)

    def post(self, request):
        serializer = VehicleCreateSerializer(data=request.data)
        if serializer.is_valid():
            vehicle = serializer.save()
            logger.info("Vehicle registered: %s", vehicle.plate_number)
            return success_response(
                data=VehicleSerializer(vehicle).data,
                message="Vehicle registered successfully",
                status_code=201
            )
        return error_response("Registration failed", errors=serializer.errors)


class MyVehicleListView(APIView):
    """GET /vehicles/my/ — everything the authenticated tag holder owns.

    The consumer app's bootstrap call. `GET /vehicles/` is IsOperator, so before
    this existed a tag holder had no way at all to enumerate their own vehicles:
    they would have had to already know the ids they were looking for.

    Vehicles with no tag are returned with tag=null rather than dropped — a tag
    reissue in progress is exactly the state a worried holder opens the app to
    check, so hiding the vehicle would be the wrong answer.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        vehicles = (
            Vehicle.objects
            .select_related('tag', 'account')
            .filter(owner=request.user)
            .order_by('-registered_at')
        )
        return success_response(data=MyVehicleSerializer(vehicles, many=True).data)


class VehicleDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            vehicle = scope_to_owner(
                Vehicle.objects.select_related('tag', 'owner'), request.user
            ).get(pk=pk)
            return success_response(data=VehicleSerializer(vehicle).data)
        except Vehicle.DoesNotExist:
            return error_response("Vehicle not found", status_code=404)

    def patch(self, request, pk):
        # Editing a vehicle is an operator action, not a self-service one.
        # vehicle_type IS the fare class, so a consumer allowed to patch their own
        # vehicle could re-declare a 4-axle truck as a car and pay car fares — a
        # revenue hole, not merely a data-integrity one. plate_number is equally
        # load-bearing: it is what an ANPR dispute is resolved against.
        if not is_privileged(request.user):
            return error_response(
                "Vehicle details can only be changed by an operator. "
                "Contact support to correct your vehicle record.",
                status_code=403,
            )
        try:
            vehicle = Vehicle.objects.get(pk=pk)
            serializer = VehicleSerializer(vehicle, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return success_response(data=serializer.data, message="Vehicle updated")
            return error_response("Update failed", errors=serializer.errors)
        except Vehicle.DoesNotExist:
            return error_response("Vehicle not found", status_code=404)


class VehicleByPlateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, plate_number):
        try:
            vehicle = scope_to_owner(
                Vehicle.objects.select_related('tag', 'owner'), request.user
            ).get(plate_number=normalize_plate(plate_number))
            return success_response(data=VehicleSerializer(vehicle).data)
        except Vehicle.DoesNotExist:
            return error_response("Vehicle not found", status_code=404)


class TagReissueView(APIView):
    permission_classes = [IsOperator]

    def post(self, request, vehicle_id):
        try:
            vehicle = Vehicle.objects.get(pk=vehicle_id)
        except Vehicle.DoesNotExist:
            return error_response("Vehicle not found", status_code=404)

        serializer = TagReissueSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Invalid data", errors=serializer.errors)

        from datetime import date
        new_serial = serializer.validated_data['tag_serial']

        from apps.vehicles.tag_history import close_open_assignment, open_assignment

        # Deactivate the vehicle's current tag
        old_tag = Tag.objects.filter(vehicle=vehicle).first()
        if old_tag:
            old_tag.vehicle = None
            old_tag.status = TagStatus.DEACTIVATED
            old_tag.save()
            # Close its history period so the old tag shows when it came off
            # this vehicle, rather than an open-ended row.
            close_open_assignment(
                old_tag.tag_serial,
                reason=f"reissued; replaced by {new_serial}",
            )

        # Assign the unassigned inventory tag to this vehicle
        new_tag = Tag.objects.get(tag_serial=new_serial, vehicle__isnull=True)
        new_tag.vehicle = vehicle
        new_tag.expiry_date = date(2099, 12, 31)
        new_tag.status = TagStatus.ACTIVE
        new_tag.save()
        open_assignment(
            new_tag, vehicle,
            assigned_by=getattr(request, 'user', None),
            notes=f"reissue, replaced {old_tag.tag_serial}" if old_tag else 'reissue',
        )

        logger.info("Tag reissued for vehicle %s — old deactivated, new serial %s", vehicle.plate_number, new_serial)
        return success_response(
            data=TagSerializer(new_tag).data,
            message="Tag reissued successfully",
            status_code=201,
        )


class AvailableTagsView(APIView):
    permission_classes = [IsOperator]

    def get(self, request):
        search = request.query_params.get('search', '').strip()
        qs = Tag.objects.filter(
            vehicle__isnull=True,
            status=TagStatus.ACTIVE,
        ).order_by('tag_serial')
        if search:
            qs = qs.filter(tag_serial__icontains=search)
        tags = qs.values('id', 'tag_serial', 'epc')[:20]
        return success_response(data=list(tags))


class TagCreateView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request):
        tag_serial = request.data.get('tag_serial', '').strip()
        epc = request.data.get('epc', '').strip()
        # tid = chip TID (gate lookup key). Normalize like the reader does.
        # Empty -> NULL (the column is UNIQUE; '' would collide across tags).
        tid = request.data.get('tid', '').strip().replace(' ', '').upper() or None
        if not tag_serial:
            return error_response("tag_serial is required")
        if Tag.objects.filter(tag_serial=tag_serial).exists():
            return error_response("A tag with this serial already exists", status_code=409)
        if tid and Tag.objects.filter(tid=tid).exists():
            return error_response("A tag with this TID already exists", status_code=409)
        tag = Tag.objects.create(
            tag_serial=tag_serial,
            tid=tid,
            epc=epc,
            vehicle=None,
            expiry_date=date(2099, 12, 31),
            status=TagStatus.ACTIVE,
        )
        logger.info("Single tag added: serial=%s tid=%s", tag_serial, tid)
        return success_response(
            data={'id': tag.id, 'tag_serial': tag.tag_serial, 'tid': tag.tid, 'epc': tag.epc},
            message="Tag added to inventory",
            status_code=201,
        )


class TagBulkCreateView(APIView):
    """Bulk-insert inventory tags directly to the DB.

    Each tag: tid (required, unique) + epc (optional), status = DEACTIVATED,
    not assigned to any vehicle. tag_serial is auto-generated as
    DDMMYYHHMM + 4-digit sequence (per-minute), unique.
    """
    permission_classes = [IsAdmin]

    def post(self, request):
        rows = request.data.get('tags', [])
        if not isinstance(rows, list) or not rows:
            return error_response("'tags' must be a non-empty list of {tid, epc}")

        prefix = timezone.localtime().strftime('%d%m%y%H%M')
        # Continue the sequence after the highest existing serial for this minute.
        last = (
            Tag.objects.filter(tag_serial__startswith=prefix)
            .order_by('-tag_serial').values_list('tag_serial', flat=True).first()
        )
        seq = 1
        if last:
            try:
                seq = int(last[len(prefix):]) + 1
            except (ValueError, TypeError):
                seq = Tag.objects.filter(tag_serial__startswith=prefix).count() + 1

        added, skipped, errors, results = [], [], [], []
        seen = set()

        for i, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                errors.append({'row': i, 'error': 'invalid row'})
                continue
            tid = (row.get('tid') or '').strip().replace(' ', '').upper()
            epc = (row.get('epc') or '').strip()
            if not tid:
                errors.append({'row': i, 'error': 'tid is required'})
                continue
            if tid in seen or Tag.objects.filter(tid=tid).exists():
                skipped.append(tid)
                continue
            seen.add(tid)

            # Find a free serial for this minute.
            serial = f"{prefix}{seq:04d}"
            seq += 1
            while Tag.objects.filter(tag_serial=serial).exists():
                serial = f"{prefix}{seq:04d}"
                seq += 1

            try:
                Tag.objects.create(
                    tag_serial=serial,
                    tid=tid,
                    epc=epc,
                    vehicle=None,
                    expiry_date=date(2099, 12, 31),
                    status=TagStatus.DEACTIVATED,
                )
                added.append(tid)
                results.append({'tid': tid, 'tag_serial': serial, 'epc': epc, 'status': 'deactivated'})
            except IntegrityError:
                skipped.append(tid)

        logger.info("Bulk tag insert: %d added, %d skipped, %d errors", len(added), len(skipped), len(errors))
        return success_response(
            data={'added': len(added), 'skipped': len(skipped), 'errors': errors, 'results': results},
            message=f"{len(added)} tag(s) added",
            status_code=201,
        )


class ScanDebugView(APIView):
    """TEMPORARY: logs whatever the device/AppCenter app sends, so we can learn
    its exact payload format + headers. Point the device's upload URL here, scan
    one tag, then check the server console. Remove after the format is known."""
    permission_classes = [AllowAny]

    def _log(self, request):
        try:
            raw = request.body.decode('utf-8', errors='replace')
        except Exception:
            raw = '<unreadable>'
        hdrs = {k[5:]: v for k, v in request.META.items() if k.startswith('HTTP_')}
        logger.warning(
            "[scan-debug] %s %s\n  content-type: %s\n  query: %s\n  headers: %s\n  body: %s",
            request.method, request.get_full_path(),
            request.content_type, dict(request.query_params), hdrs, raw,
        )

    def post(self, request):
        self._log(request)
        return success_response(data={'received': True}, message="logged")

    def get(self, request):
        self._log(request)
        return success_response(data={'received': True}, message="logged")


class TagExistsCheckView(APIView):
    """Given a list of TIDs, return which ones already exist in the DB.
    Used by the scanner app to validate before bulk-insert."""
    permission_classes = [IsAdmin]

    def post(self, request):
        tids = request.data.get('tids', [])
        if not isinstance(tids, list):
            return error_response("'tids' must be a list")
        norm = [(t or '').strip().replace(' ', '').upper() for t in tids]
        norm = [t for t in norm if t]
        existing = list(
            Tag.objects.filter(tid__in=norm).values_list('tid', flat=True)
        )
        return success_response(data={'existing': existing})


class TagScanBufferView(APIView):
    """Transient scan buffer for handheld scanning sessions (per admin user).

    POST   {tid, epc}  → add a detected tag to the buffer (dedup by tid)
    GET                → current buffer { count, tags:[{tid, epc, scanned_at}] }
    DELETE             → clear the buffer

    The WiFi RFID device posts each scan to POST; the web app polls GET to show
    a live list + count, then bulk-inserts. (Device-side auth for POST is handled
    separately once the device is known — for now it uses the same admin auth.)
    """
    permission_classes = [IsAdmin]

    def post(self, request):
        from .models import ScanBuffer
        tid = (request.data.get('tid') or '').strip().replace(' ', '').upper()
        epc = (request.data.get('epc') or '').strip()
        if not tid:
            return error_response("tid is required")
        ScanBuffer.objects.update_or_create(
            user=request.user, tid=tid, defaults={'epc': epc}
        )
        count = ScanBuffer.objects.filter(user=request.user).count()
        return success_response(data={'tid': tid, 'count': count}, message="scanned")

    def get(self, request):
        from .models import ScanBuffer
        qs = ScanBuffer.objects.filter(user=request.user)
        tags = [
            {'tid': s.tid, 'epc': s.epc, 'scanned_at': s.scanned_at.isoformat()}
            for s in qs
        ]
        return success_response(data={'count': len(tags), 'tags': tags})

    def delete(self, request):
        from .models import ScanBuffer
        deleted, _ = ScanBuffer.objects.filter(user=request.user).delete()
        return success_response(data={'cleared': deleted}, message="buffer cleared")


class VehicleSuspendView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, pk):
        try:
            vehicle = Vehicle.objects.select_related('tag').get(pk=pk)
        except Vehicle.DoesNotExist:
            return error_response("Vehicle not found", status_code=404)

        from .models import VehicleStatus
        action = request.data.get('action')
        if action == 'suspend':
            vehicle.status = VehicleStatus.SUSPENDED
            vehicle.save(update_fields=['status'])
            tag = getattr(vehicle, 'tag', None)
            if tag:
                tag.status = TagStatus.SUSPENDED
                tag.save(update_fields=['status'])
        elif action == 'activate':
            vehicle.status = VehicleStatus.ACTIVE
            vehicle.save(update_fields=['status'])
            tag = getattr(vehicle, 'tag', None)
            if tag:
                tag.status = TagStatus.ACTIVE
                tag.save(update_fields=['status'])
        else:
            return error_response("action must be 'suspend' or 'activate'")

        logger.info("Vehicle %s — action: %s", vehicle.plate_number, action)
        return success_response(data=VehicleSerializer(vehicle).data, message=f"Vehicle {action}d successfully")


class TagInventoryUploadView(APIView):
    permission_classes = [IsAdmin]
    parser_classes = [MultiPartParser]

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return error_response("No file uploaded.", status_code=400)
        if not file.name.lower().endswith('.csv'):
            return error_response("File must be a CSV.", status_code=400)

        try:
            content = file.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            return error_response("File encoding not supported. Use UTF-8.", status_code=400)

        reader = csv.DictReader(io.StringIO(content))
        existing = set(Tag.objects.values_list('tag_serial', flat=True))
        to_create, added, skipped, row_errors = [], [], [], []

        for i, row in enumerate(reader, start=2):
            serial = (row.get('TID') or '').strip()
            epc = (row.get('EPC') or '').strip()
            if not serial:
                row_errors.append(f"Row {i}: missing TID")
                continue
            if serial in existing:
                skipped.append(serial)
                continue
            existing.add(serial)
            to_create.append(Tag(
                tag_serial=serial,
                epc=epc,
                vehicle=None,
                expiry_date=date(2099, 12, 31),
                status=TagStatus.ACTIVE,
            ))
            added.append(serial)

        Tag.objects.bulk_create(to_create)
        logger.info("Tag CSV upload: %d added, %d skipped", len(added), len(skipped))

        return success_response(
            data={
                'added': len(added),
                'skipped': len(skipped),
                'errors': row_errors,
                'skipped_serials': skipped,
            },
            message=f"{len(added)} tag(s) added, {len(skipped)} already existed.",
            status_code=201,
        )


# ============= Inventory Management API Views =============

class InventoryUploadView(APIView):
    """Bulk upload unregistered inventory from CSV."""
    permission_classes = [IsAdmin]
    parser_classes = [MultiPartParser]

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return error_response("No file uploaded.", status_code=400)
        if not file.name.lower().endswith('.csv'):
            return error_response("File must be a CSV.", status_code=400)

        try:
            content = file.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            return error_response("File encoding not supported. Use UTF-8.", status_code=400)

        reader = csv.DictReader(io.StringIO(content))
        existing_serials = set(UnregisteredInventory.objects.values_list('tag_serial', flat=True))
        existing_tids = set(UnregisteredInventory.objects.values_list('tid', flat=True))
        to_create, added, skipped, row_errors = [], [], [], []

        for i, row in enumerate(reader, start=2):
            tag_serial = (row.get('tag_serial') or '').strip()
            tid = (row.get('tid') or '').strip()
            epc = (row.get('epc') or '').strip()
            vehicle_plate = (row.get('vehicle_plate') or '').strip()
            vehicle_type = (row.get('vehicle_type') or 'car').strip()
            vehicle_color = (row.get('vehicle_color') or '').strip()

            if not tag_serial:
                row_errors.append(f"Row {i}: missing tag_serial")
                continue
            if not tid:
                row_errors.append(f"Row {i}: missing tid")
                continue

            if tag_serial in existing_serials or tid in existing_tids:
                skipped.append(tag_serial)
                continue

            existing_serials.add(tag_serial)
            existing_tids.add(tid)

            to_create.append(UnregisteredInventory(
                tag_serial=tag_serial,
                tid=tid,
                epc=epc,
                vehicle_plate=vehicle_plate,
                vehicle_type=vehicle_type,
                vehicle_color=vehicle_color,
                status=UnregisteredInventoryStatus.UNREGISTERED,
            ))
            added.append(tag_serial)

        UnregisteredInventory.objects.bulk_create(to_create, batch_size=500)
        logger.info("Inventory CSV upload: %d added, %d skipped", len(added), len(skipped))

        return success_response(
            data={
                'added': len(added),
                'skipped': len(skipped),
                'errors': row_errors,
                'skipped_serials': skipped,
            },
            message=f"{len(added)} tag(s) added, {len(skipped)} duplicates.",
            status_code=201,
        )


class InventoryListView(APIView):
    """List unregistered inventory with filtering."""
    permission_classes = [IsOperator]

    def get(self, request):
        from .serializers import UnregisteredInventoryListSerializer
        qs = UnregisteredInventory.objects.all()

        status = request.query_params.get('status')
        if status:
            qs = qs.filter(status=status)

        booth_id = request.query_params.get('booth_assigned_id')
        if booth_id:
            try:
                qs = qs.filter(booth_assigned_id=int(booth_id))
            except (ValueError, TypeError):
                pass

        vehicle_type = request.query_params.get('vehicle_type')
        if vehicle_type:
            qs = qs.filter(vehicle_type=vehicle_type)

        search = request.query_params.get('search')
        if search:
            qs = qs.filter(tag_serial__icontains=search) | qs.filter(tid__icontains=search)

        page = int(request.query_params.get('page', 1))
        per_page = int(request.query_params.get('per_page', 100))
        start = (page - 1) * per_page
        end = start + per_page

        total = qs.count()
        items = qs[start:end]

        return success_response(
            data={
                'items': UnregisteredInventoryListSerializer(items, many=True).data,
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': (total + per_page - 1) // per_page,
            }
        )


class BoothAssignmentView(APIView):
    """Assign unregistered inventory to a specific booth."""
    permission_classes = [IsAdmin]

    def post(self, request):
        from .serializers import BoothAssignmentSerializer, BoothInventoryAssignment
        serializer = BoothAssignmentSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors, status_code=400)

        inventory_ids = serializer.validated_data['inventory_ids']
        booth_id = serializer.validated_data['booth_id']
        assigned_by = serializer.validated_data.get('assigned_by', request.user.phone or 'system')

        try:
            inventories = UnregisteredInventory.objects.filter(id__in=inventory_ids)
            if not inventories.exists():
                return error_response("No inventory found for given IDs.", status_code=404)

            assigned_count = 0
            for inv in inventories:
                inv.booth_assigned_id = booth_id
                inv.booth_assigned_at = timezone.now()
                inv.status = UnregisteredInventoryStatus.BOOTH_ASSIGNED
                inv.save()

                BoothInventoryAssignment.objects.create(
                    inventory=inv,
                    booth_id=booth_id,
                    assigned_by=assigned_by,
                )
                assigned_count += 1

            logger.info("Assigned %d inventory items to booth %d", assigned_count, booth_id)
            return success_response(
                data={
                    'assigned': assigned_count,
                    'booth_id': booth_id,
                },
                message=f"{assigned_count} tag(s) assigned to Booth {booth_id}.",
                status_code=200,
            )
        except Exception as e:
            logger.error("Error assigning inventory: %s", str(e))
            return error_response(f"Assignment failed: {str(e)}", status_code=500)


class TagActivationQuickCreateView(APIView):
    """Quick activation: create new account and activate tag."""
    permission_classes = [IsOperator]

    def post(self, request):
        from .serializers import TagActivationQuickCreateSerializer
        from apps.users.models import User
        from apps.accounts.models import Account
        serializer = TagActivationQuickCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors, status_code=400)

        tag_serial = serializer.validated_data['tag_serial']
        tid = serializer.validated_data['tid']
        customer_name = serializer.validated_data['customer_name']
        customer_phone = serializer.validated_data['customer_phone']
        initial_topup = serializer.validated_data.get('initial_topup', 0)
        payment_method = serializer.validated_data.get('payment_method', 'CASH')
        activation_booth_id = serializer.validated_data['activation_booth_id']

        try:
            from django.db import transaction
            from apps.vehicles.tag_history import close_open_assignment, open_assignment

            with transaction.atomic():
                inv = UnregisteredInventory.objects.get(tag_serial=tag_serial, tid=tid)

                if inv.status == UnregisteredInventoryStatus.ACTIVATED:
                    return error_response("Tag already activated.", status_code=400)

                if inv.booth_assigned_id and inv.booth_assigned_id != activation_booth_id:
                    return error_response(
                        f"Tag assigned to Booth {inv.booth_assigned_id}, not Booth {activation_booth_id}.",
                        status_code=400
                    )

                phone_parts = customer_phone.replace('+', '').replace(' ', '')
                user_or_none = User.objects.filter(phone__in=[customer_phone, phone_parts[-10:] if len(phone_parts) > 10 else phone_parts]).first()

                if user_or_none:
                    user = user_or_none
                else:
                    # password is a required positional on the manager. A booth
                    # walk-up customer never logs in, so give them an unusable
                    # password rather than omitting the argument — which raised
                    # TypeError and 500'd every activation for a new customer.
                    user = User.objects.create_user(
                        phone=customer_phone,
                        password=None,
                        full_name=customer_name,
                    )

                vehicle = Vehicle.objects.create(
                    owner=user,
                    plate_number=inv.vehicle_plate or f"{tag_serial}",
                    vehicle_type=inv.vehicle_type or 'car',
                )

                # The barrier matches on tags.tid, so activation has to create a
                # real Tag row. Without it this endpoint returned 201 "activated"
                # while the vehicle was refused at the gate with "Tag not found".
                tag = Tag.objects.create(
                    tag_serial=inv.tag_serial,
                    tid=tid,
                    epc=inv.epc or '',
                    vehicle=vehicle,
                    expiry_date=date(2099, 12, 31),
                    status=TagStatus.ACTIVE,
                )
                open_assignment(tag, vehicle,
                                notes=f'activated at booth {activation_booth_id}')

                account = Account.objects.create(user=user, vehicle=vehicle, balance=initial_topup)

                inv.status = UnregisteredInventoryStatus.ACTIVATED
                inv.activated_for_account = account
                inv.first_activated_booth_id = activation_booth_id
                inv.first_activated_at = timezone.now()
                inv.save()

                TagActivation.objects.create(
                    tag_serial=tag_serial,
                    tid=tid,
                    first_scan_booth_id=activation_booth_id,
                    first_scan_at=timezone.now(),
                    created_account=account,
                    activation_type='auto_created',
                )

                logger.info("Tag %s activated at Booth %d, account created for %s", tag_serial, activation_booth_id, customer_name)

                from .serializers import UnregisteredInventorySerializer
                return success_response(
                    data=UnregisteredInventorySerializer(inv).data,
                    message=f"Tag activated for {customer_name}",
                    status_code=201,
                )

        except UnregisteredInventory.DoesNotExist:
            return error_response(f"Tag {tag_serial} not found in inventory.", status_code=404)
        except Exception as e:
            logger.error("Error activating tag: %s", str(e))
            return error_response(f"Activation failed: {str(e)}", status_code=500)


class TagActivationLinkExistingView(APIView):
    """Link tag to existing account."""
    permission_classes = [IsOperator]

    def post(self, request):
        from .serializers import TagActivationLinkExistingSerializer
        from apps.accounts.models import Account
        serializer = TagActivationLinkExistingSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors, status_code=400)

        tag_serial = serializer.validated_data['tag_serial']
        tid = serializer.validated_data['tid']
        account_id = serializer.validated_data['account_id']
        activation_booth_id = serializer.validated_data['activation_booth_id']

        try:
            from django.db import transaction
            from apps.vehicles.tag_history import close_open_assignment, open_assignment

            with transaction.atomic():
                inv = UnregisteredInventory.objects.get(tag_serial=tag_serial, tid=tid)

                if inv.status == UnregisteredInventoryStatus.ACTIVATED:
                    return error_response("Tag already activated.", status_code=400)

                if inv.booth_assigned_id and inv.booth_assigned_id != activation_booth_id:
                    return error_response(
                        f"Tag assigned to Booth {inv.booth_assigned_id}, not Booth {activation_booth_id}.",
                        status_code=400
                    )

                account = Account.objects.get(id=account_id)
                vehicle = account.vehicle

                # Same as the quick-create path: the gate matches on tags.tid, so
                # linking has to produce a Tag row. Replacing the vehicle's
                # current tag is a tag swap, so close its history period first.
                old_tag = Tag.objects.filter(vehicle=vehicle).first()
                if old_tag and old_tag.tid != tid:
                    close_open_assignment(
                        old_tag.tag_serial,
                        reason=f'replaced by {inv.tag_serial} at booth {activation_booth_id}',
                    )
                    old_tag.vehicle = None
                    old_tag.status = TagStatus.DEACTIVATED
                    old_tag.save()

                tag, _ = Tag.objects.update_or_create(
                    tid=tid,
                    defaults={
                        'tag_serial': inv.tag_serial,
                        'epc': inv.epc or '',
                        'vehicle': vehicle,
                        'expiry_date': date(2099, 12, 31),
                        'status': TagStatus.ACTIVE,
                    },
                )
                open_assignment(tag, vehicle,
                                notes=f'linked at booth {activation_booth_id}')

                inv.status = UnregisteredInventoryStatus.ACTIVATED
                inv.activated_for_account = account
                inv.first_activated_booth_id = activation_booth_id
                inv.first_activated_at = timezone.now()
                inv.save()

                TagActivation.objects.create(
                    tag_serial=tag_serial,
                    tid=tid,
                    first_scan_booth_id=activation_booth_id,
                    first_scan_at=timezone.now(),
                    created_account=account,
                    activation_type='linked',
                )

                logger.info("Tag %s linked to account %s at Booth %d", tag_serial, account_id, activation_booth_id)

                from .serializers import UnregisteredInventorySerializer
                return success_response(
                    data=UnregisteredInventorySerializer(inv).data,
                    message="Tag linked to existing account",
                    status_code=200,
                )

        except UnregisteredInventory.DoesNotExist:
            return error_response(f"Tag {tag_serial} not found in inventory.", status_code=404)
        except Account.DoesNotExist:
            return error_response(f"Account {account_id} not found.", status_code=404)
        except Exception as e:
            logger.error("Error linking tag: %s", str(e))
            return error_response(f"Linking failed: {str(e)}", status_code=500)


class InventoryCheckView(APIView):
    """Check if a tag is in unregistered inventory and get its status."""
    permission_classes = [IsOperator]

    def get(self, request, tag_serial):
        try:
            inv = UnregisteredInventory.objects.get(tag_serial=tag_serial)

            return success_response(
                data={
                    'found': True,
                    'tid': inv.tid,
                    'status': inv.status,
                    'booth_assigned_id': inv.booth_assigned_id,
                    'first_activated_booth_id': inv.first_activated_booth_id,
                    'vehicle_plate': inv.vehicle_plate,
                    'vehicle_type': inv.vehicle_type,
                    'can_activate': inv.status == UnregisteredInventoryStatus.BOOTH_ASSIGNED,
                    'activation_required': inv.status != UnregisteredInventoryStatus.ACTIVATED,
                }
            )
        except UnregisteredInventory.DoesNotExist:
            return success_response(
                data={
                    'found': False,
                    'status': 'not_in_inventory',
                    'activation_required': False,
                }
            )
