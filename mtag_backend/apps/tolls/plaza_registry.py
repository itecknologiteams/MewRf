"""
Canonical plaza list — the operator-assigned numbering, in one place.

Single source of truth for `manage.py load_plazas` and `manage.py seed_data`, so
the two can never drift apart and disagree about which number is which plaza.

plaza_id is stored as an INTEGER, so the operator's leading zeros ("001") are a
display concern, not a storage one — 001 is stored as 1 and rendered by
format_plaza_id(). Numbering scheme: main toll plazas are 001-099, interchanges
are 101+.

NOTE: 105 and 106 are both named "Quaidabad Interchange" — that is intentional
per the operator's list (two separate plazas at the same interchange). Names are
not unique in the model, but they will look identical in admin dropdowns, so
tell them apart by plaza_id.
"""

# (plaza_id, name)
PLAZAS = [
    (1,   'Shahfaisal Main Toll Plaza'),
    (2,   'Kathor Main Toll Plaza'),
    (101, 'Shafaisal-1 Interchange'),
    (102, 'Shafaisal-2 Interchange'),
    (103, 'Korangi 1 Interchange'),
    (104, 'Korangi 2 Interchange'),
    (105, 'Quaidabad Interchange'),
    (106, 'Quaidabad Interchange'),
    (107, 'Mai Niyari'),
]

# Pre-existing plazas from the old Malir Expressway seed are renumbered into this
# range by migration 0007 so they can never collide with a real plaza_id above
# (old KPT would otherwise have taken 1, which belongs to Shahfaisal Main).
# Anything at or above this is legacy and safe to delete.
LEGACY_PLAZA_ID_BASE = 9000

PLAZA_ID_WIDTH = 3


def format_plaza_id(plaza_id) -> str:
    """Render a plaza_id the way the operator writes it: 1 -> '001', 101 -> '101'.

    Used for display only. Lookups, config and the API all use the integer.
    """
    if plaza_id is None:
        return ''
    try:
        return f"{int(plaza_id):0{PLAZA_ID_WIDTH}d}"
    except (TypeError, ValueError):
        return str(plaza_id)
