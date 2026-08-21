/// The spacing, radius and depth scales. Three fixed ladders, no ad-hoc values.
///
/// Depth and radius move together: a puffier shape needs a rounder corner or it
/// reads as a bevelled box rather than pressed clay. The pairs below are the
/// combinations that hold up — a hero card at depth 10 wants radius 36, a chip
/// at depth 4 wants 22.
library;

import 'package:flutter/animation.dart';

abstract final class ClaySpace {
  static const double xs = 4;
  static const double sm = 8;
  static const double md = 12;
  static const double lg = 16;
  static const double xl = 24;
  static const double xxl = 32;

  /// Left/right page margin.
  static const double gutter = 20;

  /// Inside a card.
  static const double cardPadding = 20;

  /// Between two stacked cards.
  static const double cardGap = 16;
}

abstract final class ClayElevation {
  /// Shadow offset in logical pixels; blur is 3x it. The BORDER defines every edge, so
  /// these only decide how far off the page a surface floats.
  ///
  /// Small on purpose. `0 1px 3px rgba(16,24,40,0.08)` for a standard card is the whole
  /// effect — anything heavier and the border stops being the thing you see.

  /// A modal sheet or a menu, floating clearly above everything.
  static const double sheet = 8;

  /// The hero balance card.
  static const double hero = 2;

  /// A standard card.
  static const double card = 1;

  /// Buttons, chips, list tiles — flat against the page, defined by their border.
  static const double control = 0;

  /// Content nested inside an already-raised surface. Never casts.
  static const double nested = 0;
}

/// Retained under the old name so existing call sites keep compiling.
///
/// The values are elevations now, not depths — see [ClayElevation].
typedef ClayDepth = ClayElevation;

abstract final class ClayRadius {
  /// Tighter than the old clay scale. With a visible border, a large radius eats the
  /// straight edge that makes a card read as a panel — and the border is now the thing
  /// doing the reading.
  static const double hero = 20;
  static const double card = 16;
  static const double control = 12;

  /// Fully rounded, for chips and status pills. Not `double.infinity`: RRect maths needs a
  /// real number, and 999 is past any height this app renders.
  static const double pill = 999;
}

/// Motion.
///
/// Every duration here is short. This is a utility app someone opens at a barrier with a
/// queue behind them, so animation exists to explain what changed — not to be admired.
/// Anything past ~300ms on a routine transition starts costing the user time.
abstract final class ClayMotion {
  /// A control responding to a finger. Short enough to feel like the surface reacted
  /// rather than animated after the fact.
  static const Duration press = Duration(milliseconds: 110);

  /// Content arriving: a card fading and lifting into place.
  static const Duration enter = Duration(milliseconds: 320);

  /// Between one screen and the next.
  static const Duration page = Duration(milliseconds: 260);

  /// The gap between consecutive items in a staggered list.
  ///
  /// 45ms x 8 items is under 400ms for the whole list, which stays a flourish. A larger
  /// step turns a scroll into a wait.
  static const Duration stagger = Duration(milliseconds: 45);

  /// A balance counting up to its new value.
  static const Duration count = Duration(milliseconds: 650);

  static const Duration shimmer = Duration(milliseconds: 1400);
  static const Duration themeSwap = Duration(milliseconds: 250);

  /// The standard easing: fast out, settle in. Matches how physical things stop.
  static const Curve ease = Curves.easeOutCubic;

  /// For something entering with a little life — the splash mark, a confirmed top-up.
  static const Curve emphasis = Curves.easeOutBack;
}

/// Backdrop blur strengths, in sigma.
///
/// Only a handful of surfaces run a real blur — see `ClaySurface.blur` for why. These are
/// the sigmas for the ones that do.
abstract final class ClayBlur {
  /// A standard glass panel over the ambient glow.
  static const double pane = 18;

  /// A modal sheet, which must obscure the screen behind it rather than tint it.
  static const double sheet = 32;
}
