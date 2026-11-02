"""Map KG entities to All of Us fields and build the interactive viewer.

Usage: python3 build_map.py [kg_export_dir]   (default: ../../kg_export/v2.1)

If aou_counts/field_counts_hiv.csv exists (output of the Workbench notebook), HIV-cohort counts are merged
into the CSVs and the viewer.

Writes to kg_aou/out/:
  aou_fields.csv            every Registered Tier field / survey item / EHR concept set
  entity_variable_map.csv   KG entity -> All of Us variable (construct), with strength
  entity_field_map.csv      KG entity -> field, with Direct / Proxy classification (+ HIV-cohort counts)
  entity_hiv_coverage.csv   per entity: best-populated Direct / any field in the HIV cohort (needs counts)
  kg_aou_viewer.html        self-contained viewer (KG graph, entity panel, schema browser)
"""
import csv
import fnmatch
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from build_catalog import load_catalog
from mapping_rules import CONCEPT_SETS, ENTITY_RULES, GAP_RULES, VARIABLES, D, P, describe

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
COUNTS_DIR = HERE / "aou_counts"
KG_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else HERE.parents[1] / "kg_export" / "v2.1"


def build_fields():
    fields = load_catalog()
    for key, spec in CONCEPT_SETS.items():
        table = spec["table"]
        fields.append(dict(id=f"ehr/{table}/{key}", source="ehr", group=table, name=key, label=spec["label"], desc=describe(spec),
                           type="concept set", provenance="EHR", privacy="available",
                           privacy_note="Individual concepts may be row-suppressed or generalized; check the Concept Suppressions sheet"))
    return fields


def expand_variables(fields):
    ids = [f["id"] for f in fields]
    resolved, problems = {}, []
    for vid, v in VARIABLES.items():
        seen = {}
        for pattern, strength, note in v["fields"]:
            hits = fnmatch.filter(ids, pattern) if "*" in pattern else [pattern] if pattern in ids else []
            if not hits:
                problems.append(f"{vid}: no field matches {pattern}")
            for h in hits:
                if h not in seen or (strength == D and seen[h][0] == P):
                    seen[h] = (strength, note)
        resolved[vid] = seen
    if problems:
        raise SystemExit("Unresolved field references:\n  " + "\n  ".join(problems))
    return resolved


def load_kg():
    ents = list(csv.DictReader(open(KG_DIR / "entities.csv", encoding="utf-8")))
    rels = list(csv.DictReader(open(KG_DIR / "relations.csv", encoding="utf-8")))
    return ents, rels


def load_counts():
    # HIV-cohort counts per field from the Workbench notebook, or ({}, None) if not available.
    path = COUNTS_DIR / "field_counts_hiv.csv"
    if not path.exists():
        return {}, None
    counts = {r["field_id"]: r for r in csv.DictReader(open(path, encoding="utf-8"))}
    info = json.load(open(COUNTS_DIR / "run_info.json")) if (COUNTS_DIR / "run_info.json").exists() else {}
    summary = list(csv.reader(open(COUNTS_DIR / "cohort_summary.csv")))[1:] if (COUNTS_DIR / "cohort_summary.csv").exists() else []
    return counts, dict(info, summary=summary)


# Generic columns of EHR event tables (e.g. measurement.value_as_number, drug_exposure.refills) support a construct
# but their counts cover every record in the table, not the construct; they are excluded when picking an entity's
# best-populated field.
SUPPORT_TABLES = {"measurement", "drug_exposure", "visit_occurrence", "condition_occurrence", "observation_period"}


def is_support(fid):
    src, table = fid.split("/")[:2]
    return src == "omop" and table in SUPPORT_TABLES


def count_num(v):
    # Numeric value of a (possibly masked) count; "<=20" sorts as 10.
    if v in (None, ""):
        return None
    return 10 if v.startswith("<=") else int(float(v))


def map_entities(ents):
    compiled = []
    for rule in ENTITY_RULES:
        pat, vars_, strength, note = rule[:4]
        opts = rule[4] if len(rule) > 4 else {}
        compiled.append((re.compile(pat, re.I), vars_, strength, note,
                         re.compile(opts["exclude"], re.I) if "exclude" in opts else None, opts.get("cats")))
    gaps = [(re.compile(g[0], re.I), g[1], re.compile(g[2], re.I) if len(g) > 2 else None) for g in GAP_RULES]
    result, gap_reason = {}, {}
    for e in ents:
        name, cat = e["entity"], e["category"]
        hits = {}
        reason = next((r for rx, r, unless in gaps if rx.search(name) and not (unless and unless.search(name))), None)
        if reason:
            result[name], gap_reason[name] = hits, reason
            continue
        for rx, vars_, strength, note, ex, cats in compiled:
            if cats and cat not in cats:
                continue
            if rx.search(name) and not (ex and ex.search(name)):
                for v in vars_:
                    if v not in hits or (strength == D and hits[v][0] == P):
                        hits[v] = (strength, note)
        result[name] = hits
    return result, gap_reason


def main():
    OUT.mkdir(exist_ok=True)
    fields = build_fields()
    fmap = {f["id"]: f for f in fields}
    var_fields = expand_variables(fields)
    ents, rels = load_kg()
    emap, gaps = map_entities(ents)
    counts, cohort = load_counts()
    cget = lambda fid, k: counts.get(fid, {}).get(k, "")

    with open(OUT / "aou_fields.csv", "w", newline="", encoding="utf-8") as fh:
        cols = ["id", "source", "group", "name", "label", "desc", "type", "choices", "provenance", "privacy", "privacy_note", "versions",
                "hiv_n_valid", "hiv_pct_valid", "count_status"]
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for f in fields:
            w.writerow(dict(f, hiv_n_valid=cget(f["id"], "n_hiv_valid"), hiv_pct_valid=cget(f["id"], "pct_hiv_valid"),
                            count_status=cget(f["id"], "status")))

    ev_rows, ef_rows = [], []
    for e in ents:
        for vid, (vs, vnote) in sorted(emap[e["entity"]].items()):
            ev_rows.append([e["entity"], e["category"], e["degree"], e["n_articles"], vid, VARIABLES[vid]["label"], vs, vnote])
            for fid, (fs, fnote) in var_fields[vid].items():
                f = fmap[fid]
                link = D if vs == D and fs == D else P
                ef_rows.append([e["entity"], e["category"], vid, VARIABLES[vid]["label"], fid, f["source"], f["group"], f["name"],
                                f["label"], link, fnote, f["privacy"], cget(fid, "n_hiv_valid"), cget(fid, "pct_hiv_valid"),
                                cget(fid, "status")])
    with open(OUT / "entity_variable_map.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["entity", "category", "degree", "n_articles", "variable", "variable_label", "strength", "rule_note"])
        w.writerows(ev_rows)
    with open(OUT / "entity_field_map.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["entity", "category", "variable", "variable_label", "field_id", "source", "table_or_module", "field_name",
                    "field_label", "link", "field_note", "registered_tier_privacy", "hiv_n_valid", "hiv_pct_valid", "count_status"])
        w.writerows(ef_rows)
    if counts:
        best = {}
        for r in ef_rows:
            n = count_num(r[12]) if r[14] == "ok" and not is_support(r[4]) else None
            if n is None:
                continue
            for kind in ("direct", "any") if r[9] == D else ("any",):
                cur = best.get((r[0], kind))
                if cur is None or n > cur[0]:
                    best[(r[0], kind)] = (n, r[4], r[12], r[13])
        with open(OUT / "entity_hiv_coverage.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["entity", "category", "degree", "n_articles", "coverage", "best_direct_field", "best_direct_hiv_n", "best_direct_hiv_pct",
                        "best_any_field", "best_any_hiv_n", "best_any_hiv_pct", "hiv_cohort_n"])
            rows = []
            for e in ents:
                d, a = best.get((e["entity"], "direct")), best.get((e["entity"], "any"))
                cov = "out_of_scope" if e["entity"] in gaps else "direct" if d else "proxy_only" if a else "mapped_no_data" if emap[e["entity"]] else "no_rule"
                rows.append([e["entity"], e["category"], e["degree"], e["n_articles"], cov, *(d[1:] if d else ("", "", "")),
                             *(a[1:] if a else ("", "", "")), cohort.get("n_hiv_cohort", "")])
            rows.sort(key=lambda r: -int(r[2]))
            w.writerows(rows)
    with open(OUT / "entity_gaps.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["entity", "category", "degree", "n_articles", "status", "reason"])
        for e in ents:
            if not emap[e["entity"]]:
                status = "out_of_scope" if e["entity"] in gaps else "no_rule"
                w.writerow([e["entity"], e["category"], e["degree"], e["n_articles"], status, gaps.get(e["entity"], "")])

    # ---- viewer payload -------------------------------------------------------------------
    used = {fid for vid in var_fields for fid in var_fields[vid]}
    data = dict(
        ents=[[e["entity"], e["category"], int(e["degree"]), int(e["n_articles"]),
               [[v, s] for v, (s, _) in sorted(emap[e["entity"]].items())]] for e in ents],
        rels=[[r["subject"], r["predicate"], r["object"], int(r["n_articles"]), r["pmids"].split(";")[:30]] for r in rels],
        gap_reasons=sorted(set(gaps.values())),
        gaps={},
        vars={vid: dict(label=v["label"], fields=[[fid, s, n] for fid, (s, n) in var_fields[vid].items()])
              for vid, v in VARIABLES.items()},
        rule_notes={e["entity"]: {v: n for v, (_, n) in emap[e["entity"]].items()} for e in ents if emap[e["entity"]]},
        fields=[[f["id"], f["source"], f["group"], f["name"], f["label"], f["desc"][:400], f["type"],
                 f.get("choices", "")[:400], f["privacy"], f["privacy_note"][:300], f.get("versions", "")] for f in fields],
        used=sorted(used),
        counts={fid: [c["n_hiv_valid"], c["pct_hiv_valid"], c["status"], c["n_all_valid"], int(is_support(fid))]
                for fid, c in counts.items() if fid in used},
        cohort=cohort,
    )
    data["gaps"] = {name: data["gap_reasons"].index(r) for name, r in gaps.items()}
    tpl = (HERE / "viewer_template.html").read_text(encoding="utf-8")
    html = tpl.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    (OUT / "kg_aou_viewer.html").write_text(html, encoding="utf-8")

    # ---- report ---------------------------------------------------------------------------
    mapped = [e for e in ents if emap[e["entity"]]]
    direct = [e for e in mapped if any(s == D for s, _ in emap[e["entity"]].values())]
    print(f"KG: {len(ents)} entities, {len(rels)} relations ({KG_DIR})")
    print(f"Mapped entities: {len(mapped)} ({len(direct)} with ≥1 Direct variable); out of scope: {len(gaps)}")
    for r, n in Counter(gaps.values()).most_common():
        print(f"    {n:>4}  {r[:90]}")
    w_all = sum(int(e["degree"]) for e in ents)
    print(f"Degree-weighted coverage: {sum(int(e['degree']) for e in mapped) / w_all:.1%}")
    print("Per category:", {c: f"{sum(1 for e in mapped if e['category'] == c)}/{n}" for c, n in Counter(e["category"] for e in ents).items()})
    print(f"Entity-field links: {len(ef_rows)} ({sum(1 for r in ef_rows if r[9] == D)} direct)")
    print(f"HTML: {(OUT / 'kg_aou_viewer.html').stat().st_size / 1e6:.1f} MB")
    if counts:
        print(f"HIV-cohort counts merged for {sum(1 for f in used if f in counts)} of {len(used)} fields "
              f"(cohort {cohort.get('cohort')}, n = {cohort.get('n_hiv_cohort')}, {cohort.get('cdr')})")
    if "--unmapped" in sys.argv:
        for e in [e for e in ents if not emap[e["entity"]] and e["entity"] not in gaps][:int(sys.argv[sys.argv.index("--unmapped") + 1])]:
            print(f"  {e['degree']:>4} {e['category']:<20} {e['entity']}")


if __name__ == "__main__":
    main()
