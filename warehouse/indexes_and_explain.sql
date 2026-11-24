-- ============================================================================
-- SkillScope: Indexing & R-Tree Spatial Query Benchmark (EXPLAIN ANALYZE)
-- Course: Data Warehousing & Business Intelligence (DWBI)
-- Purpose: Verify B-Tree, Composite B-Tree, FULLTEXT, and Spatial R-Tree Indexes
-- ============================================================================

USE skillscope_dw;

-- ============================================================================
-- 1. VERIFY EXISTING INDEXES IN THE WAREHOUSE
-- ============================================================================
SELECT
    TABLE_NAME,
    INDEX_NAME,
    INDEX_TYPE,
    GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX) AS INDEX_COLUMNS
FROM INFORMATION_SCHEMA.STATISTICS
WHERE TABLE_SCHEMA = 'skillscope_dw'
GROUP BY TABLE_NAME, INDEX_NAME, INDEX_TYPE
ORDER BY TABLE_NAME, INDEX_NAME;

-- ============================================================================
-- 2. BENCHMARK 1: SPATIAL R-TREE INDEX ON dim_location(geom)
--    Query: Find all cities and job postings within a bounding box (e.g., US West Coast / Bay Area)
-- ============================================================================

-- A. Query ignoring Spatial R-Tree Index (Full Table Scan on dim_location)
EXPLAIN ANALYZE
SELECT
    l.city,
    l.region,
    COUNT(f.posting_key) AS total_postings
FROM dim_location l IGNORE INDEX (sp_idx_location_geom)
JOIN fact_job_posting f ON f.location_key = l.location_key
WHERE MBRContains(
    ST_GeomFromText('POLYGON((-125.0 32.0, -114.0 32.0, -114.0 42.5, -125.0 42.5, -125.0 32.0))'),
    l.geom
)
GROUP BY l.city, l.region;

-- B. Same Query USING the Spatial R-Tree Index (sp_idx_location_geom)
EXPLAIN ANALYZE
SELECT
    l.city,
    l.region,
    COUNT(f.posting_key) AS total_postings
FROM dim_location l FORCE INDEX (sp_idx_location_geom)
JOIN fact_job_posting f ON f.location_key = l.location_key
WHERE MBRContains(
    ST_GeomFromText('POLYGON((-125.0 32.0, -114.0 32.0, -114.0 42.5, -125.0 42.5, -125.0 32.0))'),
    l.geom
)
GROUP BY l.city, l.region;

-- ============================================================================
-- 3. BENCHMARK 2: COMPOSITE B-TREE INDEX ON fact_posting_skill(skill_key, posting_key)
--    Query: Count monthly demand and average salary for top skills by role
-- ============================================================================

-- A. Query ignoring Composite Index (idx_fps_skill_posting)
EXPLAIN ANALYZE
SELECT
    sk.skill_name,
    d.`year_month`,
    COUNT(fps.posting_key) AS demand_count,
    AVG(f.salary_annual_usd) AS avg_salary_usd
FROM fact_posting_skill fps IGNORE INDEX (idx_fps_skill_posting)
JOIN dim_skill sk ON fps.skill_key = sk.skill_key
JOIN fact_job_posting f ON fps.posting_key = f.posting_key
JOIN dim_date d ON f.date_key = d.date_key
WHERE fps.skill_key IN (1, 2, 3, 4, 5)
GROUP BY sk.skill_name, d.`year_month`;

-- B. Same Query USING Composite Index (idx_fps_skill_posting)
EXPLAIN ANALYZE
SELECT
    sk.skill_name,
    d.`year_month`,
    COUNT(fps.posting_key) AS demand_count,
    AVG(f.salary_annual_usd) AS avg_salary_usd
FROM fact_posting_skill fps FORCE INDEX (idx_fps_skill_posting)
JOIN dim_skill sk ON fps.skill_key = sk.skill_key
JOIN fact_job_posting f ON fps.posting_key = f.posting_key
JOIN dim_date d ON f.date_key = d.date_key
WHERE fps.skill_key IN (1, 2, 3, 4, 5)
GROUP BY sk.skill_name, d.`year_month`;

-- ============================================================================
-- 4. BENCHMARK 3: FULLTEXT INDEX ON dim_skill(skill_name) & dim_role(role_title_norm)
-- ============================================================================
EXPLAIN ANALYZE
SELECT skill_key, skill_name, taxonomy_id
FROM dim_skill
WHERE MATCH(skill_name) AGAINST('+Python +Machine +Learning' IN BOOLEAN MODE);
