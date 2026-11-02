"""Build a flat catalog of every All of Us Registered Tier field and survey item.

Reads the two workbooks in AllOfUs_Analysis/ and returns one record per field:
  id, source, group, name, label, desc, type, privacy, privacy_note
Sources: omop (OMOP-compatible tables), ds (Data Explorer / Workbench tables), survey,
wear (Fitbit / HealthKit), emt (Exploring the Mind tasks). EHR concept sets are added
separately by mapping_rules.py because the dictionary lists columns, not concepts.
"""
import re
import warnings
from pathlib import Path

import openpyxl

warnings.filterwarnings("ignore", module="openpyxl")

ROOT = Path(__file__).resolve().parent.parent
DICT_XLSX = ROOT / "All of Us Registered Tier Dataset v9 CDR Data Dictionary (R2025Q4R6).xlsx"
SURVEY_XLSX = ROOT / "All of Us Survey Data Codebooks.xlsx"

# Codebook sheet -> (module key, display name). Sheet names are truncated in the workbook.
SURVEY_SHEETS = {
    "Basics": ("basics", "The Basics"),
    "Lifestyle": ("lifestyle", "Lifestyle"),
    "Overall Health": ("overall_health", "Overall Health"),
    "Personal and Family Health Hist": ("pfhh", "Personal and Family Health History"),
    "Healthcare Access and Utilizati": ("hcau", "Health Care Access & Utilization"),
    "Social Determinants of Health": ("sdoh", "Social Determinants of Health"),
    "COPE ": ("cope", "COVID-19 Participant Experience (COPE)"),
    "Minute Survey on COVID-19 Vacci": ("covid_vaccine", "Minute Survey on COVID-19 Vaccines"),
    "Family Health History": ("fhh_legacy", "Family Health History (legacy, pre-PFHH)"),
    "Personal Medical History": ("pmh_legacy", "Personal Medical History (legacy, pre-PFHH)"),
}


def _rows(ws):
    return [r for r in ws.iter_rows(values_only=True) if any(c not in (None, "") for c in r)]


def _clean(v):
    return re.sub(r"\s+", " ", str(v)).strip() if v not in (None, "") else ""


def _norm_header(h):
    return re.sub(r"[^a-z]", "", str(h or "").lower())


def _privacy_index(wb):
    supp, gen = {}, {}
    for r in _rows(wb["Field (Column) Suppressions"])[1:]:
        supp[(_clean(r[0]).lower(), _clean(r[1]))] = _clean(r[9]) or _clean(r[8])
    for r in _rows(wb["Field (Column) Generalizations"])[1:]:
        gen[(_clean(r[0]).lower(), _clean(r[1]))] = _clean(r[8]) + (": " + _clean(r[9])[:300] if r[9] else "")
    tables = {_clean(r[0]).lower(): _clean(r[6]) for r in _rows(wb["Table Suppressions"])[1:]}
    concept_gen = {}
    for r in _rows(wb["Concept (Row) Generalizations"])[1:]:
        if _clean(r[5]):  # PPI module present -> survey question
            concept_gen[_clean(r[2]).lower()] = _clean(r[6])
    return supp, gen, tables, concept_gen


def _privacy(table, field, transformed_note, supp, gen, tables):
    key = (table.lower(), field)
    if table.lower() in tables:
        return "suppressed", "Table suppressed: " + tables[table.lower()]
    if key in supp:
        return "suppressed", "Column suppressed in Registered Tier: " + supp[key]
    if key in gen:
        return "generalized", gen[key]
    if transformed_note and "date shift" in transformed_note.lower():
        return "available", "Dates shifted per participant (Registered Tier privacy method)"
    return "available", transformed_note


def load_catalog():
    wb = openpyxl.load_workbook(DICT_XLSX, read_only=True)
    supp, gen, tables, concept_gen = _privacy_index(wb)
    out = []

    for r in _rows(wb["OMOP-Compatible Tables"])[1:]:
        table, field = _clean(r[0]), _clean(r[1])
        if not table or not field:
            continue
        p, note = _privacy(table, field, _clean(r[8]), supp, gen, tables)
        out.append(dict(id=f"omop/{table}/{field}", source="omop", group=table, name=field, label=field,
                        desc=_clean(r[3]), type=_clean(r[4]), provenance=_clean(r[5]), privacy=p, privacy_note=note))

    for r in _rows(wb["Data Explorer Tables"])[1:]:
        table, field = _clean(r[0]), _clean(r[2])
        if not table or not field:
            continue
        p, note = _privacy(table, field, _clean(r[9]), supp, gen, tables)
        out.append(dict(id=f"ds/{table}/{field}", source="ds", group=table, name=field, label=field,
                        desc=_clean(r[4]), type=_clean(r[5]), provenance=_clean(r[6]), privacy=p, privacy_note=note))

    for r in _rows(wb["Wearables"])[1:]:
        dev, table, field = _clean(r[0]), _clean(r[1]), _clean(r[3])
        if not dev or not table or not field:
            continue
        affected = _clean(r[7]).lower() == "yes"
        out.append(dict(id=f"wear/{dev.lower()}/{table}/{field}", source="wear", group=f"{dev} · {table}",
                        name=field, label=field, desc=_clean(r[5]), type=_clean(r[4]), provenance=dev,
                        privacy="available", privacy_note=_clean(r[8]) if affected else ""))

    for r in _rows(wb["Exploring the Mind"])[1:]:
        task, table, field = _clean(r[0]), _clean(r[1]), _clean(r[3])
        if not table or not field or field.lower() == "field name":
            continue
        out.append(dict(id=f"emt/{table}/{field}", source="emt", group=table, name=field,
                        label=field, desc=_clean(r[4]), type=_clean(r[5]), provenance=f"Exploring the Mind · {task}",
                        privacy="available", privacy_note=_clean(r[7])))

    swb = openpyxl.load_workbook(SURVEY_XLSX, read_only=True)
    by_id = {}
    for sheet, (mod, mod_name) in SURVEY_SHEETS.items():
        rows = _rows(swb[sheet])
        hi = next(i for i, r in enumerate(rows) if any(_norm_header(c) == "itemconcept" for c in r))
        cols = {_norm_header(c): i for i, c in enumerate(rows[hi]) if c}
        get = lambda r, k: _clean(r[cols[k]]) if k in cols and cols[k] < len(r) else ""
        for r in rows[hi + 1:]:
            item, ftype = get(r, "itemconcept"), get(r, "fieldtype")
            if not item or ftype == "descriptive":
                continue
            fid = f"survey/{mod}/{item.lower()}"
            version = get(r, "version")
            if fid in by_id:  # COPE repeats items across monthly versions
                if version and version not in by_id[fid]["versions"]:
                    by_id[fid]["versions"] += ", " + version
                continue
            rule = get(r, "registeredtierrules")
            if "SUPPRESSED" in rule and "UNSUPPRESSED" not in rule:
                p, note = "suppressed", "Question suppressed in Registered Tier"
            elif item.lower() in concept_gen:
                p, note = "generalized", concept_gen[item.lower()]
            else:
                p, note = "available", ""
            choices = get(r, "choicescalculationsorsliderlabels")
            rec = dict(id=fid, source="survey", group=mod_name, name=item.lower(), label=get(r, "fieldlabel"),
                       desc=get(r, "sectionheader")[:300], type=ftype,
                       choices=" | ".join(c.split(",", 1)[-1].strip() for c in choices.split("|"))[:600] if choices else "",
                       provenance="PPI survey", privacy=p, privacy_note=note, versions=version)
            by_id[fid] = rec
            out.append(rec)
    return out


if __name__ == "__main__":
    from collections import Counter
    cat = load_catalog()
    print(len(cat), Counter(f["source"] for f in cat), Counter(f["privacy"] for f in cat))
    print(Counter(f["group"] for f in cat if f["source"] == "survey"))
    for f in cat:
        if f["privacy"] != "available" and f["source"] == "survey":
            print(f["id"], f["privacy"], f["privacy_note"][:80])
