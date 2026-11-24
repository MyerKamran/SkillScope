# SkillScope: Job Market & Skill-Gap Intelligence Warehouse & BI Dashboard

**University:** National University of Computer & Emerging Sciences (FAST-NUCES), Karachi Campus  
**Section:** BDS-5B  
**Courses Covered:**
1. **Data Warehousing & Business Intelligence (DWBI):** Lakehouse Architecture (Bronze/Silver/Gold), Staging Tables, Constellation & Snowflake Schema (`schema_postgres_postgis.sql` for PostgreSQL + PostGIS and `schema.sql` for MySQL 8.0), R-Tree Spatial Index (PostGIS GiST / MySQL `SPATIAL INDEX` on `POINT` coordinates), Composite B-Tree, BRIN & GIN/FULLTEXT Indexing, `EXPLAIN ANALYZE` benchmarking, SCD Type 1/2 dimensions, Demand Mart & Skills Mart SQL views, and AI write-back table (`fact_skill_gap_result`).
2. **Data Analytics & Visualization (DAV):** Rule-based ESCO-aligned NLP Skill Extraction (86 canonical skills across 21 categories, 29 job roles across 10 families) with independent 100-posting Precision/Recall evaluation (`nlp/ground_truth_100.json`), Exploratory Data Analysis (EDA), Ridge-Damped 6-Month Skill Demand Forecasting, 5-Fold CV Random Forest Salary Key Influencers, Mamdani Fuzzy Logic Skill-Gap Recommender with explainability rationales, 7-Page Power BI Dashboard (`measures.dax` + `POWERBI_BUILD_GUIDE.md`), and the animated 8-Page **SkillScope Studio** (`frontend/app.py` with Live NLP Lab & MySQL Write-Back).

**Group Members:**
- `24K-2505` — Myer Kamran
- `24K-2521` — Shazil Ahmed
- `24K-2583` — Ali John Rajani

---

## Project Directory Structure

```text
SkillScope/
├── data/
│   ├── bronze/                 # Authentic raw datasets (LinkedIn 33,246 CSV, StackOverflow 2020-2025 424,980 Parquet, ai-jobs 2020-2025 151,445 CSV, ESCO 3,015 Parquet, GeoNames 34,216 cities)
│   ├── silver/                 # Cleaned Silver Parquet tables (postings, extracted skills, 2024 survey, historical SO & salaries, ESCO, GeoNames)
│   ├── gold/                   # Star/Snowflake Dimension & 7 Fact/Bridge Parquet tables + Gold Aggregates + JSON evaluation & reconciliation reports
│   └── powerbi_export/         # Ready-to-import CSV tables for Power BI Desktop
├── nlp/
│   ├── skill_extractor.py      # HTML cleaner + ESCO-aligned NLP skill extractor + context disambiguation + independent evaluator
│   └── ground_truth_100.json   # Independent human-audited 100-posting benchmark (75 tech/data + 25 non-tech hard negatives)
├── ai/
│   └── fuzzy_recommender.py    # Knowledge-based expert system with Mamdani Fuzzy Priority Scoring & explainability rationales
├── etl/
│   ├── fetch_historical_data.py # Idempotent Bronze downloader for Stack Overflow (2020-2025) & ai-jobs.net salaries (2020-2025)
│   └── run_pipeline.py         # End-to-end Bronze -> Silver -> Gold ETL, Quality Gate (50 checks) & AI write-back pipeline
├── analytics/
│   └── eda_and_forecast.py     # Authentic EDA, 6-Year (2020-2025) SO & Salary Forecasting, & 5-fold CV Random Forest Influencers
├── warehouse/
│   ├── schema_postgres_postgis.sql       # PostgreSQL + PostGIS DDL (Staging, 11 Dims, 7 Facts/Bridges, GiST/GIN/BRIN/B-Tree, Mart Views)
│   ├── indexes_and_explain_postgres.sql  # PostGIS GiST R-Tree, BRIN, GIN Trigram, & Composite B-Tree EXPLAIN ANALYZE benchmarks
│   ├── load_postgres.py                  # Idempotent PostgreSQL + PostGIS warehouse loader & benchmark runner
│   ├── schema.sql                        # MySQL 8.0 DDL (Staging, 11 Dims, 7 Facts/Bridges, R-Tree Spatial Index, Mart Views)
│   ├── indexes_and_explain.sql           # MySQL 8.0 B-Tree, Composite B-Tree, FULLTEXT & R-Tree EXPLAIN ANALYZE benchmarks
│   └── load_mysql.py                     # Automated MySQL 8.0 warehouse loader, SCD Type 1/2 demo & benchmark runner
├── powerbi/
│   ├── measures.dax            # DAX measures library for all 7 Power BI pages + Live Disconnected Simulator
│   └── POWERBI_BUILD_GUIDE.md  # Step-by-step Power BI Desktop relationship & visual configuration guide
├── frontend-next/
│   ├── app/                    # Next.js 15 + React App Router (RYTHM-inspired Warm Ivory / Editorial Blue / Coral UI)
│   └── components/             # Framer Motion primitives + Recharts interactive 5-view Career & Market Studio
└── frontend/
    └── app.py                  # Python Lakehouse, ESCO NLP, Fuzzy AI & MySQL 8.0 API Backend (port 8050)
```

---

## How to Run Everything

### 1. Run the Main Code (Historical Download + ETL + Silver/Gold Lakehouse + NLP Benchmark + EDA & Forecasting)
```powershell
python -u etl/fetch_historical_data.py
python -u etl/run_pipeline.py
python -u analytics/eda_and_forecast.py
```

### 2. Load the Data Warehouse & Run R-Tree `EXPLAIN ANALYZE` Benchmarks
**MySQL 8.0 (Local Windows Runtime):**
```powershell
$env:MYSQL_USER="root"
$env:MYSQL_PASSWORD="your_mysql_password"
python -u warehouse/load_mysql.py
```
**PostgreSQL + PostGIS (Proposal Target Engine, requires `psycopg2-binary` & PostGIS):**
```powershell
$env:PGHOST="127.0.0.1"
$env:PGDATABASE="skillscope_dw"
$env:PGUSER="postgres"
$env:PGPASSWORD="your_postgres_password"
python -u warehouse/load_postgres.py
```

### 3. Fresh Clone Setup & Launch (Next.js + React Studio)
Install Python and Node dependencies once after cloning (run from the repo root):
```powershell
pip install -r requirements.txt
npm install
npm run build
```
*(Or inside `frontend-next/`: `cd frontend-next && npm install && npm run build`.)*

*(Optional — only needed if re-running the full Bronze-to-Gold ETL from raw CSVs: extract `data/bronze/job_postings.zip` inside `data/bronze/` to restore `job_postings.csv`. The website and analytics run directly off `data/gold/` without extracting it.)*

Start the studio:
```powershell
.\start_studio.ps1
```
Then open **http://127.0.0.1:3000** in your browser (port `8050` runs the headless Python API backend and redirects `/` to `:3000`).
