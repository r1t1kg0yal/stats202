# External repos archive

Repos that were cloned into the staging tree at some point for
reference or evaluation, but are not actively integrated as PRISM
payloads or staging dev tools. Kept here per the workspace rule
"never delete files".

## Contents

| Folder        | What it is                                                                 | When archived | Why archived                                                                                                |
|---|---|---|---|
| `defeatbeta/` | Clone of the [`defeatbeta_api`](https://github.com/defeat-beta/defeatbeta-api) Python package (yfinance-style stock-data alternative). Contains pyproject.toml, source tree, MCP server config, skills, notebooks, tests. Mar 30 2026 vintage. | 2026-05-02 | Was sitting in `GS/data/apis/` at the repo top level, but it's an external Python package, not a staging API source. Got moved here during the apis/ folder cleanup pass. If integration becomes a real plan, lift selectively rather than restoring the full clone. |
