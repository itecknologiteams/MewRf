import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mtag_user_app/core/data/cached.dart';
import 'package:mtag_user_app/core/utils/app_dates.dart';
import 'package:mtag_user_app/core/utils/labels.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// Renders the four states every list in this app must have: loading, empty, error,
/// offline.
///
/// A widget rather than a convention, because "every list needs four states" is the
/// kind of rule that holds for the first three screens and quietly stops holding on
/// the fifth. Routing them all through here means a new screen gets the offline
/// ribbon and the retry button whether or not its author remembered them.
class AsyncView<T> extends StatelessWidget {
  const AsyncView({
    required this.value,
    required this.data,
    required this.onRetry,
    this.loading,
    this.emptyCheck,
    this.empty,
    super.key,
  });

  final AsyncValue<T> value;

  /// Builds the content. [staleness] is non-null when the data came from cache, and
  /// the builder is expected to have already been given a ribbon by this widget — it
  /// is passed through for screens that want to mark individual figures too.
  final Widget Function(T data, Cached<Object?>? staleness) data;

  final Future<void> Function() onRetry;

  /// Clay skeletons, not a spinner.
  final Widget? loading;

  final bool Function(T data)? emptyCheck;
  final Widget? empty;

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);

    return value.when(
      loading: () => loading ?? const _DefaultSkeletons(),
      error: (error, _) => ClayErrorState(
        message: describeError(error, l10n),
        retryLabel: l10n.actionRetry,
        onRetry: onRetry,
      ),
      data: (data) {
        final staleness = data is Cached<Object?> ? data : null;
        final payload = staleness == null ? data : (staleness.value as T);

        if (emptyCheck?.call(payload) ?? false) {
          return RefreshIndicator(
            onRefresh: onRetry,
            child: ListView(
              children: [
                SizedBox(
                  height: MediaQuery.sizeOf(context).height * 0.6,
                  child: empty ?? const SizedBox.shrink(),
                ),
              ],
            ),
          );
        }

        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (staleness != null && !staleness.isFresh)
              Padding(
                padding: const EdgeInsets.only(bottom: ClaySpace.md),
                child: StaleDataRibbon(cached: staleness, onRefresh: onRetry),
              ),
            Expanded(child: this.data(payload, staleness)),
          ],
        );
      },
    );
  }
}

/// The "showing saved data" ribbon, with the actual time on it.
///
/// The time is not decoration. This app's central number is a balance the user
/// decides whether to enter a plaza on, and a two-hour-old balance presented without
/// its age is indistinguishable from a current one.
class StaleDataRibbon extends StatelessWidget {
  const StaleDataRibbon({required this.cached, this.onRefresh, super.key});

  final Cached<Object?> cached;
  final Future<void> Function()? onRefresh;

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final storedAt = cached.storedAt;
    return ClayStaleRibbon(
      message: l10n.offlineShowingSaved(
        storedAt == null
            ? l10n.unknownValue
            : AppDates.relative(storedAt, locale: localeTag(context)),
      ),
      onRefresh: onRefresh == null ? null : () => onRefresh!(),
    );
  }
}

class _DefaultSkeletons extends StatelessWidget {
  const _DefaultSkeletons();

  @override
  Widget build(BuildContext context) => ListView(
    physics: const NeverScrollableScrollPhysics(),
    children: const [
      ClaySkeletonCard(),
      SizedBox(height: ClaySpace.cardGap),
      ClaySkeletonCard(lines: 2),
      SizedBox(height: ClaySpace.cardGap),
      ClaySkeletonCard(lines: 2),
    ],
  );
}
