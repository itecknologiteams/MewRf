import 'package:decimal/decimal.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:mtag_user_app/core/env/app_env.dart';
import 'package:mtag_user_app/core/utils/labels.dart';
import 'package:mtag_user_app/core/utils/money.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/shared/money_text.dart';
import 'package:mtag_user_app/features/topup/domain/payment_gateway.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// The amount step: presets, custom entry, and a live "balance after".
///
/// The Rs. 100 minimum is enforced here as well as on the server (twice, in
/// `InitiateTopupSerializer` and `JazzCashService.initiate_topup`). Client-side purely so
/// the user is warned before they submit rather than bounced afterwards — the server
/// remains the authority, and if it ever rejects an amount this screen allowed, the
/// server's wording is what gets shown.
///
/// There is no Rs. 50 preset: it would be below the minimum, and offering an amount that
/// is guaranteed to be rejected is a trap.
class AmountStep extends StatefulWidget {
  const AmountStep({
    required this.amount,
    required this.currentBalance,
    required this.onChanged,
    required this.onSubmit,
    this.errorKey,
    this.isBusy = false,
    super.key,
  });

  final Decimal? amount;
  final Decimal? currentBalance;

  /// Non-null when the amount is invalid. `'min'` is the client-side minimum; anything
  /// else is the server's own message, shown verbatim.
  final String? errorKey;

  final ValueChanged<Decimal?> onChanged;
  final VoidCallback onSubmit;
  final bool isBusy;

  @override
  State<AmountStep> createState() => _AmountStepState();
}

class _AmountStepState extends State<AmountStep> {
  final _controller = TextEditingController();
  bool _customMode = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _selectPreset(int rupees) {
    setState(() {
      _customMode = false;
      _controller.clear();
    });
    widget.onChanged(TopupPresets.asDecimal(rupees));
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final palette = ClayTheme.of(context).palette;
    final textTheme = Theme.of(context).textTheme;
    final amount = widget.amount;

    final balanceAfter = (amount == null || widget.currentBalance == null)
        ? null
        : widget.currentBalance! + amount;

    final errorText = switch (widget.errorKey) {
      null => null,
      'min' => l10n.topupMinimum(AppEnv.minimumTopupAmount),
      final String message => message,
    };

    return ClayCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(l10n.topupAmount, style: textTheme.titleLarge),
          const SizedBox(height: ClaySpace.lg),

          Wrap(
            spacing: ClaySpace.sm,
            runSpacing: ClaySpace.sm,
            children: [
              for (final preset in TopupPresets.amounts)
                ClayFilterChip(
                  label: Money.format(
                    TopupPresets.asDecimal(preset),
                    locale: localeTag(context),
                  ),
                  selected:
                      !_customMode && amount == TopupPresets.asDecimal(preset),
                  onTap: () => _selectPreset(preset),
                ),
              ClayFilterChip(
                label: l10n.topupAmountCustom,
                selected: _customMode,
                onTap: () {
                  setState(() => _customMode = true);
                  widget.onChanged(null);
                },
              ),
            ],
          ),

          if (_customMode) ...[
            const SizedBox(height: ClaySpace.lg),
            ClayTextField(
              controller: _controller,
              label: l10n.topupAmount,
              hint: '${AppEnv.minimumTopupAmount}',
              prefixIcon: Icons.payments_outlined,
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
              autofocus: true,
              inputFormatters: [
                // Digits and at most one decimal point. Money is Decimal all the way
                // through, so the text is parsed with Decimal.tryParse rather than
                // double.parse.
                FilteringTextInputFormatter.allow(RegExp('[0-9.]')),
              ],
              errorText: errorText,
              onChanged: (text) =>
                  widget.onChanged(text.isEmpty ? null : Money.tryParse(text)),
            ),
          ] else if (errorText != null) ...[
            const SizedBox(height: ClaySpace.md),
            Row(
              children: [
                Icon(
                  Icons.error_outline_rounded,
                  size: 15,
                  color: palette.dangerOnSurface,
                ),
                const SizedBox(width: ClaySpace.xs + 2),
                Expanded(
                  child: Text(
                    errorText,
                    style: textTheme.bodySmall?.copyWith(
                      color: palette.dangerOnSurface,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
          ],

          const SizedBox(height: ClaySpace.lg),
          Text(
            l10n.topupMinimum(AppEnv.minimumTopupAmount),
            style: textTheme.bodySmall,
          ),

          // "Balance after top-up", live.
          //
          // A PREVIEW, not a credit. Nothing here changes the displayed balance —
          // that only ever moves when the server says it has.
          if (balanceAfter != null) ...[
            const SizedBox(height: ClaySpace.lg),
            ClaySurface(
              style: ClayDepthStyle.pressed,
              depth: ClayDepth.nested,
              radius: ClayRadius.control,
              padding: const EdgeInsets.all(ClaySpace.lg),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      l10n.topupBalanceAfter(''),
                      style: textTheme.bodySmall,
                    ),
                  ),
                  MoneyText(balanceAfter, style: textTheme.titleLarge),
                ],
              ),
            ),
          ],

          const SizedBox(height: ClaySpace.xl),
          ClayButton(
            label: l10n.actionTopUp,
            icon: Icons.lock_outline_rounded,
            variant: ClayButtonVariant.primary,
            expand: true,
            loading: widget.isBusy,
            // Disabled until the amount is valid, so the Rs. 100 rule is felt as
            // "not yet" rather than as a rejection after the fact.
            onPressed:
                (amount != null && widget.errorKey == null && !widget.isBusy)
                ? widget.onSubmit
                : null,
          ),
          const SizedBox(height: ClaySpace.md),
          Text(
            l10n.topupNeverCreditedLocally,
            style: textTheme.labelSmall,
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}
