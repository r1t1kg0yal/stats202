"""Optional node+vega render check: runs a Vega-Lite spec through the real
vega runtime to catch expression errors static compilation misses."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


_NODE_RENDER_SCRIPT = r"""
const vega = require('vega');
const vl = require('vega-lite');
const fs = require('fs');

async function main() {
  const specStr = fs.readFileSync(0, 'utf8');
  const spec = JSON.parse(specStr);
  try {
    const {spec: vegaSpec} = vl.compile(spec);
    const runtime = vega.parse(vegaSpec);
    const view = new vega.View(runtime, {renderer: 'none'});
    await view.runAsync();
    // Also exercise tooltip-like eval paths
    await view.toSVG();
    console.log(JSON.stringify({ok: true}));
  } catch (e) {
    console.log(JSON.stringify({
      ok: false,
      error: e.message,
      stack: e.stack ? e.stack.split('\n').slice(0, 3).join(' | ') : null,
    }));
    process.exit(0);
  }
}
main().catch(e => {
  console.log(JSON.stringify({ok: false, error: String(e)}));
  process.exit(0);
});
"""


def _find_node_modules_with_vega() -> Optional[str]:
    """Return the path to a node_modules directory that contains vega and
    vega-lite, or None if not found anywhere standard.

    Checks (in order):
        1. CWD/node_modules
        2. ancestors of CWD
        3. /tmp/node_modules (test/dev convention)
        4. ~/.node_modules
    """
    candidates: List[Path] = []
    here = Path.cwd()
    candidates.append(here)
    candidates.extend(here.parents)
    candidates.append(Path("/tmp"))
    candidates.append(Path.home() / ".node_modules")
    for d in candidates:
        nm = d / "node_modules"
        if (nm / "vega").exists() and (nm / "vega-lite").exists():
            return str(nm)
    return None


def _try_node_render_check(spec_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Run the spec through node+vega+vega-lite (if available) to catch
    runtime render errors that static compilation misses.

    Returns:
        {"ok": True} on success
        {"ok": False, "error": "..."} on render error
        None if node or the packages aren't available
    """
    import os
    import shutil
    import subprocess
    import tempfile

    if not shutil.which("node"):
        return None

    node_modules = _find_node_modules_with_vega()
    if node_modules is None:
        return None

    # Write the script ADJACENT to node_modules so node can resolve `vega`
    # via its usual lookup rules. Using tempfile's default would put the
    # script in /var/folders/... where vega isn't installed.
    script_dir = Path(node_modules).parent
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                     dir=str(script_dir)) as f:
        f.write(_NODE_RENDER_SCRIPT)
        script_path = f.name

    env = dict(os.environ)
    # Belt + suspenders: also set NODE_PATH in case the script was moved.
    existing_node_path = env.get("NODE_PATH", "")
    env["NODE_PATH"] = (node_modules + (os.pathsep + existing_node_path)
                        if existing_node_path else node_modules)

    try:
        result = subprocess.run(
            ["node", script_path],
            input=json.dumps(spec_dict, default=str),
            capture_output=True, text=True, timeout=30,
            cwd=str(script_dir),
            env=env,
        )
        output = result.stdout.strip()
        if not output:
            return {"ok": False,
                    "error": f"node exit {result.returncode}: {result.stderr[:300]}"}
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {"ok": False,
                    "error": f"unparseable node output: {output[:200]}"}
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass
