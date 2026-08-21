import 'dart:convert';
import 'dart:io';

import 'package:drift/drift.dart';
import 'package:drift/native.dart';
import 'package:path_provider/path_provider.dart';

part 'cache_database.g.dart';

/// One cached API document, with the time it was written.
///
/// A single key/value table rather than a relational mirror of the API. The cache
/// exists so the app opens with real content on a dead connection, not so it can
/// query offline — there is no screen that filters or joins locally. A schema per
/// endpoint would be five migrations to maintain for a feature whose entire job is
/// "show me the last thing the server said".
///
/// [storedAt] is NOT optional and nothing writes here without it. Every
/// cache-served balance in this app is displayed with its age, and a row that has
/// forgotten when it was written cannot be displayed at all — it would render as a
/// current balance, which is the one outcome worse than showing nothing.
class CacheEntries extends Table {
  TextColumn get key => text()();

  /// The `data` member of the envelope, re-encoded.
  TextColumn get payload => text()();

  DateTimeColumn get storedAt => dateTime()();

  @override
  Set<Column<Object>> get primaryKey => {key};
}

@DriftDatabase(tables: [CacheEntries])
class CacheDatabase extends _$CacheDatabase {
  CacheDatabase() : super(_open());

  CacheDatabase.forTesting(super.e);

  @override
  int get schemaVersion => 1;

  static QueryExecutor _open() {
    return LazyDatabase(() async {
      final dir = await getApplicationSupportDirectory();
      final file = File('${dir.path}/mtag_cache.sqlite');
      return NativeDatabase.createInBackground(file);
    });
  }

  Future<void> write(String key, Object? data, {DateTime? at}) async {
    await into(cacheEntries).insertOnConflictUpdate(
      CacheEntry(
        key: key,
        payload: jsonEncode(data),
        storedAt: at ?? DateTime.now().toUtc(),
      ),
    );
  }

  /// Reads a cached document, or null if absent.
  ///
  /// A corrupt payload is treated as absent and deleted. Throwing here would mean a
  /// single bad row makes the app unopenable offline, which is the exact situation
  /// the cache is meant to rescue.
  Future<CachedDocument?> read(String key) async {
    final row = await (select(
      cacheEntries,
    )..where((t) => t.key.equals(key))).getSingleOrNull();
    if (row == null) return null;
    try {
      return CachedDocument(
        data: jsonDecode(row.payload),
        storedAt: row.storedAt,
      );
    } on FormatException {
      await (delete(cacheEntries)..where((t) => t.key.equals(key))).go();
      return null;
    }
  }

  /// Wipes everything. Called on logout — a cached balance surviving a logout would
  /// show the previous user's money to the next one on a shared handset, which is
  /// common enough here to design for.
  Future<void> clearAll() => delete(cacheEntries).go();
}

class CachedDocument {
  const CachedDocument({required this.data, required this.storedAt});

  final dynamic data;
  final DateTime storedAt;

  Duration get age => DateTime.now().toUtc().difference(storedAt.toUtc());
}

/// The cache key namespace.
///
/// Keys are per-user where the data is per-user, so a second account signing in on
/// the same handset cannot read the first one's cached balances before its own
/// fetch lands.
abstract final class CacheKeys {
  static String me(int userId) => 'me:$userId';

  static String myVehicles(int userId) => 'vehicles.my:$userId';

  static String summary(int userId) => 'accounts.summary:$userId';

  static String account(int accountId) => 'account:$accountId';

  static String transactionsFirstPage(int accountId) => 'txns.p1:$accountId';

  static String tripsFirstPage(int vehicleId) => 'trips.p1:$vehicleId';

  /// Every vehicle's trips in one list, so the Activity tab has something to show
  /// offline. Keyed by USER, not vehicle: the union is a property of the account
  /// holder, and keying it by vehicle would collide with the per-vehicle pages above.
  static String myTripsFirstPage(int userId) => 'trips.my.p1:$userId';

  static const String plazas = 'tolls.plazas';
  static const String fares = 'tolls.fares';
  static const String categories = 'tolls.categories';
}
