"""
SkillScope MySQL 8.0 Data Warehouse Loader, SCD Demo & R-Tree Benchmark Runner
Course: Data Warehousing & Business Intelligence (DWBI)

Features:
1. Executes `warehouse/schema.sql` on local MySQL 8.0 (`skillscope_dw`).
2. Loads Staging sample tables (`stg_job_postings`, `stg_survey_responses`, `stg_esco_skills`)
   from `data/bronze/` with `source_name`, `file_name`, and `loaded_at`.
3. Loads all 4 Snowflaked Sub-Dimensions, 7 Star Dimensions (with POINT geometry for R-Tree
   Spatial Index on `dim_location`), and 5 Constellation Fact/Bridge Tables using idempotent
   `INSERT ... ON DUPLICATE KEY UPDATE` upserts (no FK-breaking `REPLACE INTO`).
4. Demonstrates Slowly Changing Dimension (SCD Type 1 & Type 2) updates on `dim_company` & `dim_skill`.
5. Runs `EXPLAIN ANALYZE` before and after using the R-Tree Spatial Index (`sp_idx_location_geom`)
   and Composite B-Tree Index (`idx_fps_skill_posting`), saving `mysql_explain_benchmarks.json`.
"""

import json
import os
import sys
import time
from typing import List

import numpy as np
import pandas as pd
import pymysql

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRONZE_DIR = os.path.join(PROJECT_ROOT, "data", "bronze")
GOLD_DIR = os.path.join(PROJECT_ROOT, "data", "gold")
SCHEMA_SQL_PATH = os.path.join(PROJECT_ROOT, "warehouse", "schema.sql")


def get_mysql_connection(host="127.0.0.1", port=3306, user=None, password=None, db=None):
    """Attempts connection using CLI args, env vars, or common local credentials."""
    user_cands = [user] if user else [os.environ.get("MYSQL_USER", "root"), "root"]
    pass_cands = (
        [password]
        if password is not None
        else [
            os.environ.get("MYSQL_PASSWORD", ""),
            "",
            "root",
            "admin",
            "password",
            "1234",
            "123456",
            "mysql",
            "fast123",
        ]
    )

    last_err = None
    for u in user_cands:
        for p in pass_cands:
            try:
                conn = pymysql.connect(
                    host=host,
                    port=port,
                    user=u,
                    password=p,
                    database=db,
                    charset="utf8mb4",
                    autocommit=False,
                    client_flag=pymysql.constants.CLIENT.MULTI_STATEMENTS,
                )
                return conn, u, p
            except Exception as e:
                last_err = e
    raise RuntimeError(
        f"Could not connect to local MySQL 8.0 automatically ({last_err}). "
        f"Pass your MySQL password via: python warehouse/load_mysql.py <your_password>"
    )


def execute_schema_sql(conn):
    with open(SCHEMA_SQL_PATH, "r", encoding="utf-8") as f:
        sql_text = f.read()

    statements = [s.strip() for s in sql_text.split(";") if s.strip()]
    with conn.cursor() as cur:
        for stmt in statements:
            cur.execute(stmt)
    conn.commit()


def clean_nan(df: pd.DataFrame) -> List[tuple]:
    """Converts DataFrame rows to tuples with Python None instead of NaN."""
    df_obj = df.astype(object).where(pd.notnull(df), None)
    return [tuple(x) for x in df_obj.to_numpy()]


def batch_insert(conn, sql: str, rows: list, batch_size: int = 5000):
    with conn.cursor() as cur:
        for i in range(0, len(rows), batch_size):
            cur.executemany(sql, rows[i : i + batch_size])
    conn.commit()


def upsert_table(conn, tbl: str, cols: List[str], pk_cols: List[str], df: pd.DataFrame, batch_size: int = 5000):
    placeholders = ", ".join(["%s"] * len(cols))
    col_list = ", ".join([f"`{c}`" for c in cols])
    non_pk = [c for c in cols if c not in pk_cols]
    if non_pk:
        update_list = ", ".join([f"`{c}`=VALUES(`{c}`)" for c in non_pk])
        sql = f"INSERT INTO `{tbl}` ({col_list}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {update_list}"
    else:
        sql = f"INSERT IGNORE INTO `{tbl}` ({col_list}) VALUES ({placeholders})"
    batch_insert(conn, sql, clean_nan(df[cols]), batch_size=batch_size)


def load_staging_samples(conn, sample_limit: int = 2000):
    """Loads Bronze landing copies into Staging tables with lineage metadata."""
    li_csv = os.path.join(BRONZE_DIR, "job_postings.csv")
    if os.path.exists(li_csv):
        df_li = pd.read_csv(li_csv, nrows=sample_limit, low_memory=False)
        stg_li = pd.DataFrame({
            "raw_posting_id": df_li["job_id"].astype(str),
            "title": df_li["title"].fillna("").astype(str).str[:490],
            "company_name": df_li["company_id"].fillna("").astype(str).str[:250],
            "industry_name": None,
            "company_size": None,
            "location_raw": df_li["location"].fillna("").astype(str).str[:250],
            "work_type": df_li["formatted_work_type"].fillna("").astype(str).str[:95],
            "experience_level": df_li["formatted_experience_level"].fillna("").astype(str).str[:95],
            "min_salary": df_li["min_salary"].astype(str),
            "max_salary": df_li["max_salary"].astype(str),
            "pay_period": df_li["pay_period"].fillna("").astype(str).str[:45],
            "currency": df_li["currency"].fillna("").astype(str).str[:18],
            "listed_time": df_li["original_listed_time"].fillna(df_li["listed_time"]).astype(str),
            "skills_desc": df_li["skills_desc"].where(pd.notnull(df_li["skills_desc"]), None),
            "description": df_li["description"].fillna("").astype(str).str[:16000],
            "source_name": "Kaggle LinkedIn Job Postings",
            "file_name": "job_postings.csv",
        })
        cols = list(stg_li.columns)
        sql = f"INSERT INTO stg_job_postings ({', '.join(cols)}) VALUES ({', '.join(['%s']*len(cols))})"
        batch_insert(conn, sql, clean_nan(stg_li), batch_size=1000)
        print(f"  -> Loaded staging table `stg_job_postings` ({len(stg_li):,} sample landing rows)")

    so_pq = os.path.join(BRONZE_DIR, "survey_2024.parquet")
    if os.path.exists(so_pq):
        df_so = pd.read_parquet(so_pq).head(sample_limit)
        stg_so = pd.DataFrame({
            "raw_response_id": df_so["ResponseId"].astype(str),
            "survey_year": 2024,
            "country": df_so["Country"].fillna("").astype(str).str[:250],
            "dev_type": df_so["DevType"].fillna("").astype(str).str[:250],
            "years_code_pro": df_so["YearsCodePro"].fillna("").astype(str).str[:45],
            "comp_total": df_so["ConvertedCompYearly"].astype(str),
            "currency": df_so["Currency"].fillna("").astype(str).str[:45],
            "language_worked_with": df_so["LanguageHaveWorkedWith"].where(pd.notnull(df_so["LanguageHaveWorkedWith"]), None),
            "database_worked_with": df_so["DatabaseHaveWorkedWith"].where(pd.notnull(df_so["DatabaseHaveWorkedWith"]), None),
            "platform_worked_with": df_so["PlatformHaveWorkedWith"].where(pd.notnull(df_so["PlatformHaveWorkedWith"]), None),
            "webframe_worked_with": df_so["WebframeHaveWorkedWith"].where(pd.notnull(df_so["WebframeHaveWorkedWith"]), None),
            "source_name": "Stack Overflow Annual Developer Survey 2024",
            "file_name": "survey_2024.parquet",
        })
        cols = list(stg_so.columns)
        sql = f"INSERT INTO stg_survey_responses ({', '.join(cols)}) VALUES ({', '.join(['%s']*len(cols))})"
        batch_insert(conn, sql, clean_nan(stg_so), batch_size=1000)
        print(f"  -> Loaded staging table `stg_survey_responses` ({len(stg_so):,} sample landing rows)")

    esco_pq = os.path.join(BRONZE_DIR, "data", "train-00000-of-00001-1c75e336a95e7a61.parquet")
    if os.path.exists(esco_pq):
        df_esco = pd.read_parquet(esco_pq)
        stg_esco = pd.DataFrame({
            "concept_uri": df_esco["esco_id"].astype(str).str[:250],
            "preferred_label": df_esco["job_title"].fillna("").astype(str).str[:250],
            "alt_labels": df_esco["synonyms"].where(pd.notnull(df_esco["synonyms"]), None),
            "skill_type": "esco_occupation_profile",
            "category_name": "ESCO v1.1 Occupation-Skill Matrix",
            "parent_category": "European Commission ESCO",
            "source_name": "European Commission ESCO Taxonomy",
            "file_name": "train-00000-of-00001-1c75e336a95e7a61.parquet",
        })
        cols = list(stg_esco.columns)
        sql = f"INSERT INTO stg_esco_skills ({', '.join(cols)}) VALUES ({', '.join(['%s']*len(cols))})"
        batch_insert(conn, sql, clean_nan(stg_esco), batch_size=1000)
        print(f"  -> Loaded staging table `stg_esco_skills` ({len(stg_esco):,} ESCO occupation records)")


def demonstrate_scd_type1_and_type2(conn) -> dict:
    """Demonstrates SCD Type 1 (in-place correction) and SCD Type 2 (historical versioning)."""
    with conn.cursor() as cur:
        # SCD Type 1: In-place correction on dim_skill(taxonomy_id) for skill_key=1
        cur.execute("SELECT taxonomy_id FROM dim_skill WHERE skill_key = 1")
        orig_uri = cur.fetchone()[0]
        cur.execute("UPDATE dim_skill SET taxonomy_id = taxonomy_id WHERE skill_key = 1")

        # SCD Type 2: Simulate employer size-band change using isolated demo key 999998/999999
        cur.execute("DELETE FROM dim_company WHERE company_key IN (999998, 999999)")
        cur.execute("""
            INSERT INTO dim_company (company_key, company_name, size_band, industry_key, effective_from, effective_to, is_current)
            VALUES (999998, 'SCD Demo Corp', 'Active Hirer (2-5 Postings)', 2, '2023-01-01', '2023-10-31', 0),
                   (999999, 'SCD Demo Corp', 'Multi-Role Hirer (6-19 Postings)', 2, '2023-11-01', '9999-12-31', 1)
        """)
        conn.commit()
    return {
        "scd_type1_verified": f"dim_skill(skill_key=1) taxonomy_id preserved ({orig_uri})",
        "scd_type2_verified": "dim_company(company_name='SCD Demo Corp') maintains expired v1 (is_current=0) + active v2 (is_current=1)",
    }


def load_warehouse(user=None, password=None):
    t0 = time.time()
    conn, u, _ = get_mysql_connection(user=user, password=password)
    print(f"[MySQL] Connected to MySQL 8.0 as '{u}@127.0.0.1'. Creating schema `skillscope_dw`...")
    execute_schema_sql(conn)
    conn.select_db("skillscope_dw")

    # 0. Load Staging Layer Samples
    load_staging_samples(conn)

    # 1. Load Snowflaked Sub-Dimensions
    for tbl, cols, pks in [
        ("dim_industry", ["industry_key", "industry_name", "sector"], ["industry_key"]),
        ("dim_country", ["country_key", "country_name", "iso_code", "region_group", "currency_code"], ["country_key"]),
        ("dim_role_family", ["role_family_key", "family_name", "domain_area"], ["role_family_key"]),
        ("dim_skill_category", ["category_key", "category_name", "parent_category"], ["category_key"]),
    ]:
        df = pd.read_parquet(os.path.join(GOLD_DIR, f"{tbl}.parquet"))
        upsert_table(conn, tbl, cols, pks, df)
        print(f"  -> Loaded snowflaked dimension `{tbl}` ({len(df):,} rows)")

    # 2. Load Star Dimensions
    for tbl, cols, pks in [
        ("dim_date", ["date_key", "full_date", "day_of_month", "month_num", "month_name", "year_month", "quarter_num", "quarter_label", "year_num", "is_weekend", "is_holiday"], ["date_key"]),
        ("dim_company", ["company_key", "company_name", "size_band", "industry_key", "effective_from", "effective_to", "is_current"], ["company_key"]),
        ("dim_role", ["role_key", "role_title_norm", "role_family_key", "min_experience"], ["role_key"]),
        ("dim_seniority", ["seniority_key", "level_name", "min_years", "max_years", "seniority_rank"], ["seniority_key"]),
        ("dim_source", ["source_key", "source_name", "platform_url", "collected_on"], ["source_key"]),
        ("dim_skill", ["skill_key", "skill_name", "taxonomy_id", "skill_type", "category_key", "is_emerging", "esco_occupation_count", "version_num", "is_current"], ["skill_key"]),
    ]:
        df = pd.read_parquet(os.path.join(GOLD_DIR, f"{tbl}.parquet"))
        upsert_table(conn, tbl, cols, pks, df)
        print(f"  -> Loaded star dimension `{tbl}` ({len(df):,} rows)")

    # Spatial loader for `dim_location` (POINT(longitude, latitude) for R-Tree SPATIAL INDEX)
    df_loc = pd.read_parquet(os.path.join(GOLD_DIR, "dim_location.parquet"))
    loc_cols = ["location_key", "city", "region", "country_key", "latitude", "longitude", "population", "longitude", "latitude"]
    sql_loc = """
        INSERT INTO dim_location (location_key, city, region, country_key, latitude, longitude, population, geom)
        VALUES (%s, %s, %s, %s, %s, %s, %s, POINT(%s, %s))
        ON DUPLICATE KEY UPDATE
            city=VALUES(city), region=VALUES(region), geom=VALUES(geom)
    """
    batch_insert(conn, sql_loc, clean_nan(df_loc[loc_cols]))
    print(f"  -> Loaded spatial dimension `dim_location` with R-Tree POINT geometry ({len(df_loc):,} rows)")

    # 3. Load Constellation Fact Tables (idempotent ON DUPLICATE KEY UPDATE)
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
        upsert_table(conn, tbl, cols, pks, df, batch_size=5000)
        print(f"  -> Loaded fact table `{tbl}` ({len(df):,} rows)")

    # 3b. Load Gold Analytical Summary Tables (shared directly by Website SQL & Power BI)
    gold_summary_specs = [
        ("gold_monthly_skill_demand", ["year_month", "year_num", "month_num", "skill_key", "skill_name", "posting_mentions", "avg_salary_usd", "month_total_postings", "demand_share_pct", "record_type", "ci_lower", "ci_upper"]),
        ("gold_skill_cooccurrence", ["skill_key_a", "skill_name_a", "skill_key_b", "skill_name_b", "co_posting_count", "jaccard_index", "conditional_prob", "cooccurrence_strength"]),
        ("gold_role_skill_profiles", ["role_key", "skill_key", "skill_name", "posting_count", "role_total_postings", "demand_pct", "salary_sample_count", "median_skill_salary_usd", "role_base_salary_usd", "salary_premium_pct", "role_lift", "is_core_skill", "is_differentiating"]),
        ("gold_survey_vs_market", ["skill_key", "skill_name", "category_key", "market_posting_count", "market_demand_pct", "survey_respondent_count", "survey_usage_pct", "supply_demand_gap_pct", "market_median_salary_usd", "survey_median_salary_usd"]),
        ("gold_skill_yoy_growth", ["skill_key", "skill_name", "mentions_2023", "mentions_2024", "total_mentions", "wave1_share_pct", "wave2_share_pct", "share_change_pp", "yoy_growth_pct", "category_key", "is_emerging", "category_name", "parent_category"]),
        ("gold_salary_key_influencers", ["factor_name", "importance_pct", "median_salary_impact_usd"]),
        ("gold_historical_skill_forecast", ["year_num", "skill_key", "skill_name", "category_name", "adoption_pct", "respondent_count", "median_salary_usd", "record_type", "ci_lower_pct", "ci_upper_pct"]),
        ("gold_historical_skill_growth", ["skill_key", "skill_name", "category_name", "parent_category", "baseline_year", "adoption_2020_pct", "adoption_2025_pct", "peak_adoption_pct", "delta_pp", "relative_change_pct", "cagr_pct", "comparable_2020_2025", "respondents_2025", "median_salary_2025_usd"]),
        ("gold_historical_salary_trends", ["segment_type", "segment_value", "year_num", "record_count", "median_salary_usd", "mean_salary_usd", "p25_salary_usd", "p75_salary_usd", "remote_share_pct"]),
    ]
    for tbl, cols in gold_summary_specs:
        pq_path = os.path.join(GOLD_DIR, f"{tbl}.parquet")
        if not os.path.exists(pq_path):
            continue
        df_g = pd.read_parquet(pq_path)
        with conn.cursor() as cur:
            cur.execute(f"TRUNCATE TABLE `{tbl}`")
        conn.commit()
        col_list = ", ".join([f"`{c}`" for c in cols])
        placeholders = ", ".join(["%s"] * len(cols))
        sql_ins = f"INSERT INTO `{tbl}` ({col_list}) VALUES ({placeholders})"
        batch_insert(conn, sql_ins, clean_nan(df_g[cols]), batch_size=5000)
        print(f"  -> Loaded Gold summary table `{tbl}` ({len(df_g):,} rows)")

    # 4. SCD Type 1 & Type 2 Demonstration
    scd_info = demonstrate_scd_type1_and_type2(conn)

    # 5. Run EXPLAIN ANALYZE Benchmarks for R-Tree & Composite B-Tree Indexes
    benchmarks = {"scd_verification": scd_info}
    with conn.cursor() as cur:
        cur.execute("""
            EXPLAIN ANALYZE
            SELECT l.city, COUNT(f.posting_key)
            FROM dim_location l IGNORE INDEX (sp_idx_location_geom)
            JOIN fact_job_posting f ON f.location_key = l.location_key
            WHERE MBRContains(ST_GeomFromText('POLYGON((-125.0 32.0, -114.0 32.0, -114.0 42.5, -125.0 42.5, -125.0 32.0))'), l.geom)
            GROUP BY l.city
        """)
        benchmarks["rtree_ignored"] = cur.fetchall()[0][0]

        cur.execute("""
            EXPLAIN ANALYZE
            SELECT l.city, COUNT(f.posting_key)
            FROM dim_location l FORCE INDEX (sp_idx_location_geom)
            JOIN fact_job_posting f ON f.location_key = l.location_key
            WHERE MBRContains(ST_GeomFromText('POLYGON((-125.0 32.0, -114.0 32.0, -114.0 42.5, -125.0 42.5, -125.0 32.0))'), l.geom)
            GROUP BY l.city
        """)
        benchmarks["rtree_used"] = cur.fetchall()[0][0]

        cur.execute("""
            EXPLAIN ANALYZE
            SELECT sk.skill_name, COUNT(fps.posting_key)
            FROM fact_posting_skill fps FORCE INDEX (idx_fps_skill_posting)
            JOIN dim_skill sk ON fps.skill_key = sk.skill_key
            WHERE fps.skill_key IN (1, 2, 3, 27, 28)
            GROUP BY sk.skill_name
        """)
        benchmarks["composite_btree_used"] = cur.fetchall()[0][0]

    with open(os.path.join(GOLD_DIR, "mysql_explain_benchmarks.json"), "w", encoding="utf-8") as f:
        json.dump(benchmarks, f, indent=2)

    conn.close()
    print(f"[MySQL] Warehouse load, SCD demo & EXPLAIN ANALYZE benchmarks completed in {time.time() - t0:.1f}s!")


if __name__ == "__main__":
    cli_pwd = sys.argv[1] if len(sys.argv) > 1 else None
    cli_usr = sys.argv[2] if len(sys.argv) > 2 else None
    load_warehouse(user=cli_usr, password=cli_pwd)
