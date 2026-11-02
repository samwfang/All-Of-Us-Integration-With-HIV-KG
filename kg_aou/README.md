# HIV KG × All of Us field map

Maps entities in the HIV virologic-failure knowledge graph (`kg_export/v2.1`) to fields in the
All of Us Registered Tier (v9 CDR data dictionary + survey codebooks in `AllOfUs_Analysis/`).

```bash
python3 build_map.py              # default KG: ../../kg_export/v2.1
python3 build_map.py --unmapped 50  # also list the top unmapped entities
```

Needs `openpyxl`. Open `out/kg_aou_viewer.html` in a browser (the Graph tab loads vis-network from a CDN).

| File | Contents |
|---|---|
| `build_catalog.py` | Reads both workbooks into one catalog of OMOP / Workbench / survey / wearable / Exploring the Mind fields, with Registered Tier privacy status |
| `mapping_rules.py` | `CONCEPT_SETS` (runnable specs for EHR content stored as concept rows: ICD prefixes, LOINC codes, RxNorm ingredients…; the single source for both the viewer's descriptions and the Workbench notebook's queries), `COHORT_SETS` (HIV cohort definition), `VARIABLES` (All of Us constructs → fields), `GAP_RULES` (out-of-scope reasons), `ENTITY_RULES` (KG entity name regexes → variables) |
| `build_map.py` | Applies the rules, validates every field reference, writes the outputs |
| `viewer_template.html` | Viewer; data is injected at build time |
| `out/entity_field_map.csv` | One row per entity × field, with `link` = direct / proxy |
| `out/entity_variable_map.csv` | One row per entity × variable |
| `out/entity_gaps.csv` | Unmapped entities, with the out-of-scope reason where one applies |
| `out/aou_fields.csv` | The full field catalog |

## Counting HIV participants per field (Researcher Workbench)

After changing `CONCEPT_SETS`, rerun `python3 build_map.py` (viewer, CSVs) and `python3 make_workbench_notebook.py` (notebook).

`python3 make_workbench_notebook.py` writes `out/kg_aou_hiv_field_counts.ipynb`, with the mapped-field list
embedded. Upload it to a Registered Tier workspace and run all cells. It builds an HIV cohort (diagnosis codes and/or
self-report, configurable), resolves the EHR concept sets, and counts participants with a valid entry in every
mapped field. Counts of 1–20 are masked. Download `kg_aou_counts.zip`.

**Direct**: the field measures the same construct, read off or derived by an objective rule
(threshold, date difference, code list). **Proxy**: a related or broader construct, or the
derivation needs judgement. A link is Direct only if both the entity → variable rule and the
variable → field entry are Direct.

EHR concept sets give vocabulary hints (ICD-10-CM, LOINC, RxNorm/ATC). Resolve exact concept
IDs in Athena or the Workbench cohort builder before use.
