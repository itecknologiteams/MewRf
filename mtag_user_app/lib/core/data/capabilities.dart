import 'package:mtag_user_app/core/errors/app_failure.dart';

/// Which of the Phase 0 endpoints this backend actually has.
///
/// The app must run against a backend that predates its own Phase 0 changes — a
/// booth that has not been redeployed, a staging server a version behind — with
/// fewer features rather than a crash. So each optional endpoint is probed once,
/// its absence remembered, and a fallback used:
///
///   * `/vehicles/my/` missing -> `/auth/me/` plus per-vehicle fetches. Degraded,
///     because without it a consumer genuinely cannot enumerate what they own
///     (`GET /vehicles/` is IsOperator), so the fallback can only show vehicles the
///     app already knows an id for from its cache.
///   * `/accounts/my/summary/` missing -> aggregate client-side from `/vehicles/my/`.
///     No loss of function, just more round trips.
///   * `tid` missing from the tag serializer -> hide the JazzCash instruction block
///     entirely rather than render an empty field next to a "type this into
///     JazzCash" instruction.
///
/// Probed by USE, not by a preflight OPTIONS call: the first real request either
/// works or 404s, and a dedicated probe would double the cold-start cost to learn
/// something the next request reveals anyway.
// The record* methods below are deliberately methods rather than setters — see
// [BackendCapabilities.recordMyVehicles] for why.
// ignore_for_file: use_setters_to_change_properties
class BackendCapabilities {
  BackendCapabilities();

  bool? _hasMyVehicles;
  bool? _hasSummary;

  /// Null until the first attempt. Callers treat null as "try it".
  bool? get hasMyVehicles => _hasMyVehicles;

  bool? get hasSummary => _hasSummary;

  bool get shouldTryMyVehicles => _hasMyVehicles != false;

  bool get shouldTrySummary => _hasSummary != false;

  /// Records what a probe found.
  ///
  /// Named-argument methods rather than setters: `recordMyVehicles(present: false)`
  /// reads as "this is what the probe found", while
  /// `capabilities.hasMyVehicles = false` reads as an assertion about the world.
  /// The distinction matters because the value is only ever written from one place —
  /// the 404 path — and must not look like something a caller may decide.
  void recordMyVehicles({required bool present}) => _hasMyVehicles = present;

  /// See [recordMyVehicles].
  void recordSummary({required bool present}) => _hasSummary = present;

  /// Whether a failure means "this endpoint does not exist here".
  ///
  /// Only a 404 counts. A 401, a timeout or a 500 are transient or auth problems;
  /// treating those as "endpoint absent" would permanently downgrade the app to its
  /// fallback path because of one dropped connection.
  static bool indicatesMissingEndpoint(Object error) =>
      error is NotFoundFailure;

  /// Reset on logout, so a second account signing in against a different server
  /// re-probes instead of inheriting the first one's conclusions.
  void reset() {
    _hasMyVehicles = null;
    _hasSummary = null;
  }
}
