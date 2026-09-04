# VEHDiag Design System — Colors

Purple-centered, engineering-grade palette. Dark-mode aware. WCAG AA-checked pairings noted.

## Brand
| Token | Value | Use |
|---|---|---|
| --veh-primary | #7C3AED | Primary actions, links, active nav |
| --veh-primary-deep | #5B21B6 | Hover/pressed states |
| --veh-primary-ink | #4C1D95 | Text on light violet fills |
| --veh-secondary | #4F46E5 | Secondary/indigo accents, charts |
| --veh-accent | #A78BFA | Electric violet accents, glow, focus rings |
| --veh-gradient | linear-gradient(135deg,#7C3AED,#4F46E5) | Hero, buttons, highlights |

## Neutrals (light)
| Token | Value |
|---|---|
| --veh-bg | #FFFFFF |
| --veh-surface | #F8FAFC |
| --veh-surface-2 | #F1F5F9 |
| --veh-border | #E2E8F0 |
| --veh-text | #0F172A |
| --veh-text-muted | #475569 |

## Dark mode
| Token | Value |
|---|---|
| --veh-bg-dark | #0B0B14 |
| --veh-surface-dark | #12121E |
| --veh-surface-2-dark | #1A1A2E |
| --veh-border-dark | #2A2A44 |
| --veh-text-dark | #F1F5F9 |
| --veh-text-muted-dark | #94A3B8 |

## Status
| Token | Value |
|---|---|
| --veh-success | #16A34A |
| --veh-warning | #D97706 |
| --veh-error | #DC2626 |
| --veh-info | #2563EB |

## Contrast notes
- #7C3AED on white: 5.4:1 — AA for normal text.
- #4C1D95 on white: 8.6:1 — AA/AAA for text.
- --veh-text (#0F172A) on --veh-bg: 17.6:1 — AAA.
- --veh-text-dark on --veh-bg-dark: 15.9:1 — AAA.
- Never use --veh-accent (#A78BFA) for body text on white (2.9:1) — decoration only.
