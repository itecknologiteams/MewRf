import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mtag_user_app/core/network/refresh_interceptor.dart';

/// The single-flight refresh.
///
/// This is the test that matters most in the file, because the bug it prevents is
/// invisible until it happens to a real user and then logs them out of a valid 7-day
/// session. The backend runs `ROTATE_REFRESH_TOKENS: True` with
/// `BLACKLIST_AFTER_ROTATION: True`, so every successful refresh issues a NEW refresh
/// token and blacklists the old one. Two concurrent refreshes therefore mean the second
/// presents an already-retired token — and depending on ordering it can blacklist the
/// one the first just issued.
///
/// It is not a rare race either: the dashboard fans out several requests at once on a
/// cold start, and after six hours idle the access token is expired for all of them
/// simultaneously. The first screen after a lunch break is the worst case.
void main() {
  group('RefreshInterceptor', () {
    late _FakeRefreshServer server;
    late Dio dio;

    setUp(() {
      server = _FakeRefreshServer();
      dio = Dio(BaseOptions(baseUrl: 'http://test.local/api/v1/'))
        ..httpClientAdapter = server;
      dio.interceptors.add(
        RefreshInterceptor(
          refreshClient: () => Dio(
            BaseOptions(baseUrl: 'http://test.local/api/v1/'),
          )..httpClientAdapter = server,
          onSessionExpired: server.recordSessionExpired,
        ),
      );
    });

    test('refreshes once and replays the original request', () async {
      server.failFirstAttemptFor('auth/me/');

      final response = await dio.get<dynamic>('auth/me/');

      expect(response.statusCode, 200);
      expect(server.refreshCalls, 1);
      // The original GET was sent twice: once to get the 401, once as the replay.
      expect(server.callsTo('auth/me/'), 2);
      expect(server.sessionExpiredCount, 0);
    });

    test('EIGHT concurrent 401s trigger exactly ONE refresh', () async {
      // The rotation race. Without the single-flight lock this would be eight refreshes,
      // seven of which present a blacklisted token, and the user is logged out.
      _concurrentPaths.forEach(server.failFirstAttemptFor);

      final responses = await Future.wait(
        _concurrentPaths.map((path) => dio.get<dynamic>(path)),
      );

      expect(responses.every((r) => r.statusCode == 200), isTrue);
      expect(
        server.refreshCalls,
        1,
        reason:
            'Concurrent 401s must queue behind a single refresh, not each start '
            'their own — rotation blacklists every loser.',
      );
      for (final path in _concurrentPaths) {
        expect(
          server.callsTo(path),
          2,
          reason: '$path should be replayed once',
        );
      }
    });

    test(
      'a failed refresh clears the session and surfaces the ORIGINAL 401',
      () async {
        server
          ..failFirstAttemptFor('auth/me/')
          ..refreshShouldFail = true;

        await expectLater(
          dio.get<dynamic>('auth/me/'),
          throwsA(
            isA<DioException>().having(
              (e) => e.response?.statusCode,
              'status',
              401,
            ),
          ),
        );

        expect(server.sessionExpiredCount, 1);
        // Not replayed: there is no session to replay with.
        expect(server.callsTo('auth/me/'), 1);
      },
    );

    test('a request that 401s AGAIN after a replay does not loop', () async {
      // A persistent 401 must terminate. Without the replayed flag this would refresh,
      // replay, 401, refresh, replay… hammering the server behind a spinner.
      server.alwaysFail('accounts/1/transactions/');

      await expectLater(
        dio.get<dynamic>('accounts/1/transactions/'),
        throwsA(isA<DioException>()),
      );

      expect(server.refreshCalls, 1);
      expect(server.callsTo('accounts/1/transactions/'), 2);
    });

    test('/auth/login/ 401 is NOT treated as an expired session', () async {
      // Wrong credentials return 401 legitimately. Refreshing in response would be
      // nonsense, and clearing the jar would log out a user who is merely mistyping.
      server.alwaysFail('auth/login/');

      await expectLater(
        dio.post<dynamic>('auth/login/', data: const {'phone': 'x'}),
        throwsA(isA<DioException>()),
      );

      expect(server.refreshCalls, 0);
      expect(server.sessionExpiredCount, 0);
    });

    test('a 401 from the refresh endpoint itself does not recurse', () async {
      server.alwaysFail('auth/token/refresh/');

      await expectLater(
        dio.post<dynamic>('auth/token/refresh/'),
        throwsA(isA<DioException>()),
      );

      // The interceptor skipped it entirely rather than trying to refresh a refresh.
      expect(server.refreshCalls, 0);
    });

    test('a second refresh IS allowed after the first one completes', () async {
      // The lock is per-flight, not permanent — a session that expires again six hours
      // later must still be refreshable.
      server.failFirstAttemptFor('auth/me/');
      await dio.get<dynamic>('auth/me/');
      expect(server.refreshCalls, 1);

      server.failFirstAttemptFor('vehicles/my/');
      await dio.get<dynamic>('vehicles/my/');
      expect(server.refreshCalls, 2);
    });

    test('a non-401 error passes straight through', () async {
      server.failWith('accounts/vehicle/9/', 404);

      await expectLater(
        dio.get<dynamic>('accounts/vehicle/9/'),
        throwsA(
          isA<DioException>().having(
            (e) => e.response?.statusCode,
            'status',
            404,
          ),
        ),
      );
      expect(server.refreshCalls, 0);
    });
  });
}

const _concurrentPaths = [
  'auth/me/',
  'vehicles/my/',
  'accounts/my/summary/',
  'accounts/1/transactions/',
  'accounts/2/transactions/',
  'tolls/trips/1/',
  'tolls/plazas/',
  'tolls/rates/',
];

/// A Dio adapter standing in for the backend.
///
/// Counts calls per path and per-path decides whether the first attempt 401s, which is
/// how "the access token expired for every in-flight request at once" is reproduced.
class _FakeRefreshServer implements HttpClientAdapter {
  final Map<String, int> _calls = {};
  final Set<String> _failFirst = {};
  final Set<String> _alwaysFail = {};
  final Map<String, int> _failWith = {};

  int refreshCalls = 0;
  int sessionExpiredCount = 0;
  bool refreshShouldFail = false;

  /// Adds ~1ms of latency so concurrent requests genuinely overlap. Without it the
  /// futures could complete in sequence and the race would never be exercised.
  Duration latency = const Duration(milliseconds: 1);

  void failFirstAttemptFor(String path) => _failFirst.add(path);

  void alwaysFail(String path) => _alwaysFail.add(path);

  void failWith(String path, int status) => _failWith[path] = status;

  int callsTo(String path) => _calls[path] ?? 0;

  Future<void> recordSessionExpired() async => sessionExpiredCount++;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<List<int>>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    await Future<void>.delayed(latency);

    final path = options.path;
    final attempt = (_calls[path] ?? 0) + 1;
    _calls[path] = attempt;

    if (path.contains('auth/token/refresh/')) {
      // Counted only when the interceptor drove it. A direct call from the test (the
      // recursion check) hits _alwaysFail below before it is counted as a refresh.
      if (!_alwaysFail.contains(path)) refreshCalls++;
      if (refreshShouldFail || _alwaysFail.contains(path)) {
        return _json({'success': false, 'message': 'Session expired'}, 401);
      }
      return _json({'success': true, 'message': 'Token refreshed'}, 200);
    }

    final forcedStatus = _failWith[path];
    if (forcedStatus != null) {
      return _json({'success': false, 'message': 'nope'}, forcedStatus);
    }

    if (_alwaysFail.contains(path) ||
        (_failFirst.contains(path) && attempt == 1)) {
      return _json({
        'success': false,
        'message': 'Authentication required',
      }, 401);
    }

    return _json(
      {'success': true, 'message': 'Success', 'data': <String, Object?>{}},
      200,
    );
  }

  ResponseBody _json(Map<String, dynamic> body, int status) =>
      ResponseBody.fromString(
        _encode(body),
        status,
        headers: {
          Headers.contentTypeHeader: [Headers.jsonContentType],
        },
      );

  static String _encode(Map<String, dynamic> body) {
    // A tiny encoder rather than dart:convert, so the fixture stays obvious.
    final entries = body.entries.map((e) {
      final value = e.value;
      final encoded = switch (value) {
        String() => '"$value"',
        bool() => '$value',
        Map<dynamic, dynamic>() => '{}',
        _ => 'null',
      };
      return '"${e.key}":$encoded';
    });
    return '{${entries.join(',')}}';
  }

  @override
  void close({bool force = false}) {}
}
