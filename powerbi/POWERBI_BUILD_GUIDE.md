# SkillScope: 7-Page Power BI Dashboard Build Guide
**Courses:** Data Analytics & Visualization (DAV) + Data Warehousing & Business Intelligence (DWBI)  
**Section:** BDS-5B | **Group:** 24K-2505, 24K-2521, 24K-2583

---

## 1. Connecting Power BI Desktop to the Warehouse / Gold Layer

You can connect Power BI Desktop using **any** of the following three methods:
1. **PostgreSQL + PostGIS Warehouse (Proposal Primary):**
   - Open Power BI Desktop $\rightarrow$ **Get Data** $\rightarrow$ **PostgreSQL database**
   - Server: `127.0.0.1:5432` | Database: `skillscope_dw` (loaded via `warehouse/load_postgres.py`)
2. **MySQL 8.0 Warehouse (Local Windows Runtime):**
   - Open Power BI Desktop $\rightarrow$ **Get Data** $\rightarrow$ **MySQL database**
   - Server: `127.0.0.1:3306` | Database: `skillscope_dw` (loaded via `warehouse/load_mysql.py`)
   - Select all `dim_*` tables, `fact_*` tables, and the two views (`mart_demand`, `mart_skills`).
3. **One-Click Gold CSV/Parquet Import (Zero-Latency):**
   - Open Power BI Desktop $\rightarrow$ **Get Data** $\rightarrow$ **Text/CSV** (or **Parquet**)
   - Browse to `c:\Users\PC\Desktop\SkillScope\data\powerbi_export\` (or `data\gold\`).

---

## 2. Model View: Star & Snowflake Schema Relationships

Set up the following relationships in Power BI's **Model View** (matches Figure 1 of your proposal):

### A. Fact Joins (1-to-Many from Dimension $\rightarrow$ Fact)
- `dim_date[date_key]` (1) $\longrightarrow$ (*) `fact_job_posting[date_key]`
- `dim_company[company_key]` (1) $\longrightarrow$ (*) `fact_job_posting[company_key]`
- `dim_location[location_key]` (1) $\longrightarrow$ (*) `fact_job_posting[location_key]`
- `dim_role[role_key]` (1) $\longrightarrow$ (*) `fact_job_posting[role_key]`
- `dim_seniority[seniority_key]` (1) $\longrightarrow$ (*) `fact_job_posting[seniority_key]`
- `dim_source[source_key]` (1) $\longrightarrow$ (*) `fact_job_posting[source_key]`

### B. Many-to-Many Bridge Fact (`fact_posting_skill`)
- `fact_job_posting[posting_key]` (1) $\longleftrightarrow$ (*) `fact_posting_skill[posting_key]` (**Cross-filter direction: Both**)
- `dim_skill[skill_key]` (1) $\longrightarrow$ (*) `fact_posting_skill[skill_key]`

### C. Snowflaked Outrigger Dimensions (1-to-Many)
- `dim_industry[industry_key]` (1) $\longrightarrow$ (*) `dim_company[industry_key]`
- `dim_country[country_key]` (1) $\longrightarrow$ (*) `dim_location[country_key]`
- `dim_role_family[role_family_key]` (1) $\longrightarrow$ (*) `dim_role[role_family_key]`
- `dim_skill_category[category_key]` (1) $\longrightarrow$ (*) `dim_skill[category_key]`

### D. Conformed Survey & AI Output Facts
- `dim_role[role_key]` (1) $\longrightarrow$ (*) `fact_survey_response[role_key]`
- `dim_country[country_key]` (1) $\longrightarrow$ (*) `fact_survey_response[country_key]`
- `dim_role[role_key]` (1) $\longrightarrow$ (*) `fact_skill_gap_result[role_key]`
- `dim_skill[skill_key]` (1) $\longrightarrow$ (*) `fact_skill_gap_result[skill_key]`

---

## 3. Page-by-Page Visual Mapping (All 7 Dashboard Pages)

| Page | Title | Visuals & Fields |
| :--- | :--- | :--- |
| **Page 1** | **Market Overview** | • **5 KPI Cards:** `[Total Job Postings]`, `[Median Annual Salary (USD)]`, `[Distinct Skills in Demand]`, `[Remote Share %]`, `[MoM Posting Growth %]`<br>• **Posting Trend Line:** X = `dim_date[year_month]`, Y = `[Total Job Postings]`<br>• **Map of Postings by Location:** Lat = `dim_location[latitude]`, Lon = `dim_location[longitude]`, Bubble Size = `[Total Job Postings]`, Legend = `dim_country[region_group]` |
| **Page 2** | **Skill Demand** | • **Ranked Bar Chart of Top Skills:** Y = `dim_skill[skill_name]`, X = `[Skill Demand %]`, Tooltip = `[Skill Mention Postings]`, `[Skill Rank by Demand]`<br>• **Treemap by Skill Category:** Category = `dim_skill_category[parent_category]`, Details = `dim_skill_category[category_name]`, Values = `[Skill Mention Postings]`<br>• **Slicers:** `dim_role_family[family_name]`, `dim_role[role_title_norm]`, `dim_country[country_name]` |
| **Page 3** | **Skill Trends** | • **Small-Multiple Line Charts:** X = `gold_monthly_skill_demand[year_month]`, Y = `demand_share_pct` (or `posting_mentions`), Small Multiples = `skill_name`, Legend = `record_type` (`Historical` vs `Forecast`)<br>• **Period Share Growth Table:** `gold_skill_yoy_growth[skill_name]`, `wave1_share_pct`, `wave2_share_pct`, `yoy_growth_pct` (Oct–Nov 2023 vs. Jun–Sep 2023) |
| **Page 4** | **Skill Relationships** | • **Skill Co-occurrence Matrix / Heatmap:** Rows = `gold_skill_cooccurrence[skill_name_a]`, Columns = `skill_name_b`, Values = `cooccurrence_strength` (or `co_posting_count`)<br>• **Key Influencers Visual for Salary:** Analyze `fact_job_posting[salary_annual_usd]` by `dim_seniority[level_name]`, `dim_role[role_title_norm]`, `fact_job_posting[is_remote]`, and `gold_salary_key_influencers` |
| **Page 5** | **Salary Insights** | • **Salary by Skill Bar Chart:** Y = `dim_skill[skill_name]`, X = `[Skill Median Salary (USD)]` & `[Skill Salary Premium (USD)]`<br>• **Salary by Role & Seniority Matrix:** Rows = `dim_role[role_title_norm]`, Columns = `dim_seniority[level_name]`, Values = `[Median Annual Salary (USD)]`<br>• **Box/Violin Salary Distribution by Country:** X = `dim_country[country_name]`, Y = `salary_annual_usd` |
| **Page 6** | **Survey vs. Market** | • **Clustered Bar / Dumbbell Chart:** Y = `gold_survey_vs_market[skill_name]`, X1 = `market_demand_pct` (Employer Request %), X2 = `survey_usage_pct` (Developer Usage %)<br>• **Supply-Demand Gap Scatter Plot:** X = `survey_usage_pct`, Y = `market_demand_pct`, Size = `market_median_salary_usd`, Category = `skill_name` |
| **Page 7** | **Skill-Gap Simulator** | • **Target Role Slicer (Single Select):** `dim_role[role_title_norm]` (or Persona Selector `fact_skill_gap_result[profile_label]`)<br>• **Multi-Select Learner Skills Slicer:** `Learner_Skills_Selector[Learner_Skill_Name]`<br>• **Match Score Gauge / KPI Card:** `[Role Match Score % (Live Simulator)]` / `fact_skill_gap_result[role_match_score]`<br>• **Ranked Missing Skills Table (with Fuzzy Priority):** `priority_rank`, `dim_skill[skill_name]`, `fuzzy_priority_level`, `gap_score`, `demand_pct`, `salary_premium_pct`, `cooccurrence_proximity` with **Drill-Through** to sample postings! |
