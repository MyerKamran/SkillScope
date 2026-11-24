-- ============================================================================
-- SkillScope: Job Market & Skill-Gap Intelligence Warehouse (PostgreSQL + PostGIS)
-- Courses: Data Warehousing & Business Intelligence (DWBI) + Data Analytics & Visualization (DAV)
-- Architecture: Staging + Constellation (Galaxy) Schema with 4 Fact Tables & Snowflaked Dimensions
-- Includes: B-Tree, Composite B-Tree, BRIN, GIN (pg_trgm), PostGIS GiST (R-Tree), & 2 Data Mart Views
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================================
-- 0. STAGING LAYER TABLES (Exact raw landing copies with load metadata)
-- ============================================================================
CREATE TABLE IF NOT EXISTS stg_job_postings (
    stg_id BIGSERIAL PRIMARY KEY,
    raw_posting_id VARCHAR(64),
    title VARCHAR(500),
    company_name VARCHAR(255),
    industry_name VARCHAR(255),
    company_size VARCHAR(100),
    location_raw VARCHAR(255),
    work_type VARCHAR(100),
    experience_level VARCHAR(100),
    min_salary VARCHAR(100),
    max_salary VARCHAR(100),
    pay_period VARCHAR(50),
    currency VARCHAR(20),
    listed_time VARCHAR(100),
    skills_desc TEXT,
    description TEXT,
    source_name VARCHAR(100),
    file_name VARCHAR(255),
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stg_survey_responses (
    stg_id BIGSERIAL PRIMARY KEY,
    raw_response_id VARCHAR(64),
    survey_year INT,
    country VARCHAR(255),
    dev_type VARCHAR(255),
    years_code_pro VARCHAR(50),
    comp_total VARCHAR(100),
    currency VARCHAR(50),
    language_worked_with TEXT,
    database_worked_with TEXT,
    platform_worked_with TEXT,
    webframe_worked_with TEXT,
    source_name VARCHAR(100),
    file_name VARCHAR(255),
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stg_esco_skills (
    stg_id BIGSERIAL PRIMARY KEY,
    concept_uri VARCHAR(255),
    preferred_label VARCHAR(255),
    alt_labels TEXT,
    skill_type VARCHAR(100),
    category_name VARCHAR(255),
    parent_category VARCHAR(255),
    source_name VARCHAR(100),
    file_name VARCHAR(255),
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 1. SNOWFLAKED SUB-DIMENSIONS
-- ============================================================================
CREATE TABLE IF NOT EXISTS dim_industry (
    industry_key INT PRIMARY KEY,
    industry_name VARCHAR(255) NOT NULL UNIQUE,
    sector VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_country (
    country_key INT PRIMARY KEY,
    country_name VARCHAR(150) NOT NULL UNIQUE,
    iso_code VARCHAR(10) NOT NULL,
    region_group VARCHAR(100) NOT NULL,
    currency_code VARCHAR(10) NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_role_family (
    role_family_key INT PRIMARY KEY,
    family_name VARCHAR(150) NOT NULL UNIQUE,
    domain_area VARCHAR(150) NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_skill_category (
    category_key INT PRIMARY KEY,
    category_name VARCHAR(150) NOT NULL UNIQUE,
    parent_category VARCHAR(150) NOT NULL
);

-- ============================================================================
-- 2. STAR DIMENSIONS (Conformed Dimensions with SCD Type 1 & Type 2)
-- ============================================================================
CREATE TABLE IF NOT EXISTS dim_date (
    date_key INT PRIMARY KEY,
    full_date DATE NOT NULL,
    day_of_month SMALLINT NOT NULL,
    month_num SMALLINT NOT NULL,
    month_name VARCHAR(20) NOT NULL,
    year_month VARCHAR(7) NOT NULL,
    quarter_num SMALLINT NOT NULL,
    quarter_label VARCHAR(10) NOT NULL,
    year_num SMALLINT NOT NULL,
    is_weekend BOOLEAN NOT NULL DEFAULT FALSE,
    is_holiday BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS dim_company (
    company_key INT PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,
    size_band VARCHAR(100) NOT NULL,
    industry_key INT NOT NULL REFERENCES dim_industry(industry_key),
    effective_from DATE NOT NULL DEFAULT '2020-01-01',
    effective_to DATE NOT NULL DEFAULT '9999-12-31',
    is_current BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS dim_location (
    location_key INT PRIMARY KEY,
    city VARCHAR(150) NOT NULL,
    region VARCHAR(150) NOT NULL,
    country_key INT NOT NULL REFERENCES dim_country(country_key),
    latitude NUMERIC(9,6) NOT NULL,
    longitude NUMERIC(9,6) NOT NULL,
    population INT NOT NULL DEFAULT 0,
    geom GEOMETRY(Point, 4326) NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_role (
    role_key INT PRIMARY KEY,
    role_title_norm VARCHAR(200) NOT NULL,
    role_family_key INT NOT NULL REFERENCES dim_role_family(role_family_key),
    min_experience SMALLINT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS dim_seniority (
    seniority_key INT PRIMARY KEY,
    level_name VARCHAR(100) NOT NULL,
    min_years SMALLINT NOT NULL,
    max_years SMALLINT NOT NULL,
    seniority_rank SMALLINT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_source (
    source_key INT PRIMARY KEY,
    source_name VARCHAR(150) NOT NULL,
    platform_url VARCHAR(255) NOT NULL,
    collected_on DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_skill (
    skill_key INT PRIMARY KEY,
    skill_name VARCHAR(150) NOT NULL UNIQUE,
    taxonomy_id VARCHAR(255) NOT NULL,
    skill_type VARCHAR(50) NOT NULL,
    category_key INT NOT NULL REFERENCES dim_skill_category(category_key),
    is_emerging BOOLEAN NOT NULL DEFAULT FALSE,
    esco_occupation_count INT NOT NULL DEFAULT 0,
    version_num INT NOT NULL DEFAULT 1,
    is_current BOOLEAN NOT NULL DEFAULT TRUE
);

-- ============================================================================
-- 3. CONSTELLATION FACT TABLES
-- ============================================================================
CREATE TABLE IF NOT EXISTS fact_job_posting (
    posting_key BIGINT PRIMARY KEY,
    natural_posting_id VARCHAR(64) NOT NULL,
    date_key INT NOT NULL REFERENCES dim_date(date_key),
    company_key INT NOT NULL REFERENCES dim_company(company_key),
    location_key INT NOT NULL REFERENCES dim_location(location_key),
    role_key INT NOT NULL REFERENCES dim_role(role_key),
    seniority_key INT NOT NULL REFERENCES dim_seniority(seniority_key),
    source_key INT NOT NULL REFERENCES dim_source(source_key),
    raw_job_title VARCHAR(300) NOT NULL,
    work_type VARCHAR(50) NOT NULL,
    salary_min_usd NUMERIC(12,2) NULL,
    salary_max_usd NUMERIC(12,2) NULL,
    salary_annual_usd NUMERIC(12,2) NULL,
    is_remote SMALLINT NOT NULL DEFAULT 0,
    posting_count SMALLINT NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS fact_posting_skill (
    posting_key BIGINT NOT NULL REFERENCES fact_job_posting(posting_key),
    skill_key INT NOT NULL REFERENCES dim_skill(skill_key),
    mention_count SMALLINT NOT NULL DEFAULT 1,
    confidence NUMERIC(4,3) NOT NULL DEFAULT 1.000,
    extraction_method VARCHAR(50) NOT NULL DEFAULT 'ESCO_NLP_Rule',
    PRIMARY KEY (posting_key, skill_key)
);

CREATE TABLE IF NOT EXISTS fact_survey_response (
    response_key BIGINT PRIMARY KEY,
    date_key INT NOT NULL REFERENCES dim_date(date_key),
    role_key INT NOT NULL REFERENCES dim_role(role_key),
    country_key INT NOT NULL REFERENCES dim_country(country_key),
    seniority_key INT NOT NULL REFERENCES dim_seniority(seniority_key),
    source_key INT NOT NULL REFERENCES dim_source(source_key),
    salary_usd NUMERIC(12,2) NULL,
    experience_years NUMERIC(4,1) NULL,
    reported_skills_csv TEXT
);

CREATE TABLE IF NOT EXISTS fact_survey_skill (
    response_key BIGINT NOT NULL REFERENCES fact_survey_response(response_key),
    skill_key INT NOT NULL REFERENCES dim_skill(skill_key),
    PRIMARY KEY (response_key, skill_key)
);

CREATE TABLE IF NOT EXISTS fact_skill_gap_result (
    gap_key BIGSERIAL PRIMARY KEY,
    profile_id VARCHAR(100) NOT NULL,
    profile_label VARCHAR(255) NOT NULL,
    role_key INT NOT NULL REFERENCES dim_role(role_key),
    skill_key INT NOT NULL REFERENCES dim_skill(skill_key),
    demand_pct NUMERIC(6,2) NOT NULL,
    salary_premium_pct NUMERIC(6,2) NOT NULL,
    cooccurrence_proximity NUMERIC(6,3) NOT NULL,
    fuzzy_priority_level VARCHAR(20) NOT NULL,
    gap_score NUMERIC(6,2) NOT NULL,
    priority_rank INT NOT NULL,
    role_match_score NUMERIC(6,2) NOT NULL,
    rationale VARCHAR(500) NULL,
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fact_historical_skill_trend (
    trend_key INT PRIMARY KEY,
    date_key INT NOT NULL REFERENCES dim_date(date_key),
    year_num SMALLINT NOT NULL,
    skill_key INT NOT NULL REFERENCES dim_skill(skill_key),
    source_key INT NOT NULL REFERENCES dim_source(source_key),
    respondent_count INT NOT NULL,
    year_total_respondents INT NOT NULL,
    adoption_pct NUMERIC(6,2) NOT NULL,
    median_salary_usd NUMERIC(12,2) NULL,
    salary_sample_count INT NOT NULL DEFAULT 0,
    yoy_adoption_change_pp NUMERIC(6,2) NULL,
    yoy_growth_pct NUMERIC(7,2) NULL
);

CREATE TABLE IF NOT EXISTS fact_historical_salary_benchmark (
    benchmark_key INT PRIMARY KEY,
    date_key INT NOT NULL REFERENCES dim_date(date_key),
    year_num SMALLINT NOT NULL,
    role_key INT NOT NULL REFERENCES dim_role(role_key),
    seniority_key INT NOT NULL REFERENCES dim_seniority(seniority_key),
    country_key INT NOT NULL REFERENCES dim_country(country_key),
    source_key INT NOT NULL REFERENCES dim_source(source_key),
    work_mode VARCHAR(30) NOT NULL,
    record_count INT NOT NULL,
    median_salary_usd NUMERIC(12,2) NOT NULL,
    mean_salary_usd NUMERIC(12,2) NOT NULL,
    p25_salary_usd NUMERIC(12,2) NOT NULL,
    p75_salary_usd NUMERIC(12,2) NOT NULL
);

-- ============================================================================
-- 4. INDEXING SUITE (B-Tree, Composite B-Tree, BRIN, GIN Trigram, GiST R-Tree)
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_fjp_date ON fact_job_posting USING btree (date_key);
CREATE INDEX IF NOT EXISTS idx_fjp_company ON fact_job_posting USING btree (company_key);
CREATE INDEX IF NOT EXISTS idx_fjp_location ON fact_job_posting USING btree (location_key);
CREATE INDEX IF NOT EXISTS idx_fjp_role ON fact_job_posting USING btree (role_key);
CREATE INDEX IF NOT EXISTS idx_fjp_seniority ON fact_job_posting USING btree (seniority_key);

CREATE INDEX IF NOT EXISTS idx_fps_skill_posting ON fact_posting_skill USING btree (skill_key, posting_key);
CREATE INDEX IF NOT EXISTS idx_fjp_date_role ON fact_job_posting USING btree (date_key, role_key);
CREATE INDEX IF NOT EXISTS idx_fss_skill ON fact_survey_skill USING btree (skill_key, response_key);
CREATE INDEX IF NOT EXISTS idx_fhst_year_skill ON fact_historical_skill_trend USING btree (year_num, skill_key);
CREATE INDEX IF NOT EXISTS idx_fhsb_year_role_sen ON fact_historical_salary_benchmark USING btree (year_num, role_key, seniority_key);

CREATE INDEX IF NOT EXISTS brin_fjp_date ON fact_job_posting USING brin (date_key);

CREATE INDEX IF NOT EXISTS gin_role_title_trgm ON dim_role USING gin (role_title_norm gin_trgm_ops);
CREATE INDEX IF NOT EXISTS gin_skill_name_trgm ON dim_skill USING gin (skill_name gin_trgm_ops);

CREATE INDEX IF NOT EXISTS gist_rtree_location_geom ON dim_location USING gist (geom);

-- ============================================================================
-- 5. DATA MARTS (Demand Mart & Skills Mart Views)
-- ============================================================================
CREATE OR REPLACE VIEW mart_demand AS
SELECT
    f.posting_key,
    f.natural_posting_id,
    f.raw_job_title,
    d.full_date AS posting_date,
    d.year_num,
    d.month_num,
    d.month_name,
    d.year_month,
    d.quarter_label,
    r.role_key,
    r.role_title_norm,
    rf.role_family_key,
    rf.family_name AS role_family,
    rf.domain_area,
    s.seniority_key,
    s.level_name AS seniority_level,
    s.seniority_rank,
    c.company_key,
    c.company_name,
    c.size_band AS company_size,
    i.industry_name,
    i.sector,
    l.location_key,
    l.city,
    l.region,
    l.latitude,
    l.longitude,
    co.country_key,
    co.country_name,
    co.iso_code,
    co.region_group,
    f.work_type,
    f.is_remote,
    f.salary_min_usd,
    f.salary_max_usd,
    f.salary_annual_usd,
    f.posting_count
FROM fact_job_posting f
JOIN dim_date d ON f.date_key = d.date_key
JOIN dim_role r ON f.role_key = r.role_key
JOIN dim_role_family rf ON r.role_family_key = rf.role_family_key
JOIN dim_seniority s ON f.seniority_key = s.seniority_key
JOIN dim_company c ON f.company_key = c.company_key
JOIN dim_industry i ON c.industry_key = i.industry_key
JOIN dim_location l ON f.location_key = l.location_key
JOIN dim_country co ON l.country_key = co.country_key;

CREATE OR REPLACE VIEW mart_skills AS
SELECT
    fps.posting_key,
    fps.skill_key,
    sk.skill_name,
    sk.taxonomy_id AS esco_uri,
    sk.skill_type,
    sk.is_emerging,
    sc.category_key,
    sc.category_name AS skill_category,
    sc.parent_category,
    fps.mention_count,
    fps.confidence,
    d.full_date AS posting_date,
    d.year_num,
    d.month_num,
    d.year_month,
    r.role_key,
    r.role_title_norm,
    rf.family_name AS role_family,
    s.level_name AS seniority_level,
    co.country_name,
    co.region_group,
    f.work_type,
    f.is_remote,
    f.salary_annual_usd
FROM fact_posting_skill fps
JOIN dim_skill sk ON fps.skill_key = sk.skill_key
JOIN dim_skill_category sc ON sk.category_key = sc.category_key
JOIN fact_job_posting f ON fps.posting_key = f.posting_key
JOIN dim_date d ON f.date_key = d.date_key
JOIN dim_role r ON f.role_key = r.role_key
JOIN dim_role_family rf ON r.role_family_key = rf.role_family_key
JOIN dim_seniority s ON f.seniority_key = s.seniority_key
JOIN dim_location l ON f.location_key = l.location_key
JOIN dim_country co ON l.country_key = co.country_key;
