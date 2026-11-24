# Final Technical Report — SkillScope: Job Market & Skill-Gap Intelligence Warehouse & Dashboard

**National University of Computer & Emerging Sciences (FAST-NUCES), Karachi Campus**  
**Section:** BDS-5B  
**Courses:** Data Warehousing & Business Intelligence (DWBI) & Data Analytics & Visualization (DAV)  
**Group Members:**
- **24K-2505** — Myer Kamran
- **24K-2521** — Shazil Ahmed
- **24K-2583** — Ali John Rajani

---

## 1. Executive Summary
SkillScope integrates five authentic public dataset families spanning **2020–2025**—**Kaggle LinkedIn Job Postings** (`33,246` raw $\rightarrow$ `32,394` deduplicated postings spanning `2023-06-08` to `2023-11-04`), six **Stack Overflow Annual Developer Surveys (2020–2025)** (`424,980` total developer respondents harmonized into 6-year skill trends plus `65,437` full 2024 cohort rows with `732,058` respondent-skill links), **`ai-jobs.net` Global Tech Salaries (2020–2025)** (`151,445` raw $\rightarrow$ `151,439` validated USD salary records), the **European Commission ESCO Taxonomy** (`3,015` occupations linked to `86` canonical skills across `21` categories), and **GeoNames Global Cities** (`34,216` raw cities $\rightarrow$ `4,208` warehouse locations across `49` countries)—into a layered **Bronze $\rightarrow$ Silver $\rightarrow$ Gold Lakehouse** and a **Constellation/Snowflake Data Warehouse**.

On top of the warehouse, SkillScope executes two AI/Analytics pipelines:
1. **Rule-Based ESCO-Aligned NLP Skill Extractor:** Cleans raw HTML safely without breaking mid-word tags, normalizes aliases (`JS` $\rightarrow$ `JavaScript`, `PowerBI` $\rightarrow$ `Power BI`), and applies explicit context disambiguation rules (`R`, `Go`, `Rust`, `React`, `Apache Spark`, `Swift`, `Excel`, `transformers`, `SAS`, `PLC`, `Ruby`, `Salesforce`). Evaluated against an independent, human-audited 100-posting ground-truth benchmark (`nlp/ground_truth_100.json`, 75 tech/data postings + 25 non-tech hard negatives), it achieves **98.48% Precision, 93.61% Recall, 95.98% F1-score**, and **100.0% Hard-Negative Specificity** (`454 TP`, `7 FP`, `31 FN`).
2. **Knowledge-Based Expert System with Mamdani Fuzzy Priority Scoring:** Evaluates a learner's current skills against any target role by fuzzifying **Role Demand %**, **Salary Premium %**, and **Co-occurrence Proximity** into *Low*, *Medium*, and *High* membership degrees, defuzzifying into a `gap_score` ($0\text{--}100$) with human-readable rationales, and writing personalized learning priorities back into `fact_skill_gap_result` (`1,080` pre-computed rows + live web studio write-back).

---

## 2. Lakehouse & ETL Reconciliation Summary (`50/50` Quality Checks Passed)

| Layer | Input / Table | Row Count | Key Operations Performed |
| :--- | :--- | :--- | :--- |
| **Bronze / Staging** | `job_postings.csv` (`stg_job_postings`) | 33,246 | Raw landing with source name, file name, and load timestamp |
| **Bronze / Staging** | `survey_2020..2025.parquet` (`stg_survey_responses`) | 424,980 | Six annual Stack Overflow cohorts (`2020`: 64,461; `2021`: 83,439; `2022`: 73,268; `2023`: 89,184; `2024`: 65,437; `2025`: 49,191) |
| **Bronze** | `ai_jobs_salaries_2020_2025.csv` | 151,445 | Global AI/ML/Data/Tech compensation records across 2020–2025 |
| **Bronze / Staging** | `train-00000-...parquet` (`stg_esco_skills`) | 3,015 | European Commission ESCO occupation-skill competency profiles |
| **Bronze** | `cities15000.txt` | 34,216 | Global GeoNames city coordinates (population > 15,000) |
| **Silver** | `silver_job_postings` / `silver_posting_skills` | 32,394 / 41,462 | HTML cleaned, deduplicated, authentic timestamps (`2023-06-08`..`2023-11-04`), GeoNames matched (`90.8%`), USD annual salary normalized (`40.07%` disclosed; missing kept as `NULL`) |
| **Silver** | `silver_historical_survey_yearly` / `silver_ai_jobs_salaries` | 516 / 151,439 | Harmonized 2020–2025 Stack Overflow schema + USD-validated multi-year salary records mapped to roles, seniority & work mode |
| **Silver** | `silver_survey_responses` / `silver_geonames_cities` | 65,437 / 4,207 | Full Stack Overflow 2024 cohort (missing experience kept as `NULL`) + all 3,400+ US cities & top 800 global cities |
| **Gold** | `fact_job_posting` + `fact_posting_skill` | 32,394 / 41,462 | Conformed job posting fact across 11,326 companies, 29 roles, & 2,146 matched locations (`16,347` postings with skills) |
| **Gold** | `fact_survey_response` + `fact_survey_skill` | 65,437 / 732,058 | Full 2024 Stack Overflow developer cohort & standardized tool usage |
| **Gold (Historical)** | `fact_historical_skill_trend` + `fact_historical_salary_benchmark` | 516 / 2,185 | Kimball periodic snapshot facts spanning 2020–2025 across `424,980` SO devs & `151,439` salary records |
| **Gold** | `fact_skill_gap_result` (AI Write-Back) | 1,080 | Pre-computed fuzzy skill-gap rankings across 5 learner personas & 18 target roles |

---

## 3. Constellation & Snowflake Schema Design

Both **PostgreSQL + PostGIS** (`warehouse/schema_postgres_postgis.sql`) and **MySQL 8.0** (`warehouse/schema.sql`) implement the complete architecture:
- **7 Fact/Bridge Tables:** `fact_job_posting`, `fact_posting_skill` (many-to-many bridge), `fact_survey_response`, `fact_survey_skill` (bridge), `fact_skill_gap_result`, `fact_historical_skill_trend` (2020–2025 SO snapshot fact), and `fact_historical_salary_benchmark` (2020–2025 global salary snapshot fact).
- **7 Star Dimensions:** `dim_date` (2,557 days, `2020-01-01` to `2026-12-31`), `dim_company` (`11,326` + 2 SCD demo rows, SCD Type 2 `effective_from`/`effective_to`/`is_current`), `dim_location` (`4,208` rows with `POINT` spatial geometry), `dim_role` (29 normalized roles), `dim_seniority` (7 levels), `dim_source` (9 sources covering 2020–2025 datasets), `dim_skill` (86 canonical skills with `esco_occupation_count` and SCD Type 2 versioning).
- **4 Snowflaked Sub-Dimensions:** `dim_industry` (10), `dim_country` (49), `dim_role_family` (10), and `dim_skill_category` (21).
- **2 Data Marts:** `mart_demand` and `mart_skills` SQL views.

---

## 4. Indexing & Spatial R-Tree Design

| Index Type | PostgreSQL + PostGIS | MySQL 8.0 | Purpose |
| :--- | :--- | :--- | :--- |
| **B-Tree (Primary & Foreign Keys)** | PK/FK B-Tree on all 11 dims & 5 facts/bridges | PK/FK B-Tree on all 11 dims & 5 facts/bridges | Fast star joins and slicer filtering |
| **Composite B-Tree** | `(skill_key, posting_key)` on `fact_posting_skill`; `(date_key, role_key)` on `fact_job_posting` | `(skill_key, posting_key)` on `fact_posting_skill`; `(date_key, role_key)` on `fact_job_posting` | Accelerates skill demand rollups by role & period |
| **BRIN / Date Index** | `BRIN` index on `fact_job_posting(date_key)` | B-Tree index on `fact_job_posting(date_key)` | Efficient chronological range scans |
| **GIN Trigram / FULLTEXT** | `GIN (gin_trgm_ops)` on `role_title_norm` & `skill_name` | `FULLTEXT` on `role_title_norm` & `skill_name` | Fast text search on titles and skills |
| **R-Tree Spatial Index** | `GiST` index on `dim_location(geom)` (`GEOMETRY(Point, 4326)`) | `SPATIAL INDEX` on `dim_location(geom)` (`POINT`) | Bounding-box (`&&` / `MBRContains`) & radius (`ST_DWithin`) queries |

### Live MySQL 8.0 Warehouse & `EXPLAIN ANALYZE` Verification (`skillscope_dw`)
Loaded cleanly via `warehouse/load_mysql.py` (`83.9s`), creating all 3 staging tables (`stg_job_postings`: 2,000, `stg_survey_responses`: 2,000, `stg_esco_skills`: 3,015), 11 dimensions (`dim_date`: 2,557 spanning 2020–2026; `dim_source`: 9), 7 facts/bridges (`fact_job_posting`: 32,394, `fact_posting_skill`: 41,462, `fact_survey_response`: 65,437, `fact_survey_skill`: 732,058, `fact_skill_gap_result`: 1,080, `fact_historical_skill_trend`: 516, `fact_historical_salary_benchmark`: 2,185), and both Data Mart views (`mart_demand`: 32,394 rows, `mart_skills`: 41,462 rows), plus SCD Type 1/2 verification (`SCD Demo Corp` expired v1 + active v2).
- **Composite B-Tree Benchmark (`idx_fps_skill_posting`):** `Covering index lookup on fps using idx_fps_skill_posting` aggregating 3,972 postings across 5 skills in **5.06 ms**.
- **Spatial Bounding-Box Benchmark (`dim_location` $\bowtie$ `fact_job_posting`, 485 West Coast cities / 4,341 postings):** **78.8 ms** (`IGNORE INDEX (sp_idx_location_geom)`) vs. **80.0 ms** (`FORCE INDEX (sp_idx_location_geom)`, using `Covering index lookup on f using idx_fjp_location`); note that without an explicit `SRID` column constraint on MySQL 8.0 `POINT`, the optimizer falls back to scanning the 4,208-row `dim_location` table rather than an R-Tree range scan.

---

## 5. Verified Exploratory Data Analysis (EDA) Findings

1. **Market Overview KPIs:** Across **32,394** deduplicated job postings (`2023-06-08` to `2023-11-04`), **12,979** (`40.07%`) disclose salaries with a median annual salary of **\$83,200 USD** (mean **\$96,123 USD**) and **14.45%** remote-eligible postings.
2. **Entry-Level Experience Paradox:** Out of **7,744** deduplicated postings tagged as *Entry Level*, **1,081** (**13.96%**) explicitly require **3+ years of experience** in their job description.
3. **Top Skills & Authentic Wave-over-Wave Shifts (Oct–Nov 2023 vs. Jun–Sep 2023):**
   - **Most Mentioned Skills Overall:** **Excel** (4,652 postings), **Supply Chain & Procurement** (2,401), **Agile & Scrum** (2,058), **Financial Accounting & Audit (GAAP)** (1,741), **SQL** (1,423), **Regulatory Compliance** (1,242), **Python** (1,173), **ServiceNow & ITIL** (1,092), **ERP Systems (SAP / NetSuite / Workday)** (1,039), and **CRM Platforms (Salesforce / HubSpot)** (1,016).
   - **Fastest Rising Normalized Demand Share ($\ge$ 20 mentions):** **Looker** (`+58.54%`), **MLOps** (`+48.78%`), **Redis** (`+33.33%`), **Databricks** (`+17.71%`), **CAD & Industrial Automation** (`+12.31%`), **Kubernetes** (`+11.74%`), **TypeScript** (`+11.19%`), and **Talent Acquisition & HRIS** (`+10.50%`).
4. **Top Co-Occurring Pairs:** **Excel + Financial Accounting (GAAP)** (662 postings), **Excel + Supply Chain** (553), **CI/CD & Git + Agile & Scrum** (479), **Python + SQL** (455), and **SQL + Agile & Scrum** (415).
5. **Salary Key Influencers (5-Fold CV Random Forest, $R^2 = 0.3344$, MAE $= \$31{,}757$, $n = 12{,}979$):** **Seniority Level** (`57.22%` importance, `+$61,500` senior vs. entry median delta), **Job Role Specialization** (`20.89%`, `+$34,650` role IQR), **Python** (`3.95%`, `+$57,350`), **GCP** (`3.19%`, `+$65,038`), **Remote Eligibility** (`2.56%`, `+$31,200`), **Machine Learning** (`1.71%`, `+$72,127`), **AWS** (`1.71%`, `+$62,426`), and **Networking & Infrastructure** (`1.19%`, `+$32,750`).
6. **6-Year Historical Developer & Compensation Trajectories (2020–2025):**
   - **Stack Overflow Developer Cohorts (`424,980` total respondents across 2020–2025):** Multi-year adoption gains ($\ge 1.0\%$ 2020 baseline) led by **Bash / Shell** (`29.44%` $\rightarrow$ `37.03%`, `+7.59 pp`), **Docker** (`29.24%` $\rightarrow$ `35.40%`, `+6.16 pp`), **TypeScript** (`22.62%` $\rightarrow$ `28.17%`, `+5.55 pp`), **Terraform & IaC** (`7.21%` $\rightarrow$ `12.34%`, `+5.13 pp`, `11.35%` CAGR), **Rust** (`4.54%` $\rightarrow$ `9.60%`, `+5.06 pp`, `16.16%` CAGR), and **Kubernetes** (`9.58%` $\rightarrow$ `14.22%`, `+4.64 pp`), plus damped Ridge projections for 2026–2027.
   - **Global AI/Tech Salary Evolution (`151,439` validated records across 2020–2025):** Overall median compensation rose from **\$79,833** (2020, $n=75$, `48.0%` remote) and **\$83,872** (2021, $n=218$, `53.2%` remote) to **\$131,300** (2022, $n=1{,}661$, `53.4%` remote), **\$145,000** (2023, $n=8{,}524$, `31.4%` remote), **\$148,932** (2024, $n=62{,}239$, `19.1%` remote), and **\$145,100** (2025, $n=78{,}722$, `20.3%` remote).

---

## 6. Known Limitations & Environmental Notes
1. **Posting Window vs. Historical Macro Window:** The LinkedIn Bronze file (`job_postings.csv`) captures **33,246** employer job postings from **June–November 2023** (`15,481` Wave 1 vs. `16,913` Wave 2), whereas genuine 6-year multi-year history (**2020–2025**) is supplied by the six annual **Stack Overflow Developer Surveys** (`424,980` developers) and the **`ai-jobs.net` Global Salaries dataset** (`151,439` compensation records).
2. **Survey Structure Changes Across Years:** Stack Overflow adjusted option names and multi-select sections slightly across 2020–2025 (for instance, AI model adoption questions began in 2023, and overall response completion rates vary by year), so 5-year comparisons (`comparable_2020_2025 = 1`) explicitly require a $\ge 1.0\%$ 2020 baseline.
3. **Incomplete Salary Disclosure (`40.07%` in LinkedIn Postings):** Missing salaries are kept as `NULL` rather than imputed; salary medians and Random Forest training (`n = 12,979`) reflect disclosed-salary postings only.
4. **Rule-Based NLP Engine & Local Runtime:** `spaCy` and `psycopg2` are not installed in this Windows Python environment, so the NLP pipeline uses compiled Python regex token/n-gram matching + context rules (`nlp/skill_extractor.py`), and the local database runtime uses **MySQL 8.0** (`warehouse/load_mysql.py`) alongside full **PostgreSQL + PostGIS** scripts (`warehouse/schema_postgres_postgis.sql`, `warehouse/load_postgres.py`).
