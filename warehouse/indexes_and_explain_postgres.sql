-- ============================================================================
-- SkillScope: PostgreSQL + PostGIS Indexing & R-Tree EXPLAIN ANALYZE Benchmarks
-- Course: Data Warehousing & Business Intelligence (DWBI)
-- Purpose: Verify B-Tree, Composite B-Tree, BRIN, GIN (pg_trgm), and GiST R-Tree
-- ============================================================================

-- 1. List all indexes in the public schema
SELECT
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;

-- 2. Benchmark 1: PostGIS GiST Spatial Index (R-Tree) on dim_location(geom)
--    Find all job postings within 100 km of San Francisco (-122.4194, 37.7749)
SET enable_indexscan = off;
SET enable_bitmapscan = off;
EXPLAIN ANALYZE
SELECT l.city, l.region, COUNT(f.posting_key) AS total_postings
FROM dim_location l
JOIN fact_job_posting f ON f.location_key = l.location_key
WHERE ST_DWithin(
    l.geom::geography,
    ST_SetSRID(ST_MakePoint(-122.4194, 37.7749), 4326)::geography,
    100000
)
GROUP BY l.city, l.region;

SET enable_indexscan = on;
SET enable_bitmapscan = on;
EXPLAIN ANALYZE
SELECT l.city, l.region, COUNT(f.posting_key) AS total_postings
FROM dim_location l
JOIN fact_job_posting f ON f.location_key = l.location_key
WHERE l.geom && ST_MakeEnvelope(-125.0, 32.0, -114.0, 42.5, 4326)
GROUP BY l.city, l.region;

-- 3. Benchmark 2: Composite B-Tree Index on fact_posting_skill(skill_key, posting_key)
EXPLAIN ANALYZE
SELECT sk.skill_name, d.year_month, COUNT(fps.posting_key) AS demand_count, AVG(f.salary_annual_usd) AS avg_salary_usd
FROM fact_posting_skill fps
JOIN dim_skill sk ON fps.skill_key = sk.skill_key
JOIN fact_job_posting f ON fps.posting_key = f.posting_key
JOIN dim_date d ON f.date_key = d.date_key
WHERE fps.skill_key IN (1, 2, 3, 27, 28)
GROUP BY sk.skill_name, d.year_month;

-- 4. Benchmark 3: BRIN Index on fact_job_posting(date_key)
EXPLAIN ANALYZE
SELECT role_key, COUNT(*) AS postings, AVG(salary_annual_usd) AS avg_sal
FROM fact_job_posting
WHERE date_key BETWEEN 20231001 AND 20231130
GROUP BY role_key;

-- 5. Benchmark 4: GIN Trigram Index on dim_skill(skill_name)
EXPLAIN ANALYZE
SELECT skill_key, skill_name, taxonomy_id
FROM dim_skill
WHERE skill_name ILIKE '%learning%';
