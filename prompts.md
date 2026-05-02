Title: API client architecture + GS proxy transport layer — verbatim introspection

I'm building a plug-and-play model for `GS/data/apis/` analogous to
`GS/viz/altair/altair-payload/` and `GS/viz/echarts/echarts-payload/`,
so that `mcp/clients/<src>_client.py` files can be developed in a
staging repo and dragged into PRISM unchanged. The blocker is faithful
local replication of the GS proxy / Kerberos transport layer (a stub
mirror with the same signatures as PRISM's real
`gs_app_proxy_negotiate.py` but with vanilla-`requests` bodies). Your
job in this prompt is to produce the introspection material I need to
build that stub mirror, the per-client payloads, and the L2 skill
modules — without fabricating anything.

Use `list_ai_repo` and `execute_analysis_script` to introspect. Reply
with verbatim source pasted in fenced code blocks and exact paths.
Mirror the section structure below — each numbered section in your
reply should answer the same-numbered section here.

If a fact requires reading a file too large to paste in full, paste
the relevant section verbatim and cite the file path + line range so
I can reconcile.

---

## 1. `mcp/gs_app_proxy_negotiate.py` — full verbatim source

Paste the complete current contents of
`ai_development/mcp/gs_app_proxy_negotiate.py` in a single fenced
`python` block. Do not paraphrase, do not abbreviate, do not summarize
docstrings. I need the file byte-for-byte to verify a documentary
reconstruction we have in `prism/_reference/gs_app_proxy_negotiate.py`
against PRISM's actual source.

After the verbatim paste, explicitly answer:

1.1 Is `urllib3.util.parse_url` actually used anywhere in the body?
    The reconstruction has it in the import block but cannot find a
    use. Confirm dead import / used / there for a side effect.

1.2 In `manual_https_request`, what is the exact `try` / `except` /
    `finally` nesting around the SSL socket lifecycle? Specifically:
    where does the inner `finally: ssl_sock.close()` sit relative to
    the outer `except Exception: sock.close(); raise`? Quote the 5-10
    lines that frame this nesting verbatim.

1.3 Are there any decorators (`@staticmethod`, `@functools.cache`,
    `@functools.lru_cache`, `@retry`, etc.) on `get_spnego_token`,
    `KerberosProxyAuthAdapter`, `session_and_auth`, or
    `manual_https_request`?

1.4 In `KerberosProxyAuthAdapter.proxies`, are the dict values
    f-strings (`f"http://{proxy_address}"`) or bare literals
    (`"http://{proxy_address}"`)? The OCR scan that informed the
    reconstruction had stripped the `f`-prefix and we restored it as
    a judgement call.

---

## 2. `mcp/clients/__init__.py` — full verbatim source

Paste the complete current contents of
`ai_development/mcp/clients/__init__.py` in a single fenced `python`
block.

If the file imports each client module by name, list every name
imported. If it uses dynamic discovery (`pkgutil.iter_modules`,
`importlib.import_module`, etc.), explain the mechanism and list the
modules it discovers in the current state.

---

## 3. `mcp/tools/script_exec_tools.py` — verbatim namespace-injection block for clients

Locate the section of `script_exec_tools.py` that builds the
`exec_namespace` dict for `execute_analysis_script`. Paste the
verbatim entries that inject the API client modules (the entries
analogous to `"make_chart": validate_params(_wrap_chart_func(...))`
but for `*_client` modules).

Specifically I need:

3.1 The verbatim import block that brings the client modules into
    `script_exec_tools.py`'s namespace (with their underscore
    prefixes). The fragment we have shows ten:
    `bis_client`, `fdic_client`, `newyorkfed_client`, `openfigi_client`,
    `sec_edgar_client`, `substack_client`, `treasury_client`,
    `treasury_direct_client`, `prediction_markets_client`,
    `wikipedia_client`. Confirm or correct.

3.2 The verbatim namespace-dict literal entries that map each client
    to its sandbox name. Each entry is roughly
    `"<client_name>": _<client_name>`. List ALL of them — do not
    abbreviate or use ellipses.

3.3 Of the 17 client modules at `mcp/clients/` (the inventory in §6
    below), which are NOT injected into the sandbox? For each
    not-injected client, explain why (intentional? loaded
    dynamically? out of date?). The seven I'm uncertain about:
    `cftc_client`, `congress`, `federal_register_client`,
    `fred_client`, `ofac_client`, `ofr_client`, `usitc_client`.

3.4 Does `script_exec_tools.py` do anything special about Kerberos /
    `KRB5CCNAME` before launching the sandbox process, or does the
    sandbox just inherit `os.environ` from the MCP server process?

---

## 4. `_USE_GS_PROXY` flag — what controls it

For at least three client modules — `fdic_client.py`,
`treasury_client.py`, and `bis_client.py` — paste the verbatim
module-level line(s) that define `_USE_GS_PROXY`. Then explicitly
answer:

4.1 Is it always a hardcoded `True`? An `os.getenv(...)` lookup? A
    network probe (e.g. tries the proxy and falls back if unreachable)?
    Some other mechanism?

4.2 If hardcoded, is there any code path that ever flips it (e.g. a
    `set_offline_mode()` function) or is the only flip-mechanism
    editing the source?

4.3 If env-driven, what's the exact env var name and how is the
    value parsed?

4.4 What's the `_USE_GS_PROXY = False` code path actually do — fall
    through to vanilla `requests.get/post(...)` with no proxy at
    all? Any direct-mode timeouts / retries that differ from the
    proxied path?

---

## 5. Per-client transport choice for the 11 unverified clients

For each of the following 11 client modules, report:
- Which transport(s) it uses: `session_and_auth()` (standard requests
  proxy) or `manual_https_request()` (manual CONNECT tunnel) or both
  (per-host).
- Quote the verbatim import line from `gs_app_proxy_negotiate` and
  the verbatim line where the transport function is called.
- One sentence explanation of why that choice (target API behaviour,
  rate limiting, header sensitivity, etc.) — read any docstring or
  comment in the client that explains this, and quote it.

The 11 clients to cover:

  5.1  `ofr_client.py`
  5.2  `openfigi_client.py`
  5.3  `sec_edgar_client.py`
  5.4  `substack_client.py`
  5.5  `congress.py`
  5.6  `federal_register_client.py`
  5.7  `usitc_client.py`
  5.8  `cftc_client.py`
  5.9  `newyorkfed_client.py`
  5.10 `ofac_client.py`
  5.11 `wikipedia_client.py`

---

## 6. Per-client public-method inventory

For each of the 17 clients at `mcp/clients/`, list its public surface:
top-level functions, class methods, module-level constants /
registries / enums.

Use `list_ai_repo(file_paths=["ai_development/mcp/clients/<file>.py"],
mode="signatures")` to extract this efficiently. One module per
sub-section, each named after the file. Format per entry:

```
<name> (<kind: function | class | classmethod | constant>)
  one-line description, ideally pulled from the docstring or
  the explicit __all__ entry
```

The 17 modules:

  6.1   `bis_client.py`
  6.2   `fdic_client.py`
  6.3   `ofr_client.py`
  6.4   `openfigi_client.py`
  6.5   `treasury_client.py`
  6.6   `congress.py`
  6.7   `treasury_direct_client.py`
  6.8   `prediction_markets_client.py`
  6.9   `wikipedia_client.py`
  6.10  `federal_register_client.py`
  6.11  `usitc_client.py`
  6.12  `substack_client.py`
  6.13  `sec_edgar_client.py`
  6.14  `cftc_client.py`
  6.15  `newyorkfed_client.py`
  6.16  `ofac_client.py`
  6.17  `fred_client.py`

If any client exports a `__all__` list, paste the verbatim `__all__`
literal.

---

## 7. Full `MODULE_REGISTRY` dump for client-mapped entries

In `ai_development/context/registry.py`, locate `MODULE_REGISTRY` and
paste the verbatim entry (every field, in its actual source order)
for each of the following keys. Do not paraphrase descriptions.

  7.1   `fdic_guide`
  7.2   `bis_data_guide`
  7.3   `nyfed_guide`
  7.4   `ofr_guide`
  7.5   `openfigi_guide`
  7.6   `sec_edgar_guide`
  7.7   `substack_guide`
  7.8   `treasury_api`
  7.9   `prediction_markets_skill`
  7.10  `fred_guide`

Plus any registry entries whose `description` or `source` references
one of the following clients but is not in the list above:

  7.11  `cftc_client`
  7.12  `congress` (note: file naming is inconsistent — module is
        `mcp/clients/congress.py`, no `_client` suffix)
  7.13  `federal_register_client`
  7.14  `usitc_client`
  7.15  `wikipedia_client`
  7.16  `ofac_client`

If a client has NO registry entry at all (i.e. it's auto-injected
into the sandbox but the LLM has no L2 guide for it), say so plainly
for that client.

For every entry returned, surface the `bundle` field if present
(verbatim list of bundled module IDs), and `specialization` if
present.

---

## 8. Sibling exception classes per client

`treasury_client.py` exports a `FiscalDataError` class. For each of
the 17 clients, report whether an analogous exception class exists
(e.g. `FdicError`, `BisError`, `TreasuryDirectError`, etc.). If yes,
paste the verbatim class definition (just the `class X(Y): ...`
header line plus any `__init__` and any class-level attributes — no
need to paste full method bodies).

Format the answer as one table:

```
client                          exception class            inherits from
treasury_client                  FiscalDataError            Exception
fdic_client                      ?                          ?
...
```

---

## 9. Shared `mcp/utils/` helpers used across clients

Look at the imports in each of the 17 client modules. Identify any
helper module under `ai_development/mcp/utils/` (or elsewhere in
`mcp/`) that is imported by more than one client. Examples to look
for:

- A shared HTTP-request wrapper (analogous to the proposed
  `request_json()` in our staging design).
- A shared pagination helper.
- A shared response normalizer / dict-coercion helper.
- A shared retry decorator.
- A shared rate limiter.
- A shared schema discovery helper.

For each shared helper found, list:
  - module path (e.g. `mcp/utils/<name>.py`)
  - public functions / classes (signatures only)
  - which clients import it

If no shared helpers exist (each client has its own bespoke
request/pagination/retry code), say so plainly. The prism/api-clients
doc currently treats this case as the default but I want to confirm.

---

## 10. `KRB5CCNAME` and the sandbox process

Already touched in §3.4. To make the answer self-contained: walk
through how a Kerberos ticket cache gets discovered when an LLM
script inside `execute_analysis_script` calls
`from ai_development.mcp.gs_app_proxy_negotiate import session_and_auth`
and then makes an HTTP request.

Specifically:

10.1 Does the sandbox process get its own copy of `os.environ` or
     does it inherit from the MCP server process at fork time?

10.2 If `KRB5CCNAME` was set on the MCP server's environment, does it
     propagate? Conversely if it's set inside the script, does it
     stick for the lifetime of that script invocation?

10.3 The `gs_app_proxy_negotiate.py` module-level bootstrap (the
     `if "KRB5CCNAME" not in os.environ:` block) runs at import time.
     Does it run once per MCP-server lifetime (because the import is
     cached), once per `execute_analysis_script` invocation (because
     the sandbox is a fresh process each time), or some hybrid?

10.4 If the discovered ticket cache has expired between MCP-server
     start and the current script invocation, what surfaces — a
     `GSSError` from `get_spnego_token()`, or something cleaner?

---

## 11. Carry-over from the previous round-trip — `list_ai_repo` verbatim

The previous context-extraction round (2026-05-01 21:25) produced
parameter names + the four mode values for `list_ai_repo` but did
NOT paste the verbatim function definition. Please complete that now:

11.1 Paste the verbatim function definition of `list_ai_repo` from
     `ai_development/mcp/tools/developer_tools.py` — signature,
     docstring, parameter defaults, return-type annotation. The full
     def, in a single fenced `python` block.

11.2 If `list_ai_repo` does any pre-processing on its inputs before
     dispatching to `RepositoryExplorer` (e.g. smart filename
     resolution, default extensions, sentinel handling), quote the
     relevant lines.

---

## 12. Sanity / coverage

Two quick coverage questions:

12.1 Are there any `*_client.py` files at `mcp/clients/` that are
     NOT in the 17-name inventory above? Or any module in
     `ai_development/mcp/` (outside `mcp/tools/`, `mcp/clients/`,
     `mcp/utils/`) that we should know about for the API endeavor?

12.2 Has the file `gs_app_proxy_negotiate.py` been refactored or
     renamed anywhere recently — is there a `gapn4.py` / `gapn5.py`
     / a `transport/` subpackage / anything else superseding it that
     we should treat as canonical instead?

---

If part of this prompt cannot be answered, add a brief
"## Could not resolve" section at the end listing what you tried and
what blocked it.
