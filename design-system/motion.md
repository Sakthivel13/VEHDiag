# VEHDiag Design System — Motion

- Durations: 120ms micro, 200ms standard, 400ms emphasis. Ease: cubic-bezier(.2,.8,.2,1).
- Respect `prefers-reduced-motion: reduce` — disable transforms/animations.
- Patterns: hero fade-up (stagger 60ms), card hover lift 2px, gauge needle 400ms ease-out, live chart scroll 1s, progress bars ease-in-out, route fade 150ms.
- No infinite loops except: live-data pulse dot (opacity), skeleton shimmer (paused on reduced motion).
