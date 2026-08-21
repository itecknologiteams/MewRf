import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mtag_user_app/core/models/enums.dart';
import 'package:mtag_user_app/core/models/tag.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/tags/presentation/widgets/tag_pass_card.dart';

import '../helpers/golden_harness.dart';

/// Goldens for every ClaySurface variant, in both themes.
///
/// These exist because clay regressions are invisible in code review and obvious
/// on screen. A wrong shadow offset, a lost inset painter, a highlight that went
/// opaque — none of that shows up in a diff, and none of it breaks a widget test
/// that only asserts a string is present. The image is the assertion.
void main() {
  setUpAll(loadClayFonts);

  group('ClaySurface', () {
    goldenTestBothThemes(
      'depth styles',
      fileName: 'clay_surface_styles',
      builder: (context) => _Grid(
        children: [
          for (final (label, style) in const [
            ('raised', ClayDepthStyle.raised),
            ('pressed', ClayDepthStyle.pressed),
            ('flat', ClayDepthStyle.flat),
          ])
            _Labelled(
              label: label,
              child: ClaySurface(
                style: style,
                width: 120,
                height: 84,
              ),
            ),
        ],
      ),
    );

    goldenTestBothThemes(
      'depth ladder',
      fileName: 'clay_surface_depth_ladder',
      builder: (context) => _Grid(
        children: [
          for (final (label, depth, radius) in const [
            ('hero 10/36', ClayDepth.hero, ClayRadius.hero),
            ('card 6/28', ClayDepth.card, ClayRadius.card),
            ('control 4/22', ClayDepth.control, ClayRadius.control),
            ('nested 2/22', ClayDepth.nested, ClayRadius.control),
          ])
            _Labelled(
              label: label,
              child: ClaySurface(
                depth: depth,
                radius: radius,
                width: 130,
                height: 90,
              ),
            ),
        ],
      ),
    );

    goldenTestBothThemes(
      'pressed depth ladder',
      fileName: 'clay_surface_pressed_ladder',
      builder: (context) => _Grid(
        children: [
          for (final (label, depth, radius) in const [
            ('hero', ClayDepth.hero, ClayRadius.hero),
            ('card', ClayDepth.card, ClayRadius.card),
            ('control', ClayDepth.control, ClayRadius.control),
            ('pill', ClayDepth.control, ClayRadius.pill),
          ])
            _Labelled(
              label: label,
              child: ClaySurface(
                style: ClayDepthStyle.pressed,
                depth: depth,
                radius: radius,
                width: 130,
                height: 90,
              ),
            ),
        ],
      ),
    );
  });

  group('primitives', () {
    goldenTestBothThemes(
      'buttons',
      fileName: 'clay_buttons',
      builder: (context) => _Column(
        children: [
          ClayButton(
            label: 'Top Up',
            variant: ClayButtonVariant.primary,
            onPressed: () {},
            icon: Icons.add_rounded,
          ),
          ClayButton(label: 'View all', onPressed: () {}),
          ClayButton(
            label: 'Not now',
            variant: ClayButtonVariant.ghost,
            onPressed: () {},
          ),
          ClayButton(
            label: 'Log out',
            variant: ClayButtonVariant.danger,
            onPressed: () {},
          ),
          const ClayButton(label: 'Disabled', onPressed: null),
          ClayButton(label: 'Working', onPressed: () {}, loading: true),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              ClayIconButton(
                icon: Icons.copy_rounded,
                semanticLabel: 'Copy',
                onPressed: () {},
              ),
              const SizedBox(width: ClaySpace.lg),
              ClayIconButton(
                icon: Icons.refresh_rounded,
                semanticLabel: 'Refresh',
                onPressed: () {},
              ),
            ],
          ),
        ],
      ),
    );

    goldenTestBothThemes(
      'text field',
      fileName: 'clay_text_field',
      builder: (context) => _Column(
        children: [
          ClayTextField(
            controller: TextEditingController(text: '0300 123 4567'),
            label: 'Phone number',
            prefixIcon: Icons.phone_rounded,
          ),
          ClayTextField(
            controller: TextEditingController(),
            label: 'Password',
            hint: 'Enter your password',
            obscureText: true,
            prefixIcon: Icons.lock_outline_rounded,
          ),
          ClayTextField(
            controller: TextEditingController(text: '50'),
            label: 'Amount',
            errorText: 'Minimum top-up amount is Rs. 100',
            prefixIcon: Icons.payments_outlined,
          ),
        ],
      ),
    );

    goldenTestBothThemes(
      'pills and chips',
      fileName: 'clay_pills',
      builder: (context) => _Column(
        children: [
          const Wrap(
            spacing: ClaySpace.sm,
            runSpacing: ClaySpace.sm,
            alignment: WrapAlignment.center,
            children: [
              ClayPill(
                label: 'Active',
                tone: ClayTone.success,
                icon: Icons.check_circle_outline_rounded,
              ),
              ClayPill(
                label: 'Expired',
                tone: ClayTone.danger,
                icon: Icons.event_busy_rounded,
              ),
              ClayPill(
                label: 'Suspended',
                tone: ClayTone.warning,
                icon: Icons.pause_circle_outline_rounded,
              ),
              ClayPill(
                label: 'No tag fitted',
                icon: Icons.help_outline_rounded,
              ),
              ClayPill(
                label: 'Car / Jeep / Taxi',
                tone: ClayTone.primary,
                icon: Icons.directions_car_rounded,
              ),
            ],
          ),
          Wrap(
            spacing: ClaySpace.sm,
            alignment: WrapAlignment.center,
            children: [
              ClayFilterChip(label: 'All', selected: true, onTap: () {}),
              ClayFilterChip(label: 'Tolls', selected: false, onTap: () {}),
              ClayFilterChip(label: 'Top-ups', selected: false, onTap: () {}),
            ],
          ),
        ],
      ),
    );

    goldenTestBothThemes(
      'skeletons',
      fileName: 'clay_skeletons',
      builder: (context) => const _Column(
        children: [
          ClaySkeletonCard(),
          ClaySkeletonCard(lines: 2),
        ],
      ),
      // The shimmer is a running animation; pumped deterministically by the
      // harness, but reduce-motion makes the block static and the golden stable.
      reduceMotion: true,
    );

    goldenTestBothThemes(
      'progress ring',
      fileName: 'clay_progress_ring',
      builder: (context) => _Grid(
        children: [
          for (final v in const [0.0, 0.35, 0.75, 1.0])
            _Labelled(
              label: '${(v * 100).round()}%',
              child: ClayProgressRing(value: v, size: 76),
            ),
        ],
      ),
    );

    goldenTestBothThemes(
      'states',
      fileName: 'clay_states',
      builder: (context) => _Column(
        children: [
          const ClayStaleRibbon(message: 'Showing saved data from 14:32'),
          const ClayBanner(
            icon: Icons.warning_amber_rounded,
            title: 'KDE1836 cannot enter',
            message: 'Balance is Rs. 42 — the barrier needs Rs. 50 minimum.',
            tone: ClayTone.danger,
          ),
          ClayEmptyState(
            icon: Icons.receipt_long_rounded,
            title: 'No transactions yet',
            message: 'Trips and top-ups appear here.',
            actionLabel: 'Top up',
            onAction: () {},
          ),
        ],
      ),
    );

    goldenTestBothThemes(
      'bottom nav',
      fileName: 'clay_bottom_nav',
      builder: (context) => ClayBottomNav(
        currentIndex: 0,
        prominentIndex: 2,
        onTap: (_) {},
        items: const [
          ClayNavItem(
            icon: Icons.home_outlined,
            activeIcon: Icons.home_rounded,
            label: 'Home',
          ),
          ClayNavItem(
            icon: Icons.sensors_outlined,
            activeIcon: Icons.sensors_rounded,
            label: 'Tags',
          ),
          ClayNavItem(
            icon: Icons.location_on_outlined,
            activeIcon: Icons.location_on_rounded,
            label: 'Plazas',
          ),
          ClayNavItem(
            icon: Icons.receipt_long_outlined,
            activeIcon: Icons.receipt_long_rounded,
            label: 'Activity',
          ),
          ClayNavItem(
            icon: Icons.person_outline_rounded,
            activeIcon: Icons.person_rounded,
            label: 'Profile',
          ),
        ],
      ),
    );

    // The tag pass — rendering the REAL TagPassCard, not a hand-built replica.
    //
    // The first version of this golden rebuilt the card's layout inline, which meant it
    // verified the copy rather than the widget: the two drifted apart within one change and
    // the golden happily kept passing. Testing the actual widget is the only version of
    // this test that can catch a regression in it.
    goldenTestBothThemes(
      'tag pass card',
      fileName: 'tag_pass_card',
      builder: (context) => Padding(
        padding: const EdgeInsets.all(ClaySpace.gutter),
        child: TagPassCard(
          tag: Tag(
            id: 1,
            tagSerial: 'MTAG000001',
            tid: 'E28011700000021234AB',
            status: TagStatus.active,
            isValid: true,
            issuedAt: DateTime.utc(2026, 3, 12),
            expiryDate: DateTime.utc(2099, 12, 31),
            // Deliberately MORE than 7 days old.
            //
            // TagPassCard renders this through AppDates.relative, which returns
            // "N days ago" inside a week and an absolute date beyond it. A recent
            // date made this golden depend on DateTime.now() — it passed the day it
            // was written and failed the next, and every day after. Past the 7-day
            // threshold the string is fixed forever.
            //
            // The relative formatting itself is covered by unit tests, which inject
            // `now` rather than reading the clock.
            lastScannedAt: DateTime.utc(2026, 3, 1, 9, 30),
          ),
          plateNumber: 'KHI-1001',
        ),
      ),
    );

    goldenTestBothThemes(
      'card and hero figure',
      fileName: 'clay_card_hero',
      builder: (context) => _Column(
        children: [
          ClayCard(
            depth: ClayDepth.hero,
            radius: ClayRadius.hero,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Total across 3 tags',
                  style: Theme.of(context).textTheme.labelMedium,
                ),
                const SizedBox(height: ClaySpace.sm),
                Text(
                  'Rs. 4,250',
                  style: Theme.of(context).textTheme.displayLarge,
                ),
                const SizedBox(height: ClaySpace.lg),
                ClayButton(
                  label: 'Top Up',
                  variant: ClayButtonVariant.primary,
                  icon: Icons.add_rounded,
                  expand: true,
                  onPressed: () {},
                ),
              ],
            ),
          ),
          ClayCard(
            onTap: () {},
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'KDE1836',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const SizedBox(height: ClaySpace.xs),
                      Text(
                        'Rs. 1,250',
                        style: Theme.of(context).textTheme.displaySmall,
                      ),
                    ],
                  ),
                ),
                const ClayPill(
                  label: 'Active',
                  tone: ClayTone.success,
                  icon: Icons.check_circle_outline_rounded,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  });
}

class _Grid extends StatelessWidget {
  const _Grid({required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) => Center(
    child: Wrap(
      spacing: ClaySpace.xl,
      runSpacing: ClaySpace.xl,
      alignment: WrapAlignment.center,
      children: children,
    ),
  );
}

class _Column extends StatelessWidget {
  const _Column({required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) => Center(
    child: Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final child in children)
          Padding(
            padding: const EdgeInsets.only(bottom: ClaySpace.lg),
            child: child,
          ),
      ],
    ),
  );
}

class _Labelled extends StatelessWidget {
  const _Labelled({required this.label, required this.child});

  final String label;
  final Widget child;

  @override
  Widget build(BuildContext context) => Column(
    mainAxisSize: MainAxisSize.min,
    children: [
      child,
      const SizedBox(height: ClaySpace.sm),
      Text(label, style: Theme.of(context).textTheme.labelSmall),
    ],
  );
}
