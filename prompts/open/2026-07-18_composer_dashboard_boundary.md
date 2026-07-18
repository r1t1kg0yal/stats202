---
class: context-extraction
topic: Composer architecture and compiled-dashboard integration boundary
status: OPEN
---

# Extract the Composer and compiled-dashboard boundary

This is read-only source introspection. Do not edit files, propose an
implementation, or build the integration. Resolve the current architecture
verbatim so a separate staging repository can document it and later design a
leaf-node integration.

The intended future ownership boundary is:

- Composer-on-dashboard logic will live in one dedicated PRISM-owned browser
  script.
- The ECharts dashboard compiler may expose narrow UI hooks, but must not absorb
  Composer's state machine, API flow, artifact resolution, or manifest-editing
  orchestration.
- Showing the existing Composer inside a compiled dashboard is separate from a
  visual component builder. Any future structural edit must preserve the typed
  dashboard transaction, concurrency, review, acknowledgment, and publish
  contracts.

Reply in exactly the structure below.

## 1. Composer file inventory

Locate the live Composer implementation and report the exact repository-relative
path, line count, and purpose of every file involved. Explicitly resolve whether
the client assets live under `web/prism_site/{js,css}/`,
`web/backend_django/news/static/`, or another path. Include:

- the client JavaScript;
- the client CSS;
- the Django views;
- the email composition/sending module;
- the artifact resolver;
- URL wiring;
- the `base.html` or other template mount;
- feature-flag definitions and settings.

Quote the exact template lines that mount `#prism-composer-root` and load the
Composer assets.

## 2. Dashboard page and compiled-HTML routes

For every current dashboard listing and detail URL, report:

| URL pattern | View | Response type | Template or S3 source | Extends `base.html`? | Composer present today? |
|---|---|---|---|---|---|

At minimum resolve:

- `/dashboards/`;
- `/dashboards/<dashboard_id>/`;
- `/profile/dashboards/`;
- `/profile/dashboards/<dashboard_id>/`;
- `/users/<kerberos>/dashboards/`;
- `/users/<kerberos>/dashboards/<dashboard_id>/`;
- Community and Observatory detail routes.

Quote the exact view body or decisive excerpts for the canonical user-dashboard
detail route. Resolve the contradiction between these two claims:

1. dashboard detail pages are ordinary Django pages that extend `base.html`; and
2. the detail view returns compiled `dashboard.html` bytes after injecting
   `PRISM_*` globals.

## 3. Composer URL contract

Quote every live `/api/composer/*` URL pattern verbatim, including route name,
view callable, and HTTP methods accepted. For each view, quote:

- its signature;
- decorators;
- authentication and Kerberos resolution;
- request JSON keys;
- response shape and status codes.

Explicitly confirm or correct this expected seven-route inventory:
`fire-off`, `chat`, `history`, `replay`, `preview`, `delete`, and
`artifact-info`.

## 4. Fire-off and inline-chat paths

Trace both data paths from browser call to terminal output.

For fire-off, quote the exact calls that establish:

```text
browser
  -> Composer fire-off view
  -> artifact resolution
  -> SMTP self-send
  -> inbound email pipeline
  -> persisted fire-off record
```

Report the exact subject sentinel, recipient derivation, persistence paths, file
schemas, manifest cap, replay/supersession behavior, and any returned identifiers.

For inline chat, report the exact feature-flag name/default, LLM constructor,
MCP-server wiring, SSE event grammar, persistence behavior, cache/proxy headers,
and abort/disconnect handling. Confirm whether it is currently enabled in the
running configuration.

## 5. Artifact resolver

Quote the signature and complete return schema of the shared Composer artifact
resolver. List every accepted artifact type and, for each type:

| Type | Files/keys read | Inline content | Attachment paths | S3 references | Live URL |
|---|---|---|---|---|---|

Confirm which artifact classes emit references rather than full content, which
are attached, and which are intentionally inlined. Identify every caller of the
resolver and quote the import/call sites.

## 6. Client state and drag-source hooks

From the live Composer JavaScript, quote:

- the `sessionStorage` key and complete persisted state shape;
- the mode/state transitions;
- the delegated click binding guard;
- per-element binding guards;
- optimistic drop and fire-off behavior;
- replay/chat in-flight guards;
- panel drop-target setup;
- `initDragSources()` and every selector or artifact-source family it handles;
- the `MutationObserver` setup and appended drag payload shape.

For dashboard cards and dashboard detail content specifically, identify the exact
DOM nodes, attributes, and initialization path that make them draggable today.

## 7. Security boundary

Quote the client and server code that enforces self-send. Report:

- how `/api/users/me` is used;
- whether client-supplied recipients are ignored;
- how the user's email address is resolved;
- CC normalization and closed-user handling;
- CSRF/auth behavior for each Composer endpoint;
- whether any endpoint permits writing or sending as another user.

## 8. Compiled-dashboard injection seam

Quote the current `dashboard.html` serving/injection function and list every
value or script it injects before returning HTML. Report:

- whether it can safely inject an additional inline script and root element;
- whether Django static asset URLs are reachable from the compiled document;
- CSP, nonce, framing, or response-header constraints;
- whether dashboards are served in an iframe anywhere;
- whether relative `/api/composer/*` and `/api/users/me` calls are same-origin on
  every canonical dashboard route;
- what behavior differs for `file://`, email attachment, presigned S3 URL,
  report-server, Community, and Observatory delivery.

Do not recommend an implementation. Report the narrowest existing hook points
where a future PRISM-owned leaf script could be mounted without moving Composer
logic into the ECharts payload.

## 9. Existing manifest-edit API exposure

Locate the current server/browser exposure, if any, of these dashboard APIs:

- `describe_dashboard`;
- `apply_manifest_operations`;
- `review_dashboard`;
- `acknowledge_dashboard_review`;
- `publish_dashboard`;
- `launch_clean_refresh`.

For each, state whether it is callable only from Python, exposed through a Django
endpoint, or wrapped elsewhere. Quote exact paths and signatures/routes. Confirm
whether any current Composer endpoint can mutate a dashboard manifest. Do not
design a new endpoint.

## 10. Documentation verdict

Return four lists:

1. facts confirmed exactly;
2. prior claims corrected by source;
3. integration seams that exist today;
4. facts that could not be resolved.

If part of this prompt cannot be answered, add a brief `## Could not resolve`
section at the end naming exactly what could not be resolved and why.
