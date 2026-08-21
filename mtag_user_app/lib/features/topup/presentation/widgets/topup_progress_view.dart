import 'package:decimal/decimal.dart';
import 'package:flutter/material.dart';
import 'package:mtag_user_app/core/models/topup.dart';
import 'package:mtag_user_app/core/models/vehicle.dart';
import 'package:mtag_user_app/core/utils/labels.dart';
import 'package:mtag_user_app/core/utils/money.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/shared/money_text.dart';
import 'package:mtag_user_app/features/topup/presentation/topup_controller.dart';
import 'package:mtag_user_app/features/topup/presentation/widgets/gateway_panels.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// What a top-up in flight looks like.
///
/// The two states this view exists for are the ones an optimistic implementation would
/// never render: **waiting** and **timed out**. The app reaches them routinely — the
/// aggregator flow has no completion signal at all, and the app-initiated flow has no
/// checkout URL — so they are designed states, not error paths.
///
/// `timedOut` is deliberately NOT a failure. The gateway callback is asynchronous and may
/// still land, so telling the user the payment failed would be a lie that costs them a
/// second payment.
class TopupProgressView extends StatelessWidget {
  const TopupProgressView({
    required this.state,
    required this.vehicle,
    required this.onDone,
    required this.onRetry,
    required this.onCheckAgain,
    super.key,
  });

  final TopupState state;
  final MyVehicle? vehicle;
  final VoidCallback onDone;
  final VoidCallback onRetry;
  final Future<void> Function() onCheckAgain;

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final textTheme = Theme.of(context).textTheme;

    return ListView(
      padding: const EdgeInsets.only(bottom: ClaySpace.xxl),
      children: [
        switch (state.progress) {
          TopupIdle() => const SizedBox.shrink(),
          TopupSubmitting() => _StatusCard(
            icon: Icons.hourglass_top_rounded,
            tone: ClayTone.primary,
            title: l10n.topupSubmitting,
            busy: true,
          ),
          final TopupWaitingForConfirmation waiting => _WaitingCard(
            amount: waiting.amount,
            tid: vehicle?.tag?.tid,
            plateNumber: vehicle?.plateNumber ?? '',
            onCheckAgain: onCheckAgain,
          ),
          final TopupConfirmed confirmed => _StatusCard(
            icon: Icons.check_circle_outline_rounded,
            tone: ClayTone.success,
            title: l10n.topupConfirmedTitle,
            message: l10n.topupConfirmedBody(
              Money.format(confirmed.amount, locale: localeTag(context)),
            ),
            // The balance shown here was RE-READ from the server after
            // confirmation, never computed as old + amount.
            trailing: confirmed.newBalance == null
                ? null
                : MoneyText(
                    confirmed.newBalance,
                    style: textTheme.displayMedium,
                  ),
            actionLabel: l10n.actionDone,
            onAction: onDone,
          ),
          final TopupFailed failed => _StatusCard(
            icon: Icons.error_outline_rounded,
            tone: ClayTone.danger,
            title: l10n.topupFailedTitle,
            message: failed.reason.isEmpty ? null : failed.reason,
            actionLabel: l10n.actionRetry,
            onAction: onRetry,
          ),
          final TopupTimedOut timedOut => _TimedOutCard(
            amount: timedOut.amount,
            onCheckAgain: onCheckAgain,
            onDone: onDone,
          ),
        },
      ],
    );
  }
}

/// Waiting for confirmation.
///
/// Carries the aggregator instructions inline, because this is exactly the moment they
/// are needed: a pending row exists, and the way to make it settle is to pay in the
/// JazzCash app using the TID shown here.
class _WaitingCard extends StatelessWidget {
  const _WaitingCard({
    required this.amount,
    required this.tid,
    required this.plateNumber,
    required this.onCheckAgain,
  });

  final Decimal amount;
  final String? tid;
  final String plateNumber;
  final Future<void> Function() onCheckAgain;

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final textTheme = Theme.of(context).textTheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _StatusCard(
          icon: Icons.schedule_rounded,
          tone: ClayTone.warning,
          title: l10n.topupWaitingTitle,
          message: l10n.topupWaitingBody(
            Money.format(amount, locale: localeTag(context)),
          ),
          busy: true,
        ),
        const SizedBox(height: ClaySpace.cardGap),

        JazzCashInstructionsPanel(tid: tid, plateNumber: plateNumber),
        const SizedBox(height: ClaySpace.cardGap),

        ClayButton(
          label: l10n.actionRefresh,
          icon: Icons.refresh_rounded,
          expand: true,
          onPressed: onCheckAgain,
        ),
        const SizedBox(height: ClaySpace.md),
        Text(
          l10n.topupNeverCreditedLocally,
          style: textTheme.labelSmall,
          textAlign: TextAlign.center,
        ),
      ],
    );
  }
}

/// Polling gave up after ~3 minutes.
///
/// Says clearly that the payment may still land and that paying again is not needed.
/// The alternative — showing a failure — is what produces duplicate payments.
class _TimedOutCard extends StatelessWidget {
  const _TimedOutCard({
    required this.amount,
    required this.onCheckAgain,
    required this.onDone,
  });

  final Decimal amount;
  final Future<void> Function() onCheckAgain;
  final VoidCallback onDone;

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _StatusCard(
          icon: Icons.watch_later_outlined,
          tone: ClayTone.warning,
          title: l10n.topupTimedOutTitle,
          message: l10n.topupTimedOutBody,
        ),
        const SizedBox(height: ClaySpace.cardGap),
        ClayButton(
          label: l10n.actionRefresh,
          icon: Icons.refresh_rounded,
          variant: ClayButtonVariant.primary,
          expand: true,
          onPressed: onCheckAgain,
        ),
        const SizedBox(height: ClaySpace.md),
        ClayButton(
          label: l10n.actionClose,
          variant: ClayButtonVariant.ghost,
          expand: true,
          onPressed: onDone,
        ),
      ],
    );
  }
}

class _StatusCard extends StatelessWidget {
  const _StatusCard({
    required this.icon,
    required this.tone,
    required this.title,
    this.message,
    this.trailing,
    this.actionLabel,
    this.onAction,
    this.busy = false,
  });

  final IconData icon;
  final ClayTone tone;
  final String title;
  final String? message;
  final Widget? trailing;
  final String? actionLabel;
  final VoidCallback? onAction;
  final bool busy;

  @override
  Widget build(BuildContext context) {
    final colors = clayToneColors(context, tone);
    final textTheme = Theme.of(context).textTheme;

    return ClayCard(
      depth: ClayDepth.hero,
      radius: ClayRadius.hero,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              ClaySurface(
                style: ClayDepthStyle.pressed,
                depth: ClayDepth.control,
                radius: ClayRadius.pill,
                width: 60,
                height: 60,
                child: Center(child: Icon(icon, size: 26, color: colors.ink)),
              ),
              const SizedBox(width: ClaySpace.lg),
              Expanded(
                child: Text(
                  title,
                  style: textTheme.titleLarge?.copyWith(color: colors.ink),
                ),
              ),
            ],
          ),
          if (message != null) ...[
            const SizedBox(height: ClaySpace.lg),
            Text(message!, style: textTheme.bodyMedium),
          ],
          if (trailing != null) ...[
            const SizedBox(height: ClaySpace.lg),
            Align(alignment: AlignmentDirectional.centerStart, child: trailing),
          ],
          if (busy) ...[
            const SizedBox(height: ClaySpace.lg),
            // A thin indeterminate bar, not a spinner — it reads as "in progress"
            // without implying the app knows how long is left. It does not.
            ClipRRect(
              borderRadius: BorderRadius.circular(ClayRadius.pill),
              child: LinearProgressIndicator(
                minHeight: 5,
                backgroundColor: colors.fill,
                valueColor: AlwaysStoppedAnimation(colors.ink),
              ),
            ),
          ],
          if (actionLabel != null && onAction != null) ...[
            const SizedBox(height: ClaySpace.xl),
            ClayButton(
              label: actionLabel!,
              variant: ClayButtonVariant.primary,
              expand: true,
              onPressed: onAction,
            ),
          ],
        ],
      ),
    );
  }
}
