import 'package:flutter/material.dart';
import 'package:mtag_user_app/core/models/tag.dart';
import 'package:mtag_user_app/core/utils/app_dates.dart';
import 'package:mtag_user_app/core/utils/labels.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/shared/support_actions.dart';
import 'package:mtag_user_app/features/shared/tag_status_badge.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// The tag rendered as a portrait payment card.
///
/// The TID is what a customer reads off this screen and types into the JazzCash app, or
/// reads aloud to a booth operator. Card conventions are borrowed because they solve
/// exactly that problem and everyone already knows how to read them:
///
///   * **Grouped in fours.** A 24-character hex run is a wall; four-character groups give
///     the eye somewhere to rest and let someone say "E280, 1170, …" without losing place.
///   * **Monospaced.** In a proportional face `0`/`O` and `1`/`I` are a coin flip, and this
///     string is being retyped into a payment app where a wrong character means a top-up
///     credited to a stranger's tag.
///   * **ISSUED / EXPIRES beneath**, laid out like VALID FROM / GOOD THRU, because that is
///     where a card holder's eye already goes.
///   * **Portrait, not landscape.** A landscape card would either be too small to read the
///     TID at a glance or need rotating; portrait keeps the number at a comfortable size in
///     a phone-shaped column.
///
/// Glass, per the design spec's "Active Toll Pass" assignment, with the whole surface
/// tap-to-copy.
class TagPassCard extends StatelessWidget {
  const TagPassCard({required this.tag, required this.plateNumber, super.key});

  final Tag tag;
  final String? plateNumber;

  /// `E28011700000021234ABCD` -> `E280 1170 0000 0212 34AB CD`
  ///
  /// Grouping is applied for DISPLAY only; the clipboard and every comparison use the raw
  /// value, because a TID with spaces in it is not a TID.
  static String _grouped(String tid) {
    final buffer = StringBuffer();
    for (var i = 0; i < tid.length; i += 4) {
      if (i > 0) buffer.write('  ');
      buffer.write(tid.substring(i, (i + 4).clamp(0, tid.length)));
    }
    return buffer.toString();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final palette = ClayTheme.of(context).palette;
    final textTheme = Theme.of(context).textTheme;
    final tid = tag.tid ?? '';

    return GestureDetector(
      onTap: () => copyToClipboard(context, value: tid, label: l10n.tagTid),
      child: ClayCard(
        // The pass is the subject of this screen and sits over the ambient glow, so it is
        // one of the few surfaces that earns a real backdrop blur.
        blur: true,
        depth: ClayDepth.hero,
        radius: ClayRadius.hero,
        padding: const EdgeInsets.all(ClaySpace.xl),
        semanticLabel: '${l10n.tagTid} $tid',
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Card head: brand + copy affordance ────────────────────────────
            Row(
              children: [
                Icon(
                  Icons.sensors_rounded,
                  size: 20,
                  color: palette.primary,
                ),
                const SizedBox(width: ClaySpace.sm),
                Expanded(
                  child: Text(
                    l10n.tagPassLabel,
                    style: textTheme.labelSmall?.copyWith(
                      letterSpacing: 1.6,
                      color: palette.textMuted,
                    ),
                  ),
                ),
                // The status badge sits where a card carries its network mark. It replaces
                // the separate Status section this screen used to have: "can this tag open
                // a barrier" is the first thing a worried holder looks for, and it belongs
                // on the pass rather than in a panel below it. Renders the server's
                // `is_valid` rather than recomputing it.
                TagStatusBadge(tag: tag),
              ],
            ),

            const SizedBox(height: ClaySpace.xxl),

            // ── The number ────────────────────────────────────────────────────
            Row(
              children: [
                Text(
                  l10n.tagTid,
                  style: textTheme.labelSmall?.copyWith(letterSpacing: 1.2),
                ),
                const SizedBox(width: ClaySpace.sm),
                Icon(Icons.copy_rounded, size: 14, color: palette.textMuted),
              ],
            ),
            const SizedBox(height: ClaySpace.sm),
            Text(
              _grouped(tid),
              style: textTheme.titleLarge?.copyWith(
                fontFamily: 'Mono',
                letterSpacing: 1.2,
                height: 1.5,
              ),
              // Always LTR. A TID is hex; an RTL layout would reverse its visual order and
              // make it unusable for the Urdu-reading half of this user base.
              textDirection: TextDirection.ltr,
            ),

            const SizedBox(height: ClaySpace.xl),

            // ── ISSUED / EXPIRES, laid out like a card's VALID FROM / THRU ─────
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: _PassField(
                    label: l10n.tagIssued,
                    value: AppDates.date(
                      tag.issuedAt,
                      locale: localeTag(context),
                    ),
                  ),
                ),
                Expanded(
                  child: _PassField(
                    label: l10n.tagExpiry,
                    value: AppDates.date(
                      tag.expiryDate,
                      locale: localeTag(context),
                    ),
                    // Expiry decides whether the barrier opens, so it carries the warning
                    // when it is close or past. `isExpiringSoon` is the model's own
                    // 30-day window, kept there so this and the tag list agree.
                    tone: (tag.daysUntilExpiry ?? 1) < 0
                        ? palette.danger
                        : tag.isExpiringSoon
                        ? palette.warning
                        : null,
                  ),
                ),
              ],
            ),

            const SizedBox(height: ClaySpace.lg),

            // Serial and last scan — the card's small print. Kept because the serial is
            // what a booth operator asks for and the last scan is how a holder confirms
            // their tag is actually being read at the gantries.
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: _PassField(
                    label: l10n.tagSerial,
                    value: tag.tagSerial,
                    monospace: true,
                  ),
                ),
                Expanded(
                  child: _PassField(
                    label: l10n.tagLastScanned,
                    value: tag.lastScannedAt == null
                        ? l10n.tagNeverScanned
                        : AppDates.relative(
                            tag.lastScannedAt,
                            locale: localeTag(context),
                          ),
                  ),
                ),
              ],
            ),

            if (plateNumber != null) ...[
              const SizedBox(height: ClaySpace.lg),
              _PassField(label: l10n.tagLinkedVehicle, value: plateNumber!),
            ],

            // The expiry warning, when the 30-day window is open or already past. On the
            // pass rather than elsewhere, next to the date it is talking about.
            if (tag.isExpiringSoon) ...[
              const SizedBox(height: ClaySpace.lg),
              Align(
                alignment: AlignmentDirectional.centerStart,
                child: TagExpiryWarning(tag: tag, dense: false),
              ),
            ],

            const SizedBox(height: ClaySpace.lg),
            Text(l10n.tagTidExplainer, style: textTheme.bodySmall),
          ],
        ),
      ),
    );
  }
}

/// One label/value pair on the pass, styled like the embossed fields on a card.
class _PassField extends StatelessWidget {
  const _PassField({
    required this.label,
    required this.value,
    this.tone,
    this.monospace = false,
  });

  final String label;
  final String value;
  final Color? tone;

  /// For identifiers a human retypes or reads aloud — see the Mono family note in pubspec.
  final bool monospace;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label.toUpperCase(),
          style: textTheme.labelSmall?.copyWith(letterSpacing: 1.2),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        const SizedBox(height: 2),
        Text(
          value,
          style: textTheme.titleMedium?.copyWith(
            color: tone,
            fontFamily: monospace ? 'Mono' : null,
          ),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          textDirection: monospace ? TextDirection.ltr : null,
        ),
      ],
    );
  }
}
