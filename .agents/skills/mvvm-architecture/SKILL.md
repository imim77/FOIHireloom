---
name: mvvm-architecture
description: Apply React MVVM when implementing, refactoring, or reviewing frontend screens in FOIHireloom. Separate presentation from screen behavior using ViewModel hooks and existing MCP adapters.
---

# React MVVM Architecture

Keep screen behavior testable independently of presentation. This is a
project-specific adaptation of the principles in
[Ledger's MVVM skill](https://github.com/LedgerHQ/ledger-live/blob/develop/.agents/skills/mvvm-architecture/SKILL.md),
using FOIHireloom's React, TypeScript, MCP Apps, and Tailwind stack.

## Responsibilities

Use Container → ViewModel → View for screens that coordinate external systems
or substantial interaction state:

- **Model and adapters:** represent tool-result contracts, domain rules, and
  communication with the MCP host. Keep authoritative business rules in the
  Python backend; do not duplicate them in a screen hook.
- **ViewModel:** a React hook owns screen state, derived display data, capability
  checks, and user actions. It coordinates adapters and exposes values and
  handlers through a typed contract.
- **View:** renders that contract and forwards user intent through callbacks.
  It does not call server tools, send host messages, or orchestrate requests.
- **Container:** obtains host context and initial data, invokes the ViewModel,
  and passes its result to the View. Keep this wiring small.

Views may use hooks for presentation concerns such as focus, measurement, or
animation. Keep business decisions and external communication in the ViewModel
or adapters. Static components do not need an empty ViewModel or container.

## Project structure

Use `frontend/src/mvvm/` with these ownership boundaries:

```text
mvvm/
├── features/<FeatureName>/
│   ├── __integrations__/       # Required browser integration tests
│   ├── components/             # Feature presentation components
│   ├── screens/<ScreenName>/   # Container, screen View, and main.tsx
│   ├── hooks/                  # ViewModels and feature motion hooks
│   ├── utils/                  # Pure helpers, unit tests, preview samples
│   └── types.ts                # Feature tool-result contracts
├── components/                 # App-wide UI
├── hooks/                      # Host connection, requests, expansion, motion
├── utils/                      # Host actions, formatting, mounting, job contracts
├── types.ts                    # Shared tool-result contracts
└── tailwind.css                # Shared theme and Tailwind entry
```

- Keep the seven existing feature names: `JobCards`, `JobComparison`,
  `CountyComparison`, `JobsByCounty`, `UnemploymentHistory`,
  `AccommodationComparison`, and `LabourMarketForecast`. Choose ownership by
  responsibility when adding code; create subfolders when they hold code.
- Every feature must have meaningful browser tests in `__integrations__/`.
  Exercise user behavior and host integration, rather than asserting folders.
  Shared browser-host support lives in `frontend/test-support/`; tests spanning
  several features remain in `frontend/tests/`.
- Keep HTML entries in `frontend/src/pages/<view-name>.html`. They reference
  the screen's `main.tsx`, which mounts its `<ScreenName>App.tsx` container.
- Follow existing names: PascalCase components, kebab-case hook files such as
  `use-job-cards.ts`, and local `types.ts` contracts. Name new hooks after their
  screen responsibility; a `ViewModel` suffix is optional.
- Use `features/JobCards/hooks/use-job-cards.ts` as an existing example of
  screen behavior, rather than introducing a parallel state architecture.
- Reuse `mvvm/hooks/use-server-tool.ts` for server-tool requests,
  `mvvm/hooks/use-mcp-app.ts` for connections, `mvvm/hooks/use-expanded.ts` for
  expansion, and `mvvm/utils/mcp.ts` for host actions. Pass
  dependencies through hook arguments or existing composition boundaries so
  behavior can be tested with substitutes.
- Keep `main.tsx` and existing mount helpers as entry points. Extract a separate
  container component only when it clarifies ownership.
- Style views with Tailwind utilities and the shared theme in
  `frontend/src/mvvm/tailwind.css`. Preserve accessible HTML and existing
  responsive behavior.
- Follow existing relative imports. Add no state library, UI framework, path
  aliases, monorepo packages, or platform-specific view variants for MVVM alone.

## Implement and review

Before changing a screen, trace its entry point, tool-result types, state,
handlers, and host calls. Identify which responsibility is currently mixed
with presentation and explain why moving it improves the requested change.
Extract incrementally; do not migrate unrelated screens just to impose a
uniform file structure.

Expose meaningful actions such as `loadMore` or `removeFilter`, rather than
requiring the View to coordinate setters and requests. Prefer derived values
over duplicated state. Keep transport details out of presentation props when
the View only needs display values and callbacks.

Make loading, error, empty, and unavailable-host states explicit. Respect host
capabilities before enabling actions. Ensure asynchronous results cannot update
an unmounted screen or replace newer data with stale data. Preserve useful
existing data on request failure unless the interaction requires clearing it.

Review for these boundary violations:

- A presentation component calls `app.callServerTool` or sends host messages.
- JSX event handlers coordinate requests and business rules directly.
- A ViewModel manipulates DOM layout or returns rendered markup.
- A hook duplicates adapter lifecycle handling or backend business rules.
- A new abstraction only forwards arguments without clarifying a responsibility.

## Verification

For behavior changes, test observable ViewModel outcomes and adapter failures:
state transitions, capability gating, pagination/filter resets, and stale-result
handling as relevant. Verify that Views render their props and invoke callbacks;
use browser coverage when the change affects user interaction or layout.

Use the existing frontend scripts (`npm test`, `npm run lint`, `npm run build`,
and `npm run test:browser`) from `frontend/` as appropriate to the change.
Both commands discover feature-local suites. Do not add empty test
directories or tests that only assert this file structure.
