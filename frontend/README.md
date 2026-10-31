# FOIHireloom MCP App views

The charts that Claude, ChatGPT and other MCP Apps hosts show inside the conversation. Each view is a React page
under `src/views/<name>.html`; `src/shared/` holds the card, theme, formatting, animations and the host connection
(`useMcpApp`).

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

To add a view: create `src/views/<name>.html` and `src/views/<name>/`, add an `AppView` to `VIEWS` in
`api/apps/views.py`, and point its tool at it with `AppConfig(resource_uri=VIEW.uri)`.
