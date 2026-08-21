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

# Lane numbers actually installed at each plaza, keyed by plaza_id.
#
# These are the operator's real lane numbers, NOT a count. They are sparse and
# do not start at 1 — plaza 001 runs 4,5,10,11,12,13 — so the old
# `range(1, --lanes+1)` seeding produced lanes that exist nowhere on the ground
# while omitting every real one. A booth whose rfid_config.ini names lane 37
# could not resolve it, and run_gate refuses to start without its lane.
#
# lane_number is unique per plaza, not globally (unique_together on
# plaza+lane_number), which is what lets lane 10 exist at both 001 and 002.
LANES = {
    1:   (4, 5, 10, 11, 12, 13),   # Shahfaisal Main
    2:   (6, 7, 8, 10),            # Kathor Main
    101: (18, 19),                 # Shafaisal-1
    102: (24,),                    # Shafaisal-2
    103: (27, 28),                 # Korangi 1
    104: (21,),                    # Korangi 2
    105: (30, 31),                 # Quaidabad (105)
    106: (33,),                    # Quaidabad (106)
    107: (37, 38),                 # Mai Niyari
}

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
