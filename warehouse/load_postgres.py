"""
SkillScope PostgreSQL + PostGIS Data Warehouse Loader & GiST R-Tree Benchmark Runner
Course: Data Warehousing & Business Intelligence (DWBI)

Features:
1. Executes `warehouse/schema_postgres_postgis.sql` (Staging, 4 Snowflaked Outriggers,
   7 Star Dimensions with PostGIS GEOMETRY(Point, 4326), 5 Constellation Facts/Bridges,
   B-Tree/Composite/BRIN/GIN(pg_trgm)/GiST(R-Tree) indexes, and Demand/Skills Mart views).
2. Loads Gold Parquet tables using idempotent `ON CONFLICT (...) DO UPDATE` upserts.
3. Demonstrates SCD Type 1 & Type 2 handling and runs `EXPLAIN ANALYZE` benchmarks.
"""

import json
import os
import sys
import time
from typing import List

import pandas as pd

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    psycopg2 = None
    execute_values = None

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLD_DIR = os.path.join(PROJECT_ROOT, "data", "gold")
SCHEMA_PG_PATH = os.path.join(PROJECT_ROOT, "warehouse", "schema_postgres_postgis.sql")


def clean_nan(df: pd.DataFrame) -> List[tuple]:
    df_obj = df.astype(object).where(pd.notnull(df), None)
    return [tuple(x) for x in df_obj.to_numpy()]


def upsert_postgres(conn, tbl: str, cols: List[str], pk_cols: List[str], df: pd.DataFrame, batch_size: int = 5000):
    col_list = ", ".join(cols)
    pk_list = ", ".join(pk_cols)
    non_pk = [c for c in cols if c not in pk_cols]
    if non_pk:
        update_clause = ", ".join([f"{c} = EXCLUDED.{c}" for c in non_pk])
        conflict = f"ON CONFLICT ({pk_list}) DO UPDATE SET {update_clause}"
    else:
        conflict = f"ON CONFLICT ({pk_list}) DO NOTHING"

    sql = f"INSERT INTO {tbl} ({col_list}) VALUES %s {conflict}"
    rows = clean_nan(df[cols])
    with conn.cursor() as cur:
        for i in range(0, len(rows), batch_size):
            execute_values(cur, sql, rows[i : i + batch_size], page_size=batch_size)
    conn.commit()


def load_postgres_warehouse(
    host: str = None,
    port: int = None,
    dbname: str = None,
    user: str = None,
    password: str = None,
):
    if psycopg2 is None:
        raise RuntimeError(
            "psycopg2 is not installed in this environment. Install via `pip install psycopg2-binary` "
            "and ensure PostgreSQL + PostGIS is running before executing `load_postgres.py`."
        )

    t0 = time.time()
    conn = psycopg2.connect(
        host=host or os.environ.get("PGHOST", "127.0.0.1"),
        port=port or int(os.environ.get("PGPORT", "5432")),
        dbname=dbname or os.environ.get("PGDATABASE", "skillscope_dw"),
        user=user or os.environ.get("PGUSER", "postgres"),
        password=password or os.environ.get("PGPASSWORD", ""),
    )

    with open(SCHEMA_PG_PATH, "r", encoding="utf-8") as f:
        ddl = f.read()
    with conn.cursor() as cur:
        cur.execute(ddl)
    conn.commit()
    print("[PostgreSQL] Executed PostGIS schema, indexes, and Data Mart views.")

    # 1. Snowflaked Outriggers
    for tbl, cols, pks in [
        ("dim_industry", ["industry_key", "industry_name", "sector"], ["industry_key"]),
        ("dim_country", ["country_key", "country_name", "iso_code", "region_group", "currency_code"], ["country_key"]),
        ("dim_role_family", ["role_family_key", "family_name", "domain_area"], ["role_family_key"]),
        ("dim_skill_category", ["category_key", "category_name", "parent_category"], ["category_key"]),
    ]:
        df = pd.read_parquet(os.path.join(GOLD_DIR, f"{tbl}.parquet"))
        upsert_postgres(conn, tbl, cols, pks, df)
        print(f"  -> Loaded `{tbl}` ({len(df):,} rows)")

    # 2. Star Dimensions (bool cast for PG)
    for tbl, cols, pks in [
        ("dim_date", ["date_key", "full_date", "day_of_month", "month_num", "month_name", "year_month", "quarter_num", "quarter_label", "year_num", "is_weekend", "is_holiday"], ["date_key"]),
        ("dim_company", ["company_key", "company_name", "size_band", "industry_key", "effective_from", "effective_to", "is_current"], ["company_key"]),
        ("dim_role", ["role_key", "role_title_norm", "role_family_key", "min_experience"], ["role_key"]),
        ("dim_seniority", ["seniority_key", "level_name", "min_years", "max_years", "seniority_rank"], ["seniority_key"]),
        ("dim_source", ["source_key", "source_name", "platform_url", "collected_on"], ["source_key"]),
        ("dim_skill", ["skill_key", "skill_name", "taxonomy_id", "skill_type", "category_key", "is_emerging", "esco_occupation_count", "version_num", "is_current"], ["skill_key"]),
    ]:
        df = pd.read_parquet(os.path.join(GOLD_DIR, f"{tbl}.parquet"))
        for bcol in ["is_weekend", "is_holiday", "is_current", "is_emerging"]:
            if bcol in df.columns:
                df[bcol] = df[bcol].astype(bool)
        upsert_postgres(conn, tbl, cols, pks, df)
        print(f"  -> Loaded `{tbl}` ({len(df):,} rows)")

    # Spatial dim_location with PostGIS ST_SetSRID(ST_MakePoint(lon, lat), 4326)
    df_loc = pd.read_parquet(os.path.join(GOLD_DIR, "dim_location.parquet"))
    loc_rows = clean_nan(df_loc[["location_key", "city", "region", "country_key", "latitude", "longitude", "population", "longitude", "latitude"]])
    sql_loc = """
        INSERT INTO dim_location (location_key, city, region, country_key, latitude, longitude, population, geom)
        VALUES %s
        ON CONFLICT (location_key) DO UPDATE SET
            city = EXCLUDED.city, region = EXCLUDED.region, geom = EXCLUDED.geom
    """
    with conn.cursor() as cur:
        execute_values(
            cur,
            sql_loc,
            loc_rows,
            template="(%s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))",
            page_size=2000,
        )
    conn.commit()
    print(f"  -> Loaded PostGIS spatial dimension `dim_location` ({len(df_loc):,} rows)")

    # 3. Facts & Bridges
    for tbl, cols, pks in [
        ("fact_job_posting", ["posting_key", "natural_posting_id", "date_key", "company_key", "location_key", "role_key", "seniority_key", "source_key", "raw_job_title", "work_type", "salary_min_usd", "salary_max_usd", "salary_annual_usd", "is_remote", "posting_count"], ["posting_key"]),
        ("fact_posting_skill", ["posting_key", "skill_key", "mention_count", "confidence", "extraction_method"], ["posting_key", "skill_key"]),
        ("fact_survey_response", ["response_key", "date_key", "role_key", "country_key", "seniority_key", "source_key", "salary_usd", "experience_years", "reported_skills_csv"], ["response_key"]),
        ("fact_survey_skill", ["response_key", "skill_key"], ["response_key", "skill_key"]),
        ("fact_skill_gap_result", ["gap_key", "profile_id", "profile_label", "role_key", "skill_key", "demand_pct", "salary_premium_pct", "cooccurrence_proximity", "fuzzy_priority_level", "gap_score", "priority_rank", "role_match_score", "rationale"], ["gap_key"]),
        ("fact_historical_skill_trend", ["trend_key", "date_key", "year_num", "skill_key", "source_key", "respondent_count", "year_total_respondents", "adoption_pct", "median_salary_usd", "salary_sample_count", "yoy_adoption_change_pp", "yoy_growth_pct"], ["trend_key"]),
        ("fact_historical_salary_benchmark", ["benchmark_key", "date_key", "year_num", "role_key", "seniority_key", "country_key", "source_key", "work_mode", "record_count", "median_salary_usd", "mean_salary_usd", "p25_salary_usd", "p75_salary_usd"], ["benchmark_key"]),
    ]:
        df = pd.read_parquet(os.path.join(GOLD_DIR, f"{tbl}.parquet"))
        upsert_postgres(conn, tbl, cols, pks, df, batch_size=5000)
        print(f"  -> Loaded `{tbl}` ({len(df):,} rows)")

    # 4. Run PostGIS EXPLAIN ANALYZE Benchmarks
    benchmarks = {}
    with conn.cursor() as cur:
        cur.execute("ANALYZE;")
        cur.execute("SET enable_indexscan = off; SET enable_bitmapscan = off;")
        cur.execute("""
            EXPLAIN ANALYZE
            SELECT l.city, COUNT(f.posting_key)
            FROM dim_location l
            JOIN fact_job_posting f ON f.location_key = l.location_key
            WHERE l.geom && ST_MakeEnvelope(-125.0, 32.0, -114.0, 42.5, 4326)
            GROUP BY l.city
        """)
        benchmarks["gist_rtree_disabled"] = "\n".join(r[0] for r in cur.fetchall())

        cur.execute("SET enable_indexscan = on; SET enable_bitmapscan = on;")
        cur.execute("""
            EXPLAIN ANALYZE
            SELECT l.city, COUNT(f.posting_key)
            FROM dim_location l
            JOIN fact_job_posting f ON f.location_key = l.location_key
            WHERE l.geom && ST_MakeEnvelope(-125.0, 32.0, -114.0, 42.5, 4326)
            GROUP BY l.city
        """)
        benchmarks["gist_rtree_enabled"] = "\n".join(r[0] for r in cur.fetchall())

    with open(os.path.join(GOLD_DIR, "postgres_explain_benchmarks.json"), "w", encoding="utf-8") as f:
        json.dump(benchmarks, f, indent=2)

    conn.close()
    print(f"[PostgreSQL] Warehouse load & EXPLAIN ANALYZE completed in {time.time() - t0:.1f}s!")


if __name__ == "__main__":
    load_postgres_warehouse()
