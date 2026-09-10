# VEHDiag Design System — Typography

- Primary: **Inter** (fallback: ui-sans-serif, system-ui, Segoe UI, Roboto, Arial). Weights 400/500/600/700/800.
- Monospace (DTC codes, VINs, terminal, values): **JetBrains Mono** (fallback: ui-monospace, SFMono-Regular, Consolas, monospace).

## Scale (1.25 minor third, clamp for responsiveness)
| Token | Size | Use |
|---|---|---|
| --veh-text-xs | 0.75rem | badges, meta |
| --veh-text-sm | 0.875rem | secondary text |
| --veh-text-base | 1rem | body |
| --veh-text-lg | 1.125rem | lead |
| --veh-text-xl | 1.25rem | h4 |
| --veh-text-2xl | 1.5rem | h3 |
| --veh-text-3xl | 1.875rem | h2 |
| --veh-text-4xl | clamp(2.25rem,5vw,3.5rem) | h1 |
| --veh-text-hero | clamp(2.5rem,6vw,4rem) | hero h1 |

- Line-height: 1.6 body, 1.15 headings. Letter-spacing: -0.02em headings, +0.06em uppercase kickers.
- Numeric/monospace for VINs, DTCs, live values: `font-family: var(--veh-mono)`.
