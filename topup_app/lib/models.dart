class TagRead {
  final String tid;
  final String epc;

  const TagRead({required this.tid, required this.epc});

  Map<String, String> toJson() => {'tid': tid, 'epc': epc};

  factory TagRead.fromMap(Map<dynamic, dynamic> m) => TagRead(
        tid: (m['tid'] ?? m['TID'] ?? '').toString().replaceAll(' ', '').toUpperCase(),
        epc: (m['epc'] ?? m['EPC'] ?? '').toString().trim(),
      );
}

/// A billing class from the fare notification (`/tolls/vehicle-categories/`).
/// `code` is what `vehicles.vehicle_type` stores and what the fare matrix is
/// joined on, so it is the value sent back on registration.
class VehicleCategory {
  final String code;
  final String name;

  const VehicleCategory({required this.code, required this.name});

  factory VehicleCategory.fromMap(Map<dynamic, dynamic> m) => VehicleCategory(
        code: (m['code'] ?? '').toString(),
        name: (m['name'] ?? m['code'] ?? '').toString(),
      );

  /// Used when the categories call fails. A booth with a flaky link must still
  /// be able to register a truck as a truck — an empty dropdown would either
  /// block the registration or file everything as a car, which is the
  /// mis-billing this list exists to prevent. Mirrors VehicleType in
  /// apps/vehicles/models.py; the server validates whatever is sent.
  static const fallback = <VehicleCategory>[
    VehicleCategory(code: 'car', name: 'Car / Jeep / Taxi / Pickup'),
    VehicleCategory(code: 'wagon', name: 'Wagon / Hiace'),
    VehicleCategory(code: 'coach', name: 'Coach / Coaster / Mini Bus'),
    VehicleCategory(code: 'large_bus', name: 'Large Bus'),
    VehicleCategory(code: 'truck_2axle', name: '2 Axle Truck'),
    VehicleCategory(code: 'truck_3axle', name: '3 Axle Truck'),
    VehicleCategory(code: 'truck_4axle', name: '4 or More Axle Truck'),
    VehicleCategory(code: 'motorcycle', name: 'Motorcycle'),
  ];
}
