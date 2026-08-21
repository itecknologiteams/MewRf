import 'package:mtag_user_app/core/errors/app_failure.dart';

/// The response envelope every endpoint in this backend uses:
///
/// ```json
/// { "success": true,  "message": "Success", "data": <object|array|null> }
/// { "success": false, "message": "Login failed", "errors": {"phone": ["…"]} }
/// ```
///
/// Unwrapped in exactly one place. The alternative — each repository reaching for
/// `response.data['data']` itself — means every endpoint gets its own subtly
/// different idea of what a failure looks like, and the `errors` map (which the
/// login form needs mapped onto its fields) gets dropped by most of them.
class ApiEnvelope<T> {
  const ApiEnvelope({
    required this.success,
    required this.message,
    this.data,
    this.fieldErrors,
  });

  final bool success;
  final String message;
  final T? data;
  final Map<String, String>? fieldErrors;

  /// Parses a decoded JSON body.
  ///
  /// [fromData] converts the `data` member. It is not called when `data` is null,
  /// which is legitimate: `/auth/logout/` and `/auth/change-password/` succeed
  /// with `data: null`.
  static ApiEnvelope<T> parse<T>(
    dynamic body,
    T Function(dynamic data)? fromData,
  ) {
    if (body is! Map<String, dynamic>) {
      throw const MalformedResponseFailure(
        message: 'Response body was not a JSON object',
      );
    }

    final success = body['success'];
    if (success is! bool) {
      // A 200 whose body has no `success` key is not this API. Most likely a
      // proxy, a captive portal, or a Django debug page — all of which are HTML
      // with a 200 and would otherwise be reported as an empty result.
      throw const MalformedResponseFailure(
        message: 'Response envelope had no boolean `success`',
      );
    }

    final message = body['message'] is String ? body['message'] as String : '';
    final fieldErrors = flattenFieldErrors(body['errors']);

    if (!success) {
      throw ValidationFailure(
        message: message.isEmpty ? null : message,
        fieldErrors: fieldErrors,
      );
    }

    final raw = body['data'];
    return ApiEnvelope<T>(
      success: true,
      message: message,
      data: raw == null || fromData == null ? null : fromData(raw),
      fieldErrors: fieldErrors,
    );
  }

  /// The `data` member, or a failure if the server said success with no payload
  /// where one was required.
  T get required {
    final value = data;
    if (value == null) {
      throw const MalformedResponseFailure(
        message: 'Expected `data` in a successful response but it was null',
      );
    }
    return value;
  }
}

/// Pagination metadata, sibling to `data` on paginated endpoints.
///
/// ```json
/// "meta": { "count": 137, "next": "…?page=2", "previous": null,
///           "total_pages": 7, "current_page": 1 }
/// ```
class PageMeta {
  const PageMeta({
    required this.count,
    required this.totalPages,
    required this.currentPage,
    this.next,
    this.previous,
  });

  factory PageMeta.fromJson(Map<String, dynamic> json) => PageMeta(
    count: (json['count'] as num?)?.toInt() ?? 0,
    totalPages: (json['total_pages'] as num?)?.toInt() ?? 1,
    currentPage: (json['current_page'] as num?)?.toInt() ?? 1,
    next: json['next'] as String?,
    previous: json['previous'] as String?,
  );

  /// A single-page result, for endpoints that return a bare list.
  ///
  /// Several endpoints the app uses are NOT paginated even though they return
  /// arrays — `/vehicles/my/`, `/tolls/plazas/`, `/tolls/rates/`,
  /// `/payments/history/{id}/`. Wrapping them in a synthetic single page lets the
  /// list widgets stay uniform instead of branching on paginated-ness.
  factory PageMeta.single(int count) =>
      PageMeta(count: count, totalPages: 1, currentPage: 1);

  final int count;
  final int totalPages;
  final int currentPage;
  final String? next;
  final String? previous;

  bool get hasMore => next != null && currentPage < totalPages;

  int get nextPage => currentPage + 1;
}

/// A page of results plus its metadata.
class PagedEnvelope<T> {
  const PagedEnvelope({required this.items, required this.meta});

  /// Parses a paginated body. [fromItem] runs per element of `data`.
  static PagedEnvelope<T> parse<T>(
    dynamic body,
    T Function(Map<String, dynamic> json) fromItem,
  ) {
    final envelope = ApiEnvelope.parse<List<T>>(body, (data) {
      if (data is! List) {
        throw const MalformedResponseFailure(
          message: 'Expected `data` to be a list on a paginated endpoint',
        );
      }
      return data
          .whereType<Map<String, dynamic>>()
          .map(fromItem)
          .toList(growable: false);
    });

    final items = envelope.data ?? const [];
    final rawMeta = (body as Map<String, dynamic>)['meta'];
    return PagedEnvelope<T>(
      items: items,
      meta: rawMeta is Map<String, dynamic>
          ? PageMeta.fromJson(rawMeta)
          : PageMeta.single(items.length),
    );
  }

  final List<T> items;
  final PageMeta meta;

  bool get isEmpty => items.isEmpty;

  PagedEnvelope<T> append(PagedEnvelope<T> next) => PagedEnvelope(
    items: [...items, ...next.items],
    meta: next.meta,
  );
}
