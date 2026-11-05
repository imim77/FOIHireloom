# FOIHireloom MCP App views

The charts that Claude, ChatGPT and other MCP Apps hosts show inside the conversation. Each view is a React page
under `src/pages/<name>.html`; application code lives in `src/mvvm/`, grouped by feature and responsibility.

Styling uses Tailwind CSS v4 through the official `@tailwindcss/vite` plugin. Every view imports
`mvvm/utils/mount.tsx`, which loads the single `mvvm/tailwind.css` entry. That entry contains Tailwind's
import, semantic theme tokens, the host's dark-theme overrides, and shared animation keyframes.
Layout, typography, interaction states, and responsive/container rules live in component utility classes;
there are no separate component style sheets. Existing named classes remain as animation and test hooks.
Use complete utility names in source so Tailwind can discover them; the entry explicitly scans all of
`src/`, including shared controls outside Vite's pages directory. Chart coordinates and animation frames
calculated from data remain dynamic styles or SVG attributes. Chart controls use the same shadcn button
primitives as other actions.

Reusable UI comes from the official shadcn/ui Nova registry with Base UI primitives. `components.json`
places the owned source in `src/mvvm/components/ui/`; the `@/` import alias resolves to `src/mvvm/`.
Screens compose those primitives through the shared `Card`, `FilterChips`, and `Sources` adapters.
Buttons, badges, alerts, empty states, loading skeletons, checkboxes, forecast sliders, tables,
collapsible history, and accommodation toggles use shadcn components. Specialized chart geometry,
hover inspection, and animation remain in the existing chart components and hooks.

The Tailwind entry maps shadcn's semantic colors to the existing host-aware tokens, so
`data-theme="dark"` updates both controls and charts. Local badge variants cover success, warning,
and provisional values. Table variants preserve comparison wrapping, sticky headers/columns, and
numeric formatting; the slider forwards accessible labels and value text to its focusable thumb.
Use component variants for appearance and `className` for layout; pass actions from ViewModels.
Add future primitives from the frontend directory with `npx shadcn@latest add @shadcn/<component>`.

Shared job conditions and search filters live in `src/mvvm/utils/jobs.ts`, independent of any view.
`FilterChips` renders removable filters, and `useServerTool` owns request status and ignores replies after
unmount. Job cards keep pagination and comparison selection in `features/JobCards/hooks/use-job-cards.ts` and grid
animation in `use-job-grid-motion.ts`; county comparison keeps its row definitions and value formatting in
`features/CountyComparison/utils/county-rows.ts` (paths relative to `src/mvvm/`).
Stateful content uses the MCP result's `revision` as its React key so a new host result discards local state
and pending replies. Expansion controls stay outside that reset.

The frontend follows Container → ViewModel → View with this physical structure:

```text
src/
├── pages/                                  # Seven HTML entries; preview URLs stay unchanged
└── mvvm/
    ├── features/
    │   └── JobCards/                       # Same ownership rules for all seven features
    │       ├── __integrations__/           # Browser behavior and MCP host tests
    │       ├── components/                 # JobCardView.tsx
    │       ├── screens/JobCards/           # JobCardsApp.tsx, JobCards.tsx, main.tsx
    │       ├── hooks/                      # use-job-cards.ts, use-job-grid-motion.ts
    │       ├── utils/                      # Formatting, preview samples, pure helpers
    │       └── types.ts                    # Tool-result contracts
    ├── components/                         # Card, FilterChips, Sources
    ├── hooks/                              # Host connection, expansion, requests, motion
    ├── utils/                              # Host actions, mounting, formatting, job contracts
    ├── types.ts                            # Shared tool-result contracts
    └── tailwind.css                        # Tailwind entry and semantic theme
```

The other features are `JobComparison`, `CountyComparison`, `JobsByCounty`, `UnemploymentHistory`,
`AccommodationComparison`, and `LabourMarketForecast`. Every feature has an `__integrations__/` suite;
other subfolders exist where there is code to own. Unit tests sit next to their pure utilities.
Shared browser-host support is in `test-support/`, and cross-feature smoke tests remain in `tests/`.

Each screen's `main.tsx` mounts its `<Name>App.tsx` container, which owns the MCP connection and
composes the screen. Interaction sessions are keyed by host revision, while expansion remains in the
outer container. Feature `hooks/` modules own screen state, derived values, capability checks, and actions.
Views receive typed props and callbacks; neither screen markup nor shared `Sources` controls access
the host directly. Static comparison rendering uses the shared expansion hook without an empty
screen ViewModel.

Keep DOM measurement, pointer coordinates, focus, SVG geometry, and animation in presentation
components and motion hooks. Keep MCP requests in adapters and ViewModels, and authoritative
business rules in the Python backend. New screens should follow the project-local
[`mvvm-architecture` skill](../.agents/skills/mvvm-architecture/SKILL.md). No additional state library
or platform-specific view files are required.

```bash
npm install
npm run dev     # http://localhost:5173/jobs-by-county.html with sample data
npm run build   # one self-contained HTML file per view in dist/
```

The MCP server serves the built files from `dist/` as `ui://` resources (`api/apps/views.py`). `dist/` is not
committed, so build before starting the server or running the tests, and again after each change, then restart the
server. The page URI changes with its content, so hosts load the new version.

`dist/sources.json` records a hash of every source; the tests fail and the server warns when a source changed after
the last build.

Chart verification (Node.js 22.6+):

```bash
npm test                      # data adapter, missing values, provisional segments and curve bounds
npm run lint
npm run build
npx playwright install chromium  # once, for browser tests
npm run test:browser           # production page in an MCP Apps iframe; mouse, keyboard, touch and themes
```

Browser tests also cover all seven standalone previews, host capabilities, pagination, filter removal,
comparison messages and retries, source/advertisement link callbacks, request failures, county ranking
selection/expansion, loading skeletons, keyboard-operated selection/toggles, and replacement results
arriving before pending tool replies.

The unemployment chart adapts the supplied `RevenueGrowthChart` to monthly DZS rates. Its stat tiles follow the
inspected month; the annual comparison tiles stay anchored to the server's latest month. Missing values remain
gaps, provisional segments stay dashed, and all 1–6 counties share consistent colours. The tool still returns
12–24 months. To save screenshots while testing, set `CHART_ARTIFACT_DIR` to an output directory.
Optionally set `CHART_LIVE_DATA_FILE` to a saved `show_unemployment_history` structured JSON response to verify its
rates against the rendered nodes as well.

To add a view: create `src/pages/<name>.html` and its feature under `src/mvvm/features/`, wire the HTML
entry to `screens/<ScreenName>/main.tsx`, and add meaningful tests in the feature’s `__integrations__/`.
Add an `AppView` to `VIEWS` in `api/apps/views.py`, and point its tool at it with
`AppConfig(resource_uri=VIEW.uri)`.

The accommodation comparison at `/accommodation-comparison.html` adapts the supplied `PortfolioAllocationChart`.
`show_accommodation_comparison` accepts county, query, category and the other job-condition filters, excluding
the accommodation filter itself, so the population always includes all three statuses. It partitions matching
ads into offered (shared/single/family), explicitly not offered, and unknown. The stored shares use all matching
ads. Legend buttons can temporarily hide groups; the view then names its visible denominator and offers a reset.
Mouse, touch and keyboard selection expose the count and share in the ring's centre. Zero groups stay in the
legend, and the last visible positive group cannot be hidden. The preview uses the real local response for
Varaždinska and query `kuhar` (2/7/1 ads), with its freshness warning.

Build before starting a fresh MCP server. A process already running and a connector with cached tool metadata
need to load the new server version to expose the new tool; this is separate from the local browser preview.
