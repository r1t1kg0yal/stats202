Investigate a live persisted-dashboard-input failure without changing files yet.

Observed on the “Chief of Staff -- Smoke Test” dashboard:
- All three `user_input` widgets render, but remain READ ONLY.
- Each displays “The server returned invalid JSON.”
- Browser console shows repeated HTTP 404s under `/api/dashboard/...`.
- The Cross-Origin-Opener-Policy warning is likely unrelated; verify rather than treating it as the cause.

Please inspect the live checkout and establish the exact request path and failure point.

1. Inspect the served dashboard HTML/runtime and report:
   - `USER_INPUT_GET_API`
   - `window.PRISM_DASHBOARD_AUTHOR`
   - `window.PRISM_DASHBOARD_ID`
   - the exact GET URL issued by `_uiLoadAll()`

2. For that exact request, report:
   - method and full URL
   - status code
   - `Content-Type`
   - first 300 characters of the response
   - which Django URL pattern/view, if any, resolves it

3. Verify these four routes individually through Django’s resolver:
   - `GET /api/dashboard/user-input/`
   - `POST /api/dashboard/user-input/save/`
   - `POST /api/dashboard/user-input/upload/`
   - `GET /api/dashboard/user-input/download/`

4. Inspect the live implementations and imports in:
   - `prism-core/dashboards/dashboard_user_input.py`
   - `prism-core/dashboards/rendering.py`
   - `web/backend_django/news/dashboard_user_input.py`
   - `web/backend_django/news/urls.py`
   - the dashboard detail view/template code that injects dashboard identity globals

5. Check specifically for:
   - missing Django server-side implementation
   - routes implemented but not registered
   - wrong route prefix or trailing-slash mismatch
   - wrong module imported by `urls.py`
   - stale Django workers after deployment
   - a view returning an HTML 404/redirect instead of the required JSON envelope

Return:
- exact root cause with file-and-line evidence
- request → resolver → view → response trace
- whether the defect is payload code, parent Django integration, or deployment state
- the smallest exact patch required

Do not modify the `prism-core/dashboards/` payload files. If the defect is in parent Django integration, identify that separately.

If part of this prompt cannot be answered, add a brief “Could not resolve” section at the end.