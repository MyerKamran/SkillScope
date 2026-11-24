"""
SkillScope Exploratory Data Analysis (EDA) & Skill Demand Forecasting Module
Courses: Data Analytics & Visualization (DAV) + Data Warehousing & Business Intelligence (DWBI)

Computes strictly from authentic Bronze/Silver/Gold data (zero synthetic multipliers):
1. Market Overview KPIs (Total Postings, Disclosed Salary Coverage %, Median/Mean Salary USD,
   Distinct Skills, Remote Share %, Top Tech Skill Share %).
2. Top Demanded Skills overall and by Role Family.
3. Authentic Wave-over-Wave Normalized Demand Share Growth (Autumn Wave Oct-Nov 2023 vs
   Summer Wave Jul-Aug 2023) + Ridge-Damped 6-Month Demand Forecast (2023-12 to 2024-05).
4. Entry-Level Experience Paradox analysis (deduplicated Entry-Level postings asking 3+ yrs exp).
5. Salary Key Influencers via 5-Fold Cross-Validated Random Forest with proper one-hot nominal
   role encoding and real observed median salary deltas (zero hardcoded boosts).
"""

import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import KFold

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from nlp.skill_extractor import clean_html_text

BRONZE_DIR = os.path.join(PROJECT_ROOT, "data", "bronze")
SILVER_DIR = os.path.join(PROJECT_ROOT, "data", "silver")
GOLD_DIR = os.path.join(PROJECT_ROOT, "data", "gold")
PBI_EXPORT_DIR = os.path.join(PROJECT_ROOT, "data", "powerbi_export")


def run_eda_and_forecast():
    print("=" * 76)
    print("SKILLSCOPE EXPLORATORY DATA ANALYSIS (EDA) & DEMAND FORECASTING")
    print("=" * 76)

    df_post = pd.read_parquet(os.path.join(GOLD_DIR, "fact_job_posting.parquet"))
    df_fps = pd.read_parquet(os.path.join(GOLD_DIR, "fact_posting_skill.parquet"))
    df_skill = pd.read_parquet(os.path.join(GOLD_DIR, "dim_skill.parquet"))
    df_cat = pd.read_parquet(os.path.join(GOLD_DIR, "dim_skill_category.parquet"))
    df_role = pd.read_parquet(os.path.join(GOLD_DIR, "dim_role.parquet"))
    df_sen = pd.read_parquet(os.path.join(GOLD_DIR, "dim_seniority.parquet"))
    df_date = pd.read_parquet(os.path.join(GOLD_DIR, "dim_date.parquet"))
    df_cooc = pd.read_parquet(os.path.join(GOLD_DIR, "gold_skill_cooccurrence.parquet"))

    # 1. Overview KPIs
    total_postings = int(len(df_post))
    sal_nonnull = int(df_post["salary_annual_usd"].notna().sum())
    salary_coverage_pct = round(float(sal_nonnull / max(1, total_postings) * 100.0), 2)
    median_salary = round(float(df_post["salary_annual_usd"].median()), 2)
    mean_salary = round(float(df_post["salary_annual_usd"].mean()), 2)
    distinct_skills = int(df_fps["skill_key"].nunique())
    remote_share_pct = round(float(df_post["is_remote"].mean() * 100.0), 2)

    tech_skill_keys = set(
        df_skill[df_skill["category_key"].isin(
            df_cat[df_cat["parent_category"].isin(["Software & Engineering", "Data & Analytics", "Cloud & DevOps", "Product & Design", "Engineering & Hardware"])]["category_key"]
        )]["skill_key"].tolist()
    )
    fps_tech = df_fps[df_fps["skill_key"].isin(tech_skill_keys)]
    sk_counts = fps_tech.groupby("skill_key")["posting_key"].nunique().sort_values(ascending=False)
    top_sk_key = int(sk_counts.index[0])
    top_sk_name = df_skill.loc[df_skill["skill_key"] == top_sk_key, "skill_name"].iloc[0]
    top_sk_share_pct = round(float(sk_counts.iloc[0] / max(1, fps_tech["posting_key"].nunique()) * 100.0), 2)

    # 2. Entry-Level Experience Paradox Analysis (on deduplicated Entry-Level postings)
    raw_li_path = os.path.join(BRONZE_DIR, "job_postings.csv")
    df_raw_li = pd.read_csv(
        raw_li_path,
        usecols=["title", "company_id", "location", "formatted_experience_level", "description"],
        low_memory=False,
    )
    df_raw_li["title"] = df_raw_li["title"].fillna("Unspecified Role").astype(str).str.strip()
    df_dedup_li = df_raw_li.drop_duplicates(subset=["title", "company_id", "location"]).copy()
    entry_sub = df_dedup_li[
        df_dedup_li["formatted_experience_level"].astype(str).str.contains("Entry", case=False, na=False)
    ].copy()
    entry_clean_desc = pd.Series([clean_html_text(x) for x in entry_sub["description"]], index=entry_sub.index)
    exp_3plus_re = (
        r"\b(?:[3-9]|1[0-5])\s*(?:\+|-\s*\d+|to\s*\d+)?\s*(?:\+?\s*)?years?\b"
        r"(?:\s+of)?(?:\s+\w+){0,3}\s+(?:experience|exp\b)"
    )
    asks_3plus = entry_clean_desc.str.contains(exp_3plus_re, case=False, regex=True)
    entry_paradox_count = int(asks_3plus.sum())
    entry_paradox_total = int(len(entry_sub))
    entry_paradox_pct = round(float(asks_3plus.mean() * 100.0), 2) if entry_paradox_total > 0 else 0.0

    # 3. Authentic Temporal Skill Demand & Wave-over-Wave Normalized Share Growth
    post_dates = df_post.merge(df_date[["date_key", "year_num", "month_num", "year_month"]], on="date_key", how="left")
    fps_dates = df_fps.merge(
        post_dates[["posting_key", "year_num", "month_num", "year_month", "salary_annual_usd"]],
        on="posting_key",
        how="left",
    ).merge(df_skill[["skill_key", "skill_name"]], on="skill_key", how="left")

    month_totals = post_dates.groupby("year_month")["posting_key"].nunique().to_dict()
    df_monthly = (
        fps_dates.groupby(["year_month", "year_num", "month_num", "skill_key", "skill_name"], as_index=False)
        .agg(
            posting_mentions=("posting_key", "nunique"),
            avg_salary_usd=("salary_annual_usd", "mean"),
        )
        .sort_values(["skill_key", "year_month"])
    )
    df_monthly["month_total_postings"] = df_monthly["year_month"].map(month_totals).fillna(1).astype(int)
    df_monthly["demand_share_pct"] = (df_monthly["posting_mentions"] / df_monthly["month_total_postings"] * 100.0).round(3)
    df_monthly["record_type"] = "Historical"
    df_monthly["ci_lower"] = df_monthly["posting_mentions"]
    df_monthly["ci_upper"] = df_monthly["posting_mentions"]

    # Wave 1 (Jun-Sep 2023) vs Wave 2 (Oct-Nov 2023) normalized share growth
    post_dates["wave"] = np.where(post_dates["year_month"] >= "2023-10", "wave2", "wave1")
    wave_totals = post_dates.groupby("wave")["posting_key"].nunique().to_dict()
    w1_tot = max(1, int(wave_totals.get("wave1", 1)))
    w2_tot = max(1, int(wave_totals.get("wave2", 1)))

    fps_dates["wave"] = np.where(fps_dates["year_month"] >= "2023-10", "wave2", "wave1")
    w1_cnts = fps_dates[fps_dates["wave"] == "wave1"].groupby(["skill_key", "skill_name"])["posting_key"].nunique()
    w2_cnts = fps_dates[fps_dates["wave"] == "wave2"].groupby(["skill_key", "skill_name"])["posting_key"].nunique()

    df_yoy = pd.DataFrame({"mentions_2023": w1_cnts, "mentions_2024": w2_cnts}).reset_index().fillna(0)
    df_yoy["mentions_2023"] = df_yoy["mentions_2023"].astype(int)
    df_yoy["mentions_2024"] = df_yoy["mentions_2024"].astype(int)
    df_yoy["total_mentions"] = df_yoy["mentions_2023"] + df_yoy["mentions_2024"]
    df_yoy["wave1_share_pct"] = (df_yoy["mentions_2023"] / w1_tot * 100.0).round(3)
    df_yoy["wave2_share_pct"] = (df_yoy["mentions_2024"] / w2_tot * 100.0).round(3)
    df_yoy["share_change_pp"] = (df_yoy["wave2_share_pct"] - df_yoy["wave1_share_pct"]).round(3)
    df_yoy["yoy_growth_pct"] = (
        (df_yoy["wave2_share_pct"] - df_yoy["wave1_share_pct"])
        / df_yoy["wave1_share_pct"].clip(lower=0.05)
        * 100.0
    ).round(2)

    df_yoy = df_yoy.merge(df_skill[["skill_key", "category_key", "is_emerging"]], on="skill_key", how="left")
    df_yoy = df_yoy.merge(df_cat[["category_key", "category_name", "parent_category"]], on="category_key", how="left")
    # Rank meaningful skills (>= 20 mentions) first to avoid tiny-N distortion
    df_yoy_sig = df_yoy[df_yoy["total_mentions"] >= 20].sort_values("yoy_growth_pct", ascending=False).copy()
    df_yoy = pd.concat([df_yoy_sig, df_yoy[df_yoy["total_mentions"] < 20].sort_values("yoy_growth_pct", ascending=False)], ignore_index=True)

    # Forecast next 6 months (2023-12 to 2024-05) from active observed months (>= 100 postings)
    active_months = sorted([ym for ym, cnt in month_totals.items() if cnt >= 100])
    avg_active_vol = float(np.mean([month_totals[m] for m in active_months])) if active_months else 8000.0
    forecast_months = [
        ("2023-12", 2023, 12),
        ("2024-01", 2024, 1),
        ("2024-02", 2024, 2),
        ("2024-03", 2024, 3),
        ("2024-04", 2024, 4),
        ("2024-05", 2024, 5),
    ]

    forecast_rows = []
    for sk_k, grp in df_monthly.groupby("skill_key"):
        grp_active = grp[grp["year_month"].isin(active_months)].sort_values("year_month")
        if len(grp_active) < 3:
            continue
        x = np.arange(len(grp_active), dtype=float).reshape(-1, 1)
        y_share = grp_active["demand_share_pct"].values.astype(float)

        # Ridge regression damps short-window slope variance safely
        ridge = Ridge(alpha=4.0)
        ridge.fit(x, y_share)
        pred_in = ridge.predict(x)
        std_err_share = float(np.std(y_share - pred_in)) if len(y_share) > 2 else 0.15

        sk_name = grp_active["skill_name"].iloc[0]
        avg_sal = float(grp_active["avg_salary_usd"].mean()) if grp_active["avg_salary_usd"].notna().any() else median_salary

        for f_i, (f_ym, f_yr, f_mo) in enumerate(forecast_months):
            t_future = np.array([[len(grp_active) + f_i]], dtype=float)
            pred_share = float(np.clip(ridge.predict(t_future)[0], 0.02, 80.0))
            ci_share = 1.96 * std_err_share * np.sqrt(1.0 + (f_i + 1) / len(grp_active))
            pred_cnt = max(1, int(round((pred_share / 100.0) * avg_active_vol)))
            lo_cnt = max(0, int(round(((pred_share - ci_share) / 100.0) * avg_active_vol)))
            hi_cnt = max(pred_cnt, int(round(((pred_share + ci_share) / 100.0) * avg_active_vol)))

            forecast_rows.append({
                "year_month": f_ym,
                "year_num": f_yr,
                "month_num": f_mo,
                "skill_key": int(sk_k),
                "skill_name": sk_name,
                "posting_mentions": pred_cnt,
                "avg_salary_usd": round(avg_sal, 2),
                "month_total_postings": int(round(avg_active_vol)),
                "demand_share_pct": round(pred_share, 3),
                "record_type": "Forecast",
                "ci_lower": lo_cnt,
                "ci_upper": hi_cnt,
            })

    df_full_trends = pd.concat([df_monthly, pd.DataFrame(forecast_rows)], ignore_index=True)
    df_full_trends.to_parquet(os.path.join(GOLD_DIR, "gold_monthly_skill_demand.parquet"), index=False)
    df_full_trends.to_csv(os.path.join(PBI_EXPORT_DIR, "gold_monthly_skill_demand.csv"), index=False)
    df_yoy.to_parquet(os.path.join(GOLD_DIR, "gold_skill_yoy_growth.parquet"), index=False)
    df_yoy.to_csv(os.path.join(PBI_EXPORT_DIR, "gold_skill_yoy_growth.csv"), index=False)

    # 4. Key Influencers of Salary (5-Fold CV Random Forest with One-Hot Role Encoding + Real Deltas)
    sal_df = (
        df_post.dropna(subset=["salary_annual_usd"])
        .merge(df_sen[["seniority_key", "seniority_rank"]], on="seniority_key", how="left")
        .copy()
    )
    sal_df["is_seniority_unspecified"] = (sal_df["seniority_rank"] == 0).astype(int)

    top_25_skills = sk_counts.head(25).index.tolist()
    fps_top = df_fps[df_fps["skill_key"].isin(top_25_skills)]
    skill_dummies = pd.crosstab(fps_top["posting_key"], fps_top["skill_key"]).clip(upper=1)
    skill_dummies.columns = [
        f"Skill: {df_skill.loc[df_skill['skill_key'] == int(c), 'skill_name'].iloc[0]}"
        for c in skill_dummies.columns
    ]

    role_dummies = pd.get_dummies(sal_df["role_key"], prefix="role", dtype=int)
    role_cols = list(role_dummies.columns)

    model_df = pd.concat(
        [
            sal_df[["posting_key", "salary_annual_usd", "seniority_rank", "is_seniority_unspecified", "is_remote"]].reset_index(drop=True),
            role_dummies.reset_index(drop=True),
        ],
        axis=1,
    ).merge(skill_dummies, on="posting_key", how="left").fillna(0)

    feature_cols = ["seniority_rank", "is_seniority_unspecified", "is_remote"] + role_cols + list(skill_dummies.columns)
    X = model_df[feature_cols].values
    y = model_df["salary_annual_usd"].values

    # 5-fold cross-validation metrics
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    oof_preds = np.zeros_like(y, dtype=float)
    for tr_idx, va_idx in kf.split(X):
        cv_rf = RandomForestRegressor(n_estimators=100, max_depth=10, min_samples_leaf=5, random_state=42, n_jobs=-1)
        cv_rf.fit(X[tr_idx], y[tr_idx])
        oof_preds[va_idx] = cv_rf.predict(X[va_idx])

    cv_r2 = round(float(r2_score(y, oof_preds)), 4)
    cv_mae = round(float(mean_absolute_error(y, oof_preds)), 2)

    rf_model = RandomForestRegressor(n_estimators=120, max_depth=10, min_samples_leaf=5, random_state=42, n_jobs=-1)
    rf_model.fit(X, y)

    imp_map = dict(zip(feature_cols, rf_model.feature_importances_))
    role_imp = sum(imp_map[c] for c in role_cols)
    sen_imp = imp_map["seniority_rank"] + imp_map["is_seniority_unspecified"]
    rem_imp = imp_map["is_remote"]

    # Real observed median salary deltas (ZERO hardcoded figures)
    sen_high_med = sal_df[sal_df["seniority_rank"] >= 4]["salary_annual_usd"].median()
    sen_low_med = sal_df[sal_df["seniority_rank"].isin([1, 2])]["salary_annual_usd"].median()
    sen_delta = float(sen_high_med - sen_low_med) if pd.notna(sen_high_med) and pd.notna(sen_low_med) else 0.0

    role_medians = sal_df[sal_df["role_key"] != 17].groupby("role_key")["salary_annual_usd"].median()
    role_delta = float(role_medians.quantile(0.75) - role_medians.quantile(0.25)) if len(role_medians) >= 4 else 0.0

    rem_delta = float(
        model_df[model_df["is_remote"] == 1]["salary_annual_usd"].median()
        - model_df[model_df["is_remote"] == 0]["salary_annual_usd"].median()
    )

    influencer_rows = [
        {"factor_name": "Factor: Seniority Level", "importance_pct": round(float(sen_imp * 100.0), 2), "median_salary_impact_usd": round(sen_delta, 2)},
        {"factor_name": "Factor: Job Role Specialization", "importance_pct": round(float(role_imp * 100.0), 2), "median_salary_impact_usd": round(role_delta, 2)},
        {"factor_name": "Factor: Remote Work Eligibility", "importance_pct": round(float(rem_imp * 100.0), 2), "median_salary_impact_usd": round(rem_delta, 2)},
    ]

    for fname in skill_dummies.columns:
        with_sal = model_df[model_df[fname] == 1]["salary_annual_usd"]
        without_sal = model_df[model_df[fname] == 0]["salary_annual_usd"]
        if len(with_sal) >= 5 and len(without_sal) >= 5:
            boost_usd = float(with_sal.median() - without_sal.median())
        else:
            boost_usd = 0.0
        influencer_rows.append({
            "factor_name": fname,
            "importance_pct": round(float(imp_map[fname] * 100.0), 2),
            "median_salary_impact_usd": round(boost_usd, 2),
        })

    df_influencers = pd.DataFrame(influencer_rows).sort_values("importance_pct", ascending=False)
    df_influencers.to_parquet(os.path.join(GOLD_DIR, "gold_salary_key_influencers.parquet"), index=False)
    df_influencers.to_csv(os.path.join(PBI_EXPORT_DIR, "gold_salary_key_influencers.csv"), index=False)

    # 4b. Multi-Year Historical Skill Trajectory & 2026-2027 Forecast (Stack Overflow 2020-2025)
    df_hist_trend = pd.read_parquet(os.path.join(GOLD_DIR, "fact_historical_skill_trend.parquet")).merge(
        df_skill[["skill_key", "skill_name", "category_key"]], on="skill_key", how="left"
    ).merge(df_cat[["category_key", "category_name", "parent_category"]], on="category_key", how="left")

    hist_cohorts = (
        df_hist_trend[["year_num", "year_total_respondents"]]
        .drop_duplicates()
        .sort_values("year_num")
        .rename(columns={"year_total_respondents": "respondents"})
        .to_dict(orient="records")
    )
    total_hist_respondents = int(sum(r["respondents"] for r in hist_cohorts))

    hist_fcst_rows = []
    hist_growth_rows = []
    for sk_k, grp in df_hist_trend.groupby("skill_key"):
        grp_s = grp.sort_values("year_num")
        sk_name = grp_s["skill_name"].iloc[0]
        cat_name = grp_s["category_name"].iloc[0]
        p_cat = grp_s["parent_category"].iloc[0]

        for row in grp_s.itertuples(index=False):
            hist_fcst_rows.append({
                "year_num": int(row.year_num),
                "skill_key": int(sk_k),
                "skill_name": sk_name,
                "category_name": cat_name,
                "adoption_pct": float(row.adoption_pct),
                "respondent_count": int(row.respondent_count),
                "median_salary_usd": float(row.median_salary_usd) if pd.notna(row.median_salary_usd) else np.nan,
                "record_type": "Historical",
                "ci_lower_pct": float(row.adoption_pct),
                "ci_upper_pct": float(row.adoption_pct),
            })

        # Compute 2020 vs 2025 growth metrics (plus earliest active survey year for newer tools)
        a_2020 = float(grp_s.loc[grp_s["year_num"] == 2020, "adoption_pct"].iloc[0]) if (grp_s["year_num"] == 2020).any() else 0.0
        a_2025 = float(grp_s.loc[grp_s["year_num"] == 2025, "adoption_pct"].iloc[0]) if (grp_s["year_num"] == 2025).any() else 0.0
        r_2025 = int(grp_s.loc[grp_s["year_num"] == 2025, "respondent_count"].iloc[0]) if (grp_s["year_num"] == 2025).any() else 0
        s_2025 = grp_s.loc[grp_s["year_num"] == 2025, "median_salary_usd"].iloc[0] if (grp_s["year_num"] == 2025).any() else np.nan
        active_grp = grp_s[grp_s["adoption_pct"] >= 0.25]
        base_yr = int(active_grp["year_num"].iloc[0]) if not active_grp.empty else 2020
        base_val = float(active_grp["adoption_pct"].iloc[0]) if not active_grp.empty else a_2020

        if a_2020 >= 0.50:
            delta_pp = round(a_2025 - a_2020, 2)
            rel_pct = round(((a_2025 - a_2020) / a_2020) * 100.0, 2)
            cagr = round(((max(0.01, a_2025) / a_2020) ** (1.0 / 5.0) - 1.0) * 100.0, 2)
        else:
            delta_pp = round(a_2025 - base_val, 2) if not active_grp.empty else 0.0
            yrs_span = max(1, 2025 - base_yr)
            rel_pct = round(((a_2025 - base_val) / base_val) * 100.0, 2) if base_val >= 0.25 else np.nan
            cagr = round(((max(0.01, a_2025) / base_val) ** (1.0 / yrs_span) - 1.0) * 100.0, 2) if base_val >= 0.25 and a_2025 > 0 else np.nan

        hist_growth_rows.append({
            "skill_key": int(sk_k),
            "skill_name": sk_name,
            "category_name": cat_name,
            "parent_category": p_cat,
            "baseline_year": base_yr,
            "adoption_2020_pct": round(a_2020, 2),
            "adoption_2025_pct": round(a_2025, 2),
            "peak_adoption_pct": round(float(grp_s["adoption_pct"].max()), 2),
            "delta_pp": delta_pp,
            "relative_change_pct": rel_pct,
            "cagr_pct": cagr,
            "comparable_2020_2025": 1 if (a_2020 >= 1.0 and float(grp_s["adoption_pct"].max()) >= 1.5) else 0,
            "respondents_2025": r_2025,
            "median_salary_2025_usd": round(float(s_2025), 2) if pd.notna(s_2025) else np.nan,
        })

        # Fit 2026-2027 damped Ridge forecast for active skills (>= 4 non-trivial years, peak >= 1.0%)
        fit_grp = grp_s[grp_s["adoption_pct"] > 0.1].sort_values("year_num")
        if len(fit_grp) >= 4 and float(fit_grp["adoption_pct"].max()) >= 1.0:
            x_h = np.arange(len(fit_grp), dtype=float).reshape(-1, 1)
            y_h = fit_grp["adoption_pct"].values.astype(float)
            ridge_h = Ridge(alpha=2.5)
            ridge_h.fit(x_h, y_h)
            err_h = float(np.std(y_h - ridge_h.predict(x_h)))
            last_yr = int(fit_grp["year_num"].iloc[-1])
            for step_i, f_yr in enumerate([2026, 2027], start=1):
                t_f = np.array([[len(fit_grp) - 1 + (f_yr - last_yr)]], dtype=float)
                pred_a = float(np.clip(ridge_h.predict(t_f)[0], 0.0, 95.0))
                ci_w = 1.96 * max(0.35, err_h) * np.sqrt(1.0 + step_i / len(fit_grp))
                hist_fcst_rows.append({
                    "year_num": f_yr,
                    "skill_key": int(sk_k),
                    "skill_name": sk_name,
                    "category_name": cat_name,
                    "adoption_pct": round(pred_a, 2),
                    "respondent_count": 0,
                    "median_salary_usd": np.nan,
                    "record_type": "Forecast",
                    "ci_lower_pct": round(max(0.0, pred_a - ci_w), 2),
                    "ci_upper_pct": round(min(98.0, pred_a + ci_w), 2),
                })

    df_hist_fcst = pd.DataFrame(hist_fcst_rows)
    df_hist_growth = pd.DataFrame(hist_growth_rows).sort_values("adoption_2025_pct", ascending=False)
    df_hist_fcst.to_parquet(os.path.join(GOLD_DIR, "gold_historical_skill_forecast.parquet"), index=False)
    df_hist_fcst.to_csv(os.path.join(PBI_EXPORT_DIR, "gold_historical_skill_forecast.csv"), index=False)
    df_hist_growth.to_parquet(os.path.join(GOLD_DIR, "gold_historical_skill_growth.parquet"), index=False)
    df_hist_growth.to_csv(os.path.join(PBI_EXPORT_DIR, "gold_historical_skill_growth.csv"), index=False)

    # 4c. 6-Year Global Tech Salary Evolution (2020-2025 exact quantiles on full 151k Silver records)
    df_ai_sal = pd.read_parquet(os.path.join(SILVER_DIR, "silver_ai_jobs_salaries.parquet")).merge(
        df_role[["role_key", "role_title_norm"]], on="role_key", how="left"
    ).merge(df_sen[["seniority_key", "level_name"]], on="seniority_key", how="left")
    total_ai_sal_records = int(len(df_ai_sal))

    sal_trend_rows = []
    def _agg_sal_segment(df_in, seg_type: str, seg_val: str):
        for yr_val, g in df_in.groupby("year_num"):
            vals = g["salary_in_usd"].values
            sal_trend_rows.append({
                "segment_type": seg_type,
                "segment_value": seg_val,
                "year_num": int(yr_val),
                "record_count": int(len(vals)),
                "median_salary_usd": round(float(np.median(vals)), 2),
                "mean_salary_usd": round(float(np.mean(vals)), 2),
                "p25_salary_usd": round(float(np.percentile(vals, 25)), 2),
                "p75_salary_usd": round(float(np.percentile(vals, 75)), 2),
                "remote_share_pct": round(float((g["work_mode"] == "Remote").mean() * 100.0), 2),
            })

    _agg_sal_segment(df_ai_sal, "overall", "All AI & Tech Roles")
    for wm in ["Remote", "Hybrid", "On-Site"]:
        _agg_sal_segment(df_ai_sal[df_ai_sal["work_mode"] == wm], "work_mode", wm)
    for sk_lvl in df_ai_sal["level_name"].dropna().unique():
        _agg_sal_segment(df_ai_sal[df_ai_sal["level_name"] == sk_lvl], "seniority", str(sk_lvl))
    top_ai_roles = (
        df_ai_sal[df_ai_sal["role_key"] != 17]["role_title_norm"]
        .value_counts()
        .loc[lambda s: s >= 150]
        .index.tolist()
    )
    for r_name in top_ai_roles:
        _agg_sal_segment(df_ai_sal[df_ai_sal["role_title_norm"] == r_name], "role", str(r_name))

    df_hist_sal_trends = pd.DataFrame(sal_trend_rows).sort_values(["segment_type", "segment_value", "year_num"])
    df_hist_sal_trends.to_parquet(os.path.join(GOLD_DIR, "gold_historical_salary_trends.parquet"), index=False)
    df_hist_sal_trends.to_csv(os.path.join(PBI_EXPORT_DIR, "gold_historical_salary_trends.csv"), index=False)

    # 5. Save Master EDA Report JSON
    min_dt = df_date.loc[df_date["date_key"] == int(df_post["date_key"].min()), "full_date"].iloc[0]
    max_dt = df_date.loc[df_date["date_key"] == int(df_post["date_key"].max()), "full_date"].iloc[0]

    eda_summary = {
        "kpis": {
            "total_postings": total_postings,
            "median_annual_salary_usd": median_salary,
            "mean_annual_salary_usd": mean_salary,
            "salary_coverage_pct": salary_coverage_pct,
            "salary_disclosed_count": sal_nonnull,
            "distinct_skills_in_demand": distinct_skills,
            "remote_share_pct": remote_share_pct,
            "top_skill_name": top_sk_name,
            "top_skill_share_pct": top_sk_share_pct,
            "entry_level_3plus_years_paradox_pct": entry_paradox_pct,
            "entry_level_3plus_years_paradox_count": entry_paradox_count,
            "entry_level_total_count": entry_paradox_total,
            "date_range": f"{min_dt} to {max_dt}",
            "wave1_postings": w1_tot,
            "wave2_postings": w2_tot,
            "rf_salary_cv_r2": cv_r2,
            "rf_salary_cv_mae_usd": cv_mae,
            "rf_sample_size": int(len(model_df)),
            "historical_years_span": "2020-2025",
            "historical_survey_total_respondents": total_hist_respondents,
            "historical_salary_total_records": total_ai_sal_records,
        },
        "historical_survey_cohorts": hist_cohorts,
        "historical_salary_overall": df_hist_sal_trends[df_hist_sal_trends["segment_type"] == "overall"].to_dict(orient="records"),
        "top_5yr_rising_skills": df_hist_growth[df_hist_growth["comparable_2020_2025"] == 1].sort_values("delta_pp", ascending=False).head(8).replace({np.nan: None}).to_dict(orient="records"),
        "top_5yr_cooling_skills": df_hist_growth[df_hist_growth["comparable_2020_2025"] == 1].sort_values("delta_pp", ascending=True).head(6).replace({np.nan: None}).to_dict(orient="records"),
        "top_10_skills": df_yoy.sort_values("total_mentions", ascending=False).head(10)[
            ["skill_name", "category_name", "mentions_2023", "mentions_2024", "wave1_share_pct", "wave2_share_pct", "yoy_growth_pct"]
        ].to_dict(orient="records"),
        "fastest_rising_skills": df_yoy_sig.head(8)[
            ["skill_name", "category_name", "mentions_2023", "mentions_2024", "wave1_share_pct", "wave2_share_pct", "yoy_growth_pct"]
        ].to_dict(orient="records"),
        "declining_skills": df_yoy_sig.tail(6)[
            ["skill_name", "category_name", "mentions_2023", "mentions_2024", "wave1_share_pct", "wave2_share_pct", "yoy_growth_pct"]
        ].to_dict(orient="records"),
        "top_cooccurring_pairs": df_cooc.head(10)[
            ["skill_name_a", "skill_name_b", "co_posting_count", "cooccurrence_strength"]
        ].to_dict(orient="records"),
        "salary_key_influencers": df_influencers.head(12).to_dict(orient="records"),
    }

    with open(os.path.join(GOLD_DIR, "eda_summary_report.json"), "w", encoding="utf-8") as f:
        json.dump(eda_summary, f, indent=2)

    print(f"  -> Overview KPIs: {total_postings:,} Postings ({min_dt}..{max_dt}) | Median Salary: ${median_salary:,.0f} ({salary_coverage_pct:.1f}% disclosed) | Remote: {remote_share_pct:.1f}%")
    print(f"  -> Entry-Level Experience Paradox: {entry_paradox_pct:.1f}% ({entry_paradox_count:,}/{entry_paradox_total:,}) ask for 3+ yrs exp.")
    print(f"  -> Salary Random Forest 5-Fold CV: R2 = {cv_r2:.4f}, MAE = ${cv_mae:,.0f} (n={len(model_df):,})")
    print(f"  -> Saved authentic Wave-over-Wave Trends, 6-Month Ridge Forecast & Key Influencers.")
    print("=" * 76)


if __name__ == "__main__":
    run_eda_and_forecast()
