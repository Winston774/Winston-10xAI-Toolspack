# Project Design System

Base: Noise Winston Design System v2.0.0

## Ownership

- Token source: `public/noise-winston.tokens.css`
- Adopted surface: `public/gomoku.html`
- Theme behavior: follows `prefers-color-scheme`; no preference UI is added
- Product mode: Operate
- Product promise: play a visible, auditable Gomoku match with a WebMCP-capable ChatGPT model

## Component mapping

- Canvas and panels use Noise Winston semantic surface, border, text, and elevation roles.
- The primary Agent action uses the action role; completion and runtime success use result or success roles.
- Buttons keep a minimum 44px interaction target and use the shared focus role.
- Runtime, game-mode, and capability states share one compact StatusBadge contract with semantic status dots.
- Tabs expose `tablist`, `tab`, and `tabpanel` semantics with keyboard navigation.
- The canvas board supports arrow-key selection and Enter/Space placement in addition to pointer and touch input.
- Technical WebMCP details remain available as secondary, auditable disclosure content.

## Exceptions

- The wooden board, grid, black and white stones, threat markers, and variation marks keep product-specific colors because they encode Gomoku material and game state.
- The root React/shadcn component catalog is not used by the current homepage, which redirects to the standalone Gomoku surface. It remains unchanged to avoid a competing unused migration.
- Lucide remains the installed icon family. The standalone page does not load an icon runtime; its former emoji controls use compact text signals instead.

## Validation

```text
npm.cmd run lint
npm.cmd run build
node C:\Users\pooh7\.codex\skills\noise-winston-design-system\scripts\inspect-project.mjs D:\Codex\WebMCP_Gomoku --json
node C:\Users\pooh7\.codex\skills\impeccable\scripts\detect.mjs --json public/gomoku.html public/noise-winston.tokens.css
```

Visual acceptance covers desktop, 390px mobile, light mode, dark mode, keyboard focus, tab navigation, new-game reset, prompt copying, and one valid black move.
