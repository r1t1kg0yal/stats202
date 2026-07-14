# CONTEXT EXTRACTION: Dashboard Unified-Sharing Integration Contract

This is a read-only context-extraction request. Do not edit files, create assets, call mutating endpoints, or implement the uplift.

Inspect the current running checkout directly. Do not infer from prior design documents, timestamps, comments, version constants, or retired functions. Use `list_ai_repo(mode="full")` or equivalent repository inspection in manageable chunks.

Return exact current code with file paths and line ranges. If a named path or symbol moved, locate and report its actual path. If it does not exist, write `NOT FOUND`; do not substitute a nearest match.

## Goal

The canonical staging dashboard compiler currently contains:

- `prism-core/dashboards/rendering.py` equivalent:
  - three-row share menu: `public`, `link`, `private`
  - share HTML around lines 3865–3908
  - share CSS around lines 2081–2117
  - inline three-state share IIFE around lines 13332–13548
  - request body `{dashboard_id, share_mode}` plus optional `reset_token`
  - retired flat response parsing through `res.share_mode`, `res.share_token`, and `res.share_url`
- `prism-core/dashboards/echart_dashboard.py` equivalent:
  - `RESERVED_HEADER_ACTION_IDS` contains `share-btn` and `share-btn-label`
  - it does not yet contain the proposed users/department/workspace submenu IDs

The intended frontend presents:

- `public`, `link`, `users`, `department`, and `private` through `POST /api/dashboard/share/`
- a separate workspace submenu using `GET /api/workspaces/` and `POST /api/workspaces/<id>/add/`
- current-state bootstrap for mode, token, users, and department
- owner and `ENABLE_SHARING_UI` gating

The compiled dashboard must remain self-contained. Do not propose extracting its controller into a required static asset. `cabinet_share.js` may be inspected only as a behavioral reference.

## 1. Verify the live dashboard relic

Inspect the live `dashboards/rendering.py`:

1. Return the complete current `#share-dd` / `#share-menu` HTML block.
2. Return all share-specific CSS.
3. Return the complete share controller from its opening comment through its closing IIFE.
4. State whether it differs materially from the staging description above.
5. Confirm whether it currently reads `window.ENABLE_SHARING_UI`.
6. Confirm every bootstrap global it reads.
7. Confirm the exact request body it currently sends and response fields it currently reads.

Inspect live `dashboards/echart_dashboard.py` and return the complete `RESERVED_HEADER_ACTION_IDS` definition.

## 2. Authoritative dashboard share endpoint

From the current Django URL and view files, return verbatim:

1. The route for `/api/dashboard/share/`.
2. The complete live `share_dashboard_api` function, including decorators, authentication, parsing, helper invocation, exception handling, status codes, and responses.
3. The exact success response schema.
4. Every error response schema and corresponding HTTP status.
5. Every accepted request key, with its required type and whether it is required:
   - `dashboard_id`
   - `share_mode`
   - `users`
   - `department`
   - `workspace`
   - `reset_token`
   - any additional fields
6. Confirm conclusively whether success is:
   - `{ok: true, share: {...}}`
   - a flat `{share_mode, share_token, share_url, ...}`
   - or another shape.
7. Confirm whether a link URL is returned or must be constructed by the client.
8. Confirm whether the live endpoint is `@csrf_exempt` and whether browser calls need anything beyond JSON content type and same-origin credentials.
9. Identify the retired three-mode view, but do not return its full body unless it still participates in routing.

## 3. Canonical `shared_acl` contract

Locate the current `shared_acl` implementation and return verbatim excerpts containing:

1. The valid share-mode enum.
2. `_RESOURCE_SUBFOLDER` or its current equivalent.
3. The complete `share_and_refresh` signature and docstring.
4. Validation and normalization of `mode`, `users`, `department`, `workspace`, and `reset_token`.
5. The code constructing the canonical dashboard share block.
6. The exact complete share-block schema, including all keys and value types.
7. The code that writes the owner registry entry.
8. The code that refreshes viewer reverse indexes.
9. The code governing token minting, preservation, rotation, and invalidation.

Then provide an exact transition matrix for each mode:

- `private`
- `link`
- `users`
- `department`
- `workspace`
- `public`

For every mode state:

- required inputs
- optional inputs
- fields retained
- fields cleared
- whether a token exists
- whether an existing token is reused
- effect of `reset_token`
- viewers receiving reverse-index grants

Resolve these edge cases explicitly:

- Does switching to `private` invalidate links automatically, or must the client send `reset_token=true`?
- Does resubmitting `link` reuse or rotate the token?
- Does `users` replace the complete cohort or append to it?
- Is an empty users list valid?
- Are users deduplicated and normalized?
- Can the owner be included?
- Is department derived server-side when omitted?
- When is the `workspace` share mode actually used?

Do not inspect or expose private user data. Use source code, tests, or sanitized fixtures only.

## 4. Workspace add-by-reference contract

Return the exact routes and complete relevant view bodies for:

- `GET /api/workspaces/`
- `POST /api/workspaces/<workspace_id>/add/`
- `POST /api/workspaces/create/`, if present

For workspace listing, provide:

- accepted query parameters
- exact success and error schemas
- every workspace-row field
- role values
- ordering
- empty-state behavior

For workspace add, provide:

- exact JSON request schema
- exact success and error schemas
- authorization rules by role
- whether a `viewer` can add resources
- idempotence behavior
- already-present behavior
- expected dashboard `name`
- canonical stored resource-reference shape

Resolve this distinction conclusively:

1. Does add-to-workspace mutate the dashboard registry’s `share.mode` to `workspace`?
2. Or does it only add a workspace resource reference and reverse-index grant while leaving the dashboard’s direct share mode unchanged?
3. Is there any current user-facing flow that directly posts `share_mode="workspace"`?
4. If a dashboard can load with `share.mode="workspace"`, how should a menu with no direct workspace-mode row represent that state?

Return the relevant `add_to_workspace` and `list_workspaces` signatures and the code establishing these semantics.

## 5. User search and people-picker reference

Return the exact route and complete view body for `GET /api/users/search/`, including:

- query-parameter names
- minimum query length
- result limit
- authentication
- exact success and error schemas
- every result field
- normalization of kerberos identifiers

Inspect the existing cabinet sharing frontend. Return only the exact code sections needed to reproduce its established behavior:

- user-search debounce and request
- selected-user state
- rendering and removing selected people
- preselection of an existing cohort
- submit/confirmation behavior
- workspace list rendering and add action
- role labels and disabled-role handling
- toast/error presentation
- modal focus, Escape, and click-outside behavior
- related HTML and CSS classes

Name the source files and line ranges. Do not return unrelated cabinet code.

## 6. Dashboard-serving bootstrap globals

Find every current view that serves dashboard HTML, including owner, public/community, shared-link, and observatory variants.

For each view, return the exact code that:

1. Locates the dashboard registry entry.
2. Reads its `share` block.
3. Injects browser globals.
4. Inserts those globals relative to the compiled dashboard HTML.

Return every current injection for:

- `PRISM_VIEWER`
- `PRISM_DASHBOARD_AUTHOR`
- `PRISM_DASHBOARD_ID`
- `PRISM_DASHBOARD_SHARE_MODE`
- `PRISM_DASHBOARD_SHARED`
- `PRISM_DASHBOARD_SHARE_TOKEN`
- `PRISM_DASHBOARD_SHARE_USERS`
- `PRISM_DASHBOARD_SHARE_DEPARTMENT`
- `PRISM_IS_OBSERVATORY`
- `PRISM_TEMPLATE_HASH`
- `ENABLE_SHARING_UI`

For each global, state:

- source field
- exact type
- value when absent
- which serving views inject it
- serialization/escaping mechanism

Confirm whether users and department are already injected. If not, identify the precise insertion points needed in every applicable serving view.

## 7. Feature-flag and owner-gate wiring

Return verbatim:

1. The `enable_sharing_ui` definition in `web/prism_site/run.py`.
2. Its current value.
3. Every place it is threaded through page context.
4. The template line exposing `window.ENABLE_SHARING_UI`.
5. Any CSS or server-side logic additionally hiding the share control.
6. Whether that global is available in the same browser window in which compiled dashboard JavaScript executes.

Describe the complete current visibility predicate:

`feature flag × authenticated viewer × dashboard author × dashboard surface`

Confirm whether non-owner viewers can ever see the dropdown.

## 8. Canonical shared-link URL

Return the current dashboard URL routes and link-validation code.

Resolve:

1. The canonical path and trailing-slash form for a shared dashboard link.
2. The exact token query-parameter name.
3. Whether the client should use `reverse()`, a returned URL, the current pathname, or construct `/users/{author}/dashboards/{id}/?share={token}`.
4. URL encoding requirements for author, dashboard ID, and token.
5. Whether link mode permits unauthenticated access or still requires an authenticated PRISM user.
6. What error is shown for missing, invalid, expired, or invalidated tokens.

## 9. Client state and error behavior

Based strictly on the live endpoint contracts, specify the correct frontend state update after every successful request:

- source of `mode`
- source of `token`
- source of `users`
- source of `department`
- correct link URL
- button label for each state
- active-row behavior

Confirm whether these intended labels are compatible with existing conventions:

- private → `Share`
- public → `Sharing`
- link → `Sharing (link)`
- users → `Shared with N`
- department → `Shared with department`
- workspace, if loadable → exact expected label

Return the established API-error extraction pattern used by existing PRISM frontend clients so the dashboard can surface the server’s `error` message instead of only `HTTP <status>`.

## 10. Tests and operational requirements

List existing tests, with paths and test names, covering:

- all dashboard share modes
- canonical share-block shape
- reverse-index updates
- link-token behavior
- user cohort replacement
- department sharing
- workspace add and idempotence
- role authorization
- dashboard-serving bootstrap globals
- feature-flag gating
- owner visibility

For each relevant test, state what contract it pins. Return short verbatim assertions only where they clarify a schema.

Finally provide the exact restart or reload requirements for changes to:

- `dashboards/rendering.py`
- `dashboards/echart_dashboard.py`
- Django dashboard-serving views
- `web/prism_site/run.py`

## Reply format

Use these sections in this exact order:

1. Runtime files and current share relic
2. Dashboard share API contract
3. Canonical share-block schema and transition matrix
4. Workspace API contract
5. User-search and cabinet-picker reference
6. Dashboard bootstrap globals
7. Feature flag and owner gating
8. Shared-link URL contract
9. Frontend state/error contract
10. Tests and restart requirements
11. Contradictions with the 2026-07-14 design note

For every contradiction, distinguish the inspected live code from the design note and treat live code as authoritative.

Do not provide implementation code or an uplift plan. This response is the final evidence packet for a separate local implementation pass.

If part of this prompt cannot be answered, add a brief '## Could not resolve' section at the end