import 'dart:async';

import 'package:dio/dio.dart';

/// Paths that must never trigger a refresh attempt.
///
/// `/auth/login/` and `/auth/token/refresh/` legitimately answer 401, and
/// refreshing in response to a failed refresh is an infinite loop.
const _noRefreshPaths = <String>{
  'auth/login/',
  'auth/logout/',
  'auth/token/refresh/',
  'auth/register/',
};

/// Refreshes the session on 401 — **exactly once**, however many requests fail.
///
/// The single-flight lock is mandatory, not an optimisation. The backend sets
/// `ROTATE_REFRESH_TOKENS: True` and `BLACKLIST_AFTER_ROTATION: True`, so every
/// successful refresh issues a NEW refresh token and blacklists the old one. Two
/// refreshes racing means the second presents a token the first has already
/// retired: it fails, and depending on ordering it can blacklist the token the
/// first just issued. The user is logged out despite having a valid 7-day session.
///
/// This is not a rare race. The dashboard fans out several requests in parallel on
/// a cold start, and after 6 hours of idle the access token is expired for all of
/// them at once — so the very first screen after a lunch break is the worst case.
///
/// The flow:
///   1. First 401 takes the lock and calls `/auth/token/refresh/`.
///   2. Concurrent 401s await the same [Future] instead of starting their own.
///   3. On success everyone replays their original request, once.
///   4. On failure the jar is cleared and [onSessionExpired] fires, which routes
///      to login. The original 401 is what propagates — not the refresh's error,
///      which would report "no refresh token" for a request the user made.
class RefreshInterceptor extends Interceptor {
  RefreshInterceptor({
    required Dio Function() refreshClient,
    required Future<void> Function() onSessionExpired,
  }) : _refreshClient = refreshClient,
       _onSessionExpired = onSessionExpired;

  /// A Dio sharing the cookie jar but NOT this interceptor — otherwise a 401 from
  /// the refresh call re-enters here.
  final Dio Function() _refreshClient;

  final Future<void> Function() _onSessionExpired;

  /// Non-null while a refresh is in flight. The lock.
  Future<bool>? _inFlight;

  /// Requests already replayed once, so a persistent 401 cannot ping-pong.
  ///
  /// Keyed per request; a replay that 401s again is a genuinely dead session, and
  /// retrying it forever would hammer the server while showing the user a spinner.
  static const _replayedFlag = 'mtag_refresh_replayed';

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    final response = err.response;
    final request = err.requestOptions;

    final isUnauthorised = response?.statusCode == 401;
    final alreadyReplayed = request.extra[_replayedFlag] == true;
    final isAuthPath = _noRefreshPaths.any((p) => request.path.contains(p));

    if (!isUnauthorised || alreadyReplayed || isAuthPath) {
      handler.next(err);
      return;
    }

    final refreshed = await _refreshOnce();

    if (!refreshed) {
      // Session is genuinely over. Surface the ORIGINAL 401 so the caller reports
      // what it asked for, not a refresh failure it never made.
      handler.next(err);
      return;
    }

    try {
      final replayed = await _replay(request);
      handler.resolve(replayed);
    } on DioException catch (error) {
      handler.next(error);
    }
  }

  /// Returns whether the session is now usable. Joins an in-flight refresh rather
  /// than starting a second one.
  Future<bool> _refreshOnce() {
    final existing = _inFlight;
    if (existing != null) return existing;

    final future = _performRefresh();
    _inFlight = future;
    // Cleared in a whenComplete rather than a finally inside _performRefresh so
    // that late arrivals joining the same tick still see the shared future.
    future.whenComplete(() => _inFlight = null);
    return future;
  }

  Future<bool> _performRefresh() async {
    try {
      final response = await _refreshClient().post<dynamic>(
        'auth/token/refresh/',
        // The body is empty on purpose. TokenRefreshCookieView reads
        // request.COOKIES['refresh_token'] and ignores the body entirely; the
        // cookie manager attaches it.
        data: const <String, dynamic>{},
      );
      final success =
          response.statusCode != null &&
          response.statusCode! >= 200 &&
          response.statusCode! < 300;
      if (!success) {
        await _onSessionExpired();
      }
      return success;
    } on DioException {
      // Includes the 401 the view returns when the refresh cookie is missing,
      // expired, or blacklisted by a previous rotation.
      await _onSessionExpired();
      return false;
    }
  }

  Future<Response<dynamic>> _replay(RequestOptions request) {
    final options = Options(
      method: request.method,
      headers: request.headers,
      responseType: request.responseType,
      contentType: request.contentType,
      sendTimeout: request.sendTimeout,
      receiveTimeout: request.receiveTimeout,
      // A replay that 401s again must not start another cycle.
      extra: {...request.extra, _replayedFlag: true},
      validateStatus: request.validateStatus,
    );

    return _refreshClient().request<dynamic>(
      request.path,
      data: request.data,
      queryParameters: request.queryParameters,
      cancelToken: request.cancelToken,
      options: options,
    );
  }
}
