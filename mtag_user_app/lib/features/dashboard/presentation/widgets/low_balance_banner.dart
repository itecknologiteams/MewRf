import 'package:flutter/material.dart';
import 'package:mtag_user_app/core/env/app_env.dart';
import 'package:mtag_user_app/core/models/vehicle.dart';
import 'package:mtag_user_app/core/utils/labels.dart';
import 'package:mtag_user_app/core/utils/money.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// The low-balance warning, in two strengths.
///
/// The distinction is the whole point:
///
///   * **Under Rs. 50 — urgent, and it NAMES THE PLATE.** Entry requires a balance of
///     at least `MINIMUM_ACCOUNT_BALANCE`; below it the barrier does not open. A
///     driver about to be turned away at a gate needs to know which of their vehicles
///     it is, not that "a balance is low".
///   * **Under Rs. 200 — soft.** Will open, top up soon. A client-side nicety with no
///     server rule behind it.
///
/// Renders nothing when neither applies, so the caller can drop it in unconditionally.
class LowBalanceBanner extends StatelessWidget {
  const LowBalanceBanner({
    required this.blocked,
    required this.low,
    required this.onTopUp,
    super.key,
  });

  final List<MyVehicle> blocked;
  final List<MyVehicle> low;
  final void Function(MyVehicle vehicle) onTopUp;

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);

    if (blocked.isEmpty && low.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (blocked.isNotEmpty) ...[
          ClayBanner(
            icon: Icons.block_rounded,
            tone: ClayTone.danger,
            title: blocked.length == 1
                ? l10n.lowBalanceTitle(blocked.first.plateNumber)
                : l10n.lowBalanceManyTitle(blocked.length),
            message: blocked.length == 1
                ? l10n.lowBalanceBody(
                    Money.format(
                      blocked.first.balance,
                      locale: localeTag(context),
                    ),
                    AppEnv.minimumEntryBalance,
                  )
                : l10n.lowBalanceManyBody(
                    _plateList(blocked),
                    AppEnv.minimumEntryBalance,
                  ),
            actionLabel: l10n.actionTopUp,
            onAction: () => onTopUp(blocked.first),
          ),
          const SizedBox(height: ClaySpace.cardGap),
        ],
        if (low.isNotEmpty) ...[
          ClayBanner(
            icon: Icons.warning_amber_rounded,
            title: l10n.lowBalanceSoonTitle,
            // count drives the plural: one plate "is" running low, several "are".
            message: l10n.lowBalanceSoonBody(
              low.length,
              _plateList(low),
              AppEnv.minimumEntryBalance,
            ),
            actionLabel: l10n.actionTopUp,
            onAction: () => onTopUp(low.first),
          ),
          const SizedBox(height: ClaySpace.cardGap),
        ],
      ],
    );
  }

  /// `KDE1836, KDE1837 and KDE1838`, truncated past three.
  ///
  /// A list of eight plates in a banner is a wall of text nobody reads; three plus a
  /// count keeps it scannable while still being specific.
  static String _plateList(List<MyVehicle> vehicles) {
    final plates = vehicles.map((v) => v.plateNumber).toList();
    if (plates.length <= 3) return plates.join(', ');
    return '${plates.take(3).join(', ')} +${plates.length - 3}';
  }
}
