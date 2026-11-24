"""
SkillScope Interactive Web Studio, Live NLP Lab & MySQL 8.0 Backend Server
Courses: Data Analytics & Visualization (DAV) + Data Warehousing & Business Intelligence (DWBI)

Queries the local MySQL 8.0 Data Warehouse (`skillscope_dw`) directly via live SQL
(Star/Constellation fact + dimension tables, window functions & Gold summaries),
falling back automatically to Gold Parquet only when MySQL is unreachable.
"""

from decimal import Decimal
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import numpy as np
import pandas as pd
import pymysql

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ai.fuzzy_recommender import FuzzySkillGapRecommender
from etl.run_pipeline import map_title_to_role_key
from nlp.skill_extractor import ESCOSkillExtractor

BRONZE_DIR = os.path.join(PROJECT_ROOT, "data", "bronze")
GOLD_DIR = os.path.join(PROJECT_ROOT, "data", "gold")


def _coerce_val(v):
    if isinstance(v, Decimal):
        return float(v)
    return v


def _df_records(df: pd.DataFrame) -> list:
    if df is None or df.empty:
        return []
    return df.astype(object).where(pd.notnull(df), None).to_dict(orient="records")


def _connect_mysql(database="skillscope_dw"):
    return pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", "root"),
        password=os.environ.get("MYSQL_PASSWORD", "fast"),
        database=database,
        charset="utf8mb4",
        connect_timeout=4,
    )


def _query_df(conn, sql: str, params=None) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
    if not rows:
        return pd.DataFrame(columns=cols)
    cleaned = [tuple(_coerce_val(v) for v in row) for row in rows]
    return pd.DataFrame(cleaned, columns=cols)


class SkillScopeDataStore:
    def __init__(self):
        self.source_mode = "parquet_fallback"
        self.data_source_info = {
            "engine": "Gold Parquet (Fallback)",
            "database": "data/gold",
            "host": "local",
            "mode": "Parquet Fallback",
        }
        self.reload()

    def _try_mysql_init(self) -> bool:
        try:
            conn = _connect_mysql()
        except Exception as exc:
            self.data_source_info["reason"] = str(exc)
            return False

        try:
            with conn.cursor() as cur:
                cur.execute("SHOW TABLES LIKE 'gold_role_skill_profiles'")
                has_gold = cur.fetchone() is not None
                cur.execute("SHOW TABLES LIKE 'fact_job_posting'")
                has_fact = cur.fetchone() is not None
            if not (has_gold and has_fact):
                self.data_source_info["reason"] = "skillscope_dw missing Gold summary tables"
                return False

            self.dim_skill = _query_df(conn, "SELECT * FROM dim_skill ORDER BY skill_key")
            self.dim_cat = _query_df(conn, "SELECT * FROM dim_skill_category ORDER BY category_key")
            self.dim_role = _query_df(conn, "SELECT * FROM dim_role ORDER BY role_key")
            self.dim_rf = _query_df(conn, "SELECT * FROM dim_role_family ORDER BY role_family_key")
            self.dim_sen = _query_df(conn, "SELECT * FROM dim_seniority ORDER BY seniority_key")
            self.dim_country = _query_df(conn, "SELECT * FROM dim_country ORDER BY country_key")

            self.gold_profiles = _query_df(conn, "SELECT * FROM gold_role_skill_profiles")
            self.gold_cooc = _query_df(
                conn,
                "SELECT * FROM gold_skill_cooccurrence ORDER BY co_posting_count DESC",
            )
            self.gold_svm = _query_df(conn, "SELECT * FROM gold_survey_vs_market")

            self.source_mode = "mysql"
            self.data_source_info = {
                "engine": "MySQL 8.0",
                "database": "skillscope_dw",
                "host": f"{os.environ.get('MYSQL_HOST', '127.0.0.1')}:{os.environ.get('MYSQL_PORT', '3306')}",
                "mode": "Live SQL Queries",
            }
            return True
        except Exception as exc:
            self.data_source_info["reason"] = str(exc)
            return False
        finally:
            conn.close()

    def reload(self):
        loaded_mysql = self._try_mysql_init()

        if not loaded_mysql:
            self.source_mode = "parquet_fallback"
            self.dim_skill = pd.read_parquet(os.path.join(GOLD_DIR, "dim_skill.parquet"))
            self.dim_cat = pd.read_parquet(os.path.join(GOLD_DIR, "dim_skill_category.parquet"))
            self.dim_role = pd.read_parquet(os.path.join(GOLD_DIR, "dim_role.parquet"))
            self.dim_rf = pd.read_parquet(os.path.join(GOLD_DIR, "dim_role_family.parquet"))
            self.dim_sen = pd.read_parquet(os.path.join(GOLD_DIR, "dim_seniority.parquet"))
            self.dim_loc = pd.read_parquet(os.path.join(GOLD_DIR, "dim_location.parquet"))
            self.dim_country = pd.read_parquet(os.path.join(GOLD_DIR, "dim_country.parquet"))
            self.dim_date = pd.read_parquet(os.path.join(GOLD_DIR, "dim_date.parquet"))

            self.fact_post = pd.read_parquet(os.path.join(GOLD_DIR, "fact_job_posting.parquet"))
            self.fact_fps = pd.read_parquet(os.path.join(GOLD_DIR, "fact_posting_skill.parquet"))
            self.fact_survey = pd.read_parquet(os.path.join(GOLD_DIR, "fact_survey_response.parquet"))
            self.fact_gap = pd.read_parquet(os.path.join(GOLD_DIR, "fact_skill_gap_result.parquet"))

            self.gold_monthly = pd.read_parquet(os.path.join(GOLD_DIR, "gold_monthly_skill_demand.parquet"))
            self.gold_cooc = pd.read_parquet(os.path.join(GOLD_DIR, "gold_skill_cooccurrence.parquet"))
            self.gold_profiles = pd.read_parquet(os.path.join(GOLD_DIR, "gold_role_skill_profiles.parquet"))
            self.gold_svm = pd.read_parquet(os.path.join(GOLD_DIR, "gold_survey_vs_market.parquet"))

            yoy_path = os.path.join(GOLD_DIR, "gold_skill_yoy_growth.parquet")
            self.gold_yoy = pd.read_parquet(yoy_path) if os.path.exists(yoy_path) else pd.DataFrame()

            inf_path = os.path.join(GOLD_DIR, "gold_salary_key_influencers.parquet")
            self.gold_inf = pd.read_parquet(inf_path) if os.path.exists(inf_path) else pd.DataFrame()

            h_fcst_path = os.path.join(GOLD_DIR, "gold_historical_skill_forecast.parquet")
            self.gold_hist_fcst = pd.read_parquet(h_fcst_path) if os.path.exists(h_fcst_path) else pd.DataFrame()

            h_growth_path = os.path.join(GOLD_DIR, "gold_historical_skill_growth.parquet")
            self.gold_hist_growth = pd.read_parquet(h_growth_path) if os.path.exists(h_growth_path) else pd.DataFrame()

            h_sal_path = os.path.join(GOLD_DIR, "gold_historical_salary_trends.parquet")
            self.gold_hist_sal = pd.read_parquet(h_sal_path) if os.path.exists(h_sal_path) else pd.DataFrame()

        with open(os.path.join(GOLD_DIR, "nlp_evaluation_report.json"), "r", encoding="utf-8") as f:
            self.nlp_eval = json.load(f)

        eda_path = os.path.join(GOLD_DIR, "eda_summary_report.json")
        self.eda_summary = json.load(open(eda_path, "r", encoding="utf-8")) if os.path.exists(eda_path) else {}

        recon_path = os.path.join(GOLD_DIR, "etl_quality_reconciliation.json")
        self.etl_reconciliation = json.load(open(recon_path, "r", encoding="utf-8")) if os.path.exists(recon_path) else {}

        mysql_bm_path = os.path.join(GOLD_DIR, "mysql_explain_benchmarks.json")
        self.mysql_benchmarks = json.load(open(mysql_bm_path, "r", encoding="utf-8")) if os.path.exists(mysql_bm_path) else {}

        esco_parquet = os.path.join(BRONZE_DIR, "data", "train-00000-of-00001-1c75e336a95e7a61.parquet")
        self.extractor = ESCOSkillExtractor(esco_parquet_path=esco_parquet)

        self.recommender = FuzzySkillGapRecommender(
            role_skill_profiles_df=self.gold_profiles,
            cooccurrence_df=self.gold_cooc,
            skills_df=self.dim_skill,
            roles_df=self.dim_role,
        )

        self.role_name_by_key = dict(zip(self.dim_role["role_key"], self.dim_role["role_title_norm"]))
        self.svm_by_key = self.gold_svm.set_index("skill_key").to_dict(orient="index")
        self.nlp_sample_jds = self._load_sample_jds()

    def _load_sample_jds(self):
        return [
            {
                "label": "Staff Data Engineer (SaaS)",
                "title": "Staff Data Engineer (SaaS)",
                "description": (
                    "We are looking for a Staff Data Engineer to design and scale our Data Warehouse and "
                    "real-time ETL pipelines. Required skills: Python, SQL, Apache Spark, Airflow, dbt, "
                    "Snowflake or BigQuery, GCP or AWS, Terraform, Docker, Kubernetes, and Data Governance."
                ),
            },
            {
                "label": "Senior IT Security Engineer",
                "title": "Senior IT Security Engineer",
                "description": (
                    "Manage enterprise information security risk, SOC 2 and HIPAA compliance, penetration testing, "
                    "SIEM monitoring (Splunk, Datadog), IAM identity management, firewall/VPN security, Linux, "
                    "SAP ERP security audits, and Python scripting."
                ),
            },
            {
                "label": "SAP Procurement & BI Analyst",
                "title": "SAP Procurement Analyst with Power BI",
                "description": (
                    "Seeking an analyst with 3+ years of Power BI, DAX, Microsoft Excel (VLOOKUP, pivot tables), "
                    "SQL, SAP ERP (SAP MM), supply chain procurement analytics, and stakeholder presentation skills."
                ),
            },
            {
                "label": "Hard Negative: Hearing Care Provider",
                "title": "Hearing Care Provider",
                "description": (
                    "HearingLife is a national hearing care company. We live our Core Values: We Create <b>T</b>rust, "
                    "We are Team Players, We apply a Can-Do Attitude. Perform diagnostic hearing evaluations, fit "
                    "hearing aids, and counsel patients with empathy. Competitive compensation and benefits offered."
                ),
            },
        ]

    def _build_cooccurrence_matrix(self, sk_enriched: pd.DataFrame, dim_cat: pd.DataFrame, gold_cooc: pd.DataFrame):
        tech_cats = set(
            dim_cat[
                dim_cat["parent_category"].isin(
                    ["Software & Engineering", "Data & Analytics", "Cloud & DevOps", "Product & Design", "Engineering & Hardware"]
                )
            ]["category_key"].tolist()
        )
        top14_skills = (
            sk_enriched[sk_enriched["category_key"].isin(tech_cats)]
            .head(14)[["skill_key", "skill_name"]]
            .to_dict(orient="records")
        )
        t14_names = [x["skill_name"] for x in top14_skills]
        t14_keys = [int(x["skill_key"]) for x in top14_skills]

        cooc_map = {}
        for r in gold_cooc.itertuples(index=False):
            k1, k2 = int(r.skill_key_a), int(r.skill_key_b)
            cnt = int(r.co_posting_count)
            cooc_map[(k1, k2)] = cnt
            cooc_map[(k2, k1)] = cnt

        matrix_z = []
        for k1 in t14_keys:
            row_z = []
            for k2 in t14_keys:
                row_z.append(0 if k1 == k2 else cooc_map.get((k1, k2), 0))
            matrix_z.append(row_z)
        return t14_names, matrix_z

    def _build_payload_from_mysql(self) -> dict:
        conn = _connect_mysql()
        try:
            # 1. Overview monthly postings trend via SQL join across fact_job_posting + dim_date
            monthly_base = _query_df(
                conn,
                """
                SELECT d.`year_month`,
                       COUNT(f.posting_key) AS postings,
                       CAST(SUM(f.is_remote) AS SIGNED) AS remote_postings
                FROM fact_job_posting f
                JOIN dim_date d ON f.date_key = d.date_key
                GROUP BY d.`year_month`
                ORDER BY d.`year_month`
                """,
            )
            monthly_sal_raw = _query_df(
                conn,
                """
                SELECT d.`year_month`, f.salary_annual_usd
                FROM fact_job_posting f
                JOIN dim_date d ON f.date_key = d.date_key
                WHERE f.salary_annual_usd IS NOT NULL
                """,
            )
            med_by_ym = (
                monthly_sal_raw.groupby("year_month")["salary_annual_usd"].median().to_dict()
                if not monthly_sal_raw.empty
                else {}
            )
            monthly_base["median_salary"] = monthly_base["year_month"].map(med_by_ym)

            # 2. Top 90 Hiring Hub Bubbles via SQL Star Schema join
            loc_counts = _query_df(
                conn,
                """
                SELECT l.location_key,
                       l.city,
                       l.region,
                       l.country_key,
                       l.latitude,
                       l.longitude,
                       l.population,
                       co.country_name,
                       co.region_group,
                       COUNT(f.posting_key) AS postings
                FROM fact_job_posting f
                JOIN dim_location l ON f.location_key = l.location_key
                JOIN dim_country co ON l.country_key = co.country_key
                GROUP BY l.location_key, l.city, l.region, l.country_key,
                         l.latitude, l.longitude, l.population, co.country_name, co.region_group
                ORDER BY postings DESC
                LIMIT 90
                """,
            )
            if not loc_counts.empty:
                loc_keys_csv = ",".join(str(int(k)) for k in loc_counts["location_key"].tolist())
                loc_sal_raw = _query_df(
                    conn,
                    f"""
                    SELECT location_key, salary_annual_usd
                    FROM fact_job_posting
                    WHERE salary_annual_usd IS NOT NULL
                      AND location_key IN ({loc_keys_csv})
                    """,
                )
                med_by_loc = (
                    loc_sal_raw.groupby("location_key")["salary_annual_usd"].median().to_dict()
                    if not loc_sal_raw.empty
                    else {}
                )
                loc_counts["median_salary"] = loc_counts["location_key"].map(med_by_loc)
            else:
                loc_counts["median_salary"] = None

            # 3. Skills enriched with category & ESCO metadata via SQL join
            sk_enriched = _query_df(
                conn,
                """
                SELECT g.*,
                       s.is_emerging,
                       s.taxonomy_id,
                       s.esco_occupation_count,
                       c.category_name,
                       c.parent_category
                FROM gold_survey_vs_market g
                LEFT JOIN dim_skill s ON g.skill_key = s.skill_key
                LEFT JOIN dim_skill_category c ON g.category_key = c.category_key
                ORDER BY g.market_posting_count DESC
                """,
            )

            dim_cat = _query_df(conn, "SELECT * FROM dim_skill_category ORDER BY category_key")
            dim_rf = _query_df(conn, "SELECT * FROM dim_role_family ORDER BY role_family_key")
            gold_cooc = _query_df(conn, "SELECT * FROM gold_skill_cooccurrence ORDER BY co_posting_count DESC")
            gold_monthly = _query_df(conn, "SELECT * FROM gold_monthly_skill_demand ORDER BY `year_month`, skill_key")
            gold_yoy = _query_df(conn, "SELECT * FROM gold_skill_yoy_growth")
            gold_inf = _query_df(conn, "SELECT * FROM gold_salary_key_influencers ORDER BY importance_pct DESC")
            gold_hist_fcst = _query_df(conn, "SELECT * FROM gold_historical_skill_forecast ORDER BY year_num, skill_key")
            gold_hist_growth = _query_df(conn, "SELECT * FROM gold_historical_skill_growth ORDER BY respondents_2025 DESC")
            gold_hist_sal = _query_df(conn, "SELECT * FROM gold_historical_salary_trends ORDER BY segment_type, segment_value, year_num")
            gold_profiles = _query_df(conn, "SELECT * FROM gold_role_skill_profiles")

            # Sync in-memory references for /api/simulate and /api/nlp/extract
            self.dim_cat = dim_cat
            self.dim_rf = dim_rf
            self.gold_cooc = gold_cooc
            self.gold_profiles = gold_profiles
            self.gold_svm = sk_enriched
            self.svm_by_key = sk_enriched.set_index("skill_key").to_dict(orient="index")

            t14_names, matrix_z = self._build_cooccurrence_matrix(sk_enriched, dim_cat, gold_cooc)

            # 4. Role x Seniority Matrix & Role Salary Percentiles via SQL Star Join
            post_sal = _query_df(
                conn,
                """
                SELECT f.role_key,
                       r.role_title_norm,
                       f.seniority_key,
                       s.level_name,
                       s.seniority_rank,
                       f.salary_annual_usd
                FROM fact_job_posting f
                JOIN dim_role r ON f.role_key = r.role_key
                JOIN dim_seniority s ON f.seniority_key = s.seniority_key
                WHERE f.salary_annual_usd IS NOT NULL
                """,
            )
            rs_sal = (
                post_sal.groupby(["role_key", "role_title_norm", "seniority_key", "level_name", "seniority_rank"], as_index=False)[
                    "salary_annual_usd"
                ]
                .median()
                .sort_values(["role_key", "seniority_rank"])
            )

            role_box_stats = []
            for (rk, rname), grp in post_sal[post_sal["role_key"] != 17].groupby(["role_key", "role_title_norm"]):
                vals = grp["salary_annual_usd"].values
                if len(vals) >= 5:
                    role_box_stats.append({
                        "role_key": int(rk),
                        "role_name": rname,
                        "count": int(len(vals)),
                        "q10": round(float(np.percentile(vals, 10)), 0),
                        "q25": round(float(np.percentile(vals, 25)), 0),
                        "median": round(float(np.median(vals)), 0),
                        "q75": round(float(np.percentile(vals, 75)), 0),
                        "q90": round(float(np.percentile(vals, 90)), 0),
                    })
            role_box_stats.sort(key=lambda x: x["median"], reverse=True)

            # 5. Country Survey Compensation Percentiles via SQL Join
            so_sal = _query_df(
                conn,
                """
                SELECT co.country_name, fs.salary_usd
                FROM fact_survey_response fs
                JOIN dim_country co ON fs.country_key = co.country_key
                WHERE fs.salary_usd IS NOT NULL
                """,
            )
            country_box_stats = []
            for cname, grp in so_sal.groupby("country_name"):
                vals = grp["salary_usd"].values
                if len(vals) >= 15 and cname != "Global / Remote":
                    country_box_stats.append({
                        "country_name": cname,
                        "count": int(len(vals)),
                        "q10": round(float(np.percentile(vals, 10)), 0),
                        "q25": round(float(np.percentile(vals, 25)), 0),
                        "median": round(float(np.median(vals)), 0),
                        "q75": round(float(np.percentile(vals, 75)), 0),
                        "q90": round(float(np.percentile(vals, 90)), 0),
                    })
            country_box_stats.sort(key=lambda x: x["median"], reverse=True)

            # 6. Top 8 Drill-Through Postings per Skill using MySQL 8.0 Window Function CTE
            fps_sample = _query_df(
                conn,
                """
                WITH ranked AS (
                    SELECT fps.posting_key,
                           fps.skill_key,
                           fps.mention_count,
                           fps.confidence,
                           fps.extraction_method,
                           f.raw_job_title,
                           f.work_type,
                           f.salary_annual_usd,
                           f.role_key,
                           f.location_key,
                           l.city,
                           l.region,
                           ROW_NUMBER() OVER (PARTITION BY fps.skill_key ORDER BY fps.confidence DESC, fps.posting_key ASC) AS rn
                    FROM fact_posting_skill fps
                    JOIN fact_job_posting f ON fps.posting_key = f.posting_key
                    LEFT JOIN dim_location l ON f.location_key = l.location_key
                )
                SELECT posting_key, skill_key, mention_count, confidence, extraction_method,
                       raw_job_title, work_type, salary_annual_usd, role_key, location_key, city, region
                FROM ranked
                WHERE rn <= 8
                """,
            )

            # 7. Role Coverage Counts via SQL Join
            role_counts = _query_df(
                conn,
                """
                SELECT r.role_key,
                       r.role_title_norm,
                       r.role_family_key,
                       r.min_experience,
                       rf.family_name,
                       rf.domain_area,
                       COUNT(f.posting_key) AS postings
                FROM fact_job_posting f
                JOIN dim_role r ON f.role_key = r.role_key
                JOIN dim_role_family rf ON r.role_family_key = rf.role_family_key
                GROUP BY r.role_key, r.role_title_norm, r.role_family_key, r.min_experience, rf.family_name, rf.domain_area
                ORDER BY postings DESC
                """,
            )

            return {
                "data_source": self.data_source_info,
                "kpis": self.eda_summary.get("kpis", {}),
                "nlp_eval": {
                    "sample_size": self.nlp_eval["sample_size"],
                    "true_positives": self.nlp_eval.get("true_positives", 0),
                    "false_positives": self.nlp_eval.get("false_positives", 0),
                    "false_negatives": self.nlp_eval.get("false_negatives", 0),
                    "precision": self.nlp_eval["precision"],
                    "recall": self.nlp_eval["recall"],
                    "f1_score": self.nlp_eval["f1_score"],
                    "hard_negative_clean_rate": self.nlp_eval.get("hard_negative_clean_rate", 1.0),
                    "false_positive_examples": self.nlp_eval.get("false_positive_examples", []),
                    "false_negative_examples": self.nlp_eval.get("false_negative_examples", []),
                    "samples": self.nlp_eval.get("samples", [])[:20],
                },
                "nlp_sample_jds": self.nlp_sample_jds,
                "etl_reconciliation": self.etl_reconciliation,
                "mysql_benchmarks": self.mysql_benchmarks,
                "roles": _df_records(role_counts),
                "role_families": _df_records(dim_rf),
                "categories": _df_records(dim_cat),
                "skills": _df_records(sk_enriched),
                "monthly_postings": _df_records(monthly_base),
                "map_locations": _df_records(loc_counts),
                "skill_trends": _df_records(gold_monthly),
                "skill_yoy": _df_records(gold_yoy),
                "historical_years": [2020, 2021, 2022, 2023, 2024, 2025],
                "historical_survey_cohorts": self.eda_summary.get("historical_survey_cohorts", []),
                "historical_skill_forecast": _df_records(gold_hist_fcst),
                "historical_skill_growth": _df_records(gold_hist_growth),
                "historical_salary_trends": _df_records(gold_hist_sal),
                "cooccurrence": _df_records(gold_cooc.head(60)),
                "cooccurrence_matrix": {"skills": t14_names, "z": matrix_z},
                "key_influencers": _df_records(gold_inf),
                "role_seniority_salary": _df_records(rs_sal),
                "role_salary_distributions": role_box_stats[:16],
                "country_salary_distributions": country_box_stats[:14],
                "role_profiles": _df_records(gold_profiles),
                "sample_postings": _df_records(fps_sample),
            }
        finally:
            conn.close()

    def build_dashboard_payload(self):
        if self.source_mode == "mysql":
            try:
                return self._build_payload_from_mysql()
            except Exception as exc:
                print(f"[WARN] Live MySQL query failed ({exc}); falling back to Parquet...")
                self.data_source_info = {
                    "engine": "Gold Parquet (Fallback)",
                    "database": "data/gold",
                    "host": "local",
                    "mode": "Parquet Fallback",
                    "reason": str(exc),
                }
                self.source_mode = "parquet_fallback"
                self.reload()

        # Parquet Fallback Path (when local MySQL 8.0 is not installed/running)
        post_dt = self.fact_post.merge(self.dim_date[["date_key", "year_month"]], on="date_key", how="left")
        monthly_postings = (
            post_dt.groupby("year_month", as_index=False)
            .agg(
                postings=("posting_key", "count"),
                median_salary=("salary_annual_usd", "median"),
                remote_postings=("is_remote", "sum"),
            )
            .sort_values("year_month")
        )

        loc_agg = (
            self.fact_post.groupby("location_key", as_index=False)
            .agg(postings=("posting_key", "count"), median_salary=("salary_annual_usd", "median"))
            .merge(self.dim_loc, on="location_key", how="left")
            .merge(self.dim_country[["country_key", "country_name", "region_group"]], on="country_key", how="left")
            .sort_values("postings", ascending=False)
            .head(90)
        )

        sk_enriched = (
            self.gold_svm.merge(
                self.dim_skill[["skill_key", "is_emerging", "taxonomy_id", "esco_occupation_count"]],
                on="skill_key",
                how="left",
            )
            .merge(self.dim_cat, on="category_key", how="left")
            .sort_values("market_posting_count", ascending=False)
        )

        t14_names, matrix_z = self._build_cooccurrence_matrix(sk_enriched, self.dim_cat, self.gold_cooc)

        rs_sal = (
            self.fact_post.dropna(subset=["salary_annual_usd"])
            .groupby(["role_key", "seniority_key"], as_index=False)["salary_annual_usd"]
            .median()
            .merge(self.dim_role[["role_key", "role_title_norm"]], on="role_key")
            .merge(self.dim_sen[["seniority_key", "level_name", "seniority_rank"]], on="seniority_key")
            .sort_values(["role_key", "seniority_rank"])
        )

        sal_clean = self.fact_post.dropna(subset=["salary_annual_usd"]).merge(
            self.dim_role[["role_key", "role_title_norm"]], on="role_key"
        )
        role_box_stats = []
        for (rk, rname), grp in sal_clean[sal_clean["role_key"] != 17].groupby(["role_key", "role_title_norm"]):
            vals = grp["salary_annual_usd"].values
            if len(vals) >= 5:
                role_box_stats.append({
                    "role_key": int(rk),
                    "role_name": rname,
                    "count": int(len(vals)),
                    "q10": round(float(np.percentile(vals, 10)), 0),
                    "q25": round(float(np.percentile(vals, 25)), 0),
                    "median": round(float(np.median(vals)), 0),
                    "q75": round(float(np.percentile(vals, 75)), 0),
                    "q90": round(float(np.percentile(vals, 90)), 0),
                })
        role_box_stats.sort(key=lambda x: x["median"], reverse=True)

        so_sal = self.fact_survey.dropna(subset=["salary_usd"]).merge(
            self.dim_country[["country_key", "country_name"]], on="country_key"
        )
        country_box_stats = []
        for cname, grp in so_sal.groupby("country_name"):
            vals = grp["salary_usd"].values
            if len(vals) >= 15 and cname != "Global / Remote":
                country_box_stats.append({
                    "country_name": cname,
                    "count": int(len(vals)),
                    "q10": round(float(np.percentile(vals, 10)), 0),
                    "q25": round(float(np.percentile(vals, 25)), 0),
                    "median": round(float(np.median(vals)), 0),
                    "q75": round(float(np.percentile(vals, 75)), 0),
                    "q90": round(float(np.percentile(vals, 90)), 0),
                })
        country_box_stats.sort(key=lambda x: x["median"], reverse=True)

        fps_sample = (
            self.fact_fps.merge(
                self.fact_post[["posting_key", "raw_job_title", "work_type", "salary_annual_usd", "role_key", "location_key"]],
                on="posting_key",
            )
            .merge(self.dim_loc[["location_key", "city", "region"]], on="location_key", how="left")
            .sort_values("confidence", ascending=False)
            .groupby("skill_key")
            .head(8)
        )

        role_counts = (
            self.fact_post.groupby("role_key", as_index=False)["posting_key"]
            .count()
            .rename(columns={"posting_key": "postings"})
            .merge(self.dim_role.merge(self.dim_rf, on="role_family_key"), on="role_key")
            .sort_values("postings", ascending=False)
        )

        return {
            "data_source": self.data_source_info,
            "kpis": self.eda_summary.get("kpis", {}),
            "nlp_eval": {
                "sample_size": self.nlp_eval["sample_size"],
                "true_positives": self.nlp_eval.get("true_positives", 0),
                "false_positives": self.nlp_eval.get("false_positives", 0),
                "false_negatives": self.nlp_eval.get("false_negatives", 0),
                "precision": self.nlp_eval["precision"],
                "recall": self.nlp_eval["recall"],
                "f1_score": self.nlp_eval["f1_score"],
                "hard_negative_clean_rate": self.nlp_eval.get("hard_negative_clean_rate", 1.0),
                "false_positive_examples": self.nlp_eval.get("false_positive_examples", []),
                "false_negative_examples": self.nlp_eval.get("false_negative_examples", []),
                "samples": self.nlp_eval.get("samples", [])[:20],
            },
            "nlp_sample_jds": self.nlp_sample_jds,
            "etl_reconciliation": self.etl_reconciliation,
            "mysql_benchmarks": self.mysql_benchmarks,
            "roles": _df_records(role_counts),
            "role_families": _df_records(self.dim_rf),
            "categories": _df_records(self.dim_cat),
            "skills": _df_records(sk_enriched),
            "monthly_postings": _df_records(monthly_postings),
            "map_locations": _df_records(loc_agg),
            "skill_trends": _df_records(self.gold_monthly),
            "skill_yoy": _df_records(self.gold_yoy),
            "historical_years": [2020, 2021, 2022, 2023, 2024, 2025],
            "historical_survey_cohorts": self.eda_summary.get("historical_survey_cohorts", []),
            "historical_skill_forecast": _df_records(self.gold_hist_fcst),
            "historical_skill_growth": _df_records(self.gold_hist_growth),
            "historical_salary_trends": _df_records(self.gold_hist_sal),
            "cooccurrence": _df_records(self.gold_cooc.head(60)),
            "cooccurrence_matrix": {"skills": t14_names, "z": matrix_z},
            "key_influencers": _df_records(self.gold_inf),
            "role_seniority_salary": _df_records(rs_sal),
            "role_salary_distributions": role_box_stats[:16],
            "country_salary_distributions": country_box_stats[:14],
            "role_profiles": _df_records(self.gold_profiles),
            "sample_postings": _df_records(fps_sample),
        }

    def save_simulation_to_mysql(self, profile_id: str, profile_label: str, role_key: int, rec_df: pd.DataFrame) -> dict:
        """Persists live Mamdani fuzzy skill-gap results back into MySQL `skillscope_dw.fact_skill_gap_result`."""
        conn = _connect_mysql()
        conn.autocommit(False)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM fact_skill_gap_result WHERE profile_id = %s AND role_key = %s",
                    (profile_id, int(role_key)),
                )
                rows = []
                for r in rec_df.itertuples(index=False):
                    rows.append((
                        profile_id[:100],
                        profile_label[:255],
                        int(r.role_key),
                        int(r.skill_key),
                        float(r.demand_pct),
                        float(r.salary_premium_pct),
                        float(r.cooccurrence_proximity),
                        str(r.fuzzy_priority_level)[:20],
                        float(r.gap_score),
                        int(r.priority_rank),
                        float(r.role_match_score),
                        str(getattr(r, "rationale", ""))[:500],
                    ))
                cur.executemany(
                    """
                    INSERT INTO fact_skill_gap_result (
                        profile_id, profile_label, role_key, skill_key,
                        demand_pct, salary_premium_pct, cooccurrence_proximity,
                        fuzzy_priority_level, gap_score, priority_rank,
                        role_match_score, rationale
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    rows,
                )
            conn.commit()
            return {"status": "saved", "database": "skillscope_dw", "table": "fact_skill_gap_result", "rows_written": len(rows)}
        finally:
            conn.close()


STORE = None


class DashboardRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length > 0 else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_OPTIONS(self):
        self._send_json({"ok": True})

    def do_GET(self):
        global STORE
        parsed = urlparse(self.path)
        if parsed.path == "/api/data":
            self._send_json(STORE.build_dashboard_payload())
            return
        elif parsed.path == "/api/simulate":
            qs = parse_qs(parsed.query)
            role_key = int(qs.get("role_key", ["1"])[0])
            skills_str = qs.get("skills", [""])[0]
            known_keys = [int(x) for x in skills_str.split(",") if x.strip().isdigit()]

            match_score, rec_df = STORE.recommender.recommend_for_profile(
                profile_id="Live_Web_User",
                profile_label="Interactive Simulator Session",
                role_key=role_key,
                known_skill_keys=known_keys,
                top_n=15,
            )
            if not rec_df.empty:
                rec_df = rec_df.merge(
                    STORE.dim_skill[["skill_key", "skill_name", "taxonomy_id", "category_key"]],
                    on="skill_key",
                    how="left",
                ).merge(STORE.dim_cat, on="category_key", how="left")
                recs = _df_records(rec_df)
            else:
                recs = []

            self._send_json({
                "role_key": role_key,
                "known_skill_keys": known_keys,
                "role_match_score": match_score,
                "recommendations": recs,
            })
            return
        elif parsed.path == "/api/health":
            self._send_json({
                "status": "ok",
                "service": "SkillScope Python API",
                "next_ui": "http://127.0.0.1:3000/",
                "data_source": STORE.data_source_info,
            })
            return
        else:
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:3000/")
            self.send_header("Content-Length", "0")
            self.end_headers()

    def do_POST(self):
        global STORE
        parsed = urlparse(self.path)
        if parsed.path == "/api/nlp/extract":
            t0 = time.perf_counter()
            try:
                body = self._read_json_body()
                title = str(body.get("title", "") or "")
                description = str(body.get("description", "") or "")
                analysis = STORE.extractor.analyze_job_description(description, title)
                inferred_rk = map_title_to_role_key(title, analysis["cleaned_text"])
                inferred_rname = STORE.role_name_by_key.get(inferred_rk, "General / Other Professional Role")

                for sk in analysis["skills"]:
                    mkt = STORE.svm_by_key.get(sk["skill_key"], {})
                    med_sal = mkt.get("market_median_salary_usd")
                    sk["market_demand_pct"] = float(mkt.get("market_demand_pct") or 0.0)
                    sk["market_median_salary_usd"] = float(med_sal) if med_sal is not None and pd.notna(med_sal) else None

                elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
                self._send_json({
                    "status": "ok",
                    "inferred_role_key": inferred_rk,
                    "inferred_role_name": inferred_rname,
                    "processing_ms": elapsed_ms,
                    **analysis,
                })
            except Exception as e:
                self._send_json({"status": "error", "message": str(e)}, status=400)
            return

        elif parsed.path == "/api/simulate/save":
            try:
                body = self._read_json_body()
                profile_id = str(body.get("profile_id", "Live_Web_Session") or "Live_Web_Session").strip()
                profile_label = str(body.get("profile_label", "Interactive Web Studio Profile") or "Interactive Web Studio Profile").strip()
                role_key = int(body.get("role_key", 1))
                known_keys = [int(k) for k in body.get("skills", []) if str(k).isdigit()]

                match_score, rec_df = STORE.recommender.recommend_for_profile(
                    profile_id=profile_id,
                    profile_label=profile_label,
                    role_key=role_key,
                    known_skill_keys=known_keys,
                    top_n=12,
                )
                if rec_df.empty:
                    self._send_json({"status": "error", "message": "No skill gap rows generated for this role."}, status=400)
                    return

                res = STORE.save_simulation_to_mysql(profile_id, profile_label, role_key, rec_df)
                self._send_json({
                    **res,
                    "profile_id": profile_id,
                    "role_key": role_key,
                    "role_match_score": match_score,
                })
            except Exception as e:
                self._send_json({"status": "error", "message": str(e)}, status=500)
            return

        self._send_json({"status": "error", "message": "Endpoint not found"}, status=404)


def run_server(port: int = 8050):
    global STORE
    print("Initializing SkillScope Data Store (MySQL 8.0 primary + Parquet fallback)...")
    STORE = SkillScopeDataStore()
    print(f"Active Warehouse Source: {STORE.data_source_info}")
    server = HTTPServer(("127.0.0.1", port), DashboardRequestHandler)
    print(f"SkillScope Python API Backend running at: http://127.0.0.1:{port} (Next.js UI at http://127.0.0.1:3000)")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
