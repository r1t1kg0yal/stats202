#!/usr/bin/env python3
"""
BIS Data Ontology Scraper
=========================
Scrapes the full BIS SDMX API to build a comprehensive ontology of all
BIS statistical datasets, their dimensions, codelists, codes, and attributes.

Outputs a structured JSON ontology file similar to the FRED ontology format.

BIS API: https://stats.bis.org/api/v2/
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' library required. Install with: pip install requests")
    sys.exit(1)

BASE_URL = "https://stats.bis.org/api/v2"
OUTPUT_DIR = Path(__file__).parent / "data" / "ontology"
DEFAULT_OUTPUT = OUTPUT_DIR / "bis_ontology.json"

HEADERS = {
    "Accept": "application/vnd.sdmx.structure+json;version=1.0.0",
    "User-Agent": "BIS-Ontology-Scraper/1.0",
}

DATA_HEADERS = {
    "Accept": "application/vnd.sdmx.data+json;version=1.0.0",
    "User-Agent": "BIS-Ontology-Scraper/1.0",
}


def api_get(endpoint, params=None, max_retries=3):
    url = f"{BASE_URL}{endpoint}"
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=60)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                wait = 2 ** (attempt + 1)
                print(f"    Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            else:
                print(f"    HTTP {resp.status_code} for {url}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return None
        except requests.exceptions.Timeout:
            print(f"    Timeout for {url}, retry {attempt+1}/{max_retries}")
            time.sleep(3)
        except Exception as e:
            print(f"    Error fetching {url}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                return None
    return None


def fetch_all_dataflows():
    print("Fetching all BIS dataflows...")
    data = api_get("/structure/dataflow/BIS", params={"format": "sdmx-json"})
    if not data:
        print("FATAL: Could not fetch dataflows")
        sys.exit(1)
    flows = data["data"]["dataflows"]
    print(f"  Found {len(flows)} dataflows")
    return flows


def parse_codelist(cl_raw):
    codelist = {
        "id": cl_raw["id"],
        "name": cl_raw.get("name", ""),
        "description": cl_raw.get("description", ""),
        "codes": {},
    }
    for code in cl_raw.get("codes", []):
        entry = {
            "id": code["id"],
            "name": code.get("name", ""),
        }
        if "description" in code:
            entry["description"] = code["description"]
        if "parent" in code:
            entry["parent"] = code["parent"]
        codelist["codes"][code["id"]] = entry
    return codelist


def extract_codelist_id_from_urn(urn):
    if not urn:
        return None
    try:
        part = urn.split("Codelist=")[1]
        cl_id = part.split(":")[1].split("(")[0]
        return cl_id
    except (IndexError, KeyError):
        return None


def parse_dimension(dim_raw, codelists_by_id):
    codelist_urn = dim_raw.get("localRepresentation", {}).get("enumeration", "")
    cl_id = extract_codelist_id_from_urn(codelist_urn)

    concept_urn = dim_raw.get("conceptIdentity", "")
    concept_name = concept_urn.split(".")[-1] if concept_urn else ""

    dim = {
        "id": dim_raw["id"],
        "position": dim_raw.get("position"),
        "concept": concept_name,
        "codelist_id": cl_id,
    }

    if cl_id and cl_id in codelists_by_id:
        cl = codelists_by_id[cl_id]
        dim["codelist_name"] = cl["name"]
        dim["num_codes"] = len(cl["codes"])
    return dim


def parse_attribute(attr_raw, codelists_by_id):
    codelist_urn = attr_raw.get("localRepresentation", {}).get("enumeration", "")
    cl_id = extract_codelist_id_from_urn(codelist_urn)

    concept_urn = attr_raw.get("conceptIdentity", "")
    concept_name = concept_urn.split(".")[-1] if concept_urn else ""

    attr = {
        "id": attr_raw["id"],
        "concept": concept_name,
        "codelist_id": cl_id,
        "assignment_status": attr_raw.get("assignmentStatus", ""),
        "relationship_type": attr_raw.get("attributeRelationship", {}).get("primaryMeasure")
        or (
            "dimensions"
            if attr_raw.get("attributeRelationship", {}).get("dimensions")
            else "observation"
            if attr_raw.get("attributeRelationship", {}).get("primaryMeasure")
            else "dataset"
        ),
    }
    if cl_id and cl_id in codelists_by_id:
        attr["codelist_name"] = codelists_by_id[cl_id]["name"]
        attr["num_codes"] = len(codelists_by_id[cl_id]["codes"])
    return attr


def fetch_and_parse_dsd(dsd_urn, flow_id):
    dsd_id_part = dsd_urn.split("DataStructure=BIS:")[1] if "DataStructure=BIS:" in dsd_urn else None
    if not dsd_id_part:
        print(f"  Could not parse DSD URN: {dsd_urn}")
        return None

    dsd_id = dsd_id_part.split("(")[0]
    version = dsd_id_part.split("(")[1].rstrip(")") if "(" in dsd_id_part else "1.0"

    print(f"  Fetching DSD: {dsd_id} v{version} (for {flow_id})...")
    data = api_get(
        f"/structure/datastructure/BIS/{dsd_id}/{version}",
        params={"format": "sdmx-json", "references": "children"},
    )
    if not data:
        print(f"    Failed to fetch DSD {dsd_id}")
        return None

    codelists_raw = data["data"].get("codelists", [])
    codelists_by_id = {}
    codelists_parsed = {}
    for cl_raw in codelists_raw:
        parsed = parse_codelist(cl_raw)
        codelists_by_id[cl_raw["id"]] = parsed
        codelists_parsed[cl_raw["id"]] = parsed

    ds = data["data"]["dataStructures"][0]
    components = ds["dataStructureComponents"]

    dims_raw = components.get("dimensionList", {}).get("dimensions", [])
    dimensions = []
    for d in sorted(dims_raw, key=lambda x: x.get("position", 0)):
        dimensions.append(parse_dimension(d, codelists_by_id))

    time_dim = components.get("dimensionList", {}).get("timeDimensions", [])
    for td in time_dim:
        dimensions.append({
            "id": td["id"],
            "position": td.get("position", len(dimensions) + 1),
            "concept": "TIME_PERIOD",
            "codelist_id": None,
            "is_time_dimension": True,
        })

    attrs_raw = components.get("attributeList", {}).get("attributes", [])
    attributes = []
    for a in attrs_raw:
        attributes.append(parse_attribute(a, codelists_by_id))

    concepts_raw = data["data"].get("conceptSchemes", [])
    concept_schemes = {}
    for cs in concepts_raw:
        scheme = {
            "id": cs["id"],
            "name": cs.get("name", ""),
            "concepts": {},
        }
        for concept in cs.get("concepts", []):
            scheme["concepts"][concept["id"]] = {
                "id": concept["id"],
                "name": concept.get("name", ""),
                "description": concept.get("description", ""),
            }
        concept_schemes[cs["id"]] = scheme

    result = {
        "dsd_id": dsd_id,
        "version": version,
        "name": ds.get("name", ""),
        "dimensions": dimensions,
        "attributes": attributes,
        "codelists": codelists_parsed,
        "concept_schemes": concept_schemes,
        "num_dimensions": len([d for d in dimensions if not d.get("is_time_dimension")]),
        "num_attributes": len(attributes),
        "num_codelists": len(codelists_parsed),
        "total_codes": sum(len(cl["codes"]) for cl in codelists_parsed.values()),
    }
    return result


def build_dataflow_entry(flow_raw, dsd_data):
    entry = {
        "id": flow_raw["id"],
        "name": flow_raw.get("name", ""),
        "description": flow_raw.get("description", ""),
        "dsd_ref": flow_raw.get("structure", ""),
    }
    if dsd_data:
        entry["structure"] = dsd_data
    return entry


def compute_stats(ontology):
    dataflows = ontology["dataflows"]
    total_dimensions = 0
    total_attributes = 0
    all_codelist_ids = set()
    total_codes = 0
    unique_dsds = set()
    domains = []

    for flow_id, flow in dataflows.items():
        domains.append(flow["name"])
        struct = flow.get("structure")
        if struct:
            unique_dsds.add(struct["dsd_id"])
            total_dimensions += struct["num_dimensions"]
            total_attributes += struct["num_attributes"]
            for cl_id, cl in struct["codelists"].items():
                if cl_id not in all_codelist_ids:
                    total_codes += len(cl["codes"])
                    all_codelist_ids.add(cl_id)

    return {
        "total_dataflows": len(dataflows),
        "unique_dsds": len(unique_dsds),
        "total_dimensions_across_flows": total_dimensions,
        "total_attributes_across_flows": total_attributes,
        "unique_codelists": len(all_codelist_ids),
        "total_unique_codes": total_codes,
        "domains": sorted(domains),
    }


def scrape_full_ontology(output_path=None, skip_existing=False):
    output_path = Path(output_path) if output_path else DEFAULT_OUTPUT
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if skip_existing and output_path.exists():
        print(f"Output already exists at {output_path}, skipping (--skip-existing)")
        return

    flows = fetch_all_dataflows()

    seen_dsds = {}
    ontology = {
        "version": "1.0",
        "source": "Bank for International Settlements (BIS)",
        "api_base": BASE_URL,
        "generated": datetime.now(timezone.utc).isoformat(),
        "stats": {},
        "dataflows": {},
    }

    total = len(flows)
    for i, flow in enumerate(flows, 1):
        flow_id = flow["id"]
        flow_name = flow.get("name", "")
        dsd_urn = flow.get("structure", "")

        print(f"\n[{i}/{total}] {flow_id}: {flow_name}")

        dsd_key = dsd_urn.split("DataStructure=BIS:")[-1] if "DataStructure=BIS:" in dsd_urn else dsd_urn
        if dsd_key in seen_dsds:
            print(f"  DSD already fetched (shared with {seen_dsds[dsd_key]}), reusing...")
            dsd_data = ontology["dataflows"][seen_dsds[dsd_key]]["structure"]
        else:
            dsd_data = fetch_and_parse_dsd(dsd_urn, flow_id)
            seen_dsds[dsd_key] = flow_id
            time.sleep(0.5)

        ontology["dataflows"][flow_id] = build_dataflow_entry(flow, dsd_data)

    ontology["stats"] = compute_stats(ontology)

    print(f"\nWriting ontology to {output_path}...")
    with open(output_path, "w") as f:
        json.dump(ontology, f, indent=2, ensure_ascii=False)

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"Done. Output: {output_path} ({size_mb:.1f} MB)")
    print(f"\nStats:")
    for k, v in ontology["stats"].items():
        if k != "domains":
            print(f"  {k}: {v}")
    print(f"  domains: {len(ontology['stats']['domains'])} datasets")


def explore_ontology(ontology_path=None):
    ontology_path = Path(ontology_path) if ontology_path else DEFAULT_OUTPUT
    if not ontology_path.exists():
        print(f"Ontology file not found at {ontology_path}")
        print("Run the scraper first: python bis_ontology_scraper.py scrape")
        return

    with open(ontology_path) as f:
        ont = json.load(f)

    while True:
        print("\n" + "=" * 60)
        print("BIS Data Ontology Explorer")
        print("=" * 60)
        print(f"Generated: {ont['generated']}")
        stats = ont["stats"]
        print(f"Dataflows: {stats['total_dataflows']}")
        print(f"Unique DSDs: {stats['unique_dsds']}")
        print(f"Unique codelists: {stats['unique_codelists']}")
        print(f"Total unique codes: {stats['total_unique_codes']}")
        print()
        print("Commands:")
        print("  1) List all dataflows")
        print("  2) Inspect a dataflow (dimensions, codelists)")
        print("  3) Search codelists by keyword")
        print("  4) Inspect a specific codelist")
        print("  5) Show dimensional cross-reference (which dims appear where)")
        print("  6) Export flat codelist summary")
        print("  q) Quit")
        print()

        choice = input("Select: ").strip().lower()
        if choice == "q":
            break
        elif choice == "1":
            _explore_list_flows(ont)
        elif choice == "2":
            _explore_inspect_flow(ont)
        elif choice == "3":
            _explore_search_codelists(ont)
        elif choice == "4":
            _explore_inspect_codelist(ont)
        elif choice == "5":
            _explore_dimension_xref(ont)
        elif choice == "6":
            _explore_export_flat(ont)
        else:
            print("Invalid choice.")


def _explore_list_flows(ont):
    print("\nAll BIS Dataflows:")
    print("-" * 80)
    for fid, flow in sorted(ont["dataflows"].items()):
        struct = flow.get("structure", {})
        ndim = struct.get("num_dimensions", "?")
        ncl = struct.get("num_codelists", "?")
        print(f"  {fid:<25s} {flow['name']:<45s} dims={ndim} codelists={ncl}")


def _explore_inspect_flow(ont):
    flow_ids = sorted(ont["dataflows"].keys())
    for i, fid in enumerate(flow_ids, 1):
        print(f"  {i:2d}) {fid}: {ont['dataflows'][fid]['name']}")
    sel = input("\nEnter number or flow ID: ").strip()
    try:
        idx = int(sel) - 1
        flow_id = flow_ids[idx]
    except (ValueError, IndexError):
        flow_id = sel

    if flow_id not in ont["dataflows"]:
        print(f"Unknown flow: {flow_id}")
        return

    flow = ont["dataflows"][flow_id]
    struct = flow.get("structure")
    print(f"\n{'=' * 60}")
    print(f"Dataflow: {flow_id}")
    print(f"Name: {flow['name']}")
    if flow.get("description"):
        print(f"Description: {flow['description']}")
    if not struct:
        print("  (No structure data available)")
        return

    print(f"\nDSD: {struct['dsd_id']} v{struct['version']}")
    print(f"Dimensions: {struct['num_dimensions']}  |  Attributes: {struct['num_attributes']}  |  Codelists: {struct['num_codelists']}")
    print(f"\nDIMENSIONS:")
    for d in struct["dimensions"]:
        if d.get("is_time_dimension"):
            print(f"  [{d['position']:2d}] {d['id']:<25s} (time dimension)")
        else:
            ncodes = d.get("num_codes", "?")
            cl_name = d.get("codelist_name", "")
            print(f"  [{d['position']:2d}] {d['id']:<25s} codelist={d.get('codelist_id',''):<25s} ({ncodes} codes) {cl_name}")

    print(f"\nATTRIBUTES:")
    for a in struct["attributes"]:
        cl_name = a.get("codelist_name", "")
        print(f"  {a['id']:<20s} codelist={a.get('codelist_id',''):<25s} {cl_name}")


def _explore_search_codelists(ont):
    keyword = input("Search keyword: ").strip().lower()
    if not keyword:
        return

    seen = set()
    for fid, flow in ont["dataflows"].items():
        struct = flow.get("structure")
        if not struct:
            continue
        for cl_id, cl in struct.get("codelists", {}).items():
            if cl_id in seen:
                continue
            match = keyword in cl_id.lower() or keyword in cl.get("name", "").lower()
            if not match:
                for code_id, code in cl.get("codes", {}).items():
                    if keyword in code_id.lower() or keyword in code.get("name", "").lower():
                        match = True
                        break
            if match:
                seen.add(cl_id)
                print(f"  {cl_id:<30s} {cl.get('name',''):<35s} ({len(cl.get('codes',{}))} codes)  [in {fid}]")


def _explore_inspect_codelist(ont):
    cl_target = input("Codelist ID (e.g. CL_L_INSTR): ").strip()
    if not cl_target:
        return

    for fid, flow in ont["dataflows"].items():
        struct = flow.get("structure")
        if not struct:
            continue
        if cl_target in struct.get("codelists", {}):
            cl = struct["codelists"][cl_target]
            print(f"\nCodelist: {cl['id']}")
            print(f"Name: {cl.get('name', '')}")
            if cl.get("description"):
                print(f"Description: {cl['description']}")
            print(f"Codes ({len(cl['codes'])}):")
            for code_id, code in sorted(cl["codes"].items()):
                parent_str = f"  [parent: {code['parent']}]" if code.get("parent") else ""
                print(f"  {code_id:<12s} {code.get('name','')}{parent_str}")
                if code.get("description"):
                    desc = code["description"][:120]
                    print(f"               {desc}{'...' if len(code.get('description',''))>120 else ''}")
            return
    print(f"Codelist {cl_target} not found in any dataflow.")


def _explore_dimension_xref(ont):
    dim_map = {}
    for fid, flow in ont["dataflows"].items():
        struct = flow.get("structure")
        if not struct:
            continue
        for d in struct.get("dimensions", []):
            did = d["id"]
            if did not in dim_map:
                dim_map[did] = {"codelist": d.get("codelist_id", ""), "flows": []}
            dim_map[did]["flows"].append(fid)

    print(f"\nDimension Cross-Reference ({len(dim_map)} unique dimensions):")
    print("-" * 90)
    for did in sorted(dim_map.keys()):
        info = dim_map[did]
        flows_str = ", ".join(info["flows"][:5])
        if len(info["flows"]) > 5:
            flows_str += f" (+{len(info['flows'])-5} more)"
        print(f"  {did:<25s} codelist={info['codelist']:<25s} used in {len(info['flows'])} flows: {flows_str}")


def _explore_export_flat(ont):
    out_path = OUTPUT_DIR / "bis_codelist_summary.json"
    all_codelists = {}
    for fid, flow in ont["dataflows"].items():
        struct = flow.get("structure")
        if not struct:
            continue
        for cl_id, cl in struct.get("codelists", {}).items():
            if cl_id not in all_codelists:
                all_codelists[cl_id] = cl

    with open(out_path, "w") as f:
        json.dump(
            {"total_codelists": len(all_codelists), "codelists": all_codelists},
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"Exported {len(all_codelists)} unique codelists to {out_path}")


LBS_DEEP_OUTPUT = OUTPUT_DIR / "lbs_deep_index.json"

REPORTING_COUNTRIES_ACTUAL = [
    "AT", "AU", "BE", "BH", "BM", "BR", "BS", "CA", "CH", "CL", "CN", "CW",
    "CY", "DE", "DK", "ES", "FI", "FR", "GB", "GG", "GR", "HK", "ID", "IE",
    "IM", "IN", "IT", "JE", "JP", "KR", "KY", "LU", "MO", "MX", "MY", "NL",
    "NO", "PA", "PH", "PT", "RU", "SA", "SE", "SG", "TR", "TW", "US", "ZA",
]

LBS_COUNTRY_NAMES = {
    "AT": "Austria", "AU": "Australia", "BE": "Belgium", "BH": "Bahrain",
    "BM": "Bermuda", "BR": "Brazil", "BS": "Bahamas", "CA": "Canada",
    "CH": "Switzerland", "CL": "Chile", "CN": "China", "CW": "Curacao",
    "CY": "Cyprus", "DE": "Germany", "DK": "Denmark", "ES": "Spain",
    "FI": "Finland", "FR": "France", "GB": "United Kingdom", "GG": "Guernsey",
    "GR": "Greece", "HK": "Hong Kong SAR", "ID": "Indonesia", "IE": "Ireland",
    "IM": "Isle of Man", "IN": "India", "IT": "Italy", "JE": "Jersey",
    "JP": "Japan", "KR": "Korea", "KY": "Cayman Islands", "LU": "Luxembourg",
    "MO": "Macao SAR", "MX": "Mexico", "MY": "Malaysia", "NL": "Netherlands",
    "NO": "Norway", "PA": "Panama", "PH": "Philippines", "PT": "Portugal",
    "RU": "Russia", "SA": "Saudi Arabia", "SE": "Sweden", "SG": "Singapore",
    "TR": "Turkey", "TW": "Chinese Taipei", "US": "United States", "ZA": "South Africa",
    "5A": "All reporting countries", "5C": "Euro area",
}


def availability_query(key_filter, max_retries=3):
    url = f"{BASE_URL}/availability/dataflow/BIS/WS_LBS_D_PUB/1.0/{key_filter}"
    params = {"mode": "available", "references": "none", "format": "sdmx-json"}
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                constraint = data["data"]["contentConstraints"][0]
                annots = {a["id"]: a["title"] for a in constraint.get("annotations", [])}
                series_count = int(annots.get("series_count", 0))
                kv_map = {}
                for kv in constraint.get("cubeRegions", [{}])[0].get("keyValues", []):
                    kv_map[kv["id"]] = kv["values"]
                return {"series_count": series_count, "dimensions": kv_map}
            elif resp.status_code == 404:
                return {"series_count": 0, "dimensions": {}}
            elif resp.status_code == 429:
                time.sleep(2 ** (attempt + 1))
                continue
            else:
                if attempt < max_retries - 1:
                    time.sleep(1)
                else:
                    return None
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                print(f"    Error: {e}")
                return None
    return None


def deep_index_lbs(output_path=None):
    output_path = Path(output_path) if output_path else LBS_DEEP_OUTPUT
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ontology_path = DEFAULT_OUTPUT
    cl_lookups = {}
    dim_to_codelist = {}
    if ontology_path.exists():
        with open(ontology_path) as f:
            ont = json.load(f)
        lbs_struct = ont.get("dataflows", {}).get("WS_LBS_D_PUB", {}).get("structure", {})
        for cl_id, cl in lbs_struct.get("codelists", {}).items():
            cl_lookups[cl_id] = {code_id: code.get("name", code_id) for code_id, code in cl.get("codes", {}).items()}
        for dim in lbs_struct.get("dimensions", []):
            if dim.get("codelist_id"):
                dim_to_codelist[dim["id"]] = dim["codelist_id"]

    def resolve(code, dim_id=None):
        if dim_id and dim_id in dim_to_codelist:
            cl_id = dim_to_codelist[dim_id]
            if cl_id in cl_lookups and code in cl_lookups[cl_id]:
                return cl_lookups[cl_id][code]
        for cl_id, codes in cl_lookups.items():
            if code in codes:
                return codes[code]
        return code

    def resolve_dim(codes, dim_id):
        return {c: resolve(c, dim_id) for c in codes}

    print("=" * 70)
    print("BIS Locational Banking Statistics - Deep Index Builder")
    print("=" * 70)

    # Key format: FREQ.L_MEASURE.L_POSITION.L_INSTR.L_DENOM.L_CURR_TYPE.L_PARENT_CTY.L_REP_BANK_TYPE.L_REP_CTY.L_CP_SECTOR.L_CP_COUNTRY.L_POS_TYPE

    print("\n[1/4] Querying global LBS availability...")
    global_avail = availability_query("Q.S....A.5J.A....") 
    if not global_avail or global_avail["series_count"] == 0:
        print("FATAL: Could not query global availability")
        return

    print(f"  Total LBS series (stocks, all banks, all parent=5J): {global_avail['series_count']}")
    rep_countries = global_avail["dimensions"].get("L_REP_CTY", [])
    cp_countries = global_avail["dimensions"].get("L_CP_COUNTRY", [])
    instruments = global_avail["dimensions"].get("L_INSTR", [])
    positions = global_avail["dimensions"].get("L_POSITION", [])
    sectors = global_avail["dimensions"].get("L_CP_SECTOR", [])
    currencies = global_avail["dimensions"].get("L_DENOM", [])

    iso_rep = [c for c in rep_countries if len(c) == 2]
    iso_cp = [c for c in cp_countries if len(c) == 2 and not c.startswith(("1", "2", "3", "4", "5", "6", "7", "8", "9"))]

    print(f"  Reporting countries: {len(iso_rep)}")
    print(f"  Counterparty countries (ISO): {len(iso_cp)}")
    instr_display = [f"{i}={resolve(i, 'L_INSTR')}" for i in instruments]
    pos_display = [f"{p}={resolve(p, 'L_POSITION')}" for p in positions]
    print(f"  Instruments available: {instr_display}")
    print(f"  Positions: {pos_display}")
    print(f"  Sectors: {len(sectors)}")
    print(f"  Currencies: {currencies}")

    index = {
        "version": "1.0",
        "source": "BIS Locational Banking Statistics (LBS)",
        "dataflow": "WS_LBS_D_PUB",
        "generated": datetime.now(timezone.utc).isoformat(),
        "global_summary": {
            "total_cross_border_series": global_avail["series_count"],
            "reporting_countries": len(iso_rep),
            "counterparty_countries_iso": len(iso_cp),
            "instruments": resolve_dim(instruments, "L_INSTR"),
            "positions": resolve_dim(positions, "L_POSITION"),
            "sectors": resolve_dim(sectors, "L_CP_SECTOR"),
            "currencies": currencies,
        },
        "reporting_countries": {},
        "cross_border_matrix": {},
    }

    print(f"\n[2/4] Querying per-reporting-country availability ({len(iso_rep)} countries)...")
    total = len(iso_rep)
    for idx, rep in enumerate(sorted(iso_rep), 1):
        rep_name = LBS_COUNTRY_NAMES.get(rep, rep)
        if idx % 5 == 1 or idx == total:
            print(f"  [{idx}/{total}] {rep} ({rep_name})...")

        # Claims: all instruments, all currencies, all sectors, cross-border only
        claims_avail = availability_query(f"Q.S.C..TO1.A.5J.A.{rep}...N")
        # Liabilities: same
        liab_avail = availability_query(f"Q.S.L..TO1.A.5J.A.{rep}...N")

        claims_cp = []
        claims_instruments = []
        claims_sectors = []
        claims_series = 0
        if claims_avail and claims_avail["series_count"] > 0:
            claims_cp = claims_avail["dimensions"].get("L_CP_COUNTRY", [])
            claims_instruments = claims_avail["dimensions"].get("L_INSTR", [])
            claims_sectors = claims_avail["dimensions"].get("L_CP_SECTOR", [])
            claims_series = claims_avail["series_count"]

        liab_cp = []
        liab_instruments = []
        liab_sectors = []
        liab_series = 0
        if liab_avail and liab_avail["series_count"] > 0:
            liab_cp = liab_avail["dimensions"].get("L_CP_COUNTRY", [])
            liab_instruments = liab_avail["dimensions"].get("L_INSTR", [])
            liab_sectors = liab_avail["dimensions"].get("L_CP_SECTOR", [])
            liab_series = liab_avail["series_count"]

        claims_cp_iso = sorted([c for c in claims_cp if len(c) == 2 and not c[0].isdigit()])
        liab_cp_iso = sorted([c for c in liab_cp if len(c) == 2 and not c[0].isdigit()])

        index["reporting_countries"][rep] = {
            "name": rep_name,
            "claims": {
                "series_count": claims_series,
                "counterparty_countries": claims_cp_iso,
                "counterparty_count": len(claims_cp_iso),
                "instruments": resolve_dim(claims_instruments, "L_INSTR"),
                "sectors": resolve_dim(claims_sectors, "L_CP_SECTOR"),
            },
            "liabilities": {
                "series_count": liab_series,
                "counterparty_countries": liab_cp_iso,
                "counterparty_count": len(liab_cp_iso),
                "instruments": resolve_dim(liab_instruments, "L_INSTR"),
                "sectors": resolve_dim(liab_sectors, "L_CP_SECTOR"),
            },
        }

        for cp in claims_cp_iso:
            key = f"{rep}->{cp}"
            if key not in index["cross_border_matrix"]:
                index["cross_border_matrix"][key] = {"from": rep, "from_name": rep_name, "to": cp, "to_name": resolve(cp, "L_CP_COUNTRY")}
            index["cross_border_matrix"][key]["has_claims"] = True

        for cp in liab_cp_iso:
            key = f"{rep}->{cp}"
            if key not in index["cross_border_matrix"]:
                index["cross_border_matrix"][key] = {"from": rep, "from_name": rep_name, "to": cp, "to_name": resolve(cp, "L_CP_COUNTRY")}
            index["cross_border_matrix"][key]["has_liabilities"] = True

        time.sleep(0.3)

    print(f"\n[3/4] Querying currency breakdowns for major reporting countries...")
    major_reporters = ["US", "GB", "JP", "DE", "FR", "CH", "HK", "SG", "CA", "AU"]
    for rep in major_reporters:
        if rep not in index["reporting_countries"]:
            continue
        rep_name = LBS_COUNTRY_NAMES.get(rep, rep)
        print(f"  {rep} ({rep_name}): currency breakdown...")
        ccy_avail = availability_query(f"Q.S...+TO1+USD+EUR+JPY+GBP+CHF+TO3+UN9.A+D+F.5J.A.{rep}....") 
        if ccy_avail and ccy_avail["series_count"] > 0:
            ccy_list = ccy_avail["dimensions"].get("L_DENOM", [])
            index["reporting_countries"][rep]["currency_breakdown"] = ccy_list
        time.sleep(0.3)

    # Bank nationality breakdown for key reporters
    print(f"\n[3b/4] Querying bank nationality breakdown for major reporters...")
    for rep in major_reporters:
        if rep not in index["reporting_countries"]:
            continue
        nat_avail = availability_query(f"Q.S.C.A.TO1.A..A+D+B+S.{rep}.A..N")
        if nat_avail and nat_avail["series_count"] > 0:
            parent_countries = nat_avail["dimensions"].get("L_PARENT_CTY", [])
            bank_types = nat_avail["dimensions"].get("L_REP_BANK_TYPE", [])
            index["reporting_countries"][rep]["bank_nationalities"] = sorted(parent_countries)
            index["reporting_countries"][rep]["bank_types"] = resolve_dim(bank_types, "L_REP_BANK_TYPE")
        time.sleep(0.3)

    print(f"\n[4/4] Computing statistics and writing output...")

    total_links = len(index["cross_border_matrix"])
    bidirectional = 0
    for key, link in index["cross_border_matrix"].items():
        if link.get("has_claims") and link.get("has_liabilities"):
            bidirectional += 1

    index["deep_stats"] = {
        "total_cross_border_links": total_links,
        "bidirectional_links": bidirectional,
        "claims_only_links": sum(1 for l in index["cross_border_matrix"].values() if l.get("has_claims") and not l.get("has_liabilities")),
        "liabilities_only_links": sum(1 for l in index["cross_border_matrix"].values() if l.get("has_liabilities") and not l.get("has_claims")),
        "avg_counterparties_per_reporter_claims": round(
            sum(r["claims"]["counterparty_count"] for r in index["reporting_countries"].values()) / max(len(index["reporting_countries"]), 1), 1
        ),
        "avg_counterparties_per_reporter_liabilities": round(
            sum(r["liabilities"]["counterparty_count"] for r in index["reporting_countries"].values()) / max(len(index["reporting_countries"]), 1), 1
        ),
        "top_reporters_by_claims_coverage": sorted(
            [(rep, data["claims"]["counterparty_count"]) for rep, data in index["reporting_countries"].items()],
            key=lambda x: -x[1],
        )[:15],
        "top_reporters_by_liabilities_coverage": sorted(
            [(rep, data["liabilities"]["counterparty_count"]) for rep, data in index["reporting_countries"].items()],
            key=lambda x: -x[1],
        )[:15],
    }

    with open(output_path, "w") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"\nDone. Output: {output_path} ({size_mb:.1f} MB)")
    print(f"\nDeep Index Stats:")
    print(f"  Total cross-border links: {total_links}")
    print(f"  Bidirectional links: {bidirectional}")
    print(f"  Avg counterparties per reporter (claims): {index['deep_stats']['avg_counterparties_per_reporter_claims']}")
    print(f"  Avg counterparties per reporter (liabilities): {index['deep_stats']['avg_counterparties_per_reporter_liabilities']}")
    print(f"\n  Top 10 reporters by claims coverage:")
    for rep, cnt in index["deep_stats"]["top_reporters_by_claims_coverage"][:10]:
        print(f"    {rep} ({LBS_COUNTRY_NAMES.get(rep, rep)}): {cnt} counterparty countries")


# ── Data Query Engine ─────────────────────────────────────────────────────────

DATA_OUTPUT_DIR = Path(__file__).parent / "data"

DATAFLOW_ALIASES = {
    "lbs": "WS_LBS_D_PUB",
    "cbs": "WS_CBS_PUB",
    "credit": "WS_TC",
    "credit-gap": "WS_CREDIT_GAP",
    "dsr": "WS_DSR",
    "property": "WS_SPP",
    "commercial-property": "WS_CPP",
    "eer": "WS_EER",
    "policy-rates": "WS_CBPOL",
    "etd": "WS_XTD_DERIV",
    "otc": "WS_OTC_DERIV2",
    "liquidity": "WS_GLI",
    "debt-securities": "WS_DEBT_SEC2_PUB",
    "fx": "WS_EER",
    "cpi": "WS_LONG_CPI",
}


def data_query(dataflow, key="all", start_period=None, end_period=None,
               detail="full", max_retries=3, quiet=False):
    """Fetch actual BIS time series data via SDMX data API.

    Args:
        dataflow: Dataflow ID (e.g. 'WS_CBPOL') or alias (e.g. 'policy-rates')
        key: Dimension filter string. 'all' for everything, or period-separated
             dimension values (e.g. 'M...US' for monthly US data).
             Use '+' for OR within a dimension: 'M...US+GB+JP'
        start_period: Start period (e.g. '2020-Q1', '2020-01', '2020')
        end_period: End period
        detail: 'full' (data+attributes), 'dataonly', 'serieskeysonly', 'nodata'
        quiet: If True, suppress "No data found" messages (for probing queries)

    Returns:
        List of series dicts: {key, dimensions, attributes, observations}
    """
    flow_id = DATAFLOW_ALIASES.get(dataflow, dataflow)
    url = f"{BASE_URL}/data/dataflow/BIS/{flow_id}/1.0/{key}"

    params = {"format": "sdmx-json", "detail": detail}
    if start_period:
        params["startPeriod"] = start_period
    if end_period:
        params["endPeriod"] = end_period

    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=DATA_HEADERS, params=params, timeout=120)
            if resp.status_code == 200:
                return _parse_sdmx_data(resp.json())
            elif resp.status_code == 404:
                if not quiet:
                    print(f"  No data found for {flow_id} / {key}")
                return []
            elif resp.status_code == 429:
                wait = 2 ** (attempt + 1)
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"  HTTP {resp.status_code} for data query: {flow_id}/{key}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    return []
        except requests.exceptions.Timeout:
            print(f"  Timeout on data query, retry {attempt+1}/{max_retries}")
            time.sleep(3)
        except Exception as e:
            print(f"  Error: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                return []
    return []


def _parse_sdmx_data(raw):
    """Parse SDMX-JSON data response into a list of series."""
    datasets = raw.get("data", {}).get("dataSets", [])
    if not datasets:
        return []

    structure = raw.get("data", {}).get("structure", {})
    dim_defs = structure.get("dimensions", {}).get("series", [])
    obs_dim = structure.get("dimensions", {}).get("observation", [])
    attr_defs = structure.get("attributes", {}).get("series", [])

    time_values = []
    if obs_dim:
        time_values = [v.get("id", v.get("name", str(i)))
                       for i, v in enumerate(obs_dim[0].get("values", []))]

    series_list = []
    ds = datasets[0]
    series_data = ds.get("series", {})

    for series_key_str, series_obj in series_data.items():
        key_indices = [int(k) for k in series_key_str.split(":")]

        dimensions = {}
        key_parts = []
        for i, dim_def in enumerate(dim_defs):
            idx = key_indices[i] if i < len(key_indices) else 0
            values = dim_def.get("values", [])
            if idx < len(values):
                val = values[idx]
                dimensions[dim_def.get("id", f"dim_{i}")] = {
                    "id": val.get("id", ""),
                    "name": val.get("name", ""),
                }
                key_parts.append(val.get("id", ""))
            else:
                key_parts.append("?")

        attributes = {}
        for i, attr_def in enumerate(attr_defs):
            attr_vals = attr_def.get("values", [])
            attr_indices = series_obj.get("attributes", [])
            if i < len(attr_indices) and attr_indices[i] is not None:
                aidx = attr_indices[i]
                if aidx < len(attr_vals):
                    attributes[attr_def.get("id", f"attr_{i}")] = attr_vals[aidx].get("name", "")

        observations = {}
        for obs_key, obs_val in series_obj.get("observations", {}).items():
            obs_idx = int(obs_key)
            period = time_values[obs_idx] if obs_idx < len(time_values) else obs_key
            value = obs_val[0] if obs_val else None
            observations[period] = value

        series_list.append({
            "key": ".".join(key_parts),
            "dimensions": dimensions,
            "attributes": attributes,
            "observations": observations,
        })

    return series_list


def _format_series_table(series_list, max_series=20, last_n_periods=12):
    """Format series data as readable output."""
    if not series_list:
        print("  No data returned.")
        return

    print(f"\n  {len(series_list)} series returned\n")

    for i, s in enumerate(series_list[:max_series]):
        dim_str = " | ".join(f"{v['name']}" for v in s["dimensions"].values() if v.get("name"))
        print(f"  [{i+1}] {dim_str}")
        print(f"      Key: {s['key']}")

        obs = s["observations"]
        if obs:
            sorted_periods = sorted(obs.keys())
            recent = sorted_periods[-last_n_periods:] if len(sorted_periods) > last_n_periods else sorted_periods
            def _fmt_obs(p):
                v = obs[p]
                if v is None:
                    return f"{p}=N/A"
                try:
                    return f"{p}={float(v):.2f}"
                except (ValueError, TypeError):
                    return f"{p}={v}"
            values_str = "  ".join(_fmt_obs(p) for p in recent)
            print(f"      {values_str}")
        print()

    if len(series_list) > max_series:
        print(f"  ... and {len(series_list) - max_series} more series")


def _save_data_json(data, filename):
    DATA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_OUTPUT_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  Saved {path}")
    return str(path)


def _series_to_csv_rows(series_list):
    rows = []
    for s in series_list:
        dim_flat = {k: v["id"] for k, v in s["dimensions"].items()}
        dim_names = {f"{k}_name": v["name"] for k, v in s["dimensions"].items()}
        for period, value in sorted(s["observations"].items()):
            row = {"period": period, "value": value, "key": s["key"]}
            row.update(dim_flat)
            row.update(dim_names)
            rows.append(row)
    return rows


# ── Pre-Built Data Recipes ────────────────────────────────────────────────────

def recipe_policy_rates(countries="US+GB+JP+DE+CH+CA+AU+SE+NO+NZ",
                        start="2000", end=None):
    """Central bank policy rates for major economies."""
    print(f"\n=== Central Bank Policy Rates ===\n")
    key = f"M.{countries}"
    series = data_query("WS_CBPOL", key=key, start_period=start, end_period=end)
    _format_series_table(series, max_series=30, last_n_periods=12)
    if series:
        ts = time.strftime("%Y%m%d_%H%M%S")
        _save_data_json({"query": f"policy-rates/{key}", "series": series},
                        f"policy_rates_{ts}.json")
    return series


def recipe_total_credit(countries="US+GB+JP+DE+FR+CN+CA+AU",
                        start="2000", end=None):
    """Total credit to non-financial sector (% of GDP and nominal)."""
    print(f"\n=== Total Credit to Non-Financial Sector ===\n")
    key = f"Q.{countries}.P.A.M.XDC.A"
    series = data_query("WS_TC", key=key, start_period=start, end_period=end)
    _format_series_table(series, max_series=20, last_n_periods=8)
    if series:
        ts = time.strftime("%Y%m%d_%H%M%S")
        _save_data_json({"query": f"credit/{key}", "series": series},
                        f"total_credit_{ts}.json")
    return series


def recipe_credit_gap(countries="US+GB+JP+DE+FR+CN+CA+AU",
                      start="2000", end=None):
    """Credit-to-GDP gaps (BIS deviation from trend)."""
    print(f"\n=== Credit-to-GDP Gaps ===\n")
    key = f"Q.{countries}.B"
    series = data_query("WS_CREDIT_GAP", key=key, start_period=start, end_period=end)
    _format_series_table(series, max_series=20, last_n_periods=8)
    if series:
        ts = time.strftime("%Y%m%d_%H%M%S")
        _save_data_json({"query": f"credit-gap/{key}", "series": series},
                        f"credit_gap_{ts}.json")
    return series


def recipe_dsr(countries="US+GB+JP+DE+FR+CN+CA+AU",
               start="2000", end=None):
    """Debt service ratios for the private non-financial sector."""
    print(f"\n=== Debt Service Ratios ===\n")
    key = f"Q.{countries}.P"
    series = data_query("WS_DSR", key=key, start_period=start, end_period=end)
    _format_series_table(series, max_series=20, last_n_periods=8)
    if series:
        ts = time.strftime("%Y%m%d_%H%M%S")
        _save_data_json({"query": f"dsr/{key}", "series": series},
                        f"dsr_{ts}.json")
    return series


def recipe_property_prices(countries="US+GB+JP+DE+FR+CN+CA+AU+NZ+SE+NO+KR",
                           start="2000", end=None):
    """Residential property prices (real, index)."""
    print(f"\n=== Residential Property Prices ===\n")
    key = f"Q.N.{countries}"
    series = data_query("WS_SPP", key=key, start_period=start, end_period=end)
    _format_series_table(series, max_series=20, last_n_periods=8)
    if series:
        ts = time.strftime("%Y%m%d_%H%M%S")
        _save_data_json({"query": f"property/{key}", "series": series},
                        f"property_prices_{ts}.json")
    return series


def recipe_eer(countries="US+GB+JP+DE+FR+CN+CH+CA+AU+SE+NO+NZ+KR+IN+BR+MX",
               start="2000", end=None):
    """Effective exchange rates (real and nominal, broad basket)."""
    print(f"\n=== Effective Exchange Rates ===\n")
    key = f"M.R.B.{countries}"
    series = data_query("WS_EER", key=key, start_period=start, end_period=end)
    _format_series_table(series, max_series=20, last_n_periods=12)
    if series:
        ts = time.strftime("%Y%m%d_%H%M%S")
        _save_data_json({"query": f"eer/{key}", "series": series},
                        f"eer_{ts}.json")
    return series


def recipe_global_liquidity(start="2010", end=None):
    """Global liquidity indicators: USD credit to non-bank borrowers outside US."""
    print(f"\n=== Global Liquidity Indicators ===\n")
    series = data_query("WS_GLI", key="all", start_period=start, end_period=end)
    _format_series_table(series, max_series=30, last_n_periods=8)
    if series:
        ts = time.strftime("%Y%m%d_%H%M%S")
        _save_data_json({"query": "liquidity/all", "series": series},
                        f"global_liquidity_{ts}.json")
    return series


def recipe_lbs_crossborder(reporter="US", position="C", start="2010", end=None):
    """Locational banking: cross-border claims/liabilities for a reporting country."""
    print(f"\n=== LBS Cross-Border: {reporter} ({position}) ===\n")
    pos = "C" if position.upper().startswith("C") else "L"
    key = f"Q.S.{pos}.A.TO1.A.5J.A.{reporter}.A..N"
    series = data_query("WS_LBS_D_PUB", key=key, start_period=start, end_period=end)
    _format_series_table(series, max_series=20, last_n_periods=8)
    if series:
        ts = time.strftime("%Y%m%d_%H%M%S")
        _save_data_json({"query": f"lbs/{key}", "series": series},
                        f"lbs_{reporter}_{pos}_{ts}.json")
    return series


# ── Cross-Border Banking & Shadow Banking Constants ───────────────────────────

CROSS_BORDER_OUTPUT_DIR = Path(__file__).parent / "data" / "cross_border"

MAJOR_LBS_REPORTERS = ["US", "GB", "JP", "DE", "FR", "CH", "HK", "SG", "CA", "AU",
                       "NL", "IE", "LU", "IT", "ES", "BE"]

OFFSHORE_CENTERS = ["GB", "HK", "SG", "KY", "BS", "JE", "GG", "IM", "LU", "IE",
                    "BH", "PA", "BM", "CW", "MO", "CY"]

CORE_OFFSHORE = ["GB", "HK", "SG", "KY", "LU", "IE", "JE"]

KEY_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF"]

LBS_SECTORS = {
    "A": "All sectors",
    "B": "Banks (total)",
    "N": "Non-banks (total)",
    "I": "Related offices (intra-group)",
    "M": "Central banks",
    "F": "Non-bank financial (NBFI)",
    "C": "Non-financial corporations",
    "G": "General government",
    "H": "Households",
    "O": "Official sector",
    "P": "Non-financial sectors",
    "R": "Non-bank private sector",
    "S": "Non-financial private sector",
}

LBS_INSTRUMENTS = {
    "A": "All instruments",
    "G": "Loans & deposits",
    "D": "Debt securities",
    "B": "Credit (loans + debt)",
    "V": "Derivatives",
    "I": "Derivatives + other",
    "N": "Repo / reverse repo",
    "L": "Debt securities (long-term)",
    "M": "Debt securities (short-term)",
}

LBS_POSITIONS = {
    "C": "Total claims",
    "L": "Total liabilities",
    "D": "Cross-border claims",
    "I": "International claims",
    "N": "Net positions",
    "K": "Capital / equity",
    "S": "Foreign claims",
    "B": "Local claims",
    "M": "Local liabilities",
}

CBS_BANK_TYPES = {
    "4B": "Domestic banks (consolidated)",
    "4C": "Inside-area foreign banks (consolidated by parent)",
    "4M": "All banks (4B+4C+4D+4E)",
    "4N": "All including 4C banks, excl. domestic positions",
    "4O": "All excluding 4C banks, excl. domestic positions",
    "4R": "Domestic banks, excl. domestic positions",
}

CBS_BASES = {
    "F": "Immediate counterparty",
    "U": "Guarantor basis",
    "R": "Guarantor, calculated (F+Q)",
    "O": "Outward risk transfers",
    "P": "Inward risk transfers",
    "Q": "Net risk transfers (Inward-Outward)",
}

CBS_MATURITIES = {
    "A": "All maturities",
    "U": "Up to 1 year",
    "M": "Over 1 to 2 years",
    "N": "Over 2 years",
}

GLI_COUNTRIES_USD = {
    "3C": "Emerging Europe",
    "3P": "All countries excluding residents (global)",
    "4T": "Emerging markets and developing economies",
    "4U": "Emerging Latin America and Caribbean",
    "4W": "Emerging Africa and Middle East",
    "4Y": "Emerging Asia and Pacific",
}

COUNTRY_NAMES_FULL = {
    "US": "United States", "GB": "United Kingdom", "JP": "Japan",
    "DE": "Germany", "FR": "France", "CH": "Switzerland",
    "HK": "Hong Kong SAR", "SG": "Singapore", "CA": "Canada",
    "AU": "Australia", "NL": "Netherlands", "IE": "Ireland",
    "LU": "Luxembourg", "KY": "Cayman Islands", "BS": "Bahamas",
    "JE": "Jersey", "GG": "Guernsey", "IM": "Isle of Man",
    "BH": "Bahrain", "PA": "Panama", "BM": "Bermuda",
    "CW": "Curacao", "MO": "Macao SAR", "CY": "Cyprus",
    "CN": "China", "BR": "Brazil", "IN": "India", "KR": "Korea",
    "MX": "Mexico", "TR": "Turkey", "RU": "Russia",
    "ZA": "South Africa", "SE": "Sweden", "NO": "Norway", "NZ": "New Zealand",
    "IT": "Italy", "ES": "Spain", "BE": "Belgium",
    "AT": "Austria", "DK": "Denmark", "FI": "Finland",
    "PT": "Portugal", "GR": "Greece", "TW": "Chinese Taipei",
    "5A": "All reporters", "5C": "Euro area", "5J": "All countries",
    "3C": "Emerging Europe", "3P": "All non-resident",
    "4T": "EM & developing", "4U": "EM Latin America",
    "4W": "EM Africa/ME", "4Y": "EM Asia/Pacific", "4A": "G10 countries",
    "XM": "Euro area", "XW": "World",
    "AR": "Argentina", "CL": "Chile", "CO": "Colombia", "PE": "Peru",
    "ID": "Indonesia", "MY": "Malaysia", "PH": "Philippines", "TH": "Thailand",
    "SA": "Saudi Arabia", "AE": "United Arab Emirates", "IL": "Israel", "EG": "Egypt",
    "PL": "Poland", "CZ": "Czech Republic", "HU": "Hungary", "RO": "Romania",
}


def _cn(code):
    return COUNTRY_NAMES_FULL.get(code, code)


def _to_num(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        f = float(val)
        if f != f:  # NaN check (NaN != NaN is True)
            return None
        return f
    try:
        f = float(val)
        if f != f:
            return None
        return f
    except (ValueError, TypeError):
        return None


def _fmt_usd_bn(val):
    """Format a USD value (in millions) as a human-readable string."""
    v = _to_num(val)
    if v is None:
        return "N/A"
    abs_v = abs(v)
    if abs_v >= 1e6:
        return f"${v/1e6:,.2f}T"
    if abs_v >= 1e3:
        return f"${v/1e3:,.1f}B"
    return f"${v:,.0f}M"


def _latest_value(series):
    """Return (value, period) for the most recent observation in a series dict.

    Handles either a single series dict or a list (returns first series's latest).
    """
    if isinstance(series, list):
        if not series:
            return None, None
        series = series[0]
    obs = series.get("observations", {}) if isinstance(series, dict) else {}
    if not obs:
        return None, None
    latest_p = max(obs.keys())
    return _to_num(obs[latest_p]), latest_p


def _save_cb_json(data, filename):
    """Save a cross-border analysis JSON to the cross_border output dir."""
    CROSS_BORDER_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = CROSS_BORDER_OUTPUT_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  Saved {path}")
    return str(path)


def _print_cb_section(title):
    width = 78
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def _print_cb_subsection(title):
    print(f"\n  --- {title} ---")


def _progress_tick(idx, total, label, start_time):
    """Print a progress update (throttled by time)."""
    elapsed = time.time() - start_time
    if idx == total or idx % max(1, total // 10) == 0 or elapsed > 5:
        print(f"  [{idx}/{total}] {label} [{elapsed:.0f}s elapsed]")


# ── LBS Cross-Border Banking Recipes ──────────────────────────────────────────

def recipe_lbs_bilateral(reporter, counterparty, currency="TO1", sector="A",
                         instrument="A", position="C", pos_type="N",
                         start="2010", end=None):
    """Bilateral LBS query between one reporter and one counterparty country.

    Key: FREQ.L_MEASURE.L_POSITION.L_INSTR.L_DENOM.L_CURR_TYPE.L_PARENT_CTY.L_REP_BANK_TYPE.L_REP_CTY.L_CP_SECTOR.L_CP_COUNTRY.L_POS_TYPE

    Args:
        reporter: Reporting country ISO (US, GB, JP, ...)
        counterparty: Counterparty country ISO (CN, TR, 5C, ...)
        currency: Currency denomination (TO1, USD, EUR, GBP, JPY, CHF, TO3, UN9)
        sector: Counterparty sector (A=All, B=Banks, N=Non-banks, F=NBFI, C=Corps, G=Govt, H=Households)
        instrument: Instrument (A=All, G=Loans, D=Debt, B=Credit, V=Derivatives)
        position: C=Claims, L=Liabilities, N=Net
        pos_type: N=Cross-border, R=Local, I=Cross-border+Local FCY, A=All
    """
    print(f"\n=== LBS Bilateral: {_cn(reporter)} -> {_cn(counterparty)} "
          f"({LBS_POSITIONS.get(position, position)}, {currency}, "
          f"{LBS_SECTORS.get(sector, sector)}) ===\n")
    key = f"Q.S.{position}.{instrument}.{currency}.A.5J.A.{reporter}.{sector}.{counterparty}.{pos_type}"
    series = data_query("WS_LBS_D_PUB", key=key, start_period=start, end_period=end)
    _format_series_table(series, max_series=10, last_n_periods=8)
    if series:
        ts = time.strftime("%Y%m%d_%H%M%S")
        _save_cb_json({"query": f"lbs/{key}", "series": series},
                      f"lbs_bilateral_{reporter}_{counterparty}_{ts}.json")
    return series


def recipe_eurodollar(start="2010", end=None, reporters=None):
    """Eurodollar system: USD-denominated cross-border claims/liabilities.

    Two layers:
    1. Global aggregate: total USD cross-border claims and liabilities
    2. Per-center: USD + FCY cross-border positions for major offshore centers

    Returns dict with aggregate series + per-reporter breakdown.
    """
    _print_cb_section("EURODOLLAR SYSTEM: USD Cross-Border Claims & Liabilities")
    results = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "start_period": start, "series": {}, "summary": {}}

    if reporters is None:
        reporters = ["GB", "JP", "FR", "DE", "CH", "HK", "SG", "CA", "AU",
                     "NL", "IE", "LU", "US", "KY"]

    _print_cb_subsection("Global USD cross-border (all reporters aggregate)")
    start_time = time.time()

    usd_claims = data_query("WS_LBS_D_PUB", key="Q.S.C.A.USD.A.5J.A.5A.A.5J.N",
                            start_period=start, end_period=end)
    usd_liabs = data_query("WS_LBS_D_PUB", key="Q.S.L.A.USD.A.5J.A.5A.A.5J.N",
                           start_period=start, end_period=end)
    usd_growth = data_query("WS_LBS_D_PUB", key="Q.G.C.A.USD.A.5J.A.5A.A.5J.N",
                            start_period=start, end_period=end)
    results["series"]["global_usd_claims"] = usd_claims
    results["series"]["global_usd_liabs"] = usd_liabs
    results["series"]["global_usd_growth"] = usd_growth

    v, p = _latest_value(usd_claims)
    if v:
        print(f"    Global USD claims:      {_fmt_usd_bn(v)} ({p})")
        results["summary"]["global_usd_claims"] = {"value": v, "period": p}
    v, p = _latest_value(usd_liabs)
    if v:
        print(f"    Global USD liabilities: {_fmt_usd_bn(v)} ({p})")
        results["summary"]["global_usd_liabs"] = {"value": v, "period": p}
    v, p = _latest_value(usd_growth)
    if v is not None:
        print(f"    YoY growth (latest):    {v:+.1f}% ({p})")
        results["summary"]["global_usd_growth"] = {"value": v, "period": p}

    _print_cb_subsection("Cross-border claims by currency denomination")
    for ccy in KEY_CURRENCIES + ["TO1", "TO3", "UN9"]:
        s = data_query("WS_LBS_D_PUB",
                       key=f"Q.S.C.A.{ccy}.A.5J.A.5A.A.5J.N",
                       start_period=start, end_period=end, quiet=True)
        v, p = _latest_value(s)
        label = {"TO1": "All currencies", "TO3": "Foreign currencies only",
                 "UN9": "Unallocated"}.get(ccy, ccy)
        if v:
            print(f"    {label:25s}: {_fmt_usd_bn(v)} ({p})")
        results["series"][f"global_{ccy.lower()}_claims"] = s
        time.sleep(0.2)

    _print_cb_subsection(f"Foreign currency cross-border positions by center ({len(reporters)} reporters)")
    print("    (Foreign currency ~ eurodollar/eurocurrency intermediation)")
    print(f"    {'Center':<22s} {'FCY Claims':>12s} {'FCY Liabs':>12s} {'Net':>12s}  Role")
    print(f"    {'-'*22} {'-'*12} {'-'*12} {'-'*12}  {'-'*14}")

    net_rows = []
    for i, rep in enumerate(reporters, 1):
        _progress_tick(i, len(reporters), f"{rep} ({_cn(rep)})", start_time)
        c_series = data_query("WS_LBS_D_PUB",
                              key=f"Q.S.C.A.TO1.F.5J.A.{rep}.A.5J.N",
                              start_period=start, end_period=end, quiet=True)
        l_series = data_query("WS_LBS_D_PUB",
                              key=f"Q.S.L.A.TO1.F.5J.A.{rep}.A.5J.N",
                              start_period=start, end_period=end, quiet=True)
        results["series"][f"{rep}_fcy_claims"] = c_series
        results["series"][f"{rep}_fcy_liabs"] = l_series

        c_val, _ = _latest_value(c_series)
        l_val, _ = _latest_value(l_series)
        c = c_val or 0
        l = l_val or 0
        net_rows.append((rep, c, l, c - l))
        time.sleep(0.2)

    net_rows.sort(key=lambda x: -x[1])
    for rep, c, l, n in net_rows:
        if c == 0 and l == 0:
            continue
        role = "FCY SUPPLIER" if n > 0 else "FCY BORROWER"
        print(f"    {_cn(rep):<22s} {_fmt_usd_bn(c):>12s} {_fmt_usd_bn(l):>12s} "
              f"{_fmt_usd_bn(n):>12s}  {role}")

    results["summary"]["fcy_by_reporter"] = {
        rep: {"claims": c, "liabs": l, "net": n} for rep, c, l, n in net_rows}

    ts = time.strftime("%Y%m%d_%H%M%S")
    _save_cb_json(results, f"eurodollar_{ts}.json")
    return results


def recipe_nbfi(start="2010", end=None, reporters=None):
    """Non-bank financial intermediation (shadow banking) cross-border exposure.

    Queries LBS with L_CP_SECTOR=F (Non-bank financial institutions).
    """
    _print_cb_section("NON-BANK FINANCIAL INTERMEDIATION (NBFI / Shadow Banking)")
    results = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "start_period": start, "series": {}, "summary": {}}

    if reporters is None:
        reporters = MAJOR_LBS_REPORTERS

    _print_cb_subsection("Cross-border claims by counterparty sector (global)")
    start_time = time.time()
    for i, (sector_code, sector_name) in enumerate(LBS_SECTORS.items(), 1):
        if sector_code in ("O", "P", "R", "S", "M"):
            continue
        s = data_query("WS_LBS_D_PUB",
                       key=f"Q.S.C.A.TO1.A.5J.A.5A.{sector_code}.5J.N",
                       start_period=start, end_period=end, quiet=True)
        results["series"][f"sector_{sector_code}"] = s
        v, p = _latest_value(s)
        if v:
            print(f"    {sector_name:<28s}: {_fmt_usd_bn(v)} ({p})")
            results["summary"][f"sector_{sector_code}"] = {"value": v, "period": p}
        time.sleep(0.2)

    _print_cb_subsection("USD-denominated claims on NBFI (all reporters)")
    nbfi_usd = data_query("WS_LBS_D_PUB",
                          key="Q.S.C.A.USD.A.5J.A.5A.F.5J.N",
                          start_period=start, end_period=end)
    results["series"]["nbfi_usd_global"] = nbfi_usd
    v, p = _latest_value(nbfi_usd)
    if v:
        print(f"    USD claims on NBFI: {_fmt_usd_bn(v)} ({p})")
        results["summary"]["nbfi_usd_global"] = {"value": v, "period": p}

    nbfi_eur = data_query("WS_LBS_D_PUB",
                          key="Q.S.C.A.EUR.A.5J.A.5A.F.5J.N",
                          start_period=start, end_period=end)
    v, p = _latest_value(nbfi_eur)
    if v:
        print(f"    EUR claims on NBFI: {_fmt_usd_bn(v)} ({p})")
    results["series"]["nbfi_eur_global"] = nbfi_eur

    _print_cb_subsection(f"NBFI claims by reporting center ({len(reporters)} reporters, all-currency)")
    print(f"    {'Center':<25s} {'Claims on NBFI':>15s}  Period")
    print(f"    {'-'*25} {'-'*15}  {'-'*7}")
    rows = []
    for i, rep in enumerate(reporters, 1):
        _progress_tick(i, len(reporters), rep, start_time)
        s = data_query("WS_LBS_D_PUB",
                       key=f"Q.S.C.A.TO1.A.5J.A.{rep}.F.5J.N",
                       start_period=start, end_period=end, quiet=True)
        results["series"][f"{rep}_nbfi_claims"] = s
        v, p = _latest_value(s)
        if v:
            rows.append((rep, v, p))
        time.sleep(0.2)

    rows.sort(key=lambda x: -x[1])
    for rep, v, p in rows:
        print(f"    {_cn(rep):<25s} {_fmt_usd_bn(v):>15s}  {p}")
    results["summary"]["nbfi_by_reporter"] = {rep: {"value": v, "period": p}
                                               for rep, v, p in rows}

    _print_cb_subsection("NBFI growth (all reporters, YoY)")
    nbfi_growth = data_query("WS_LBS_D_PUB",
                             key="Q.G.C.A.TO1.A.5J.A.5A.F.5J.N",
                             start_period=start, end_period=end)
    results["series"]["nbfi_growth"] = nbfi_growth
    if nbfi_growth:
        obs = nbfi_growth[0].get("observations", {})
        recent = sorted(obs.keys())[-8:]
        for period in recent:
            v = _to_num(obs[period])
            if v is not None:
                print(f"    {period}: {v:+.1f}%")

    ts = time.strftime("%Y%m%d_%H%M%S")
    _save_cb_json(results, f"nbfi_{ts}.json")
    return results


def recipe_interbank(currency="USD", start="2010", end=None, reporters=None):
    """Interbank loans & deposits -- repo/money market proxy.

    Queries LBS with L_INSTR=G (Loans & deposits), L_CP_SECTOR=B (Banks).
    """
    _print_cb_section(f"INTERBANK LOANS & DEPOSITS ({currency}) -- Repo/Money Market Proxy")
    results = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "currency": currency, "start_period": start,
               "series": {}, "summary": {}}

    if reporters is None:
        reporters = ["US", "GB", "JP", "FR", "DE", "CH", "HK", "SG", "CA", "KY", "LU", "IE"]

    _print_cb_subsection(f"Global {currency} interbank loans & deposits")
    global_interbank = data_query("WS_LBS_D_PUB",
                                   key=f"Q.S.C.G.{currency}.A.5J.A.5A.B.5J.N",
                                   start_period=start, end_period=end)
    results["series"]["global_interbank"] = global_interbank
    v, p = _latest_value(global_interbank)
    if v:
        print(f"    Global {currency} interbank claims: {_fmt_usd_bn(v)} ({p})")
        results["summary"]["global_interbank"] = {"value": v, "period": p}

    global_interbank_liabs = data_query("WS_LBS_D_PUB",
                                         key=f"Q.S.L.G.{currency}.A.5J.A.5A.B.5J.N",
                                         start_period=start, end_period=end)
    results["series"]["global_interbank_liabs"] = global_interbank_liabs
    v, p = _latest_value(global_interbank_liabs)
    if v:
        print(f"    Global {currency} interbank liabs:   {_fmt_usd_bn(v)} ({p})")

    _print_cb_subsection(f"Intra-group (related offices, {currency}) -- internal liquidity")
    intragroup_c = data_query("WS_LBS_D_PUB",
                               key=f"Q.S.C.A.{currency}.A.5J.A.5A.I.5J.N",
                               start_period=start, end_period=end)
    intragroup_l = data_query("WS_LBS_D_PUB",
                               key=f"Q.S.L.A.{currency}.A.5J.A.5A.I.5J.N",
                               start_period=start, end_period=end)
    results["series"]["intragroup_claims"] = intragroup_c
    results["series"]["intragroup_liabs"] = intragroup_l
    v, p = _latest_value(intragroup_c)
    if v:
        print(f"    Intra-group claims ({currency}): {_fmt_usd_bn(v)} ({p})")
    v, p = _latest_value(intragroup_l)
    if v:
        print(f"    Intra-group liabs   ({currency}): {_fmt_usd_bn(v)} ({p})")

    _print_cb_subsection(f"All-currency interbank claims on banks by reporting center")
    print(f"    (BIS doesn't publish per-reporter breakdown of instrument=Loans by sector)")
    print(f"    (Showing all-instrument, all-currency claims on Banks sector)")
    print(f"    {'Center':<22s} {'Banks Claims':>15s}  Period")
    print(f"    {'-'*22} {'-'*15}  {'-'*7}")
    start_time = time.time()
    rows = []
    for i, rep in enumerate(reporters, 1):
        _progress_tick(i, len(reporters), rep, start_time)
        s = data_query("WS_LBS_D_PUB",
                       key=f"Q.S.C.A.TO1.A.5J.A.{rep}.B.5J.N",
                       start_period=start, end_period=end, quiet=True)
        results["series"][f"{rep}_interbank_claims"] = s
        v, p = _latest_value(s)
        if v:
            rows.append((rep, v, p))
        time.sleep(0.2)

    rows.sort(key=lambda x: -x[1])
    for rep, v, p in rows:
        print(f"    {_cn(rep):<22s} {_fmt_usd_bn(v):>15s}  {p}")

    ts = time.strftime("%Y%m%d_%H%M%S")
    _save_cb_json(results, f"interbank_{currency}_{ts}.json")
    return results


def recipe_offshore_centers(start="2010", end=None, centers=None):
    """Offshore center intermediation: claims/liabilities for GB, HK, SG, KY, LU, IE, JE, etc."""
    _print_cb_section("OFFSHORE CENTER INTERMEDIATION")
    results = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "start_period": start, "series": {}, "summary": {}}

    if centers is None:
        centers = CORE_OFFSHORE + ["JP", "CH"]

    _print_cb_subsection("Total cross-border positions by offshore center")
    print(f"    {'Center':<22s} {'Claims':>12s} {'Liabilities':>12s} "
          f"{'Net':>12s} Role")
    print(f"    {'-'*22} {'-'*12} {'-'*12} {'-'*12} {'-'*14}")

    start_time = time.time()
    net_rows = []
    for i, center in enumerate(centers, 1):
        _progress_tick(i, len(centers), center, start_time)
        claims = data_query("WS_LBS_D_PUB",
                            key=f"Q.S.C.A.TO1.A.5J.A.{center}.A.5J.N",
                            start_period=start, end_period=end, quiet=True)
        liabs = data_query("WS_LBS_D_PUB",
                            key=f"Q.S.L.A.TO1.A.5J.A.{center}.A.5J.N",
                            start_period=start, end_period=end, quiet=True)
        results["series"][f"{center}_claims"] = claims
        results["series"][f"{center}_liabs"] = liabs

        c, _ = _latest_value(claims)
        l, _ = _latest_value(liabs)
        c = c or 0
        l = l or 0
        net = c - l
        net_rows.append((center, c, l, net))
        time.sleep(0.2)

    net_rows.sort(key=lambda x: -x[1])
    for center, c, l, n in net_rows:
        role = "CREDITOR" if n > 0 else "DEBTOR"
        print(f"    {_cn(center):<22s} {_fmt_usd_bn(c):>12s} "
              f"{_fmt_usd_bn(l):>12s} {_fmt_usd_bn(n):>12s} {role}")
    results["summary"]["positions_by_center"] = {
        center: {"claims": c, "liabs": l, "net": n} for center, c, l, n in net_rows}

    _print_cb_subsection("USD + FCY foreign currency claims by center (eurodollar intermediation)")
    print(f"    {'Center':<22s} {'USD Claims':>13s} {'EUR Claims':>13s} "
          f"{'FCY Total':>13s}")
    print(f"    {'-'*22} {'-'*13} {'-'*13} {'-'*13}")
    for center in centers:
        if REPORTER_DOMESTIC_CCY.get(center) == "USD":
            usd_type, eur_type = "D", "F"
        elif REPORTER_DOMESTIC_CCY.get(center) == "EUR":
            usd_type, eur_type = "F", "D"
        else:
            usd_type, eur_type = "F", "F"
        usd_s = data_query("WS_LBS_D_PUB",
                            key=f"Q.S.C.A.USD.{usd_type}.5J.A.{center}.A.5J.N",
                            start_period=start, end_period=end, quiet=True)
        eur_s = data_query("WS_LBS_D_PUB",
                            key=f"Q.S.C.A.EUR.{eur_type}.5J.A.{center}.A.5J.N",
                            start_period=start, end_period=end, quiet=True)
        fcy_s = data_query("WS_LBS_D_PUB",
                            key=f"Q.S.C.A.TO1.F.5J.A.{center}.A.5J.N",
                            start_period=start, end_period=end, quiet=True)
        results["series"][f"{center}_usd"] = usd_s
        results["series"][f"{center}_eur"] = eur_s
        results["series"][f"{center}_fcy"] = fcy_s
        uv, _ = _latest_value(usd_s)
        ev, _ = _latest_value(eur_s)
        fv, _ = _latest_value(fcy_s)
        print(f"    {_cn(center):<22s} {_fmt_usd_bn(uv):>13s} "
              f"{_fmt_usd_bn(ev):>13s} {_fmt_usd_bn(fv):>13s}")
        time.sleep(0.15)

    ts = time.strftime("%Y%m%d_%H%M%S")
    _save_cb_json(results, f"offshore_centers_{ts}.json")
    return results


def recipe_bank_nationality(host=None, start="2010", end=None, parents=None):
    """Bank nationality breakdown: cross-border claims by parent country of bank.

    BIS publishes L_PARENT_CTY only at the aggregate (5A = all reporting countries)
    level, not per-host-country. This recipe shows global claims by parent country
    nationality. The `host` parameter is accepted for compatibility but will only
    filter if the specific host+parent combo is available (rare); default is
    global aggregate (5A).
    """
    if host is None or host == "5A":
        rep_cty = "5A"
        host_label = "global aggregate (all reporters)"
    else:
        rep_cty = host
        host_label = _cn(host)
    _print_cb_section(f"BANK NATIONALITY: cross-border claims in {host_label} by parent HQ")
    results = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "host": host, "start_period": start, "series": {}, "summary": {}}

    if parents is None:
        parents = ["US", "JP", "DE", "FR", "CH", "GB", "CN", "HK", "SG",
                   "NL", "IE", "LU", "IT", "ES", "CA", "AU"]

    _print_cb_subsection(f"All-currency cross-border claims by parent country")
    print(f"    {'Parent Country':<22s} {'Claims':>15s}  Period")
    print(f"    {'-'*22} {'-'*15}  {'-'*7}")

    start_time = time.time()
    rows = []
    for i, nat in enumerate(parents, 1):
        _progress_tick(i, len(parents), nat, start_time)
        s = data_query("WS_LBS_D_PUB",
                       key=f"Q.S.C.A.TO1.A.{nat}.A.{rep_cty}.A.5J.N",
                       start_period=start, end_period=end, quiet=True)
        results["series"][f"parent_{nat}_claims"] = s
        v, p = _latest_value(s)
        if v:
            rows.append((nat, v, p))
        time.sleep(0.2)

    rows.sort(key=lambda x: -x[1])
    for nat, v, p in rows:
        print(f"    {_cn(nat):<22s} {_fmt_usd_bn(v):>15s}  {p}")
    results["summary"]["by_parent_country"] = {nat: {"value": v, "period": p}
                                                 for nat, v, p in rows}

    _print_cb_subsection(f"USD-denominated cross-border claims by parent country")
    print(f"    {'Parent Country':<22s} {'USD Claims':>15s}  Period")
    print(f"    {'-'*22} {'-'*15}  {'-'*7}")

    rows_usd = []
    for nat in [r[0] for r in rows]:
        s = data_query("WS_LBS_D_PUB",
                       key=f"Q.S.C.A.USD.A.{nat}.A.{rep_cty}.A.5J.N",
                       start_period=start, end_period=end, quiet=True)
        results["series"][f"parent_{nat}_usd_claims"] = s
        v, p = _latest_value(s)
        if v:
            rows_usd.append((nat, v, p))
        time.sleep(0.15)

    rows_usd.sort(key=lambda x: -x[1])
    for nat, v, p in rows_usd:
        print(f"    {_cn(nat):<22s} {_fmt_usd_bn(v):>15s}  {p}")
    results["summary"]["by_parent_country_usd"] = {nat: {"value": v, "period": p}
                                                     for nat, v, p in rows_usd}

    ts = time.strftime("%Y%m%d_%H%M%S")
    host_tag = host if host else "global"
    _save_cb_json(results, f"bank_nationality_{host_tag}_{ts}.json")
    return results


# Domestic currency of each LBS reporting country (used to switch L_CURR_TYPE)
REPORTER_DOMESTIC_CCY = {
    "US": "USD", "GB": "GBP", "JP": "JPY", "DE": "EUR", "FR": "EUR",
    "CH": "CHF", "HK": "HKD", "SG": "SGD", "CA": "CAD", "AU": "AUD",
    "AT": "EUR", "BE": "EUR", "BH": "BHD", "BM": "BMD", "BR": "BRL",
    "BS": "BSD", "CL": "CLP", "CN": "CNY", "CW": "ANG", "CY": "EUR",
    "DK": "DKK", "ES": "EUR", "FI": "EUR", "GG": "GBP", "GR": "EUR",
    "ID": "IDR", "IE": "EUR", "IM": "GBP", "IN": "INR", "IT": "EUR",
    "JE": "GBP", "KR": "KRW", "KY": "KYD", "LU": "EUR", "MO": "MOP",
    "MX": "MXN", "MY": "MYR", "NL": "EUR", "NO": "NOK", "PA": "PAB",
    "PH": "PHP", "PT": "EUR", "RU": "RUB", "SA": "SAR", "SE": "SEK",
    "TR": "TRY", "TW": "TWD", "ZA": "ZAR",
}


def recipe_currency_breakdown(reporter="US", start="2010", end=None):
    """Currency breakdown of cross-border claims for a single reporter.

    Handles L_CURR_TYPE correctly based on whether the queried currency is the
    reporter's domestic currency (L_CURR_TYPE=D) or foreign (L_CURR_TYPE=F).
    """
    _print_cb_section(f"CURRENCY BREAKDOWN: {_cn(reporter)} cross-border claims")
    results = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "reporter": reporter, "start_period": start,
               "series": {}, "summary": {}}

    domestic_ccy = REPORTER_DOMESTIC_CCY.get(reporter, "USD")

    def _curr_type(ccy):
        if ccy in ("TO1",):
            return "A"
        if ccy in ("UN9",):
            return "U"
        if ccy == "TO3":
            return "F"
        return "D" if ccy == domestic_ccy else "F"

    queries = [
        ("TO1", "All currencies"),
        ("USD", "USD"),
        ("EUR", "EUR"),
        ("GBP", "GBP"),
        ("JPY", "JPY"),
        ("CHF", "CHF"),
        ("TO3", "Foreign currencies (agg)"),
        ("UN9", "Unallocated"),
    ]

    _print_cb_subsection(f"Cross-border claims by currency ({reporter}, domestic={domestic_ccy})")
    print(f"    {'Currency':<26s} {'Claims':>14s}  {'Liabs':>14s}  Period")
    print(f"    {'-'*26} {'-'*14}  {'-'*14}  {'-'*7}")

    total_claims = None
    rows = []
    for ccy, label in queries:
        curr_type = _curr_type(ccy)
        c = data_query("WS_LBS_D_PUB",
                       key=f"Q.S.C.A.{ccy}.{curr_type}.5J.A.{reporter}.A.5J.N",
                       start_period=start, end_period=end, quiet=True)
        l = data_query("WS_LBS_D_PUB",
                       key=f"Q.S.L.A.{ccy}.{curr_type}.5J.A.{reporter}.A.5J.N",
                       start_period=start, end_period=end, quiet=True)
        results["series"][f"{ccy}_claims"] = c
        results["series"][f"{ccy}_liabs"] = l

        cv, cp = _latest_value(c)
        lv, lp = _latest_value(l)
        rows.append((ccy, label, cv, lv, cp or lp))
        if ccy == "TO1":
            total_claims = cv
        time.sleep(0.2)

    for ccy, label, cv, lv, p in rows:
        pct_c = ""
        if total_claims and cv and ccy != "TO1":
            try:
                pct_c = f" ({cv/total_claims*100:.0f}%)"
            except (ValueError, TypeError):
                pct_c = ""
        # Flag domestic currency
        ccy_label = f"{label} (dom)" if ccy == domestic_ccy else label
        print(f"    {ccy_label:<26s} {_fmt_usd_bn(cv):>14s}{pct_c:<6s} "
              f"{_fmt_usd_bn(lv):>14s}  {p}")
        results["summary"][ccy] = {"claims": cv, "liabs": lv, "period": p,
                                    "is_domestic": ccy == domestic_ccy}

    ts = time.strftime("%Y%m%d_%H%M%S")
    _save_cb_json(results, f"currency_breakdown_{reporter}_{ts}.json")
    return results


def recipe_fcy_mismatch(start="2010", end=None, reporters=None):
    """Foreign vs domestic currency cross-border positions -- vulnerability indicator."""
    _print_cb_section("CURRENCY MISMATCH: Foreign Currency Cross-Border Positions")
    results = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "start_period": start, "series": {}, "summary": {}}

    if reporters is None:
        reporters = ["US", "GB", "JP", "DE", "FR", "CH", "AU", "CA", "NL",
                     "IT", "ES", "SE", "KR", "BR", "MX", "TR", "IN", "CN",
                     "HK", "SG"]

    _print_cb_subsection(f"Domestic vs Foreign currency CLAIMS by center ({len(reporters)} reporters)")
    print(f"    {'Center':<22s} {'All':>12s} {'Domestic':>12s} "
          f"{'Foreign':>12s} {'FCY %':>6s}")
    print(f"    {'-'*22} {'-'*12} {'-'*12} {'-'*12} {'-'*6}")

    start_time = time.time()
    rows = []
    for i, rep in enumerate(reporters, 1):
        _progress_tick(i, len(reporters), rep, start_time)
        a = data_query("WS_LBS_D_PUB",
                       key=f"Q.S.C.A.TO1.A.5J.A.{rep}.A.5J.N",
                       start_period=start, end_period=end, quiet=True)
        d = data_query("WS_LBS_D_PUB",
                       key=f"Q.S.C.A.TO1.D.5J.A.{rep}.A.5J.N",
                       start_period=start, end_period=end, quiet=True)
        f = data_query("WS_LBS_D_PUB",
                       key=f"Q.S.C.A.TO1.F.5J.A.{rep}.A.5J.N",
                       start_period=start, end_period=end, quiet=True)
        results["series"][f"{rep}_all"] = a
        results["series"][f"{rep}_dom"] = d
        results["series"][f"{rep}_fgn"] = f

        av, _ = _latest_value(a)
        dv, _ = _latest_value(d)
        fv, _ = _latest_value(f)
        av, dv, fv = av or 0, dv or 0, fv or 0
        pct = (fv / av * 100) if av else 0
        rows.append((rep, av, dv, fv, pct))
        time.sleep(0.2)

    rows.sort(key=lambda x: -x[1])
    for rep, av, dv, fv, pct in rows:
        print(f"    {_cn(rep):<22s} {_fmt_usd_bn(av):>12s} {_fmt_usd_bn(dv):>12s} "
              f"{_fmt_usd_bn(fv):>12s} {pct:>5.0f}%")
    results["summary"]["fcy_mismatch_by_reporter"] = {
        rep: {"all": av, "domestic": dv, "foreign": fv, "fcy_pct": pct}
        for rep, av, dv, fv, pct in rows}

    ts = time.strftime("%Y%m%d_%H%M%S")
    _save_cb_json(results, f"fcy_mismatch_{ts}.json")
    return results


def recipe_sector_matrix(reporter="US", start="2010", end=None):
    """Counterparty sector decomposition for a single reporter.

    Shows claims on: Banks, NBFI, Non-fin corps, Households, Government, Related offices.
    """
    _print_cb_section(f"SECTOR MATRIX: {_cn(reporter)} cross-border claims by sector")
    results = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "reporter": reporter, "start_period": start,
               "series": {}, "summary": {}}

    sectors = [("A", "All sectors"), ("B", "Banks (total)"),
               ("I", "Related offices (intra-group)"),
               ("J", "Unrelated banks"), ("N", "Non-banks (total)"),
               ("F", "Non-bank financial (NBFI)"),
               ("C", "Non-financial corps"), ("G", "General government"),
               ("H", "Households"), ("O", "Official sector")]

    usd_type = "D" if REPORTER_DOMESTIC_CCY.get(reporter) == "USD" else "F"

    _print_cb_subsection(f"{reporter} cross-border claims by counterparty sector")
    print(f"    {'Sector':<32s} {'All CCY':>13s} {'USD':>13s} Period")
    print(f"    {'-'*32} {'-'*13} {'-'*13} {'-'*7}")

    for sec_code, sec_name in sectors:
        all_s = data_query("WS_LBS_D_PUB",
                           key=f"Q.S.C.A.TO1.A.5J.A.{reporter}.{sec_code}.5J.N",
                           start_period=start, end_period=end, quiet=True)
        usd_s = data_query("WS_LBS_D_PUB",
                           key=f"Q.S.C.A.USD.{usd_type}.5J.A.{reporter}.{sec_code}.5J.N",
                           start_period=start, end_period=end, quiet=True)
        results["series"][f"sector_{sec_code}_all"] = all_s
        results["series"][f"sector_{sec_code}_usd"] = usd_s

        av, ap = _latest_value(all_s)
        uv, up = _latest_value(usd_s)
        period = ap or up or ""
        print(f"    {sec_name:<32s} {_fmt_usd_bn(av):>13s} "
              f"{_fmt_usd_bn(uv):>13s} {period}")
        results["summary"][sec_code] = {"all_ccy": av, "usd": uv, "period": period}
        time.sleep(0.2)

    _print_cb_subsection(f"{reporter} instruments breakdown")
    print(f"    {'Instrument':<28s} {'Claims':>13s} Period")
    print(f"    {'-'*28} {'-'*13} {'-'*7}")
    for instr_code, instr_name in LBS_INSTRUMENTS.items():
        s = data_query("WS_LBS_D_PUB",
                       key=f"Q.S.C.{instr_code}.TO1.A.5J.A.{reporter}.A.5J.N",
                       start_period=start, end_period=end, quiet=True)
        results["series"][f"instr_{instr_code}"] = s
        v, p = _latest_value(s)
        if v:
            print(f"    {instr_name:<28s} {_fmt_usd_bn(v):>13s} {p}")
            results["summary"][f"instr_{instr_code}"] = {"value": v, "period": p}
        time.sleep(0.2)

    ts = time.strftime("%Y%m%d_%H%M%S")
    _save_cb_json(results, f"sector_matrix_{reporter}_{ts}.json")
    return results


def recipe_exposure_to(target, start="2010", end=None, reporters=None):
    """All-reporters' cross-border claims on a target country (contagion view).

    For each reporter, queries LBS claims where counterparty = target.
    """
    _print_cb_section(f"GLOBAL EXPOSURE TO {_cn(target)} (contagion view)")
    results = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "target": target, "start_period": start,
               "series": {}, "summary": {}}

    if reporters is None:
        extra = ["KY", "JE", "SE", "AT"]
        seen = set()
        reporters = []
        for rep in MAJOR_LBS_REPORTERS + extra:
            if rep not in seen:
                seen.add(rep)
                reporters.append(rep)

    _print_cb_subsection(f"All reporters -> {target}: total cross-border claims")
    all_rep_s = data_query("WS_LBS_D_PUB",
                           key=f"Q.S.C.A.TO1.A.5J.A.5A.A.{target}.N",
                           start_period=start, end_period=end)
    results["series"]["all_reporters_total"] = all_rep_s
    v, p = _latest_value(all_rep_s)
    if v:
        print(f"    Total claims on {target}: {_fmt_usd_bn(v)} ({p})")

    all_rep_usd = data_query("WS_LBS_D_PUB",
                              key=f"Q.S.C.A.USD.A.5J.A.5A.A.{target}.N",
                              start_period=start, end_period=end)
    results["series"]["all_reporters_usd"] = all_rep_usd
    v, p = _latest_value(all_rep_usd)
    if v:
        print(f"    USD claims on {target}:   {_fmt_usd_bn(v)} ({p})")

    all_rep_eur = data_query("WS_LBS_D_PUB",
                              key=f"Q.S.C.A.EUR.A.5J.A.5A.A.{target}.N",
                              start_period=start, end_period=end)
    results["series"]["all_reporters_eur"] = all_rep_eur
    v, p = _latest_value(all_rep_eur)
    if v:
        print(f"    EUR claims on {target}:   {_fmt_usd_bn(v)} ({p})")

    _print_cb_subsection(f"Exposure decomposition by reporter ({len(reporters)} reporters)")
    print(f"    {'Reporter':<22s} {'All CCY Claims':>15s} {'USD Claims':>15s}")
    print(f"    {'-'*22} {'-'*15} {'-'*15}")
    start_time = time.time()
    rows = []
    for i, rep in enumerate(reporters, 1):
        _progress_tick(i, len(reporters), rep, start_time)
        all_s = data_query("WS_LBS_D_PUB",
                           key=f"Q.S.C.A.TO1.A.5J.A.{rep}.A.{target}.N",
                           start_period=start, end_period=end, quiet=True)
        usd_type = "D" if REPORTER_DOMESTIC_CCY.get(rep) == "USD" else "F"
        usd_s = data_query("WS_LBS_D_PUB",
                           key=f"Q.S.C.A.USD.{usd_type}.5J.A.{rep}.A.{target}.N",
                           start_period=start, end_period=end, quiet=True)
        results["series"][f"{rep}_all"] = all_s
        results["series"][f"{rep}_usd"] = usd_s
        av, _ = _latest_value(all_s)
        uv, _ = _latest_value(usd_s)
        if av or uv:
            rows.append((rep, av or 0, uv or 0))
        time.sleep(0.2)

    rows.sort(key=lambda x: -x[1])
    for rep, av, uv in rows:
        print(f"    {_cn(rep):<22s} {_fmt_usd_bn(av):>15s} {_fmt_usd_bn(uv):>15s}")
    results["summary"]["by_reporter"] = {rep: {"all_ccy": av, "usd": uv}
                                          for rep, av, uv in rows}

    _print_cb_subsection(f"Sector breakdown of exposure to {target} (all reporters)")
    print(f"    {'Sector':<32s} {'Claims':>15s}")
    print(f"    {'-'*32} {'-'*15}")
    for sec_code, sec_name in [("B", "Banks"), ("F", "NBFI"),
                                 ("N", "Non-banks total"),
                                 ("C", "Non-financial corps"),
                                 ("G", "General government"),
                                 ("H", "Households")]:
        s = data_query("WS_LBS_D_PUB",
                       key=f"Q.S.C.A.TO1.A.5J.A.5A.{sec_code}.{target}.N",
                       start_period=start, end_period=end, quiet=True)
        v, _ = _latest_value(s)
        if v:
            print(f"    {sec_name:<32s} {_fmt_usd_bn(v):>15s}")
            results["summary"][f"sector_{sec_code}"] = v
        time.sleep(0.2)

    ts = time.strftime("%Y%m%d_%H%M%S")
    _save_cb_json(results, f"exposure_to_{target}_{ts}.json")
    return results


def recipe_usd_funding(reporter="US", start="2010", end=None):
    """USD funding structure for a reporter -- liabilities side.

    Shows USD liabilities by counterparty sector, instrument, counterparty region.
    """
    _print_cb_section(f"USD FUNDING STRUCTURE: {_cn(reporter)}")
    results = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "reporter": reporter, "start_period": start,
               "series": {}, "summary": {}}

    usd_type = "D" if REPORTER_DOMESTIC_CCY.get(reporter) == "USD" else "F"

    _print_cb_subsection(f"{reporter} total USD liabilities (cross-border)")
    total_usd = data_query("WS_LBS_D_PUB",
                            key=f"Q.S.L.A.USD.{usd_type}.5J.A.{reporter}.A.5J.N",
                            start_period=start, end_period=end)
    results["series"]["total_usd_liabs"] = total_usd
    v, p = _latest_value(total_usd)
    if v:
        print(f"    Total USD liabilities: {_fmt_usd_bn(v)} ({p})")

    _print_cb_subsection(f"{reporter} USD liabilities by sector (who funds)")
    print(f"    {'Source sector':<32s} {'USD Liabs':>13s} Period")
    print(f"    {'-'*32} {'-'*13} {'-'*7}")
    for sec_code, sec_name in [("A", "All sectors"), ("B", "Banks"),
                                ("I", "Related offices (intra-group)"),
                                ("N", "Non-banks total"),
                                ("F", "NBFI"), ("M", "Central banks"),
                                ("G", "General government"),
                                ("C", "Non-financial corps"),
                                ("H", "Households")]:
        s = data_query("WS_LBS_D_PUB",
                       key=f"Q.S.L.A.USD.{usd_type}.5J.A.{reporter}.{sec_code}.5J.N",
                       start_period=start, end_period=end, quiet=True)
        results["series"][f"sector_{sec_code}"] = s
        v, p = _latest_value(s)
        if v:
            print(f"    {sec_name:<32s} {_fmt_usd_bn(v):>13s} {p}")
            results["summary"][f"sector_{sec_code}"] = {"value": v, "period": p}
        time.sleep(0.2)

    _print_cb_subsection(f"{reporter} USD liabilities by instrument")
    print(f"    {'Instrument':<30s} {'USD Liabs':>13s} Period")
    print(f"    {'-'*30} {'-'*13} {'-'*7}")
    for instr in ["A", "G", "D", "B", "V"]:
        s = data_query("WS_LBS_D_PUB",
                       key=f"Q.S.L.{instr}.USD.{usd_type}.5J.A.{reporter}.A.5J.N",
                       start_period=start, end_period=end, quiet=True)
        results["series"][f"instr_{instr}"] = s
        v, p = _latest_value(s)
        if v:
            print(f"    {LBS_INSTRUMENTS.get(instr, instr):<30s} "
                  f"{_fmt_usd_bn(v):>13s} {p}")
        time.sleep(0.2)

    ts = time.strftime("%Y%m%d_%H%M%S")
    _save_cb_json(results, f"usd_funding_{reporter}_{ts}.json")
    return results


def recipe_derivatives_crossborder(start="2010", end=None):
    """Cross-border derivatives positions (LBS L_INSTR=V)."""
    _print_cb_section("CROSS-BORDER DERIVATIVES POSITIONS (LBS)")
    results = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "start_period": start, "series": {}, "summary": {}}

    _print_cb_subsection("Global cross-border derivatives (all reporters)")
    global_der_c = data_query("WS_LBS_D_PUB",
                               key="Q.S.C.V.TO1.A.5J.A.5A.A.5J.N",
                               start_period=start, end_period=end)
    global_der_l = data_query("WS_LBS_D_PUB",
                               key="Q.S.L.V.TO1.A.5J.A.5A.A.5J.N",
                               start_period=start, end_period=end)
    results["series"]["global_claims"] = global_der_c
    results["series"]["global_liabs"] = global_der_l
    v, p = _latest_value(global_der_c)
    if v:
        print(f"    Global derivatives claims:    {_fmt_usd_bn(v)} ({p})")
    v, p = _latest_value(global_der_l)
    if v:
        print(f"    Global derivatives liabs:     {_fmt_usd_bn(v)} ({p})")

    _print_cb_subsection("Derivatives cross-border positions by center")
    print(f"    {'Center':<22s} {'Claims':>13s} {'Liabs':>13s} {'Net':>13s}")
    print(f"    {'-'*22} {'-'*13} {'-'*13} {'-'*13}")
    start_time = time.time()
    rows = []
    centers = ["US", "GB", "JP", "DE", "FR", "CH", "HK", "SG", "LU", "IE",
               "NL", "IT", "ES"]
    for i, rep in enumerate(centers, 1):
        _progress_tick(i, len(centers), rep, start_time)
        c = data_query("WS_LBS_D_PUB",
                       key=f"Q.S.C.V.TO1.A.5J.A.{rep}.A.5J.N",
                       start_period=start, end_period=end, quiet=True)
        l = data_query("WS_LBS_D_PUB",
                       key=f"Q.S.L.V.TO1.A.5J.A.{rep}.A.5J.N",
                       start_period=start, end_period=end, quiet=True)
        results["series"][f"{rep}_claims"] = c
        results["series"][f"{rep}_liabs"] = l
        cv, _ = _latest_value(c)
        lv, _ = _latest_value(l)
        cv, lv = cv or 0, lv or 0
        rows.append((rep, cv, lv, cv - lv))
        time.sleep(0.2)

    rows.sort(key=lambda x: -x[1])
    for rep, c, l, n in rows:
        if c == 0 and l == 0:
            continue
        print(f"    {_cn(rep):<22s} {_fmt_usd_bn(c):>13s} "
              f"{_fmt_usd_bn(l):>13s} {_fmt_usd_bn(n):>13s}")

    ts = time.strftime("%Y%m%d_%H%M%S")
    _save_cb_json(results, f"derivatives_crossborder_{ts}.json")
    return results


# ── CBS Consolidated Banking Statistics Recipes ───────────────────────────────

def recipe_cbs_foreign_claims(reporter="US", basis="F", bank_type="4R",
                                start="2010", end=None):
    """CBS foreign claims for a reporting country.

    Key: FREQ.L_MEASURE.L_REP_CTY.CBS_BANK_TYPE.CBS_BASIS.L_POSITION.L_INSTR.REM_MATURITY.CURR_TYPE_BOOK.L_CP_SECTOR.L_CP_COUNTRY

    Args:
        reporter: Reporting country (US, GB, JP, ...) or 5A=all
        basis: F=Immediate counterparty, U=Guarantor basis, R=Guarantor calc
        bank_type: 4R=Domestic banks excl domestic, 4B=Domestic banks all,
                   4M=All banks, 4N=All incl 4C excl domestic
    """
    basis_name = CBS_BASES.get(basis, basis)
    bt_name = CBS_BANK_TYPES.get(bank_type, bank_type)
    _print_cb_section(f"CBS FOREIGN CLAIMS: {_cn(reporter)} ({basis_name}, {bt_name})")
    results = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "reporter": reporter, "basis": basis, "bank_type": bank_type,
               "start_period": start, "series": {}, "summary": {}}

    _print_cb_subsection("Total international claims (position=I)")
    intl_claims = data_query("WS_CBS_PUB",
                              key=f"Q.S.{reporter}.{bank_type}.{basis}.I.A.A.TO1.A.5J",
                              start_period=start, end_period=end)
    results["series"]["intl_claims"] = intl_claims
    v, p = _latest_value(intl_claims)
    if v:
        print(f"    Total international claims: {_fmt_usd_bn(v)} ({p})")
        results["summary"]["intl_claims"] = {"value": v, "period": p}

    _print_cb_subsection("Total claims and cross-border claims")
    total_claims = data_query("WS_CBS_PUB",
                               key=f"Q.S.{reporter}.{bank_type}.{basis}.C.A.A.TO1.A.5J",
                               start_period=start, end_period=end, quiet=True)
    xb_claims = data_query("WS_CBS_PUB",
                            key=f"Q.S.{reporter}.{bank_type}.{basis}.D.A.A.TO1.A.5J",
                            start_period=start, end_period=end, quiet=True)
    local_claims = data_query("WS_CBS_PUB",
                               key=f"Q.S.{reporter}.{bank_type}.{basis}.B.A.A.TO1.A.5J",
                               start_period=start, end_period=end, quiet=True)
    results["series"]["total_claims"] = total_claims
    results["series"]["xb_claims"] = xb_claims
    results["series"]["local_claims"] = local_claims
    v, p = _latest_value(total_claims)
    if v:
        print(f"    Total claims:        {_fmt_usd_bn(v)} ({p})")
    v, p = _latest_value(xb_claims)
    if v:
        print(f"    Cross-border only:   {_fmt_usd_bn(v)} ({p})")
    v, p = _latest_value(local_claims)
    if v:
        print(f"    Local claims:        {_fmt_usd_bn(v)} ({p})")

    _print_cb_subsection("By counterparty sector")
    print(f"    {'Sector':<32s} {'Intl Claims':>13s} Period")
    print(f"    {'-'*32} {'-'*13} {'-'*7}")
    for sec_code, sec_name in [("A", "All sectors"), ("B", "Banks"),
                                 ("F", "NBFI"), ("C", "Non-financial corps"),
                                 ("H", "Households"), ("O", "Official sector"),
                                 ("R", "Non-bank private")]:
        s = data_query("WS_CBS_PUB",
                       key=f"Q.S.{reporter}.{bank_type}.{basis}.I.A.A.TO1.{sec_code}.5J",
                       start_period=start, end_period=end, quiet=True)
        results["series"][f"sector_{sec_code}"] = s
        v, p = _latest_value(s)
        if v:
            print(f"    {sec_name:<32s} {_fmt_usd_bn(v):>13s} {p}")
            results["summary"][f"sector_{sec_code}"] = {"value": v, "period": p}
        time.sleep(0.2)

    ts = time.strftime("%Y%m%d_%H%M%S")
    _save_cb_json(results, f"cbs_foreign_claims_{reporter}_{basis}_{ts}.json")
    return results


def recipe_cbs_exposure_to(target, basis="F", bank_type="4R",
                             start="2010", end=None):
    """CBS exposure to a specific target country from all reporters."""
    basis_name = CBS_BASES.get(basis, basis)
    _print_cb_section(f"CBS EXPOSURE TO {_cn(target)} ({basis_name})")
    results = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "target": target, "basis": basis, "bank_type": bank_type,
               "start_period": start, "series": {}, "summary": {}}

    _print_cb_subsection(f"All reporters -> {target}: international claims")
    all_rep = data_query("WS_CBS_PUB",
                          key=f"Q.S.5A.{bank_type}.{basis}.I.A.A.TO1.A.{target}",
                          start_period=start, end_period=end)
    results["series"]["all_reporters_intl"] = all_rep
    v, p = _latest_value(all_rep)
    if v:
        print(f"    Total int'l claims: {_fmt_usd_bn(v)} ({p})")

    _print_cb_subsection(f"Breakdown by reporter")
    print(f"    {'Reporter':<22s} {'Intl Claims':>13s} Period")
    print(f"    {'-'*22} {'-'*13} {'-'*7}")

    start_time = time.time()
    reporters = ["US", "GB", "JP", "DE", "FR", "CH", "ES", "IT", "NL",
                 "CA", "AU", "SE", "AT", "BE", "HK", "SG", "IE", "LU"]
    rows = []
    for i, rep in enumerate(reporters, 1):
        _progress_tick(i, len(reporters), rep, start_time)
        s = data_query("WS_CBS_PUB",
                       key=f"Q.S.{rep}.{bank_type}.{basis}.I.A.A.TO1.A.{target}",
                       start_period=start, end_period=end, quiet=True)
        results["series"][f"{rep}_intl"] = s
        v, p = _latest_value(s)
        if v:
            rows.append((rep, v, p))
        time.sleep(0.2)

    rows.sort(key=lambda x: -x[1])
    for rep, v, p in rows:
        print(f"    {_cn(rep):<22s} {_fmt_usd_bn(v):>13s} {p}")
    results["summary"]["by_reporter"] = {rep: {"value": v, "period": p}
                                          for rep, v, p in rows}

    ts = time.strftime("%Y%m%d_%H%M%S")
    _save_cb_json(results, f"cbs_exposure_to_{target}_{ts}.json")
    return results


def recipe_cbs_maturity(reporter="US", basis="F", bank_type="4R",
                         start="2010", end=None):
    """CBS remaining maturity breakdown for a reporter.

    REM_MATURITY: A=All, U=Up to 1yr, M=Over 1 to 2yr, N=Over 2yr.
    """
    _print_cb_section(f"CBS MATURITY BREAKDOWN: {_cn(reporter)}")
    results = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "reporter": reporter, "basis": basis, "bank_type": bank_type,
               "start_period": start, "series": {}, "summary": {}}

    _print_cb_subsection(f"{reporter} international claims by remaining maturity")
    print(f"    {'Maturity':<28s} {'Claims':>13s} Period")
    print(f"    {'-'*28} {'-'*13} {'-'*7}")
    for mat_code, mat_name in CBS_MATURITIES.items():
        s = data_query("WS_CBS_PUB",
                       key=f"Q.S.{reporter}.{bank_type}.{basis}.I.A.{mat_code}.TO1.A.5J",
                       start_period=start, end_period=end, quiet=True)
        results["series"][f"mat_{mat_code}"] = s
        v, p = _latest_value(s)
        if v:
            print(f"    {mat_name:<28s} {_fmt_usd_bn(v):>13s} {p}")
            results["summary"][mat_code] = {"value": v, "period": p,
                                             "name": mat_name}
        time.sleep(0.2)

    ts = time.strftime("%Y%m%d_%H%M%S")
    _save_cb_json(results, f"cbs_maturity_{reporter}_{ts}.json")
    return results


def recipe_cbs_guarantor_diff(reporter="US", start="2010", end=None):
    """Compare CBS immediate counterparty basis vs guarantor basis.

    Difference shows where risk actually sits after guarantees/risk transfers.
    """
    _print_cb_section(f"CBS IMMEDIATE vs GUARANTOR BASIS: {_cn(reporter)}")
    results = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "reporter": reporter, "start_period": start,
               "series": {}, "summary": {}}

    print(f"    {'Counterparty':<22s} {'Immediate (F)':>15s} "
          f"{'Guarantor (U)':>15s} {'Diff':>15s}")
    print(f"    {'-'*22} {'-'*15} {'-'*15} {'-'*15}")

    targets = ["5J", "5C", "US", "GB", "JP", "CN", "TR", "BR", "MX",
               "KR", "IN", "RU", "ZA", "4T", "4U", "4W", "4Y"]
    for target in targets:
        f_s = data_query("WS_CBS_PUB",
                         key=f"Q.S.{reporter}.4R.F.I.A.A.TO1.A.{target}",
                         start_period=start, end_period=end, quiet=True)
        u_s = data_query("WS_CBS_PUB",
                         key=f"Q.S.{reporter}.4R.U.I.A.A.TO1.A.{target}",
                         start_period=start, end_period=end, quiet=True)
        results["series"][f"{target}_immediate"] = f_s
        results["series"][f"{target}_guarantor"] = u_s

        fv, _ = _latest_value(f_s)
        uv, _ = _latest_value(u_s)
        fv, uv = fv or 0, uv or 0
        diff = uv - fv
        if fv or uv:
            print(f"    {_cn(target):<22s} {_fmt_usd_bn(fv):>15s} "
                  f"{_fmt_usd_bn(uv):>15s} {_fmt_usd_bn(diff):>15s}")
            results["summary"][target] = {"immediate": fv, "guarantor": uv,
                                           "diff": diff}
        time.sleep(0.2)

    ts = time.strftime("%Y%m%d_%H%M%S")
    _save_cb_json(results, f"cbs_guarantor_diff_{reporter}_{ts}.json")
    return results


# ── GLI Global Liquidity Recipes ──────────────────────────────────────────────

def recipe_gli_currency(currency="USD", start="2010", end=None, regions=None):
    """GLI: credit to non-residents by currency.

    Key: FREQ.CURR_DENOM.BORROWERS_CTY.BORROWERS_SECTOR.LENDERS_SECTOR.L_POS_TYPE.L_INSTR.UNIT_MEASURE
    """
    _print_cb_section(f"GLOBAL LIQUIDITY: {currency} credit to non-residents")
    results = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "currency": currency, "start_period": start,
               "series": {}, "summary": {}}

    global_region = "3P"

    if regions is None:
        regions = ["3P", "4T", "4U", "4W", "4Y", "CN", "BR", "IN", "MX",
                   "TR", "ID", "RU", "ZA"]

    _print_cb_subsection(f"Global {currency} credit to non-banks ({global_region})")
    for instr_code, instr_name in [("B", "Total credit"),
                                     ("G", "Bank loans"),
                                     ("D", "Debt securities")]:
        s = data_query("WS_GLI",
                       key=f"Q.{currency}.{global_region}.N.A.I.{instr_code}.{currency}",
                       start_period=start, end_period=end, quiet=True)
        results["series"][f"global_{instr_code}"] = s
        v, p = _latest_value(s)
        if v:
            print(f"    {instr_name:<20s}: {_fmt_usd_bn(v)} ({p})")
            results["summary"][f"global_{instr_code}"] = {"value": v, "period": p}
        time.sleep(0.2)

    _print_cb_subsection(f"YoY growth in global {currency} credit")
    growth = data_query("WS_GLI",
                         key=f"Q.{currency}.{global_region}.N.A.I.B.771",
                         start_period=start, end_period=end)
    results["series"]["global_growth_yoy"] = growth
    if growth:
        obs = growth[0].get("observations", {})
        recent = sorted(obs.keys())[-8:]
        for period in recent:
            v = _to_num(obs[period])
            if v is not None:
                print(f"    {period}: {v:+.1f}%")

    _print_cb_subsection(f"{currency} credit by region/country")
    print(f"    {'Region':<32s} {'Credit':>13s} Period")
    print(f"    {'-'*32} {'-'*13} {'-'*7}")
    for region in regions:
        s = data_query("WS_GLI",
                       key=f"Q.{currency}.{region}.N.A.I.B.{currency}",
                       start_period=start, end_period=end, quiet=True)
        results["series"][f"region_{region}"] = s
        v, p = _latest_value(s)
        if v:
            print(f"    {_cn(region):<32s} {_fmt_usd_bn(v):>13s} {p}")
            results["summary"][region] = {"value": v, "period": p}
        time.sleep(0.2)

    ts = time.strftime("%Y%m%d_%H%M%S")
    _save_cb_json(results, f"gli_{currency}_{ts}.json")
    return results


def recipe_gli_all_currencies(start="2010", end=None):
    """Compare USD, EUR, JPY credit to non-residents."""
    _print_cb_section("GLOBAL LIQUIDITY: USD vs EUR vs JPY credit to non-residents")
    results = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "start_period": start, "series": {}, "summary": {}}

    _print_cb_subsection("Total credit to non-banks by currency (outstanding, native units)")
    for currency in ["USD", "EUR", "JPY"]:
        # BIS GLI outstanding uses the currency itself as UNIT_MEASURE
        s = data_query("WS_GLI",
                       key=f"Q.{currency}.3P.N.A.I.B.{currency}",
                       start_period=start, end_period=end, quiet=True)
        results["series"][f"{currency}_credit"] = s
        v, p = _latest_value(s)
        if v:
            unit_suffix = {"USD": "USD", "EUR": "EUR", "JPY": "JPY"}[currency]
            print(f"    {currency} credit: {v:,.0f} {unit_suffix} mn ({p})")
            results["summary"][currency] = {"value": v, "period": p,
                                             "unit": unit_suffix}
        time.sleep(0.2)

    _print_cb_subsection("YoY growth by currency")
    for currency in ["USD", "EUR", "JPY"]:
        s = data_query("WS_GLI",
                       key=f"Q.{currency}.3P.N.A.I.B.771",
                       start_period=start, end_period=end, quiet=True)
        results["series"][f"{currency}_growth"] = s
        if s:
            obs = s[0].get("observations", {})
            recent = sorted(obs.keys())[-1:]
            if recent:
                v = _to_num(obs[recent[0]])
                if v is not None:
                    print(f"    {currency}: {v:+.1f}% ({recent[0]})")

    ts = time.strftime("%Y%m%d_%H%M%S")
    _save_cb_json(results, f"gli_all_currencies_{ts}.json")
    return results


# ── Composite Shadow Banking Recipes ──────────────────────────────────────────

def recipe_shadow_banking_full(start="2010", end=None):
    """Comprehensive shadow banking / cross-border banking analysis.

    Runs all major shadow banking analysis modules in sequence.
    """
    _print_cb_section("SHADOW BANKING & CROSS-BORDER BANKING -- FULL ANALYSIS")
    master_start = time.time()
    all_results = {"generated_at": datetime.now(timezone.utc).isoformat(),
                   "start_period": start, "modules": {}}

    modules = [
        ("eurodollar", "Eurodollar system", lambda: recipe_eurodollar(start, end)),
        ("nbfi", "Non-bank financial intermediation", lambda: recipe_nbfi(start, end)),
        ("interbank_usd", "USD interbank / repo proxy",
         lambda: recipe_interbank("USD", start, end)),
        ("offshore_centers", "Offshore center intermediation",
         lambda: recipe_offshore_centers(start, end)),
        ("fcy_mismatch", "Currency mismatch",
         lambda: recipe_fcy_mismatch(start, end)),
        ("derivatives", "Cross-border derivatives",
         lambda: recipe_derivatives_crossborder(start, end)),
        ("gli_usd", "USD global liquidity",
         lambda: recipe_gli_currency("USD", start, end)),
        ("gli_all", "All-currency global liquidity",
         lambda: recipe_gli_all_currencies(start, end)),
    ]

    for key, name, func in modules:
        elapsed = time.time() - master_start
        print(f"\n\n  >>> Starting module: {name} [{elapsed:.0f}s elapsed]")
        try:
            all_results["modules"][key] = func()
        except Exception as e:
            print(f"  ERROR in {name}: {e}")
            import traceback
            traceback.print_exc()
            all_results["modules"][key] = {"error": str(e)}

    total = time.time() - master_start
    print(f"\n\n{'='*78}")
    print(f"  SHADOW BANKING FULL ANALYSIS COMPLETE")
    print(f"  Total elapsed: {total:.0f}s ({total/60:.1f}min)")
    print(f"{'='*78}")

    ts = time.strftime("%Y%m%d_%H%M%S")
    _save_cb_json(all_results, f"shadow_banking_full_{ts}.json")
    return all_results


def recipe_contagion(target="TR", start="2010", end=None):
    """Full contagion analysis: exposure to stressed country across all lenses.

    Combines LBS exposure, CBS exposure (immediate + guarantor),
    and USD-denominated exposure.
    """
    _print_cb_section(f"CONTAGION ANALYSIS: Global exposure to {_cn(target)}")
    results = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "target": target, "start_period": start, "modules": {}}

    print(f"\n>>> 1. LBS exposure (locational, who lends from where)")
    results["modules"]["lbs_exposure"] = recipe_exposure_to(target, start, end)

    print(f"\n>>> 2. CBS exposure immediate counterparty (who's exposed by HQ)")
    results["modules"]["cbs_immediate"] = recipe_cbs_exposure_to(
        target, basis="F", start=start, end=end)

    print(f"\n>>> 3. CBS exposure guarantor basis (ultimate risk)")
    try:
        results["modules"]["cbs_guarantor"] = recipe_cbs_exposure_to(
            target, basis="U", start=start, end=end)
    except Exception as e:
        print(f"    CBS guarantor basis not available: {e}")
        results["modules"]["cbs_guarantor"] = {"error": str(e)}

    ts = time.strftime("%Y%m%d_%H%M%S")
    _save_cb_json(results, f"contagion_{target}_{ts}.json")
    return results


def recipe_eurodollar_system(start="2010", end=None):
    """Dedicated eurodollar system analysis (alias for recipe_eurodollar with full reporter list).

    Includes global USD + FCY positions + intragroup + interbank + GLI.
    """
    _print_cb_section("EURODOLLAR SYSTEM -- Full Analysis")
    master_start = time.time()
    results = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "start_period": start, "modules": {}}

    reporters_full = ["GB", "JP", "FR", "DE", "CH", "HK", "SG", "CA", "AU",
                      "NL", "IE", "LU", "US", "KY", "JE", "BH", "PA", "BS",
                      "BM", "IT", "ES", "SE", "BE", "AT"]

    print(f"\n>>> 1. Eurodollar positions (global + per-center)")
    results["modules"]["eurodollar"] = recipe_eurodollar(
        start, end, reporters=reporters_full)

    print(f"\n>>> 2. USD interbank (repo/money market proxy)")
    results["modules"]["interbank_usd"] = recipe_interbank("USD", start, end)

    print(f"\n>>> 3. GLI: USD credit to non-residents")
    results["modules"]["gli_usd"] = recipe_gli_currency("USD", start, end)

    total = time.time() - master_start
    print(f"\n\n{'='*78}")
    print(f"  EURODOLLAR SYSTEM ANALYSIS COMPLETE ({total:.0f}s)")
    print(f"{'='*78}")

    ts = time.strftime("%Y%m%d_%H%M%S")
    _save_cb_json(results, f"eurodollar_system_{ts}.json")
    return results


def _cmd_data_query(dataflow, key="all", start=None, end=None, save=True):
    """Generic data query command."""
    print(f"\n=== BIS Data Query: {dataflow} / {key} ===\n")
    series = data_query(dataflow, key=key, start_period=start, end_period=end)
    _format_series_table(series, max_series=30, last_n_periods=12)
    if save and series:
        flow_id = DATAFLOW_ALIASES.get(dataflow, dataflow)
        ts = time.strftime("%Y%m%d_%H%M%S")
        _save_data_json(
            {"query": f"{flow_id}/{key}", "start": start, "end": end, "series": series},
            f"query_{flow_id}_{ts}.json")
    return series


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="BIS Data Ontology Scraper, Explorer & Data Query Engine")
    subparsers = parser.add_subparsers(dest="command")

    scrape_p = subparsers.add_parser("scrape", help="Scrape full BIS ontology from SDMX API")
    scrape_p.add_argument("--output", "-o", help="Output JSON path")
    scrape_p.add_argument("--skip-existing", action="store_true", help="Skip if output already exists")

    explore_p = subparsers.add_parser("explore", help="Interactively explore the ontology")
    explore_p.add_argument("--input", "-i", help="Path to ontology JSON")

    deep_p = subparsers.add_parser("deep-index", help="Build deep LBS cross-border index")
    deep_p.add_argument("--output", "-o", help="Output JSON path")

    query_p = subparsers.add_parser("query", help="Query BIS time series data")
    query_p.add_argument("dataflow", help="Dataflow ID or alias (e.g. policy-rates, credit, lbs)")
    query_p.add_argument("--key", "-k", default="all", help="Dimension key filter (default: all)")
    query_p.add_argument("--start", "-s", help="Start period (e.g. 2020, 2020-Q1)")
    query_p.add_argument("--end", "-e", help="End period")

    sub_pr = subparsers.add_parser("policy-rates", help="Central bank policy rates")
    sub_pr.add_argument("--countries", default="US+GB+JP+DE+CH+CA+AU+SE+NO+NZ")
    sub_pr.add_argument("--start", default="2000")

    sub_tc = subparsers.add_parser("total-credit", help="Total credit to non-financial sector")
    sub_tc.add_argument("--countries", default="US+GB+JP+DE+FR+CN+CA+AU")
    sub_tc.add_argument("--start", default="2000")

    sub_cg = subparsers.add_parser("credit-gap", help="Credit-to-GDP gaps")
    sub_cg.add_argument("--countries", default="US+GB+JP+DE+FR+CN+CA+AU")
    sub_cg.add_argument("--start", default="2000")

    sub_dsr = subparsers.add_parser("dsr", help="Debt service ratios")
    sub_dsr.add_argument("--countries", default="US+GB+JP+DE+FR+CN+CA+AU")
    sub_dsr.add_argument("--start", default="2000")

    sub_pp = subparsers.add_parser("property-prices", help="Residential property prices")
    sub_pp.add_argument("--countries", default="US+GB+JP+DE+FR+CN+CA+AU+NZ+SE+NO+KR")
    sub_pp.add_argument("--start", default="2000")

    sub_eer = subparsers.add_parser("eer", help="Effective exchange rates")
    sub_eer.add_argument("--countries", default="US+GB+JP+DE+FR+CN+CH+CA+AU+SE+NO+NZ+KR+IN+BR+MX")
    sub_eer.add_argument("--start", default="2000")

    sub_gli = subparsers.add_parser("global-liquidity", help="Global liquidity indicators")
    sub_gli.add_argument("--start", default="2010")

    sub_lbs = subparsers.add_parser("lbs", help="Locational banking cross-border data")
    sub_lbs.add_argument("--reporter", default="US", help="Reporting country (default: US)")
    sub_lbs.add_argument("--position", default="C", choices=["C", "L"], help="Claims or Liabilities")
    sub_lbs.add_argument("--start", default="2010")

    # ── Cross-Border Banking & Shadow Banking Subcommands ──────────────────────

    sub_bilat = subparsers.add_parser("lbs-bilateral",
        help="LBS bilateral query (reporter -> counterparty)")
    sub_bilat.add_argument("--reporter", default="US")
    sub_bilat.add_argument("--counterparty", default="CN")
    sub_bilat.add_argument("--currency", default="TO1",
        help="TO1=All, USD, EUR, GBP, JPY, CHF, TO3=FCY only")
    sub_bilat.add_argument("--sector", default="A",
        help="A=All, B=Banks, N=Non-banks, F=NBFI, C=Corps, G=Govt, H=Households")
    sub_bilat.add_argument("--instrument", default="A",
        help="A=All, G=Loans+Deposits, D=Debt securities, B=Credit, V=Derivatives")
    sub_bilat.add_argument("--position", default="C",
        help="C=Claims, L=Liabilities, N=Net")
    sub_bilat.add_argument("--pos-type", default="N",
        help="N=Cross-border, R=Local, I=XB+Local FCY, A=All", dest="pos_type")
    sub_bilat.add_argument("--start", default="2010")
    sub_bilat.add_argument("--end", default=None)

    sub_eur = subparsers.add_parser("eurodollar",
        help="Eurodollar system: USD + FCY cross-border claims/liabilities")
    sub_eur.add_argument("--reporters", default=None,
        help="+-separated reporter ISOs (default: major offshore + major onshore)")
    sub_eur.add_argument("--start", default="2010")
    sub_eur.add_argument("--end", default=None)

    sub_nbfi = subparsers.add_parser("nbfi",
        help="Non-bank financial intermediation (shadow banking) cross-border")
    sub_nbfi.add_argument("--reporters", default=None,
        help="+-separated reporter ISOs")
    sub_nbfi.add_argument("--start", default="2010")
    sub_nbfi.add_argument("--end", default=None)

    sub_ibk = subparsers.add_parser("interbank",
        help="Interbank loans & deposits (repo/money market proxy) + intra-group")
    sub_ibk.add_argument("--currency", default="USD",
        help="USD, EUR, JPY, GBP, CHF, TO1")
    sub_ibk.add_argument("--reporters", default=None)
    sub_ibk.add_argument("--start", default="2010")
    sub_ibk.add_argument("--end", default=None)

    sub_off = subparsers.add_parser("offshore-centers",
        help="Offshore center intermediation (GB, HK, SG, KY, LU, IE, JE, ...)")
    sub_off.add_argument("--centers", default=None,
        help="+-separated ISO codes (default: core offshore centers)")
    sub_off.add_argument("--start", default="2010")
    sub_off.add_argument("--end", default=None)

    sub_nat = subparsers.add_parser("bank-nationality",
        help="Bank nationality breakdown by parent country (global aggregate)")
    sub_nat.add_argument("--host", default="5A",
        help="Host/reporter country (default: 5A=all, since BIS publishes L_PARENT_CTY "
             "breakdowns only at the 5A aggregate level)")
    sub_nat.add_argument("--parents", default=None,
        help="+-separated parent country ISOs")
    sub_nat.add_argument("--start", default="2010")
    sub_nat.add_argument("--end", default=None)

    sub_ccy = subparsers.add_parser("currency-breakdown",
        help="Currency split of cross-border claims for a reporter")
    sub_ccy.add_argument("--reporter", default="US")
    sub_ccy.add_argument("--start", default="2010")
    sub_ccy.add_argument("--end", default=None)

    sub_fcy = subparsers.add_parser("fcy-mismatch",
        help="Foreign vs domestic currency positions by reporter")
    sub_fcy.add_argument("--reporters", default=None)
    sub_fcy.add_argument("--start", default="2010")
    sub_fcy.add_argument("--end", default=None)

    sub_smat = subparsers.add_parser("sector-matrix",
        help="Counterparty sector breakdown for a reporter")
    sub_smat.add_argument("--reporter", default="US")
    sub_smat.add_argument("--start", default="2010")
    sub_smat.add_argument("--end", default=None)

    sub_exp = subparsers.add_parser("exposure-to",
        help="All-reporters exposure to a target country (contagion)")
    sub_exp.add_argument("--target", default="TR")
    sub_exp.add_argument("--reporters", default=None)
    sub_exp.add_argument("--start", default="2010")
    sub_exp.add_argument("--end", default=None)

    sub_fund = subparsers.add_parser("usd-funding",
        help="USD funding structure (liabilities) for a reporter")
    sub_fund.add_argument("--reporter", default="US")
    sub_fund.add_argument("--start", default="2010")
    sub_fund.add_argument("--end", default=None)

    sub_der = subparsers.add_parser("derivatives-crossborder",
        help="Cross-border derivatives positions (LBS)")
    sub_der.add_argument("--start", default="2010")
    sub_der.add_argument("--end", default=None)

    sub_cbs_fc = subparsers.add_parser("cbs-foreign-claims",
        help="CBS foreign claims for a reporter")
    sub_cbs_fc.add_argument("--reporter", default="US")
    sub_cbs_fc.add_argument("--basis", default="F",
        help="F=Immediate counterparty, U=Guarantor, R=Guarantor calculated")
    sub_cbs_fc.add_argument("--bank-type", default="4R",
        help="4R=Domestic banks excl domestic, 4B=Domestic (all), 4M=All banks",
        dest="bank_type")
    sub_cbs_fc.add_argument("--start", default="2010")
    sub_cbs_fc.add_argument("--end", default=None)

    sub_cbs_exp = subparsers.add_parser("cbs-exposure-to",
        help="CBS: all reporters exposure to a target country")
    sub_cbs_exp.add_argument("--target", default="TR")
    sub_cbs_exp.add_argument("--basis", default="F")
    sub_cbs_exp.add_argument("--bank-type", default="4R", dest="bank_type")
    sub_cbs_exp.add_argument("--start", default="2010")
    sub_cbs_exp.add_argument("--end", default=None)

    sub_cbs_mat = subparsers.add_parser("cbs-maturity",
        help="CBS remaining maturity breakdown")
    sub_cbs_mat.add_argument("--reporter", default="US")
    sub_cbs_mat.add_argument("--basis", default="F")
    sub_cbs_mat.add_argument("--bank-type", default="4R", dest="bank_type")
    sub_cbs_mat.add_argument("--start", default="2010")
    sub_cbs_mat.add_argument("--end", default=None)

    sub_cbs_gd = subparsers.add_parser("cbs-guarantor-diff",
        help="Compare CBS immediate vs guarantor basis")
    sub_cbs_gd.add_argument("--reporter", default="US")
    sub_cbs_gd.add_argument("--start", default="2010")
    sub_cbs_gd.add_argument("--end", default=None)

    sub_gli_c = subparsers.add_parser("gli-currency",
        help="Global liquidity: credit to non-residents by currency")
    sub_gli_c.add_argument("--currency", default="USD",
        help="USD, EUR, JPY, TO1 (total)")
    sub_gli_c.add_argument("--regions", default=None,
        help="+-separated region/country codes")
    sub_gli_c.add_argument("--start", default="2010")
    sub_gli_c.add_argument("--end", default=None)

    sub_gli_all = subparsers.add_parser("gli-all",
        help="Compare USD/EUR/JPY global liquidity")
    sub_gli_all.add_argument("--start", default="2010")
    sub_gli_all.add_argument("--end", default=None)

    sub_sbf = subparsers.add_parser("shadow-banking-full",
        help="Full composite shadow banking analysis (8 modules)")
    sub_sbf.add_argument("--start", default="2010")
    sub_sbf.add_argument("--end", default=None)

    sub_cont = subparsers.add_parser("contagion",
        help="Contagion analysis: LBS + CBS exposure to target country")
    sub_cont.add_argument("--target", default="TR")
    sub_cont.add_argument("--start", default="2010")
    sub_cont.add_argument("--end", default=None)

    sub_eurs = subparsers.add_parser("eurodollar-system",
        help="Full eurodollar system analysis (LBS + interbank + GLI)")
    sub_eurs.add_argument("--start", default="2010")
    sub_eurs.add_argument("--end", default=None)

    args = parser.parse_args()

    if args.command == "scrape":
        scrape_full_ontology(output_path=args.output, skip_existing=args.skip_existing)
    elif args.command == "explore":
        explore_ontology(ontology_path=args.input)
    elif args.command == "deep-index":
        deep_index_lbs(output_path=args.output)
    elif args.command == "query":
        _cmd_data_query(args.dataflow, key=args.key, start=args.start, end=args.end)
    elif args.command == "policy-rates":
        recipe_policy_rates(countries=args.countries, start=args.start)
    elif args.command == "total-credit":
        recipe_total_credit(countries=args.countries, start=args.start)
    elif args.command == "credit-gap":
        recipe_credit_gap(countries=args.countries, start=args.start)
    elif args.command == "dsr":
        recipe_dsr(countries=args.countries, start=args.start)
    elif args.command == "property-prices":
        recipe_property_prices(countries=args.countries, start=args.start)
    elif args.command == "eer":
        recipe_eer(countries=args.countries, start=args.start)
    elif args.command == "global-liquidity":
        recipe_global_liquidity(start=args.start)
    elif args.command == "lbs":
        recipe_lbs_crossborder(reporter=args.reporter, position=args.position, start=args.start)
    elif args.command == "lbs-bilateral":
        recipe_lbs_bilateral(reporter=args.reporter, counterparty=args.counterparty,
                              currency=args.currency, sector=args.sector,
                              instrument=args.instrument, position=args.position,
                              pos_type=args.pos_type, start=args.start, end=args.end)
    elif args.command == "eurodollar":
        reporters = args.reporters.split("+") if args.reporters else None
        recipe_eurodollar(start=args.start, end=args.end, reporters=reporters)
    elif args.command == "nbfi":
        reporters = args.reporters.split("+") if args.reporters else None
        recipe_nbfi(start=args.start, end=args.end, reporters=reporters)
    elif args.command == "interbank":
        reporters = args.reporters.split("+") if args.reporters else None
        recipe_interbank(currency=args.currency, start=args.start, end=args.end,
                          reporters=reporters)
    elif args.command == "offshore-centers":
        centers = args.centers.split("+") if args.centers else None
        recipe_offshore_centers(start=args.start, end=args.end, centers=centers)
    elif args.command == "bank-nationality":
        parents = args.parents.split("+") if args.parents else None
        recipe_bank_nationality(host=args.host, start=args.start, end=args.end,
                                  parents=parents)
    elif args.command == "currency-breakdown":
        recipe_currency_breakdown(reporter=args.reporter, start=args.start, end=args.end)
    elif args.command == "fcy-mismatch":
        reporters = args.reporters.split("+") if args.reporters else None
        recipe_fcy_mismatch(start=args.start, end=args.end, reporters=reporters)
    elif args.command == "sector-matrix":
        recipe_sector_matrix(reporter=args.reporter, start=args.start, end=args.end)
    elif args.command == "exposure-to":
        reporters = args.reporters.split("+") if args.reporters else None
        recipe_exposure_to(target=args.target, start=args.start, end=args.end,
                            reporters=reporters)
    elif args.command == "usd-funding":
        recipe_usd_funding(reporter=args.reporter, start=args.start, end=args.end)
    elif args.command == "derivatives-crossborder":
        recipe_derivatives_crossborder(start=args.start, end=args.end)
    elif args.command == "cbs-foreign-claims":
        recipe_cbs_foreign_claims(reporter=args.reporter, basis=args.basis,
                                    bank_type=args.bank_type, start=args.start,
                                    end=args.end)
    elif args.command == "cbs-exposure-to":
        recipe_cbs_exposure_to(target=args.target, basis=args.basis,
                                 bank_type=args.bank_type, start=args.start,
                                 end=args.end)
    elif args.command == "cbs-maturity":
        recipe_cbs_maturity(reporter=args.reporter, basis=args.basis,
                              bank_type=args.bank_type, start=args.start,
                              end=args.end)
    elif args.command == "cbs-guarantor-diff":
        recipe_cbs_guarantor_diff(reporter=args.reporter, start=args.start,
                                    end=args.end)
    elif args.command == "gli-currency":
        regions = args.regions.split("+") if args.regions else None
        recipe_gli_currency(currency=args.currency, start=args.start,
                              end=args.end, regions=regions)
    elif args.command == "gli-all":
        recipe_gli_all_currencies(start=args.start, end=args.end)
    elif args.command == "shadow-banking-full":
        recipe_shadow_banking_full(start=args.start, end=args.end)
    elif args.command == "contagion":
        recipe_contagion(target=args.target, start=args.start, end=args.end)
    elif args.command == "eurodollar-system":
        recipe_eurodollar_system(start=args.start, end=args.end)
    else:
        interactive_menu()


def interactive_menu():
    while True:
        print("\n" + "=" * 70)
        print("BIS Data: Ontology, Cross-Border Banking & Data Query Engine")
        print("=" * 70)
        print()
        print("  Ontology & Metadata")
        print("     1) Scrape full BIS ontology from SDMX API")
        print("     2) Explore existing ontology")
        print("     3) Scrape + Explore")
        print("     4) Deep-index LBS (cross-border relations)")
        print("     5) Full pipeline (scrape + deep-index)")
        print()
        print("  Core Data Queries (time series)")
        print("    10) Central bank policy rates")
        print("    11) Total credit to non-financial sector")
        print("    12) Credit-to-GDP gaps")
        print("    13) Debt service ratios")
        print("    14) Residential property prices")
        print("    15) Effective exchange rates (REER/NEER)")
        print("    16) Global liquidity indicators (basic)")
        print("    17) LBS cross-border banking (basic reporter view)")
        print("    18) Custom data query (any dataflow + key)")
        print()
        print("  Cross-Border Banking & Shadow Banking (LBS)")
        print("    30) LBS Bilateral (reporter -> counterparty)")
        print("    31) Eurodollar system (USD + FCY cross-border)")
        print("    32) Non-bank financial intermediation (NBFI / shadow)")
        print("    33) Interbank & intra-group (repo/money market proxy)")
        print("    34) Offshore center intermediation (GB, HK, SG, KY, LU...)")
        print("    35) Bank nationality breakdown (who owns host pipes)")
        print("    36) Currency breakdown (USD/EUR/JPY/GBP/CHF by reporter)")
        print("    37) Currency mismatch (domestic vs foreign) by reporter")
        print("    38) Sector matrix (counterparty sector breakdown)")
        print("    39) Exposure TO target country (contagion view)")
        print("    40) USD funding structure (liabilities for a reporter)")
        print("    41) Cross-border derivatives positions (LBS)")
        print()
        print("  Consolidated Banking Statistics (CBS, nationality basis)")
        print("    50) CBS foreign claims for a reporter")
        print("    51) CBS exposure TO a target country")
        print("    52) CBS remaining maturity breakdown")
        print("    53) CBS immediate vs guarantor basis diff")
        print()
        print("  Global Liquidity (GLI)")
        print("    60) GLI by currency (USD/EUR/JPY credit to non-residents)")
        print("    61) GLI all-currency comparison")
        print()
        print("  Composite Analyses")
        print("    70) Shadow banking FULL (8 modules, ~5-10min)")
        print("    71) Contagion analysis (LBS + CBS for target country)")
        print("    72) Eurodollar system FULL (LBS + interbank + GLI)")
        print()
        print("     q) Quit")
        print()
        choice = input("Select: ").strip().lower()
        if choice == "q":
            break
        elif choice == "1":
            scrape_full_ontology()
        elif choice == "2":
            explore_ontology()
        elif choice == "3":
            scrape_full_ontology()
            explore_ontology()
        elif choice == "4":
            deep_index_lbs()
        elif choice == "5":
            scrape_full_ontology()
            deep_index_lbs()
        elif choice == "10":
            countries = input("  Countries [US+GB+JP+DE+CH+CA+AU+SE+NO+NZ]: ").strip() or "US+GB+JP+DE+CH+CA+AU+SE+NO+NZ"
            start = input("  Start period [2000]: ").strip() or "2000"
            recipe_policy_rates(countries=countries, start=start)
        elif choice == "11":
            countries = input("  Countries [US+GB+JP+DE+FR+CN+CA+AU]: ").strip() or "US+GB+JP+DE+FR+CN+CA+AU"
            start = input("  Start period [2000]: ").strip() or "2000"
            recipe_total_credit(countries=countries, start=start)
        elif choice == "12":
            countries = input("  Countries [US+GB+JP+DE+FR+CN+CA+AU]: ").strip() or "US+GB+JP+DE+FR+CN+CA+AU"
            start = input("  Start period [2000]: ").strip() or "2000"
            recipe_credit_gap(countries=countries, start=start)
        elif choice == "13":
            countries = input("  Countries [US+GB+JP+DE+FR+CN+CA+AU]: ").strip() or "US+GB+JP+DE+FR+CN+CA+AU"
            start = input("  Start period [2000]: ").strip() or "2000"
            recipe_dsr(countries=countries, start=start)
        elif choice == "14":
            countries = input("  Countries [US+GB+JP+DE+FR+CN+CA+AU+NZ+SE+NO+KR]: ").strip() or "US+GB+JP+DE+FR+CN+CA+AU+NZ+SE+NO+KR"
            start = input("  Start period [2000]: ").strip() or "2000"
            recipe_property_prices(countries=countries, start=start)
        elif choice == "15":
            countries = input("  Countries [US+GB+JP+DE+FR+CN+CH+CA+AU+SE+NO+NZ+KR+IN+BR+MX]: ").strip() or "US+GB+JP+DE+FR+CN+CH+CA+AU+SE+NO+NZ+KR+IN+BR+MX"
            start = input("  Start period [2000]: ").strip() or "2000"
            recipe_eer(countries=countries, start=start)
        elif choice == "16":
            start = input("  Start period [2010]: ").strip() or "2010"
            recipe_global_liquidity(start=start)
        elif choice == "17":
            reporter = input("  Reporter country [US]: ").strip() or "US"
            pos = input("  Position [C=Claims, L=Liabilities]: ").strip() or "C"
            start = input("  Start period [2010]: ").strip() or "2010"
            recipe_lbs_crossborder(reporter=reporter, position=pos, start=start)
        elif choice == "18":
            print("  Available dataflow aliases: " + ", ".join(sorted(DATAFLOW_ALIASES.keys())))
            dataflow = input("  Dataflow (ID or alias): ").strip()
            if not dataflow:
                continue
            key = input("  Key filter [all]: ").strip() or "all"
            start = input("  Start period [2000]: ").strip() or "2000"
            end = input("  End period [latest]: ").strip() or None
            _cmd_data_query(dataflow, key=key, start=start, end=end)
        elif choice == "30":
            reporter = input("  Reporter [US]: ").strip() or "US"
            counterparty = input("  Counterparty [CN]: ").strip() or "CN"
            currency = input("  Currency [TO1]: ").strip() or "TO1"
            sector = input("  Sector [A=All]: ").strip() or "A"
            instrument = input("  Instrument [A=All]: ").strip() or "A"
            position = input("  Position [C=Claims, L=Liab]: ").strip() or "C"
            start = input("  Start [2010]: ").strip() or "2010"
            recipe_lbs_bilateral(reporter=reporter, counterparty=counterparty,
                                  currency=currency, sector=sector,
                                  instrument=instrument, position=position,
                                  start=start)
        elif choice == "31":
            reporters_raw = input("  Reporters [default offshore+major]: ").strip()
            reporters = reporters_raw.split("+") if reporters_raw else None
            start = input("  Start [2010]: ").strip() or "2010"
            recipe_eurodollar(start=start, reporters=reporters)
        elif choice == "32":
            reporters_raw = input("  Reporters [default major reporters]: ").strip()
            reporters = reporters_raw.split("+") if reporters_raw else None
            start = input("  Start [2010]: ").strip() or "2010"
            recipe_nbfi(start=start, reporters=reporters)
        elif choice == "33":
            currency = input("  Currency [USD]: ").strip() or "USD"
            reporters_raw = input("  Reporters [default major]: ").strip()
            reporters = reporters_raw.split("+") if reporters_raw else None
            start = input("  Start [2010]: ").strip() or "2010"
            recipe_interbank(currency=currency, start=start, reporters=reporters)
        elif choice == "34":
            centers_raw = input("  Centers [default core offshore]: ").strip()
            centers = centers_raw.split("+") if centers_raw else None
            start = input("  Start [2010]: ").strip() or "2010"
            recipe_offshore_centers(start=start, centers=centers)
        elif choice == "35":
            host = input("  Host country [GB]: ").strip() or "GB"
            parents_raw = input("  Parent countries [default major]: ").strip()
            parents = parents_raw.split("+") if parents_raw else None
            start = input("  Start [2010]: ").strip() or "2010"
            recipe_bank_nationality(host=host, start=start, parents=parents)
        elif choice == "36":
            reporter = input("  Reporter [US]: ").strip() or "US"
            start = input("  Start [2010]: ").strip() or "2010"
            recipe_currency_breakdown(reporter=reporter, start=start)
        elif choice == "37":
            reporters_raw = input("  Reporters [default major + EM]: ").strip()
            reporters = reporters_raw.split("+") if reporters_raw else None
            start = input("  Start [2010]: ").strip() or "2010"
            recipe_fcy_mismatch(start=start, reporters=reporters)
        elif choice == "38":
            reporter = input("  Reporter [US]: ").strip() or "US"
            start = input("  Start [2010]: ").strip() or "2010"
            recipe_sector_matrix(reporter=reporter, start=start)
        elif choice == "39":
            target = input("  Target country [TR]: ").strip() or "TR"
            reporters_raw = input("  Reporters [default major + offshore]: ").strip()
            reporters = reporters_raw.split("+") if reporters_raw else None
            start = input("  Start [2010]: ").strip() or "2010"
            recipe_exposure_to(target=target, start=start, reporters=reporters)
        elif choice == "40":
            reporter = input("  Reporter [US]: ").strip() or "US"
            start = input("  Start [2010]: ").strip() or "2010"
            recipe_usd_funding(reporter=reporter, start=start)
        elif choice == "41":
            start = input("  Start [2010]: ").strip() or "2010"
            recipe_derivatives_crossborder(start=start)
        elif choice == "50":
            reporter = input("  Reporter [US]: ").strip() or "US"
            basis = input("  Basis [F=Immediate, U=Guarantor]: ").strip() or "F"
            bank_type = input("  Bank type [4R=Domestic excl domestic]: ").strip() or "4R"
            start = input("  Start [2010]: ").strip() or "2010"
            recipe_cbs_foreign_claims(reporter=reporter, basis=basis,
                                        bank_type=bank_type, start=start)
        elif choice == "51":
            target = input("  Target country [TR]: ").strip() or "TR"
            basis = input("  Basis [F=Immediate, U=Guarantor]: ").strip() or "F"
            bank_type = input("  Bank type [4R]: ").strip() or "4R"
            start = input("  Start [2010]: ").strip() or "2010"
            recipe_cbs_exposure_to(target=target, basis=basis,
                                     bank_type=bank_type, start=start)
        elif choice == "52":
            reporter = input("  Reporter [US]: ").strip() or "US"
            basis = input("  Basis [F=Immediate, U=Guarantor]: ").strip() or "F"
            start = input("  Start [2010]: ").strip() or "2010"
            recipe_cbs_maturity(reporter=reporter, basis=basis, start=start)
        elif choice == "53":
            reporter = input("  Reporter [US]: ").strip() or "US"
            start = input("  Start [2010]: ").strip() or "2010"
            recipe_cbs_guarantor_diff(reporter=reporter, start=start)
        elif choice == "60":
            currency = input("  Currency [USD]: ").strip() or "USD"
            regions_raw = input("  Regions [default: global + EM]: ").strip()
            regions = regions_raw.split("+") if regions_raw else None
            start = input("  Start [2010]: ").strip() or "2010"
            recipe_gli_currency(currency=currency, start=start, regions=regions)
        elif choice == "61":
            start = input("  Start [2010]: ").strip() or "2010"
            recipe_gli_all_currencies(start=start)
        elif choice == "70":
            start = input("  Start [2010]: ").strip() or "2010"
            confirm = input("  This runs ~200 API queries (5-10min). Continue? [y/N]: ").strip().lower()
            if confirm == "y":
                recipe_shadow_banking_full(start=start)
        elif choice == "71":
            target = input("  Target country [TR]: ").strip() or "TR"
            start = input("  Start [2010]: ").strip() or "2010"
            recipe_contagion(target=target, start=start)
        elif choice == "72":
            start = input("  Start [2010]: ").strip() or "2010"
            recipe_eurodollar_system(start=start)
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
