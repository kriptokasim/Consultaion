# Theme Migration Guide — Semantic Design Tokens

> Introduced in **Patchset 106**. This document describes the canonical semantic token system.

## Token Reference

| CSS Variable | Tailwind Class | Light Value | Dark Value | Usage |
|---|---|---|---|---|
| `--color-bg-primary` | `bg-bg-primary` | Near-white | Navy | Page background |
| `--color-bg-secondary` | `bg-secondary` | Light gray | Dark navy | Panels, sidebars |
| `--color-bg-elevated` | `bg-bg-elevated` | White | Dark elevated | Modals, cards |
| `--color-text-primary` | `text-foreground` | Dark blue-gray | White | Primary text |
| `--color-text-secondary` | `text-muted-foreground` | Muted gray | Light gray | Secondary text |
| `--color-accent-primary` | `text-primary` / `bg-primary` | Parliament blue | Blue 60% | CTAs, links, focus |
| `--color-accent-secondary` | `text-accent-secondary` | Amber/gold | Amber 60% | Highlights, badges |
| `--color-border` | `border-border` | Light gray | Dark gray | All borders |
| `--color-focus` | `ring-focus` | Blue | Blue 60% | Focus outlines |
| `--color-success` | `text-success` | Emerald | Emerald | Success state |
| `--color-warning` | `text-warning` | Amber | Amber | Warning state |
| `--color-error` | `text-error` | Red | Red | Error state |

## Approved Patterns

### Border Radius

- **Cards / Panels**: `rounded-2xl` or `rounded-3xl`
- **Pills / Badges**: `rounded-full`
- **Buttons**: `rounded-xl` (default) or `rounded-full` (amber / CTA)
- **Inputs**: `rounded-xl`

### Shadows

- **Cards**: `shadow-smooth` (default), `shadow-smooth-lg` (hover)
- **CTAs / Hero**: `shadow-smooth-lg` (default), `shadow-smooth-xl` (hover)
- **Elevated surfaces**: `shadow-smooth-xl`

### Focus Ring Pattern

All interactive elements must use:

```
focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2
```

### Status Colors (keep explicit)

These are **intentionally not** mapped to generic semantic tokens:

- **Running**: `emerald-*` (green)
- **Error**: `red-*`
- **Connecting**: `amber-*`
- **Reconnecting**: `rose-*`

## Migration Checklist

When migrating a new surface, replace:

| Raw Class | Semantic Replacement |
|---|---|
| `text-stone-900` / `text-slate-900 dark:text-white` | `text-foreground` |
| `text-stone-600` / `text-slate-600 dark:text-slate-300` | `text-muted-foreground` |
| `border-stone-200` / `border-slate-200 dark:border-slate-700` | `border-border` |
| `bg-white` / `bg-white dark:bg-slate-800` | `bg-card` |
| `bg-stone-50` / `bg-slate-50` | `bg-secondary` |
| `text-amber-700` (accent/highlight) | `text-accent-secondary` |
| `bg-amber-600` (CTA) | `bg-primary` |
| `focus-visible:ring-amber-500` | `focus-visible:ring-focus` |

## Guardrail Script

Run `npm run lint:colors` to detect remaining raw color usage in pilot surfaces.
