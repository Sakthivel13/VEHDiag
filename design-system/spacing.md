# VEHDiag Design System — Spacing & Layout

- Base unit: 4px. Scale: 4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 96, 128.
- Container: max-width 1200px, padding-inline clamp(1rem, 4vw, 2rem).
- Section padding: clamp(3rem, 8vw, 6rem) block.
- Card padding: 24px; card gap: 16–24px; radius: 12px cards, 8px inputs, 999px pills.
- Grid: 12-col; feature grids auto-fit minmax(280px, 1fr); dashboard 12-col with 3-col sidebar.
- Elevation: 3 levels — shadow-sm (0 1px 2px rgba(15,23,42,.06)), shadow-md (0 8px 24px rgba(76,29,149,.10)), shadow-lg (0 24px 64px rgba(76,29,149,.16)).
- Focus rings: 2px solid var(--veh-accent) with 2px offset; visible in both modes.
