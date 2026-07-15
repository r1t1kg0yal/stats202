"""dashboard_share -- in-browser share client for compiled dashboards.

Owns the fetch/ACL client that the dashboard Share dropdown uses:
``POST /api/dashboard/share/``, ``GET /api/users/search/``, and the
workspace list/add endpoints. CSS/HTML chrome stays in ``rendering.py``;
Django / ``shared_acl`` remain the server SSOT.

``rendering.DASHBOARD_APP_JS`` injects ``SHARE_CONTROLLER_JS`` via the
``__SHARE_CONTROLLER__`` placeholder so the compiled page stays
self-contained (no external ``dashboard_share.js``).

Destination: ``prism-core/dashboards/dashboard_share.py``.
"""

from __future__ import annotations

from typing import Final, FrozenSet, Tuple


VALID_SHARE_MODES: Final[Tuple[str, ...]] = (
    "private",
    "link",
    "users",
    "department",
    "workspace",
    "public",
)
VALID_SHARE_MODES_SET: Final[FrozenSet[str]] = frozenset(VALID_SHARE_MODES)

SHARE_API_DEFAULT: Final[str] = "/api/dashboard/share/"
USER_SEARCH_API: Final[str] = "/api/users/search/"
WORKSPACES_API: Final[str] = "/api/workspaces/"


def _valid_share_modes_js_object() -> str:
    """JS object-literal body for the client ``validModes`` map.

    Packed onto two lines to match the historical controller layout.
    """
    parts = [f"'{mode}': true" for mode in VALID_SHARE_MODES]
    return f"{', '.join(parts[:3])},\n      {', '.join(parts[3:])}"


_SHARE_CONTROLLER_JS_TEMPLATE = r"""  // ----- share dropdown (unified ACL + workspace add-by-reference) -----
  (function(){
    var ddWrap = document.getElementById('share-dd');
    var btn   = document.getElementById('share-btn');
    var menu  = document.getElementById('share-menu');
    var lbl   = document.getElementById('share-btn-label');
    if (!ddWrap || !btn || !menu) return;

    var viewer = window.PRISM_VIEWER || null;
    var author = window.PRISM_DASHBOARD_AUTHOR || MD.kerberos || null;
    // Only the owner sees the share control. Some dashboard-serving
    // views do not inject the portal-only flag, so only an explicit
    // false disables this self-contained surface.
    if (window.ENABLE_SHARING_UI === false
        || !viewer || !author || viewer !== author) {
      ddWrap.style.display = 'none';
      return;
    }
    ddWrap.style.display = '';

    var validModes = {
      __VALID_SHARE_MODES_JS__
    };
    // Prefer the unified mode global; retain the legacy boolean until
    // every dashboard-serving view reads the nested registry share block.
    var state = window.PRISM_DASHBOARD_SHARE_MODE;
    if (!validModes[state]) {
      state = window.PRISM_DASHBOARD_SHARED ? 'public' : 'private';
    }
    var currentToken = window.PRISM_DASHBOARD_SHARE_TOKEN || null;
    var currentUsers = Array.isArray(window.PRISM_DASHBOARD_SHARE_USERS)
      ? window.PRISM_DASHBOARD_SHARE_USERS.filter(function(v){
          return typeof v === 'string' && v;
        })
      : [];
    var currentDepartment =
      (typeof window.PRISM_DASHBOARD_SHARE_DEPARTMENT === 'string'
       && window.PRISM_DASHBOARD_SHARE_DEPARTMENT)
        ? window.PRISM_DASHBOARD_SHARE_DEPARTMENT : null;

    var SHARE_API = (window.MD && window.MD.share_api_url)
      || MD.share_api_url || '__SHARE_API_DEFAULT__';
    var USER_SEARCH_API = '__USER_SEARCH_API__';
    var WORKSPACES_API = '__WORKSPACES_API__';
    var DASHBOARD_ID = window.PRISM_DASHBOARD_ID || MD.dashboard_id || MANIFEST.id || null;

    var items = {
      'public':  document.getElementById('share-mode-public'),
      'link':    document.getElementById('share-mode-link'),
      'users':   document.getElementById('share-mode-users'),
      'department': document.getElementById('share-mode-department'),
      'private': document.getElementById('share-mode-private')
    };
    var workspaceHost = document.getElementById('share-workspace-host');
    var workspaceBtn = document.getElementById('share-add-workspace');
    var workspaceMenu = document.getElementById('share-workspace-submenu');
    var workspacesLoaded = false;
    var workspacesLoading = false;

    function paint(){
      if (state === 'public') {
        lbl.textContent = 'Sharing';
        btn.classList.add('shared');
      } else if (state === 'link') {
        lbl.textContent = 'Sharing (link)';
        btn.classList.add('shared');
      } else if (state === 'users') {
        lbl.textContent = currentUsers.length
          ? 'Shared with ' + currentUsers.length : 'Shared with people';
        btn.classList.add('shared');
      } else if (state === 'department') {
        lbl.textContent = 'Shared with dept';
        btn.classList.add('shared');
      } else if (state === 'workspace') {
        lbl.textContent = 'Shared with workspace';
        btn.classList.add('shared');
      } else {
        lbl.textContent = 'Share';
        btn.classList.remove('shared');
      }
      Object.keys(items).forEach(function(k){
        if (!items[k]) return;
        if (k === state) items[k].setAttribute('data-active', 'true');
        else items[k].removeAttribute('data-active');
      });
    }
    paint();

    // ----- dropdown open/close (mirrors download-dd pattern verbatim) -----
    function openMenu(){
      menu.hidden = false;
      btn.setAttribute('aria-expanded', 'true');
      ddWrap.setAttribute('data-open', 'true');
    }
    function closeWorkspaceMenu(){
      if (!workspaceMenu || !workspaceBtn) return;
      workspaceMenu.hidden = true;
      workspaceBtn.setAttribute('aria-expanded', 'false');
    }
    function closeMenu(){
      closeWorkspaceMenu();
      menu.hidden = true;
      btn.setAttribute('aria-expanded', 'false');
      ddWrap.removeAttribute('data-open');
    }
    btn.addEventListener('click', function(e){
      e.stopPropagation();
      if (menu.hidden) openMenu(); else closeMenu();
    });
    document.addEventListener('click', function(e){
      if (!ddWrap.contains(e.target)) closeMenu();
    });
    document.addEventListener('keydown', function(e){
      if (e.key === 'Escape') closeMenu();
    });

    // ----- API calls -----
    function fetchJson(url, options){
      options = options || {};
      options.credentials = 'same-origin';
      return fetch(url, options).then(function(r){
        return r.json().catch(function(){ return {}; }).then(function(data){
          if (!r.ok) {
            throw new Error(
              (data && (data.error || data.detail))
              || ('request failed (' + r.status + ')')
            );
          }
          return data;
        });
      });
    }

    function postShareMode(target_mode, opts){
      opts = opts || {};
      if (!DASHBOARD_ID) {
        return Promise.reject(new Error('dashboard id is unavailable'));
      }
      var body = {
        dashboard_id: DASHBOARD_ID,
        share_mode: target_mode
      };
      if (Array.isArray(opts.users)) body.users = opts.users;
      if (typeof opts.department === 'string') body.department = opts.department;
      if (typeof opts.workspace === 'string') body.workspace = opts.workspace;
      if (opts.reset_token) body.reset_token = true;
      return fetchJson(SHARE_API, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(body)
      });
    }

    function applyShareResponse(res, expectedMode){
      if (!res || res.ok !== true || !res.share
          || typeof res.share !== 'object') {
        throw new Error('share API returned an invalid response');
      }
      var share = res.share;
      if (!validModes[share.mode]) {
        throw new Error('share API returned an invalid mode');
      }
      if (expectedMode && share.mode !== expectedMode) {
        throw new Error(
          'share API returned mode ' + share.mode
          + ' after requesting ' + expectedMode
        );
      }
      state = share.mode;
      currentToken = (typeof share.token === 'string' && share.token)
        ? share.token : null;
      currentUsers = Array.isArray(share.users)
        ? share.users.filter(function(v){
            return typeof v === 'string' && v;
          })
        : [];
      currentDepartment =
        (typeof share.department === 'string' && share.department)
          ? share.department : null;
      paint();
      return share;
    }

    function showToast(message, isError){
      var prior = document.getElementById('share-toast');
      if (prior) prior.remove();
      var toast = document.createElement('div');
      toast.id = 'share-toast';
      toast.className = 'share-toast' + (isError ? ' error' : '');
      toast.setAttribute('role', isError ? 'alert' : 'status');
      toast.setAttribute('aria-live', 'polite');
      toast.textContent = message;
      document.body.appendChild(toast);
      requestAnimationFrame(function(){ toast.classList.add('visible'); });
      setTimeout(function(){
        toast.classList.remove('visible');
        setTimeout(function(){ toast.remove(); }, 180);
      }, 2600);
    }

    function modalBody(){
      var back = document.getElementById('ed-modal-backdrop');
      return back ? back.querySelector('.ed-modal-body') : null;
    }

    // ----- link modal -----
    function showLinkModal(fullUrl){
      showModal(
        'Share with link',
        '<p>Anyone with this link can view the dashboard. '
          + 'It is not listed in the Community gallery.</p>'
          + '<div class="share-modal-copy-row">'
          +   '<input class="share-modal-input" type="text" '
          +          'id="share-link-input" readonly />'
          +   '<button class="share-modal-btn primary" type="button" '
          +           'id="share-link-copy">Copy</button>'
          + '</div>'
          + '<div class="share-modal-actions">'
          +   '<button class="share-modal-btn" type="button" '
          +           'id="share-link-close">Done</button>'
          + '</div>'
      );
      var body = modalBody();
      var input = body.querySelector('#share-link-input');
      var copy  = body.querySelector('#share-link-copy');
      var close = body.querySelector('#share-link-close');
      input.value = fullUrl;
      copy.addEventListener('click', function(){
        input.select();
        try { document.execCommand('copy'); copy.textContent = 'Copied!'; }
        catch(e){ copy.textContent = 'Select and copy'; }
        setTimeout(function(){ copy.textContent = 'Copy'; }, 1800);
      });
      close.addEventListener('click', hideModal);
    }

    function showShareConfirm(title, message, confirmLabel, danger, onConfirm){
      showModal(
        title,
        '<p id="share-confirm-message"></p>'
          + '<div class="share-modal-error" id="share-confirm-error"></div>'
          + '<div class="share-modal-actions">'
          +   '<button class="share-modal-btn" type="button" '
          +           'id="share-confirm-cancel">Cancel</button>'
          +   '<button class="share-modal-btn '
          +           (danger ? 'danger' : 'primary')
          +           '" type="button" id="share-confirm-ok"></button>'
          + '</div>'
      );
      var body = modalBody();
      body.querySelector('#share-confirm-message').textContent = message;
      var cancel = body.querySelector('#share-confirm-cancel');
      var confirm = body.querySelector('#share-confirm-ok');
      var err = body.querySelector('#share-confirm-error');
      confirm.textContent = confirmLabel;
      cancel.addEventListener('click', hideModal);
      confirm.addEventListener('click', function(){
        confirm.disabled = true;
        err.textContent = '';
        Promise.resolve(onConfirm()).then(function(){
          hideModal();
        }).catch(function(exc){
          err.textContent = exc.message;
          confirm.disabled = false;
        });
      });
    }

    function confirmStopSharing(){
      showShareConfirm(
        'Stop sharing?',
        'The dashboard becomes private. Any existing share links '
          + 'stop working immediately.',
        'Stop sharing',
        true,
        function(){
          return postShareMode('private').then(function(res){
            applyShareResponse(res, 'private');
            showToast('Dashboard is private');
          });
        }
      );
    }

    function confirmDepartmentSharing(){
      var audience = currentDepartment
        ? currentDepartment : 'your department';
      showShareConfirm(
        'Share with your department?',
        'Everyone in ' + audience + ' will be able to view this dashboard.',
        'Share with department',
        false,
        function(){
          return postShareMode('department').then(function(res){
            applyShareResponse(res, 'department');
            showToast('Shared with '
              + (currentDepartment || 'your department'));
          });
        }
      );
    }

    // ----- people picker -----
    function showUsersModal(){
      showModal(
        'Share with people',
        '<p>Search for colleagues, then choose the complete group '
          + 'that should have access.</p>'
          + '<input class="share-modal-input" type="search" '
          +        'id="share-users-search" autocomplete="off" '
          +        'placeholder="Search by name, kerberos, email, or department" />'
          + '<div class="share-users-selected" '
          +      'id="share-users-selected"></div>'
          + '<div class="share-users-results" id="share-users-results" '
          +      'role="listbox">'
          +   '<div class="share-submenu-status">Type to search for colleagues</div>'
          + '</div>'
          + '<div class="share-modal-error" id="share-users-error"></div>'
          + '<div class="share-modal-actions">'
          +   '<button class="share-modal-btn" type="button" '
          +           'id="share-users-cancel">Cancel</button>'
          +   '<button class="share-modal-btn primary" type="button" '
          +           'id="share-users-save">Share</button>'
          + '</div>',
        {wide: true}
      );
      var body = modalBody();
      var input = body.querySelector('#share-users-search');
      var selectedEl = body.querySelector('#share-users-selected');
      var resultsEl = body.querySelector('#share-users-results');
      var errorEl = body.querySelector('#share-users-error');
      var cancel = body.querySelector('#share-users-cancel');
      var save = body.querySelector('#share-users-save');
      var selected = Object.create(null);
      currentUsers.forEach(function(id){
        selected[id] = {kerberos: id, display_name: id};
      });
      var searchTimer = null;

      function selectedIds(){ return Object.keys(selected); }
      function renderSelected(){
        selectedEl.innerHTML = '';
        var ids = selectedIds();
        if (!ids.length) {
          var empty = document.createElement('span');
          empty.className = 'share-users-empty';
          empty.textContent = 'No colleagues selected';
          selectedEl.appendChild(empty);
        } else {
          ids.forEach(function(id){
            var user = selected[id];
            var chip = document.createElement('span');
            chip.className = 'share-user-chip';
            var label = document.createElement('span');
            label.textContent = user.display_name || id;
            var remove = document.createElement('button');
            remove.type = 'button';
            remove.setAttribute('aria-label', 'Remove ' + id);
            remove.textContent = '\u00D7';
            remove.addEventListener('click', function(){
              delete selected[id];
              renderSelected();
            });
            chip.appendChild(label);
            chip.appendChild(remove);
            selectedEl.appendChild(chip);
          });
        }
        save.disabled = ids.length === 0;
      }

      function renderResults(results){
        resultsEl.innerHTML = '';
        if (!results.length) {
          var empty = document.createElement('div');
          empty.className = 'share-submenu-status';
          empty.textContent = 'No matching colleagues';
          resultsEl.appendChild(empty);
          return;
        }
        results.forEach(function(user){
          var id = user && user.kerberos;
          if (!id || typeof id !== 'string') return;
          var row = document.createElement('button');
          row.type = 'button';
          row.className = 'share-user-result';
          row.setAttribute('role', 'option');
          row.disabled = !!selected[id];
          var copy = document.createElement('span');
          copy.className = 'share-user-result-copy';
          var name = document.createElement('strong');
          name.textContent = user.display_name || id;
          var meta = document.createElement('span');
          meta.textContent = [user.department, user.location]
            .filter(Boolean).join(' \u00B7 ') || 'PRISM user';
          copy.appendChild(name);
          copy.appendChild(meta);
          var kerb = document.createElement('span');
          kerb.className = 'share-user-result-kerb';
          kerb.textContent = id;
          row.appendChild(copy);
          row.appendChild(kerb);
          row.addEventListener('click', function(){
            selected[id] = user;
            renderSelected();
            row.disabled = true;
          });
          resultsEl.appendChild(row);
        });
      }

      function searchUsers(){
        var q = input.value.trim();
        errorEl.textContent = '';
        if (!q) {
          resultsEl.innerHTML =
            '<div class="share-submenu-status">'
            + 'Type to search for colleagues</div>';
          return;
        }
        resultsEl.innerHTML =
          '<div class="share-submenu-status">Searching\u2026</div>';
        fetchJson(
          USER_SEARCH_API + '?q=' + encodeURIComponent(q) + '&limit=10'
        ).then(function(res){
          if (!res || res.ok !== true || !Array.isArray(res.results)) {
            throw new Error('user search returned an invalid response');
          }
          renderResults(res.results);
        }).catch(function(exc){
          resultsEl.innerHTML =
            '<div class="share-submenu-status">Search unavailable</div>';
          errorEl.textContent = exc.message;
        });
      }

      input.addEventListener('input', function(){
        clearTimeout(searchTimer);
        searchTimer = setTimeout(searchUsers, 250);
      });
      cancel.addEventListener('click', hideModal);
      save.addEventListener('click', function(){
        var users = selectedIds();
        if (!users.length) {
          errorEl.textContent = 'Select at least one colleague.';
          return;
        }
        save.disabled = true;
        save.textContent = 'Sharing\u2026';
        errorEl.textContent = '';
        postShareMode('users', {users: users}).then(function(res){
          applyShareResponse(res, 'users');
          hideModal();
          showToast('Shared with ' + currentUsers.length
            + (currentUsers.length === 1 ? ' colleague' : ' colleagues'));
        }).catch(function(exc){
          errorEl.textContent = exc.message;
          save.disabled = false;
          save.textContent = 'Share';
        });
      });
      renderSelected();
      setTimeout(function(){ input.focus(); }, 0);
    }

    // ----- workspace add-by-reference -----
    function renderWorkspaceStatus(message){
      if (!workspaceMenu) return;
      workspaceMenu.innerHTML = '';
      var row = document.createElement('li');
      row.className = 'share-submenu-status';
      row.setAttribute('role', 'none');
      row.textContent = message;
      workspaceMenu.appendChild(row);
    }

    function addToWorkspace(workspace, row){
      var workspaceId = workspace.workspace_id;
      if (!workspaceId) return;
      row.disabled = true;
      fetchJson(
        WORKSPACES_API + encodeURIComponent(workspaceId) + '/add/',
        {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            resource_type: 'dashboard',
            owner: author,
            resource_id: DASHBOARD_ID,
            name: MANIFEST.title || document.title || DASHBOARD_ID
          })
        }
      ).then(function(res){
        if (!res || res.ok !== true || !Array.isArray(res.resources)) {
          throw new Error('workspace API returned an invalid response');
        }
        closeMenu();
        showToast('Added to ' + (workspace.name || workspaceId));
      }).catch(function(exc){
        row.disabled = false;
        showToast(exc.message, true);
      });
    }

    function renderWorkspaces(workspaces){
      workspaceMenu.innerHTML = '';
      if (!workspaces.length) {
        renderWorkspaceStatus('No workspaces yet');
        return;
      }
      workspaces.forEach(function(workspace){
        if (!workspace || !workspace.workspace_id) return;
        var li = document.createElement('li');
        li.setAttribute('role', 'none');
        var row = document.createElement('button');
        row.type = 'button';
        row.className = 'share-submenu-item';
        row.setAttribute('role', 'menuitem');
        var canAdd = workspace.role === 'owner' || workspace.role === 'editor';
        row.disabled = !canAdd;
        if (!canAdd) row.title = 'Viewer access is read-only';
        var copy = document.createElement('span');
        copy.className = 'share-workspace-copy';
        var name = document.createElement('strong');
        name.textContent = workspace.name || workspace.workspace_id;
        var meta = document.createElement('span');
        var count = Number(workspace.resource_count) || 0;
        meta.textContent = (workspace.role || 'viewer')
          + ' \u00B7 ' + count + (count === 1 ? ' resource' : ' resources');
        copy.appendChild(name);
        copy.appendChild(meta);
        row.appendChild(copy);
        if (canAdd) {
          row.addEventListener('click', function(e){
            e.stopPropagation();
            addToWorkspace(workspace, row);
          });
        }
        li.appendChild(row);
        workspaceMenu.appendChild(li);
      });
    }

    function loadWorkspaces(){
      if (workspacesLoaded || workspacesLoading || !workspaceMenu) return;
      workspacesLoading = true;
      renderWorkspaceStatus('Loading workspaces\u2026');
      fetchJson(WORKSPACES_API).then(function(res){
        if (!res || res.ok !== true || !Array.isArray(res.workspaces)) {
          throw new Error('workspace list returned an invalid response');
        }
        workspacesLoaded = true;
        renderWorkspaces(res.workspaces);
      }).catch(function(exc){
        renderWorkspaceStatus('Could not load workspaces');
        showToast(exc.message, true);
      }).then(function(){
        workspacesLoading = false;
      });
    }

    function openWorkspaceMenu(){
      if (!workspaceMenu || !workspaceBtn) return;
      workspaceMenu.hidden = false;
      workspaceBtn.setAttribute('aria-expanded', 'true');
      loadWorkspaces();
    }

    if (workspaceHost && workspaceBtn && workspaceMenu) {
      workspaceBtn.addEventListener('click', function(e){
        e.stopPropagation();
        if (workspaceMenu.hidden) openWorkspaceMenu();
        else closeWorkspaceMenu();
      });
      workspaceHost.addEventListener('mouseenter', openWorkspaceMenu);
      workspaceHost.addEventListener('mouseleave', closeWorkspaceMenu);
      workspaceMenu.addEventListener('click', function(e){
        e.stopPropagation();
      });
    }

    // ----- menu-item handlers -----
    if (items['public']) {
      items['public'].addEventListener('click', function(){
        closeMenu();
        postShareMode('public').then(function(res){
          applyShareResponse(res, 'public');
        }).catch(function(err){
          showToast(err.message, true);
        });
      });
    }
    if (items['link']) {
      items['link'].addEventListener('click', function(){
        closeMenu();
        postShareMode('link').then(function(res){
          applyShareResponse(res, 'link');
          if (!currentToken) {
            throw new Error('share API did not return a link token');
          }
          var fullUrl = window.location.origin + window.location.pathname
            + '?share=' + encodeURIComponent(currentToken);
          showLinkModal(fullUrl);
        }).catch(function(err){
          showToast(err.message, true);
        });
      });
    }
    if (items['users']) {
      items['users'].addEventListener('click', function(){
        closeMenu();
        showUsersModal();
      });
    }
    if (items['department']) {
      items['department'].addEventListener('click', function(){
        closeMenu();
        confirmDepartmentSharing();
      });
    }
    if (items['private']) {
      items['private'].addEventListener('click', function(){
        closeMenu();
        confirmStopSharing();
      });
    }
    btn.style.display = 'inline-flex';
  })();
"""


def _assemble_share_controller_js() -> str:
    return (
        _SHARE_CONTROLLER_JS_TEMPLATE
        .replace("__VALID_SHARE_MODES_JS__", _valid_share_modes_js_object())
        .replace("__SHARE_API_DEFAULT__", SHARE_API_DEFAULT)
        .replace("__USER_SEARCH_API__", USER_SEARCH_API)
        .replace("__WORKSPACES_API__", WORKSPACES_API)
    )


SHARE_CONTROLLER_JS: Final[str] = _assemble_share_controller_js()


__all__ = [
    "VALID_SHARE_MODES",
    "VALID_SHARE_MODES_SET",
    "SHARE_API_DEFAULT",
    "USER_SEARCH_API",
    "WORKSPACES_API",
    "SHARE_CONTROLLER_JS",
]
