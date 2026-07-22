# Composer streaming and dashboard reload handshake

> CURRENT STATUS (verified 2026-07-21): this neutral handshake is the
> canonical candidate, not the installed live pair. Live `composer.js`
> publishes `window.__prismComposerStreaming` /
> `prism:composer-streaming-change`, and installed `rendering.py` listens
> to those same names; the live halves are internally consistent.
> Canonical `projects/echarts/echarts-payload/rendering.py` uses the
> neutral names below and differs from installed bytes
> (`b4d5e4c2…` candidate vs `913ce12d…` installed). Land this as a paired
> parent `composer.js` edit plus byte-identical payload promotion; do not
> treat the current live old pair as a mixed runtime defect.

## Purpose

Prevent the dashboard's automatic structural reload from interrupting an
inline Composer response. Normal in-place live-data updates continue. Manual
user-initiated reloads remain unchanged.

```text
Composer stream count
        │
        ├─ count > 0 ──→ structural hash drift is remembered
        │
        └─ count = 0 ──→ pending structural reload fires exactly once
```

The two scripts share one neutral hold count and one lifecycle event:

- `window.__prismNavigationHoldCount` provides the synchronous state checked
  by the dashboard when structural drift arrives.
- `prism:navigation-hold-change` wakes the dashboard as soon as the last hold
  is released. Release does not depend on another live-refresh poll, which may
  be delayed or disabled.

The bridge is deliberately navigation-generic. `rendering.py` has an enforced
neutrality boundary and must not contain Composer MIME types, routes, component
policy, or even Composer-specific literals. Composer owns the stream-to-hold
mapping; the dashboard engine only understands whether automatic navigation is
temporarily held.

## `web/prism_site/js/composer.js`

Add this immediately after the `_streams` declaration:

```javascript
var _streams = {};  // { [tabId]: {abort, tabId, chat} }
window.__prismNavigationHoldCount = 0;

function _publishNavigationHoldState() {
  var count = Object.keys(_streams).length;

  window.__prismNavigationHoldCount = count;
  window.dispatchEvent(new CustomEvent(
    'prism:navigation-hold-change',
    {detail: {count: count}}
  ));
}
```

Call `_publishNavigationHoldState()` immediately after every `_streams`
mutation:

```javascript
// Keep the existing stream record assignment unchanged.
_streams[tabIdForRun] = { /* existing abort, tabId, and chat fields */ };
_publishNavigationHoldState();
```

```javascript
delete _streams[tabId];
_publishNavigationHoldState();
```

```javascript
_streams = {};
_publishNavigationHoldState();
```

Apply those calls at all of the existing mutation paths:

| Path | Required placement |
|---|---|
| `_launchRun` stream creation | Immediately after `_streams[tabIdForRun] = ...` |
| `_finishChat` deletion or reset | After the final response is rendered and its run/history state is persisted |
| `closeTab` last-tab reset abort | Immediately after deleting or resetting the stream entry |
| `closeTab` normal close abort | Immediately after deleting the closed tab's stream entry |
| Chat-back abort | Immediately after deleting the active tab's stream entry |

The `_finishChat` ordering is load-bearing. The transition to `count: 0` must
be published only after the completed response and history are safely stored.
The dashboard may synchronously request navigation when it receives that
event.

Multiple tabs require no separate logic. If two streams are active, finishing
one publishes `{count: 1}` and the dashboard continues waiting. Finishing the
final stream publishes `{count: 0}` and releases the pending reload.

## `prism-core/dashboards/rendering.py`

The canonical source is:

```text
projects/echarts/echarts-payload/rendering.py
```

Promote that file byte-identically to:

```text
prism-core/dashboards/rendering.py
```

The canonical file now keeps `PENDING_STRUCTURAL_RELOAD_HASH`, checks
`window.__prismNavigationHoldCount` before automatic structural navigation,
and listens for `prism:navigation-hold-change`.

Its structural branch behaves as follows:

```javascript
if (LAST_KNOWN_TEMPLATE_HASH &&
    payload.manifest_template_hash &&
    payload.manifest_template_hash !== LAST_KNOWN_TEMPLATE_HASH){
  if (_navigationHoldIsActive()){
    PENDING_STRUCTURAL_RELOAD_HASH = payload.manifest_template_hash;
    console.log(
      '[live] template hash changed; deferring reload while navigation is held'
    );
    return;
  }
  console.log('[live] template hash changed; reloading for new structure');
  location.reload();
  return;
}
```

When Composer publishes its final inactive transition, the listener clears the
pending hash before calling `location.reload()`, ensuring one navigation:

```javascript
window.addEventListener('prism:navigation-hold-change', function(event){
  if (event.detail && event.detail.count === 0){
    _flushPendingStructuralReload();
  }
});
```

## Required verification

```text
┌─────────────────────────────┬──────────────────────────────────────┐
│ Scenario                    │ Expected result                      │
├─────────────────────────────┼──────────────────────────────────────┤
│ No stream + structural drift│ Immediate automatic reload           │
│ One stream + drift          │ No reload until that stream finishes │
│ Two streams + drift         │ No reload until both finish          │
│ Stream abort/error/tab close│ Release when active count reaches 0   │
│ Same hash while streaming   │ Normal in-place data update           │
│ Manual Reload button        │ Existing user-initiated reload        │
└─────────────────────────────┴──────────────────────────────────────┘
```

Do not make release depend on the next `pollLiveData()` invocation. Polling can
be disabled with `live_refresh_seconds = 0`, and otherwise introduces an
unnecessary delay after Composer has completed.
