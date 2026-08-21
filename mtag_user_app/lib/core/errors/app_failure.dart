import 'package:dio/dio.dart';

/// Every way a request can fail, as one closed set.
///
/// A `sealed class` rather than a freezed union: this needs no JSON, no copyWith
/// and no equality beyond identity, so codegen would add a build step and a
/// generated file for a switch statement Dart already checks exhaustively.
///
/// **No DioException ever escapes the data layer.** A raw
/// `DioException [connection error]: SocketException: Connection refused` on
/// screen tells a motorist nothing and looks like a crash. Every failure that
/// reaches the UI carries a localisation key the presentation layer turns into a
/// sentence.
sealed class AppFailure implements Exception {
  const AppFailure({this.message, this.fieldErrors});

  /// The server's own `message`, when it sent one worth showing.
  final String? message;

  /// The envelope's `errors` map, flattened to one string per field.
  ///
  /// The login screen maps this straight onto its form fields. Note that DRF puts
  /// non-field validation errors — including "Invalid phone number or password."
  /// and "Account is blocked. Contact support." — under `non_field_errors`, not
  /// under `phone` or `password`.
  final Map<String, String>? fieldErrors;

  /// Key into the ARB bundle for the user-facing fallback sentence.
  String get l10nKey;

  /// Whether retrying the identical request could plausibly succeed.
  ///
  /// Consulted for GETs only. A POST that moves money is never auto-retried, no
  /// matter what this says.
  bool get isRetryable => false;

  String? get nonFieldError => fieldErrors?['non_field_errors'];
}

/// No route to the host: airplane mode, no signal, LAN unreachable.
class NetworkFailure extends AppFailure {
  const NetworkFailure({super.message});

  @override
  String get l10nKey => 'errorNetwork';

  @override
  bool get isRetryable => true;
}

class TimeoutFailure extends AppFailure {
  const TimeoutFailure({super.message});

  @override
  String get l10nKey => 'errorTimeout';

  @override
  bool get isRetryable => true;
}

/// 401. The session is gone — the cookie expired, was blacklisted by a rotation,
/// or the jar is stale. The interceptor has already tried a refresh by the time
/// this surfaces, so it means "log in again", not "retry".
class UnauthorisedFailure extends AppFailure {
  const UnauthorisedFailure({super.message, super.fieldErrors});

  @override
  String get l10nKey => 'errorUnauthorised';
}

/// 403. Authenticated but not permitted — which in this app means the code
/// reached an operator endpoint. That is a bug, not a user problem.
class ForbiddenFailure extends AppFailure {
  const ForbiddenFailure({super.message});

  @override
  String get l10nKey => 'errorForbidden';
}

/// 404. Also what the server returns for a resource that exists but is not
/// yours — deliberately, so ids cannot be enumerated.
class NotFoundFailure extends AppFailure {
  const NotFoundFailure({super.message});

  @override
  String get l10nKey => 'errorNotFound';
}

/// 429. First-class, with the server's `Retry-After` honoured.
///
/// `/auth/login/` is throttled at 10/minute, so a user fat-fingering their
/// password hits this in normal use and must be told to wait rather than shown a
/// generic error and left tapping.
class ThrottledFailure extends AppFailure {
  const ThrottledFailure({this.retryAfter, super.message});

  final Duration? retryAfter;

  @override
  String get l10nKey => 'errorThrottled';
}

/// 400/422 with a field map.
class ValidationFailure extends AppFailure {
  const ValidationFailure({super.message, super.fieldErrors});

  @override
  String get l10nKey => 'errorValidation';
}

/// 5xx.
class ServerFailure extends AppFailure {
  const ServerFailure({this.statusCode, super.message});

  final int? statusCode;

  @override
  String get l10nKey => 'errorServer';

  @override
  bool get isRetryable => true;
}

/// A well-formed HTTP response whose body was not the expected envelope.
///
/// Distinct from [ServerFailure] because it usually means a proxy, a captive
/// portal or an HTML error page — worth telling apart when debugging a LAN
/// deployment.
class MalformedResponseFailure extends AppFailure {
  const MalformedResponseFailure({super.message});

  @override
  String get l10nKey => 'errorMalformed';
}

class UnknownFailure extends AppFailure {
  const UnknownFailure({super.message});

  @override
  String get l10nKey => 'errorUnknown';
}

/// Maps a [DioException] onto the closed set.
///
/// The single choke point where Dio's vocabulary is translated. Anything that
/// gets past here would reach a screen as a stack trace.
AppFailure failureFromDio(DioException error) {
  switch (error.type) {
    case DioExceptionType.connectionTimeout:
    case DioExceptionType.sendTimeout:
    case DioExceptionType.receiveTimeout:
    // transformTimeout is JSON decoding taking too long, not the network. Grouped
    // here because the user-facing answer is identical — "the server took too long"
    // — and splitting it out would add a message nobody can act on differently.
    case DioExceptionType.transformTimeout:
      return TimeoutFailure(message: error.message);

    case DioExceptionType.connectionError:
      return NetworkFailure(message: error.message);

    case DioExceptionType.cancel:
      // A cancelled request is usually a screen that went away mid-flight. It is
      // not a network problem and must not be reported as one.
      return const UnknownFailure(message: 'cancelled');

    case DioExceptionType.badCertificate:
      // Only reachable on the pinned prod flavour, where it means the pin did not
      // match — a MITM, or a rotated certificate nobody added a pin for.
      return const NetworkFailure(message: 'certificate rejected');

    case DioExceptionType.badResponse:
      return failureFromResponse(error.response!);

    case DioExceptionType.unknown:
      // Dio funnels SocketException here on some platforms.
      final message = error.message ?? '';
      if (message.contains('SocketException') ||
          message.contains('Connection')) {
        return NetworkFailure(message: error.message);
      }
      return UnknownFailure(message: error.message);
  }
}

AppFailure failureFromResponse(Response<dynamic> response) {
  final status = response.statusCode ?? 0;
  final body = response.data;

  String? message;
  Map<String, String>? fields;

  if (body is Map<String, dynamic>) {
    final rawMessage = body['message'];
    if (rawMessage is String && rawMessage.isNotEmpty) message = rawMessage;
    fields = flattenFieldErrors(body['errors']);
  }

  if (status == 401) {
    return UnauthorisedFailure(message: message, fieldErrors: fields);
  }
  if (status == 403) return ForbiddenFailure(message: message);
  if (status == 404) return NotFoundFailure(message: message);
  if (status == 429) {
    return ThrottledFailure(
      message: message,
      retryAfter: _retryAfter(response.headers.value('retry-after')),
    );
  }
  if (status >= 500) return ServerFailure(statusCode: status, message: message);
  if (status >= 400) {
    return ValidationFailure(message: message, fieldErrors: fields);
  }

  return UnknownFailure(message: message);
}

/// Flattens DRF's `{"field": ["msg", "msg2"]}` into `{"field": "msg msg2"}`.
///
/// DRF is inconsistent about whether a value is a list, a bare string or a nested
/// map, and a client that assumes one shape drops the others on the floor —
/// leaving a form that refuses to submit with no visible reason.
Map<String, String>? flattenFieldErrors(dynamic errors) {
  if (errors is! Map) return null;
  final out = <String, String>{};
  for (final entry in errors.entries) {
    final key = entry.key.toString();
    final value = entry.value;
    if (value is List) {
      final parts = value.map((v) => v.toString()).where((s) => s.isNotEmpty);
      if (parts.isNotEmpty) {
        out[key] = parts.join(' ');
      }
    } else if (value is Map) {
      final nested = flattenFieldErrors(value);
      if (nested != null && nested.isNotEmpty) {
        out[key] = nested.values.join(' ');
      }
    } else if (value != null) {
      out[key] = value.toString();
    }
  }
  return out.isEmpty ? null : out;
}

Duration? _retryAfter(String? header) {
  if (header == null || header.isEmpty) return null;
  final seconds = int.tryParse(header.trim());
  if (seconds != null) return Duration(seconds: seconds);
  // The HTTP-date form is legal but DRF sends integer seconds; parse it anyway
  // rather than silently losing the cooldown.
  final date = DateTime.tryParse(header);
  if (date == null) return null;
  final delta = date.difference(DateTime.now());
  return delta.isNegative ? null : delta;
}
