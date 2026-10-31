# FOIHireloom MCP App views

The charts that Claude, ChatGPT and other MCP Apps hosts show inside the conversation. Each view is a React page
under `src/views/<name>.html`; `src/shared/` holds the card, theme, formatting, animations and the host connection
(`useMcpApp`).

```bash
npm install
npm run dev     # http://localhost:5173/jobs-by-county.html with sample data
npm run build   # one self-contained HTML file per view in ../src/FOIHireloom/api/apps/views/
```

The MCP server serves the built files as `ui://` resources (`api/apps/views.py`), so commit them after each build
and restart the server. The page URI changes with its content, so hosts load the new version.

To add a view: create `src/views/<name>.html` and `src/views/<name>/`, add an `AppView` to `VIEWS` in
`api/apps/views.py`, and point its tool at it with `AppConfig(resource_uri=VIEW.uri)`.
