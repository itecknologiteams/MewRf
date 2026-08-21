import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mtag_user_app/core/cache/cache_database.dart';
import 'package:mtag_user_app/core/data/auth_repository.dart';
import 'package:mtag_user_app/core/data/capabilities.dart';
import 'package:mtag_user_app/core/data/payment_repository.dart';
import 'package:mtag_user_app/core/data/toll_repository.dart';
import 'package:mtag_user_app/core/data/wallet_repository.dart';
import 'package:mtag_user_app/core/network/api_client.dart';
import 'package:mtag_user_app/core/storage/secure_store.dart';
import 'package:mtag_user_app/features/notifications/data/push_repository.dart';

/// Dependency injection.
///
/// Providers, not singletons. Every one of these is overridable in a test, which is
/// what makes the refresh single-flight and the top-up pending/timeout branches
/// testable without a live server.
///
/// [apiClientProvider] is seeded via an override in `main` rather than constructed
/// lazily here, because opening the cookie jar and the cache is async and the app
/// must not paint its first frame — and certainly must not decide whether the user
/// is logged in — before the jar is on disk.

/// Overridden in `main`. Reading it without the override is a programming error.
final apiClientProvider = Provider<ApiClient>((ref) {
  throw StateError(
    'apiClientProvider must be overridden in main() with the instance created by '
    'ApiClient.create(). It is async because the cookie jar is on disk, and the '
    'session cannot be probed before the jar is open.',
  );
});

/// Overridden in `main`, same reason.
final cacheDatabaseProvider = Provider<CacheDatabase>((ref) {
  throw StateError('cacheDatabaseProvider must be overridden in main()');
});

final secureStoreProvider = Provider<SecureStore>((ref) => const SecureStore());

/// One instance for the app's lifetime: the probe results are learned once, and a
/// per-request instance would re-probe a missing endpoint on every call.
final capabilitiesProvider = Provider<BackendCapabilities>(
  (ref) => BackendCapabilities(),
);

final authRepositoryProvider = Provider<AuthRepository>(
  (ref) => AuthRepository(
    client: ref.watch(apiClientProvider),
    cache: ref.watch(cacheDatabaseProvider),
    secureStore: ref.watch(secureStoreProvider),
  ),
);

final walletRepositoryProvider = Provider<WalletRepository>(
  (ref) => WalletRepository(
    client: ref.watch(apiClientProvider),
    cache: ref.watch(cacheDatabaseProvider),
    capabilities: ref.watch(capabilitiesProvider),
  ),
);

final tollRepositoryProvider = Provider<TollRepository>(
  (ref) => TollRepository(
    client: ref.watch(apiClientProvider),
    cache: ref.watch(cacheDatabaseProvider),
  ),
);

final paymentRepositoryProvider = Provider<PaymentRepository>(
  (ref) => PaymentRepository(client: ref.watch(apiClientProvider)),
);

/// Device registration for push. No cache: a token is only ever useful live, and a stale
/// one persisted across a reinstall would be registered for a device that cannot receive.
final pushRepositoryProvider = Provider<PushRepository>(
  (ref) => PushRepository(client: ref.watch(apiClientProvider)),
);
