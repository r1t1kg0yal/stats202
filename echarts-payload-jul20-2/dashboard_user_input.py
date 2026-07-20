"""dashboard_user_input -- persisted input client for compiled dashboards.

Owns the in-browser controller for ``widget: "user_input"``. The controller
uses authenticated Django endpoints for shared text, checklist, and file
state. It never writes S3 directly and never persists browser-local copies.

``rendering.DASHBOARD_APP_JS`` injects ``USER_INPUT_CONTROLLER_JS`` through
the ``__USER_INPUT_CONTROLLER__`` placeholder. Django remains the
authorization and persistence source of truth.

Destination: ``prism-core/dashboards/dashboard_user_input.py``.
"""

from __future__ import annotations

from typing import Final, FrozenSet, Tuple


VALID_USER_INPUT_MODES: Final[Tuple[str, ...]] = (
    "text",
    "checklist",
    "files",
)
VALID_USER_INPUT_MODES_SET: Final[FrozenSet[str]] = frozenset(
    VALID_USER_INPUT_MODES
)

USER_INPUT_GET_API: Final[str] = "/api/dashboard/user-input/"
USER_INPUT_SAVE_API: Final[str] = "/api/dashboard/user-input/save/"
USER_INPUT_UPLOAD_API: Final[str] = "/api/dashboard/user-input/upload/"
USER_INPUT_DOWNLOAD_API: Final[str] = "/api/dashboard/user-input/download/"
USER_INPUT_MAX_FILE_BYTES: Final[int] = 25_000_000


_USER_INPUT_CONTROLLER_JS_TEMPLATE = r"""
  // ===========================================================================
  // PERSISTED USER INPUT RUNTIME
  // ===========================================================================
  var USER_INPUTS = (PAYLOAD && PAYLOAD.userInputs) || {};
  var USER_INPUT_STATE = {};
  var USER_INPUT_INITIALIZED = false;
  var USER_INPUT_GET_API = '__USER_INPUT_GET_API__';
  var USER_INPUT_SAVE_API = '__USER_INPUT_SAVE_API__';
  var USER_INPUT_UPLOAD_API = '__USER_INPUT_UPLOAD_API__';
  var USER_INPUT_MAX_FILE_BYTES = __USER_INPUT_MAX_FILE_BYTES__;

  function _uiClone(value){
    return JSON.parse(JSON.stringify(value));
  }

  function _uiElement(tag, className, text){
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function _uiTile(widgetId){
    return document.querySelector(
      '[data-user-input-id="' + widgetId + '"]'
    );
  }

  function _uiCsrfToken(){
    var cookies = String(document.cookie || '').split(';');
    for (var i = 0; i < cookies.length; i += 1){
      var part = cookies[i].trim();
      if (part.indexOf('csrftoken=') === 0){
        return decodeURIComponent(part.slice('csrftoken='.length));
      }
    }
    return '';
  }

  function _uiIdentity(){
    return {
      owner: window.PRISM_DASHBOARD_AUTHOR || null,
      dashboardId: window.PRISM_DASHBOARD_ID
        || (MANIFEST && MANIFEST.id) || null
    };
  }

  function _uiSeed(entry){
    var seed = entry && entry.seed;
    if (entry.mode === 'text'){
      return {
        text: seed && typeof seed.text === 'string' ? seed.text : ''
      };
    }
    if (entry.mode === 'checklist'){
      return {
        items: seed && Array.isArray(seed.items)
          ? _uiClone(seed.items) : []
      };
    }
    return {files: []};
  }

  function _uiSetPhase(state, phase, message, errorDetails){
    state.phase = phase;
    var tile = _uiTile(state.widgetId);
    if (!tile) return;
    tile.setAttribute('data-user-input-state', phase);
    var status = tile.querySelector('[data-user-input-status]');
    if (!status) return;
    while (status.firstChild) status.removeChild(status.firstChild);
    status.appendChild(_uiElement(
      'span',
      'user-input-status-text',
      message || phase
    ));

    if (phase === 'conflict'){
      var reload = _uiElement(
        'button', 'user-input-link-button', 'Reload current'
      );
      reload.type = 'button';
      reload.addEventListener('click', function(){
        if (!errorDetails || !errorDetails.current_widget) return;
        _uiApplyServerWidget(
          state,
          errorDetails.current_widget,
          state.canWrite
        );
      });
      status.appendChild(reload);
    } else if (phase === 'unavailable'){
      var retry = _uiElement('button', 'user-input-link-button', 'Retry');
      retry.type = 'button';
      retry.addEventListener('click', function(){ _uiLoadAll(); });
      status.appendChild(retry);
    }
  }

  function _uiRequestJson(url, options){
    var opts = options || {};
    opts.credentials = 'same-origin';
    return fetch(url, opts).then(function(response){
      return response.text().then(function(text){
        var body = null;
        if (text){
          try { body = JSON.parse(text); }
          catch (parseError) {
            body = {
              ok: false,
              error: {
                code: 'invalid_response',
                message: 'The server returned invalid JSON.',
                details: {}
              }
            };
          }
        }
        if (!response.ok || !body || body.ok !== true){
          var failure = new Error(
            body && body.error && body.error.message
              ? body.error.message
              : 'The user-input request failed.'
          );
          failure.status = response.status;
          failure.body = body;
          throw failure;
        }
        return body;
      });
    });
  }

  function _uiPostJson(url, payload){
    return _uiRequestJson(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': _uiCsrfToken()
      },
      body: JSON.stringify(payload)
    });
  }

  function _uiErrorDetails(error){
    return error && error.body && error.body.error
      ? error.body.error.details || {} : {};
  }

  function _uiHandleMutationError(state, error){
    var bodyError = error && error.body && error.body.error;
    if (error && error.status === 409
        && bodyError && bodyError.code === 'revision_conflict'){
      _uiSetPhase(
        state,
        'conflict',
        'Another save won. Reload current or keep editing.',
        bodyError.details || {}
      );
      return;
    }
    _uiSetPhase(
      state,
      'unavailable',
      bodyError && bodyError.message
        ? bodyError.message : 'Saving is unavailable.'
    );
  }

  function _uiMarkDirty(state){
    if (!state.canWrite) return;
    state.dirty = true;
    _uiSetPhase(state, 'dirty', 'Unsaved changes');
  }

  function _uiActionButton(label, className){
    var button = _uiElement(
      'button',
      'user-input-button' + (className ? ' ' + className : ''),
      label
    );
    button.type = 'button';
    return button;
  }

  function _uiSaveContent(state, content){
    if (!state.canWrite || state.phase === 'saving') return;
    var identity = _uiIdentity();
    _uiSetPhase(state, 'saving', 'Saving');
    _uiPostJson(USER_INPUT_SAVE_API, {
      owner: identity.owner,
      dashboard_id: identity.dashboardId,
      widget_id: state.widgetId,
      mode: state.entry.mode,
      expected_revision_id: state.revisionId,
      content: content
    }).then(function(response){
      _uiApplyServerWidget(state, response.widget, response.can_write);
      _uiSetPhase(state, 'saved', 'Saved');
    }).catch(function(error){
      _uiHandleMutationError(state, error);
    });
  }

  function _uiRenderText(state, host){
    var textarea = _uiElement('textarea', 'user-input-textarea');
    textarea.rows = Number(state.entry.rows || 8);
    textarea.placeholder = state.entry.placeholder || '';
    textarea.value = state.content && typeof state.content.text === 'string'
      ? state.content.text : '';
    textarea.disabled = !state.canWrite;
    textarea.addEventListener('input', function(){
      state.content = {text: textarea.value};
      _uiMarkDirty(state);
    });
    host.appendChild(textarea);

    if (state.canWrite){
      var actions = _uiElement('div', 'user-input-actions');
      var save = _uiActionButton('Save', 'user-input-primary');
      save.addEventListener('click', function(){
        state.content = {text: textarea.value};
        _uiSaveContent(state, state.content);
      });
      actions.appendChild(save);
      host.appendChild(actions);
    }
  }

  function _uiNewChecklistId(){
    if (!window.crypto || typeof window.crypto.randomUUID !== 'function'){
      throw new Error('Secure checklist id generation is unavailable.');
    }
    return 'ui-' + window.crypto.randomUUID();
  }

  function _uiRenderChecklist(state, host){
    var items = state.content && Array.isArray(state.content.items)
      ? state.content.items : [];
    state.content = {items: items};
    var list = _uiElement('div', 'user-input-checklist');

    function rerender(){
      _uiRenderState(state);
      _uiMarkDirty(state);
    }

    items.forEach(function(item, index){
      var row = _uiElement('div', 'user-input-checklist-row');
      row.setAttribute('data-checklist-item-id', item.id);

      var check = document.createElement('input');
      check.type = 'checkbox';
      check.checked = !!item.checked;
      check.disabled = !state.canWrite;
      check.setAttribute('aria-label', 'Complete ' + String(item.text || 'item'));
      check.addEventListener('change', function(){
        item.checked = check.checked;
        _uiMarkDirty(state);
      });
      row.appendChild(check);

      var text = document.createElement('input');
      text.type = 'text';
      text.className = 'user-input-checklist-text';
      text.value = item.text || '';
      text.disabled = !state.canWrite;
      text.maxLength = 2000;
      text.addEventListener('input', function(){
        item.text = text.value;
        _uiMarkDirty(state);
      });
      row.appendChild(text);

      if (state.canWrite){
        var up = _uiActionButton('Up', 'user-input-compact');
        up.disabled = index === 0;
        up.addEventListener('click', function(){
          if (index <= 0) return;
          var moved = items.splice(index, 1)[0];
          items.splice(index - 1, 0, moved);
          rerender();
        });
        row.appendChild(up);

        var down = _uiActionButton('Down', 'user-input-compact');
        down.disabled = index >= items.length - 1;
        down.addEventListener('click', function(){
          if (index >= items.length - 1) return;
          var moved = items.splice(index, 1)[0];
          items.splice(index + 1, 0, moved);
          rerender();
        });
        row.appendChild(down);

        var remove = _uiActionButton('Remove', 'user-input-compact');
        remove.addEventListener('click', function(){
          items.splice(index, 1);
          rerender();
        });
        row.appendChild(remove);
      }
      list.appendChild(row);
    });
    host.appendChild(list);

    if (state.canWrite){
      var actions = _uiElement('div', 'user-input-actions');
      var add = _uiActionButton('Add item');
      add.addEventListener('click', function(){
        try {
          items.push({id: _uiNewChecklistId(), text: '', checked: false});
          rerender();
        } catch (error) {
          _uiSetPhase(state, 'unavailable', error.message);
        }
      });
      actions.appendChild(add);
      var save = _uiActionButton('Save', 'user-input-primary');
      save.addEventListener('click', function(){
        _uiSaveContent(state, {items: items});
      });
      actions.appendChild(save);
      host.appendChild(actions);
    }
  }

  function _uiSaveActiveFiles(state, activeFileIds){
    _uiSaveContent(state, {active_file_ids: activeFileIds});
  }

  function _uiUploadFile(state, file){
    if (!state.canWrite || !file || state.phase === 'saving') return;
    if (file.size > USER_INPUT_MAX_FILE_BYTES){
      _uiSetPhase(
        state, 'unavailable', 'The selected file exceeds 25 MB.'
      );
      return;
    }
    var identity = _uiIdentity();
    var form = new FormData();
    form.append('owner', identity.owner);
    form.append('dashboard_id', identity.dashboardId);
    form.append('widget_id', state.widgetId);
    form.append('mode', 'files');
    form.append(
      'expected_revision_id',
      state.revisionId === null ? '' : state.revisionId
    );
    form.append('file', file, file.name);

    _uiSetPhase(state, 'saving', 'Uploading');
    _uiRequestJson(USER_INPUT_UPLOAD_API, {
      method: 'POST',
      headers: {'X-CSRFToken': _uiCsrfToken()},
      body: form
    }).then(function(response){
      _uiApplyServerWidget(state, response.widget, response.can_write);
      _uiSetPhase(state, 'saved', 'Uploaded');
    }).catch(function(error){
      _uiHandleMutationError(state, error);
    });
  }

  function _uiRenderFiles(state, host){
    var files = state.content && Array.isArray(state.content.files)
      ? state.content.files : [];
    state.content = {files: files};
    var list = _uiElement('div', 'user-input-file-list');

    if (!files.length){
      list.appendChild(_uiElement(
        'div', 'user-input-empty', 'No files uploaded.'
      ));
    }

    files.forEach(function(file){
      var row = _uiElement('div', 'user-input-file-row');
      var main = _uiElement('div', 'user-input-file-main');
      var name = _uiElement(
        file.download_url ? 'a' : 'span',
        'user-input-file-name',
        file.normalized_filename || file.original_filename || file.file_id
      );
      if (file.download_url){
        name.href = file.download_url;
        name.setAttribute('download', '');
      }
      main.appendChild(name);
      var meta = _uiElement(
        'span',
        'user-input-file-meta',
        String(file.size_bytes || 0) + ' bytes'
      );
      main.appendChild(meta);
      row.appendChild(main);

      if (state.canWrite){
        var remove = _uiActionButton('Remove', 'user-input-compact');
        remove.addEventListener('click', function(){
          var remaining = files.filter(function(candidate){
            return candidate.file_id !== file.file_id;
          }).map(function(candidate){ return candidate.file_id; });
          _uiSaveActiveFiles(state, remaining);
        });
        row.appendChild(remove);
      }
      list.appendChild(row);
    });
    host.appendChild(list);

    if (state.canWrite){
      var actions = _uiElement('div', 'user-input-actions');
      var picker = document.createElement('input');
      picker.type = 'file';
      picker.className = 'user-input-file-picker';
      picker.accept = (
        '.pdf,.docx,.xlsx,.pptx,.txt,.md,.csv,.json,.png,.jpg,.jpeg,'
        + '.gif,.webp,.bmp,.tif,.tiff'
      );
      actions.appendChild(picker);
      var upload = _uiActionButton('Upload', 'user-input-primary');
      upload.addEventListener('click', function(){
        _uiUploadFile(state, picker.files && picker.files[0]);
      });
      actions.appendChild(upload);
      host.appendChild(actions);
    }
  }

  function _uiRenderState(state){
    var tile = _uiTile(state.widgetId);
    if (!tile) return;
    var host = tile.querySelector('[data-user-input-content]');
    if (!host) return;
    while (host.firstChild) host.removeChild(host.firstChild);
    if (state.entry.mode === 'text'){
      _uiRenderText(state, host);
    } else if (state.entry.mode === 'checklist'){
      _uiRenderChecklist(state, host);
    } else {
      _uiRenderFiles(state, host);
    }
    var access = tile.querySelector('[data-user-input-access]');
    if (access){
      access.textContent = state.canWrite ? '' : 'Read only';
      access.hidden = !!state.canWrite;
    }
  }

  function _uiApplyServerWidget(state, widget, canWrite){
    if (!widget || widget.widget_id !== state.widgetId
        || widget.mode !== state.entry.mode){
      _uiSetPhase(
        state,
        'unavailable',
        'The server returned a mismatched widget state.'
      );
      return;
    }
    state.revisionId = widget.revision_id || null;
    state.content = _uiClone(widget.content || _uiSeed(state.entry));
    state.persistedContent = _uiClone(state.content);
    state.canWrite = canWrite === true;
    state.dirty = false;
    state.updatedAt = widget.updated_at || null;
    _uiRenderState(state);
    _uiSetPhase(
      state,
      'ready',
      state.canWrite
        ? (state.updatedAt ? 'Saved ' + state.updatedAt : 'Ready')
        : 'Read only'
    );
  }

  function _uiLoadAll(){
    var ids = Object.keys(USER_INPUTS);
    if (!ids.length) return Promise.resolve();
    var identity = _uiIdentity();
    if (!identity.owner || !identity.dashboardId){
      ids.forEach(function(widgetId){
        _uiSetPhase(
          USER_INPUT_STATE[widgetId],
          'unavailable',
          'Dashboard identity is unavailable.'
        );
      });
      return Promise.resolve();
    }

    ids.forEach(function(widgetId){
      _uiSetPhase(USER_INPUT_STATE[widgetId], 'loading', 'Loading');
    });
    var query = (
      '?owner=' + encodeURIComponent(identity.owner)
      + '&dashboard_id=' + encodeURIComponent(identity.dashboardId)
    );
    return _uiRequestJson(USER_INPUT_GET_API + query, {method: 'GET'})
      .then(function(response){
        ids.forEach(function(widgetId){
          var widget = response.widgets && response.widgets[widgetId];
          if (!widget){
            _uiSetPhase(
              USER_INPUT_STATE[widgetId],
              'unavailable',
              'The server omitted this widget.'
            );
            return;
          }
          _uiApplyServerWidget(
            USER_INPUT_STATE[widgetId],
            widget,
            response.can_write
          );
        });
      })
      .catch(function(error){
        var bodyError = error && error.body && error.body.error;
        ids.forEach(function(widgetId){
          _uiSetPhase(
            USER_INPUT_STATE[widgetId],
            'unavailable',
            bodyError && bodyError.message
              ? bodyError.message : 'Persisted input is unavailable.'
          );
        });
      });
  }

  function initUserInputs(){
    if (USER_INPUT_INITIALIZED) return;
    USER_INPUT_INITIALIZED = true;
    Object.keys(USER_INPUTS).forEach(function(widgetId){
      var entry = USER_INPUTS[widgetId];
      USER_INPUT_STATE[widgetId] = {
        widgetId: widgetId,
        entry: entry,
        revisionId: null,
        content: _uiSeed(entry),
        persistedContent: null,
        canWrite: false,
        dirty: false,
        phase: 'idle',
        updatedAt: null
      };
      _uiRenderState(USER_INPUT_STATE[widgetId]);
      _uiSetPhase(USER_INPUT_STATE[widgetId], 'idle', 'Not loaded');
    });
    _uiLoadAll();
  }

  window.initUserInputs = initUserInputs;
  window.DASHBOARD_USER_INPUTS = USER_INPUTS;
  window.DASHBOARD_USER_INPUT_STATE = USER_INPUT_STATE;
"""


def _assemble_user_input_controller_js() -> str:
    return (
        _USER_INPUT_CONTROLLER_JS_TEMPLATE
        .replace("__USER_INPUT_GET_API__", USER_INPUT_GET_API)
        .replace("__USER_INPUT_SAVE_API__", USER_INPUT_SAVE_API)
        .replace("__USER_INPUT_UPLOAD_API__", USER_INPUT_UPLOAD_API)
        .replace(
            "__USER_INPUT_MAX_FILE_BYTES__",
            str(USER_INPUT_MAX_FILE_BYTES),
        )
    )


USER_INPUT_CONTROLLER_JS: Final[str] = _assemble_user_input_controller_js()


__all__ = [
    "VALID_USER_INPUT_MODES",
    "VALID_USER_INPUT_MODES_SET",
    "USER_INPUT_GET_API",
    "USER_INPUT_SAVE_API",
    "USER_INPUT_UPLOAD_API",
    "USER_INPUT_DOWNLOAD_API",
    "USER_INPUT_MAX_FILE_BYTES",
    "USER_INPUT_CONTROLLER_JS",
]
