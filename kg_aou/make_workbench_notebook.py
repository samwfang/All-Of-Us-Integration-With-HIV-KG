"""Generate a Researcher Workbench notebook that counts, for every mapped All of Us field,
how many participants with HIV have a valid entry.

Usage: python3 make_workbench_notebook.py   (run build_map.py first)
Writes out/kg_aou_hiv_field_counts.ipynb with the mapped-field list embedded.
"""
import json
import re
from pathlib import Path

from mapping_rules import COHORT_SETS, CONCEPT_SETS

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"


def used_fields():
    html = (OUT / "kg_aou_viewer.html").read_text(encoding="utf-8")
    data = json.loads(re.search(r"const DATA = (\{.*?\});\n", html, re.S).group(1))
    fields = {f[0]: f for f in data["fields"]}
    rows = []
    for fid in data["used"]:
        f = fields[fid]
        rows.append({"id": fid, "src": f[1], "group": f[2], "name": f[3], "label": f[4][:160], "privacy": f[8]})
    return rows


MD_INTRO = r"""# HIV KG × All of Us: valid entries per mapped field (HIV cohort)

For each All of Us field mapped from the HIV virologic-failure knowledge graph, this notebook counts how many
participants **in an HIV cohort** have a valid entry. The field list (676 fields) is embedded below.

**Run order:** Kernel → Restart & Run All. Each step prints what it found; review the tables marked **REVIEW**.

**Outputs** (folder `kg_aou_counts/`, also zipped as `kg_aou_counts.zip`):

| File | Contents |
|---|---|
| `field_counts_hiv.csv` | One row per field: participants with any / valid entry, in the HIV cohort and in all of All of Us |
| `cohort_summary.csv` | Size and overlap of each HIV definition |
| `concept_set_review.csv` | Every concept pulled into each EHR concept set (check these) |
| `survey_item_matching.csv` | How codebook item codes matched questions in the CDR |
| `table_resolution.csv` | How dictionary tables / columns matched the CDR |
| `run_info.json` | CDR version, cohort definition, date |

**Dissemination policy:** every count from 1 to `MASK_AT_OR_BELOW` (default 20) is replaced with `<=20` before
anything is written, and the matching percentages are blanked. Only aggregate counts are written. Check the current
All of Us Data and Statistics Dissemination Policy before sharing results outside the Workbench.

**Cost:** the queries scan the concept-ID columns of the large EHR tables once. Each query prints its size first
(dry run) and stops if it exceeds `MAX_GB_PER_QUERY`.
"""

CONFIG = r"""# ---- Configuration -------------------------------------------------------------------------
# HIV cohort = union of the components listed (separate with "|"):
#   "dx"    >=1 HIV diagnosis code (ICD-10-CM B20, Z21, O98.7, B97.35; ICD-9-CM 042, V08, 079.53, plus their standard targets)
#   "dx2"   >=2 distinct dates with an HIV diagnosis code (more specific than "dx")
#   "self"  self-reported HIV/AIDS in the Personal (and Family) Health History survey
#   "arv"   >=1 prescription for an HIV-only antiretroviral (excludes PrEP / HBV / COVID-use drugs)
COHORT = "dx|self"

# The Workbench sets WORKSPACE_CDR automatically. If it is missing, paste your CDR here as "project.dataset"
# (Workbench: workspace "About" / "Data" panel, or the dataset name shown in a Dataset Builder notebook).
CDR_OVERRIDE = ""
# On the newer (Verily-based) Workbench the CDR is a referenced workspace resource; the notebook resolves it
# with `wb resource resolve` when WORKSPACE_CDR is not set.
CDR_RESOURCE_ID = "R2025Q4R6"
# Other datasets to search for tables not in the CDR (e.g. ds_zip_code_socioeconomic, Exploring the Mind tasks):
# workspace resource IDs (resolved with `wb`) and/or explicit "project.dataset" names.
EXTRA_DATASET_RESOURCES = ["prep_R2025Q4R6"]
EXTRA_DATASETS = []

MASK_AT_OR_BELOW = 20        # counts 1..20 are written as "<=20"
MAX_GB_PER_QUERY = 800       # safety stop for a single query
OUT_DIR = "kg_aou_counts"

# Extra table names to try when a dictionary table name differs in the CDR (dictionary name -> candidates)
TABLE_ALIASES = {
    "activity_measurements": ["activity_summary"],
    "sleep_daily_summary_ext": ["sleep_daily_summary"],
    "physical_measurements": ["healthkit_physical_measurements", "hk_physical_measurements"],
}
"""

SETUP = r"""import os, re, json, zipfile, datetime
import pandas as pd
from google.cloud import bigquery

def resolve_resource(rid):
    # "project.dataset" for a workspace BigQuery resource on the Verily-based Workbench, or "" if unavailable.
    import subprocess
    try:
        res = subprocess.run(["wb", "resource", "resolve", f"--id={rid}"], capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        print("`wb` CLI not found")
        return ""
    m = re.search(r"([a-z][a-z0-9-]{4,})[.:](" + re.escape(rid) + r")\b", res.stdout + res.stderr)
    if not m:
        print(f"Could not parse `wb resource resolve --id={rid}` output:\n", (res.stdout + res.stderr)[:500])
    return f"{m.group(1)}.{m.group(2)}" if m else ""


CDR = CDR_OVERRIDE.strip() or os.environ.get("WORKSPACE_CDR", "")   # "project.dataset" of this workspace's CDR
if not CDR and CDR_RESOURCE_ID:
    CDR = resolve_resource(CDR_RESOURCE_ID)
if not CDR:
    found = {k: v for k, v in os.environ.items() if any(s in k for s in ("CDR", "WORKSPACE", "GOOGLE"))}
    raise RuntimeError(
        "WORKSPACE_CDR is not set. This notebook must run inside an All of Us Researcher Workbench Jupyter environment. "
        "If you are in the Workbench, set CDR_OVERRIDE in the Configuration cell to your CDR (\"project.dataset\"). "
        f"Related environment variables found: {found or 'none'}")
client = bigquery.Client()
os.makedirs(OUT_DIR, exist_ok=True)
pd.set_option("display.max_rows", 200, "display.max_colwidth", 80)
print("CDR:", CDR)
EXTRA = [d for d in EXTRA_DATASETS + [resolve_resource(r) for r in EXTRA_DATASET_RESOURCES] if d]
print("Extra datasets:", EXTRA)


def run(sql, params=(), label=""):
    # Run a query after a dry run that reports (and caps) the bytes scanned.
    params = list(params)
    dry = client.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params, dry_run=True, use_query_cache=False))
    gb = dry.total_bytes_processed / 1e9
    print(f"[{label}] ~{gb:,.1f} GB scanned")
    if gb > MAX_GB_PER_QUERY:
        raise RuntimeError(f"{label}: {gb:.0f} GB exceeds MAX_GB_PER_QUERY")
    return client.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).to_dataframe()


def arr(name, typ, values):
    # Convert NumPy scalars (e.g. int64 from pandas) to plain Python values so the client can serialize them.
    return bigquery.ArrayQueryParameter(name, typ, [v.item() if hasattr(v, "item") else v for v in values])


def zipped(prefix, cols):
    # SQL for a table built from parallel array parameters @{prefix}_{col}.
    first, *rest = cols
    sql = f"SELECT {', '.join(cols)} FROM UNNEST(@{prefix}_{first}) AS {first} WITH OFFSET AS o_{first}"
    for c in rest:
        sql += f" JOIN UNNEST(@{prefix}_{c}) AS {c} WITH OFFSET AS o_{c} ON o_{first} = o_{c}"
    return sql


def mask(n):
    if pd.isna(n):
        return n
    n = int(n)
    return f"<={MASK_AT_OR_BELOW}" if 0 < n <= MASK_AT_OR_BELOW else n
"""

FIELDS = r"""# Mapped fields from kg_aou (entity_field_map.csv), embedded so no upload is needed.
FIELDS = pd.DataFrame(json.loads(r'''__USED_FIELDS_JSON__'''))
print(FIELDS.groupby("src").size().rename("fields").to_string())
"""

SPECS = r"""# ---- EHR concept-set specifications --------------------------------------------------------
# Generated from CONCEPT_SETS / COHORT_SETS in kg_aou/mapping_rules.py, which also produces the descriptions
# shown in the viewer. Change specs there and regenerate this notebook; quick experiments can edit SETS here.
# Every resolved concept is listed in concept_set_review.csv.
SETS = json.loads(r'''__SETS_JSON__''')

rx = lambda names: r"^(" + "|".join(names) + r")$"
ICD = {s: dict(icd10=d.get("icd10", []), icd9=d.get("icd9", [])) for s, d in SETS.items() if d.get("icd10") or d.get("icd9")}
LOINC = {s: d["loinc"] for s, d in SETS.items() if d.get("loinc")}
MEAS_REGEX = {s: tuple(d["name_regex"]) for s, d in SETS.items() if d.get("name_regex")}
INGREDIENT = {s: (rx(d["ingredients"]), d.get("drug_name_regex", "")) for s, d in SETS.items() if d.get("ingredients")}
ATC = {s: d["atc"] for s, d in SETS.items() if d.get("atc")}
CONCEPT_IDS = {s: d["concept_ids"] for s, d in SETS.items() if d.get("concept_ids")}
CODE_RANGE = {s: [tuple(r) for r in d["code_ranges"]] for s, d in SETS.items() if d.get("code_ranges")}
GENERIC = {s for s, d in SETS.items() if d.get("generic")}   # placeholders, not countable
# "art_str" (single-tablet regimens) is derived in concept_map(): products with >=3 distinct "art" ingredients.
print(len(SETS), "concept sets:", {k: len(v) for k, v in dict(ICD=ICD, LOINC=LOINC, MEAS_REGEX=MEAS_REGEX, INGREDIENT=INGREDIENT,
                                                              ATC=ATC, CONCEPT_IDS=CONCEPT_IDS, CODE_RANGE=CODE_RANGE).items()})
"""

CMAP = r"""def concept_map(sets=None):
    # Return (CTE SQL defining cmap(s, concept_id, how), query parameters) for the selected concept sets.
    keep = lambda s: sets is None or s in sets
    P = {}
    def add(prefix, **cols):
        for c, v in cols.items():
            P.setdefault(f"{prefix}_{c}", []).append(v)
    for s, d in ICD.items():
        if keep(s):
            for vocab, key in (("ICD10CM", "icd10"), ("ICD9CM", "icd9")):
                for p in d.get(key, []):
                    add("icd", s=s, v=vocab, p=p)
    for s, codes in LOINC.items():
        if keep(s):
            for c in codes:
                add("lc", s=s, c=c)
    for s, (inc, exc) in MEAS_REGEX.items():
        if keep(s):
            add("mr", s=s, inc=inc, exc=exc)
    for s, (ing, drx) in INGREDIENT.items():
        if keep(s) or (s == "art" and keep("art_str")):
            add("ig", s=s, rx=ing, drx=drx)
    for s, codes in ATC.items():
        if keep(s):
            for c in codes:
                add("atc", s=s, c=c)
    for s, ids in CONCEPT_IDS.items():
        if keep(s):
            for i in ids:
                add("cid", s=s, c=i)
    for s, ranges in CODE_RANGE.items():
        if keep(s):
            for v, lo, hi in ranges:
                add("rg", s=s, v=v, lo=lo, hi=hi)
    layout = {"icd": ["s", "v", "p"], "lc": ["s", "c"], "mr": ["s", "inc", "exc"], "ig": ["s", "rx", "drx"],
              "atc": ["s", "c"], "cid": ["s", "c"], "rg": ["s", "v", "lo", "hi"]}
    params = []
    for prefix, cols in layout.items():
        for c in cols:
            vals = P.get(f"{prefix}_{c}", [])
            params.append(arr(f"{prefix}_{c}", "INT64" if (prefix == "cid" and c == "c") else "STRING", vals))
    z = lambda prefix: zipped(prefix, layout[prefix])
    str_sql = ""
    if keep("art_str"):
        str_sql = f'''
  UNION ALL SELECT 'art_str', ca.descendant_concept_id, 'derived: >=3 ARV ingredients'
  FROM ig_ing g JOIN `{CDR}.concept_ancestor` ca ON ca.ancestor_concept_id = g.concept_id
  WHERE g.s = 'art' GROUP BY ca.descendant_concept_id HAVING COUNT(DISTINCT g.concept_id) >= 3'''
    cte = f'''
icd_src AS (SELECT DISTINCT x.s, c.concept_id FROM ({z("icd")}) x
  JOIN `{CDR}.concept` c ON c.vocabulary_id = x.v AND STARTS_WITH(c.concept_code, x.p)),
icd_std_all AS (SELECT DISTINCT a.s, r.concept_id_2 AS concept_id FROM icd_src a
  JOIN `{CDR}.concept_relationship` r ON r.concept_id_1 = a.concept_id AND r.relationship_id = 'Maps to'),
-- Keep a standard target only if every ICD code mapping to it is in the set. Combination codes (e.g. O98.7x
-- "HIV complicating pregnancy") also map to generic targets such as "First trimester pregnancy" or
-- "History of event"; those are shared with many unrelated codes and are dropped here.
icd_std AS (SELECT t.s, t.concept_id FROM icd_std_all t
  JOIN `{CDR}.concept_relationship` r2 ON r2.concept_id_2 = t.concept_id AND r2.relationship_id = 'Maps to'
  JOIN `{CDR}.concept` c2 ON c2.concept_id = r2.concept_id_1 AND c2.vocabulary_id IN ('ICD10CM', 'ICD9CM')
  LEFT JOIN icd_src x ON x.s = t.s AND x.concept_id = r2.concept_id_1
  GROUP BY t.s, t.concept_id HAVING COUNTIF(x.concept_id IS NULL) = 0),
ig_ing AS (SELECT DISTINCT x.s, x.drx, c.concept_id FROM ({z("ig")}) x
  JOIN `{CDR}.concept` c ON c.vocabulary_id IN ('RxNorm', 'RxNorm Extension') AND c.concept_class_id = 'Ingredient'
   AND REGEXP_CONTAINS(LOWER(c.concept_name), x.rx)),
cmap AS (
  SELECT s, concept_id, 'icd source code' AS how FROM icd_src
  UNION ALL SELECT s, concept_id, 'icd maps-to standard' FROM icd_std
  UNION ALL SELECT x.s, c.concept_id, 'loinc code' FROM ({z("lc")}) x
    JOIN `{CDR}.concept` c ON c.vocabulary_id = 'LOINC' AND c.concept_code = x.c
  UNION ALL SELECT x.s, c.concept_id, 'measurement name regex' FROM ({z("mr")}) x
    JOIN `{CDR}.concept` c ON c.domain_id = 'Measurement' AND c.standard_concept = 'S'
     AND REGEXP_CONTAINS(LOWER(c.concept_name), x.inc) AND (x.exc = '' OR NOT REGEXP_CONTAINS(LOWER(c.concept_name), x.exc))
  UNION ALL SELECT g.s, ca.descendant_concept_id, 'ingredient descendant' FROM ig_ing g
    JOIN `{CDR}.concept_ancestor` ca ON ca.ancestor_concept_id = g.concept_id
    JOIN `{CDR}.concept` d ON d.concept_id = ca.descendant_concept_id
    WHERE g.drx = '' OR REGEXP_CONTAINS(LOWER(d.concept_name), g.drx)
  UNION ALL SELECT x.s, ca.descendant_concept_id, 'atc descendant' FROM ({z("atc")}) x
    JOIN `{CDR}.concept` c ON c.vocabulary_id = 'ATC' AND c.concept_code = x.c
    JOIN `{CDR}.concept_ancestor` ca ON ca.ancestor_concept_id = c.concept_id
  UNION ALL SELECT x.s, ca.descendant_concept_id, 'concept descendant' FROM ({z("cid")}) x
    JOIN `{CDR}.concept_ancestor` ca ON ca.ancestor_concept_id = x.c
  UNION ALL SELECT x.s, c.concept_id, 'code range' FROM ({z("rg")}) x
    JOIN `{CDR}.concept` c ON c.vocabulary_id = x.v AND LENGTH(c.concept_code) = LENGTH(x.lo)
     AND c.concept_code BETWEEN x.lo AND x.hi{str_sql}
)'''
    return cte, params


# Event rows from every EHR domain table, one row per (person, concept id) with a "has a value" flag.
EVENTS = f'''
ev AS (
  SELECT person_id, cid, condition_start_date AS d, TRUE AS v FROM `{CDR}.condition_occurrence`, UNNEST([condition_concept_id, condition_source_concept_id]) AS cid
  UNION ALL SELECT person_id, cid, observation_date, TRUE FROM `{CDR}.observation`, UNNEST([observation_concept_id, observation_source_concept_id]) AS cid
  UNION ALL SELECT person_id, cid, measurement_date, (value_as_number IS NOT NULL OR IFNULL(value_as_concept_id, 0) != 0)
    FROM `{CDR}.measurement`, UNNEST([measurement_concept_id, measurement_source_concept_id]) AS cid
  UNION ALL SELECT person_id, drug_concept_id, drug_exposure_start_date, TRUE FROM `{CDR}.drug_exposure`
  UNION ALL SELECT person_id, cid, procedure_date, TRUE FROM `{CDR}.procedure_occurrence`, UNNEST([procedure_concept_id, procedure_source_concept_id]) AS cid
  UNION ALL SELECT person_id, visit_concept_id, visit_start_date, TRUE FROM `{CDR}.visit_occurrence`
)'''
# Lighter version for the cohort: HIV codes and ARVs only live in these three tables.
EVENTS_COHORT = f'''
ev AS (
  SELECT person_id, cid, condition_start_date AS d FROM `{CDR}.condition_occurrence`, UNNEST([condition_concept_id, condition_source_concept_id]) AS cid
  UNION ALL SELECT person_id, cid, observation_date FROM `{CDR}.observation`, UNNEST([observation_concept_id, observation_source_concept_id]) AS cid
  UNION ALL SELECT person_id, drug_concept_id, drug_exposure_start_date FROM `{CDR}.drug_exposure`
)'''
"""

COHORT_MD = r"""## 1. HIV cohort
Builds each component separately, shows their overlap, then takes the union named in `COHORT`.
"""

COHORT_CELL = r"""cte, params = concept_map({"__hiv_dx", "__arv"})
coh = run(f'''WITH {cte}, {EVENTS_COHORT.strip()},
hits AS (SELECT DISTINCT m.s, e.person_id, e.d FROM ev e JOIN (SELECT DISTINCT s, concept_id FROM cmap) m ON e.cid = m.concept_id)
SELECT s, person_id, COUNT(DISTINCT d) AS n_dates FROM hits GROUP BY s, person_id''', params, "cohort: EHR")

self_rep = run(f'''
SELECT DISTINCT o.person_id FROM `{CDR}.observation` o
WHERE LOWER(o.value_source_value) = 'infectiousdiseasecondition_hivaids'
   OR o.value_source_concept_id IN (SELECT concept_id FROM `{CDR}.concept`
                                    WHERE vocabulary_id = 'PPI' AND LOWER(concept_code) = 'infectiousdiseasecondition_hivaids')''',
               label="cohort: self-report")

C = {
    "dx":   set(coh.loc[coh.s == "__hiv_dx", "person_id"]),
    "dx2":  set(coh.loc[(coh.s == "__hiv_dx") & (coh.n_dates >= 2), "person_id"]),
    "arv":  set(coh.loc[coh.s == "__arv", "person_id"]),
    "self": set(self_rep.person_id),
}
HIV = set().union(*(C[k.strip()] for k in COHORT.split("|")))
N_HIV = len(HIV)

rows = [(k, len(v)) for k, v in C.items()]
rows += [("dx & self", len(C["dx"] & C["self"])), ("dx only (not self)", len(C["dx"] - C["self"])),
         ("self only (not dx)", len(C["self"] - C["dx"])), ("arv & not (dx|self)", len(C["arv"] - C["dx"] - C["self"])),
         (f"COHORT = {COHORT}", N_HIV)]
cohort_summary = pd.DataFrame(rows, columns=["definition", "participants"])
cohort_summary["participants"] = cohort_summary["participants"].map(mask)
cohort_summary.to_csv(f"{OUT_DIR}/cohort_summary.csv", index=False)
display(cohort_summary)
hiv_param = arr("hiv", "INT64", sorted(HIV))
"""

REVIEW_MD = r"""## 2. Resolve EHR concept sets — **REVIEW**
Lists how many concepts each set pulled in and how. The full list goes to `concept_set_review.csv`; skim it for
concepts that do not belong (e.g. an over-broad name regex) and edit the specs above if needed.
"""

REVIEW_CELL = r"""cte, params = concept_map()
review = run(f'''WITH {cte}
SELECT m.s AS concept_set, m.how, c.concept_id, c.concept_name, c.vocabulary_id, c.concept_code, c.domain_id, c.standard_concept
FROM (SELECT DISTINCT s, concept_id, how FROM cmap) m JOIN `{CDR}.concept` c USING (concept_id)
WHERE NOT STARTS_WITH(m.s, "__")''', params, "concept sets")
review.sort_values(["concept_set", "how", "concept_name"]).to_csv(f"{OUT_DIR}/concept_set_review.csv", index=False)
summary = review.groupby(["concept_set", "how"]).size().unstack(fill_value=0)
display(summary)
ehr_sets = sorted(FIELDS.loc[FIELDS.src == "ehr", "name"])
print("Sets with no concepts:", [s for s in ehr_sets if s not in summary.index and s not in GENERIC])
# Spot-check a few sets:
for s in ["vl", "cd4", "hiv_test", "art_str", "art_lai"]:
    print(f"\n--- {s} (first 15) ---")
    print(review.loc[review.concept_set == s, ["concept_id", "concept_name", "vocabulary_id"]].head(15).to_string(index=False))
"""

EHR_MD = r"""## 3. Count EHR concept sets
`n_*_any` = at least one record of any concept in the set. `n_*_valid` = for measurements, a record with a numeric
or coded result; for other domains, same as any.
"""

EHR_CELL = r"""cte, params = concept_map()
ehr_counts = run(f'''WITH {cte}, {EVENTS.strip()},
hits AS (SELECT DISTINCT m.s, e.person_id, e.v FROM ev e JOIN (SELECT DISTINCT s, concept_id FROM cmap) m ON e.cid = m.concept_id)
SELECT s AS name,
  COUNT(DISTINCT person_id) AS n_all_any,
  COUNT(DISTINCT IF(v, person_id, NULL)) AS n_all_valid,
  COUNT(DISTINCT IF(person_id IN UNNEST(@hiv), person_id, NULL)) AS n_hiv_any,
  COUNT(DISTINCT IF(v AND person_id IN UNNEST(@hiv), person_id, NULL)) AS n_hiv_valid
FROM hits GROUP BY s''', params + [hiv_param], "EHR concept sets")
display(ehr_counts.sort_values("n_hiv_valid", ascending=False).head(20).assign(**{c: lambda d, c=c: d[c].map(mask) for c in ["n_all_any", "n_all_valid", "n_hiv_any", "n_hiv_valid"]}))
"""

SURVEY_MD = r"""## 4. Count survey items
Codebook item codes are matched to the CDR's PPI question concepts (case-insensitive) and to
`observation_source_value`. **Valid** = an answer other than Skip / Prefer not to answer / Don't know.
`n_hiv_self` applies to Personal and Family Health History "who in your family…" items: participants answering *Self*.
"""

SURVEY_CELL = r"""codes = sorted(FIELDS.loc[FIELDS.src == "survey", "name"].unique())
qcon = run(f'''SELECT concept_id, LOWER(concept_code) AS code, concept_name, concept_class_id FROM `{CDR}.concept`
WHERE vocabulary_id = 'PPI' AND LOWER(concept_code) IN UNNEST(@codes)''', [arr("codes", "STRING", codes)], "survey: PPI concepts")
qmap = qcon[qcon.concept_class_id.str.contains("Question", na=False)].drop_duplicates("concept_id")

survey_counts = run(f'''
WITH qm AS ({zipped("qm", ["qid", "code"])}),
o AS (
  SELECT o.person_id, COALESCE(qm.code, LOWER(o.observation_source_value)) AS code, o.value_source_concept_id, o.value_source_value
  FROM `{CDR}.observation` o LEFT JOIN qm ON o.observation_source_concept_id = qm.qid
  WHERE o.observation_source_concept_id IN UNNEST(@qm_qid) OR LOWER(o.observation_source_value) IN UNNEST(@codes)),
a AS (SELECT o.*, LOWER(CONCAT(IFNULL(c.concept_name, ''), ' ', IFNULL(o.value_source_value, ''))) AS ans  -- e.g. "skip pmi_skip"
      FROM o LEFT JOIN `{CDR}.concept` c ON c.concept_id = o.value_source_concept_id),
b AS (SELECT *, NOT REGEXP_CONTAINS(ans, r"(^|[ _:])(skip|skipped question|prefer ?not ?to ?answer|don.?t ?know)( |$)|pmi_(skip|prefernottoanswer|dontknow)") AS v,
             person_id IN UNNEST(@hiv) AS h FROM a)
SELECT code AS name,
  COUNT(DISTINCT person_id) AS n_all_any, COUNT(DISTINCT IF(v, person_id, NULL)) AS n_all_valid,
  COUNT(DISTINCT IF(h, person_id, NULL)) AS n_hiv_any, COUNT(DISTINCT IF(h AND v, person_id, NULL)) AS n_hiv_valid,
  COUNT(DISTINCT IF(h AND REGEXP_CONTAINS(ans, r"(^| )self( |$)"), person_id, NULL)) AS n_hiv_self
FROM b WHERE code IN UNNEST(@codes) GROUP BY code''',
    [arr("qm_qid", "INT64", qmap.concept_id), arr("qm_code", "STRING", qmap.code), arr("codes", "STRING", codes), hiv_param],
    "survey items")

match = pd.DataFrame({"name": codes})
match["ppi_question_concept"] = match.name.isin(qmap.code)
match["rows_in_observation"] = match.name.isin(survey_counts.name)
match.to_csv(f"{OUT_DIR}/survey_item_matching.csv", index=False)
print(f"{match.rows_in_observation.sum()} of {len(codes)} survey items found in observation")
print("Not found:", list(match.loc[~match.rows_in_observation, "name"]))
"""

COLS_MD = r"""## 5. Count table columns (OMOP, Workbench ds_, wearables, Exploring the Mind)
Participants with at least one row where the column is non-null. Columns suppressed in the Registered Tier show 0.
"""

COLS_CELL = r"""def dataset_columns(ds):
    # {table: set(columns)} for one dataset.
    try:
        info = run(f'''SELECT table_name, column_name FROM `{ds}.INFORMATION_SCHEMA.COLUMNS`''', label=f"schema {ds}")
        return info.groupby("table_name").column_name.apply(set).to_dict()
    except Exception as e:  # fall back to the API if INFORMATION_SCHEMA is not readable
        print("INFORMATION_SCHEMA not available, listing tables via the API:", str(e)[:120])
        return {t.table_id: {f.name for f in client.get_table(t.reference).schema} for t in client.list_tables(ds)}

# Table name -> (dataset, columns); the CDR wins over extra datasets.
cols_by_table, table_ds = {}, {}
for ds in reversed([CDR] + EXTRA):
    for t, cols in dataset_columns(ds).items():
        cols_by_table[t], table_ds[t] = cols, ds
print(len(cols_by_table), "tables across", [CDR] + EXTRA)
hint = re.compile(r"zip|ses|socio|flanker|gradcpt|delay|emorecog|task|healthkit|fitbit|activity|sleep|heart", re.I)
print("Tables that may hold wearable / ZIP / cognitive-task data:", sorted(t for t in cols_by_table if hint.search(t)))

col_fields = FIELDS[FIELDS.src.isin(["omop", "ds", "wear", "emt"])].copy()
col_fields["dict_table"] = col_fields.apply(lambda r: r.id.split("/")[-2], axis=1)
res_rows, col_counts = [], []
for dict_table, grp in col_fields.groupby("dict_table"):
    cands = [dict_table] + TABLE_ALIASES.get(dict_table, [])
    table = next((t for t in cands if t in cols_by_table), None)
    if table is None or "person_id" not in cols_by_table[table]:
        status = "table not found" if table is None else "no person_id column"
        res_rows += [(f, dict_table, table, status) for f in grp.id]
        continue
    present = [n for n in grp.name.unique() if n in cols_by_table[table] and n != "person_id"]
    res_rows += [(f, dict_table, table, "ok" if n in present or n == "person_id" else "column not found")
                 for f, n in zip(grp.id, grp.name)]
    exprs = ["COUNT(DISTINCT person_id) AS `person_id__all`",
             "COUNT(DISTINCT IF(person_id IN UNNEST(@hiv), person_id, NULL)) AS `person_id__hiv`"]
    for n in present:
        exprs += [f"COUNT(DISTINCT IF(`{n}` IS NOT NULL, person_id, NULL)) AS `{n}__all`",
                  f"COUNT(DISTINCT IF(`{n}` IS NOT NULL AND person_id IN UNNEST(@hiv), person_id, NULL)) AS `{n}__hiv`"]
    try:
        r = run(f"SELECT {', '.join(exprs)} FROM `{table_ds[table]}.{table}`", [hiv_param], f"columns: {table}").iloc[0]
    except Exception as e:  # keep going; the error is recorded
        print("  failed:", e)
        res_rows = [(f, d, t, f"error: {e}"[:200]) if t == table else (f, d, t, s) for f, d, t, s in res_rows]
        continue
    for f, n in zip(grp.id, grp.name):
        if n in present or n == "person_id":
            col_counts.append(dict(id=f, n_all_any=r[f"{n}__all"], n_all_valid=r[f"{n}__all"],
                                   n_hiv_any=r[f"{n}__hiv"], n_hiv_valid=r[f"{n}__hiv"]))
resolution = pd.DataFrame(res_rows, columns=["field_id", "dictionary_table", "cdr_table", "status"])
resolution["dataset"] = resolution.cdr_table.map(table_ds)
resolution.to_csv(f"{OUT_DIR}/table_resolution.csv", index=False)
display(resolution.groupby(["dictionary_table", "cdr_table", "status"], dropna=False).size().rename("fields").reset_index())
"""

ASSEMBLE_MD = r"""## 6. Assemble, mask and save
"""

ASSEMBLE_CELL = r"""COUNT_COLS = ["n_all_any", "n_all_valid", "n_hiv_any", "n_hiv_valid", "n_hiv_self"]
out = FIELDS.copy()
ehr = out.src == "ehr"
sv = out.src == "survey"
parts = [
    out[ehr].merge(ehr_counts, on="name", how="left"),
    out[sv].merge(survey_counts, on="name", how="left"),
    out[~ehr & ~sv].merge(pd.DataFrame(col_counts, columns=["id"] + COUNT_COLS[:4]), on="id", how="left"),
]
out = pd.concat(parts, ignore_index=True)

status = pd.Series("ok", index=out.index)
status[ehr & out.name.isin(GENERIC)] = "generic placeholder (not countable)"
status[(out.src == "ehr") & out.n_all_any.isna() & ~out.name.isin(GENERIC)] = "no records / no concepts"
status[(out.src == "survey") & out.n_all_any.isna()] = "question not found in CDR"
res = resolution.set_index("field_id").status
cols_mask = out.src.isin(["omop", "ds", "wear", "emt"])
status[cols_mask] = out.loc[cols_mask, "id"].map(res).fillna("not counted")
out["status"] = status
for c in COUNT_COLS:
    out[c] = out[c].where(out.status != "generic placeholder (not countable)")
    out.loc[out.status.isin(["no records / no concepts", "question not found in CDR"]) & out[c].isna(), c] = 0

out.loc[~out.name.str.endswith("_yes"), "n_hiv_self"] = None   # only meaningful for "who in your family" items
out["n_hiv_cohort"] = N_HIV
out["pct_hiv_valid"] = (100 * out.n_hiv_valid / N_HIV).round(1)
small = out.n_hiv_valid.between(1, MASK_AT_OR_BELOW)
out.loc[small, "pct_hiv_valid"] = None
for c in COUNT_COLS + ["n_hiv_cohort"]:
    out[c] = out[c].map(mask)

out = out[["id", "src", "group", "name", "label", "privacy", "status", "n_hiv_cohort", "n_hiv_valid", "pct_hiv_valid",
           "n_hiv_any", "n_hiv_self", "n_all_valid", "n_all_any"]].rename(columns={"id": "field_id"})
out.to_csv(f"{OUT_DIR}/field_counts_hiv.csv", index=False)

json.dump({"cdr": CDR, "cohort": COHORT, "n_hiv_cohort": mask(N_HIV), "mask_at_or_below": MASK_AT_OR_BELOW,
           "run_at": datetime.datetime.now().isoformat(timespec="seconds")}, open(f"{OUT_DIR}/run_info.json", "w"), indent=2)

with zipfile.ZipFile("kg_aou_counts.zip", "w", zipfile.ZIP_DEFLATED) as zf:
    for f in sorted(os.listdir(OUT_DIR)):
        zf.write(os.path.join(OUT_DIR, f), f"kg_aou_counts/{f}")

print(out.status.value_counts().to_string())
display(out.sort_values("pct_hiv_valid", ascending=False).head(40))
"""

FINAL_MD = r"""## 7. Download
In the Jupyter file browser (left panel, or *File → Open*), right-click **`kg_aou_counts.zip`** → *Download*.
Before downloading, check that `field_counts_hiv.csv` and `cohort_summary.csv` contain no count from 1 to
`MASK_AT_OR_BELOW` (the masking above does this; also confirm nothing can be recovered by subtracting two counts).
Copy the zip to `AllOfUs_Analysis/kg_aou/` locally to merge the counts into the map and viewer.
"""


def cell(kind, src):
    lines = src.strip("\n").splitlines(keepends=True)
    c = {"cell_type": kind, "metadata": {}, "source": lines}
    if kind == "code":
        c.update(execution_count=None, outputs=[])
    return c


def main():
    fields_json = json.dumps(used_fields(), ensure_ascii=False)
    assert "'''" not in fields_json
    sets = {k: {f: v for f, v in d.items() if f not in ("table", "label", "note")} for k, d in {**CONCEPT_SETS, **COHORT_SETS}.items()}
    sets_json = json.dumps(sets, ensure_ascii=False)
    assert "'''" not in sets_json
    cells = [
        cell("markdown", MD_INTRO),
        cell("code", CONFIG),
        cell("code", SETUP),
        cell("code", FIELDS.replace("__USED_FIELDS_JSON__", fields_json)),
        cell("code", SPECS.replace("__SETS_JSON__", sets_json)),
        cell("code", CMAP),
        cell("markdown", COHORT_MD), cell("code", COHORT_CELL),
        cell("markdown", REVIEW_MD), cell("code", REVIEW_CELL),
        cell("markdown", EHR_MD), cell("code", EHR_CELL),
        cell("markdown", SURVEY_MD), cell("code", SURVEY_CELL),
        cell("markdown", COLS_MD), cell("code", COLS_CELL),
        cell("markdown", ASSEMBLE_MD), cell("code", ASSEMBLE_CELL),
        cell("markdown", FINAL_MD),
    ]
    nb = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                       "language_info": {"name": "python"}},
          "nbformat": 4, "nbformat_minor": 5}
    path = OUT / "kg_aou_hiv_field_counts.ipynb"
    path.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {path} ({path.stat().st_size / 1e3:.0f} KB, {len(cells)} cells)")


if __name__ == "__main__":
    main()
