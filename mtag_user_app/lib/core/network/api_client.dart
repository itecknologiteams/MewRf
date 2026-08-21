import 'dart:async';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:dio_cookie_manager/dio_cookie_manager.dart';
import 'package:mtag_user_app/core/env/app_env.dart';
import 'package:mtag_user_app/core/errors/app_failure.dart';
import 'package:mtag_user_app/core/network/api_envelope.dart';
import 'package:mtag_user_app/core/network/cookie_store.dart';
import 'package:mtag_user_app/core/network/logging_interceptor.dart';
import 'package:mtag_user_app/core/network/refresh_interceptor.dart';
import 'package:mtag_user_app/core/network/tls_pinning.dart';

/// The HTTP client. One instance for the app's lifetime.
///
/// Two Dio instances share the cookie jar:
///
///   * [_dio] — everything the app calls, with the refresh interceptor attached.
///   * [_bare] — the same jar and base URL, WITHOUT the refresh interceptor. Used
///     for the refresh call itself and for replaying a request afterwards. Without
///     this split, a 401 from `/auth/token/refresh/` would re-enter the
///     interceptor and recurse.
class ApiClient {
  ApiClient._(this._dio, this._bare, this.cookies);

  final Dio _dio;
  final Dio _bare;
  final CookieStore cookies;

  /// Fired when a refresh fails and the session is over. The router listens.
  final _sessionExpired = StreamController<void>.broadcast();

  Stream<void> get onSessionExpired => _sessionExpired.stream;

  Uri get origin => Uri.parse(AppEnv.resolvedApiBase);

  static Future<ApiClient> create({CookieStore? cookieStore}) async {
    final store = cookieStore ?? await CookieStore.open();

    Dio build() {
      final dio = Dio(
        BaseOptions(
          baseUrl: AppEnv.apiRoot,
          // 15s. Long enough for a booth LAN under load, short enough that a
          // motorist at a gate is not staring at a spinner.
          connectTimeout: const Duration(seconds: 15),
          sendTimeout: const Duration(seconds: 15),
          receiveTimeout: const Duration(seconds: 15),
          contentType: Headers.jsonContentType,
          // Non-2xx is handled as an AppFailure rather than thrown raw, but Dio
          // still needs to raise so the interceptors see it.
          validateStatus: (status) => status != null && status < 400,
        ),
      );
      dio.interceptors.add(CookieManager(store.jar));
      dio.interceptors.add(const LoggingInterceptor());
      configureTlsPinning(dio);
      return dio;
    }

    final bare = build();
    final main = build();

    final client = ApiClient._(main, bare, store);

    main.interceptors.add(
      RefreshInterceptor(
        refreshClient: () => bare,
        onSessionExpired: client._handleSessionExpired,
      ),
    );

    return client;
  }

  Future<void> _handleSessionExpired() async {
    await cookies.clear();
    if (!_sessionExpired.isClosed) _sessionExpired.add(null);
  }

  /// Clears the local session. Used by logout after the server call.
  Future<void> clearSession() => cookies.clear();

  void dispose() {
    _sessionExpired.close();
    _dio.close(force: true);
    _bare.close(force: true);
  }

  // ── Verbs ──────────────────────────────────────────────────────────────────

  /// A GET returning a single object.
  ///
  /// Idempotent, so it is the only verb this client will retry — see [_send].
  Future<T> get<T>(
    String path, {
    required T Function(dynamic data) parse,
    Map<String, dynamic>? query,
    CancelToken? cancelToken,
  }) async {
    final response = await _send(
      () => _dio.get<dynamic>(
        path,
        queryParameters: query,
        cancelToken: cancelToken,
      ),
      retryable: true,
    );
    return ApiEnvelope.parse<T>(response.data, parse).required;
  }

  /// A GET whose `data` may legitimately be null.
  Future<T?> getNullable<T>(
    String path, {
    required T Function(dynamic data) parse,
    Map<String, dynamic>? query,
    CancelToken? cancelToken,
  }) async {
    final response = await _send(
      () => _dio.get<dynamic>(
        path,
        queryParameters: query,
        cancelToken: cancelToken,
      ),
      retryable: true,
    );
    return ApiEnvelope.parse<T>(response.data, parse).data;
  }

  /// A paginated GET.
  Future<PagedEnvelope<T>> getPaged<T>(
    String path, {
    required T Function(Map<String, dynamic> json) parseItem,
    int? page,
    int? pageSize,
    Map<String, dynamic>? query,
    CancelToken? cancelToken,
  }) async {
    final response = await _send(
      () => _dio.get<dynamic>(
        path,
        queryParameters: {
          'page': ?page,
          'page_size': ?pageSize,
          ...?query,
        },
        cancelToken: cancelToken,
      ),
      retryable: true,
    );
    return PagedEnvelope.parse<T>(response.data, parseItem);
  }

  /// A POST.
  ///
  /// **Never retried.** `/payments/topup/` creates a `TopupRequest` row; a
  /// transparent retry on a timeout would leave two pending top-ups for one
  /// intent, and the user would see a payment history that does not match what
  /// they did. Retry is the caller's decision, made with an idempotency key.
  Future<T?> post<T>(
    String path, {
    Object? body,
    T Function(dynamic data)? parse,
    CancelToken? cancelToken,
    Map<String, String>? headers,
  }) async {
    final response = await _send(
      () => _dio.post<dynamic>(
        path,
        data: body,
        cancelToken: cancelToken,
        options: headers == null ? null : Options(headers: headers),
      ),
      retryable: false,
    );
    return ApiEnvelope.parse<T>(response.data, parse).data;
  }

  Future<T?> patch<T>(
    String path, {
    Object? body,
    T Function(dynamic data)? parse,
    CancelToken? cancelToken,
  }) async {
    final response = await _send(
      () => _dio.patch<dynamic>(path, data: body, cancelToken: cancelToken),
      retryable: false,
    );
    return ApiEnvelope.parse<T>(response.data, parse).data;
  }

  /// Runs a request, translating every Dio failure into an [AppFailure].
  ///
  /// [retryable] permits ONE retry on a transport-level failure (timeout or
  /// connection error) — never on an HTTP status, and never for a non-idempotent
  /// verb. A single retry covers the common case of a phone switching from a dying
  /// WiFi to mobile data mid-request; more than that just delays telling the user
  /// something is wrong.
  Future<Response<dynamic>> _send(
    Future<Response<dynamic>> Function() send, {
    required bool retryable,
  }) async {
    try {
      return await send();
    } on DioException catch (error) {
      final failure = failureFromDio(error);
      if (retryable && failure.isRetryable && failure is! ServerFailure) {
        try {
          return await send();
        } on DioException catch (retryError) {
          throw failureFromDio(retryError);
        }
      }
      throw failure;
    } on SocketException catch (error) {
      throw NetworkFailure(message: error.message);
    }
  }
}
