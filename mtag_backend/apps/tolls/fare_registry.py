"""
Notified toll fares — Shahra-e-Bhutto (Malir Expressway) toll notification.

Source: Government of Sindh / Malir Expressway (Private) Limited toll
notification, Column 2 (vehicle type) x Column 3 (Partial Length Facility).

CURRENT CONFIGURATION: a SINGLE TARIFF (see TARIFF below). One fare per vehicle
category, charged for every plaza pair regardless of distance travelled.

    !!! If the notification's Column 4 (Full Length Facility) applies to this
    !!! road, a trip crossing Quaidabad should cost MORE than TARIFF and is
    !!! currently UNDER-BILLED. Filling in FULL_LENGTH and SEGMENT below switches
    !!! load_fares to distance-banded pricing automatically — no code change.

The notification's banding, retained for when/if it is adopted:

    Partial Length Facility (P)
        Qayumabad <-> Quaidabad, or any shorter trip between those points
        Quaidabad <-> M9,        or any shorter trip between those points

    Full Length Facility (F)
        Qayumabad <-> M9 — i.e. a trip that CROSSES Quaidabad
"""
from apps.vehicles.models import VehicleType

# The vehicle_categories table is seeded from this list by `load_fares`.
# (category_index, code, name, description)
CATEGORIES = [
    (1, VehicleType.CAR,         'Car / Jeep / Taxi / Pickup', 'Cars, jeeps, taxis and pickups'),
    (2, VehicleType.WAGON,       'Wagon / Hiace',              'Wagons and Hiace vans'),
    (3, VehicleType.COACH,       'Coach / Coaster / Mini Bus', 'Coaches, coasters and mini buses'),
    (4, VehicleType.LARGE_BUS,   'Large Bus',                  'Full-size buses'),
    (5, VehicleType.TRUCK_2AXLE, '2 Axle Truck',               'Trucks with 2 axles'),
    (6, VehicleType.TRUCK_3AXLE, '3 Axle Truck',               'Trucks with 3 axles'),
    (7, VehicleType.TRUCK_4AXLE, '4 or More Axle Truck',       'Trucks with 4 or more axles'),
]

# ── The tariff in force ───────────────────────────────────────────────────────
# category_index -> fare in PKR. Applied to EVERY plaza pair, both directions.
TARIFF = {
    1: 100,   # Car / Jeep / Taxi / Pickup
    2: 150,   # Wagon / Hiace
    3: 200,   # Coach / Coaster / Mini Bus
    4: 250,   # Large Bus
    5: 350,   # 2 Axle Truck
    6: 350,   # 3 Axle Truck
    7: 450,   # 4 or More Axle Truck
}

# Kept as an explicit alias: TARIFF is the notification's Partial-Length column.
PARTIAL_LENGTH = TARIFF

# ── Optional distance banding (currently unused) ──────────────────────────────
# Fill BOTH to switch load_fares from flat TARIFF to Partial/Full pricing.
#
# FULL_LENGTH: category_index -> fare for a trip that crosses Quaidabad.
FULL_LENGTH: dict = {}
#
# SEGMENT: Plaza.plaza_id -> 'qayumabad_side' | 'quaidabad' | 'm9_side'.
# A trip whose two plazas sit on OPPOSITE sides crosses Quaidabad -> FULL_LENGTH.
SEGMENT: dict = {}

# Motorcycles are not permitted on the expressway, so they get no fare row at
# all — an attempted exit is refused with "Toll rate not configured for this
# route" rather than being billed at some arbitrary rate.
EXCLUDED_FROM_FARES = {VehicleType.MOTORCYCLE}


def zoning_configured() -> bool:
    """True when distance-banded pricing is fully specified."""
    return bool(FULL_LENGTH) and bool(SEGMENT)


def is_complete() -> tuple:
    """Return (ok, missing) — load_fares refuses to build a partial matrix.

    Satisfied either by the flat TARIFF (the current setup) or by a fully
    specified Partial/Full banding. A half-specified banding is an error: it
    would silently price some trips from one table and some from another.
    """
    missing = []
    category_indexes = {c[0] for c in CATEGORIES}

    if zoning_configured():
        gaps = category_indexes - set(FULL_LENGTH)
        if gaps:
            missing.append(f"FULL_LENGTH is missing category_index: {sorted(gaps)}")
        gaps = category_indexes - set(PARTIAL_LENGTH)
        if gaps:
            missing.append(f"PARTIAL_LENGTH is missing category_index: {sorted(gaps)}")
        return (not missing), missing

    # Half-configured banding — refuse rather than silently falling back to flat.
    if FULL_LENGTH and not SEGMENT:
        missing.append(
            "FULL_LENGTH is set but SEGMENT is empty — without knowing which side "
            "of Quaidabad each plaza is on, no trip can be classified Partial vs Full"
        )
    if SEGMENT and not FULL_LENGTH:
        missing.append(
            "SEGMENT is set but FULL_LENGTH is empty — there is no Full-Length "
            "fare to charge a trip that crosses Quaidabad"
        )
    if missing:
        return False, missing

    gaps = category_indexes - set(TARIFF)
    if gaps:
        missing.append(f"TARIFF is missing category_index: {sorted(gaps)}")
    return (not missing), missing
