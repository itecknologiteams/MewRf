import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mtag_user_app/core/models/toll.dart';
import 'package:mtag_user_app/core/providers.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/shared/support_actions.dart';
import 'package:mtag_user_app/features/topup/domain/payment_gateway.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';
import 'package:url_launcher/url_launcher.dart';

/// Renders the panel for whichever method is selected.
class GatewayPanel extends StatelessWidget {
  const GatewayPanel({
    required this.gateway,
    required this.gatewayContext,
    this.child,
    super.key,
  });

  final PaymentGateway gateway;
  final GatewayContext gatewayContext;

  /// The amount step, when this method can take an amount from the app.
  final Widget? child;

  @override
  Widget build(BuildContext context) {
    final availability = gateway.availabilityFor(gatewayContext);

    return switch (gateway) {
      JazzCashAggregatorGateway() => JazzCashInstructionsPanel(
        tid: gatewayContext.tid,
        plateNumber: gatewayContext.plateNumber,
      ),
      JazzCashCheckoutGateway() =>
        availability == GatewayAvailability.available
            ? (child ?? const SizedBox.shrink())
            : const _CheckoutNotConfiguredPanel(),
      CashAtBoothGateway() => CashAtBoothPanel(
        plateNumber: gatewayContext.plateNumber,
      ),
      EasypaisaGateway() => const _ComingSoonPanel(method: _Method.easypaisa),
      CardGateway() => const _ComingSoonPanel(method: _Method.card),
      _ => const SizedBox.shrink(),
    };
  }
}

/// **Flow A.** The instructions that actually get money into an account today.
///
/// The customer opens JazzCash, picks M-Tag, types their TID, and pays. JazzCash calls
/// `/payments/jazzcash/inquiry/` to show them their own name and plate as a check, then
/// `/payments/jazzcash/payment/` to credit the account idempotently.
///
/// This app is not in that loop, so this panel is deliberately not a form. It is a big
/// copyable TID, numbered steps, and a deep link — plus a "check again" that polls the
/// server, because a callback the app never sees is the only completion signal there is.
class JazzCashInstructionsPanel extends StatelessWidget {
  const JazzCashInstructionsPanel({
    required this.tid,
    required this.plateNumber,
    super.key,
  });

  final String? tid;
  final String plateNumber;

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final palette = ClayTheme.of(context).palette;
    final textTheme = Theme.of(context).textTheme;

    // No TID means the instructions cannot be followed — there is nothing for the
    // customer to type. Hidden rather than shown with a blank, per the degrade-gracefully
    // rule: an older backend omits `tid` from TagSerializer.
    if (tid == null || tid!.isEmpty) {
      return ClayBanner(
        icon: Icons.info_outline_rounded,
        title: l10n.topupJazzCashNoTidTitle,
        message: l10n.topupJazzCashNoTidBody,
        actionLabel: l10n.actionCallSupport,
        onAction: () => callSupport(context),
      );
    }

    final steps = [
      l10n.topupJazzCashStep1,
      l10n.topupJazzCashStep2,
      l10n.topupJazzCashStep3,
      l10n.topupJazzCashStep4,
      l10n.topupJazzCashStep5,
    ];

    return ClayCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(l10n.topupJazzCashStepsTitle, style: textTheme.titleLarge),
          const SizedBox(height: ClaySpace.lg),

          for (var i = 0; i < steps.length; i++) ...[
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                ClaySurface(
                  style: ClayDepthStyle.pressed,
                  depth: ClayDepth.nested,
                  radius: ClayRadius.pill,
                  width: 26,
                  height: 26,
                  child: Center(
                    child: Text(
                      '${i + 1}',
                      style: textTheme.labelSmall?.copyWith(
                        color: palette.primaryOnSurface,
                        fontWeight: FontWeight.w700,
                      ),
                      textDirection: TextDirection.ltr,
                    ),
                  ),
                ),
                const SizedBox(width: ClaySpace.md),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.only(top: 3),
                    child: Text(steps[i], style: textTheme.bodyMedium),
                  ),
                ),
              ],
            ),
            if (i < steps.length - 1) const SizedBox(height: ClaySpace.md),
          ],

          const SizedBox(height: ClaySpace.xl),

          // The TID, large and copyable. It is read off this screen and typed into
          // another app, so it is monospaced and letter-spaced.
          Text(l10n.tagTid, style: textTheme.labelMedium),
          const SizedBox(height: ClaySpace.sm),
          GestureDetector(
            onTap: () => copyToClipboard(
              context,
              value: tid!,
              label: l10n.tagTid,
            ),
            child: ClaySurface(
              style: ClayDepthStyle.pressed,
              depth: ClayDepth.control,
              radius: ClayRadius.control,
              padding: const EdgeInsets.all(ClaySpace.lg),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      tid!,
                      style: textTheme.titleLarge?.copyWith(
                        fontFamily: 'Mono',
                        letterSpacing: 1.8,
                      ),
                      textDirection: TextDirection.ltr,
                    ),
                  ),
                  Icon(Icons.copy_rounded, size: 18, color: palette.textMuted),
                ],
              ),
            ),
          ),

          const SizedBox(height: ClaySpace.md),
          Text(
            // The amount is entered in JazzCash, not here. Saying so prevents the
            // obvious misread of a screen with no amount field.
            l10n.topupJazzCashAmountNote,
            style: textTheme.bodySmall,
          ),

          const SizedBox(height: ClaySpace.xl),
          ClayButton(
            label: l10n.topupJazzCashOpenApp,
            icon: Icons.open_in_new_rounded,
            variant: ClayButtonVariant.primary,
            expand: true,
            onPressed: () => _openJazzCash(context),
          ),
        ],
      ),
    );
  }

  Future<void> _openJazzCash(BuildContext context) async {
    final l10n = AppL10n.of(context);
    final link = const JazzCashAggregatorGateway().deepLink();
    var launched = false;
    if (link != null) {
      launched = await launchUrl(link, mode: LaunchMode.externalApplication);
    }
    if (!launched && context.mounted) {
      // The scheme is a guess at best and the app may not be installed. Said plainly
      // rather than failing silently on a button the user just pressed.
      showClaySnack(
        context,
        message: l10n.topupJazzCashOpenAppFailed,
        tone: ClayTone.warning,
      );
    }
  }
}

/// **Flow B, unconfigured.** Which is its normal state.
///
/// `/payments/topup/` returns `pp_*` fields but **no checkout URL**, the merchant
/// password is (correctly) withheld from the response so the payload is not a complete
/// Hosted Checkout form, and `JAZZCASH_VERIFY_HASH` is off with the hashing formula
/// unconfirmed. With `MTAG_JAZZCASH_CHECKOUT_URL` unset there is nowhere to send the
/// user, and this panel says so and points at the path that works.
class _CheckoutNotConfiguredPanel extends StatelessWidget {
  const _CheckoutNotConfiguredPanel();

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    return ClayBanner(
      icon: Icons.build_outlined,
      title: l10n.topupCheckoutUnavailableTitle,
      message: l10n.topupCheckoutUnavailableBody,
    );
  }
}

enum _Method { easypaisa, card }

/// Easypaisa and card: **no backend implementation of any kind.**
///
/// No endpoint, no service, no model field. The seam exists so wiring one up later is a
/// single class; the UI exists so the option is visible. What it does NOT do is invent
/// an endpoint or offer a button that silently fails — either would be worse than the
/// honest "not yet", because a user who taps a dead Pay button assumes their money is
/// somewhere.
class _ComingSoonPanel extends StatelessWidget {
  const _ComingSoonPanel({required this.method});

  final _Method method;

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    return ClayBanner(
      icon: Icons.schedule_rounded,
      title: method == _Method.easypaisa
          ? l10n.topupEasypaisaComingSoonTitle
          : l10n.topupCardComingSoonTitle,
      message: method == _Method.easypaisa
          ? l10n.topupEasypaisaComingSoonBody
          : l10n.topupCardComingSoonBody,
    );
  }
}

/// Cash at a booth. Pure information, and always available.
///
/// The operator tops up by TID or plate and the POS prints a receipt. The app never
/// calls that endpoint — `/accounts/topup/cash/` is `IsOperator` surface.
class CashAtBoothPanel extends ConsumerWidget {
  const CashAtBoothPanel({required this.plateNumber, super.key});

  final String plateNumber;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppL10n.of(context);
    final palette = ClayTheme.of(context).palette;
    final textTheme = Theme.of(context).textTheme;
    final plazas = ref.watch(plazaListProvider);

    return ClayCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(l10n.topupCashTitle, style: textTheme.titleLarge),
          const SizedBox(height: ClaySpace.md),
          Text(l10n.topupCashBody, style: textTheme.bodyMedium),
          const SizedBox(height: ClaySpace.xl),

          Text(l10n.topupCashWhatToBring, style: textTheme.titleMedium),
          const SizedBox(height: ClaySpace.md),
          for (final item in [
            l10n.topupCashBringTag,
            l10n.topupCashBringPlate(plateNumber),
            l10n.topupCashBringCash,
          ]) ...[
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  Icons.check_rounded,
                  size: 17,
                  color: palette.successOnSurface,
                ),
                const SizedBox(width: ClaySpace.sm),
                Expanded(child: Text(item, style: textTheme.bodyMedium)),
              ],
            ),
            const SizedBox(height: ClaySpace.sm),
          ],

          const SizedBox(height: ClaySpace.lg),
          Text(l10n.topupCashPlazas, style: textTheme.titleMedium),
          const SizedBox(height: ClaySpace.md),

          // The plaza list comes from `/tolls/plazas/`, never a hardcoded list — the
          // operator adds interchanges, and a baked-in list would send someone to a
          // plaza that no longer exists or omit the one nearest them.
          plazas.when(
            loading: () => const Column(
              children: [
                ClaySkeleton.line(height: 13),
                SizedBox(height: ClaySpace.sm),
                ClaySkeleton.line(height: 13, width: 200),
              ],
            ),
            error: (_, _) => Text(
              l10n.errorNetwork,
              style: textTheme.bodySmall,
            ),
            data: (plazaList) => Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (final plaza in plazaList)
                  Padding(
                    padding: const EdgeInsets.only(bottom: ClaySpace.sm),
                    child: Row(
                      children: [
                        Text(
                          plaza.displayId,
                          style: textTheme.labelSmall?.copyWith(
                            fontFamily: 'Mono',
                          ),
                          textDirection: TextDirection.ltr,
                        ),
                        const SizedBox(width: ClaySpace.md),
                        Expanded(
                          child: Text(plaza.name, style: textTheme.bodyMedium),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Active plazas, for the cash panel and the fares screen.
final plazaListProvider = FutureProvider<List<Plaza>>((ref) async {
  final repository = ref.watch(tollRepositoryProvider);
  final cached = await repository.plazas();
  return cached.value.where((p) => p.isActive).toList(growable: false)
    ..sort((a, b) => a.plazaId.compareTo(b.plazaId));
});
