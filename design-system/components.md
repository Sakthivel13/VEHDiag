# VEHDiag Design System — Components

- **Buttons**: primary (gradient purple, white text, shadow-md), secondary (surface, border, purple text), ghost (text-only), danger (red). Sizes: sm/md/lg. Radius 8px. Min touch target 44px.
- **Cards**: surface bg, 1px border, radius 12px, shadow-sm → hover shadow-md + 2px translateY.
- **Badges/chips**: pill, mono font for codes; status colors (success/warning/error/info).
- **Forms**: label sm semibold; input 44px, 1px border, focus ring accent; inline validation messages under fields; error state red border.
- **Tables**: header surface-2, row hover surface, mono for codes/VIN; responsive → card list under 720px.
- **Gauges/charts**: purple→indigo gradients, rounded line joins, dark-mode aware; canvas-rendered (no chart libs).
- **Modals/dialogs**: centered, backdrop blur 4px, radius 16px, ESC/backdrop close, focus trap.
- **Toasts**: bottom-right stack, auto-dismiss 4s, status icon + title + body.
- **Empty states**: centered icon (40px, muted), title, guidance, CTA.
- **Loading**: skeleton shimmer (surface-2 → accent 8%), inline spinners for buttons.
- **Terminal**: dark surface, mono, log-style scrollback, status line (used by OBD Terminal + simulator console).
