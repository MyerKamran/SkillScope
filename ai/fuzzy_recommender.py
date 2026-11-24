"""
SkillScope AI Module: Knowledge-Based Expert System with Fuzzy Priority Scoring
Courses: Data Analytics & Visualization (DAV) + Data Warehousing & Business Intelligence (DWBI)

Implements:
1. Knowledge Base Rules: classifies skills per role into Core, Differentiating, and Emerging.
2. Fuzzy Logic Engine (Mamdani inference + Centroid defuzzification):
   - Fuzzifies Demand (%), Salary Premium (%), and Co-occurrence Proximity (0..1) into
     Low, Medium, and High fuzzy sets using triangular/trapezoidal membership functions.
   - Applies fuzzy inference rules to compute a defuzzified gap_score (0..100) and
     fuzzy_priority_level (Low, Medium, High, Very High).
3. Computes overall Role Match Score (%) for any learner profile + target role and writes
   recommendations back to the warehouse table `fact_skill_gap_result`.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple


def trapmf(x: float, a: float, b: float, c: float, d: float) -> float:
    """Trapezoidal membership function."""
    if x <= a or x >= d:
        return 0.0
    elif b <= x <= c:
        return 1.0
    elif a < x < b:
        return (x - a) / (b - a) if b > a else 1.0
    else:
        return (d - x) / (d - c) if d > c else 1.0


def trimf(x: float, a: float, b: float, c: float) -> float:
    """Triangular membership function."""
    if x <= a or x >= c:
        return 0.0
    elif x == b:
        return 1.0
    elif a < x < b:
        return (x - a) / (b - a) if b > a else 1.0
    else:
        return (c - x) / (c - b) if c > b else 1.0


class FuzzySkillGapRecommender:
    """
    Knowledge-based skill-gap recommender with fuzzy priority scoring.
    """

    def __init__(
        self,
        role_skill_profiles_df: pd.DataFrame,
        cooccurrence_df: pd.DataFrame,
        skills_df: pd.DataFrame,
        roles_df: pd.DataFrame,
    ):
        self.role_profiles = role_skill_profiles_df.copy()
        self.cooccurrence = cooccurrence_df.copy()
        self.skills = skills_df.copy()
        self.roles = roles_df.copy()

        self.skill_name_to_key = dict(zip(self.skills["skill_name"], self.skills["skill_key"]))
        self.skill_key_to_name = dict(zip(self.skills["skill_key"], self.skills["skill_name"]))
        self.skill_key_to_emerging = dict(zip(self.skills["skill_key"], self.skills["is_emerging"]))

        # Build fast lookup for pairwise co-occurrence jaccard / conditional probability
        self.cooc_lookup = {}
        for _, row in self.cooccurrence.iterrows():
            k1 = int(row["skill_key_a"])
            k2 = int(row["skill_key_b"])
            score = float(row["cooccurrence_strength"])
            self.cooc_lookup[(k1, k2)] = score
            self.cooc_lookup[(k2, k1)] = score

    @staticmethod
    def fuzzify_demand(demand_pct: float) -> Dict[str, float]:
        """Fuzzifies role demand percentage (0% to 70%+) into Low, Medium, High."""
        val = float(np.clip(demand_pct, 0.0, 100.0))
        return {
            "low": trapmf(val, -1.0, 0.0, 6.0, 16.0),
            "medium": trimf(val, 8.0, 20.0, 35.0),
            "high": trapmf(val, 22.0, 38.0, 100.0, 101.0),
        }

    @staticmethod
    def fuzzify_salary_premium(premium_pct: float) -> Dict[str, float]:
        """Fuzzifies salary premium percentage (-20% to +40%+) into Low, Medium, High."""
        val = float(np.clip(premium_pct, -30.0, 60.0))
        return {
            "low": trapmf(val, -31.0, -30.0, 0.0, 6.0),
            "medium": trimf(val, 2.0, 10.0, 20.0),
            "high": trapmf(val, 12.0, 22.0, 60.0, 61.0),
        }

    @staticmethod
    def fuzzify_proximity(proximity: float) -> Dict[str, float]:
        """Fuzzifies learning proximity / co-occurrence with existing skills (0..1)."""
        val = float(np.clip(proximity, 0.0, 1.0))
        return {
            "low": trapmf(val, -0.1, 0.0, 0.12, 0.28),
            "medium": trimf(val, 0.18, 0.38, 0.60),
            "high": trapmf(val, 0.45, 0.68, 1.0, 1.1),
        }

    @staticmethod
    def _dominant_level(fuzzy_dict: Dict[str, float]) -> str:
        """Returns capitalized dominant fuzzy linguistic term (Low/Medium/High)."""
        best = max(fuzzy_dict.items(), key=lambda kv: kv[1])[0]
        return best.capitalize()

    def compute_fuzzy_priority(
        self,
        demand_pct: float,
        premium_pct: float,
        proximity: float,
        is_core: bool,
        is_differentiating: bool,
        is_emerging: bool,
    ) -> Tuple[float, str]:
        """
        Applies Mamdani fuzzy rule base and centroid defuzzification to output:
        (gap_score in [0, 100], fuzzy_priority_level in ['Low', 'Medium', 'High', 'Very High'])
        """
        d = self.fuzzify_demand(demand_pct)
        s = self.fuzzify_salary_premium(premium_pct)
        p = self.fuzzify_proximity(proximity)

        # Fuzzy Rule Base activations (firing strengths via Zadeh AND=min, OR=max)
        # Rule set for VERY HIGH priority (centroid = 92)
        r_vh_1 = min(d["high"], p["high"])
        r_vh_2 = min(d["high"], s["high"])
        r_vh_3 = min(d["high"], p["medium"], s["medium"])
        act_very_high = max(r_vh_1, r_vh_2, r_vh_3)

        # Rule set for HIGH priority (centroid = 74)
        r_h_1 = min(d["high"], p["low"])
        r_h_2 = min(d["medium"], p["high"])
        r_h_3 = min(d["medium"], s["high"])
        r_h_4 = min(p["high"], s["high"])
        act_high = max(r_h_1, r_h_2, r_h_3, r_h_4)

        # Rule set for MEDIUM priority (centroid = 48)
        r_m_1 = min(d["medium"], p["medium"])
        r_m_2 = min(d["medium"], p["low"])
        r_m_3 = min(d["low"], p["high"])
        r_m_4 = min(d["low"], s["high"])
        act_medium = max(r_m_1, r_m_2, r_m_3, r_m_4)

        # Rule set for LOW priority (centroid = 20)
        r_l_1 = min(d["low"], p["low"])
        r_l_2 = min(d["low"], p["medium"], s["low"])
        act_low = max(r_l_1, r_l_2, 0.05)

        # Centroid Defuzzification over output fuzzy singletons
        numerator = (
            act_very_high * 92.0
            + act_high * 74.0
            + act_medium * 48.0
            + act_low * 20.0
        )
        denominator = act_very_high + act_high + act_medium + act_low
        base_score = numerator / denominator if denominator > 0 else 25.0

        # Knowledge-based Expert System bonuses (Core, Differentiating, Emerging)
        expert_bonus = 0.0
        if is_core:
            expert_bonus += 6.0
        if is_differentiating:
            expert_bonus += 4.0
        if is_emerging:
            expert_bonus += 3.0

        gap_score = float(np.clip(base_score + expert_bonus, 5.0, 99.5))

        if gap_score >= 76.0:
            level = "Very High"
        elif gap_score >= 58.0:
            level = "High"
        elif gap_score >= 38.0:
            level = "Medium"
        else:
            level = "Low"

        return round(gap_score, 2), level

    def recommend_for_profile(
        self,
        profile_id: str,
        profile_label: str,
        role_key: int,
        known_skill_keys: List[int],
        top_n: int = 15,
    ) -> Tuple[float, pd.DataFrame]:
        """
        Evaluates a learner's current skills against a target role_key.
        Returns (role_match_score, recommendations_df) with Mamdani fuzzy explainability fields.
        """
        role_sub = self.role_profiles[self.role_profiles["role_key"] == role_key].copy()
        if role_sub.empty:
            return 0.0, pd.DataFrame()

        known_set = set(int(k) for k in known_skill_keys)

        # Compute overall Role Match Score weighted by demand_pct of the top 15 skills of the role
        top_role_skills = role_sub.sort_values("demand_pct", ascending=False).head(15)
        total_weight = top_role_skills["demand_pct"].sum()
        matched_weight = top_role_skills[top_role_skills["skill_key"].isin(known_set)]["demand_pct"].sum()
        role_match_score = round(float((matched_weight / total_weight) * 100.0), 2) if total_weight > 0 else 0.0

        # Evaluate every missing skill for the target role
        missing_sub = role_sub[~role_sub["skill_key"].isin(known_set)].copy()
        rows = []

        for _, r in missing_sub.iterrows():
            sk_key = int(r["skill_key"])
            demand_pct = float(r["demand_pct"])
            premium_pct = float(r.get("salary_premium_pct", 0.0))
            is_core = bool(r.get("is_core_skill", demand_pct >= 18.0))
            is_diff = bool(r.get("is_differentiating", False))
            is_em = bool(self.skill_key_to_emerging.get(sk_key, 0))

            # Calculate co-occurrence proximity to the learner's existing skills
            if known_set:
                proximities = [
                    (k, self.cooc_lookup.get((sk_key, k), 0.05))
                    for k in known_set
                ]
                proximities.sort(key=lambda x: x[1], reverse=True)
                top_prox = proximities[:3]
                proximity = float(np.mean([p[1] for p in top_prox]))
                closest_names = [self.skill_key_to_name.get(p[0], "") for p in top_prox[:2] if p[1] >= 0.10]
            else:
                proximity = 0.25
                closest_names = []

            d_fuzz = self.fuzzify_demand(demand_pct)
            s_fuzz = self.fuzzify_salary_premium(premium_pct)
            p_fuzz = self.fuzzify_proximity(proximity)

            gap_score, priority_level = self.compute_fuzzy_priority(
                demand_pct=demand_pct,
                premium_pct=premium_pct,
                proximity=proximity,
                is_core=is_core,
                is_differentiating=is_diff,
                is_emerging=is_em,
            )

            tags = []
            if is_core:
                tags.append("Core role skill")
            if is_diff:
                tags.append("Differentiating for role")
            if is_em:
                tags.append("Emerging trend")
            tag_str = ", ".join(tags) if tags else "Supporting skill"

            prox_txt = (
                f"strong co-occurrence with {' & '.join(closest_names)}"
                if closest_names
                else f"proximity {proximity:.2f}"
            )
            prem_sign = "+" if premium_pct >= 0 else ""
            rationale = (
                f"{tag_str} ({demand_pct:.1f}% role demand, "
                f"{prem_sign}{premium_pct:.1f}% salary premium, {prox_txt})"
            )

            rows.append({
                "profile_id": profile_id,
                "profile_label": profile_label,
                "role_key": int(role_key),
                "skill_key": sk_key,
                "demand_pct": round(demand_pct, 2),
                "salary_premium_pct": round(premium_pct, 2),
                "cooccurrence_proximity": round(proximity, 3),
                "fuzzy_priority_level": priority_level,
                "gap_score": gap_score,
                "role_match_score": role_match_score,
                "is_core_skill": int(is_core),
                "is_differentiating": int(is_diff),
                "is_emerging": int(is_em),
                "demand_level": self._dominant_level(d_fuzz),
                "premium_level": self._dominant_level(s_fuzz),
                "proximity_level": self._dominant_level(p_fuzz),
                "rationale": rationale,
            })

        rec_df = pd.DataFrame(rows)
        if not rec_df.empty:
            rec_df = rec_df.sort_values(["gap_score", "demand_pct"], ascending=[False, False]).head(top_n).copy()
            rec_df["priority_rank"] = range(1, len(rec_df) + 1)

        return role_match_score, rec_df
