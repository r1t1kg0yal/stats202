This is a read-only runtime-identification request.

Determine exactly which ECharts dashboard payload is installed and imported by this PRISM runtime. Do not infer from timestamps, Git history, documentation wording, folder names, or version constants alone.

Use a fresh `execute_analysis_script` invocation and run the following Python exactly. Do not modify files, install packages, restart services, or substitute alternate paths.

The candidate labels and hashes are external comparison data. You are not expected to recognize those labels independently.

```python
from pathlib import Path
import hashlib
import importlib
import importlib.util
import inspect
import json
import sys

from prism_meta import REPO_ROOT


EXPECTED_FILES = [
    "__init__.py",
    "config.py",
    "dashboards_time.py",
    "echart_dashboard.py",
    "echart_studio.py",
    "refresh_runner.py",
    "refresh_dashboards.py",
    "rendering.py",
    "dashboards.md",
    "dashboards_hub.md",
    "dashboards/build.md",
    "dashboards/diagnose.md",
    "dashboards/charts.md",
    "dashboards/widgets.md",
    "dashboards/widget_tool.md",
    "dashboards/filters.md",
    "dashboards/recipes.md",
    "dashboards/pipelines.md",
    "dashboards/template_crud.md",
]


CANDIDATE_BUNDLES = {
    "staging/echarts-payload-jul8":
        "8b0e9b5bb8cd9532173fedefbf031c71f6c0db1ec657cb58e7334285cfcace78",

    "staging/echarts-payload-jul9":
        "44402533a518b1971937c4d1d14c335f93cbff78e8958280aedcba5c606e7bb5",

    "staging/echarts-payload-jul11":
        "225cf29d6fc28347222888b32ca7143957b50f1d1324c5b89922d73398daae0b",

    "staging/echarts-payload-jul12":
        "629f30eec47ae37233d6e4fd299886c7226f9b1be52a319a7e72d3e32b42cc5d",

    "staging/echarts-payload":
        "bd77a3bf109623a21b87514d6ac655b7a47aebeccc845c25b8b86bd0b0924625",

    "projects/echarts/echarts-payload":
        "10021e5da4b634dacfb3cbbdaade37ad798ba7f680e4fb7f1204e936534e6ab8",
}


# Independent per-file anchors let us identify a mixed installation even
# when the complete bundle does not match any candidate.
CANDIDATE_ANCHORS = {
    "staging/echarts-payload-jul8": {
        "__init__.py":
            "b42b6c34716bcbee50013a530c5a3dfdeb4d07b1cd24ad9dc5532f1db5a3b560",
        "echart_dashboard.py":
            "aca2134ba28801339f5d03f11d69490db8e35fa43dfcd26e8731384a0b2e8a45",
        "rendering.py":
            "43fbd2237b113586310473b4af91c41054a034fe26f796202cec33acfba87f2d",
        "dashboards.md":
            "9a159b080bd01a618e712d85a3e82f82d131475d9e0928d8583bfa4586b754f8",
        "dashboards_hub.md":
            "5389b5035ee9a7ca21e59c825c0f40975f55cdedad0ea7eb80cc15ea0cae3c84",
    },
    "staging/echarts-payload-jul9": {
        "__init__.py":
            "d0456500ce8d56a1ecba57c58212e2c51c800195fda9b51fae27585976f8e0a2",
        "echart_dashboard.py":
            "c98918f0931503688c85c16cebdbaf5e7d2cccfbcba1e9e5b0a31a50c12e7eec",
        "rendering.py":
            "185468fd2cfe3e48f9f8c2f22bb79f312e2fd0cd2ce5aced832eaa55d24a9df7",
        "dashboards.md":
            "0d4de2c39a1eddd534502d52683b583b53b4f5572ee40c4c940ea1afa05cc20b",
        "dashboards_hub.md":
            "66bfe90068a49c2c1babcd62df780b2fec59f814f3ba03d333e6923228dc7b65",
    },
    "staging/echarts-payload-jul11": {
        "__init__.py":
            "455c6b82a0dd7eedd07e8491e1c2edd8b8c54834574f13a9886e84e7857b49b5",
        "echart_dashboard.py":
            "785b8405cd59ce64060c92c1a702ad23c7b7430ac393fe3b4f62bebdde466036",
        "rendering.py":
            "3231e0a7421da44f75152fd93cdec058a1315a52350f68175f1439ffdc960e94",
        "dashboards.md":
            "7cb78399944cb58c2bbc18514b1814d35cee725f27cf104ffe974f093f8a9449",
        "dashboards_hub.md":
            "9c591ec685b2a6486e54db1f9e8a64b69581a3c430182e1bc09215392ff6075f",
    },
    "staging/echarts-payload-jul12": {
        "__init__.py":
            "8ee41e9a5f27c35b5d90e486fec74b186250b9514997cddb70045d64fe00e136",
        "echart_dashboard.py":
            "e42b071b7b0f83e6999b199a40fe86e1057dda00c74e258b633739c9c2762d46",
        "rendering.py":
            "9a665924d7850cdb21ecd6b0b1971c14f51e384f77c9e2d97aa627d16aa559f7",
        "dashboards.md":
            "1902c94f108bedf22379aeaef7ec216f132f9550f07ee5e904a648817d8c5888",
        "dashboards_hub.md":
            "1fa28e927c307efc5bf008c5692684c95599d113045c0ab563e733bbcd93ce0c",
    },
    "staging/echarts-payload": {
        "__init__.py":
            "b1ab1d677031d28d53147f1e950f21fa3e900dfa92f50eab362051eb34dd1f2f",
        "echart_dashboard.py":
            "25fb129c020b466cc7e929bdebe4d796b173bcf381e1fd1d80d01eac2e7b4ce0",
        "rendering.py":
            "9a665924d7850cdb21ecd6b0b1971c14f51e384f77c9e2d97aa627d16aa559f7",
        "dashboards.md":
            "7d0ddefed2a21d93170e736682f837884777a27b05054454210ee325d8ed23ab",
        "dashboards_hub.md":
            "2bb78049d1cba814bc9464864306f29e8da678914462c846e88ee3f27540d6ea",
    },
    "projects/echarts/echarts-payload": {
        "__init__.py":
            "42c49e49ec77124172d710f42b074685853ce345009659365f1a501d454ae36d",
        "echart_dashboard.py":
            "debefe3d1922b32a0171da44aa0485bc5ce9c17df7f0a8bc541756178c4f70a8",
        "rendering.py":
            "96d06d415a99cd762c2f14d6d00738e861ddd36864a30dd1cd12879c49210b8c",
        "dashboards.md":
            "7d0ddefed2a21d93170e736682f837884777a27b05054454210ee325d8ed23ab",
        "dashboards_hub.md":
            "6e375f00840a5c1e90929d765a150f0e1911fe01c644d13435c016e916b0cd78",
    },
}


FEATURE_NAMES = [
    "run_pull",
    "build_dashboard",
    "refresh_dashboard",
    "launch_clean_refresh",
    "compile_dashboard",
    "render_dashboard",
    "validate_manifest",
    "prepare_manifest",
    "manifest_template",
    "populate_template",
    "df_to_source",
    "match_targets",
    "load_manifest",
    "save_manifest",
    "chart_data_diagnostics",
    "audit_dashboard_layout",
    "_audit_dashboard_layout",
    "apply_manifest_operations",
    "apply_persisted_script_operations",
    "synchronize_refresh_frequency",
    "sync_refresh_frequency",
    "inspect_dashboard",
    "list_dashboard_versions",
    "restore_dashboard_version",
    "Dashboard",
    "Tab",
    "ChartRef",
    "KPIRef",
    "TableRef",
    "MarkdownRef",
    "NoteRef",
    "DividerRef",
    "GlobalFilter",
    "Link",
    "Manifest",
    "DashboardResult",
    "Diagnostic",
    "RefreshAttachmentError",
    "DashboardVersionRestoreError",
    "utcnow",
    "parse_iso",
    "format_iso",
    "parse_freq",
    "freq_delta",
    "is_stale",
    "UTC",
    "ET",
    "REFRESH_FREQ_DELTAS",
]


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def fingerprint_file(path):
    path = Path(path).resolve()
    if not path.is_file():
        return {
            "resolved_path": str(path),
            "present": False,
            "sha256": None,
            "bytes": None,
            "lines": None,
        }

    data = path.read_bytes()
    return {
        "resolved_path": str(path),
        "present": True,
        "sha256": sha256_bytes(data),
        "bytes": len(data),
        "lines": len(data.splitlines()),
    }


repo_root = Path(REPO_ROOT).resolve()
package_root = repo_root / "prism-core" / "dashboards"
context_root = (
    repo_root
    / "prism-core"
    / "context"
    / "modules"
    / "static"
    / "tools"
)

logical_paths = {}
for rel in EXPECTED_FILES:
    if rel == "refresh_dashboards.py":
        logical_paths[rel] = repo_root / "jobs" / "hourly" / rel
    elif rel.endswith(".py"):
        logical_paths[rel] = package_root / rel
    else:
        logical_paths[rel] = context_root / rel


records = []
record_by_rel = {}
bundle = hashlib.sha256()

for rel in sorted(EXPECTED_FILES):
    path = logical_paths[rel].resolve()

    bundle.update(rel.encode("utf-8"))
    bundle.update(b"\0")

    if path.is_file():
        data = path.read_bytes()
        record = {
            "logical_path": rel,
            "resolved_path": str(path),
            "present": True,
            "sha256": sha256_bytes(data),
            "bytes": len(data),
            "lines": len(data.splitlines()),
        }

        bundle.update(b"FILE\0")
        bundle.update(str(len(data)).encode("ascii"))
        bundle.update(b"\0")
        bundle.update(data)
    else:
        record = {
            "logical_path": rel,
            "resolved_path": str(path),
            "present": False,
            "sha256": None,
            "bytes": None,
            "lines": None,
        }
        bundle.update(b"MISSING")

    bundle.update(b"\0")
    records.append(record)
    record_by_rel[rel] = record


bundle_sha256 = bundle.hexdigest()
bundle_matches = [
    label
    for label, expected_hash in CANDIDATE_BUNDLES.items()
    if bundle_sha256 == expected_hash
]


anchor_analysis = {}
for rel in [
    "__init__.py",
    "echart_dashboard.py",
    "rendering.py",
    "dashboards.md",
    "dashboards_hub.md",
]:
    actual_hash = record_by_rel[rel]["sha256"]
    anchor_analysis[rel] = {
        "actual_sha256": actual_hash,
        "candidate_matches": [
            label
            for label, hashes in CANDIDATE_ANCHORS.items()
            if hashes.get(rel) == actual_hash
        ] if actual_hash else [],
    }


preloaded_before_probe = {
    name: name in sys.modules
    for name in [
        "dashboards",
        "dashboards.echart_dashboard",
        "dashboards.rendering",
    ]
}


resolution = {
    "repo_root": str(repo_root),
    "expected_package_root": str(package_root.resolve()),
    "expected_init_path": str(logical_paths["__init__.py"].resolve()),
    "expected_engine_path": str(
        logical_paths["echart_dashboard.py"].resolve()
    ),
    "python_executable": sys.executable,
    "sys_path": list(sys.path),
    "preloaded_before_probe": preloaded_before_probe,
    "find_spec_error": None,
    "dashboards_spec_origin": None,
    "dashboards_search_locations": [],
    "spec_origin_matches_expected_init": False,
}

try:
    spec = importlib.util.find_spec("dashboards")
    if spec is not None:
        if spec.origin:
            resolution["dashboards_spec_origin"] = str(
                Path(spec.origin).resolve()
            )
        if spec.submodule_search_locations:
            resolution["dashboards_search_locations"] = [
                str(Path(path).resolve())
                for path in spec.submodule_search_locations
            ]
except Exception as exc:
    resolution["find_spec_error"] = (
        f"{type(exc).__name__}: {exc}"
    )

resolution["spec_origin_matches_expected_init"] = (
    resolution["dashboards_spec_origin"]
    == resolution["expected_init_path"]
)


runtime = {
    "import_ok": False,
    "import_error": None,
    "package_version": None,
    "engine_version": None,
    "package_file": None,
    "engine_file": None,
    "rendering_file": None,
    "package_file_sha256": None,
    "engine_file_sha256": None,
    "rendering_file_sha256": None,
    "package_file_matches_hashed_init": False,
    "engine_file_matches_hashed_engine": False,
    "package_all": None,
    "symbols": {},
}


try:
    dashboards = importlib.import_module("dashboards")
    engine = importlib.import_module("dashboards.echart_dashboard")
    rendering = importlib.import_module("dashboards.rendering")

    runtime["import_ok"] = True
    runtime["package_version"] = getattr(
        dashboards, "__version__", None
    )
    runtime["engine_version"] = getattr(
        engine, "ENGINE_VERSION", None
    )

    package_file = Path(dashboards.__file__).resolve()
    engine_file = Path(engine.__file__).resolve()
    rendering_file = Path(rendering.__file__).resolve()

    runtime["package_file"] = str(package_file)
    runtime["engine_file"] = str(engine_file)
    runtime["rendering_file"] = str(rendering_file)

    runtime["package_file_sha256"] = (
        fingerprint_file(package_file)["sha256"]
    )
    runtime["engine_file_sha256"] = (
        fingerprint_file(engine_file)["sha256"]
    )
    runtime["rendering_file_sha256"] = (
        fingerprint_file(rendering_file)["sha256"]
    )

    runtime["package_file_matches_hashed_init"] = (
        runtime["package_file"] == resolution["expected_init_path"]
        and runtime["package_file_sha256"]
        == record_by_rel["__init__.py"]["sha256"]
    )

    runtime["engine_file_matches_hashed_engine"] = (
        runtime["engine_file"] == resolution["expected_engine_path"]
        and runtime["engine_file_sha256"]
        == record_by_rel["echart_dashboard.py"]["sha256"]
    )

    package_all = getattr(dashboards, "__all__", None)
    runtime["package_all"] = (
        list(package_all)
        if isinstance(package_all, (list, tuple))
        else None
    )

    for name in FEATURE_NAMES:
        present = hasattr(dashboards, name)
        item = {
            "present": present,
            "callable": False,
            "signature": None,
            "defined_in_module": None,
            "source_file": None,
        }

        if present:
            obj = getattr(dashboards, name)
            item["callable"] = callable(obj)
            item["defined_in_module"] = getattr(
                obj, "__module__", None
            )

            try:
                source_file = inspect.getsourcefile(obj)
                if source_file:
                    item["source_file"] = str(
                        Path(source_file).resolve()
                    )
            except Exception:
                pass

            if callable(obj):
                try:
                    item["signature"] = str(
                        inspect.signature(obj)
                    )
                except (TypeError, ValueError) as exc:
                    item["signature"] = (
                        f"UNAVAILABLE: {type(exc).__name__}: {exc}"
                    )

        runtime["symbols"][name] = item

except Exception as exc:
    runtime["import_error"] = (
        f"{type(exc).__name__}: {exc}"
    )


if len(bundle_matches) == 1:
    classification_status = "EXACT_LOCAL_BUNDLE_MATCH"
elif len(bundle_matches) > 1:
    classification_status = "AMBIGUOUS_BUNDLE_HASH_MATCH"
elif len(
    anchor_analysis["echart_dashboard.py"]["candidate_matches"]
) == 1:
    classification_status = (
        "MIXED_OR_MODIFIED_BUNDLE_WITH_KNOWN_ENGINE_LINEAGE"
    )
else:
    classification_status = "NO_RECOGNIZED_BUNDLE_OR_ENGINE_MATCH"


present_records = [
    record for record in records if record["present"]
]
missing_paths = [
    record["logical_path"]
    for record in records
    if not record["present"]
]


result = {
    "classification": {
        "status": classification_status,
        "exact_bundle_match": (
            bundle_matches[0]
            if len(bundle_matches) == 1
            else None
        ),
        "all_bundle_matches": bundle_matches,
        "bundle_sha256": bundle_sha256,
        "engine_lineage_matches": anchor_analysis[
            "echart_dashboard.py"
        ]["candidate_matches"],
        "interpretation_rule": (
            "Only an exact 19-file bundle digest permits an overall "
            "candidate label. Anchor matches identify individual layers "
            "only. Do not choose a nearest candidate."
        ),
    },
    "inventory": {
        "expected_production_files": len(EXPECTED_FILES),
        "present_production_files": len(present_records),
        "missing_logical_paths": missing_paths,
        "total_present_bytes": sum(
            record["bytes"] for record in present_records
        ),
        "test_prompts_included": False,
        "pycache_included": False,
    },
    "anchor_analysis": anchor_analysis,
    "import_resolution": resolution,
    "runtime": runtime,
    "files": records,
}

print(json.dumps(result, indent=2, sort_keys=True))
```

Return the complete JSON stdout verbatim in one fenced JSON block. Do not omit or summarize any paths, hashes, byte counts, line counts, signatures, symbols, or import-resolution fields.

After the JSON, provide exactly one of these conclusions:

1. If `status` is `EXACT_LOCAL_BUNDLE_MATCH` and the imported package and engine paths match the hashed files:

   `PRISM has an exact installed and imported match for: <exact_bundle_match>.`

2. If the full bundle does not match but one or more anchors match:

   `PRISM has a mixed or modified installation. Its component-level matches are: <list every anchor and its candidate_matches>. Do not assign one overall snapshot label.`

3. If neither the bundle nor engine matches:

   `PRISM does not exactly match any supplied candidate. It is a different, newer, older, incomplete, or modified payload.`

Explicitly call out any of the following:

- Missing production files
- Failed imports
- `dashboards` resolving outside the expected `prism-core/dashboards` path
- Imported file hashes differing from the filesystem hashes
- More than one candidate matching an anchor
- A preloaded module despite this being requested as a fresh execution

Do not perform a nearest-match guess.