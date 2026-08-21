/**
 * The ME wordmark.
 *
 * Two pre-rendered PNGs ship instead of one filtered image: the mark is black
 * glyphs + orange road, and a CSS invert would flip the orange too. Swapping by
 * `dark:` class keeps the brand orange constant in both themes and avoids the
 * theme flash a JS-driven `src` would cause on first paint.
 */

const INTRINSIC = { width: 720, height: 305 };

/**
 * `className` lands on the wrapper, not the images. The theme swap already
 * spends `hidden`/`dark:block` on the images, so a responsive `lg:hidden`
 * passed down to them would lose to `dark:block` and leak the mark onto
 * desktop. Sizing and visibility belong one level up.
 */
export function BrandLogo({ className = 'h-8' }: { className?: string }) {
  return (
    <span className={`inline-flex items-center ${className}`}>
      <img {...INTRINSIC} src="/me-logo.png" alt="ME" className="h-full w-auto dark:hidden" />
      <img
        {...INTRINSIC}
        src="/me-logo-light.png"
        alt="ME"
        className="h-full w-auto hidden dark:block"
      />
    </span>
  );
}

/** Wordmark + product name, divided by a hairline. Used in the sidebar. */
export function BrandLockup({ className = '' }: { className?: string }) {
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <BrandLogo className="h-8 shrink-0" />
      <span className="h-8 w-px bg-line shrink-0" aria-hidden="true" />
      <div className="min-w-0">
        <p className="text-[13px] font-bold text-ink leading-tight truncate">
          Smart Expressway
        </p>
        <p className="text-[10px] text-ink-muted uppercase tracking-[0.14em] truncate">
          Toll System
        </p>
      </div>
    </div>
  );
}

export default BrandLogo;
