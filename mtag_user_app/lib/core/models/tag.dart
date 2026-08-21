import 'package:freezed_annotation/freezed_annotation.dart';
import 'package:mtag_user_app/core/env/app_env.dart';
import 'package:mtag_user_app/core/models/enums.dart';
import 'package:mtag_user_app/core/utils/app_dates.dart';

part 'tag.freezed.dart';

/// A tag, from `TagSerializer`.
///
/// `tid` and `epc` are read-only server-side and were added to the serializer as
/// part of this app's Phase 0 changes. `tid` is load-bearing: the JazzCash
/// aggregator flow is keyed on it — the customer types the TID into the JazzCash
/// app — so without it the app cannot tell a holder how to top up. If the field is
/// absent (an older backend), [tid] is null and the app HIDES the JazzCash
/// instruction block rather than showing an empty field.
@freezed
abstract class Tag with _$Tag {
  const factory Tag({
    required int id,
    required String tagSerial,
    required TagStatus status,

    /// The server's own `is_valid`: assigned to a vehicle AND status == active AND
    /// expiry_date >= today. Treated as authoritative and never recomputed —
    /// "today" on a phone with a wrong clock is not the server's today, and the
    /// barrier obeys the server.
    required bool isValid,
    DateTime? expiryDate,
    DateTime? issuedAt,
    DateTime? lastScannedAt,
    String? tid,
    String? epc,
  }) = _Tag;

  factory Tag.fromApi(Map<String, dynamic> json) {
    String? nonEmpty(Object? raw) {
      final text = raw?.toString().trim();
      return (text == null || text.isEmpty) ? null : text;
    }

    return Tag(
      id: (json['id'] as num).toInt(),
      tagSerial: json['tag_serial']?.toString() ?? '',
      status: TagStatus.parse(json['status']),
      isValid: json['is_valid'] == true,
      // A DateField, so no time component — parsed as UTC midnight and only ever
      // compared on PKT calendar days.
      expiryDate: AppDates.tryParseUtc(json['expiry_date']),
      issuedAt: AppDates.tryParseUtc(json['issued_at']),
      lastScannedAt: AppDates.tryParseUtc(json['last_scanned_at']),
      tid: nonEmpty(json['tid']),
      epc: nonEmpty(json['epc']),
    );
  }
}

extension TagX on Tag {
  /// Days until expiry, negative once past. Null when the server sent no date.
  int? get daysUntilExpiry {
    final expiry = expiryDate;
    return expiry == null ? null : AppDates.daysUntil(expiry);
  }

  /// Whether to show an "expires in N days" warning.
  ///
  /// Only for a tag that is still valid — an already-expired tag gets the harder
  /// expired state, and showing both would be noise on top of a real problem.
  bool get isExpiringSoon {
    final days = daysUntilExpiry;
    if (days == null || !isValid) return false;
    return days >= 0 && days <= AppEnv.tagExpiryWarningDays;
  }

  /// Whether the aggregator top-up instructions can be shown for this tag.
  bool get canShowJazzCashInstructions => (tid ?? '').isNotEmpty;
}
