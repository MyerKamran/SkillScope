"""
SkillScope Interactive Web Studio, Live NLP Lab & MySQL Write-Back Server
Courses: Data Analytics & Visualization (DAV) + Data Warehousing & Business Intelligence (DWBI)

Serves the SkillScope Intelligence Studio on http://127.0.0.1:8050 backed directly
by the Gold Lakehouse, live ESCO NLP Extractor (`nlp/skill_extractor.py`),
Mamdani Fuzzy Recommender (`ai/fuzzy_recommender.py`), and MySQL 8.0 Write-Back.
"""

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


class SkillScopeDataStore:
    def __init__(self):
        self.reload()

    def reload(self):
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
        """Loads 4 diverse real job postings from Bronze for 1-click Live NLP Lab demos."""
        samples = [
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
        return samples

    def build_dashboard_payload(self):
        # 1. Overview monthly postings trend
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

        # 2. Location map bubbles
        loc_agg = (
            self.fact_post.groupby("location_key", as_index=False)
            .agg(postings=("posting_key", "count"), median_salary=("salary_annual_usd", "median"))
            .merge(self.dim_loc, on="location_key", how="left")
            .merge(self.dim_country[["country_key", "country_name", "region_group"]], on="country_key", how="left")
            .sort_values("postings", ascending=False)
            .head(90)
        )

        # 3. Skills with Category & Demand
        sk_enriched = (
            self.gold_svm.merge(
                self.dim_skill[["skill_key", "is_emerging", "taxonomy_id", "esco_occupation_count"]],
                on="skill_key",
                how="left",
            )
            .merge(self.dim_cat, on="category_key", how="left")
            .sort_values("market_posting_count", ascending=False)
        )

        # 4. 2D Co-occurrence Heatmap Matrix for Top 14 Technical Skills
        tech_cats = set(
            self.dim_cat[
                self.dim_cat["parent_category"].isin(
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
        t14_keys = [x["skill_key"] for x in top14_skills]

        cooc_map = {}
        for r in self.gold_cooc.itertuples(index=False):
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

        # 5. Role x Seniority Salary Matrix
        rs_sal = (
            self.fact_post.dropna(subset=["salary_annual_usd"])
            .groupby(["role_key", "seniority_key"], as_index=False)["salary_annual_usd"]
            .median()
            .merge(self.dim_role[["role_key", "role_title_norm"]], on="role_key")
            .merge(self.dim_sen[["seniority_key", "level_name", "seniority_rank"]], on="seniority_key")
            .sort_values(["role_key", "seniority_rank"])
        )

        # 6. Salary distribution percentiles (q10, q25, median, q75, q90) by Role (all named roles)
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

        # 7. Survey Salary Distribution by Country
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

        # 8. Sample postings per skill for Drill-Through
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

        # 9. Role counts for Role Coverage chart
        role_counts = (
            self.fact_post.groupby("role_key", as_index=False)["posting_key"]
            .count()
            .rename(columns={"posting_key": "postings"})
            .merge(self.dim_role.merge(self.dim_rf, on="role_family_key"), on="role_key")
            .sort_values("postings", ascending=False)
        )

        return {
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
            "roles": role_counts.replace({np.nan: None}).to_dict(orient="records"),
            "role_families": self.dim_rf.to_dict(orient="records"),
            "categories": self.dim_cat.to_dict(orient="records"),
            "skills": sk_enriched.replace({np.nan: None}).to_dict(orient="records"),
            "monthly_postings": monthly_postings.replace({np.nan: None}).to_dict(orient="records"),
            "map_locations": loc_agg.replace({np.nan: None}).to_dict(orient="records"),
            "skill_trends": self.gold_monthly.replace({np.nan: None}).to_dict(orient="records"),
            "skill_yoy": self.gold_yoy.replace({np.nan: None}).to_dict(orient="records"),
            "historical_years": [2020, 2021, 2022, 2023, 2024, 2025],
            "historical_survey_cohorts": self.eda_summary.get("historical_survey_cohorts", []),
            "historical_skill_forecast": self.gold_hist_fcst.replace({np.nan: None}).to_dict(orient="records"),
            "historical_skill_growth": self.gold_hist_growth.replace({np.nan: None}).to_dict(orient="records"),
            "historical_salary_trends": self.gold_hist_sal.replace({np.nan: None}).to_dict(orient="records"),
            "cooccurrence": self.gold_cooc.head(60).replace({np.nan: None}).to_dict(orient="records"),
            "cooccurrence_matrix": {"skills": t14_names, "z": matrix_z},
            "key_influencers": self.gold_inf.replace({np.nan: None}).to_dict(orient="records"),
            "role_seniority_salary": rs_sal.replace({np.nan: None}).to_dict(orient="records"),
            "role_salary_distributions": role_box_stats[:16],
            "country_salary_distributions": country_box_stats[:14],
            "role_profiles": self.gold_profiles.replace({np.nan: None}).to_dict(orient="records"),
            "sample_postings": fps_sample.replace({np.nan: None}).to_dict(orient="records"),
        }

    def save_simulation_to_mysql(self, profile_id: str, profile_label: str, role_key: int, rec_df: pd.DataFrame) -> dict:
        """Persists live Mamdani fuzzy skill-gap results back into MySQL `skillscope_dw.fact_skill_gap_result`."""
        user = os.environ.get("MYSQL_USER", "root")
        pwd = os.environ.get("MYSQL_PASSWORD", "fast")
        conn = pymysql.connect(
            host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
            port=int(os.environ.get("MYSQL_PORT", "3306")),
            user=user,
            password=pwd,
            database="skillscope_dw",
            charset="utf8mb4",
            autocommit=False,
        )
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
                recs = rec_df.replace({np.nan: None}).to_dict(orient="records")
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
            self._send_json({"status": "ok", "service": "SkillScope Python API", "next_ui": "http://127.0.0.1:3000/"})
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
    print("Loading SkillScope Gold Lakehouse & ESCO NLP Engine into memory...")
    STORE = SkillScopeDataStore()
    server = HTTPServer(("127.0.0.1", port), DashboardRequestHandler)
    print(f"SkillScope Python API Backend running at: http://127.0.0.1:{port} (Next.js UI at http://127.0.0.1:3000)")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
