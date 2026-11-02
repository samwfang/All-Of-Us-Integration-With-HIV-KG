"""Curated rules linking KG entities to All of Us Registered Tier fields.

Two layers keep the rules auditable:

1. VARIABLES: named All of Us constructs (e.g. "food_insecurity"). Each lists the fields that
   measure it, as (field id or glob, strength, note). Field ids come from build_catalog.py, or
   from CONCEPT_SETS below for EHR content that lives in concept rows rather than columns.
2. ENTITY_RULES: regexes over KG entity names that route an entity to one or more variables
   with a strength.

An entity-field link is Direct only if both the entity->variable rule and the variable->field
entry are Direct; otherwise it is Proxy.

  Direct: the field measures the same construct as the KG entity, read off as-is or derived by a
          standard, objective rule (a threshold, a date difference, a code list).
  Proxy:  the field measures a related, broader or narrower construct, or deriving the entity
          needs assumptions or judgement (e.g. general discrimination standing in for HIV stigma).
"""

D, P = "direct", "proxy"

# EHR content is stored as concept rows inside OMOP domain tables, so each EHR "field" is a concept set.
# These specs are the single source for both the map (describe() turns them into the text shown in the
# viewer and CSVs) and the Workbench notebook (make_workbench_notebook.py runs them as BigQuery queries).
#
# Spec keys (all optional, combined with OR):
#   icd10 / icd9      ICD-10-CM / ICD-9-CM code prefixes. Source codes are matched by prefix; their "Maps to"
#                     standard targets are added only when every ICD code mapping to the target is in the set.
#   loinc             exact LOINC codes
#   name_regex        (include, exclude) regexes on lower-cased standard Measurement concept names
#   ingredients       RxNorm ingredient names (regex-anchored); all drug products containing them are included
#   drug_name_regex   ...restricted to products whose name matches this regex
#   atc               ATC class codes; all descendant drugs are included
#   concept_ids       OMOP concept IDs plus their descendants
#   code_ranges       [(vocabulary, low, high)] code ranges, e.g. CPT4
#   derived           computed in the notebook (see make_workbench_notebook.py)
#   generic           placeholder, not countable
#   note              extra human-readable context appended to the description


def rng(letter, a, b, width=2):
    return [f"{letter}{i:0{width}d}" for i in range(a, b + 1)]


NNRTI = ["efavirenz", "nevirapine", "rilpivirine", "etravirine", "doravirine", "delavirdine"]
PI = ["lopinavir", "atazanavir", "darunavir", "fosamprenavir", "amprenavir", "saquinavir", "indinavir", "nelfinavir", "tipranavir"]
INSTI = ["dolutegravir", "bictegravir", "raltegravir", "elvitegravir", "cabotegravir"]
NRTI = ["tenofovir.*", "emtricitabine", "lamivudine", "abacavir", "zidovudine", "stavudine", "didanosine", "zalcitabine"]
OTHER_ARV = ["ritonavir", "cobicistat", "maraviroc", "enfuvirtide", "ibalizumab.*", "fostemsavir", "lenacapavir"]
HIV_CODES = dict(icd10=["B20", "Z21", "O98.7", "B97.35"], icd9=["042", "V08", "079.53"])

CONCEPT_SETS = {
    # condition_occurrence
    "hiv": dict(table="condition_occurrence", label="HIV disease", **HIV_CODES),
    "aids_oi": dict(table="condition_occurrence", label="AIDS-defining / opportunistic infections",
                    icd10=["B59", "B45", "B25", "B58", "A31", "B37.1", "B37.81", "C46", "A81.2", "A07.2", "B39"],
                    note="pneumocystosis, cryptococcosis, CMV, toxoplasmosis, nontuberculous mycobacteria, candidal esophagitis, Kaposi sarcoma, PML, cryptosporidiosis, histoplasmosis"),
    "tb": dict(table="condition_occurrence", label="Tuberculosis (active or latent)",
               icd10=rng("A", 15, 19) + ["R76.1", "Z22.7"], icd9=[f"0{i}" for i in range(10, 19)]),
    "hbv": dict(table="condition_occurrence", label="Hepatitis B", icd10=["B16", "B18.0", "B18.1", "Z22.51"]),
    "hcv": dict(table="condition_occurrence", label="Hepatitis C", icd10=["B17.1", "B18.2"]),
    "sti": dict(table="condition_occurrence", label="Sexually transmitted infections", icd10=rng("A", 50, 64),
                note="syphilis, gonorrhea, chlamydia, genital herpes, etc."),
    "depression_dx": dict(table="condition_occurrence", label="Depressive disorders",
                          icd10=["F32", "F33", "F34.1"], icd9=["296.2", "296.3", "311", "300.4"]),
    "anxiety_dx": dict(table="condition_occurrence", label="Anxiety disorders", icd10=["F40", "F41"]),
    "ptsd_dx": dict(table="condition_occurrence", label="PTSD and acute stress reaction", icd10=["F43.0", "F43.1"], icd9=["309.81"]),
    "smi_dx": dict(table="condition_occurrence", label="Serious mental illness", icd10=rng("F", 20, 29) + ["F31"],
                   note="psychotic disorders and bipolar disorder"),
    "suicide_dx": dict(table="condition_occurrence", label="Suicidal ideation / attempt", icd10=["R45.851", "T14.91", "Z91.5"]),
    "aud_dx": dict(table="condition_occurrence", label="Alcohol-related disorders", icd10=["F10"], icd9=["303", "305.0"]),
    "sud_dx": dict(table="condition_occurrence", label="Drug use disorders", icd10=rng("F", 11, 16) + ["F18", "F19"],
                   icd9=["304", "305.2", "305.3", "305.4", "305.5", "305.6", "305.7", "305.8", "305.9"]),
    "opioid_dx": dict(table="condition_occurrence", label="Opioid-related disorders", icd10=["F11"]),
    "stimulant_dx": dict(table="condition_occurrence", label="Cocaine / other stimulant disorders", icd10=["F14", "F15"]),
    "nicotine_dx": dict(table="condition_occurrence", label="Nicotine dependence / tobacco use", icd10=["F17", "Z72.0", "Z87.891"], icd9=["305.1"]),
    "cognitive_dx": dict(table="condition_occurrence", label="Cognitive impairment / dementia",
                         icd10=["F01", "F02", "F03", "G30", "G31.84", "R41.81", "R41.84"]),
    "sleep_dx": dict(table="condition_occurrence", label="Sleep disorders", icd10=["G47", "F51"], note="includes sleep apnea"),
    "malnutrition_dx": dict(table="condition_occurrence", label="Malnutrition / wasting", icd10=rng("E", 40, 46) + ["R64"]),
    "obesity_dx": dict(table="condition_occurrence", label="Obesity / overweight", icd10=["E66", "Z68.3", "Z68.4"]),
    "anemia_dx": dict(table="condition_occurrence", label="Anemia", icd10=rng("D", 50, 64)),
    "kidney_dx": dict(table="condition_occurrence", label="Kidney disease", icd10=["N17", "N18", "N19"]),
    "liver_dx": dict(table="condition_occurrence", label="Liver disease", icd10=rng("K", 70, 77)),
    "diabetes_dx": dict(table="condition_occurrence", label="Diabetes", icd10=rng("E", 8, 13)),
    "htn_dx": dict(table="condition_occurrence", label="Hypertension", icd10=rng("I", 10, 16)),
    "cvd_dx": dict(table="condition_occurrence", label="Cardiovascular disease", icd10=rng("I", 20, 25) + ["I50"] + rng("I", 60, 69),
                   note="ischemic heart disease, heart failure, cerebrovascular disease"),
    "cancer_dx": dict(table="condition_occurrence", label="Malignancies", icd10=["C"]),
    "pregnancy_dx": dict(table="condition_occurrence", label="Pregnancy", icd10=["O", "Z33", "Z34"]),
    "art_adverse": dict(table="condition_occurrence", label="Adverse effects of antiretrovirals", icd10=["T37.5X5"],
                        note="adverse effect of antiviral drugs; drug-specific findings (lipodystrophy, neuropathy) are not included"),
    "art_underdosing": dict(table="condition_occurrence", label="Underdosing of antiretrovirals", icd10=["T37.5X6"]),
    "noncompliance": dict(table="observation", label="Documented medication / treatment noncompliance", icd10=["Z91.1"],
                          note="Z91.12 intentional underdosing, Z91.13 unintentional underdosing, Z91.14 other medication noncompliance, Z91.19 other treatment noncompliance"),
    # observation (Z-code social needs)
    "homeless_z": dict(table="observation", label="Homelessness / inadequate housing (Z-codes)", icd10=["Z59.0", "Z59.1", "Z59.81"]),
    "food_z": dict(table="observation", label="Food insecurity (Z-code)", icd10=["Z59.4"]),
    "poverty_z": dict(table="observation", label="Low income / poverty (Z-codes)", icd10=["Z59.5", "Z59.6", "Z59.86"]),
    "transport_z": dict(table="observation", label="Transportation insecurity (Z-code)", icd10=["Z59.82"]),
    "unemployment_z": dict(table="observation", label="Unemployment (Z-code)", icd10=["Z56.0"]),
    "education_z": dict(table="observation", label="Education / literacy problems (Z-codes)", icd10=["Z55"]),
    "incarceration_z": dict(table="observation", label="Imprisonment / legal problems (Z-codes)", icd10=["Z65.1", "Z65.2", "Z65.3"]),
    "isolation_z": dict(table="observation", label="Living alone / social exclusion (Z-codes)", icd10=["Z60.2", "Z60.4"]),
    "discrimination_z": dict(table="observation", label="Target of perceived discrimination (Z-code)", icd10=["Z60.5"]),
    "violence_z": dict(table="observation", label="Abuse / violence exposure", icd10=["T74", "T76", "Z91.41", "Z69"],
                       note="these codes (and assault / perpetrator codes X92–Y09) are row-suppressed in the Registered Tier, so this set is effectively empty there; see the Concept Suppressions sheet"),
    "trauma_hx_z": dict(table="observation", label="Personal history of psychological trauma (Z-codes)", icd10=["Z91.4", "Z62.81"],
                        note="the abuse-history codes are row-suppressed in the Registered Tier, so this set is effectively empty there"),
    # measurement
    "vl": dict(table="measurement", label="HIV-1 RNA viral load", loinc=["20447-9"], name_regex=(r"hiv ?1 rna", r"presence|genotyp|ratio"),
               note="value_as_number in copies/mL; operator_concept_id marks '<' (below detection) results"),
    "cd4": dict(table="measurement", label="CD4+ T-cell count / percent", loinc=["24467-3"],
                name_regex=(r"^cd3\+cd4\+ \(t4 helper\) cells ?(\[#/volume\]|/100 cells)|^cd4\+? (t[- ]?)?cells? (\[#/volume\]|/100)|absolute cd4", r"cd8|ratio")),
    "cd4cd8": dict(table="measurement", label="CD4/CD8 ratio", name_regex=(r"cd4.*cd8.*ratio|cd3\+cd4\+.*/.*cd3\+cd8\+|cd4/cd8", r"")),
    "hiv_geno": dict(table="measurement", label="HIV genotypic resistance testing", name_regex=(r"hiv ?1.*(genotyp|resistance|mutation|susceptib)", r""),
                     note="mutation-level results are rarely structured; value_source_value is suppressed in the Registered Tier"),
    "hiv_test": dict(table="measurement", label="HIV screening / diagnostic tests",
                     name_regex=(r"hiv ?(1|2|1\+2|1\+o\+2|1 and 2).*(\bab\b|\bag\b|antibod|antigen)", r"rna|dna"),
                     note="date of first positive test approximates diagnosis date"),
    "hep_labs": dict(table="measurement", label="Hepatitis B / C laboratory tests",
                     name_regex=(r"hepatitis b virus (surface ag|dna)|hepatitis c virus (ab|rna)", r"donor|hiv|\+")),
    "weight_bmi": dict(table="measurement", label="Body weight, height and BMI", loinc=["29463-7", "3141-9", "8302-2", "39156-5"],
                       note="includes enrollment Physical Measurements"),
    "hemoglobin": dict(table="measurement", label="Hemoglobin", loinc=["718-7"]),
    "renal_labs": dict(table="measurement", label="Creatinine / eGFR", loinc=["2160-0"], name_regex=(r"glomerular filtration rate", r"")),
    "liver_labs": dict(table="measurement", label="Liver enzymes", loinc=["1742-6", "1920-8"],
                       name_regex=(r"^(alanine|aspartate) aminotransferase \[enzymatic activity/volume\]", r"")),
    "glycemic_labs": dict(table="measurement", label="Glucose / HbA1c", loinc=["4548-4", "2345-7"], name_regex=(r"^hemoglobin a1c/hemoglobin\.total", r"")),
    "lipid_labs": dict(table="measurement", label="Lipids", loinc=["2093-3", "2085-9", "13457-7", "18262-6", "2571-8"]),
    # drug_exposure
    "art": dict(table="drug_exposure", label="Antiretroviral therapy (any)", ingredients=NNRTI + PI + INSTI + NRTI + OTHER_ARV,
                note="includes drugs also used for PrEP, HBV or COVID-19 (tenofovir, emtricitabine, lamivudine, ritonavir)"),
    "art_nnrti": dict(table="drug_exposure", label="NNRTIs", ingredients=NNRTI),
    "art_pi": dict(table="drug_exposure", label="Protease inhibitors", ingredients=PI, note="ritonavir alone is excluded (also used in nirmatrelvir/ritonavir)"),
    "art_insti": dict(table="drug_exposure", label="Integrase inhibitors", ingredients=INSTI),
    "art_nrti": dict(table="drug_exposure", label="NRTI backbones", ingredients=NRTI),
    "art_str": dict(table="drug_exposure", label="Single-tablet ART regimens", derived="drug products containing ≥3 distinct antiretroviral ingredients"),
    "art_lai": dict(table="drug_exposure", label="Long-acting injectable ART", ingredients=["cabotegravir", "rilpivirine"],
                    drug_name_regex=r"inject|extended release suspension"),
    "moud": dict(table="drug_exposure", label="Opioid agonist / MOUD therapy", ingredients=["methadone", "buprenorphine", "naltrexone"]),
    "psychotropics": dict(table="drug_exposure", label="Antidepressants / anxiolytics / antipsychotics", atc=["N06A", "N05A", "N05B"]),
    "tb_drugs": dict(table="drug_exposure", label="TB treatment / preventive therapy",
                     ingredients=["isoniazid", "rifampin", "rifapentine", "rifabutin", "pyrazinamide", "ethambutol"]),
    "oi_prophylaxis": dict(table="drug_exposure", label="OI prophylaxis", ingredients=["sulfamethoxazole", "dapsone", "atovaquone"],
                           note="azithromycin and fluconazole are excluded as too common to indicate prophylaxis"),
    "polypharmacy": dict(table="drug_exposure", label="Concurrent non-ART medications", generic=True,
                         note="count of distinct non-ART ingredients with overlapping exposure windows"),
    # visit_occurrence / procedure
    "inpatient": dict(table="visit_occurrence", label="Inpatient and emergency visits", concept_ids=[9201, 9203, 262],
                      note="9201 Inpatient Visit, 9203 Emergency Room Visit, 262 ER and Inpatient Visit"),
    "outpatient": dict(table="visit_occurrence", label="Outpatient visits", concept_ids=[9202], note="9202 Outpatient Visit, incl. telehealth"),
    "mh_services": dict(table="procedure_occurrence", label="Mental health / behavioral services", code_ranges=[("CPT4", "90791", "90899")],
                        note="psychiatric diagnostic and psychotherapy codes"),
    "sud_services": dict(table="procedure_occurrence", label="Substance use treatment services",
                         code_ranges=[("HCPCS", "H0001", "H0050"), ("HCPCS", "G2067", "G2088"), ("CPT4", "99408", "99409")],
                         note="behavioral health HCPCS codes, opioid treatment program bundles, SBIRT"),
    # placeholders for entities naming a specific condition / lab / drug
    "other_condition": dict(table="condition_occurrence", label="Other specific diagnosis (search by concept)", generic=True,
                            note="search the condition concept hierarchy (SNOMED / ICD-10-CM) for the named condition"),
    "other_lab": dict(table="measurement", label="Other routine laboratory test (search by concept)", generic=True,
                      note="search LOINC measurement concepts for the named test, e.g. CRP, D-dimer, albumin, vitamin D"),
    "other_drug": dict(table="drug_exposure", label="Other specific medication (search by ingredient)", generic=True,
                       note="search RxNorm ingredients / ATC classes for the named drug"),
}

# Sets used only to define the HIV cohort in the Workbench notebook (not mapped to KG entities).
# Cohort-defining ARVs exclude drugs also used for PrEP (tenofovir, emtricitabine, cabotegravir, lenacapavir),
# HBV (lamivudine, tenofovir) or COVID-19 (ritonavir), and the booster cobicistat.
COHORT_SETS = {
    "__hiv_dx": dict(**HIV_CODES),
    "__arv": dict(ingredients=NNRTI + PI + ["dolutegravir", "bictegravir", "raltegravir", "elvitegravir"]
                  + ["abacavir", "zidovudine", "stavudine", "didanosine", "zalcitabine", "maraviroc", "enfuvirtide", "ibalizumab.*", "fostemsavir"]),
}


def _compress(codes):
    # ["A15", "A16", "A17"] -> "A15–A17"; other codes are kept as-is.
    out, run = [], []
    def flush():
        if len(run) > 2:
            out.append(f"{run[0]}–{run[-1]}")
        else:
            out.extend(run)
        run.clear()
    for c in codes:
        if run and len(c) == 3 and c[0] == run[-1][0] and c[1:].isdigit() and run[-1][1:].isdigit() and int(c[1:]) == int(run[-1][1:]) + 1:
            run.append(c)
        else:
            flush()
            run.append(c)
    flush()
    return ", ".join(out)


def describe(spec):
    # Human-readable description of a concept-set spec (shown in the viewer and CSVs).
    parts = []
    if spec.get("icd10"):
        parts.append("ICD-10-CM " + _compress(spec["icd10"]))
    if spec.get("icd9"):
        parts.append("ICD-9-CM " + _compress(spec["icd9"]))
    if spec.get("icd10") or spec.get("icd9"):
        parts[-1] += " (code prefixes; plus standard concepts mapped only from these codes)"
    if spec.get("loinc"):
        parts.append("LOINC " + ", ".join(spec["loinc"]))
    if spec.get("name_regex"):
        inc, exc = spec["name_regex"]
        parts.append(f"measurement concepts named /{inc}/" + (f" excluding /{exc}/" if exc else ""))
    if spec.get("ingredients"):
        names = ", ".join(n.replace(".*", "*") for n in spec["ingredients"])
        parts.append(f"RxNorm ingredients {names} and all products containing them"
                     + (f", limited to products named /{spec['drug_name_regex']}/" if spec.get("drug_name_regex") else ""))
    if spec.get("atc"):
        parts.append("ATC classes " + ", ".join(spec["atc"]) + " and all descendant drugs")
    if spec.get("concept_ids"):
        parts.append("concept IDs " + ", ".join(map(str, spec["concept_ids"])) + " and descendants")
    for v, lo, hi in spec.get("code_ranges", []):
        parts.append(f"{v} {lo}–{hi}")
    if spec.get("derived"):
        parts.append("Derived: " + spec["derived"])
    text = "; ".join(parts)
    if spec.get("note"):
        note = spec["note"][0].upper() + spec["note"][1:]
        text = f"{text}. {note}" if text else note
    return text


# (field id or glob, strength, note)
VARIABLES = {
    # ---- Demographic --------------------------------------------------------------------
    "age": dict(label="Age", fields=[
        ("ds/ds_person/date_of_birth", D, "Age at any event = event date − date of birth (both date-shifted by the same offset)"),
        ("omop/person/birth_datetime", D, "Date-shifted birth datetime"),
        ("omop/person/year_of_birth", D, "Suppressed in Registered Tier; use birth_datetime"),
    ]),
    "sex_at_birth": dict(label="Sex assigned at birth", fields=[
        ("survey/basics/biologicalsexatbirth_sexatbirth", D, "Self-report; generalized to Male / Female / Other"),
        ("ds/ds_person/sex_at_birth", D, ""),
        ("omop/person/sex_at_birth_concept_id", D, ""),
    ]),
    "gender": dict(label="Gender identity", fields=[
        ("survey/basics/gender_genderidentity", D, "Generalized to Man / Woman / Other in Registered Tier"),
        ("ds/ds_person/gender", D, "Column suppressed; use the survey item"),
        ("survey/basics/gender_closergenderdescription", D, "Transgender sub-identities; suppressed in Registered Tier"),
    ]),
    "sexual_orientation": dict(label="Sexual orientation", fields=[
        ("survey/basics/thebasics_sexualorientation", D, "Generalized to Straight / Not straight in Registered Tier"),
        ("survey/basics/genderidentity_sexualitycloserdescription", D, "Suppressed in Registered Tier"),
    ]),
    "race_ethnicity": dict(label="Race / ethnicity", fields=[
        ("survey/basics/race_whatraceethnicity", D, "Self-report; generalized to broad categories in Registered Tier"),
        ("ds/ds_person/race", D, "Column suppressed in Registered Tier; use the survey item"),
        ("ds/ds_person/ethnicity", D, "Column suppressed in Registered Tier; use the survey item"),
        ("survey/basics/*specific", D, "Detailed subgroups; suppressed in Registered Tier"),
    ]),
    "education": dict(label="Educational attainment", fields=[
        ("survey/basics/educationlevel_highestgrade", D, "Generalized categories in Registered Tier"),
        ("ds/ds_zip_code_socioeconomic/fraction_high_school_edu", P, "Area-level (3-digit ZIP) share with high-school education"),
        ("ehr/observation/education_z", P, "Clinician-coded education/literacy problems"),
    ]),
    "income": dict(label="Household income / poverty", fields=[
        ("survey/basics/income_annualincome", D, "Banded annual household income"),
        ("survey/basics/livingsituation_howmanypeople", P, "Household size, needed to compute income relative to the poverty line"),
        ("ds/ds_zip_code_socioeconomic/median_income", P, "Area-level median income"),
        ("ds/ds_zip_code_socioeconomic/fraction_poverty", P, "Area-level poverty rate"),
        ("ds/ds_zip_code_socioeconomic/fraction_assisted_income", P, "Area-level public assistance / SNAP"),
        ("ehr/observation/poverty_z", D, "Clinician-coded low income / extreme poverty"),
    ]),
    "area_deprivation": dict(label="Neighborhood deprivation", fields=[
        ("ds/ds_zip_code_socioeconomic/deprivation_index", D, "ACS-based deprivation index at 3-digit ZIP"),
        ("ds/ds_zip_code_socioeconomic/fraction_vacant_housing", P, ""),
        ("survey/sdoh/nds_*", D, "Neighborhood Disorder Scale"),
        ("survey/sdoh/ips_*", P, "Neighborhood built environment"),
    ]),
    "financial_strain": dict(label="Financial strain / cost barriers", fields=[
        ("survey/hcau/cantaffordcare_worriedaboutpaying", D, ""),
        ("survey/hcau/cantaffordcare_*", D, "Could not afford specific care types in past 12 months"),
        ("survey/hcau/delayedmedicalcare_cantaffordcopay", D, ""),
        ("survey/hcau/delayedmedicalcare_deductibletoohigh", D, ""),
        ("survey/cope/cdc_covid_19_23", P, "COVID-related hardships (job/income loss), 2020–21 only"),
    ]),
    "employment": dict(label="Employment status", fields=[
        ("survey/basics/employment_employmentstatus", D, "Generalized to employed / not employed in Registered Tier"),
        ("survey/cope/basics_12", D, "COPE repeat (2020–21)"),
        ("ehr/observation/unemployment_z", D, ""),
        ("survey/hcau/delayedmedicalcare_timeoffwork", P, "Work as a barrier to care"),
    ]),
    "marital": dict(label="Marital / partner status", fields=[
        ("survey/basics/maritalstatus_currentmaritalstatus", D, ""),
        ("survey/cope/basics_8", D, "COPE repeat (2020–21)"),
    ]),
    "household": dict(label="Household composition / living alone", fields=[
        ("survey/basics/livingsituation_howmanypeople", D, "0 others in household = living alone"),
        ("survey/basics/livingsituation_peopleunder18", D, "Children in household"),
        ("ehr/observation/isolation_z", D, "Z60.2 problems related to living alone"),
    ]),
    "caregiving": dict(label="Caregiving / childcare responsibilities", fields=[
        ("survey/hcau/delayedmedicalcare_childcare", D, ""),
        ("survey/hcau/delayedmedicalcare_elderlycare", D, ""),
        ("survey/basics/livingsituation_peopleunder18", P, ""),
    ]),
    "birthplace": dict(label="Country of birth / immigration", fields=[
        ("survey/basics/thebasics_birthplace", D, "USA vs other"),
        ("survey/sdoh/chis_1", P, "Non-English language at home"),
    ]),
    "language": dict(label="Language / English proficiency", fields=[
        ("survey/sdoh/chis_1", D, ""),
        ("survey/sdoh/chis_1_xx", D, "Self-rated English proficiency"),
    ]),
    "veteran": dict(label="Military service", fields=[
        ("survey/basics/activeduty_activedutyservestatus", D, "Suppressed in Registered Tier"),
    ]),
    "pregnancy": dict(label="Pregnancy", fields=[
        ("survey/overall_health/pregnancy_1pregnancystatus", D, "Current pregnancy at enrollment"),
        ("survey/cope/overallhealth_14b", D, "COPE repeat"),
        ("survey/cope/cope_aou_xx_1", P, "Receiving prenatal care"),
        ("ehr/condition_occurrence/pregnancy_dx", D, ""),
    ]),
    "disability": dict(label="Functional limitation / disability", fields=[
        ("survey/basics/disability_*", D, "ACS six-question disability set"),
        ("survey/overall_health/overallhealth_everydayactivities", D, ""),
    ]),
    "religion": dict(label="Religiosity / spirituality", fields=[
        ("survey/sdoh/bmmrs_*", D, "Brief Multidimensional Measure of Religiousness/Spirituality"),
        ("survey/sdoh/nhs_xx", D, "Religious service attendance"),
    ]),
    "msm_proxy": dict(label="Sexual minority men (MSM proxy)", fields=[
        ("survey/basics/thebasics_sexualorientation", P, "Gay/bisexual identity; AoU does not ask about sexual behavior with partners"),
        ("survey/basics/biologicalsexatbirth_sexatbirth", P, "Combine with orientation"),
        ("survey/basics/gender_genderidentity", P, ""),
    ]),
    "traditional_healer": dict(label="Traditional / alternative medicine use", fields=[
        ("survey/hcau/healthadvice_spokentotraditionalhealer", D, "Saw a traditional healer (shaman, acupuncturist, non-western medicine)"),
        ("survey/hcau/healthadvice_traditionalhealervisits", D, "Visits in past 12 months"),
        ("survey/hcau/cantaffordcare_alternativetherapies", P, "Used alternative therapies to save money"),
    ]),
    # ---- Social / environmental ---------------------------------------------------------
    "housing": dict(label="Housing instability / homelessness", fields=[
        ("survey/basics/livingsituation_stablehouseconcern", D, "Worried about not having a place to live (past 6 months)"),
        ("survey/sdoh/urs_8c", D, "Number of moves in last 12 months"),
        ("survey/basics/livingsituation_currentliving", D, "Includes shelter / homeless options; suppressed in Registered Tier"),
        ("survey/basics/homeown_currenthomeown", P, "Own vs rent vs other arrangement"),
        ("survey/basics/livingsituation_howmanylivingyears", P, "Years at current address"),
        ("ehr/observation/homeless_z", D, ""),
        ("survey/sdoh/ahc_2", P, "Housing quality problems (mold, pests, heat)"),
    ]),
    "food_insecurity": dict(label="Food insecurity", fields=[
        ("survey/sdoh/hvs_1", D, "Hunger Vital Sign item 1"),
        ("survey/sdoh/hvs_2", D, "Hunger Vital Sign item 2"),
        ("ehr/observation/food_z", D, ""),
        ("ds/ds_zip_code_socioeconomic/fraction_assisted_income", P, "Area-level SNAP / public assistance"),
    ]),
    "transportation": dict(label="Transportation barriers", fields=[
        ("survey/hcau/delayedmedicalcare_transportation", D, "Delayed care: didn't have transportation"),
        ("survey/sdoh/ips_3", P, "Transit stop within 10–15 min walk"),
        ("survey/sdoh/sdoh_mos_ss_2", P, "Someone to take you to the doctor"),
        ("ehr/observation/transport_z", D, ""),
    ]),
    "rurality": dict(label="Rural residence / geography", fields=[
        ("survey/hcau/delayedmedicalcare_ruralarea", P, "Delayed care because rural area is too far from provider"),
        ("ds/ds_zip_code_socioeconomic/zip3_as_string", P, "3-digit ZIP only; too coarse for RUCA-based rurality"),
        ("survey/sdoh/ips_1", P, "Main housing type in neighborhood"),
    ]),
    "insurance": dict(label="Health insurance", fields=[
        ("survey/basics/insurance_healthinsurance", D, "Any coverage"),
        ("survey/basics/healthinsurance_insurancetypeupdate", D, "Coverage type (Medicaid, Medicare, private, etc.)"),
        ("survey/hcau/insurance_insuranceaccepted", P, "Provider did not accept insurance"),
        ("survey/hcau/insurance_healthcarecoverage", P, "Coverage vs a year ago"),
        ("survey/cope/basics_11", D, "COPE repeat"),
        ("ds/ds_zip_code_socioeconomic/fraction_no_health_ins", P, "Area-level uninsured rate"),
    ]),
    "healthcare_access": dict(label="Health care access / usual source of care", fields=[
        ("survey/hcau/healthadvice_placeforhealthadvice", D, "Usual place of care"),
        ("survey/hcau/healthadvice_whatkindofplace", D, ""),
        ("survey/hcau/healthadvice_spokentoprofessional", D, "Time since last provider contact"),
        ("survey/hcau/delayedmedicalcare_*", D, "Reasons for delayed care"),
        ("survey/hcau/cantaffordcare_healthcareprovider", D, ""),
        ("survey/hcau/cantaffordcare_followupcare", D, ""),
        ("survey/hcau/healthadvice_generaldoctorvisits", P, "Visit counts, past 12 months"),
        ("survey/hcau/healthadvice_medicalspecialistvisits", P, "Specialist (e.g. HIV) visit counts"),
    ]),
    "provider_relationship": dict(label="Patient–provider relationship / communication", fields=[
        ("survey/hcau/healthadvice_respectedbyprovider", D, ""),
        ("survey/hcau/healthadvice_askedforopinion", D, ""),
        ("survey/hcau/healthadvice_easeofunderstanding", D, ""),
        ("survey/hcau/healthproviderracereligion_*", P, "Provider concordance and care avoidance"),
        ("survey/sdoh/sdoh_dms_*", P, "Discrimination in medical settings"),
    ]),
    "incarceration": dict(label="Incarceration", fields=[
        ("ehr/observation/incarceration_z", D, "Only clinician-coded history; no survey item"),
    ]),
    "violence": dict(label="Violence / abuse exposure", fields=[
        ("ehr/observation/violence_z", D, "Partly row-suppressed in Registered Tier"),
        ("survey/sdoh/sdoh_eds_9", P, "Threatened or harassed (Everyday Discrimination item)"),
        ("survey/cope/cdc_covid_19_26", P, "Increased household interpersonal conflict / violence, 2020–21"),
        ("survey/sdoh/nds_8", P, "Neighborhood crime"),
    ]),
    "social_support": dict(label="Social support", fields=[
        ("survey/sdoh/sdoh_mos_ss_*", D, "MOS Social Support Survey (8 items)"),
        ("survey/cope/mos_ss_*", D, "COPE MOS-SS (2020–21)"),
        ("survey/overall_health/overallhealth_socialsatisfaction", P, ""),
    ]),
    "loneliness": dict(label="Loneliness / social isolation", fields=[
        ("survey/sdoh/sdoh_ucla_ls8_*", D, "UCLA Loneliness Scale (ULS-8)"),
        ("survey/cope/ucla_ls8_*", D, "COPE ULS-8 (2020–21)"),
        ("survey/basics/livingsituation_howmanypeople", P, "Living alone"),
        ("ehr/observation/isolation_z", D, ""),
    ]),
    "social_cohesion": dict(label="Neighborhood social cohesion / social capital", fields=[
        ("survey/sdoh/scns_*", D, "Social Cohesion and Neighborhood Support scale"),
        ("survey/sdoh/nds_12", D, "People watch out for each other"),
    ]),
    "discrimination": dict(label="Discrimination", fields=[
        ("survey/sdoh/sdoh_eds_*", D, "Everyday Discrimination Scale + attributed reason"),
        ("survey/sdoh/sdoh_dms_*", D, "Discrimination in Medical Settings scale"),
        ("survey/cope/eds_*", D, "COPE EDS (2020–21)"),
        ("ehr/observation/discrimination_z", D, ""),
    ]),
    "stress": dict(label="Perceived stress", fields=[
        ("survey/sdoh/sdoh_cpss_*", D, "Cohen Perceived Stress Scale (PSS-10)"),
        ("survey/cope/cpss_*", D, "COPE PSS (2020–21)"),
    ]),
    # ---- Substance use ------------------------------------------------------------------
    "alcohol": dict(label="Alcohol use", fields=[
        ("survey/lifestyle/alcohol_alcoholparticipant", D, "Lifetime use"),
        ("survey/lifestyle/alcohol_drinkfrequencypastyear", D, "AUDIT-C item 1"),
        ("survey/lifestyle/alcohol_averagedailydrinkcount", D, "AUDIT-C item 2"),
        ("survey/lifestyle/alcohol_6ormoredrinksoccurence", D, "AUDIT-C item 3 (heavy episodic drinking)"),
        ("survey/cope/audit_c_*", D, "COPE AUDIT-C (2020–21)"),
        ("survey/pfhh/mentalcondition_alcoholuse_yes", D, "Self-reported alcohol use disorder ('Self')"),
        ("ehr/condition_occurrence/aud_dx", D, ""),
    ]),
    "binge": dict(label="Heavy episodic (binge) drinking", fields=[
        ("survey/lifestyle/alcohol_6ormoredrinksoccurence", D, "Six or more drinks on one occasion"),
        ("survey/cope/audit_c_3", D, ""),
    ]),
    "tobacco": dict(label="Tobacco / nicotine use", fields=[
        ("survey/lifestyle/smoking_*", D, "Cigarette smoking history, frequency, quantity"),
        ("survey/lifestyle/attemptquitsmoking_*", D, ""),
        ("survey/lifestyle/electronicsmoking_*", D, "E-cigarettes"),
        ("survey/lifestyle/cigarsmoking_*", D, ""),
        ("survey/lifestyle/hookahsmoking_*", D, ""),
        ("survey/lifestyle/smokelesstobacco_*", D, ""),
        ("survey/cope/lifestyle_2_xx12", D, "COPE current smoking"),
        ("ehr/condition_occurrence/nicotine_dx", D, ""),
    ]),
    "drug_use": dict(label="Drug use (any illicit / non-medical)", fields=[
        ("survey/lifestyle/recreationaldruguse_whichdrugsused", D, "Lifetime use by substance"),
        ("survey/lifestyle/past3monthusefrequency_*", D, "ASSIST-style past-3-month frequency by substance"),
        ("survey/cope/tsu_ds5_13_*", D, "COPE past-month drug use (2020–21)"),
        ("survey/pfhh/mentalcondition_druguse_yes", D, "Self-reported drug use disorder ('Self')"),
        ("ehr/condition_occurrence/sud_dx", D, ""),
    ]),
    "cocaine": dict(label="Cocaine / crack use", fields=[
        ("survey/lifestyle/past3monthusefrequency_cocaine3monthuse", D, ""),
        ("survey/lifestyle/recreationaldruguse_whichdrugsused", D, "'Cocaine (coke, crack, etc.)' option"),
        ("ehr/condition_occurrence/stimulant_dx", D, "F14 cocaine-related disorders"),
    ]),
    "stimulant": dict(label="Methamphetamine / other stimulant use", fields=[
        ("survey/lifestyle/past3monthusefrequency_otherstimulant3monthuse", D, "Methamphetamine, speed, crystal meth"),
        ("survey/lifestyle/past3monthusefrequency_prescriptionstimulant3monthuse", D, "Non-medical prescription stimulants"),
        ("ehr/condition_occurrence/stimulant_dx", D, ""),
    ]),
    "opioid": dict(label="Opioid / heroin use", fields=[
        ("survey/lifestyle/past3monthusefrequency_streetopioid3monthuse", D, "Heroin, opium"),
        ("survey/lifestyle/past3monthusefrequency_prescriptionopiod3monthuse", D, "Non-medical prescription opioids"),
        ("ehr/condition_occurrence/opioid_dx", D, ""),
    ]),
    "cannabis": dict(label="Cannabis use", fields=[
        ("survey/lifestyle/past3monthusefrequency_marijuana3monthuse", D, ""),
        ("survey/lifestyle/recreationaldruguse_whichdrugsused", D, "'Marijuana' option"),
    ]),
    "injection": dict(label="Injection drug use", fields=[
        ("survey/lifestyle/past3monthusefrequency_streetopioid3monthuse", P, "AoU does not ask about route of administration"),
        ("survey/lifestyle/past3monthusefrequency_otherstimulant3monthuse", P, ""),
        ("ehr/condition_occurrence/sud_dx", P, "Opioid / stimulant use disorders; injection route rarely coded"),
        ("ehr/condition_occurrence/hcv", P, "HCV infection is a common correlate of injection"),
    ]),
    "sud_treatment": dict(label="Substance use treatment", fields=[
        ("ehr/drug_exposure/moud", D, ""),
        ("ehr/procedure_occurrence/sud_services", D, ""),
    ]),
    "sexual_risk": dict(label="Sexual risk behavior", fields=[
        ("survey/pfhh/infectiousdiseases_infectiousdiseasecondition", P, "'Sexually transmitted infections' option; AoU does not ask about condom use or partners"),
        ("ehr/condition_occurrence/sti", P, "STI diagnoses as a marker of sexual risk"),
    ]),
    # ---- Psychosocial -------------------------------------------------------------------
    "depression": dict(label="Depression", fields=[
        ("survey/cope/phq_9_*", D, "PHQ-9 (COPE, 2020–21)"),
        ("survey/pfhh/mentalcondition_depression_yes", D, "Self-reported diagnosis ('Self')"),
        ("ehr/condition_occurrence/depression_dx", D, ""),
        ("survey/overall_health/overallhealth_emotionalproblem7days", P, "Bothered by emotional problems (anxious, depressed, irritable)"),
        ("ehr/drug_exposure/psychotropics", P, "Antidepressant prescriptions"),
    ]),
    "anxiety": dict(label="Anxiety", fields=[
        ("survey/cope/gad_7_*", D, "GAD-7 (COPE, 2020–21)"),
        ("survey/pfhh/mentalcondition_anxietypanic_yes", D, "Self-reported anxiety/panic disorder ('Self')"),
        ("ehr/condition_occurrence/anxiety_dx", D, ""),
        ("survey/overall_health/overallhealth_emotionalproblem7days", P, ""),
    ]),
    "ptsd": dict(label="PTSD / trauma", fields=[
        ("survey/pfhh/mentalcondition_ptsd_yes", D, "Self-reported PTSD ('Self')"),
        ("ehr/condition_occurrence/ptsd_dx", D, ""),
        ("ehr/observation/trauma_hx_z", D, ""),
        ("survey/cope/ies_r_6_*", P, "Impact of Event Scale items, COVID-specific"),
    ]),
    "smi": dict(label="Serious mental illness", fields=[
        ("survey/pfhh/mentalcondition_bipolar_yes", D, ""),
        ("survey/pfhh/mentalcondition_schizophrenia_yes", D, ""),
        ("survey/pfhh/mentalcondition_personalitydisorder_yes", P, ""),
        ("ehr/condition_occurrence/smi_dx", D, ""),
    ]),
    "mental_health_general": dict(label="General mental health / psychological distress", fields=[
        ("survey/overall_health/overallhealth_generalmentalhealth", D, "PROMIS Global mental health item"),
        ("survey/overall_health/overallhealth_emotionalproblem7days", D, ""),
        ("survey/cope/phq_9_*", P, ""),
        ("survey/cope/gad_7_*", P, ""),
        ("survey/sdoh/sdoh_cpss_*", P, "Perceived stress"),
        ("survey/pfhh/diagnosedhealthcondition_mentalcondition", D, "Any self-reported mental health condition"),
    ]),
    "suicidality": dict(label="Suicidal ideation", fields=[
        ("survey/cope/phq_9_9", D, "PHQ-9 item 9"),
        ("ehr/condition_occurrence/suicide_dx", D, ""),
    ]),
    "mh_treatment": dict(label="Mental health treatment", fields=[
        ("survey/hcau/healthadvice_spokentomentalhealthprofessional", D, ""),
        ("survey/hcau/healthadvice_mentalhealthprofessionalvisits", D, ""),
        ("survey/hcau/cantaffordcare_mentalhealthcounseling", D, "Could not afford counseling"),
        ("ehr/procedure_occurrence/mh_services", D, ""),
        ("ehr/drug_exposure/psychotropics", D, ""),
    ]),
    "resilience": dict(label="Resilience / coping", fields=[
        ("survey/cope/brcs_*", D, "Brief Resilient Coping Scale (COPE)"),
        ("survey/sdoh/sdoh_cpss_4", P, "Confident handling personal problems"),
        ("survey/cope/cdc_covid_19_25", P, "Coping activities during isolation (2020–21)"),
    ]),
    "optimism": dict(label="Optimism / hope / life meaning", fields=[
        ("survey/cope/lot_r_1", D, "LOT-R optimism item"),
        ("survey/cope/ukmh_j1", P, "Happiness"),
        ("survey/cope/ukmh_j3", P, "Life meaning"),
        ("survey/cope/phq_9_2", P, "'Feeling down, depressed, or hopeless'"),
    ]),
    "self_efficacy": dict(label="Self-efficacy / sense of control", fields=[
        ("survey/sdoh/sdoh_cpss_2", P, "Unable to control important things"),
        ("survey/sdoh/sdoh_cpss_4", P, "Confident about handling personal problems"),
        ("survey/sdoh/sdoh_cpss_5", P, ""),
        ("survey/overall_health/overallhealth_medicalformconfidence", P, "Confidence with medical forms"),
    ]),
    "health_literacy": dict(label="Health literacy", fields=[
        ("survey/overall_health/overallhealth_medicalformconfidence", D, "Brief Health Literacy Screen item"),
        ("survey/overall_health/overallhealth_healthmaterialassistance", D, "BHLS item"),
        ("survey/overall_health/overallhealth_difficultunderstandinfo", D, "BHLS item"),
        ("survey/hcau/healthadvice_easeofunderstanding", P, ""),
    ]),
    "cognition": dict(label="Cognitive function", fields=[
        ("survey/basics/disability_difficultyconcentrating", D, "Serious difficulty concentrating/remembering"),
        ("survey/pfhh/nervouscondition_memoryloss_yes", D, ""),
        ("survey/pfhh/nervouscondition_dementia_yes", D, ""),
        ("ehr/condition_occurrence/cognitive_dx", D, ""),
        ("emt/flanker_task/*", P, "Executive function / inhibitory control task"),
        ("emt/gradcpt_task/*", P, "Sustained attention task"),
    ]),
    "impulsivity": dict(label="Impulsivity / time preference", fields=[
        ("emt/delaydiscounting_task/*", D, "Delay discounting (k parameter)"),
        ("emt/gradcpt_task/nogo_accuracy", P, "Commission errors"),
    ]),
    "quality_of_life": dict(label="Quality of life / self-rated health", fields=[
        ("survey/overall_health/overallhealth_generalquality", D, "PROMIS Global quality-of-life item"),
        ("survey/overall_health/overallhealth_generalhealth", D, "Self-rated health"),
        ("survey/overall_health/overallhealth_generalphysicalhealth", D, ""),
        ("survey/overall_health/overallhealth_generalmentalhealth", D, ""),
        ("survey/overall_health/overallhealth_generalsocial", D, ""),
        ("survey/overall_health/overallhealth_averagepain7days", P, ""),
        ("survey/overall_health/overallhealth_averagefatigue7days", P, ""),
    ]),
    "sleep": dict(label="Sleep", fields=[
        ("wear/fitbit/sleep_daily_summary/minute_asleep", D, "Fitbit subset only"),
        ("wear/fitbit/sleep_daily_summary_ext/sleep_efficiency", D, ""),
        ("survey/pfhh/nervouscondition_insomnia_yes", D, ""),
        ("survey/cope/phq_9_3", D, "Trouble sleeping (PHQ-9 item 3)"),
        ("ehr/condition_occurrence/sleep_dx", D, ""),
    ]),
    "physical_activity": dict(label="Physical activity", fields=[
        ("wear/fitbit/activity_measurements/steps", D, "Fitbit subset only"),
        ("wear/fitbit/activity_measurements/very_active_minutes", D, ""),
        ("wear/fitbit/activity_measurements/sedentary_minutes", D, ""),
        ("survey/cope/ipaq_*", D, "IPAQ short form (COPE)"),
    ]),
    "pain_fatigue": dict(label="Pain / fatigue", fields=[
        ("survey/overall_health/overallhealth_averagepain7days", D, ""),
        ("survey/overall_health/overallhealth_averagefatigue7days", D, ""),
        ("survey/cope/phq_9_4", P, "Tired / little energy"),
        ("survey/pfhh/nervouscondition_chronicfatigue_yes", D, ""),
    ]),
    # ---- Biological / clinical ----------------------------------------------------------
    "hiv_dx": dict(label="HIV diagnosis / HIV cohort definition", fields=[
        ("ehr/condition_occurrence/hiv", D, "Core HIV phenotype"),
        ("survey/pfhh/infectiousdiseases_infectiousdiseasecondition", D, "'HIV/AIDS' option (self-report)"),
        ("survey/pfhh/infectiousdiseases_howoldwereyouhivaids", D, "Age at diagnosis (banded)"),
        ("survey/pfhh/infectiousdiseases_hivaidscurrently", D, "Currently seeing a provider for HIV"),
        ("survey/pfhh/infectiousdiseases_rxmedsforhivaids", D, "Currently on HIV medication"),
        ("ehr/measurement/hiv_test", D, "First positive test date"),
        ("ehr/drug_exposure/art", P, "ART exposure (excluding PrEP-only regimens) supports the phenotype"),
    ]),
    "viral_load": dict(label="HIV viral load", fields=[
        ("ehr/measurement/vl", D, "Threshold value_as_number (e.g. <50 or <200 copies/mL suppressed; ≥200 or ≥1000 failure)"),
        ("omop/measurement/value_as_number", D, "Numeric result"),
        ("omop/measurement/operator_concept_id", D, "Captures '<' (below detection) results"),
        ("omop/measurement/measurement_date", D, "Sequencing for rebound / timing relative to ART start"),
        ("ehr/drug_exposure/art", P, "Time on ART needed for failure definitions"),
    ]),
    "cd4": dict(label="CD4 count", fields=[
        ("ehr/measurement/cd4", D, "Threshold value_as_number (e.g. <200 cells/µL)"),
        ("omop/measurement/value_as_number", D, ""),
        ("omop/measurement/measurement_date", D, "Trajectory: recovery / decline"),
    ]),
    "cd4cd8": dict(label="CD4/CD8 ratio", fields=[("ehr/measurement/cd4cd8", D, "")]),
    "resistance": dict(label="HIV drug resistance", fields=[
        ("ehr/measurement/hiv_geno", P, "Test ordered/performed; mutation-level results generally unavailable"),
        ("ehr/drug_exposure/art", P, "Switch to salvage regimens implies resistance"),
    ]),
    "advanced_hiv": dict(label="Advanced HIV / AIDS stage", fields=[
        ("ehr/measurement/cd4", D, "CD4 <200 cells/µL defines advanced disease"),
        ("ehr/condition_occurrence/aids_oi", D, "AIDS-defining illness"),
        ("ehr/condition_occurrence/hiv", P, "B20 vs Z21 roughly separates symptomatic from asymptomatic"),
    ]),
    "oi": dict(label="Opportunistic infections", fields=[
        ("ehr/condition_occurrence/aids_oi", D, ""),
        ("ehr/drug_exposure/oi_prophylaxis", P, ""),
    ]),
    "tb": dict(label="Tuberculosis", fields=[
        ("ehr/condition_occurrence/tb", D, ""),
        ("survey/pfhh/infectiousdiseases_infectiousdiseasecondition", D, "'Tuberculosis' option"),
        ("survey/pfhh/infectiousdiseases_tuberculosiscurrently", D, ""),
        ("ehr/drug_exposure/tb_drugs", D, ""),
    ]),
    "hbv": dict(label="Hepatitis B", fields=[
        ("ehr/condition_occurrence/hbv", D, ""),
        ("survey/pfhh/infectiousdiseases_infectiousdiseasecondition", D, "'Hepatitis B' option"),
        ("ehr/measurement/hep_labs", D, ""),
    ]),
    "hcv": dict(label="Hepatitis C", fields=[
        ("ehr/condition_occurrence/hcv", D, ""),
        ("survey/pfhh/infectiousdiseases_infectiousdiseasecondition", D, "'Hepatitis C' option"),
        ("ehr/measurement/hep_labs", D, ""),
    ]),
    "sti": dict(label="Sexually transmitted infections", fields=[
        ("ehr/condition_occurrence/sti", D, ""),
        ("survey/pfhh/infectiousdiseases_infectiousdiseasecondition", D, "'Sexually transmitted infections' option"),
    ]),
    "body_size": dict(label="Weight / BMI", fields=[
        ("ehr/measurement/weight_bmi", D, "Serial weights for gain/loss; BMI thresholds"),
        ("wear/healthkit/physical_measurements/value", P, "Self-tracked, HealthKit subset only"),
        ("ehr/condition_occurrence/obesity_dx", D, ""),
        ("survey/pfhh/otherhealthcondition_obesity_yes", D, ""),
    ]),
    "malnutrition": dict(label="Malnutrition / wasting", fields=[
        ("ehr/condition_occurrence/malnutrition_dx", D, ""),
        ("ehr/measurement/weight_bmi", P, "BMI <18.5 or weight loss"),
    ]),
    "anemia": dict(label="Anemia", fields=[
        ("ehr/measurement/hemoglobin", D, ""),
        ("ehr/condition_occurrence/anemia_dx", D, ""),
    ]),
    "kidney": dict(label="Kidney function / disease", fields=[
        ("ehr/measurement/renal_labs", D, ""),
        ("ehr/condition_occurrence/kidney_dx", D, ""),
        ("survey/pfhh/kidneycondition_*", D, ""),
    ]),
    "liver": dict(label="Liver disease / hepatotoxicity", fields=[
        ("ehr/measurement/liver_labs", D, ""),
        ("ehr/condition_occurrence/liver_dx", D, ""),
        ("survey/pfhh/diagnosedhealthcondition_livercondition_yes", D, ""),
    ]),
    "cardiometabolic": dict(label="Cardiometabolic comorbidity", fields=[
        ("ehr/condition_occurrence/diabetes_dx", D, ""),
        ("ehr/condition_occurrence/htn_dx", D, ""),
        ("ehr/condition_occurrence/cvd_dx", D, ""),
        ("ehr/measurement/glycemic_labs", D, ""),
        ("ehr/measurement/lipid_labs", D, ""),
        ("survey/pfhh/circulatorycondition_*", D, ""),
        ("survey/pfhh/endocrinecondition_type2diabetes_yes", D, ""),
    ]),
    "cancer": dict(label="Cancer", fields=[
        ("ehr/condition_occurrence/cancer_dx", D, ""),
        ("survey/pfhh/diagnosedhealthcondition_cancercondition", D, ""),
    ]),
    "other_clinical": dict(label="Other clinical diagnosis / lab", fields=[
        ("ehr/condition_occurrence/other_condition", D, "Condition named by the entity"),
        ("ehr/measurement/other_lab", D, "Lab named by the entity"),
    ]),
    "polypharmacy_var": dict(label="Polypharmacy / drug interactions", fields=[
        ("ehr/drug_exposure/polypharmacy", D, "Overlapping exposure windows of ARV and non-ARV ingredients"),
    ]),
    "other_drug_var": dict(label="Other specific medication", fields=[
        ("ehr/drug_exposure/other_drug", D, "Drug named by the entity"),
    ]),
    "comorbidity": dict(label="Comorbidity burden", fields=[
        ("omop/condition_occurrence/condition_concept_id", D, "Compute Charlson / Elixhauser indices from diagnosis codes"),
        ("ehr/drug_exposure/polypharmacy", P, ""),
    ]),
    # ---- Treatment ----------------------------------------------------------------------
    "art_exposure": dict(label="ART exposure / regimen", fields=[
        ("ehr/drug_exposure/art", D, ""),
        ("omop/drug_exposure/drug_exposure_start_date", D, ""),
        ("omop/drug_exposure/drug_exposure_end_date", D, ""),
        ("survey/pfhh/infectiousdiseases_rxmedsforhivaids", D, "Self-reported current HIV medication"),
    ]),
    "art_nnrti": dict(label="NNRTI-based regimens", fields=[("ehr/drug_exposure/art_nnrti", D, "")]),
    "art_pi": dict(label="PI-based regimens", fields=[("ehr/drug_exposure/art_pi", D, "")]),
    "art_insti": dict(label="INSTI-based regimens", fields=[("ehr/drug_exposure/art_insti", D, "")]),
    "art_nrti": dict(label="NRTI backbone", fields=[("ehr/drug_exposure/art_nrti", D, "")]),
    "art_str": dict(label="Single-tablet regimen", fields=[("ehr/drug_exposure/art_str", D, "")]),
    "art_lai": dict(label="Long-acting injectable ART", fields=[("ehr/drug_exposure/art_lai", D, "")]),
    "art_timing": dict(label="ART initiation timing", fields=[
        ("ehr/drug_exposure/art", P, "First ARV date in EHR; may be left-censored if ART began before EHR coverage"),
        ("ehr/condition_occurrence/hiv", P, "First HIV diagnosis date"),
        ("ehr/measurement/cd4", P, "CD4 at ART start (CD4-guided 'late' initiation)"),
        ("omop/observation_period/observation_period_start_date", P, "Start of observable EHR history"),
    ]),
    "regimen_change": dict(label="Regimen switch / discontinuation", fields=[
        ("ehr/drug_exposure/art", D, "Change in ARV ingredient set over time"),
        ("omop/drug_exposure/stop_reason", P, "Sparsely populated"),
    ]),
    "pill_burden": dict(label="Pill burden / dosing frequency", fields=[
        ("ehr/drug_exposure/art_str", P, ""),
        ("omop/drug_exposure/quantity", P, ""),
        ("omop/drug_exposure/sig", P, "Free-text directions; often null after cleaning"),
        ("ehr/drug_exposure/polypharmacy", P, ""),
    ]),
    "side_effects": dict(label="ART side effects / toxicity", fields=[
        ("ehr/condition_occurrence/art_adverse", D, ""),
        ("ehr/measurement/liver_labs", P, ""),
        ("ehr/measurement/renal_labs", P, ""),
    ]),
    "tb_treatment": dict(label="TB treatment / preventive therapy", fields=[("ehr/drug_exposure/tb_drugs", D, "")]),
    "oi_prophylaxis": dict(label="OI prophylaxis", fields=[("ehr/drug_exposure/oi_prophylaxis", D, "")]),
    "treatment_duration": dict(label="Time on ART", fields=[
        ("ehr/drug_exposure/art", P, "Cumulative ARV exposure days; left-censored before EHR coverage"),
        ("omop/drug_exposure/days_supply", P, ""),
    ]),
    # ---- Adherence / engagement ---------------------------------------------------------
    "adherence": dict(label="Medication adherence", fields=[
        ("omop/drug_exposure/days_supply", P, "Refill-based proportion of days covered (PDC); depends on pharmacy-fill capture"),
        ("omop/drug_exposure/refills", P, ""),
        ("ehr/drug_exposure/art", P, "ARV dispensing gaps"),
        ("ehr/observation/noncompliance", D, "Clinician-documented nonadherence (under-coded)"),
        ("ehr/condition_occurrence/art_underdosing", D, ""),
        ("survey/hcau/cantaffordcare_skippedmedtosavemoney", D, "Cost-related nonadherence"),
        ("survey/hcau/cantaffordcare_tooklessmedtosavemoney", D, "Cost-related nonadherence"),
        ("survey/hcau/cantaffordcare_delayedfillingrxtosavemoney", D, "Cost-related nonadherence"),
    ]),
    "cost_nonadherence": dict(label="Cost-related nonadherence", fields=[
        ("survey/hcau/cantaffordcare_skippedmedtosavemoney", D, ""),
        ("survey/hcau/cantaffordcare_tooklessmedtosavemoney", D, ""),
        ("survey/hcau/cantaffordcare_delayedfillingrxtosavemoney", D, ""),
        ("survey/hcau/cantaffordcare_prescriptionmedicines", D, ""),
    ]),
    "retention": dict(label="Retention / engagement in care", fields=[
        ("ehr/visit_occurrence/outpatient", P, "HRSA-style retention from visit dates; misses care outside AoU partner sites"),
        ("omop/visit_occurrence/visit_start_date", P, ""),
        ("ehr/measurement/vl", P, "Lab dates as evidence of care (CDC 'in care' definition)"),
        ("ehr/measurement/cd4", P, ""),
        ("omop/observation_period/observation_period_end_date", P, "End of observable EHR record (loss to follow-up proxy)"),
        ("survey/hcau/healthadvice_spokentoprofessional", P, "Time since last provider contact (self-report)"),
    ]),
    "linkage": dict(label="Linkage to care / diagnosis timing", fields=[
        ("ehr/condition_occurrence/hiv", P, "First HIV code date"),
        ("ehr/measurement/hiv_test", P, "First positive test date"),
        ("ehr/visit_occurrence/outpatient", P, "First HIV-related visit"),
        ("ehr/measurement/cd4", P, "CD4 at diagnosis (late presentation if <350 or <200)"),
    ]),
    "hiv_testing": dict(label="HIV testing", fields=[("ehr/measurement/hiv_test", D, "")]),
    # ---- Outcomes -----------------------------------------------------------------------
    "mortality": dict(label="Death", fields=[
        ("omop/death/death_date", D, "Date-shifted"),
        ("omop/aou_death/death_date", D, "Includes non-EHR death sources"),
        ("omop/death/cause_concept_id", D, "Cause of death suppressed in Registered Tier"),
    ]),
    "hospitalization": dict(label="Hospitalization / ED use", fields=[
        ("ehr/visit_occurrence/inpatient", D, ""),
        ("omop/visit_occurrence/visit_concept_id", D, ""),
        ("omop/visit_occurrence/visit_start_date", D, ""),
    ]),
    "covid": dict(label="COVID-19 experience", fields=[
        ("survey/cope/*", P, "COPE survey module"),
    ]),
}

# Entities matching a gap rule get no field mapping; the reason is shown instead. Checked first.
# (pattern, reason) - optional third element: regex that cancels the gap ("unless").
GAP_RULES = [
    (r"\binfants?\b|\bchild\b|\bchild's\b|\bchildren\b|childhood|paediatric|pediatric|caregiver|weight[- ]for[- ]age|height[- ]for[- ]age|weight[- ]for[- ]height|z[- ]score|orphan|stunting|short stature|impaired growth|perinatal(ly)? (hiv|acquired|transmission|antiretroviral)|perinatally|congenital|vertical transmission|mother-to-child|pmtct|\bschool\b|adolescent club|adolescent-friendly|youth-targeted|teacher|transition to adult|medical transition|successful transition|age at transition|\bpaediatric|externali[sz]ing|behaviou?ral (problems|difficulties)|parent-child|child-caregiver",
     "All of Us enrolls adults (18+); constructs about infants, children, their caregivers or perinatal transmission have no participant-level field.",
     r"having children|number of children|being primary caregiver|childcare|child care|childhood (abuse|adversity|trauma|sexual abuse)|child sexual abuse|having at least two children"),
    (r"\b(partner|partner's|partners'|husband|husbands'|husband's|spouse's|wife's|parental|parents'|parent's|maternal|mother's|father's|family member|household member|network|caregiver)\b.{0,25}\b(use|using|drinking|alcohol|drug|smoking|viral load|cd4|hiv status|serostatus|depression|education|age)\b|death of (a|the|her|his|mother|father|parent)|parental death|unemployed family|knowing spouse",
     "Describes another person (partner, parent, family, network); All of Us records data about the participant only."),
    (r"disclos", "All of Us has no item on HIV status disclosure."),
    (r"concentration|plasma levels?|trough|hair (level|concentration)|\bin hair\b|hair levels?|drug levels?|pharmacokinetic|\bauc\b|therapeutic drug|subtherapeutic|tenofovir diphosphate|dried blood spot|peak plasma",
     "Antiretroviral drug levels are not routinely measured or stored as structured EHR results."),
    (r"cyp2b6|cyp3a|cyp2|\bhla\b|hla-b|ccr5|pharmacogen|polymorphism|ugt1a1|abcb1|slco|nr1i|host genet|slow.metaboli|metabolizer|apol1|single nucleotide",
     "Host genotype data (srWGS / arrays) are available only in the Controlled Tier."),
    (r"subtype|\bcrf\d|crf\d|clade|tropism|tropic|quasispecies|reservoir|hiv dna|cell-associated|proviral|integrated dna|genetic diversity|hiv diversity|phylogen|minority variant|low-frequency|minority (drug|mutation|y181|k103|nnrti)|ultra-?deep|next-generation sequencing|replication capacity|viral fitness|genital hiv|shedding|csf viral|cerebrospinal",
     "Viral subtype, tropism, reservoir, minority-variant and compartment assays are research measures not captured in EHR data."),
    (r"interleukin|\bil-?\d|\btnf|soluble cd|\bscd\d|monocyte activation|immune activation|t-cell activation|cd8 t-cell activation|apoptosis|exhaustion|inflamma(tion|tory) ?(bio)?markers?|^inflammation$|arterial inflammation|chemokine|ccl\d|cxcl|mcp-1|kynurenine|microbial translocation|\blps\b|i-fabp|cd38|hla-dr|senescence|telomere|neopterin|cytokine|regulatory t|\btreg|th17|nk cell|b-cell|cd8 t-cell function|anti-hiv antibody|cd8 activation|soluble pd-l1|systemic inflammation|residual viral replication|insertion",
     "Research immunology / inflammation biomarkers are not part of routine clinical care, so they rarely appear in EHR measurements."),
    (r"polic(y|ies)|criminali[sz]ation|\blaws?\b|legislat|\bcountry\b|\bnational\b(?!ity)|government|health system|stock-?outs?|supply chain|drug shortage|facility (type|level|ownership)|clinic (type|size|level|location)|health facility type|staff turnover|staffing|task.shifting|patient volume|physician (hiv )?experience|differentiated service|community-based (art )?delivery|decentrali|down-referral|private sector|public sector|program(me)? (implementation|scale-up|coverage)|coverage expansion|tb burden|hiv prevalence|community (hiv )?prevalence|\bsetting\b|turnaround time|point-of-care|clinic (hours|location)|rural clinic|urban health facility|pharmacy delivery|home delivery|delivery service|integrated (maternal|services|care model)|one-stop|service integration|sub-saharan|high-income|low-income|middle-income|era\b|calendar year|year of (art )?initiation|year of diagnosis|study (site|period)|program size|hospital size|recently opened|practice transformation|care model|outpatient pharmacy care|adult clinic care|patient portal|clinical monitoring alone|cares program|ingestible sensor",
     "Health-system, facility, policy or calendar-period factor; the Registered Tier has no facility / provider identifiers (provider and care_site tables are suppressed)."),
    (r"intervention|training|text messag|\bsms\b|mhealth|m-health|mobile phone|cell ?phone|reminder|directly observed|\bdot\b|\bdots\b|case management|navigat|incentive|cash transfer|adherence club|support group|treatment supporter|treatment buddy|buddy|home visit|home-based|community health worker|outreach|peer (counsel|educat|mentor|support worker)|enhanced adherence counsel|adherence counsel|adherence support|adherence device|electronic (pill|monitor|dose)|mems\b|pillbox|pill box|wisepill|video|telephone counsel|telehealth|telemedicine|motivational interview|psychoeducat|counselling and sms|multimonth dispensing|multi-month|fast.track|community art group|club (attendance|membership|participation)|recruitment|enrollment in (the )?(study|trial|program)|participation in (a|the) (study|trial)",
     "Program or intervention exposure (reminders, navigation, adherence clubs, incentives, peer support) is not recorded in the Registered Tier."),
    (r"belief|perception|perceived (benefit|risk|need|susceptibility|severity|efficacy|treatment)|attitude|concerns? (about|over|regarding)|worr(y|ies|ied) about|fear of|expectanc|motivation|readiness|intention|awareness|denial|acceptance of|necessity|treatment optimism|pill aversion|illness perception|self-esteem|self-worth|mindfulness|attachment|patient activation|behaviou?ral skills|information-motivation|\bimb\b|sense of coherence|internalized homophobia|homonegativity|syndemic|microaggression|identity affirmation|cultural capabilities|rumination|affect regulation|social skills|psychological resources|sensitivity to medicines|medication concerns|requesting informational",
     "No All of Us survey instrument measures this attitude, belief or psychological construct.",
     r"medical mistrust|trust in (provider|physician|doctor|health|clinician)|perceived (stress|discrimination|social support|stigma|racism|healthcare)|health literacy"),
    (r"heterosexual (transmission|exposure|risk|contact)|mode of (acquisition|transmission)|transmission (category|route|group|risk)|risk group|risk category|behaviou?rally acquired|route of (hiv )?(acquisition|infection)|blood transfusion|nosocomial",
     "HIV acquisition route / transmission category is not recorded in All of Us."),
    (r"\bprep\b|pre-exposure prophylaxis|post-exposure|\bpep\b|hiv transmission$|onward transmission|undetectable equals untransmittable|\bu=u\b", "Concerns HIV prevention or onward transmission rather than the participant's own HIV care; not observable in All of Us."),
]

# (pattern, variables, strength, note) - optional fifth element: dict(exclude=regex, cats={...})
# Patterns are matched case-insensitively against the KG entity name. All matching rules apply.
_DRUG_CTX = r"resistan|mutation|cross-resistance|susceptib|\bmonotherapy\b(?=.*resist)"
_OTHER_PERSON = r"partner|caregiver|husband|parental|parent|maternal|mother|network|family|household"
ENTITY_RULES = [
    # Demographic
    (r"\bages?\b|younger|older|elderly|\byouth\b|adolescen|young adult|\baged?\b|\byears? (old|or older|or younger)",
     ["age"], D, "Age is computed from date of birth",
     dict(exclude=r"age at (art|hiv|diagnos|initiation|first|seroconversion|start|infection|haart|transition)|stage|dosage|age-(related|associated)|older (regimen|drug|nrti)|gestational|maternal")),
    (r"\bage at (art|hiv|diagnos|initiation|first|seroconversion|start|infection|haart)|(older|younger|young) age at", ["age"], D, "Age at an event = event date − date of birth",
     dict(exclude=r"gestational")),
    (r"age-(related|associated)", ["age", "comorbidity"], P, "Age plus diagnosis codes"),
    (r"\bfemale|\bmales?\b|\bmen\b|\bwomen\b|\bwoman\b|\bman\b|\bsex\b|cisgender", ["sex_at_birth"], D, "Sex at birth is asked directly",
     dict(exclude=r"(unsafe|condomless|unprotected|safer|before|selling|trading|exchange|commercial|bartering|anal|male-male|transactional|forced|casual) sex|sex (work|exchange|trade|partner|with|act)|sex-trade|men who have sex|sexual|\bmsm\b|same.sex|regimen|partner|headed|transgender|trans (wo)?men|minority women|who inject")),
    (r"\bgender\b|transgender|\btrans (wo)?men|\btrans (masculine|feminine)|non-?binary|gender minority|gender (identity|affirm)", ["gender"], D, "Gender identity is asked directly",
     dict(exclude=r"gender-based violence|gender norm|gender-related discrimination|identity documents|child's gender")),
    (r"\bmsm\b|men who have sex with men|\bgay\b|bisexual|homosexual|male-male sex", ["msm_proxy"], P,
     "AoU records sexual orientation identity, not sexual behavior", dict(exclude=r"criminali|homophobia|internalized|sexual minority women")),
    (r"sexual orientation|lgbt|sexual minorit|lesbian|\bqueer\b", ["sexual_orientation"], D, "Sexual orientation is asked directly"),
    (r"\brace\b|ethnic|\bblacks?\b|african american|\bwhite\b|hispanic|latin[oax]|\basian\b|caucasian|non-white|nonwhite|\bminority (status|race|ethnicity|group)|racial/ethnic minority|aboriginal|indigenous|pacific islander|native american",
     ["race_ethnicity"], D, "Race/ethnicity is self-reported (generalized categories in Registered Tier)",
     dict(exclude=r"ryan white|white blood|white matter|segregation|mistrust|discrimination|stress|affirmation|neighbo")),
    (r"segregation|predominantly (black|latino|hispanic|white) neighbo", ["race_ethnicity", "area_deprivation"], P, "No neighborhood racial composition field; 3-digit ZIP SES only"),
    (r"educat|schooling|illitera|\bliteracy\b|high school|college|tertiary|secondary educ|primary educ",
     ["education"], D, "Highest grade completed is asked directly",
     dict(exclude=r"health literacy|treatment literacy|hiv treatment literacy|psychoeducat|self-education|hiv education|health education|patient education|adherence education|education session")),
    (r"\bincome|poverty|wealth|socioeconomic|socio-economic|\bses\b|economic (status|position|disadvantage)|financial status|low economic|material deprivation|economic deprivation|living conditions",
     ["income"], D, "Banded household income is asked directly; area-level SES from 3-digit ZIP",
     dict(exclude=r"country|setting|poverty stigma")),
    (r"financial|out-of-pocket|economic (hardship|barrier|strain|constraint)|socio-?economic (constraint|challenge|distress)|money|user fee|catastrophic|afford|healthcare costs|cost of (care|treatment|travel|medication)|paying for|self-funded|competing (subsistence )?needs|subsistence needs|income loss",
     ["financial_strain"], D, "HCAU asks about cost barriers to care and medications",
     dict(exclude=r"incentive|empowerment|safe and affordable|affordable care act")),
    (r"affordable care act", ["insurance"], D, "Insurance coverage and type"),
    (r"deprivation|neighbo(u)?rhood|disadvantaged area|community violence|area-level|built environment|living conditions",
     ["area_deprivation"], D, "ZIP-level deprivation index and neighborhood disorder scale", dict(exclude=r"predominantly")),
    (r"unemploy|employ|\bjobs?\b|occupation|\bwork(ing)?\b|\blabou?r\b|time off work|income.generating", ["employment"], D, "Employment status is asked directly",
     dict(exclude=r"sex work|social work|health( ?care)? work|network|framework|workload|work-up|community health worker|outreach work|forced sex|fear of losing")),
    (r"fear of losing (job|employment)|job security|job insecurity", ["employment"], P, "Employment status only; no job-security item"),
    (r"marital|married|marriage|spouse|widow|divorc|\bsingle\b|unmarried|partnered|cohabit|steady partner|living with (a )?(spouse|partner)|relationship status|lack of (spouse|partner)",
     ["marital"], D, "Marital status is asked directly",
     dict(exclude=r"single[- ](tablet|dose|pill|protease|boosted|visit|pi|regimen|drug|agent|nucleoside|mutation)|ritonavir single|single regular sexual|non-marital|sexual|disclos")),
    (r"living alone|lives alone|living with (family|parents|relatives|others)|household (composition|size|head)|headed household|family size|living arrangement|number of (people|persons) in",
     ["household"], D, "Household size is asked directly"),
    (r"having children|number of children|childcare|child care|caregiving|being primary caregiver|dependents|having at least two children", ["caregiving"], D,
     "HCAU childcare / caregiving barriers and number of children in household"),
    (r"migra|immigra|foreign.born|country of birth|refugee|nativity|undocumented|nationality|\borigin\b", ["birthplace"], P,
     "Only US vs non-US birthplace (detailed country suppressed)", dict(exclude=r"undocumented disease")),
    (r"language|english proficien|interpreter|limited english", ["language"], D, "Language at home and English proficiency are asked"),
    (r"veteran|military", ["veteran"], D, "Active duty service is asked"),
    (r"pregnan|postpartum|post-partum|antenatal|prenatal|breastfeed|perinatal|gestation|childbirth|antenatal care", ["pregnancy"], D, "Pregnancy status / codes"),
    (r"disabilit|functional (status|impairment|limitation|disabilit)|physical function|impaired mobility|mobility (limitation|impairment)|bed-?ridden|ambulatory|activities of daily living|\badl\b|performance status|karnofsky",
     ["disability"], D, "ACS disability items and everyday-activities item"),
    (r"religio|spiritual|faith|church|prayer", ["religion"], D, "BMMRS religiosity / spirituality items"),
    (r"traditional (healer|medicine)|herbal|alternative (medicine|therap)|complementary", ["traditional_healer"], D, "HCAU traditional healer items"),
    # Social / environmental
    (r"hous|homeless|shelter|evict|residential (instability|mobility)|marginally housed|street (residence|living|homeless)|unsheltered|residentially unstable|tenure",
     ["housing"], D, "Housing concern, moves and Z59 codes", dict(exclude=r"household|in-house")),
    (r"food|hunger|hungry|meals?\b|food assistance|food rations", ["food_insecurity"], D, "Hunger Vital Sign items and Z59.4",
     dict(exclude=r"food and drug administration|with food|food requirement|food effect|\bfda\b")),
    (r"transport|travel (time|distance|cost)|distance to (clinic|facility|health|care|healthcare|pharmacy)|\bdistance\b|bus fare|long journey|drive time|proximity to|commute",
     ["transportation"], D, "Transportation as a reason for delayed care", dict(exclude=r"genetic distance")),
    (r"\brural|\burban|remote area|semi-urban|peri-urban|geographic", ["rurality"], P,
     "No residence-level rurality field; only a rural-distance barrier item and 3-digit ZIP"),
    (r"insur|medicaid|medicare|uninsured|ryan white|\badap\b|aids drug assistance|health (plan|coverage)|healthcare coverage", ["insurance"], D,
     "Insurance coverage and type are asked directly", dict(exclude=r"haart coverage|art coverage")),
    (r"(health ?care|healthcare|clinic|service|care) access|access to (health ?care|care|services|clinic|treatment|medication|art)|barriers? to care|usual source of care|structural barrier|waiting time|wait time|primary care (physician|provider)|unmet (need|needs) for|ancillary|health service use|healthcare utili[sz]ation|service utili[sz]ation",
     ["healthcare_access"], D, "HCAU usual source of care and delayed-care reasons"),
    (r"patient-provider|provider-patient|doctor-patient|patient-doctor|patient-physician|therapeutic alliance|trust in (health|medical|provider|physician|doctor|clinician)|(medical|healthcare|physician) (mis)?trust|mistrust|provider (communication|trust|relationship|support|cultural)|communication with (health|provider|doctor|clinician)|healthcare provider (communication|treatment|trust)|respectful|staff treatment|treatment by (clinic )?staff|patient satisfaction|satisfaction with (provider|care|service)|treatment satisfaction|dissatisfaction with (?!life)|supportive (health ?care )?providers|perceptions of .*providers|attitudes towards health|victimization by healthcare|discussing .* with provider|provider-rated|shared decision|involvement in care decision|cultural competence",
     ["provider_relationship"], P, "HCAU respect / communication items approximate the relationship"),
    (r"incarcerat|prison|jail|criminal justice|\barrest|correctional|detention|imprisonment|reincarceration|re-incarceration", ["incarceration"], D,
     "Z65 imprisonment codes only (under-coded)"),
    (r"violence|abuse|assault|maltreat|\bipv\b|battered|sexual coercion|\brape\b|victimi[sz]ation|bullying",
     ["violence"], D, "T74/T76/Z91.41 codes; partly suppressed",
     dict(exclude=r"substance abuse|drug abuse|alcohol abuse|drug and alcohol abuse|abuse and dependence|healthcare staff")),
    (r"social support|support from|family support|peer support|emotional support|instrumental support|support network|social network|partner support|perceived support|psychosocial support|lack of support|social support satisfaction|emotional closeness|social relationships|social ties|support for sobriety|caregiver support",
     ["social_support"], D, "MOS Social Support Survey", dict(exclude=r"intervention|group (membership|participation)|telephone|from specialized staff")),
    (r"lonel|social isolation|socially isolated|\bisolation\b", ["loneliness"], D, "UCLA Loneliness Scale"),
    (r"social capital|social cohesion|community cohesion|collective efficacy|community support|community engagement|community connectedness", ["social_cohesion"], D,
     "Neighborhood social cohesion scale"),
    (r"discriminat|racism|homophobia|transphobia|prejudice|marginali|mistreatment|unfair treatment", ["discrimination"], D, "Everyday and medical discrimination scales",
     dict(exclude=r"non-discrimination laws")),
    (r"stigma|shame|stigmati", ["discrimination"], P, "General discrimination scales; AoU has no HIV-stigma instrument"),
    (r"stigma (from|in) (health ?care|hiv care|clinic)|health ?care.{0,12}stigma|stigma.{0,20}health ?care", ["provider_relationship"], P, "Medical discrimination items"),
    (r"stress|stressful|life events|adversit|hardship|negative life", ["stress"], D, "Perceived Stress Scale",
     dict(exclude=r"post-traumatic|posttraumatic|oxidative|financial|economic|socio-?economic|drug reaction|dosing schedule|hispanic stress")),
    # Substance use
    (r"alcohol|drink|ethanol|\baudit\b|hazardous drinking|\bdrunk", ["alcohol"], D, "AUDIT-C items and alcohol use disorder codes",
     dict(exclude=_OTHER_PERSON + r"|stigma|belief|avoidance|interactive")),
    (r"alcohol.{0,15}(stigma|belief|avoidance|interactive)|interactive toxicity", ["alcohol"], P, "Alcohol use only; no alcohol–ART belief items"),
    (r"binge|heavy episodic|heavy (alcohol|drinking)|excessive alcohol|at-risk drinking|hazardous", ["binge"], D, "Six or more drinks on one occasion"),
    (r"smok|tobacco|cigar|nicotine|vaping|e-cig", ["tobacco"], D, "Lifestyle smoking module and F17/Z72.0 codes",
     dict(exclude=r"crack|cocaine|" + _OTHER_PERSON)),
    (r"substance|drug use|drug abuse|illicit|recreational drug|polysubstance|polydrug|drug users?\b|people who use drugs|\bpwud\b|street drug|addiction|chemsex|party drug|drug dependence|\bsud\b|hard drug|other drug|illegal (drug|substance)|non-medical use|misuse",
     ["drug_use"], D, "Lifestyle drug use items and F11–F19 codes",
     dict(exclude=r"antiretroviral drug|drug resistance|drug-drug|drug interaction|drug level|drug concentration|study drug|drug toxicity|drug regimen|drug class|drug exposure|drug supply|treatment|stigma|criminali|" + _OTHER_PERSON)),
    (r"substance use stigma|drug use(r)? stigma|internalized drug use stigma", ["drug_use", "discrimination"], P, "Drug use items plus general discrimination"),
    (r"cocaine|crack", ["cocaine", "drug_use"], D, "Past-3-month cocaine use and F14 codes", dict(exclude=_OTHER_PERSON)),
    (r"methamphetamine|\bmeth\b|amphetamine|stimulant|crystal", ["stimulant", "drug_use"], D, "Past-3-month stimulant use and F15 codes", dict(exclude=_OTHER_PERSON)),
    (r"opioid|opiate|heroin|fentanyl|narcotic", ["opioid", "drug_use"], D, "Past-3-month opioid use and F11 codes",
     dict(exclude=r"opioid (agonist|substitution|maintenance)|treatment|" + _OTHER_PERSON)),
    (r"benzodiazepine|sedative|tranquil", ["drug_use"], D, "Non-medical sedative use item", dict(exclude=r"prescription(?!.*misuse)")),
    (r"cannabis|marijuana|marihuana", ["cannabis", "drug_use"], D, "Past-3-month cannabis use", dict(exclude=_OTHER_PERSON)),
    (r"inject|\bidu\b|\bpwid\b|intravenous drug|\bivdu\b|needle|syringe|\biv drug", ["injection", "drug_use"], P, "Route of drug use is not recorded",
     dict(exclude=r"long-acting|injectable|cabotegravir|injection site|missed injection|late injection|injection visit|non-?inject|noninjected|\bexchange\b")),
    (r"non-?inject(ion|ed)? drug", ["drug_use"], D, "Drug use items (route not recorded)"),
    (r"methadone|buprenorphine|opioid (agonist|substitution|maintenance)|\bmoud\b|\bmat\b|\bost\b|\boat\b|substance (abuse|use)( disorder)? treatment|drug treatment|addiction treatment|rehab|harm reduction|needle exchange|syringe service|detox",
     ["sud_treatment"], D, "MOUD prescriptions and SUD service codes"),
    (r"unprotected|condom|sexual (risk|behav|activity|intercourse)|multiple (sexual )?partners|number of (sexual )?partners|transactional sex|sex work|commercial sex|risky sex|casual partner|selling sex|trading sex|sex exchange|bartering sex|sex-trade|unsafe sex|serodiscordant|concurrent partner",
     ["sexual_risk"], P, "No sexual behavior items; STI history as a marker"),
    # Psychosocial
    (r"\bdepress|dysthymi|\bphq\b|\bcesd\b|ces-d|mood disorder|antidepressant|\baffective disorder|internali[sz]ing|low mood", ["depression"], D,
     "PHQ-9, self-reported diagnosis and F32–F33 codes", dict(exclude=r"immunodepress|clinician-rated|alleviation")),
    (r"clinician-rated depression|depression alleviation", ["depression"], D, "Depression diagnosis codes and PHQ-9"),
    (r"\banxi|\bpanic\b|panic disorder|\bgad\b|\bworry\b|\bnervous(ness)?\b|internali[sz]ing", ["anxiety"], D, "GAD-7, self-reported diagnosis and F41 codes",
     dict(exclude=r"nervous system|attachment|death anxiety")),
    (r"death anxiety", ["anxiety"], P, "Generalized anxiety measures only"),
    (r"ptsd|post-?traumatic stress|\btrauma\b|trauma (symptom|history|exposure)|traumatic (event|experience|stress|life)|lifetime trauma|psychosocial trauma|adverse childhood|\baces\b|childhood (abuse|adversity|trauma)|child sexual abuse",
     ["ptsd"], D, "Self-reported PTSD, F43.1 and trauma-history codes", dict(exclude=r"traumatic brain|trauma surgery|growth")),
    (r"post-?traumatic growth", ["resilience"], P, "Resilient coping items"),
    (r"bipolar|schizo|psychos|psychotic|serious mental illness|\bsmi\b|severe mental illness", ["smi"], D, "Self-reported diagnosis and F20–F31 codes"),
    (r"mental (health|illness|disorder)|psychiatric (illness|disorder|diagnos|comorbid|background|condition|symptom|history)|psychological (distress|symptom|problem|issue|challenge|condition|disturbance|well)|\bdistress\b|emotional (functioning|distress|problem|well)|wellbeing|well-being|common mental|neuropsychiatric symptoms|negative affect|psychosocial (problem|stress|factor)",
     ["mental_health_general"], D, "PROMIS global mental health and emotional problems items",
     dict(exclude=r"mental health (service|treatment|care|referral|counsel|intervention|stigma)|psychological (support|intervention|counsel)|caregiver|youth|physical well|economic")),
    (r"mental health stigma", ["mental_health_general", "discrimination"], P, "Mental health items plus general discrimination"),
    (r"suicid|self-harm|self harm", ["suicidality"], D, "PHQ-9 item 9 and R45.851 codes"),
    (r"(mental health|psychiatric|psychological|behavioral health) (service|treatment|care|referral|counsel|support|intervention)|psychotherapy|cognitive behavio|contact with psychiatric|psychiatric care|counsel+ing services|professional counsel|psychotropic|antipsychotic|anxiolytic",
     ["mh_treatment"], D, "Mental health visits, services and psychotropic prescriptions",
     dict(exclude=r"adherence|non-medical|misuse")),
    (r"resilien", ["resilience"], D, "Brief Resilient Coping Scale"),
    (r"coping|\bcopes?\b", ["resilience"], P, "Brief Resilient Coping Scale (COVID-era); no coping-style instrument",
     dict(exclude=r"religious coping|spiritual coping|substance use coping")),
    (r"\bhope|optimis|pessimis|fatalis|meaning in life|purpose in life|positive affect|happiness|unhappiness|life satisfaction", ["optimism"], P,
     "LOT-R optimism and happiness items (COPE)", dict(exclude=r"hopeless|treatment optimism")),
    (r"hopeless", ["optimism", "depression"], P, "PHQ-9 item 2 and LOT-R optimism"),
    (r"self-efficacy|self efficacy|locus of control|mastery|empowerment|perceived control|confidence", ["self_efficacy"], P,
     "No self-efficacy instrument; perceived-stress control items", dict(exclude=r"economic empowerment|intervention|confidence interval")),
    (r"health literacy|\bnumeracy", ["health_literacy"], D, "Brief Health Literacy Screen items"),
    (r"\bliteracy\b|illitera", ["health_literacy"], P, "Health literacy screen approximates general literacy"),
    (r"hiv knowledge|knowledge (of|about) (hiv|art|treatment|antiretroviral)|treatment (knowledge|literacy)|art knowledge|comprehensive hiv knowledge", ["health_literacy"], P,
     "Health literacy approximates HIV treatment knowledge"),
    (r"cognit|dementia|\bmemory\b|executive function|\battention\b|difficulty concentrating|intellectual functioning|\bhand\b|hiv-associated neurocog",
     ["cognition"], D, "Self-report, diagnoses and Exploring the Mind tasks",
     dict(exclude=r"cognitive behavio|cognitive depressive|medical attention|attention to|cognitive resilience|memory-based strategy")),
    (r"prospective memory|memory-based strategy", ["cognition"], P, "Memory self-report and cognitive tasks; no prospective-memory test"),
    (r"impulsiv|delay discount|present bias|time preference|future orientation|risk.taking|sensation seeking", ["impulsivity"], P,
     "Delay discounting task (Exploring the Mind)", dict(exclude=r"sexual risk")),
    (r"quality of life|\bqol\b|hrqol|self-rated health|self-reported health|perceived health|health status|general health|overall health|(physical|social|role|emotional) functioning|health perceptions",
     ["quality_of_life"], D, "PROMIS Global items in Overall Health", dict(exclude=r"caregiver")),
    (r"symptom burden|hiv symptom|hiv-related symptoms|physical symptoms|distressing physical|somatic symptom", ["pain_fatigue", "quality_of_life"], P,
     "Pain / fatigue items; no HIV symptom index"),
    (r"sleep|insomnia", ["sleep"], D, "Fitbit sleep, insomnia history, PHQ-9 sleep item"),
    (r"physical activity|exercise|sedentary|fitness|\bsteps\b|physically active", ["physical_activity"], D, "Fitbit activity and IPAQ"),
    (r"frail", ["disability", "quality_of_life", "physical_activity"], P, "No frailty index; functional limitation and activity items"),
    (r"\bpain\b|fatigue|tiredness|\btired\b", ["pain_fatigue"], D, "Pain and fatigue items", dict(exclude=r"treatment fatigue|pill fatigue")),
    # Biological / clinical
    (r"hiv infection|hiv diagnos|hiv-positive|hiv positive|living with hiv|\bplwh|\bplhiv|seropositiv|\bhiv status|newly diagnosed|symptomatic hiv|hiv-2|hiv-related (disease|complication|event)|hiv disease\b|^hiv$|hiv/aids diagnosis",
     ["hiv_dx"], D, "HIV condition codes and PFHH self-report",
     dict(cats={"BiologicalMarker", "Outcome", "Demographic", "Treatment", "AdherenceBehavior"})),
    (r"time since (hiv )?(diagnosis|infection)|duration of hiv|years since (hiv )?diagnosis|years with hiv|time with hiv|known hiv duration", ["hiv_dx"], P,
     "Earliest HIV code / test date; left-censored before EHR coverage"),
    (r"coinfect|co-infect", ["hbv", "hcv", "tb", "sti"], P, "Generic coinfection: pick the specific pathogen"),
    (r"viral load|viraemi|viremi|virolog|suppress(ed|ion)? viral|viral (suppression|resuppression|rebound|response|blip|control)|resuppress|unsuppress|non-?suppress|\bvl\b|hiv rna|rna level|\bblips?\b|detectable|copies|log10|\bu=u\b",
     ["viral_load"], D, "HIV-1 RNA measurements with standard thresholds",
     dict(exclude=r"hbv|hcv|discussion|immunosuppress|cd4")),
    (r"treatment failure|art failure|treatment response|treatment outcome|clinical failure|therapeutic failure|regimen failure|first-line failure|second-line failure|drug failure|treatment success|class (drug )?failure|incomplete (viral|virologic) response|virologic outcome",
     ["viral_load", "cd4", "regimen_change"], P, "Composite of VL, CD4 and regimen switches; exact definition varies"),
    (r"\bcd4\b|cd4\+|t-cell count|t cell count|lymphocyte count|immunolog|immune (recovery|reconstitution|response|status|non-?response)|immunosuppress|immunodeficien|immunodepress|lymphopenia|discordant (immun|cd4)",
     ["cd4"], D, "CD4 measurements with standard thresholds", dict(exclude=r"cd4/cd8|cd4:cd8|activation|apoptosis")),
    (r"cd4/cd8|cd4:cd8|cd8 (count|percent|ratio)", ["cd4cd8"], D, "CD4/CD8 ratio"),
    (r"resistan|mutation|genotyp|\bdrms?\b|k103n|m184v|k65r|y181c|y188l|\btams?\b|thymidine analog|genotypic (sensitivity|susceptibility)|susceptibility score|phenotypic|cross-resistance",
     ["resistance"], P, "Resistance testing may be recorded, but mutation results are rarely structured",
     dict(exclude=r"insulin resistance|tubercul|\btb\b|\bmdr\b|vascular resistance")),
    (r"multidrug.resistant tuberculosis|\bmdr-?tb|drug-resistant tb", ["tb"], D, "TB codes (resistance not structured)"),
    (r"advanced hiv|\baids\b|clinical stage|disease stage|late (presentation|presenter|diagnosis)|late-stage|cdc stage|stage (3|4|iii|iv|c)\b|disease progression|clinical progression|hiv progression|aids progression|aids-defining|aids (event|diagnosis|illness|development|mortality|death)|history of aids|prior aids|clinical aids",
     ["advanced_hiv"], D, "CD4 <200 and AIDS-defining diagnoses",
     dict(exclude=r"who (clinical )?stage|who disease stage|clinical stage|disease stage|non-aids|orphan|drug assistance|stigma|family history|undocumented|disease progression|clinical progression")),
    (r"who (clinical )?stag|who disease stage|clinical stage|disease stage|disease progression|clinical progression|hiv stage", ["advanced_hiv"], P,
     "WHO staging is not coded; approximate from CD4 and AIDS-defining diagnoses", dict(exclude=r"undocumented")),
    (r"non-aids|serious non-aids|non-communicable", ["comorbidity"], D, "Non-AIDS diagnosis codes"),
    (r"opportunistic|\bois?\b|pneumocystis|\bpcp\b|cryptococc|toxoplasm|kaposi|cytomegalovirus|\bcmv\b|candid|mycobacterium avium|\bmac\b|microsporid|cryptosporid|histoplasm|talaromyc|\bpml\b|aids-defining (illness|event|condition|opportunistic)",
     ["oi"], D, "AIDS-defining condition codes", dict(exclude=r"non-aids|herpesvirus coinfection|prophyla")),
    (r"tubercul|\btb\b|\bmtb\b", ["tb"], D, "TB codes, PFHH self-report and TB drugs", dict(exclude=r"country|burden")),
    (r"isoniazid|rifamp|rifabutin|\bipt\b|\btpt\b|\binh\b|tb (treatment|therapy|preventive|regimen)|anti-?tb|anti-?tuberculosis|tuberculosis (treatment|preventive|therapy)", ["tb_treatment"], D,
     "TB drug exposures"),
    (r"hepatitis b|\bhbv\b|hbsag", ["hbv"], D, "HBV codes, labs and self-report"),
    (r"hepatitis c|\bhcv\b", ["hcv"], D, "HCV codes, labs and self-report"),
    (r"\bstis?\b|\bstds?\b|sexually transmitted|syphilis|gonorr|chlamydia|genital herpes|\bhsv-?2|\bhpv\b|trichomon", ["sti"], D, "STI codes and PFHH self-report"),
    (r"\bbmi\b|body mass|\bweight\b|bodyweight|obes|overweight|underweight|waist|adipos|lipodystroph|lipoatrophy|anthropometr", ["body_size"], D,
     "Weight/height/BMI measurements and obesity codes", dict(exclude=r"low birth weight|molecular weight|weighted")),
    (r"malnutrition|undernutrition|wasting|cachexia|nutritional status|malnourish|\bmuac\b", ["malnutrition"], D, "E40–E46/R64 codes"),
    (r"an(a)?emi|hemoglobin|haemoglobin", ["anemia"], D, "Hemoglobin and D50–D64 codes"),
    (r"renal|kidney|creatinine|\begfr\b|nephro|albuminuria|proteinuria", ["kidney"], D, "Renal labs and N17–N19 codes"),
    (r"\bliver\b|hepatotoxic|transaminase|\balt\b|\bast\b|cirrhosis|hepatic|fibrosis|steato", ["liver"], D, "Liver labs and K70–K77 codes"),
    (r"diabet|hypertens|blood pressure|cardiovascular|cardiac|\bheart\b|stroke|lipid|cholesterol|dyslipid|metabolic syndrome|glucose|insulin|\bcvd\b|cardiomyopath|myocard|atheroscl|coronary",
     ["cardiometabolic"], D, "Cardiometabolic condition codes and labs"),
    (r"cancer|malignan|lymphoma|tumou?r|neoplas|carcinoma|intraepithelial|dysplasia", ["cancer"], D, "C00–C96 codes and PFHH cancer"),
    (r"comorbid|multimorbid|multi-morbid|co-morbid|chronic (disease|condition|illness)|\bncds?\b|\bmorbidity\b|severe morbidity", ["comorbidity"], D,
     "Charlson/Elixhauser from diagnosis codes"),
    (r"erectile|sexual dysfunction|hypogonad|lactic acidosis|pancreatitis|gynecomastia|osteop|bone (mineral|density|loss)|fracture|vitamin d|dental|caries|periodont|herpes zoster|shingles|pneumonia|respiratory (tract )?infection|sepsis|diarrh|neuropathy|seizure|thrombo|hyperlactat",
     ["other_clinical"], D, "Specific diagnosis / lab concept in EHR"),
    (r"c-reactive|\bcrp\b|d-dimer|albumin\b|lactate|ferritin|platelet|white (blood )?cell|neutrophil", ["other_clinical"], D, "Routine lab concept in measurement"),
    # Treatment
    (r"\bart\b|\bcart\b|\bhaart\b|antiretrovira|\barvs?\b|regimen|first-line|second-line|third-line|salvage|triple therapy|dual therapy|two-drug|three-drug|monotherapy",
     ["art_exposure"], D, "ARV drug_exposure records",
     dict(exclude=_DRUG_CTX + r"|knowledge|initiation|initiat|start|duration|time on|adherence|nonadherence|non-adherence|missed|side effect|adverse|toxicit|failure|stigma|belief|switch|change|modif|substitut|complexity|optimism|literacy|club|tuberculosis|\btb\b")),
    (r"(art|antiretroviral|haart|regimen).{0,20}(side effect|adverse|toxicit)", ["art_exposure"], P, "ARV exposure plus adverse-effect codes"),
    (r"efavirenz|\befv\b|nevirapine|\bnvp\b|rilpivirine|\brpv\b|etravirine|doravirine|nnrti|non-nucleoside", ["art_nnrti", "art_exposure"], D, "NNRTI ingredients",
     dict(exclude=_DRUG_CTX + r"|toxicit|side effect|adverse")),
    (r"lopinavir|atazanavir|darunavir|ritonavir|protease inhibitor|\bpis?\b|boosted|saquinavir|indinavir|nelfinavir|fosamprenavir|tipranavir", ["art_pi", "art_exposure"], D, "PI ingredients",
     dict(exclude=_DRUG_CTX + r"|toxicit|side effect|adverse")),
    (r"dolutegravir|\bdtg\b|bictegravir|raltegravir|elvitegravir|cabotegravir|integrase|\binstis?\b", ["art_insti", "art_exposure"], D, "INSTI ingredients",
     dict(exclude=_DRUG_CTX + r"|toxicit|side effect|adverse")),
    (r"tenofovir|\btdf\b|\btaf\b|emtricitabine|lamivudine|\b3tc\b|abacavir|zidovudine|\bazt\b|stavudine|\bd4t\b|didanosine|zalcitabine|\bnrtis?\b|nucleoside", ["art_nrti", "art_exposure"], D, "NRTI ingredients",
     dict(exclude=_DRUG_CTX + r"|toxicit|side effect|adverse")),
    (r"maraviroc|enfuvirtide|ibalizumab|fostemsavir|lenacapavir", ["art_exposure"], D, "Other ARV ingredients", dict(exclude=_DRUG_CTX)),
    (r"single.tablet|fixed.dose combination|\bfdc\b|\bstr\b", ["art_str", "art_exposure"], D, "Combination ARV products"),
    (r"long-acting|injectable (art|antiretroviral|regimen)|cabotegravir|missed injection|late injection|injection visit", ["art_lai"], D, "Long-acting cabotegravir/rilpivirine"),
    (r"(art|antiretroviral|treatment|haart|cart|therapy) (initiation|start)|initiat|time to (art|treatment)|rapid art|same-day|deferred (art|treatment)|immediate art|delayed (art|haart|cart|treatment)|treatment delay|early art|late art|pre-art|before art|art-naive|treatment-naive",
     ["art_timing"], P, "ART start and diagnosis dates can be left-censored in EHR"),
    (r"switch|substitut|discontinu|regimen (change|modification)|change (of|in) regimen|regimen simplif|simplification|stopp|regimen modification|treatment modification",
     ["regimen_change"], D, "Changes in ARV ingredient sets", dict(exclude=r"opioid substitution|discontinuous care|education|smoking")),
    (r"pill burden|number of pills|pill count|dosing frequency|dosing schedule|times daily|twice.daily|once.daily|daily dosing|pill size|polypharmacy|treatment complexity|regimen complexity|medication complexity",
     ["pill_burden"], P, "Derived from drug products and quantities"),
    (r"side effect|adverse (drug )?(event|effect|reaction)|toxicit|intoleran|\bades?\b|drug reaction|hypersensitiv|\brash\b|dizziness|nausea|vomiting|gastrointestinal|central nervous system|neuropsychiatric (side|adverse|toxic)",
     ["side_effects"], D, "Adverse-effect codes T37.5X5", dict(exclude=r"belief|concern|distress|spirituality")),
    (r"prophyla|cotrimoxazole|co-trimoxazole|trimethoprim|fluconazole|dapsone|azithromycin|sulfamethoxazole", ["oi_prophylaxis"], D, "OI prophylaxis prescriptions",
     dict(exclude=r"isoniazid|\binh\b|pre-exposure|antiretroviral prophylaxis")),
    (r"(art|treatment|haart|cart|therapy|regimen|line art|medication|art treatment) (duration|follow-up)|duration (of|on) (art|haart|cart|treatment|therapy|hiv medication|first|second|failing|nonsuppressive)|time on (art|treatment|haart)|years on (art|treatment)|months on (art|treatment)|length of (art|treatment)|treatment (experience|experienced)|art-experienced|prior art|previous art|art exposure|prior (protease|nnrti|nrti|regimen)|multiple prior|number of (prior )?regimens|lifetime number|art duration|long duration on|longer art|shorter art|short art",
     ["treatment_duration"], P, "Cumulative ARV exposure from EHR (left-censored)"),
    # Adherence / engagement
    (r"adheren|complian|missed (art )?doses?|missing dose|skipped dose|forget|forgot|pill taking|drug taking|selective drug|treatment interruption|treatment fatigue|pill fatigue|refill|pharmacy (pick|collect|nonadheren)|drug pick-?up|medication pick-?up|pickups?|\bmpr\b|\bpdc\b|possession ratio|dose timing|late dose|missed medication|medication (error|hiding)|treatment (continuation|resumption|discontinuation)|self-manag|self-care|treatment default|never defaulting|overadherence",
     ["adherence"], P, "Refill-based PDC, nonadherence Z-codes; no self-reported ART adherence item",
     dict(exclude=r"cost-related|due to cost|to save money|appointment|clinical follow-up|visit")),
    (r"cost-related|due to cost|to save money|cannot afford (medication|drugs)|medication cost|self-funded", ["cost_nonadherence"], D, "HCAU cost-related nonadherence items"),
    (r"retention|retained|engagement in (hiv )?care|engaged in care|care engagement|hiv care engagement|clinic attend|appointment|missed (clinic|hiv|office|medical|gynecologic|clinical) (visit|appointment)|missed visits?|no-show|loss to follow|lost to follow|\bltfu\b|disengage|dropout|drop-out|attrition|continuity of care|re-?engage|out of care|discontinuous care|gaps? in care|visit constancy|clinic nonattendance|care interruption|clinical follow-up|follow-up visit",
     ["retention"], P, "Visit / lab dates at AoU partner sites only", dict(exclude=r"intervention|decision")),
    (r"linkage|linked to care|time to (care|linkage)|delayed (care|presentation|diagnosis)|late (presentation|diagnosis|presenter)|entry (into|to) care|care entry|diagnosis delay|early (hiv )?diagnosis",
     ["linkage"], P, "Diagnosis and first-care dates from EHR"),
    (r"hiv test|testing uptake|hiv screening|\bhts\b|\bvct\b|self-test|testing history|prior (hiv )?testing", ["hiv_testing"], D, "HIV test measurements"),
    (r"viral load (monitoring|testing|test)|cd4 testing|laboratory monitoring|lab monitoring", ["retention"], P, "Lab test dates as engagement markers"),
    # Outcomes
    (r"mortality|death|died|surviv|fatal(ity)?\b|deceased|dying", ["mortality"], D, "Death dates (cause suppressed)",
     dict(exclude=r"death anxiety|fatalis|child mortality")),
    (r"hospitali|admission|inpatient|emergency (department|room|visit)|\bed (visit|use)|readmission|acute care|\bicu\b|intensive care", ["hospitalization"], D,
     "Inpatient/ER visit concepts"),
    (r"social determinants|social needs|social risk", ["income", "housing", "food_insecurity", "transportation", "social_support"], P,
     "Generic SDOH construct: pick component measures"),
    (r"physical (health|well-?being)|poor health|health outcomes", ["quality_of_life"], D, "PROMIS Global physical health items"),
    (r"drug interaction|drug-drug|coadministration|concomitant (medication|drug)|co-medication", ["polypharmacy_var"], P, "Overlapping drug exposures"),
    (r"mirtazapine|carbamazepine|phenytoin|hydroxyurea|hormon|contracepti|statin|metformin|steroid|anticonvuls|antibiotic", ["other_drug_var"], D, "Specific drug ingredient in drug_exposure"),
    (r"start(ing)? (art|regimen|treatment)|rapid start", ["art_timing"], P, "ART start date (left-censored)"),
    (r"time since last visit|late visits|consistent (hiv )?care|treatment engagement|hiv care continuum|care continuum", ["retention"], P, "Visit dates at AoU partner sites"),
    (r"severity of illness|severe clinical|advanced clinical|clinical status", ["advanced_hiv"], P, "CD4 and AIDS-defining diagnoses"),
    (r"oral thrush|thrush", ["oi"], D, "Candidiasis codes"),
    (r"\bparity\b|multipar|nullipar|preterm|birth weight|periconception|gravid", ["pregnancy"], P, "Pregnancy codes in the participant's EHR"),
    (r"student", ["employment"], D, "Employment status includes 'student'"),
    (r"automobile|car ownership|vehicle", ["transportation"], P, "Transportation barrier items"),
    (r"southern|\bregion\b|regional|\bstate of residence|residence in", ["rurality"], P, "3-digit ZIP only"),
    (r"family (functioning|cohesion)|family relationships|family conflict", ["social_support"], P, "MOS social support items"),
    (r"khat|kava|betel", ["drug_use"], P, "Lifestyle 'other drugs' item only"),
    (r"covid|sars-cov-2|pandemic|lockdown", ["covid"], P, "COPE survey (2020–21)"),
]
