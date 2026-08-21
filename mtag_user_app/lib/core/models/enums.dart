/// The backend's `TextChoices`, mirrored exactly.
///
/// Every enum here carries an `unknown` member and parses by value with a
/// fallback. The server can add a choice — a new fare class, a new transaction
/// source — in a deployment the app does not know about, and a client that throws
/// on an unrecognised string turns "we added a category" into "the app crashes on
/// launch for everyone". Unknown renders as the raw value, which is ugly but
/// truthful and debuggable.
///
/// Labels are NOT here. They live in the ARB bundle, because they are shown to
/// motorists in English and Urdu.
library;

/// `apps.vehicles.models.VehicleType` — the FARE CLASS, from the official
/// Shahra-e-Bhutto toll notification. Not a cosmetic description: the fare matrix
/// joins on it via `VehicleCategory.code`.
enum VehicleType {
  car('car'),
  wagon('wagon'),
  coach('coach'),
  largeBus('large_bus'),
  truck2Axle('truck_2axle'),
  truck3Axle('truck_3axle'),
  truck4Axle('truck_4axle'),

  /// Recorded as a registration class but **not permitted on the expressway**.
  /// Kept as a valid choice server-side so a motorcycle is refused rather than
  /// mis-billed as a car, and the app must say so rather than quoting it a fare.
  motorcycle('motorcycle'),

  unknown('');

  const VehicleType(this.value);

  final String value;

  static VehicleType parse(Object? raw) {
    final text = raw?.toString() ?? '';
    for (final type in values) {
      if (type.value == text) return type;
    }
    return unknown;
  }

  bool get isPermittedOnExpressway => this != motorcycle && this != unknown;
}

/// `apps.vehicles.models.TagStatus`.
enum TagStatus {
  active('active'),
  expired('expired'),
  suspended('suspended'),
  deactivated('deactivated'),
  unknown('');

  const TagStatus(this.value);

  final String value;

  static TagStatus parse(Object? raw) {
    final text = raw?.toString() ?? '';
    for (final status in values) {
      if (status.value == text) return status;
    }
    return unknown;
  }
}

/// `apps.vehicles.models.VehicleStatus`.
enum VehicleStatus {
  active('active'),
  inactive('inactive'),
  suspended('suspended'),
  unknown('');

  const VehicleStatus(this.value);

  final String value;

  static VehicleStatus parse(Object? raw) {
    final text = raw?.toString() ?? '';
    for (final status in values) {
      if (status.value == text) return status;
    }
    return unknown;
  }
}

/// `apps.accounts.models.TransactionType`.
enum TransactionType {
  tollDeduction('toll_deduction'),
  topup('topup'),
  refund('refund'),
  transferOut('transfer_out'),
  transferIn('transfer_in'),
  unknown('');

  const TransactionType(this.value);

  final String value;

  static TransactionType parse(Object? raw) {
    final text = raw?.toString() ?? '';
    for (final type in values) {
      if (type.value == text) return type;
    }
    return unknown;
  }

  /// Whether this ADDS to the balance. Drives the sign and the colour on a
  /// transaction row, so getting it wrong shows a deduction as income.
  bool get isCredit => switch (this) {
    topup || refund || transferIn => true,
    tollDeduction || transferOut => false,
    // An unrecognised type is shown unsigned rather than guessed at.
    unknown => false,
  };
}

/// `apps.accounts.models.TransactionStatus`.
enum TransactionStatus {
  success('success'),
  failed('failed'),
  pending('pending'),
  unknown('');

  const TransactionStatus(this.value);

  final String value;

  static TransactionStatus parse(Object? raw) {
    final text = raw?.toString() ?? '';
    for (final status in values) {
      if (status.value == text) return status;
    }
    return unknown;
  }
}

/// `apps.accounts.models.TransactionSource`.
enum TransactionSource {
  onlineExit('online_exit'),

  /// A deduction taken at a booth that was offline, replicated to master on a
  /// later sync. It can land in history minutes after the trip, so a row carrying
  /// this gets a "synced from booth" note — without which the history looks
  /// simply wrong to someone who exited twenty minutes ago.
  offlineExitSync('offline_exit_sync'),

  topupJazzCash('topup_jazzcash'),
  topupCash('topup_cash'),
  refund('refund'),

  /// Also what a row with a NULL source parses to. Several server paths — the
  /// operator top-up and the app-initiated JazzCash callback — create
  /// transactions without setting `source`, so absent is common, not exceptional.
  unknown('');

  const TransactionSource(this.value);

  final String value;

  static TransactionSource parse(Object? raw) {
    final text = raw?.toString() ?? '';
    for (final source in values) {
      if (source.value == text) return source;
    }
    return unknown;
  }
}

/// `apps.payments.models.TopupStatus`.
enum TopupStatus {
  pending('pending'),
  success('success'),
  failed('failed'),
  unknown('');

  const TopupStatus(this.value);

  final String value;

  static TopupStatus parse(Object? raw) {
    final text = raw?.toString() ?? '';
    for (final status in values) {
      if (status.value == text) return status;
    }
    return unknown;
  }

  bool get isSettled => this == success || this == failed;
}

/// `apps.tolls.models.TripStatus` — read from the source, not guessed:
/// `active`, `completed`, `failed`.
enum TripStatus {
  /// Entered, not yet exited. Rendered as a distinct live card.
  active('active'),
  completed('completed'),
  failed('failed'),
  unknown('');

  const TripStatus(this.value);

  final String value;

  static TripStatus parse(Object? raw) {
    final text = raw?.toString() ?? '';
    for (final status in values) {
      if (status.value == text) return status;
    }
    return unknown;
  }
}

/// `apps.users.models.UserRole`.
///
/// The app is a CONSUMER app. An operator or admin can log in with these
/// credentials, and the app must not silently show them a broken dashboard — it
/// says plainly that this account is a staff account and points at the portal.
enum UserRole {
  user('user'),
  operator('operator'),
  admin('admin'),
  unknown('');

  const UserRole(this.value);

  final String value;

  static UserRole parse(Object? raw) {
    final text = raw?.toString() ?? '';
    for (final role in values) {
      if (role.value == text) return role;
    }
    return unknown;
  }

  bool get isConsumer => this == user;
}

/// `apps.users.models.UserStatus`.
enum UserStatus {
  active('active'),
  inactive('inactive'),
  blocked('blocked'),
  unknown('');

  const UserStatus(this.value);

  final String value;

  static UserStatus parse(Object? raw) {
    final text = raw?.toString() ?? '';
    for (final status in values) {
      if (status.value == text) return status;
    }
    return unknown;
  }
}
