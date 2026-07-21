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
USER_INPUT_MAX_FILES: Final[int] = 100


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
  var USER_INPUT_MAX_FILES = __USER_INPUT_MAX_FILES__;
  var USER_INPUT_FILE_DROP_GUARD_INSTALLED = false;
  var USER_INPUT_DATE_FORMATTER = new Intl.DateTimeFormat(undefined, {
    weekday: 'short',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit'
  });

  function _uiClone(value){
    return JSON.parse(JSON.stringify(value));
  }

  function _uiElement(tag, className, text){
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function _uiFormatTimestamp(value){
    return USER_INPUT_DATE_FORMATTER.format(new Date(value));
  }

  function _uiSavedLabel(state){
    return state.updatedAt
      ? 'Saved ' + _uiFormatTimestamp(state.updatedAt)
      : 'Ready';
  }

  function _uiFormatBytes(value){
    var bytes = Number(value || 0);
    if (bytes < 1000) return bytes + ' B';
    var units = ['KB', 'MB', 'GB'];
    var amount = bytes;
    var unit = '';
    for (var i = 0; i < units.length && amount >= 1000; i += 1){
      amount /= 1000;
      unit = units[i];
    }
    return (amount >= 10 ? amount.toFixed(0) : amount.toFixed(1))
      + ' ' + unit;
  }

  function _uiFileType(filename){
    var match = String(filename || '').match(/\.([^.]+)$/);
    return match ? match[1].slice(0, 5).toUpperCase() : 'FILE';
  }

  function _uiHasFileDrag(event){
    var transfer = event && event.dataTransfer;
    if (!transfer || !transfer.types) return false;
    return Array.prototype.indexOf.call(transfer.types, 'Files') !== -1;
  }

  function _uiDroppedFiles(transfer){
    var files = Array.prototype.slice.call(
      transfer && transfer.files ? transfer.files : []
    );
    if (files.length) return files;
    return Array.prototype.slice.call(
      transfer && transfer.items ? transfer.items : []
    ).filter(function(item){
      return item && item.kind === 'file';
    }).map(function(item){
      return item.getAsFile();
    }).filter(Boolean);
  }

  function _uiInstallFileDropGuard(){
    if (USER_INPUT_FILE_DROP_GUARD_INSTALLED) return;
    USER_INPUT_FILE_DROP_GUARD_INSTALLED = true;
    ['dragover', 'drop'].forEach(function(eventName){
      window.addEventListener(eventName, function(event){
        if (_uiHasFileDrag(event)) event.preventDefault();
      });
    });
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
    if (state.savedTimer && phase !== 'saved'){
      window.clearTimeout(state.savedTimer);
      state.savedTimer = null;
    }
    state.phase = phase;
    var tile = _uiTile(state.widgetId);
    if (!tile) return;
    tile.setAttribute('data-user-input-state', phase);
    var dropzone = tile.querySelector('[data-user-input-dropzone]');
    if (dropzone){
      dropzone.setAttribute(
        'aria-disabled',
        phase === 'saving' || state.uploading ? 'true' : 'false'
      );
    }
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

  function _uiAcknowledgeSaved(state){
    var label = _uiSavedLabel(state);
    if (state.savedTimer) window.clearTimeout(state.savedTimer);
    _uiSetPhase(state, 'saved', label);
    state.savedTimer = window.setTimeout(function(){
      state.savedTimer = null;
      if (!state.dirty && state.phase === 'saved'){
        _uiSetPhase(state, 'ready', label);
      }
    }, 1800);
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
      _uiAcknowledgeSaved(state);
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

  function _uiUploadFile(state, file, index, total){
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

    _uiSetPhase(
      state,
      'saving',
      total > 1
        ? 'Uploading ' + index + ' of ' + total + ': ' + file.name
        : 'Uploading ' + file.name
    );
    return _uiRequestJson(USER_INPUT_UPLOAD_API, {
      method: 'POST',
      headers: {'X-CSRFToken': _uiCsrfToken()},
      body: form
    }).then(function(response){
      _uiApplyServerWidget(state, response.widget, response.can_write);
      return response;
    });
  }

  function _uiUploadFiles(state, fileList){
    if (!state.canWrite || state.uploading) return;
    var files = Array.prototype.slice.call(fileList || []).filter(Boolean);
    if (!files.length) return;

    var activeFiles = state.content && Array.isArray(state.content.files)
      ? state.content.files.length : 0;
    if (activeFiles + files.length > USER_INPUT_MAX_FILES){
      _uiSetPhase(
        state,
        'unavailable',
        'This widget can contain up to ' + USER_INPUT_MAX_FILES + ' files.'
      );
      return;
    }
    for (var i = 0; i < files.length; i += 1){
      if (files[i].size > USER_INPUT_MAX_FILE_BYTES){
        _uiSetPhase(
          state,
          'unavailable',
          files[i].name + ' exceeds the 25 MB file limit.'
        );
        return;
      }
    }

    state.uploading = true;
    var chain = Promise.resolve();
    files.forEach(function(file, fileIndex){
      chain = chain.then(function(){
        return _uiUploadFile(state, file, fileIndex + 1, files.length);
      });
    });
    chain.then(function(){
      state.uploading = false;
      _uiAcknowledgeSaved(state);
    }).catch(function(error){
      state.uploading = false;
      _uiHandleMutationError(state, error);
    });
  }

  function _uiRenderFiles(state, host){
    var files = state.content && Array.isArray(state.content.files)
      ? state.content.files : [];
    state.content = {files: files};

    if (state.canWrite){
      var picker = document.createElement('input');
      picker.type = 'file';
      picker.className = 'user-input-file-picker';
      picker.accept = (
        '.pdf,.docx,.xlsx,.pptx,.msg,.txt,.md,.csv,.json,.png,.jpg,'
        + '.jpeg,.gif,.webp,.bmp,.tif,.tiff'
      );
      picker.multiple = true;
      picker.hidden = true;

      var dropzone = _uiElement('div', 'user-input-dropzone');
      dropzone.tabIndex = 0;
      dropzone.setAttribute('role', 'button');
      dropzone.setAttribute('data-user-input-dropzone', '');
      dropzone.setAttribute(
        'aria-label',
        'Drop files here or choose files to upload'
      );
      dropzone.setAttribute(
        'aria-disabled',
        state.uploading ? 'true' : 'false'
      );
      dropzone.appendChild(_uiElement(
        'span',
        'user-input-drop-title',
        'Drop files here or choose files'
      ));
      dropzone.appendChild(_uiElement(
        'span',
        'user-input-drop-hint',
        'PDF, Office, Outlook .msg, text and images · 25 MB each'
      ));
      dropzone.appendChild(picker);

      function chooseFiles(selected){
        _uiUploadFiles(state, selected);
        picker.value = '';
      }

      dropzone.addEventListener('click', function(){
        if (!state.uploading) picker.click();
      });
      dropzone.addEventListener('keydown', function(event){
        if (
          !state.uploading
          && (event.key === 'Enter' || event.key === ' ')
        ){
          event.preventDefault();
          picker.click();
        }
      });
      picker.addEventListener('change', function(){
        chooseFiles(picker.files);
      });

      var dragDepth = 0;
      dropzone.addEventListener('dragenter', function(event){
        if (!_uiHasFileDrag(event) || state.uploading) return;
        event.preventDefault();
        dragDepth += 1;
        dropzone.classList.add('is-dragover');
      });
      dropzone.addEventListener('dragover', function(event){
        if (!_uiHasFileDrag(event) || state.uploading) return;
        event.preventDefault();
        event.stopPropagation();
        event.dataTransfer.dropEffect = 'copy';
      });
      dropzone.addEventListener('dragleave', function(event){
        if (!_uiHasFileDrag(event)) return;
        dragDepth = Math.max(0, dragDepth - 1);
        if (dragDepth === 0) dropzone.classList.remove('is-dragover');
      });
      dropzone.addEventListener('drop', function(event){
        if (!_uiHasFileDrag(event) || state.uploading) return;
        event.preventDefault();
        event.stopPropagation();
        dragDepth = 0;
        dropzone.classList.remove('is-dragover');
        chooseFiles(_uiDroppedFiles(event.dataTransfer));
      });
      host.appendChild(dropzone);
    }

    var list = _uiElement('div', 'user-input-file-list');
    files.forEach(function(file){
      var row = _uiElement('div', 'user-input-file-row');
      var identity = _uiElement('div', 'user-input-file-identity');
      identity.appendChild(_uiElement(
        'span',
        'user-input-file-type',
        _uiFileType(
          file.normalized_filename || file.original_filename || file.file_id
        )
      ));
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
        _uiFormatBytes(file.size_bytes)
      );
      main.appendChild(meta);
      identity.appendChild(main);
      row.appendChild(identity);

      if (state.canWrite){
        var remove = _uiActionButton(
          'Remove', 'user-input-compact user-input-danger'
        );
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
    if (files.length){
      host.appendChild(list);
    } else if (!state.canWrite){
      host.appendChild(_uiElement(
        'div', 'user-input-empty', 'No files have been added.'
      ));
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
    state.parentRevisionId = widget.parent_revision_id || null;
    state.contentSha256 = widget.content_sha256 || null;
    state.source = widget.source || null;
    state.content = _uiClone(widget.content || _uiSeed(state.entry));
    state.persistedContent = _uiClone(state.content);
    state.canWrite = canWrite === true;
    state.dirty = false;
    state.updatedAt = widget.updated_at || null;
    state.updatedBy = widget.updated_by || null;
    _uiRenderState(state);
    _uiSetPhase(
      state,
      'ready',
      state.canWrite ? _uiSavedLabel(state) : 'Read only'
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
    if (Object.keys(USER_INPUTS).some(function(widgetId){
      return USER_INPUTS[widgetId].mode === 'files';
    })){
      _uiInstallFileDropGuard();
    }
    Object.keys(USER_INPUTS).forEach(function(widgetId){
      var entry = USER_INPUTS[widgetId];
      USER_INPUT_STATE[widgetId] = {
        widgetId: widgetId,
        entry: entry,
        revisionId: null,
        parentRevisionId: null,
        contentSha256: null,
        source: null,
        content: _uiSeed(entry),
        persistedContent: null,
        canWrite: false,
        dirty: false,
        phase: 'idle',
        updatedAt: null,
        updatedBy: null,
        uploading: false,
        savedTimer: null
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
        .replace(
            "__USER_INPUT_MAX_FILES__",
            str(USER_INPUT_MAX_FILES),
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
    "USER_INPUT_MAX_FILES",
    "USER_INPUT_CONTROLLER_JS",
]
