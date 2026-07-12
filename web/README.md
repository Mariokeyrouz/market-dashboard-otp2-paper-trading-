# Macro Signal Dashboard — product front-end

The subscription-product MVP: a customizable macro dashboard (Next.js + TypeScript +
Tailwind) built from the validated warm-cream design system. The Streamlit app at the
repo root remains the internal/research tool; this is the customer-facing product.

## Features (phase 1)

- **Element system** — every visualization is a registered element
  ([`src/lib/elements/registry.ts`](src/lib/elements/registry.ts)), the single source of
  truth for the grid, the default layout, and the Logic explainer.
- **Z-pattern default layout** — regime (top-left) → classification (top-right) → the
  Hinge decomposition (diagonal) → tripwires (bottom stroke) → calendar (exit), with
  supporting evidence below.
- **Customization** — Customize mode: drag to rearrange, resize from the corner, hide
  via ×, re-add from the Element Library, Reset restores the default. Layout + region
  persist in `localStorage` (`mws_state_v1`); moves to account storage in the auth phase.
- **Logic panel** — floating side tab opens a drawer explaining the Z reading order and
  each element's rationale, generated from the registry in the user's *current* order.
- **Region lens** — US / EU / CN / JP / Global re-derives every element.
- **Mock data** — all values are placeholders ([`src/lib/data/mock.ts`](src/lib/data/mock.ts)).
  Real feeds (phase 2) replace that module; `derive.ts` and all components stay unchanged.

## Develop

```bash
npm install
npm run dev    # http://localhost:3000
npm test       # vitest unit tests on the derive selectors
npm run lint
npm run build  # production build (typecheck + compile)
```

## Deploy (Vercel)

1. Sign up at vercel.com with the GitHub account that owns this repo.
2. "Add New → Project" → import the repo.
3. Set **Root Directory** to `web/` (Framework Preset: Next.js — auto-detected).
4. Deploy. Every push to `main` redeploys automatically.

## Roadmap

- **Phase 2** — real data via Next API routes (FRED / market data, server-side cache).
- **Phase 3** — auth (Supabase or Clerk) + server-saved layouts.
- **Phase 4** — Stripe subscriptions + plan gating.
- **Phase 5** — marketing landing page, onboarding, custom domain.
