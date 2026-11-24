-- ============================================================================
-- SkillScope: Job Market & Skill-Gap Intelligence Warehouse
-- Courses: Data Warehousing & Business Intelligence (DWBI) + Data Analytics & Visualization (DAV)
-- Database Engine: MySQL 8.0 (InnoDB + Spatial R-Tree Index + FULLTEXT + B-Tree)
-- Architecture: Constellation (Galaxy) Schema with 4 Fact Tables & Snowflaked Dimensions
-- ============================================================================

CREATE DATABASE IF NOT EXISTS skillscope_dw
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE skillscope_dw;

SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================================
-- 1. STAGING LAYER TABLES (Exact raw landing copies with metadata)
-- ============================================================================
DROP TABLE IF EXISTS stg_job_postings;
CREATE TABLE stg_job_postings (
    stg_id BIGINT AUTO_INCREMENT PRIMARY KEY,
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
    description LONGTEXT,
    source_name VARCHAR(100),
    file_name VARCHAR(255),
    loaded_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

DROP TABLE IF EXISTS stg_survey_responses;
CREATE TABLE stg_survey_responses (
    stg_id BIGINT AUTO_INCREMENT PRIMARY KEY,
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
    loaded_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

DROP TABLE IF EXISTS stg_esco_skills;
CREATE TABLE stg_esco_skills (
    stg_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    concept_uri VARCHAR(255),
    preferred_label VARCHAR(255),
    alt_labels TEXT,
    skill_type VARCHAR(100),
    category_name VARCHAR(255),
    parent_category VARCHAR(255),
    source_name VARCHAR(100),
    file_name VARCHAR(255),
    loaded_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ============================================================================
-- 2. SNOWFLAKED SUB-DIMENSIONS (Normalized Outriggers)
-- ============================================================================

DROP TABLE IF EXISTS dim_industry;
CREATE TABLE dim_industry (
    industry_key INT PRIMARY KEY,
    industry_name VARCHAR(255) NOT NULL,
    sector VARCHAR(255) NOT NULL,
    UNIQUE KEY uk_industry_name (industry_name)
) ENGINE=InnoDB;

DROP TABLE IF EXISTS dim_country;
CREATE TABLE dim_country (
    country_key INT PRIMARY KEY,
    country_name VARCHAR(150) NOT NULL,
    iso_code VARCHAR(10) NOT NULL,
    region_group VARCHAR(100) NOT NULL,
    currency_code VARCHAR(10) NOT NULL,
    UNIQUE KEY uk_country_name (country_name)
) ENGINE=InnoDB;

DROP TABLE IF EXISTS dim_role_family;
CREATE TABLE dim_role_family (
    role_family_key INT PRIMARY KEY,
    family_name VARCHAR(150) NOT NULL,
    domain_area VARCHAR(150) NOT NULL,
    UNIQUE KEY uk_family_name (family_name)
) ENGINE=InnoDB;

DROP TABLE IF EXISTS dim_skill_category;
CREATE TABLE dim_skill_category (
    category_key INT PRIMARY KEY,
    category_name VARCHAR(150) NOT NULL,
    parent_category VARCHAR(150) NOT NULL,
    UNIQUE KEY uk_category_name (category_name)
) ENGINE=InnoDB;

-- ============================================================================
-- 3. STAR DIMENSIONS (Conformed Dimensions with SCD Type 1 & Type 2 columns)
-- ============================================================================

DROP TABLE IF EXISTS dim_date;
CREATE TABLE dim_date (
    date_key INT PRIMARY KEY,               -- YYYYMMDD format (e.g., 20240115)
    full_date DATE NOT NULL,
    day_of_month TINYINT NOT NULL,
    month_num TINYINT NOT NULL,
    month_name VARCHAR(20) NOT NULL,
    `year_month` VARCHAR(7) NOT NULL,         -- YYYY-MM
    quarter_num TINYINT NOT NULL,
    quarter_label VARCHAR(10) NOT NULL,     -- Q1..Q4
    year_num SMALLINT NOT NULL,
    is_weekend TINYINT(1) NOT NULL DEFAULT 0,
    is_holiday TINYINT(1) NOT NULL DEFAULT 0,
    INDEX idx_date_ym (year_num, month_num)
) ENGINE=InnoDB;

DROP TABLE IF EXISTS dim_company;
CREATE TABLE dim_company (
    company_key INT PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,
    size_band VARCHAR(100) NOT NULL,
    industry_key INT NOT NULL,
    -- Slowly Changing Dimension (SCD Type 2) attributes
    effective_from DATE NOT NULL DEFAULT '2020-01-01',
    effective_to DATE NOT NULL DEFAULT '9999-12-31',
    is_current TINYINT(1) NOT NULL DEFAULT 1,
    CONSTRAINT fk_company_industry FOREIGN KEY (industry_key) REFERENCES dim_industry(industry_key),
    INDEX idx_company_industry (industry_key),
    INDEX idx_company_name (company_name)
) ENGINE=InnoDB;

DROP TABLE IF EXISTS dim_location;
CREATE TABLE dim_location (
    location_key INT PRIMARY KEY,
    city VARCHAR(150) NOT NULL,
    region VARCHAR(150) NOT NULL,
    country_key INT NOT NULL,
    latitude DECIMAL(9,6) NOT NULL,
    longitude DECIMAL(9,6) NOT NULL,
    population INT NOT NULL DEFAULT 0,
    -- Spatial point column for R-Tree Spatial Indexing (SRID 0 / Cartesian or 4326)
    geom POINT NOT NULL,
    CONSTRAINT fk_location_country FOREIGN KEY (country_key) REFERENCES dim_country(country_key),
    INDEX idx_location_country (country_key),
    INDEX idx_location_city (city),
    SPATIAL INDEX sp_idx_location_geom (geom)
) ENGINE=InnoDB;

DROP TABLE IF EXISTS dim_role;
CREATE TABLE dim_role (
    role_key INT PRIMARY KEY,
    role_title_norm VARCHAR(200) NOT NULL,
    role_family_key INT NOT NULL,
    min_experience TINYINT NOT NULL DEFAULT 0,
    CONSTRAINT fk_role_family FOREIGN KEY (role_family_key) REFERENCES dim_role_family(role_family_key),
    INDEX idx_role_family (role_family_key),
    FULLTEXT INDEX ft_idx_role_title (role_title_norm)
) ENGINE=InnoDB;

DROP TABLE IF EXISTS dim_seniority;
CREATE TABLE dim_seniority (
    seniority_key INT PRIMARY KEY,
    level_name VARCHAR(100) NOT NULL,
    min_years TINYINT NOT NULL,
    max_years TINYINT NOT NULL,
    seniority_rank TINYINT NOT NULL
) ENGINE=InnoDB;

DROP TABLE IF EXISTS dim_source;
CREATE TABLE dim_source (
    source_key INT PRIMARY KEY,
    source_name VARCHAR(150) NOT NULL,
    platform_url VARCHAR(255) NOT NULL,
    collected_on DATE NOT NULL
) ENGINE=InnoDB;

DROP TABLE IF EXISTS dim_skill;
CREATE TABLE dim_skill (
    skill_key INT PRIMARY KEY,
    skill_name VARCHAR(150) NOT NULL,
    taxonomy_id VARCHAR(255) NOT NULL,      -- ESCO URI / identifier
    skill_type VARCHAR(50) NOT NULL,        -- skill/competence vs knowledge
    category_key INT NOT NULL,
    is_emerging TINYINT(1) NOT NULL DEFAULT 0,
    esco_occupation_count INT NOT NULL DEFAULT 0,
    -- SCD Type 2 tracking
    version_num INT NOT NULL DEFAULT 1,
    is_current TINYINT(1) NOT NULL DEFAULT 1,
    CONSTRAINT fk_skill_category FOREIGN KEY (category_key) REFERENCES dim_skill_category(category_key),
    INDEX idx_skill_category (category_key),
    UNIQUE KEY uk_skill_name (skill_name),
    FULLTEXT INDEX ft_idx_skill_name (skill_name)
) ENGINE=InnoDB;

-- ============================================================================
-- 4. CONSTELLATION FACT TABLES (6 Fact Tables)
-- ============================================================================

-- Fact 1: Job Postings Fact (1 row per job posting)
DROP TABLE IF EXISTS fact_job_posting;
CREATE TABLE fact_job_posting (
    posting_key BIGINT PRIMARY KEY,
    natural_posting_id VARCHAR(64) NOT NULL,
    date_key INT NOT NULL,
    company_key INT NOT NULL,
    location_key INT NOT NULL,
    role_key INT NOT NULL,
    seniority_key INT NOT NULL,
    source_key INT NOT NULL,
    raw_job_title VARCHAR(300) NOT NULL,
    work_type VARCHAR(50) NOT NULL,
    salary_min_usd DECIMAL(12,2) NULL,
    salary_max_usd DECIMAL(12,2) NULL,
    salary_annual_usd DECIMAL(12,2) NULL,
    is_remote TINYINT(1) NOT NULL DEFAULT 0,
    posting_count TINYINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_fjp_date FOREIGN KEY (date_key) REFERENCES dim_date(date_key),
    CONSTRAINT fk_fjp_company FOREIGN KEY (company_key) REFERENCES dim_company(company_key),
    CONSTRAINT fk_fjp_location FOREIGN KEY (location_key) REFERENCES dim_location(location_key),
    CONSTRAINT fk_fjp_role FOREIGN KEY (role_key) REFERENCES dim_role(role_key),
    CONSTRAINT fk_fjp_seniority FOREIGN KEY (seniority_key) REFERENCES dim_seniority(seniority_key),
    CONSTRAINT fk_fjp_source FOREIGN KEY (source_key) REFERENCES dim_source(source_key),
    -- Foreign Key & Composite B-Tree Indexes for fast Star Joins & Time-Range Scans
    INDEX idx_fjp_date (date_key),
    INDEX idx_fjp_company (company_key),
    INDEX idx_fjp_location (location_key),
    INDEX idx_fjp_role (role_key),
    INDEX idx_fjp_seniority (seniority_key),
    INDEX idx_fjp_date_role (date_key, role_key),
    INDEX idx_fjp_role_salary (role_key, salary_annual_usd)
) ENGINE=InnoDB;

-- Fact 2: Bridge Fact for Many-to-Many Posting <-> Skill (1 row per posting and skill)
DROP TABLE IF EXISTS fact_posting_skill;
CREATE TABLE fact_posting_skill (
    posting_key BIGINT NOT NULL,
    skill_key INT NOT NULL,
    mention_count SMALLINT NOT NULL DEFAULT 1,
    confidence DECIMAL(4,3) NOT NULL DEFAULT 1.000,
    extraction_method VARCHAR(50) NOT NULL DEFAULT 'ESCO_NLP_Rule',
    PRIMARY KEY (posting_key, skill_key),
    -- Composite B-Tree index in reverse order (skill_key, posting_key) as specified in Proposal
    INDEX idx_fps_skill_posting (skill_key, posting_key),
    CONSTRAINT fk_fps_posting FOREIGN KEY (posting_key) REFERENCES fact_job_posting(posting_key),
    CONSTRAINT fk_fps_skill FOREIGN KEY (skill_key) REFERENCES dim_skill(skill_key)
) ENGINE=InnoDB;

-- Fact 3: Developer Survey Responses Fact (1 row per survey respondent)
DROP TABLE IF EXISTS fact_survey_response;
CREATE TABLE fact_survey_response (
    response_key BIGINT PRIMARY KEY,
    date_key INT NOT NULL,
    role_key INT NOT NULL,
    country_key INT NOT NULL,
    seniority_key INT NOT NULL,
    source_key INT NOT NULL,
    salary_usd DECIMAL(12,2) NULL,
    experience_years DECIMAL(4,1) NULL,
    reported_skills_csv TEXT,
    CONSTRAINT fk_fsr_date FOREIGN KEY (date_key) REFERENCES dim_date(date_key),
    CONSTRAINT fk_fsr_role FOREIGN KEY (role_key) REFERENCES dim_role(role_key),
    CONSTRAINT fk_fsr_country FOREIGN KEY (country_key) REFERENCES dim_country(country_key),
    CONSTRAINT fk_fsr_seniority FOREIGN KEY (seniority_key) REFERENCES dim_seniority(seniority_key),
    CONSTRAINT fk_fsr_source FOREIGN KEY (source_key) REFERENCES dim_source(source_key),
    INDEX idx_fsr_role (role_key),
    INDEX idx_fsr_country (country_key)
) ENGINE=InnoDB;

-- Bridge table for Survey Respondent <-> Skill (enables direct Survey vs Market skill queries)
DROP TABLE IF EXISTS fact_survey_skill;
CREATE TABLE fact_survey_skill (
    response_key BIGINT NOT NULL,
    skill_key INT NOT NULL,
    PRIMARY KEY (response_key, skill_key),
    INDEX idx_fss_skill (skill_key, response_key),
    CONSTRAINT fk_fss_response FOREIGN KEY (response_key) REFERENCES fact_survey_response(response_key),
    CONSTRAINT fk_fss_skill FOREIGN KEY (skill_key) REFERENCES dim_skill(skill_key)
) ENGINE=InnoDB;

-- Fact 4: AI Skill-Gap Recommender Output Fact (written back to warehouse)
DROP TABLE IF EXISTS fact_skill_gap_result;
CREATE TABLE fact_skill_gap_result (
    gap_key BIGINT AUTO_INCREMENT PRIMARY KEY,
    profile_id VARCHAR(100) NOT NULL,
    profile_label VARCHAR(255) NOT NULL,
    role_key INT NOT NULL,
    skill_key INT NOT NULL,
    demand_pct DECIMAL(6,2) NOT NULL,
    salary_premium_pct DECIMAL(6,2) NOT NULL,
    cooccurrence_proximity DECIMAL(6,3) NOT NULL,
    fuzzy_priority_level VARCHAR(20) NOT NULL,   -- Low, Medium, High, Very High
    gap_score DECIMAL(6,2) NOT NULL,             -- 0 to 100 fuzzy defuzzified score
    priority_rank INT NOT NULL,
    role_match_score DECIMAL(6,2) NOT NULL,      -- Overall learner match % for target role
    rationale VARCHAR(500) NULL,
    computed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_fsgr_role FOREIGN KEY (role_key) REFERENCES dim_role(role_key),
    CONSTRAINT fk_fsgr_skill FOREIGN KEY (skill_key) REFERENCES dim_skill(skill_key),
    INDEX idx_fsgr_profile_role (profile_id, role_key, priority_rank)
) ENGINE=InnoDB;

-- Fact 5: Multi-Year Historical Skill Adoption Trend Fact (2020-2025 Stack Overflow Cohorts)
DROP TABLE IF EXISTS fact_historical_skill_trend;
CREATE TABLE fact_historical_skill_trend (
    trend_key INT PRIMARY KEY,
    date_key INT NOT NULL,
    year_num SMALLINT NOT NULL,
    skill_key INT NOT NULL,
    source_key INT NOT NULL,
    respondent_count INT NOT NULL,
    year_total_respondents INT NOT NULL,
    adoption_pct DECIMAL(6,2) NOT NULL,
    median_salary_usd DECIMAL(12,2) NULL,
    salary_sample_count INT NOT NULL DEFAULT 0,
    yoy_adoption_change_pp DECIMAL(6,2) NULL,
    yoy_growth_pct DECIMAL(7,2) NULL,
    CONSTRAINT fk_fhst_date FOREIGN KEY (date_key) REFERENCES dim_date(date_key),
    CONSTRAINT fk_fhst_skill FOREIGN KEY (skill_key) REFERENCES dim_skill(skill_key),
    CONSTRAINT fk_fhst_source FOREIGN KEY (source_key) REFERENCES dim_source(source_key),
    INDEX idx_fhst_year_skill (year_num, skill_key),
    INDEX idx_fhst_skill_year (skill_key, year_num)
) ENGINE=InnoDB;

-- Fact 6: Multi-Year Global Salary Benchmark Fact (2020-2025 ai-jobs.net Records)
DROP TABLE IF EXISTS fact_historical_salary_benchmark;
CREATE TABLE fact_historical_salary_benchmark (
    benchmark_key INT PRIMARY KEY,
    date_key INT NOT NULL,
    year_num SMALLINT NOT NULL,
    role_key INT NOT NULL,
    seniority_key INT NOT NULL,
    country_key INT NOT NULL,
    source_key INT NOT NULL,
    work_mode VARCHAR(30) NOT NULL,
    record_count INT NOT NULL,
    median_salary_usd DECIMAL(12,2) NOT NULL,
    mean_salary_usd DECIMAL(12,2) NOT NULL,
    p25_salary_usd DECIMAL(12,2) NOT NULL,
    p75_salary_usd DECIMAL(12,2) NOT NULL,
    CONSTRAINT fk_fhsb_date FOREIGN KEY (date_key) REFERENCES dim_date(date_key),
    CONSTRAINT fk_fhsb_role FOREIGN KEY (role_key) REFERENCES dim_role(role_key),
    CONSTRAINT fk_fhsb_seniority FOREIGN KEY (seniority_key) REFERENCES dim_seniority(seniority_key),
    CONSTRAINT fk_fhsb_country FOREIGN KEY (country_key) REFERENCES dim_country(country_key),
    CONSTRAINT fk_fhsb_source FOREIGN KEY (source_key) REFERENCES dim_source(source_key),
    INDEX idx_fhsb_year_role_sen (year_num, role_key, seniority_key),
    INDEX idx_fhsb_country (country_key, year_num)
) ENGINE=InnoDB;

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================================
-- 5. DATA MARTS (Demand Mart & Skills Mart Views for Power BI & Analytics)
-- ============================================================================

-- Data Mart 1: Demand Mart (Postings, Roles, Regions, Seniority, Work Type, Trends)
CREATE OR REPLACE VIEW mart_demand AS
SELECT
    f.posting_key,
    f.natural_posting_id,
    f.raw_job_title,
    d.full_date AS posting_date,
    d.year_num,
    d.month_num,
    d.month_name,
    d.`year_month`,
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

-- Data Mart 2: Skills Mart (Skills, Categories, Demand by Role/Region, Salary per Skill)
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
    d.`year_month`,
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
