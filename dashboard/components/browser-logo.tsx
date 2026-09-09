// A small, clean "browser window" glyph used as the brand mark.
export function BrowserLogo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden>
      {/* window frame */}
      <rect x="2.5" y="4" width="19" height="16" rx="2.5" stroke="currentColor" strokeWidth="1.7" />
      {/* tab bar */}
      <path d="M2.5 8h19" stroke="currentColor" strokeWidth="1.7" />
      {/* tab */}
      <path d="M6.5 4v4" stroke="currentColor" strokeWidth="1.7" />
      {/* address bar */}
      <rect x="6" y="9.6" width="9" height="2.4" rx="1.2" fill="currentColor" opacity="0.55" />
      {/* content lines */}
      <rect x="6" y="13.6" width="12" height="1.3" rx="0.65" fill="currentColor" opacity="0.35" />
      <rect x="6" y="15.8" width="10" height="1.3" rx="0.65" fill="currentColor" opacity="0.22" />
    </svg>
  )
}
