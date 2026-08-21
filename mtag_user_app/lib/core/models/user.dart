import 'package:freezed_annotation/freezed_annotation.dart';
import 'package:mtag_user_app/core/models/enums.dart';
import 'package:mtag_user_app/core/utils/app_dates.dart';

part 'user.freezed.dart';

/// `GET /auth/me/` — `UserDetailSerializer`.
///
/// Parsing is `fromApi`, hand-written, deliberately NOT named `fromJson`.
///
/// Two reasons. First, freezed treats a `fromJson` factory as a request to wire
/// up json_serializable, which would then generate a parser keyed on the Dart
/// field names (`fullName`) rather than the API's (`full_name`) — silently
/// producing empty models. Second, every field here needs custom handling that
/// annotations express worse than code does: enums fall back to `unknown` instead
/// of throwing on a value a future deployment adds, money is a Decimal parsed
/// from a string, and timestamps are normalised to UTC.
///
/// `fromApi` also names the thing accurately: this reads ONE specific server's
/// response shape, verified against `UserDetailSerializer`. It is not a general
/// JSON round-trip and there is no `toJson` — the app never sends a user object
/// back.
@freezed
abstract class AppUser with _$AppUser {
  const factory AppUser({
    required int id,
    required String uuid,
    required String fullName,
    required String phone,
    required UserRole role,
    required UserStatus status,
    String? cnic,
    DateTime? createdAt,
  }) = _AppUser;

  factory AppUser.fromApi(Map<String, dynamic> json) => AppUser(
    id: (json['id'] as num).toInt(),
    uuid: json['uuid']?.toString() ?? '',
    fullName: json['full_name']?.toString() ?? '',
    phone: json['phone']?.toString() ?? '',
    role: UserRole.parse(json['user_role']),
    status: UserStatus.parse(json['status']),
    // Empty string and null both mean "no CNIC on file"; the profile screen
    // shows a dash, not an empty row.
    cnic: (json['cnic']?.toString().trim().isEmpty ?? true)
        ? null
        : json['cnic'].toString(),
    createdAt: AppDates.tryParseUtc(json['created_at']),
  );
}

/// `POST /auth/login/` — the body of a successful login.
///
/// **The JWTs are not in here.** `LoginView` pops `access` and `refresh` out of
/// `data` and sets them as httpOnly cookies, so this carries identity only. If a
/// future server version starts returning tokens in the body, this model
/// deliberately ignores them — the client is cookie-based and a second source of
/// truth for the session would be a bug waiting to happen.
@freezed
abstract class LoginResult with _$LoginResult {
  const factory LoginResult({
    required int userId,
    required String uuid,
    required String fullName,
    required String phone,
    required UserRole role,
  }) = _LoginResult;

  factory LoginResult.fromApi(Map<String, dynamic> json) => LoginResult(
    userId: (json['user_id'] as num).toInt(),
    uuid: json['uuid']?.toString() ?? '',
    fullName: json['full_name']?.toString() ?? '',
    phone: json['phone']?.toString() ?? '',
    role: UserRole.parse(json['role']),
  );
}
