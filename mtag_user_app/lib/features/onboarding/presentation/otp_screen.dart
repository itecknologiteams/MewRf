import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:mtag_user_app/core/router/app_router.dart';
import 'package:mtag_user_app/core/utils/labels.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/onboarding/presentation/otp_controller.dart';
import 'package:mtag_user_app/features/onboarding/presentation/widgets/otp_boxes.dart';
import 'package:mtag_user_app/features/onboarding/presentation/widgets/verify_burst.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// Step 2: the code.
///
/// There is no submit button — the reference says "it'll auto-verify once entered", and a
/// button whose only job is to confirm the digit you just typed is pure friction.
///
/// The ceremony runs boxes → 2x2 → converge → burst → success, then routes onward. It is
/// driven by ONE controller so the layout, the particles and the colour stay in step; three
/// independent animations would drift apart on a slow frame.
class OtpScreen extends ConsumerStatefulWidget {
  const OtpScreen({super.key});

  @override
  ConsumerState<OtpScreen> createState() => _OtpScreenState();
}

class _OtpScreenState extends ConsumerState<OtpScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ceremony = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1100),
  );

  /// A real keyboard, kept invisible.
  ///
  /// Rather than building a custom keypad: this gets the platform's own numeric keyboard,
  /// SMS autofill, paste, and haptics for free — and a bespoke keypad would be one more
  /// thing to get wrong on an unusual device.
  final _hidden = TextEditingController();
  final _focus = FocusNode();

  bool _celebrated = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _focus.requestFocus());
  }

  @override
  void dispose() {
    _ceremony.dispose();
    _hidden.dispose();
    _focus.dispose();
    super.dispose();
  }

  void _onChanged(String raw) {
    final digits = raw.replaceAll(RegExp(r'\D'), '');
    final controller = ref.read(otpFlowControllerProvider.notifier);
    final current = ref.read(otpFlowControllerProvider).code;

    if (digits.length > current.length && digits.isNotEmpty) {
      controller.pushDigit(digits[digits.length - 1]);
    } else if (digits.length < current.length) {
      controller.popDigit();
    }
    // The hidden field is only a keystroke source; the controller owns the truth.
    _hidden.text = digits;
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final palette = ClayTheme.of(context).palette;
    final flow = ref.watch(otpFlowControllerProvider);

    // Verified: play the burst once, then hand over.
    if (flow.step == OtpStep.password && !_celebrated) {
      _celebrated = true;
      if (clayReduceMotion(context)) {
        _ceremony.value = 1;
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) context.pushReplacement(Routes.setPassword);
        });
      } else {
        final router = GoRouter.of(context);
        // Fire and forget by design: build() cannot await, and the AnimationController
        // drives the rest of the sequence itself.
        unawaited(
          _ceremony.forward().then((_) async {
            // A beat on "Verified Successfully" — the point of the animation is that the
            // user SEES it succeed, and moving on instantly wastes it.
            await Future<void>.delayed(const Duration(milliseconds: 620));
            if (mounted) unawaited(router.pushReplacement(Routes.setPassword));
          }),
        );
      }
    }

    final phase = switch (flow.step) {
      OtpStep.password => OtpPhase.success,
      _ when flow.error != null => OtpPhase.error,
      _ when flow.busy => OtpPhase.verifying,
      _ => OtpPhase.entering,
    };

    return ClayScaffold(
      showBack: flow.step != OtpStep.password,
      body: ListView(
        children: [
          // The invisible input. Zero-sized rather than Offstage: an offstage field cannot
          // hold focus, and focus is the whole point.
          SizedBox(
            height: 0,
            child: Opacity(
              opacity: 0,
              child: TextField(
                controller: _hidden,
                focusNode: _focus,
                keyboardType: TextInputType.number,
                maxLength: OtpFlowState.codeLength,
                enabled: flow.step != OtpStep.password,
                inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                autofillHints: const [AutofillHints.oneTimeCode],
                onChanged: _onChanged,
              ),
            ),
          ),

          const SizedBox(height: ClaySpace.xl),

          // The card from the reference: glass, with a drag handle at the top.
          ClayCard(
            blur: true,
            depth: ClayDepth.hero,
            radius: ClayRadius.hero,
            padding: const EdgeInsets.symmetric(
              horizontal: ClaySpace.xl,
              vertical: ClaySpace.xxl,
            ),
            child: Column(
              children: [
                Container(
                  width: 46,
                  height: 4,
                  decoration: BoxDecoration(
                    color: palette.borderStrong,
                    borderRadius: BorderRadius.circular(ClayRadius.pill),
                  ),
                ),
                const SizedBox(height: ClaySpace.xl),

                // Only the parts that actually change per frame are inside an
                // AnimatedBuilder, and each gets its own.
                //
                // Previously ONE builder wrapped this entire Column, so all of it was rebuilt
                // ~120 times a second for 1.1s: two TextStyle allocations via copyWith, four
                // BoxDecorations, a ClayButton, and — worst of the lot — `l10n.otpResendIn()`
                // and `describeError()`, which run ICU message formatting. None of that
                // changes while the boxes travel, and formatting a plural per frame is pure
                // waste on the exact frames the animation cannot afford to miss.
                _CeremonyHeading(
                  ceremony: _ceremony,
                  idleTitle: l10n.otpTitle,
                  verifiedTitle: l10n.otpVerified,
                  idleBody: switch (flow) {
                    // Console first: on a build with no SMS gateway the code is in the
                    // server log, and telling the user to watch for an SMS is a dead end.
                    _ when flow.delivery == 'console' => l10n.otpBodyConsole,
                    _ when flow.pushedToDevices => l10n.otpBodyPush,
                    _ => l10n.otpBody,
                  },
                  verifiedBody: l10n.otpVerifiedBody,
                ),
                const SizedBox(height: ClaySpace.xxl),

                // Boxes and burst share one Stack so the particles radiate from where
                // the boxes converged, not from an arbitrary centre.
                //
                // RepaintBoundary because this card is GLASS: it sits under a BackdropFilter,
                // and without a boundary every animated frame marks the card's layer dirty,
                // forcing the blur to be recomputed 120 times a second. The boundary lets the
                // blurred backdrop be reused while only this subtree repaints.
                RepaintBoundary(
                  child: SizedBox(
                    height: 150,
                    child: _CeremonyStage(
                      ceremony: _ceremony,
                      code: flow.code,
                      phase: phase,
                      onTapBoxes: _focus.requestFocus,
                    ),
                  ),
                ),

                // Built ONCE per state change rather than per frame. The tree shape below no
                // longer flips on an animation threshold either: swapping subtrees mid-flight
                // destroys and recreates elements, which is a dropped frame at precisely the
                // moment the user is watching for the "verified" beat.
                _CeremonyFooter(
                  ceremony: _ceremony,
                  secureLabel: l10n.otpVerifiedSecure,
                  errorText: flow.error == null
                      ? null
                      : describeError(flow.error!, l10n),
                  notReceivedLabel: l10n.otpNotReceived,
                  resendLabel: flow.resendIn > 0
                      ? l10n.otpResendIn(flow.resendIn)
                      : l10n.otpResend,
                  onResend: flow.resendIn > 0 || flow.busy
                      ? null
                      : () {
                          _hidden.clear();
                          ref
                              .read(otpFlowControllerProvider.notifier)
                              .requestCode();
                        },
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Title and body, cross-fading between "enter the code" and "verified".
///
/// The two texts are built once each and cross-faded, rather than one `Text` whose string
/// and colour are recomputed per frame. Colour is lerped so the change reads as a
/// transition instead of a swap at a threshold.
class _CeremonyHeading extends StatelessWidget {
  const _CeremonyHeading({
    required this.ceremony,
    required this.idleTitle,
    required this.verifiedTitle,
    required this.idleBody,
    required this.verifiedBody,
  });

  final Animation<double> ceremony;
  final String idleTitle;
  final String verifiedTitle;
  final String idleBody;
  final String verifiedBody;

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    final textTheme = Theme.of(context).textTheme;

    // Allocated once, not per frame: `copyWith` builds a whole new TextStyle, and it was
    // being called twice a frame for a colour that only moves between two known values.
    final idleStyle = textTheme.titleLarge?.copyWith(color: palette.textPrimary);
    final doneStyle = textTheme.titleLarge?.copyWith(color: palette.success);

    return AnimatedBuilder(
      animation: ceremony,
      builder: (context, _) {
        // 0 before the hand-over, 1 after. Narrow so the two labels do not both sit at
        // half opacity for long, which would look like a rendering fault.
        final done = ((ceremony.value - 0.68) / 0.14).clamp(0.0, 1.0);

        return Column(
          children: [
            Stack(
              alignment: Alignment.center,
              children: [
                Opacity(
                  opacity: 1 - done,
                  child: Text(
                    idleTitle,
                    style: idleStyle,
                    textAlign: TextAlign.center,
                  ),
                ),
                Opacity(
                  opacity: done,
                  child: Text(
                    verifiedTitle,
                    style: doneStyle,
                    textAlign: TextAlign.center,
                  ),
                ),
              ],
            ),
            const SizedBox(height: ClaySpace.sm),
            // The bodies differ in length, so they are NOT stacked — a Stack would size to
            // the taller and leave a gap under the shorter one.
            Text(
              done > 0.5 ? verifiedBody : idleBody,
              style: textTheme.bodySmall,
              textAlign: TextAlign.center,
            ),
          ],
        );
      },
    );
  }
}

/// Boxes, burst and success tick, all present at all times.
///
/// The tree SHAPE is constant on purpose. The previous version switched
/// `if (verified) tick else boxes` at t = 0.72 and mounted the burst at t = 0.34, which
/// destroyed and created elements mid-animation — a layout and element rebuild on the two
/// frames the eye is most focused on. Now everything is built once and only opacity moves.
class _CeremonyStage extends StatelessWidget {
  const _CeremonyStage({
    required this.ceremony,
    required this.code,
    required this.phase,
    required this.onTapBoxes,
  });

  final Animation<double> ceremony;
  final String code;
  final OtpPhase phase;
  final VoidCallback onTapBoxes;

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;

    return AnimatedBuilder(
      animation: ceremony,
      builder: (context, _) {
        final t = ceremony.value;
        final tickIn = ((t - 0.72) / 0.28).clamp(0.0, 1.0);
        final boxesOut = (1 - tickIn).clamp(0.0, 1.0);

        return Stack(
          alignment: Alignment.center,
          children: [
            // The painter early-returns at progress <= 0, so it costs nothing before the
            // burst starts and does not need mounting on a threshold.
            VerifyBurst(progress: ((t - 0.34) / 0.66).clamp(0.0, 1.0)),

            // Hidden rather than removed. IgnorePointer so the invisible boxes cannot
            // swallow the tap that re-opens the keyboard.
            IgnorePointer(
              ignoring: boxesOut < 0.5,
              child: Opacity(
                opacity: boxesOut,
                child: GestureDetector(
                  onTap: onTapBoxes,
                  child: OtpBoxes(
                    code: code,
                    phase: phase,
                    progress: (t / 0.72).clamp(0.0, 1.0),
                  ),
                ),
              ),
            ),

            IgnorePointer(
              child: Opacity(
                opacity: tickIn,
                child: Container(
                  width: 62,
                  height: 62,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(ClayRadius.control),
                    border: Border.all(color: palette.success),
                  ),
                  child: Icon(
                    Icons.check_rounded,
                    color: palette.success,
                    size: 34,
                  ),
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}

/// The resend row, or the "secured" line once verified.
///
/// Rebuilt only when the STATE changes — a new error, a tick of the resend countdown — not
/// once per animation frame. The countdown label in particular is an ICU plural, and
/// formatting one 120 times a second was the single most expensive thing in the old
/// per-frame builder.
class _CeremonyFooter extends StatelessWidget {
  const _CeremonyFooter({
    required this.ceremony,
    required this.secureLabel,
    required this.errorText,
    required this.notReceivedLabel,
    required this.resendLabel,
    required this.onResend,
  });

  final Animation<double> ceremony;
  final String secureLabel;
  final String? errorText;
  final String notReceivedLabel;
  final String resendLabel;
  final VoidCallback? onResend;

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    final textTheme = Theme.of(context).textTheme;

    final secured = Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Icon(Icons.lock_outline_rounded, size: 15, color: palette.success),
        const SizedBox(width: ClaySpace.xs),
        Text(
          secureLabel,
          style: textTheme.labelSmall?.copyWith(color: palette.success),
        ),
      ],
    );

    final resend = Column(
      children: [
        if (errorText != null) ...[
          const SizedBox(height: ClaySpace.sm),
          Text(
            errorText!,
            style: textTheme.bodySmall?.copyWith(
              color: palette.dangerOnSurface,
            ),
            textAlign: TextAlign.center,
          ),
        ],
        const SizedBox(height: ClaySpace.lg),
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Flexible(
              child: Text(
                notReceivedLabel,
                style: textTheme.bodySmall,
                overflow: TextOverflow.ellipsis,
              ),
            ),
            const SizedBox(width: ClaySpace.sm),
            // Disabled during the cooldown rather than hidden: a control that
            // vanishes reads as broken, one that counts down explains itself.
            ClayButton(
              label: resendLabel,
              variant: ClayButtonVariant.ghost,
              onPressed: onResend,
            ),
          ],
        ),
      ],
    );

    // Only the SELECTOR is animated; both children are already built. The subtree that is
    // on screen therefore never has to be constructed on an animation frame.
    return AnimatedBuilder(
      animation: ceremony,
      builder: (context, _) {
        final done = ceremony.value > 0.75;
        return AnimatedSwitcher(
          duration: clayDuration(context, ClayMotion.enter),
          child: done
              ? Padding(
                  key: const ValueKey('secured'),
                  padding: const EdgeInsets.only(top: ClaySpace.md),
                  child: secured,
                )
              : KeyedSubtree(key: const ValueKey('resend'), child: resend),
        );
      },
    );
  }
}
