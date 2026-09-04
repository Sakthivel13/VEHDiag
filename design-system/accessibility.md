# VEHDiag Design System — Accessibility

- WCAG 2.1 AA baseline. Contrast pairs documented in colors.md.
- Semantic landmarks (header/nav/main/footer), one h1 per page, logical heading order.
- All interactive elements keyboard-operable; visible focus rings; skip-to-content link.
- Form inputs: programmatic labels, aria-describedby for hints/errors, role=alert on errors.
- Tables: caption + th scope. Charts: text fallback (aria-label + data list). Toasts: role=status/alert.
- Icons: aria-hidden + adjacent visible text (never icon-only actions without aria-label).
- Dark mode via prefers-color-scheme + manual toggle (no color-only info).
- Target size ≥ 24px visual, ≥ 44px touch where feasible.
