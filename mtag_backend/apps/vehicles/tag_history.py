"""Recording tag<->vehicle installation history (see models.TagAssignment).

Every place that attaches or detaches a tag should call through here, so the
audit trail cannot drift from `tags.vehicle`. Both helpers are idempotent-ish
and never raise into the caller's transaction for history reasons alone: losing
an audit row must not fail a tag assignment a booth operator is waiting on.
"""
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


def close_open_assignment(tag_serial: str, reason: str = '', when=None):
    """Mark the tag's current installation period as ended. Returns it, or None."""
    from .models import TagAssignment

    try:
        current = TagAssignment.objects.filter(
            tag_serial=tag_serial, removed_at__isnull=True
        ).first()
        if current is None:
            return None
        current.removed_at = when or timezone.now()
        current.removed_reason = (reason or '')[:120]
        current.save(update_fields=['removed_at', 'removed_reason', 'updated_at'])
        logger.info("Tag %s removed from %s (%s)",
                    tag_serial, current.plate_number or '?', reason or 'no reason given')
        return current
    except Exception:
        logger.exception("Could not close tag assignment for %s", tag_serial)
        return None


def open_assignment(tag, vehicle, assigned_by=None, notes: str = ''):
    """Record that `tag` is now fitted to `vehicle`.

    Closes any still-open period for this tag first, so the unique constraint
    (one open assignment per tag) always holds and the previous vehicle gets a
    proper removal timestamp instead of an open-ended row.
    """
    from .models import TagAssignment

    try:
        previous = close_open_assignment(
            tag.tag_serial,
            reason=f"reassigned to {vehicle.plate_number}" if vehicle else 'unassigned',
        )
        assignment = TagAssignment.objects.create(
            tag=tag,
            tag_serial=tag.tag_serial,
            vehicle=vehicle,
            plate_number=vehicle.plate_number if vehicle else '',
            assigned_at=timezone.now(),
            assigned_by=assigned_by,
            notes=notes[:255],
        )
        logger.info("Tag %s installed on %s%s", tag.tag_serial,
                    vehicle.plate_number if vehicle else '?',
                    f" (previously {previous.plate_number})" if previous else '')
        return assignment
    except Exception:
        logger.exception("Could not record tag assignment for %s", tag.tag_serial)
        return None


def history_for(tag_serial: str):
    """Full installation history for a tag, newest first."""
    from .models import TagAssignment
    return (TagAssignment.objects
            .filter(tag_serial=tag_serial)
            .select_related('vehicle', 'assigned_by')
            .order_by('-assigned_at'))
