import 'package:mtag_user_app/core/cache/cache_database.dart';
import 'package:mtag_user_app/core/errors/app_failure.dart';

/// A value plus where it came from and when.
///
/// Every repository read returns one of these, not a bare value. That is the
/// mechanism behind a hard rule: **a cached balance is never displayed without its
/// age.** If the value carried no provenance, the widget could not know whether to
/// show a stale ribbon, and the default would be to show a two-hour-old balance as
/// current — which is what the driver then decides whether to enter a plaza on.
class Cached<T> {
  const Cached({
    required this.value,
    required this.isFresh,
    this.storedAt,
    this.staleReason,
  });

  /// Straight from the server.
  const Cached.fresh(T value) : this(value: value, isFresh: true);

  /// From disk, with the time it was written and why the network read did not
  /// happen (or failed).
  const Cached.stale(T value, DateTime storedAt, AppFailure? reason)
    : this(
        value: value,
        isFresh: false,
        storedAt: storedAt,
        staleReason: reason,
      );

  final T value;

  final bool isFresh;

  /// When the cache row was written. Null for fresh reads.
  final DateTime? storedAt;

  /// The failure that forced the fallback, when there was one.
  final AppFailure? staleReason;

  Duration? get age => storedAt == null
      ? null
      : DateTime.now().toUtc().difference(storedAt!.toUtc());

  Cached<R> map<R>(R Function(T value) transform) => Cached(
    value: transform(value),
    isFresh: isFresh,
    storedAt: storedAt,
    staleReason: staleReason,
  );
}

/// Fetch from the network, fall back to cache, and stamp the result.
///
/// The network is tried FIRST every time — this is not a cache-first store. A
/// balance is the whole point of the app and a stale one is only ever a
/// consolation prize when the request fails, never a way to save a round trip.
///
/// A successful fetch writes through. A failure returns the cached copy marked
/// stale, and only rethrows when there is nothing cached — an error screen is
/// better than an empty one, but real content with a "saved from 14:32" ribbon is
/// better than either.
Future<Cached<T>> fetchWithCache<T>({
  required CacheDatabase cache,
  required String key,
  required Future<T> Function() fetch,
  required Object? Function(T value) encode,
  required T Function(dynamic json) decode,
}) async {
  try {
    final value = await fetch();
    await cache.write(key, encode(value));
    return Cached.fresh(value);
  } on AppFailure catch (failure) {
    // An expired session must NOT be answered with cached content: the user is
    // about to be routed to login, and showing them a balance on the way out is
    // both confusing and a small leak on a shared handset.
    if (failure is UnauthorisedFailure) rethrow;

    final cached = await cache.read(key);
    if (cached == null) rethrow;

    try {
      return Cached.stale(decode(cached.data), cached.storedAt, failure);
    } on Object {
      // A payload written by an older version of the app that no longer parses.
      // The original network failure is the useful error, not the decode one.
      rethrow;
    }
  }
}

/// Reads only the cache. Used by the splash screen to paint real content before
/// the first network call resolves.
Future<Cached<T>?> readCacheOnly<T>({
  required CacheDatabase cache,
  required String key,
  required T Function(dynamic json) decode,
}) async {
  final cached = await cache.read(key);
  if (cached == null) return null;
  try {
    return Cached.stale(decode(cached.data), cached.storedAt, null);
  } on Object {
    return null;
  }
}
