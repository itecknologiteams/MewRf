/// The design system. Import this, not the individual files.
///
/// Everything visual in the app composes from these primitives. Three rules the
/// whole system rests on:
///
///   1. **Three materials, each doing its own job.** Glass for content surfaces (~70%),
///      neumorphism ONLY on interactive controls and used sparingly, clay only for
///      illustrations and empty states. Mixing them everywhere is how an app ends up
///      looking like a texture sampler; each one is picked for what it is good at.
///   2. **Colour never carries meaning alone.** Every status colour is paired with a
///      label or an icon — some users cannot read hue at all.
///   3. **Motion explains what changed.** Nothing animates for its own sake, nothing on a
///      routine path runs past ~300ms, and everything collapses to zero under
///      reduce-motion via `clayDuration`.
library;

export 'clay/clay_ambient.dart';
export 'clay/clay_badge.dart';
export 'clay/clay_bottom_nav.dart';
export 'clay/clay_button.dart';
export 'clay/clay_card.dart';
export 'clay/clay_motion.dart';
export 'clay/clay_progress_ring.dart';
export 'clay/clay_scaffold.dart';
export 'clay/clay_sheet.dart';
export 'clay/clay_skeleton.dart';
export 'clay/clay_snack.dart';
export 'clay/clay_states.dart';
export 'clay/clay_surface.dart';
export 'clay/clay_text_field.dart';
export 'theme/clay_theme.dart';
export 'tokens/clay_metrics.dart';
export 'tokens/clay_palette.dart';
