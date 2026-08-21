import 'package:flutter/widgets.dart';
import 'package:mtag_user_app/core/errors/app_failure.dart';
import 'package:mtag_user_app/core/models/enums.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// Enum -> localised label, in one place.
///
/// The raw values (`truck_2axle`, `offline_exit_sync`) are database strings and must
/// never reach a screen. Centralised so a new fare class is labelled once rather
/// than in every widget that renders one, and so the Urdu build cannot end up with
/// half the statuses in English.
extension VehicleTypeLabel on VehicleType {
  String label(AppL10n l10n) => switch (this) {
    VehicleType.car => l10n.vehicleTypeCar,
    VehicleType.wagon => l10n.vehicleTypeWagon,
    VehicleType.coach => l10n.vehicleTypeCoach,
    VehicleType.largeBus => l10n.vehicleTypeLargeBus,
    VehicleType.truck2Axle => l10n.vehicleTypeTruck2Axle,
    VehicleType.truck3Axle => l10n.vehicleTypeTruck3Axle,
    VehicleType.truck4Axle => l10n.vehicleTypeTruck4Axle,
    VehicleType.motorcycle => l10n.vehicleTypeMotorcycle,
    VehicleType.unknown => l10n.vehicleTypeUnknown,
  };
}

extension TagStatusLabel on TagStatus {
  String label(AppL10n l10n) => switch (this) {
    TagStatus.active => l10n.tagStatusActive,
    TagStatus.expired => l10n.tagStatusExpired,
    TagStatus.suspended => l10n.tagStatusSuspended,
    TagStatus.deactivated => l10n.tagStatusDeactivated,
    TagStatus.unknown => l10n.tagStatusUnknown,
  };
}

extension VehicleStatusLabel on VehicleStatus {
  String label(AppL10n l10n) => switch (this) {
    VehicleStatus.active => l10n.vehicleStatusActive,
    VehicleStatus.inactive => l10n.vehicleStatusInactive,
    VehicleStatus.suspended => l10n.vehicleStatusSuspended,
    VehicleStatus.unknown => l10n.vehicleStatusUnknown,
  };
}

extension TransactionTypeLabel on TransactionType {
  String label(AppL10n l10n) => switch (this) {
    TransactionType.tollDeduction => l10n.transactionTypeToll,
    TransactionType.topup => l10n.transactionTypeTopup,
    TransactionType.refund => l10n.transactionTypeRefund,
    TransactionType.transferIn => l10n.transactionTypeTransferIn,
    TransactionType.transferOut => l10n.transactionTypeTransferOut,
    TransactionType.unknown => l10n.transactionTypeUnknown,
  };
}

/// [AppFailure] -> a sentence a motorist can act on.
///
/// The single place a failure becomes words. A raw
/// `DioException [connection error]` is not an error message, it is a stack trace
/// with punctuation.
///
/// The server's own `message` is preferred when it exists, because it is more
/// specific than any generic string here — "Minimum top-up amount is Rs.100" beats
/// "Please check what you entered". The generic text is the fallback.
extension AppFailureLabel on AppFailure {
  String label(AppL10n l10n) {
    final serverMessage = message;
    if (this is ValidationFailure &&
        serverMessage != null &&
        serverMessage.isNotEmpty) {
      return serverMessage;
    }
    return switch (l10nKey) {
      'errorNetwork' => l10n.errorNetwork,
      'errorTimeout' => l10n.errorTimeout,
      'errorUnauthorised' => l10n.errorUnauthorised,
      'errorForbidden' => l10n.errorForbidden,
      'errorNotFound' => l10n.errorNotFound,
      'errorThrottled' => l10n.errorThrottled,
      'errorValidation' => l10n.errorValidation,
      'errorServer' => l10n.errorServer,
      'errorMalformed' => l10n.errorMalformed,
      _ => l10n.errorUnknown,
    };
  }
}

/// Localises whatever went wrong, including a non-[AppFailure] surprise.
///
/// Anything that is not an [AppFailure] reaching the UI is a bug in the data layer,
/// but the user still gets a sentence rather than a red screen.
String describeError(Object error, AppL10n l10n) =>
    error is AppFailure ? error.label(l10n) : l10n.errorUnknown;

/// The active locale as an `intl` tag, for number and date formatting.
String localeTag(BuildContext context) =>
    Localizations.localeOf(context).toLanguageTag();
