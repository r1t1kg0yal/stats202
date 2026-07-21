# Composer streaming and dashboard reload handshake

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

The two scripts share one boolean snapshot and one lifecycle event:

- `window.__prismComposerStreaming` provides the synchronous state checked by
  the dashboard when structural drift arrives.
- `prism:composer-streaming-change` wakes the dashboard as soon as the last
  active stream finishes or aborts. Release does not depend on another
  live-refresh poll, which may be delayed or disabled.

## `web/prism_site/js/composer.js`

Add this immediately after the `_streams` declaration:

```javascript
var _streams = {};  // { [tabId]: {abort, tabId, chat} }
window.__prismComposerStreaming = false;

function _publishComposerStreamingState() {
  var count = Object.keys(_streams).length;
  var active = count > 0;

  window.__prismComposerStreaming = active;
  window.dispatchEvent(new CustomEvent(
    'prism:composer-streaming-change',
    {detail: {active: active, count: count}}
  ));
}
```

Call `_publishComposerStreamingState()` immediately after every `_streams`
mutation:

```javascript
// Keep the existing stream record assignment unchanged.
_streams[tabIdForRun] = { /* existing abort, tabId, and chat fields */ };
_publishComposerStreamingState();
```

```javascript
delete _streams[tabId];
_publishComposerStreamingState();
```

```javascript
_streams = {};
_publishComposerStreamingState();
```

Apply those calls at all of the existing mutation paths:

| Path | Required placement |
|---|---|
| `_launchRun` stream creation | Immediately after `_streams[tabIdForRun] = ...` |
| `_finishChat` deletion or reset | After the final response is rendered and its run/history state is persisted |
| `closeTab` last-tab reset abort | Immediately after deleting or resetting the stream entry |
| `closeTab` normal close abort | Immediately after deleting the closed tab's stream entry |
| Chat-back abort | Immediately after deleting the active tab's stream entry |

The `_finishChat` ordering is load-bearing. The transition to `active: false`
must be published only after the completed response and history are safely
stored. The dashboard may synchronously request navigation when it receives
that event.

Multiple tabs require no separate logic. If two streams are active, finishing
one publishes `{active: true, count: 1}` and the dashboard continues waiting.
Finishing the final stream publishes `{active: false, count: 0}` and releases
the pending reload.

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
`window.__prismComposerStreaming` before automatic structural navigation, and
listens for `prism:composer-streaming-change`.

Its structural branch behaves as follows:

```javascript
if (LAST_KNOWN_TEMPLATE_HASH &&
    payload.manifest_template_hash &&
    payload.manifest_template_hash !== LAST_KNOWN_TEMPLATE_HASH){
  if (_composerStreamIsActive()){
    PENDING_STRUCTURAL_RELOAD_HASH = payload.manifest_template_hash;
    console.log(
      '[live] template hash changed; deferring reload until composer finishes'
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
window.addEventListener('prism:composer-streaming-change', function(event){
  if (event.detail && event.detail.active === false){
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
