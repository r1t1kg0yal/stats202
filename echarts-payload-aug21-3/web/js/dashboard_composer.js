/* ==========================================================================
   Prism Composer -- dashboard component-drag boot (owner-only, read-only refs).

   Standalone compiled dashboard.html documents do NOT extend base.html, so the
   Portal Composer mount never reaches them. dashboard_composer.py splices in
   (before </body>): the composer.css link, the #prism-composer-root div, an
   inline flag script (PRISM_COMPOSER_INLINE_CHAT + PRISM_COMPOSER_DND_MODE =
   "dashboard_components"), then composer.js (defer), then THIS boot (defer).

   Mission: let the dashboard OWNER drag one rendered component into the
   Composer as a read-only "dashboard_component" reference. No manifest
   mutation, no layout editing, no screenshots, no HTML/dataset attachments.

   Two-latch startup (no polling):
     composerReady   <- composer.js has executed (window.ComposerManager present)
     dashboardReady  <- document 'prism:dashboard:ready' (or window.DASHBOARD)
   Bind exactly once when both are satisfied.

   composer.js runs in DND_MODE 'dashboard_components': its panel is a drop
   target, upload + generic Portal source scanning are OFF, and ONLY the
   dashboard_component artifact type is accepted. This boot supplies the drag
   SOURCES; composer.js owns the drop side.

   Grab surface: press-and-hold on the whole tile
   ----------------------------------------------
   The drag source is the [data-tile-id] wrapper, not a header strip, and it is
   armed by a press-and-hold rather than being permanently draggable. Three
   consequences, each of them the reason for the design:

     1. WHOLE TILE. Users reach for the component, not for its 28px header. The
        wrapper is the component.
     2. HOLD, NOT STATIC. A permanently draggable wrapper would swallow the
        mousedown that ECharts needs for canvas pan/brush and that tables need
        for text selection, because HTML5 DnD wins over both. Arming only after
        the pointer has been held still for HOLD_MS means an immediate drag
        gesture still reaches the widget, and only a deliberate hold hands the
        tile to Composer. Any movement past MOVE_TOLERANCE_PX before the timer
        fires cancels the arming.
     3. NO HEADER LOOKUP. Because the wrapper carries the drag, the boot no
        longer needs to find `.tile-header` / `.kpi-header` per kind. That
        removes the coverage hole where `note` and semantic `markdown` render
        `.note-head`, and where plain markdown, `divider`, and an untitled
        image render no header at all -- five surfaces that were allowlisted
        but permanently undraggable. All twelve kinds now grip.

   Headers keep their old instant response: a mousedown inside FAST_ARM_SELECTOR
   arms with no delay, so existing muscle memory is unchanged. The hold applies
   only where there is something to conflict with.

   Delegated, so there is nothing to rebind
   ----------------------------------------
   All listeners are document-level and resolve the tile at event time via
   closest('[data-tile-id]'). Tiles that appear or are replaced after boot --
   lazily built tab contents, filter re-renders, in-place refresh data swaps --
   are draggable with no rebind, no MutationObserver, and no per-element state.
   The widget registry is read from window.DASHBOARD at drag time for the same
   reason.
   ========================================================================== */
(function () {
  'use strict';

  // Idempotency: never bind twice (e.g. if this boot is included more than once).
  if (window.__prismComposerComponentDragBooted) return;
  window.__prismComposerComponentDragBooted = true;

  // Every top-level widget kind is eligible.
  var ALLOWED_KINDS = {
    chart: 1, kpi: 1, table: 1, data_grid: 1, pivot: 1, stat_grid: 1,
    tool: 1, user_input: 1, markdown: 1, note: 1, image: 1, divider: 1
  };

  // Interactive descendants that must NOT initiate a component drag (chart
  // controls, sort buttons, info popover, toolbar affordances, links, form
  // fields). A mousedown inside one of these never arms the tile.
  var INTERACTIVE_SELECTOR =
    'button, a, input, select, textarea, [role="button"], .tile-info, ' +
    '.chart-toolbar, .kpi-toolbar, .tile-toolbar, [data-tile-control], ' +
    '.tile-menu, .kpi-menu';

  // Header strips have nothing to conflict with, so they arm instantly and
  // behave exactly as they did before the whole-tile surface existed. This is
  // a responsiveness hint only -- a kind that renders no header still grips
  // through the hold.
  var FAST_ARM_SELECTOR = '.tile-header, .kpi-header, .note-head';

  var HOLD_MS = 200;
  var MOVE_TOLERANCE_PX = 5;

  // DISPLAY label is "<Kind>: <component title>" (e.g. "KPI: US 2Y",
  // "Chart: Treasury benchmark yields"). Built IDENTICALLY here (drag payload)
  // and in the server resolver (composer_artifacts.py) so the optimistic card
  // and the enriched card carry the SAME label -> no flip. dashTitle stays
  // available in content_summary (LLM-facing) server-side.
  var KIND_PREFIX = {
    chart: 'Chart', kpi: 'KPI', table: 'Table',
    data_grid: 'Data Grid', pivot: 'Pivot', stat_grid: 'Stat Grid',
    tool: 'Tool', user_input: 'User Input', markdown: 'Markdown',
    note: 'Note', image: 'Image', divider: 'Divider'
  };

  var _composerReady = false;
  var _dashboardReady = false;
  var _dashboardObj = null;
  var _bound = false;

  // Immutable authority fields, resolved once at bind time from PRISM globals.
  var _ownerPath = '';
  var _dashboardId = '';
  var _templateHash = '';

  // Arming state. _pending is a hold in progress; _armed is the tile currently
  // carrying draggable="true". At most one of each, ever.
  var _pending = null;
  var _armed = null;

  function maybeBind() {
    if (_bound) return;
    if (!_composerReady || !_dashboardReady) return;
    _bound = true;
    bindComponentDrag(_dashboardObj);
  }

  // ---- Latch A: composer.js ready ----
  // Both scripts are `defer` and composer.js precedes this one in document order,
  // so composer.js has already executed and self-initialized by the time this
  // top-level code runs. window.ComposerManager is the readiness signal.
  function checkComposerReady() {
    if (window.ComposerManager && typeof window.ComposerManager.init === 'function') {
      _composerReady = true;
      maybeBind();
      return true;
    }
    return false;
  }

  // ---- Latch B: dashboard ready ----
  // rendering.py dispatches 'prism:dashboard:ready' ONCE with
  // detail.dashboard = window.DASHBOARD. If it already fired before we attached
  // (defer race), window.DASHBOARD is present -- use it directly.
  document.addEventListener('prism:dashboard:ready', function (e) {
    _dashboardObj = (e && e.detail && e.detail.dashboard) || window.DASHBOARD || null;
    _dashboardReady = true;
    maybeBind();
  });
  if (window.DASHBOARD) {
    _dashboardObj = window.DASHBOARD;
    _dashboardReady = true;
  }

  // Resolve composer readiness now (guaranteed under the defer ordering); if for
  // any reason ComposerManager is not yet defined, retry on DOMContentLoaded.
  if (!checkComposerReady()) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', function () {
        checkComposerReady();
      });
    }
    // window 'load' is the final backstop -- both defer scripts have surely run.
    window.addEventListener('load', function () {
      checkComposerReady();
    });
  }
  // In case both latches were already satisfiable synchronously.
  maybeBind();

  // ---- Bind (owner-only, once, delegated) ----
  function bindComponentDrag(dashboard) {
    // Owner gate: only the dashboard owner viewing their OWN dashboard gets a
    // drag surface. Non-owners see the Composer panel and nothing else -- no
    // listeners are attached at all.
    var viewer = window.PRISM_VIEWER || null;
    var owner = window.PRISM_DASHBOARD_OWNER || null;
    if (!viewer || !owner || viewer !== owner) return;

    if (!dashboard) dashboard = window.DASHBOARD || null;
    if (!dashboard) return;
    _dashboardObj = dashboard;

    // Derive the immutable authority fields from PRISM globals (NOT from any
    // client-supplied path). The server re-derives users/{kerberos}/dashboards/
    // {dashboard_id} from the authenticated kerberos and re-validates the hash.
    _dashboardId = window.PRISM_DASHBOARD_ID || '';
    _templateHash = (typeof window.PRISM_TEMPLATE_HASH !== 'undefined' &&
                     window.PRISM_TEMPLATE_HASH !== null)
                    ? window.PRISM_TEMPLATE_HASH : '';
    _ownerPath = 'users/' + owner + '/dashboards/' + _dashboardId;

    document.addEventListener('mousedown', onMouseDown, true);
    document.addEventListener('mousemove', onMouseMove, true);
    document.addEventListener('mouseup', disarm, true);
    // Capture phase: this must write the payload before any bubble-phase
    // listener elsewhere on the page inspects dataTransfer.
    document.addEventListener('dragstart', onDragStart, true);
    document.addEventListener('dragend', disarm, true);
    // A drag that leaves the window, or a tab switch mid-hold, must not leave
    // a tile armed and stealing the next canvas gesture.
    window.addEventListener('blur', disarm);
  }

  // ---- Arming ----

  function widgetFor(tile) {
    var dash = _dashboardObj || window.DASHBOARD || null;
    var widgets = (dash && dash.widgets) || {};
    return widgets[tile.getAttribute('data-tile-id')] || null;
  }

  function onMouseDown(e) {
    if (e.button !== 0) return;
    disarm();

    var origin = e.target;
    if (!origin || origin.nodeType !== 1 || !origin.closest) return;
    // Let the native control handle it; no arming, no drag payload.
    if (origin.closest(INTERACTIVE_SELECTOR)) return;

    var tile = origin.closest('[data-tile-id]');
    if (!tile) return;
    var widget = widgetFor(tile);
    if (!widget || !ALLOWED_KINDS[widget.widget]) return;

    if (origin.closest(FAST_ARM_SELECTOR)) {
      arm(tile);
      return;
    }
    _pending = {
      tile: tile,
      x: e.clientX,
      y: e.clientY,
      timer: window.setTimeout(function () { arm(tile); }, HOLD_MS)
    };
  }

  // Movement before the hold completes means the gesture belongs to the widget
  // -- an ECharts pan or brush, or a text selection in a table.
  function onMouseMove(e) {
    if (!_pending) return;
    if (Math.abs(e.clientX - _pending.x) > MOVE_TOLERANCE_PX ||
        Math.abs(e.clientY - _pending.y) > MOVE_TOLERANCE_PX) {
      cancelPending();
    }
  }

  function arm(tile) {
    cancelPending();
    _armed = tile;
    tile.setAttribute('draggable', 'true');
    // Reuse the EXISTING composer.css rule keyed to this attribute:
    //   [data-composer-draggable="1"]{cursor:grab} :active{cursor:grabbing}
    // so the hand cursor + grabbing state are CSS-driven, not just inline.
    tile.setAttribute('data-composer-draggable', '1');
    // Serve-time class from dashboard_composer.py's injected style block:
    // the armed outline that tells the user the tile is now holdable.
    tile.classList.add('prism-composer-armed');
    // CRITICAL: the tile contains SELECTABLE text (titles, table cells, prose).
    // In HTML5 DnD, mousedown on selectable text starts a TEXT selection
    // instead of the ancestor element drag. Suppressing selection at ARM time
    // -- after the hold, before any movement -- lets the element drag win
    // without having blocked selection during the part of the gesture where
    // the user may still have wanted to select.
    tile.style.userSelect = 'none';
    tile.style.webkitUserSelect = 'none';
    tile.style.MozUserSelect = 'none';
    tile.style.msUserSelect = 'none';
  }

  function cancelPending() {
    if (!_pending) return;
    window.clearTimeout(_pending.timer);
    _pending = null;
  }

  function disarm() {
    cancelPending();
    if (!_armed) return;
    var tile = _armed;
    _armed = null;
    tile.removeAttribute('draggable');
    tile.removeAttribute('data-composer-draggable');
    tile.classList.remove('prism-composer-armed');
    tile.style.userSelect = '';
    tile.style.webkitUserSelect = '';
    tile.style.MozUserSelect = '';
    tile.style.msUserSelect = '';
  }

  // ---- Drag payload ----

  function onDragStart(e) {
    // Only an armed tile is a drag source. Anything else dragging on the page
    // (a native image drag, a text drag) is left completely alone.
    if (!_armed) return;
    var origin = e.target;
    if (!origin || !origin.closest || origin.closest('[data-tile-id]') !== _armed) {
      return;
    }
    var widget = widgetFor(_armed);
    if (!widget) return;
    var kind = widget.widget;
    if (!ALLOWED_KINDS[kind]) return;

    var wid = _armed.getAttribute('data-tile-id');
    var widgetTitle = widget.title || widget.label || wid;
    var payload = {
      type: 'dashboard_component',
      id: wid,
      path: _ownerPath,
      label: (KIND_PREFIX[kind] || 'Component') + ': ' + widgetTitle,
      dashboard_id: _dashboardId,
      widget_kind: kind,
      template_sha256: _templateHash
    };
    try {
      e.dataTransfer.setData('application/x-prism-artifact',
                             JSON.stringify(payload));
      e.dataTransfer.effectAllowed = 'all';
    } catch (_err) {
      // If the browser blocked setData, abort silently -- no partial drag.
    }
  }
})();
