import 'dart:developer' as developer;

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

/// Request logging with hard redaction.
///
/// Everything this app talks about is sensitive: the cookies ARE the session, the
/// TID is what a stranger needs to pay into (or inspect) someone's wallet, and a
/// balance in a log is a balance in a crash report. So:
///
///   * **Nothing at all is logged in release.** Not redacted — absent. `kDebugMode`
///     gates the whole interceptor, because "we redact carefully" is one missed
///     field away from a wallet balance in a bug tracker.
///   * In debug, cookie headers, passwords, `pp_*` gateway fields, TIDs and
///     balances are replaced before the line is written.
class LoggingInterceptor extends Interceptor {
  const LoggingInterceptor();

  static const _redacted = '«redacted»';

  static const _sensitiveHeaders = <String>{
    'cookie',
    'set-cookie',
    'authorization',
  };

  /// Body keys whose values never appear in a log.
  ///
  /// `pp_*` is matched by prefix as well — the JazzCash payload's field names are
  /// not fully pinned down and a new `pp_Something` must not become the one leak.
  static const _sensitiveKeys = <String>{
    'password',
    'old_password',
    'new_password',
    'access',
    'refresh',
    'access_token',
    'refresh_token',
    'tid',
    'epc',
    'balance',
    'new_balance',
    'balance_before',
    'balance_after',
    'total_balance',
    'cnic',
    'pp_securehash',
    'pp_password',
    'pp_merchantid',
  };

  bool get _enabled => kDebugMode;

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    if (_enabled) {
      _log('→ ${options.method} ${options.uri.path}');
      final query = options.uri.queryParameters;
      if (query.isNotEmpty) _log('  query ${_scrubMap(query)}');
      if (options.data != null) _log('  body ${_scrub(options.data)}');
      _log('  headers ${_scrubHeaders(options.headers)}');
    }
    handler.next(options);
  }

  @override
  void onResponse(
    Response<dynamic> response,
    ResponseInterceptorHandler handler,
  ) {
    if (_enabled) {
      _log(
        '← ${response.statusCode} ${response.requestOptions.method} '
        '${response.requestOptions.uri.path}',
      );
      _log('  body ${_scrub(response.data)}');
    }
    handler.next(response);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    if (_enabled) {
      _log(
        '✗ ${err.response?.statusCode ?? err.type.name} '
        '${err.requestOptions.method} ${err.requestOptions.uri.path}',
      );
      if (err.response?.data != null) {
        _log('  body ${_scrub(err.response!.data)}');
      }
    }
    handler.next(err);
  }

  void _log(String line) => developer.log(line, name: 'mtag.http');

  Map<String, dynamic> _scrubHeaders(Map<String, dynamic> headers) {
    return {
      for (final entry in headers.entries)
        entry.key: _sensitiveHeaders.contains(entry.key.toLowerCase())
            ? _redacted
            : entry.value,
    };
  }

  Object? _scrub(Object? value) {
    if (value is Map) return _scrubMap(value);
    if (value is List) return value.map(_scrub).toList();
    return value;
  }

  Map<String, Object?> _scrubMap(Map<dynamic, dynamic> map) {
    return {
      for (final entry in map.entries)
        entry.key.toString(): _isSensitive(entry.key.toString())
            ? _redacted
            : _scrub(entry.value),
    };
  }

  bool _isSensitive(String key) {
    final lower = key.toLowerCase();
    return _sensitiveKeys.contains(lower) || lower.startsWith('pp_');
  }
}
