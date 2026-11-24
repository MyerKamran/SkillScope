"""
SkillScope Master ETL, NLP, AI & Analytics Pipeline (Bronze -> Silver -> Gold -> Warehouse)
Courses: Data Warehousing & Business Intelligence (DWBI) + Data Analytics & Visualization (DAV)

Processes authentic datasets in `data/bronze/`:
  1. Kaggle LinkedIn Job Postings (`job_postings.csv` - 33,246 postings, Jun-Nov 2023)
  2. Stack Overflow Annual Developer Surveys 2020-2025 (`survey_2020..2025.parquet` - 424,980 responses)
  3. Global AI/ML & Tech Salaries 2020-2025 (`ai_jobs_salaries_2020_2025.csv` - 151,445 records)
  4. European Commission ESCO Taxonomy (`data/train-00000-of-00001-1c75e336a95e7a61.parquet` - 3,015 occupations)
  5. GeoNames Cities (`cities15000.txt` - 34,000+ global cities with lat/lon coordinates)
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ai.fuzzy_recommender import FuzzySkillGapRecommender
from nlp.skill_extractor import ESCOSkillExtractor, clean_html_text

BRONZE_DIR = os.path.join(PROJECT_ROOT, "data", "bronze")
SILVER_DIR = os.path.join(PROJECT_ROOT, "data", "silver")
GOLD_DIR = os.path.join(PROJECT_ROOT, "data", "gold")
PBI_EXPORT_DIR = os.path.join(PROJECT_ROOT, "data", "powerbi_export")

for d in [BRONZE_DIR, SILVER_DIR, GOLD_DIR, PBI_EXPORT_DIR]:
    os.makedirs(d, exist_ok=True)


# ============================================================================
# 1. ROLE & ROLE FAMILY NORMALIZATION RULES (Word-Boundary + Domain Guards)
# ============================================================================
ROLE_TAXONOMY = [
    # (role_key, role_title_norm, family_key, family_name, domain_area, min_exp, title_keywords)
    (1, "Data Scientist", 1, "Data Science & AI", "Data & Analytics", 2, ["data scientist", "decision scientist", "applied scientist", "research scientist", "statistician"]),
    (2, "Machine Learning / AI Engineer", 1, "Data Science & AI", "Data & Analytics", 3, ["machine learning", "ml engineer", "ai engineer", "artificial intelligence", "deep learning", "nlp engineer", "computer vision", "llm engineer", "llm"]),
    (3, "Data Analyst", 2, "Data Analytics & BI", "Data & Analytics", 1, ["data analyst", "marketing analyst", "operations analyst", "product analyst", "reporting analyst", "quantitative analyst", "insights analyst", "analytics manager", "analytics engineer"]),
    (4, "BI Developer / Engineer", 2, "Data Analytics & BI", "Data & Analytics", 2, ["business intelligence", "bi developer", "bi engineer", "bi analyst", "power bi", "tableau developer"]),
    (5, "Data Engineer", 3, "Data Engineering & Database", "Data & Analytics", 2, ["data engineer", "etl developer", "etl engineer", "big data", "databricks", "snowflake", "data warehouse", "data architect"]),
    (6, "Database Administrator", 3, "Data Engineering & Database", "Data & Analytics", 3, ["database administrator", "dba", "sql developer", "database engineer", "database developer"]),
    (7, "Backend Software Engineer", 4, "Software Engineering", "Technology", 2, ["backend", "back-end", "back end", "java developer", "java engineer", "python developer", "golang", "c++ developer", "c# developer", ".net developer", "api engineer"]),
    (8, "Frontend / Web Developer", 4, "Software Engineering", "Technology", 1, ["frontend", "front-end", "front end", "react developer", "angular developer", "vue developer", "web developer", "ui developer", "javascript developer"]),
    (9, "Full-Stack Software Engineer", 4, "Software Engineering", "Technology", 2, ["full stack", "full-stack", "fullstack", "software engineer", "software developer", "application developer", "programmer"]),
    (10, "Mobile Developer", 4, "Software Engineering", "Technology", 2, ["ios developer", "ios engineer", "android developer", "android engineer", "mobile developer", "mobile engineer", "flutter", "react native"]),
    (11, "Cloud / DevOps / SRE Engineer", 5, "Cloud, DevOps & Security", "Technology", 3, ["devops", "site reliability", "sre", "cloud engineer", "cloud architect", "platform engineer", "kubernetes", "infrastructure engineer", "systems engineer", "network engineer"]),
    (12, "Cybersecurity Analyst / Engineer", 5, "Cloud, DevOps & Security", "Technology", 2, ["cybersecurity", "cyber security", "infosec", "information security", "security engineer", "security analyst", "security architect", "soc analyst", "penetration test", "iam engineer", "red team"]),
    (13, "QA / Test Automation Engineer", 4, "Software Engineering", "Technology", 1, ["qa engineer", "qa analyst", "qa lead", "qa manager", "sdet", "test automation", "automation tester", "software test", "quality assurance engineer", "quality assurance analyst"]),
    (14, "Product / Technical Project Manager", 6, "Product & Business Management", "Business", 3, ["product manager", "project manager", "scrum master", "agile coach", "program manager", "product owner", "technical project"]),
    (15, "Business / Financial Systems Analyst", 6, "Product & Business Management", "Business", 1, ["business analyst", "financial analyst", "systems analyst", "erp analyst", "salesforce", "sap ", "business systems"]),
    (16, "Engineering / IT Manager", 6, "Product & Business Management", "Business", 5, ["engineering manager", "it manager", "director of engineering", "vp of engineering", "cto", "head of data", "head of engineering", "tech lead", "it director"]),
    (17, "General / Other Professional Role", 7, "General & Domain Operations", "Operations", 1, []),
    (18, "UI/UX & Product Designer", 4, "Software Engineering", "Technology", 2, ["ux designer", "ui/ux", "ui designer", "product designer", "interaction designer", "visual designer", "graphic designer", "web designer"]),
    (19, "Solutions / Enterprise Architect", 5, "Cloud, DevOps & Security", "Technology", 5, ["solutions architect", "solution architect", "enterprise architect", "technical architect", "software architect", "system architect", "principal architect"]),
    (20, "IT Support / Systems Administrator", 5, "Cloud, DevOps & Security", "Technology", 1, ["help desk", "helpdesk", "it support", "desktop support", "technical support", "service desk", "system administrator", "systems administrator", "sysadmin", "it technician", "it specialist", "network administrator"]),
    (21, "Embedded / Firmware / Hardware Engineer", 8, "Engineering & Hardware", "Engineering", 2, ["embedded software", "embedded engineer", "firmware", "hardware engineer", "fpga", "asic", "rf engineer", "controls engineer", "robotics engineer"]),
    (22, "Mechanical / Civil / Industrial Engineer", 8, "Engineering & Hardware", "Engineering", 2, ["mechanical engineer", "civil engineer", "structural engineer", "industrial engineer", "manufacturing engineer", "process engineer", "chemical engineer", "electrical engineer", "project engineer", "field engineer"]),
    (23, "Accounting / Finance / Audit Specialist", 9, "Finance, Sales & Marketing", "Business", 2, ["accountant", "accounting manager", "controller", "auditor", "tax manager", "tax analyst", "payroll", "finance manager", "bookkeeper", "credit analyst", "underwriter"]),
    (24, "Sales / Account Executive / BDR", 9, "Finance, Sales & Marketing", "Business", 1, ["account executive", "sales representative", "sales manager", "account manager", "business development", "sales engineer", "solutions consultant", "bdr", "sdr"]),
    (25, "Digital Marketing / Growth Specialist", 9, "Finance, Sales & Marketing", "Business", 1, ["marketing manager", "digital marketing", "seo", "social media manager", "content marketing", "brand manager", "growth marketing", "marketing specialist", "marketing coordinator"]),
    (26, "Human Resources / Talent Acquisition", 10, "Operations, Legal & Healthcare", "Operations", 1, ["recruiter", "talent acquisition", "human resources", "hr manager", "hr generalist", "hrbp", "people operations", "compensation analyst", "benefits specialist"]),
    (27, "Supply Chain / Operations Manager", 10, "Operations, Legal & Healthcare", "Operations", 2, ["supply chain", "logistics manager", "procurement", "purchasing", "operations manager", "inventory manager", "warehouse manager", "demand planner"]),
    (28, "Legal / Compliance / Risk Specialist", 10, "Operations, Legal & Healthcare", "Operations", 3, ["attorney", "legal counsel", "paralegal", "compliance officer", "compliance manager", "risk manager", "regulatory affairs", "privacy officer"]),
    (29, "Healthcare / Clinical / Nursing Professional", 10, "Operations, Legal & Healthcare", "Healthcare", 1, ["registered nurse", "nurse practitioner", "lpn", "physician", "pharmacist", "physical therapist", "occupational therapist", "respiratory therapist", "medical assistant", "dental hygienist", "clinical nurse"]),
]

# Precompile word-boundary regexes; evaluate generic role 9 (Full-Stack / Software Engineer) after specialized engineering roles (18..22)
ROLE_KEYWORD_REGEXES = []
_ordered_taxonomy = [r for r in ROLE_TAXONOMY if r[0] not in (9, 17)] + [r for r in ROLE_TAXONOMY if r[0] == 9]
for r_key, _, _, _, _, _, kw_list in _ordered_taxonomy:
    if kw_list:
        joined = "|".join(re.escape(k.strip()) for k in kw_list)
        ROLE_KEYWORD_REGEXES.append((r_key, re.compile(rf"(?<!\w)(?:{joined})(?!\w)", re.IGNORECASE)))

PHYSICAL_SECURITY_RE = re.compile(
    r"\b(?:security guard|security officer|armed security|unarmed security|loss prevention|patrol|bouncer|door security|concierge)\b",
    re.IGNORECASE,
)
NONTECH_QA_RE = re.compile(
    r"\b(?:pharmacy|pharmaceutical|food|clinical|hospital|patient|nursing|dental|manufacturing|warehouse|laboratory|gmp|meat|sanitation|plant)\b",
    re.IGNORECASE,
)
TECH_QA_RE = re.compile(
    r"\b(?:software|sdet|selenium|cypress|playwright|automated test|web|api|qa engineer|agile|jira)\b",
    re.IGNORECASE,
)
NONTECH_TITLE_RE = re.compile(
    r"\b(?:nurse|rn\b|lpn\b|cook|dishwasher|driver|cashier|dental|hygienist|hearing|store director|warehouse|shipping|janitor|therapist|pharmacist|account executive|sales representative|territory|carpenter|electrician|mechanic|bartender|waiter|server|delivery|housekeeper|receptionist|caregiver)\b",
    re.IGNORECASE,
)
GENERIC_TECH_TITLE_RE = re.compile(
    r"\b(?:engineer|developer|analyst|scientist|architect|consultant|specialist|associate|intern|staff|lead|manager|technician|administrator)\b",
    re.IGNORECASE,
)

# Explicit Stack Overflow 2024 DevType -> SkillScope role_key mapping
SO_DEVTYPE_TO_ROLE_KEY = {
    "data scientist or machine learning specialist": 1,
    "academic researcher": 1,
    "research & development role": 2,
    "data or business analyst": 3,
    "data engineer": 5,
    "database administrator": 6,
    "developer, back-end": 7,
    "developer, front-end": 8,
    "developer, full-stack": 9,
    "developer, desktop or enterprise applications": 9,
    "developer, embedded applications or devices": 9,
    "developer, game or graphics": 9,
    "developer, mobile": 10,
    "devops specialist": 11,
    "cloud infrastructure engineer": 11,
    "system administrator": 20,
    "hardware engineer": 21,
    "designer": 18,
    "marketing or sales professional": 24,
    "security professional": 12,
    "developer, qa or test": 13,
    "product manager": 14,
    "project manager": 14,
    "engineering manager": 16,
    "senior executive (c-suite, vp, etc.)": 16,
}

SENIORITY_LEVELS = [
    # (seniority_key, level_name, min_years, max_years, seniority_rank)
    (1, "Internship", 0, 1, 1),
    (2, "Entry Level / Junior", 0, 2, 2),
    (3, "Associate", 1, 3, 3),
    (4, "Mid-Senior Level", 3, 7, 4),
    (5, "Director / Lead", 7, 12, 5),
    (6, "Executive", 10, 25, 6),
    (7, "Not Specified", 0, 0, 0),
]

CURRENCY_TO_USD = {
    "USD": 1.0,
    "EUR": 1.08,
    "GBP": 1.27,
    "CAD": 0.74,
    "AUD": 0.66,
    "INR": 0.012,
    "PKR": 0.0036,
    "CHF": 1.13,
    "SGD": 0.74,
    "JPY": 0.0067,
    "BRL": 0.20,
    "PLN": 0.25,
    "SEK": 0.095,
}

# Complete 50 US states + DC + PR
US_STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
    "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "DC": "District of Columbia", "PR": "Puerto Rico",
}

# Expanded global country metadata covering top Stack Overflow & job-market countries
COUNTRY_METADATA = {
    "US": ("United States", "North America", "USD"),
    "GB": ("United Kingdom", "Europe", "GBP"),
    "CA": ("Canada", "North America", "CAD"),
    "DE": ("Germany", "Europe", "EUR"),
    "IN": ("India", "Asia-Pacific", "INR"),
    "FR": ("France", "Europe", "EUR"),
    "AU": ("Australia", "Asia-Pacific", "AUD"),
    "NL": ("Netherlands", "Europe", "EUR"),
    "ES": ("Spain", "Europe", "EUR"),
    "IT": ("Italy", "Europe", "EUR"),
    "BR": ("Brazil", "Latin America", "BRL"),
    "PL": ("Poland", "Europe", "PLN"),
    "SE": ("Sweden", "Europe", "SEK"),
    "CH": ("Switzerland", "Europe", "CHF"),
    "SG": ("Singapore", "Asia-Pacific", "SGD"),
    "PK": ("Pakistan", "Asia-Pacific", "PKR"),
    "JP": ("Japan", "Asia-Pacific", "JPY"),
    "IE": ("Ireland", "Europe", "EUR"),
    "MX": ("Mexico", "Latin America", "USD"),
    "AE": ("United Arab Emirates", "Middle East & Africa", "USD"),
    "UA": ("Ukraine", "Europe", "USD"),
    "RU": ("Russian Federation", "Europe", "USD"),
    "AT": ("Austria", "Europe", "EUR"),
    "CZ": ("Czech Republic", "Europe", "EUR"),
    "IL": ("Israel", "Middle East & Africa", "USD"),
    "TR": ("Turkey", "Europe", "USD"),
    "BE": ("Belgium", "Europe", "EUR"),
    "DK": ("Denmark", "Europe", "EUR"),
    "PT": ("Portugal", "Europe", "EUR"),
    "NO": ("Norway", "Europe", "USD"),
    "RO": ("Romania", "Europe", "EUR"),
    "FI": ("Finland", "Europe", "EUR"),
    "NZ": ("New Zealand", "Asia-Pacific", "AUD"),
    "AR": ("Argentina", "Latin America", "USD"),
    "CO": ("Colombia", "Latin America", "USD"),
    "ZA": ("South Africa", "Middle East & Africa", "USD"),
    "GR": ("Greece", "Europe", "EUR"),
    "HU": ("Hungary", "Europe", "EUR"),
    "KR": ("South Korea", "Asia-Pacific", "USD"),
    "CN": ("China", "Asia-Pacific", "USD"),
    "TW": ("Taiwan", "Asia-Pacific", "USD"),
    "HK": ("Hong Kong", "Asia-Pacific", "USD"),
    "EG": ("Egypt", "Middle East & Africa", "USD"),
    "NG": ("Nigeria", "Middle East & Africa", "USD"),
    "SA": ("Saudi Arabia", "Middle East & Africa", "USD"),
    "CL": ("Chile", "Latin America", "USD"),
    "PH": ("Philippines", "Asia-Pacific", "USD"),
    "VN": ("Vietnam", "Asia-Pacific", "USD"),
}

COUNTRY_ALIASES = {
    "united states of america": "US",
    "united kingdom of great britain and northern ireland": "GB",
    "iran, islamic republic of...": "AE",
    "republic of korea": "KR",
    "south korea": "KR",
    "czechia": "CZ",
    "türkiye": "TR",
    "turkiye": "TR",
    "viet nam": "VN",
    "hong kong (s.a.r.)": "HK",
    "taiwan": "TW",
    "russian federation": "RU",
}

GENERIC_ATS_DOMAINS = {
    "click2apply.net", "smartrecruiters.com", "appcast.io", "greenhouse.io", "ultipro.com",
    "aplitrak.com", "jobsyn.org", "recruitics.com", "myworkdayjobs.com", "workday.com",
    "lever.co", "icims.com", "taleo.net", "bamboohr.com", "ashbyhq.com", "jobvite.com",
    "paycomonline.net", "adp.com", "brassring.com", "successfactors.com", "linkedin.com",
    "indeed.com", "ziprecruiter.com", "monster.com", "careerbuilder.com", "snagajob.com",
    "talent.com", "applytojob.com", "paylocity.com", "dayforcehcm.com", "oraclecloud.com",
    "phenompeople.com", "eightfold.ai", "rippling.com", "gusto.com", "breezy.hr",
    "apply.workable.com", "workable.com", "dejobs.org", "directemployers.org", "appone.com",
}


def build_role_dimensions() -> Tuple[pd.DataFrame, pd.DataFrame]:
    families = {}
    roles = []
    for r_key, r_title, f_key, f_name, dom, min_exp, _ in ROLE_TAXONOMY:
        if f_key not in families:
            families[f_key] = {
                "role_family_key": f_key,
                "family_name": f_name,
                "domain_area": dom,
            }
        roles.append({
            "role_key": r_key,
            "role_title_norm": r_title,
            "role_family_key": f_key,
            "min_experience": min_exp,
        })
    return pd.DataFrame(list(families.values())), pd.DataFrame(roles)


def map_title_to_role_key(title: str, desc_snippet: str = "") -> int:
    t = str(title or "").strip()
    t_lower = t.lower()

    if PHYSICAL_SECURITY_RE.search(t_lower):
        return 17
    if NONTECH_QA_RE.search(t_lower) and not TECH_QA_RE.search(t_lower):
        return 17

    for r_key, pat in ROLE_KEYWORD_REGEXES:
        if pat.search(t):
            return r_key

    # Only inspect description snippet when title is generic/ambiguous and NOT obviously non-tech
    if not NONTECH_TITLE_RE.search(t_lower) and GENERIC_TECH_TITLE_RE.search(t_lower):
        d = str(desc_snippet or "")[:450]
        if NONTECH_QA_RE.search(d) and not TECH_QA_RE.search(d):
            return 17
        for r_key, pat in ROLE_KEYWORD_REGEXES:
            if pat.search(d):
                return r_key

    return 17


def map_so_devtype_to_role_key(dev_type: str) -> int:
    if not dev_type or pd.isna(dev_type):
        return 17
    dt_lower = str(dev_type).strip().lower()
    if dt_lower in SO_DEVTYPE_TO_ROLE_KEY:
        return SO_DEVTYPE_TO_ROLE_KEY[dt_lower]
    for token in dt_lower.split(";"):
        tok = token.strip()
        if tok in SO_DEVTYPE_TO_ROLE_KEY:
            return SO_DEVTYPE_TO_ROLE_KEY[tok]
    return map_title_to_role_key(dt_lower)


def map_seniority_key(exp_level: str, title: str = "") -> int:
    el = str(exp_level or "").strip().lower()
    t = str(title or "").strip().lower()
    if "intern" in el or re.search(r"\bintern(?:ship)?\b", t):
        return 1
    if "entry" in el or re.search(r"\b(?:junior|jr\.?|grad|entry[- ]level)\b", t):
        return 2
    if "associate" in el:
        return 3
    if "mid-senior" in el or re.search(r"\b(?:senior|sr\.?|staff|principal)\b", t):
        return 4
    if "director" in el or re.search(r"\b(?:director|head of)\b", t):
        return 5
    if "executive" in el or re.search(r"\b(?:vp|vice president|chief|cto|cio|ceo|cfo)\b", t):
        return 6
    return 7


# ============================================================================
# 2. GEONAMES REFERENCE LOADER (Authentic `cities15000.txt`)
# ============================================================================
def load_geonames_and_locations() -> Tuple[pd.DataFrame, pd.DataFrame, Dict, pd.DataFrame]:
    """
    Reads GeoNames `cities15000.txt`, saves cleaned Silver city reference,
    and builds `dim_country`, `dim_location` (all US cities + top 800 global cities),
    and fast lookup dictionaries for city/state resolution.
    """
    geo_path = os.path.join(BRONZE_DIR, "cities15000.txt")
    cols = [
        "geonameid", "name", "asciiname", "alternatenames", "latitude", "longitude",
        "feature_class", "feature_code", "country_code", "cc2", "admin1", "admin2",
        "admin3", "admin4", "population", "elevation", "dem", "timezone", "modification_date",
    ]
    df_geo = pd.read_csv(geo_path, sep="\t", header=None, names=cols, low_memory=False, encoding="utf-8")
    df_geo["population"] = pd.to_numeric(df_geo["population"], errors="coerce").fillna(0).astype(int)
    df_geo = df_geo.sort_values("population", ascending=False)

    # Build dim_country
    countries = []
    iso_to_ckey = {}
    cname_to_ckey = {}
    c_idx = 1
    for iso, (cname, rgroup, curr) in COUNTRY_METADATA.items():
        countries.append({
            "country_key": c_idx,
            "country_name": cname,
            "iso_code": iso,
            "region_group": rgroup,
            "currency_code": curr,
        })
        iso_to_ckey[iso] = c_idx
        cname_to_ckey[cname.lower()] = c_idx
        c_idx += 1

    # Unknown / Global Remote country member
    countries.append({
        "country_key": c_idx,
        "country_name": "Global / Remote",
        "iso_code": "GL",
        "region_group": "Global",
        "currency_code": "USD",
    })
    iso_to_ckey["GL"] = c_idx
    cname_to_ckey["global / remote"] = c_idx
    for alias, iso_code in COUNTRY_ALIASES.items():
        if iso_code in iso_to_ckey:
            cname_to_ckey[alias] = iso_to_ckey[iso_code]

    df_country = pd.DataFrame(countries)

    # Include ALL US cities in GeoNames (3,400+) + top 800 major international cities
    df_us = df_geo[df_geo["country_code"] == "US"].drop_duplicates(subset=["asciiname", "admin1"])
    df_intl = (
        df_geo[(df_geo["country_code"] != "US") & (df_geo["country_code"].isin(iso_to_ckey.keys()))]
        .drop_duplicates(subset=["asciiname", "country_code"])
        .head(800)
    )
    df_selected_geo = pd.concat([df_us, df_intl], ignore_index=True)

    locations = []
    city_state_lookup = {}
    city_lookup = {}
    state_lookup = {}
    loc_idx = 1

    for r in df_selected_geo.itertuples(index=False):
        city_name = str(r.asciiname or r.name).strip()
        iso = str(r.country_code).strip()
        admin1 = str(r.admin1 or "").strip() if pd.notna(r.admin1) else ""
        lat = float(r.latitude)
        lon = float(r.longitude)
        pop = int(r.population)

        region_name = US_STATE_NAMES.get(admin1, admin1 if admin1 else city_name) if iso == "US" else (admin1 or city_name)
        c_key = iso_to_ckey.get(iso, iso_to_ckey["US"])

        locations.append({
            "location_key": loc_idx,
            "city": city_name,
            "region": str(region_name),
            "country_key": c_key,
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "population": pop,
        })

        city_lower = city_name.lower()
        if iso == "US" and admin1:
            cs_key = (city_lower, admin1.upper())
            if cs_key not in city_state_lookup:
                city_state_lookup[cs_key] = loc_idx
        if city_lower not in city_lookup:
            city_lookup[city_lower] = loc_idx
        if iso == "US" and admin1 in US_STATE_NAMES and admin1 not in state_lookup:
            # Because df_us is sorted by population desc, first city per state is its largest metro
            state_lookup[admin1] = loc_idx

        loc_idx += 1

    # Add US state-level aliases for "New York City", "Washington DC", etc.
    for alias_city, target_city in [
        ("new york city", "new york"),
        ("nyc", "new york"),
        ("washington dc", "washington"),
        ("washington d.c.", "washington"),
        ("st. louis", "st. louis"),
        ("saint louis", "st. louis"),
        ("saint paul", "saint paul"),
        ("st. paul", "saint paul"),
    ]:
        if alias_city not in city_lookup and target_city in city_lookup:
            city_lookup[alias_city] = city_lookup[target_city]

    # Default Remote / National US location
    remote_loc_key = loc_idx
    locations.append({
        "location_key": remote_loc_key,
        "city": "Remote / National",
        "region": "National / Remote",
        "country_key": iso_to_ckey["US"],
        "latitude": 39.828300,
        "longitude": -98.579500,
        "population": 0,
    })

    df_location = pd.DataFrame(locations)
    silver_geo = df_selected_geo[["geonameid", "asciiname", "country_code", "admin1", "latitude", "longitude", "population"]].copy()

    lookup_bundle = {
        "city_state_lookup": city_state_lookup,
        "city_lookup": city_lookup,
        "state_lookup": state_lookup,
        "iso_to_ckey": iso_to_ckey,
        "cname_to_ckey": cname_to_ckey,
        "remote_loc_key": remote_loc_key,
    }
    return df_country, df_location, lookup_bundle, silver_geo


def resolve_location_key(loc_raw: str, lookup_bundle: Dict) -> int:
    if not loc_raw or pd.isna(loc_raw):
        return lookup_bundle["remote_loc_key"]
    s = str(loc_raw).strip()
    s_lower = s.lower()
    if "remote" in s_lower or s_lower in {"united states", "usa", "us"}:
        return lookup_bundle["remote_loc_key"]

    # Handle "Greater Seattle Area", "Dallas-Fort Worth Metroplex", etc.
    metro_m = re.match(r"^(?:greater\s+)?([a-z\s.\-]+?)(?:\s+(?:metropolitan\s+)?area|\s+metro(?:plex)?)$", s_lower)
    if metro_m:
        cand = metro_m.group(1).strip()
        if cand in lookup_bundle["city_lookup"]:
            return lookup_bundle["city_lookup"][cand]

    parts = [p.strip() for p in s.split(",")]
    city_cand = parts[0].lower()
    state_cand = parts[1].strip().upper()[:2] if len(parts) > 1 and len(parts[1].strip()) >= 2 else ""

    if state_cand and (city_cand, state_cand) in lookup_bundle["city_state_lookup"]:
        return lookup_bundle["city_state_lookup"][(city_cand, state_cand)]

    if city_cand in lookup_bundle["city_lookup"]:
        return lookup_bundle["city_lookup"][city_cand]

    for p in parts[1:]:
        p_up = p.strip().upper()[:2]
        if p_up in lookup_bundle["state_lookup"]:
            return lookup_bundle["state_lookup"][p_up]

    # Check full state name (e.g., "California, United States")
    for st_code, st_name in US_STATE_NAMES.items():
        if st_name.lower() == city_cand and st_code in lookup_bundle["state_lookup"]:
            return lookup_bundle["state_lookup"][st_code]

    return lookup_bundle["remote_loc_key"]


# ============================================================================
# 3. SALARY NORMALIZATION (Hourly, Monthly, Weekly, Yearly -> Annual USD)
# ============================================================================
def normalize_salary_usd(min_sal, med_sal, max_sal, pay_period: str, currency: str) -> Tuple[float, float, float]:
    """
    Converts raw salary values and pay periods to standardized annual USD.
    Does NOT impute missing salaries (returns np.nan when absent, per Proposal).
    """
    vals = []
    for v in [min_sal, med_sal, max_sal]:
        if pd.notna(v):
            try:
                fv = float(v)
                if fv > 0:
                    vals.append(fv)
            except Exception:
                pass
    if not vals:
        return (np.nan, np.nan, np.nan)

    s_min = min(vals)
    s_max = max(vals)
    s_ann = float(np.mean([s_min, s_max]))

    period = str(pay_period or "YEARLY").strip().upper()
    if "HOUR" in period:
        mult = 2080.0
    elif "MONTH" in period:
        mult = 12.0
    elif "WEEK" in period:
        mult = 52.0
    elif "DAY" in period or "DAILY" in period:
        mult = 260.0
    elif "ONCE" in period:
        return (np.nan, np.nan, np.nan)
    else:
        mult = 2080.0 if s_ann < 250 else 1.0

    fx = CURRENCY_TO_USD.get(str(currency or "USD").strip().upper(), 1.0)
    s_min_usd = s_min * mult * fx
    s_max_usd = s_max * mult * fx
    s_ann_usd = s_ann * mult * fx

    # Filter extreme data-entry outliers (< $12,000/yr or > $750,000/yr)
    if s_ann_usd < 12000 or s_ann_usd > 750000:
        return (np.nan, np.nan, np.nan)

    return (round(s_min_usd, 2), round(s_max_usd, 2), round(s_ann_usd, 2))


# ============================================================================
# 4. HONEST COMPANY & INDUSTRY INFERENCE (NO RANDOM MODULO FABRICATION)
# ============================================================================
INDUSTRY_RULES = [
    (4, re.compile(r"\b(?:hospital|medical|healthcare|nursing|clinical|patient|pharmacy|pharma|dental|biotech|health care)\b", re.I)),
    (3, re.compile(r"\b(?:bank|banking|fintech|financial|insurance|mortgage|wealth|investment|trading|credit|accounting|payments)\b", re.I)),
    (5, re.compile(r"\b(?:retail|e-commerce|ecommerce|store|merchandising|grocery|apparel|consumer|hospitality|restaurant)\b", re.I)),
    (8, re.compile(r"\b(?:manufacturing|automotive|aerospace|industrial|logistics|supply chain|warehouse|trucking|construction|semiconductor)\b", re.I)),
    (9, re.compile(r"\b(?:university|college|school|education|edtech|academic|student|curriculum)\b", re.I)),
    (6, re.compile(r"\b(?:telecom|telecommunications|wireless|5g|fiber|network provider|broadband)\b", re.I)),
    (7, re.compile(r"\b(?:consulting|advisory|staffing|recruiting|audit|deloitte|accenture|capgemini|kpmg|pwc)\b", re.I)),
    (2, re.compile(r"\b(?:saas|software product|b2b software|software company|platform engineering|web application)\b", re.I)),
    (1, re.compile(r"\b(?:information technology|it services|cloud|cybersecurity|data engineering|technology solutions)\b", re.I)),
]


def extract_company_name_from_domain(domain: str, cid_int: int) -> str:
    if not domain or pd.isna(domain):
        return f"Employer #{cid_int}"
    d = str(domain).strip().lower()
    if d.startswith("www."):
        d = d[4:]
    for generic in GENERIC_ATS_DOMAINS:
        if d == generic or d.endswith("." + generic):
            return f"Employer #{cid_int}"
    # e.g. careers.hcahealthcare.com -> hcahealthcare
    parts = [p for p in d.split(".") if p and p not in {"careers", "jobs", "apply", "recruiting", "talent", "hire", "us", "com", "org", "net", "io", "co"}]
    if parts:
        brand = re.sub(r"[^a-z0-9]+", " ", parts[0]).strip().title()
        if len(brand) >= 3:
            return f"{brand} (#{cid_int})"
    return f"Employer #{cid_int}"


def infer_industry_key(text_corpus: str) -> int:
    for ind_key, pat in INDUSTRY_RULES:
        if pat.search(text_corpus):
            return ind_key
    return 10  # General Enterprise & Other


def infer_posting_volume_tier(posting_count: int) -> str:
    if posting_count >= 20:
        return "High-Volume Hirer (20+ Postings)"
    elif posting_count >= 6:
        return "Multi-Role Hirer (6-19 Postings)"
    elif posting_count >= 2:
        return "Active Hirer (2-5 Postings)"
    return "Single Posting (Unverified Size)"


# ============================================================================
# 5. DATA QUALITY & RECONCILIATION GATE
# ============================================================================
def run_quality_and_reconciliation_checks(
    bronze_counts: Dict[str, int],
    silver_counts: Dict[str, int],
    tables: Dict[str, pd.DataFrame],
) -> Dict:
    """
    Runs row-count reconciliation, PK uniqueness, FK referential integrity,
    null-preservation (no salary imputation), and coordinate/date range checks.
    Raises AssertionError if any critical warehouse integrity check fails.
    """
    checks = []

    def record(name: str, passed: bool, details: str):
        checks.append({"check": name, "status": "PASSED" if passed else "FAILED", "details": details})
        if not passed:
            raise AssertionError(f"ETL Quality Gate FAILED [{name}]: {details}")

    # 1. Primary Key Uniqueness
    pk_specs = [
        ("dim_industry", ["industry_key"]),
        ("dim_country", ["country_key"]),
        ("dim_role_family", ["role_family_key"]),
        ("dim_skill_category", ["category_key"]),
        ("dim_date", ["date_key"]),
        ("dim_company", ["company_key"]),
        ("dim_location", ["location_key"]),
        ("dim_role", ["role_key"]),
        ("dim_seniority", ["seniority_key"]),
        ("dim_source", ["source_key"]),
        ("dim_skill", ["skill_key"]),
        ("fact_job_posting", ["posting_key"]),
        ("fact_posting_skill", ["posting_key", "skill_key"]),
        ("fact_survey_response", ["response_key"]),
        ("fact_survey_skill", ["response_key", "skill_key"]),
        ("fact_skill_gap_result", ["gap_key"]),
        ("fact_historical_skill_trend", ["trend_key"]),
        ("fact_historical_salary_benchmark", ["benchmark_key"]),
    ]
    for tbl, cols in pk_specs:
        df = tables[tbl]
        dups = int(df.duplicated(subset=cols).sum())
        record(f"pk_unique:{tbl}", dups == 0, f"Duplicate PK count={dups} on {cols}")

    # 2. Foreign Key Referential Integrity
    fk_specs = [
        ("dim_company", "industry_key", "dim_industry", "industry_key"),
        ("dim_location", "country_key", "dim_country", "country_key"),
        ("dim_role", "role_family_key", "dim_role_family", "role_family_key"),
        ("dim_skill", "category_key", "dim_skill_category", "category_key"),
        ("fact_job_posting", "date_key", "dim_date", "date_key"),
        ("fact_job_posting", "company_key", "dim_company", "company_key"),
        ("fact_job_posting", "location_key", "dim_location", "location_key"),
        ("fact_job_posting", "role_key", "dim_role", "role_key"),
        ("fact_job_posting", "seniority_key", "dim_seniority", "seniority_key"),
        ("fact_job_posting", "source_key", "dim_source", "source_key"),
        ("fact_posting_skill", "posting_key", "fact_job_posting", "posting_key"),
        ("fact_posting_skill", "skill_key", "dim_skill", "skill_key"),
        ("fact_survey_response", "date_key", "dim_date", "date_key"),
        ("fact_survey_response", "role_key", "dim_role", "role_key"),
        ("fact_survey_response", "country_key", "dim_country", "country_key"),
        ("fact_survey_response", "seniority_key", "dim_seniority", "seniority_key"),
        ("fact_survey_skill", "response_key", "fact_survey_response", "response_key"),
        ("fact_survey_skill", "skill_key", "dim_skill", "skill_key"),
        ("fact_skill_gap_result", "role_key", "dim_role", "role_key"),
        ("fact_skill_gap_result", "skill_key", "dim_skill", "skill_key"),
        ("fact_historical_skill_trend", "date_key", "dim_date", "date_key"),
        ("fact_historical_skill_trend", "skill_key", "dim_skill", "skill_key"),
        ("fact_historical_skill_trend", "source_key", "dim_source", "source_key"),
        ("fact_historical_salary_benchmark", "date_key", "dim_date", "date_key"),
        ("fact_historical_salary_benchmark", "role_key", "dim_role", "role_key"),
        ("fact_historical_salary_benchmark", "seniority_key", "dim_seniority", "seniority_key"),
        ("fact_historical_salary_benchmark", "country_key", "dim_country", "country_key"),
        ("fact_historical_salary_benchmark", "source_key", "dim_source", "source_key"),
    ]
    for child_t, child_c, parent_t, parent_c in fk_specs:
        child_vals = set(tables[child_t][child_c].dropna().unique())
        parent_vals = set(tables[parent_t][parent_c].unique())
        orphans = len(child_vals - parent_vals)
        record(f"fk_integrity:{child_t}.{child_c}->{parent_t}", orphans == 0, f"Orphan FK count={orphans}")

    # 3. Domain, Historical Span & Range Checks
    fjp = tables["fact_job_posting"]
    sal_nonnull = int(fjp["salary_annual_usd"].notna().sum())
    sal_pct = sal_nonnull / max(1, len(fjp)) * 100.0
    record(
        "salary_no_silent_imputation",
        30.0 <= sal_pct <= 50.0,
        f"Disclosed salary coverage={sal_pct:.2f}% ({sal_nonnull:,}/{len(fjp):,}); missing retained as NULL",
    )

    dl = tables["dim_location"]
    valid_coords = bool(((dl["latitude"].between(-90, 90)) & (dl["longitude"].between(-180, 180))).all())
    record("geonames_coordinate_bounds", valid_coords, f"All {len(dl)} locations within lat[-90,90], lon[-180,180]")

    valid_dates = bool(fjp["date_key"].between(20230101, 20241231).all())
    record("posting_date_bounds", valid_dates, f"Date key range {int(fjp['date_key'].min())}..{int(fjp['date_key'].max())}")

    fhst = tables["fact_historical_skill_trend"]
    fhsb = tables["fact_historical_salary_benchmark"]
    so_yrs = sorted(fhst["year_num"].unique().tolist())
    sal_yrs = sorted(fhsb["year_num"].unique().tolist())
    record(
        "historical_span_2020_2025",
        so_yrs == [2020, 2021, 2022, 2023, 2024, 2025] and sal_yrs == [2020, 2021, 2022, 2023, 2024, 2025],
        f"SO survey years={so_yrs}, ai-jobs salary years={sal_yrs}",
    )

    return {
        "overall_status": "PASSED",
        "bronze_row_counts": bronze_counts,
        "silver_row_counts": silver_counts,
        "gold_row_counts": {k: int(len(v)) for k, v in tables.items()},
        "checks_passed": len(checks),
        "checks_total": len(checks),
        "checks": checks,
    }


# ============================================================================
# 6. MAIN PIPELINE EXECUTION
# ============================================================================
def run_full_pipeline():
    t0 = time.time()
    print("=" * 76)
    print("SKILLSCOPE DATA WAREHOUSE & ANALYTICS PIPELINE (BRONZE -> SILVER -> GOLD)")
    print("=" * 76)

    # 1. Initialize NLP Skill Extractor with ESCO Parquet Taxonomy
    esco_parquet = os.path.join(BRONZE_DIR, "data", "train-00000-of-00001-1c75e336a95e7a61.parquet")
    extractor = ESCOSkillExtractor(esco_parquet_path=esco_parquet)
    df_skill_cat, df_skill = extractor.get_dimension_tables()
    esco_bronze_cnt = len(extractor.esco_raw_df) if extractor.esco_raw_df is not None else 0
    print(f"[1/8] Loaded ESCO Taxonomy ({esco_bronze_cnt:,} occupations) -> {len(df_skill)} canonical skills across {len(df_skill_cat)} categories.")

    # Save Silver ESCO Taxonomy
    if extractor.esco_raw_df is not None:
        silver_esco = extractor.esco_raw_df.copy()
        silver_esco["job_title"] = silver_esco["job_title"].fillna("").astype(str).str.strip()
        silver_esco["skills"] = silver_esco["skills"].fillna("").astype(str).str.strip()
        silver_esco.to_parquet(os.path.join(SILVER_DIR, "silver_esco_taxonomy.parquet"), index=False)

    # 2. Load GeoNames & Build Location/Country Dimensions
    df_country, df_location, loc_bundle, silver_geo = load_geonames_and_locations()
    silver_geo.to_parquet(os.path.join(SILVER_DIR, "silver_geonames_cities.parquet"), index=False)
    print(f"[2/8] Built GeoNames Spatial Reference: {len(df_location):,} cities across {len(df_country)} countries.")

    # 3. Build Role, Role Family, Seniority, Industry & Source Dimensions
    df_role_family, df_role = build_role_dimensions()
    df_seniority = pd.DataFrame(
        SENIORITY_LEVELS,
        columns=["seniority_key", "level_name", "min_years", "max_years", "seniority_rank"],
    )
    df_source = pd.DataFrame([
        {"source_key": 1, "source_name": "Kaggle LinkedIn Job Postings", "platform_url": "https://www.linkedin.com/jobs", "collected_on": "2023-11-04"},
        {"source_key": 2, "source_name": "Stack Overflow Annual Developer Survey 2024", "platform_url": "https://survey.stackoverflow.co/2024", "collected_on": "2024-05-15"},
        {"source_key": 3, "source_name": "European Commission ESCO Taxonomy", "platform_url": "https://esco.ec.europa.eu", "collected_on": "2024-05-01"},
        {"source_key": 4, "source_name": "Stack Overflow Annual Developer Survey 2020", "platform_url": "https://survey.stackoverflow.co/2020", "collected_on": "2020-05-15"},
        {"source_key": 5, "source_name": "Stack Overflow Annual Developer Survey 2021", "platform_url": "https://survey.stackoverflow.co/2021", "collected_on": "2021-05-15"},
        {"source_key": 6, "source_name": "Stack Overflow Annual Developer Survey 2022", "platform_url": "https://survey.stackoverflow.co/2022", "collected_on": "2022-05-15"},
        {"source_key": 7, "source_name": "Stack Overflow Annual Developer Survey 2023", "platform_url": "https://survey.stackoverflow.co/2023", "collected_on": "2023-05-15"},
        {"source_key": 8, "source_name": "Stack Overflow Annual Developer Survey 2025", "platform_url": "https://survey.stackoverflow.co/2025", "collected_on": "2025-05-15"},
        {"source_key": 9, "source_name": "ai-jobs.net Global Tech Salaries (2020-2025)", "platform_url": "https://ai-jobs.net/salaries/", "collected_on": "2025-12-31"},
    ])

    # 4. Read & Clean Authentic LinkedIn Job Postings (Bronze -> Silver)
    li_csv = os.path.join(BRONZE_DIR, "job_postings.csv")
    print(f"[3/8] Reading authentic LinkedIn Job Postings from {li_csv}...")
    df_raw_li = pd.read_csv(li_csv, low_memory=False)
    raw_row_count = len(df_raw_li)

    # Safe HTML cleanup preserving word boundaries (never breaking `<b>T</b>rust`)
    df_raw_li["desc_clean"] = [clean_html_text(x) for x in df_raw_li["description"]]
    df_raw_li["title"] = df_raw_li["title"].fillna("Unspecified Role").astype(str).str.strip()
    df_li = df_raw_li.drop_duplicates(subset=["title", "company_id", "location"]).copy().reset_index(drop=True)
    dedup_row_count = len(df_li)
    print(f"      Reconciled LinkedIn rows: {raw_row_count:,} raw -> {dedup_row_count:,} deduplicated postings.")

    # Evaluate NLP Skill Extraction on INDEPENDENT 100-posting Ground Truth (`nlp/ground_truth_100.json`)
    eval_report = extractor.evaluate_100_sample_benchmark(df_li)
    print(
        f"[4/8] Independent 100-Posting NLP Benchmark -> "
        f"Precision: {eval_report['precision']*100:.2f}%, "
        f"Recall: {eval_report['recall']*100:.2f}%, "
        f"F1-Score: {eval_report['f1_score']*100:.2f}% "
        f"(Hard-Neg Clean Rate: {eval_report['hard_negative_clean_rate']*100:.1f}%)"
    )
    with open(os.path.join(GOLD_DIR, "nlp_evaluation_report.json"), "w", encoding="utf-8") as f:
        json.dump(eval_report, f, indent=2)
    pd.DataFrame(eval_report["samples"]).to_parquet(os.path.join(GOLD_DIR, "nlp_evaluation_samples.parquet"), index=False)

    # Build Industries & Companies (Honest domain extraction + text-inferred industry + posting-volume tier)
    industries_list = [
        (1, "Information Technology & Services", "Technology"),
        (2, "Computer Software & SaaS", "Technology"),
        (3, "Financial Services & FinTech", "Finance & Banking"),
        (4, "Healthcare & Pharmaceuticals", "Healthcare"),
        (5, "E-Commerce & Retail", "Consumer & Retail"),
        (6, "Telecommunications & Cloud", "Technology"),
        (7, "Management Consulting & Advisory", "Professional Services"),
        (8, "Manufacturing & Automotive", "Industrial & Engineering"),
        (9, "Education & EdTech", "Public & Education"),
        (10, "General Enterprise & Other", "Operations"),
    ]
    df_industry = pd.DataFrame(industries_list, columns=["industry_key", "industry_name", "sector"])

    comp_agg = {}
    for row in df_li[["company_id", "title", "desc_clean", "posting_domain"]].itertuples(index=False):
        cid = row.company_id
        if pd.isna(cid):
            continue
        cid_int = int(cid)
        if cid_int not in comp_agg:
            comp_agg[cid_int] = {
                "count": 0,
                "domain": row.posting_domain if pd.notna(row.posting_domain) else "",
                "snippets": [],
            }
        comp_agg[cid_int]["count"] += 1
        if not comp_agg[cid_int]["domain"] and pd.notna(row.posting_domain):
            comp_agg[cid_int]["domain"] = row.posting_domain
        if len(comp_agg[cid_int]["snippets"]) < 3:
            comp_agg[cid_int]["snippets"].append(f"{row.title} {row.desc_clean[:220]}")

    comp_rows = []
    cid_to_ckey = {}
    for idx, cid_int in enumerate(sorted(comp_agg.keys()), start=1):
        meta = comp_agg[cid_int]
        c_name = extract_company_name_from_domain(meta["domain"], cid_int)
        ind_key = infer_industry_key(" ".join(meta["snippets"]))
        s_band = infer_posting_volume_tier(meta["count"])
        comp_rows.append({
            "company_key": idx,
            "company_name": c_name,
            "size_band": s_band,
            "industry_key": ind_key,
            "effective_from": "2023-01-01",
            "effective_to": "9999-12-31",
            "is_current": 1,
        })
        cid_to_ckey[float(cid_int)] = idx

    unk_comp_key = len(comp_rows) + 1
    comp_rows.append({
        "company_key": unk_comp_key,
        "company_name": "Unknown / Confidential Employer",
        "size_band": "Unknown",
        "industry_key": 10,
        "effective_from": "2020-01-01",
        "effective_to": "9999-12-31",
        "is_current": 1,
    })
    df_company = pd.DataFrame(comp_rows)

    # Build dim_date spanning Jan 1, 2020 to Dec 31, 2026 (covers 2020-2025 history + 2026 forecasts)
    start_dt = datetime(2020, 1, 1)
    end_dt = datetime(2026, 12, 31)
    date_rows = []
    curr_dt = start_dt
    while curr_dt <= end_dt:
        d_key = int(curr_dt.strftime("%Y%m%d"))
        date_rows.append({
            "date_key": d_key,
            "full_date": curr_dt.strftime("%Y-%m-%d"),
            "day_of_month": curr_dt.day,
            "month_num": curr_dt.month,
            "month_name": curr_dt.strftime("%B"),
            "year_month": curr_dt.strftime("%Y-%m"),
            "quarter_num": (curr_dt.month - 1) // 3 + 1,
            "quarter_label": f"Q{(curr_dt.month - 1) // 3 + 1}",
            "year_num": curr_dt.year,
            "is_weekend": 1 if curr_dt.weekday() >= 5 else 0,
            "is_holiday": 1 if (curr_dt.month == 1 and curr_dt.day == 1) or (curr_dt.month == 12 and curr_dt.day == 25) else 0,
        })
        curr_dt += timedelta(days=1)
    df_date = pd.DataFrame(date_rows)
    valid_date_keys = set(df_date["date_key"].tolist())

    # Parse REAL posting timestamps (`original_listed_time` with fallback to `listed_time`)
    olt = pd.to_datetime(df_li["original_listed_time"], unit="ms", errors="coerce")
    lt = pd.to_datetime(df_li["listed_time"], unit="ms", errors="coerce")
    real_dt = olt.fillna(lt)

    # Process each LinkedIn Job Posting into Silver & Gold Fact + Bridge Skill Extraction
    print("[5/8] Transforming job postings (real timestamps, GeoNames, ESCO NLP extraction)...")
    silver_postings = []
    posting_facts = []
    posting_skill_facts = []

    for p_idx, row in enumerate(df_li.itertuples(index=False), start=1):
        nat_id = str(getattr(row, "job_id", p_idx))
        title = str(getattr(row, "title", "Unspecified Role"))[:290]
        desc = str(getattr(row, "desc_clean", ""))
        raw_skills_desc = getattr(row, "skills_desc", None)
        skills_desc = str(raw_skills_desc) if pd.notna(raw_skills_desc) else ""

        role_key = map_title_to_role_key(title, desc)
        sen_key = map_seniority_key(getattr(row, "formatted_experience_level", None), title)
        comp_id = getattr(row, "company_id", None)
        comp_key = cid_to_ckey.get(float(comp_id), unk_comp_key) if pd.notna(comp_id) else unk_comp_key
        loc_raw = getattr(row, "location", None)
        loc_key = resolve_location_key(loc_raw, loc_bundle)

        w_type = str(getattr(row, "formatted_work_type", None) or getattr(row, "work_type", None) or "Full-time").strip()
        rem_val = getattr(row, "remote_allowed", None)
        is_rem = 1 if (pd.notna(rem_val) and float(rem_val) == 1.0) or ("remote" in str(loc_raw or "").lower()) else 0

        s_min, s_max, s_ann = normalize_salary_usd(
            getattr(row, "min_salary", None),
            getattr(row, "med_salary", None),
            getattr(row, "max_salary", None),
            getattr(row, "pay_period", None),
            getattr(row, "currency", None),
        )

        # Authentic date_key from original_listed_time / listed_time
        dt_val = real_dt.iloc[p_idx - 1]
        if pd.notna(dt_val):
            d_key = int(dt_val.strftime("%Y%m%d"))
            if d_key not in valid_date_keys:
                d_key = 20230824
        else:
            d_key = 20230824

        posting_facts.append({
            "posting_key": p_idx,
            "natural_posting_id": nat_id,
            "date_key": d_key,
            "company_key": comp_key,
            "location_key": loc_key,
            "role_key": role_key,
            "seniority_key": sen_key,
            "source_key": 1,
            "raw_job_title": title,
            "work_type": w_type,
            "salary_min_usd": s_min,
            "salary_max_usd": s_max,
            "salary_annual_usd": s_ann,
            "is_remote": is_rem,
            "posting_count": 1,
        })

        silver_postings.append({
            "posting_key": p_idx,
            "job_id": nat_id,
            "posted_date": f"{d_key // 10000:04d}-{(d_key // 100) % 100:02d}-{d_key % 100:02d}",
            "title": title,
            "role_key": role_key,
            "seniority_key": sen_key,
            "location_raw": str(loc_raw) if pd.notna(loc_raw) else None,
            "location_key": loc_key,
            "work_type": w_type,
            "is_remote": is_rem,
            "salary_annual_usd": s_ann,
            "desc_char_len": len(desc),
        })

        # Extract ESCO skills from title + description + skills_desc
        extracted = extractor.extract_from_text(f"{title}. {desc}", skills_desc)
        for item in extracted:
            posting_skill_facts.append({
                "posting_key": p_idx,
                "skill_key": item["skill_key"],
                "mention_count": item["mention_count"],
                "confidence": item["confidence"],
                "extraction_method": "ESCO_NLP_Rule",
            })

    df_silver_postings = pd.DataFrame(silver_postings)
    df_fact_posting = pd.DataFrame(posting_facts)
    df_fact_posting_skill = pd.DataFrame(posting_skill_facts)

    # Save Silver posting & posting_skill tables
    df_silver_postings.to_parquet(os.path.join(SILVER_DIR, "silver_job_postings.parquet"), index=False)
    df_fact_posting_skill.to_parquet(os.path.join(SILVER_DIR, "silver_posting_skills.parquet"), index=False)

    salary_coverage_pct = df_fact_posting["salary_annual_usd"].notna().mean() * 100.0
    rem_fallback_pct = (df_fact_posting["location_key"] == loc_bundle["remote_loc_key"]).mean() * 100.0
    print(
        f"      Built `fact_job_posting` ({len(df_fact_posting):,} rows, salary coverage: {salary_coverage_pct:.1f}%, "
        f"GeoNames matched: {100.0 - rem_fallback_pct:.1f}%) and `fact_posting_skill` ({len(df_fact_posting_skill):,} skill links)."
    )

    # 5. Process ALL 65,437 Stack Overflow 2024 Developer Survey Respondents
    print("[6/8] Processing ALL Stack Overflow 2024 Developer Survey respondents (`survey_2024.parquet`)...")
    so_parquet = os.path.join(BRONZE_DIR, "survey_2024.parquet")
    df_so_raw = pd.read_parquet(so_parquet)
    so_raw_count = len(df_so_raw)

    # Symbolic name_to_key mappings (zero hardcoded integer bugs!)
    n2k = extractor.name_to_key
    so_token_to_skill_key = {}
    for s in extractor.skills_catalog:
        sk_key = s["skill_key"]
        so_token_to_skill_key[s["skill_name"].lower()] = sk_key
        for a in s["aliases"]:
            so_token_to_skill_key[a.lower()] = sk_key

    so_token_to_skill_key.update({
        "bash/shell (all shells)": n2k["Bash / Shell"],
        "bash/shell/powershell": n2k["Bash / Shell"],
        "bash/shell": n2k["Bash / Shell"],
        "powershell": n2k["Bash / Shell"],
        "html/css": n2k["HTML & CSS"],
        "c#": n2k["C#"],
        "c++": n2k["C++"],
        "go": n2k["Go"],
        "r": n2k["R"],
        "rust": n2k["Rust"],
        "swift": n2k["Swift"],
        "kotlin": n2k["Kotlin"],
        "scala": n2k["Scala"],
        "php": n2k["PHP"],
        "microsoft sql server": n2k["Microsoft SQL Server"],
        "postgresql": n2k["PostgreSQL"],
        "mysql": n2k["MySQL"],
        "mariadb": n2k["MySQL"],
        "oracle": n2k["Oracle Database"],
        "mongodb": n2k["MongoDB"],
        "dynamodb": n2k["MongoDB"],
        "cassandra": n2k["MongoDB"],
        "redis": n2k["Redis"],
        "elasticsearch": n2k["Redis"],
        "duckdb": n2k["SQL"],
        "amazon web services (aws)": n2k["AWS"],
        "aws": n2k["AWS"],
        "microsoft azure": n2k["Microsoft Azure"],
        "google cloud": n2k["Google Cloud Platform (GCP)"],
        "google cloud platform": n2k["Google Cloud Platform (GCP)"],
        "bigquery": n2k["BigQuery"],
        "snowflake": n2k["Snowflake"],
        "databricks": n2k["Databricks"],
        "databricks sql": n2k["Databricks"],
        "microsoft fabric": n2k["Power BI"],
        "docker": n2k["Docker"],
        "kubernetes": n2k["Kubernetes"],
        "terraform": n2k["Terraform & IaC"],
        "teraform": n2k["Terraform & IaC"],
        "ansible": n2k["Terraform & IaC"],
        "react": n2k["React"],
        "react.js": n2k["React"],
        "next.js": n2k["React"],
        "angular": n2k["Angular"],
        "angular.js": n2k["Angular"],
        "angularjs": n2k["Angular"],
        "vue.js": n2k["Vue.js"],
        "nuxt.js": n2k["Vue.js"],
        "node.js": n2k["Node.js"],
        "express": n2k["Node.js"],
        "nestjs": n2k["Node.js"],
        "fastapi": n2k["FastAPI & Flask"],
        "flask": n2k["FastAPI & Flask"],
        "django": n2k["FastAPI & Flask"],
        "spring": n2k["Spring Boot"],
        "spring boot": n2k["Spring Boot"],
        ".net": n2k[".NET Core"],
        ".net core": n2k[".NET Core"],
        ".net (5+)": n2k[".NET Core"],
        ".net (5+) ": n2k[".NET Core"],
        ".net framework (1.0 - 4.8)": n2k[".NET Core"],
        "asp.net core": n2k[".NET Core"],
        "asp.net": n2k[".NET Core"],
        "pandas": n2k["Pandas & NumPy"],
        "numpy": n2k["Pandas & NumPy"],
        "scikit-learn": n2k["Scikit-Learn"],
        "pytorch": n2k["PyTorch"],
        "torch/pytorch": n2k["PyTorch"],
        "tensorflow": n2k["TensorFlow"],
        "keras": n2k["TensorFlow"],
        "hugging face transformers": n2k["Generative AI & LLMs"],
        "chatgpt": n2k["Generative AI & LLMs"],
        "github copilot": n2k["Generative AI & LLMs"],
        "claude": n2k["Generative AI & LLMs"],
        "claude code": n2k["Generative AI & LLMs"],
        "anthropic: claude sonnet": n2k["Generative AI & LLMs"],
        "anthropic: claude opus": n2k["Generative AI & LLMs"],
        "anthropic: claude haiku": n2k["Generative AI & LLMs"],
        "google gemini": n2k["Generative AI & LLMs"],
        "google bard ai": n2k["Generative AI & LLMs"],
        "gemini (flash general purpose models)": n2k["Generative AI & LLMs"],
        "gemini (pro reasoning models)": n2k["Generative AI & LLMs"],
        "deepseek (r- reasoning models)": n2k["Generative AI & LLMs"],
        "deepseek (v- general purpose models)": n2k["Generative AI & LLMs"],
        "meta llama (all models)": n2k["Generative AI & LLMs"],
        "large language model": n2k["Generative AI & LLMs"],
        "cursor": n2k["Generative AI & LLMs"],
        "opencv": n2k["Computer Vision"],
        "apache spark": n2k["Apache Spark"],
        "hadoop": n2k["Apache Spark"],
        "apache kafka": n2k["Apache Kafka"],
        "rabbitmq": n2k["Apache Kafka"],
        "airflow": n2k["Apache Airflow"],
        "dbt": n2k["dbt"],
        "git": n2k["CI/CD & Git"],
        "github": n2k["CI/CD & Git"],
        "github discussions": n2k["CI/CD & Git"],
        "gitlab": n2k["CI/CD & Git"],
        "azure devops": n2k["CI/CD & Git"],
        "jira": n2k["Agile & Scrum"],
        "jira work management": n2k["Agile & Scrum"],
        "confluence": n2k["Agile & Scrum"],
        "ubuntu": n2k["Linux"],
        "debian": n2k["Linux"],
        "fedora": n2k["Linux"],
        "windows subsystem for linux (wsl)": n2k["Linux"],
        "red hat": n2k["Linux"],
        "linux": n2k["Linux"],
        "ruby": n2k["Ruby & Rails"],
        "ruby on rails": n2k["Ruby & Rails"],
        "playwright": n2k["Test Automation (Selenium / Cypress)"],
        "cypress": n2k["Test Automation (Selenium / Cypress)"],
        "selenium": n2k["Test Automation (Selenium / Cypress)"],
        "figma": n2k["UI/UX Design & Figma"],
        "grafana": n2k["Observability & Monitoring"],
        "prometheus": n2k["Observability & Monitoring"],
        "datadog": n2k["Observability & Monitoring"],
        "new relic": n2k["Observability & Monitoring"],
        "splunk": n2k["Observability & Monitoring"],
        "matlab": n2k["Statistical Tools (SAS / SPSS / MATLAB / Qlik)"],
        "sas": n2k["Statistical Tools (SAS / SPSS / MATLAB / Qlik)"],
        "zendesk": n2k["ServiceNow & ITIL / ITSM"],
    })

    ml_sub_keys = {n2k["PyTorch"], n2k["TensorFlow"], n2k["Scikit-Learn"]}
    ml_key = n2k["Machine Learning"]

    so_cols_needed = [
        "ResponseId", "Country", "DevType", "YearsCodePro", "ConvertedCompYearly",
        "LanguageHaveWorkedWith", "DatabaseHaveWorkedWith", "PlatformHaveWorkedWith",
        "WebframeHaveWorkedWith", "MiscTechHaveWorkedWith", "ToolsTechHaveWorkedWith",
        "OfficeStackAsyncHaveWorkedWith", "AISearchDevHaveWorkedWith", "OpSysProfessional use",
    ]
    df_so_sub = df_so_raw[[c for c in so_cols_needed if c in df_so_raw.columns]].copy()

    survey_facts = []
    survey_skill_facts = []

    for r_idx, srow in enumerate(df_so_sub.itertuples(index=False), start=1):
        dev_type = getattr(srow, "DevType", None)
        r_key = map_so_devtype_to_role_key(dev_type)
        c_raw = str(getattr(srow, "Country", "") or "").strip().lower()
        c_key = loc_bundle["cname_to_ckey"].get(c_raw, loc_bundle["iso_to_ckey"]["GL"])

        # Parse YearsCodePro honestly (keep missing as None, seniority_key=7 'Not Specified')
        y_raw_val = getattr(srow, "YearsCodePro", None)
        exp_yrs = np.nan
        sen_key = 7
        if pd.notna(y_raw_val):
            y_raw = str(y_raw_val).strip().lower()
            if "less than" in y_raw:
                exp_yrs = 0.5
            elif "more than" in y_raw:
                exp_yrs = 30.0
            else:
                try:
                    exp_yrs = float(y_raw)
                except Exception:
                    exp_yrs = np.nan

        if pd.notna(exp_yrs):
            if exp_yrs < 2:
                sen_key = 2
            elif exp_yrs < 4:
                sen_key = 3
            elif exp_yrs < 8:
                sen_key = 4
            elif exp_yrs < 13:
                sen_key = 5
            else:
                sen_key = 6

        comp_val = getattr(srow, "ConvertedCompYearly", None)
        sal_usd = np.nan
        if pd.notna(comp_val):
            try:
                fv = float(comp_val)
                if 5000 <= fv <= 750000:
                    sal_usd = round(fv, 2)
            except Exception:
                pass

        tech_fields = [
            getattr(srow, "LanguageHaveWorkedWith", None),
            getattr(srow, "DatabaseHaveWorkedWith", None),
            getattr(srow, "PlatformHaveWorkedWith", None),
            getattr(srow, "WebframeHaveWorkedWith", None),
            getattr(srow, "MiscTechHaveWorkedWith", None),
            getattr(srow, "ToolsTechHaveWorkedWith", None),
            getattr(srow, "OfficeStackAsyncHaveWorkedWith", None),
            getattr(srow, "AISearchDevHaveWorkedWith", None),
            getattr(srow, "_13", None) if hasattr(srow, "_13") else None,  # OpSysProfessional use (space in col name)
        ]
        raw_tools = ";".join(str(x) for x in tech_fields if pd.notna(x))
        matched_skeys = set()
        for tok in raw_tools.split(";"):
            t_clean = tok.strip().lower()
            if t_clean in so_token_to_skill_key:
                matched_skeys.add(so_token_to_skill_key[t_clean])
        if ml_sub_keys & matched_skeys:
            matched_skeys.add(ml_key)

        reported_names = [extractor.key_to_name[k] for k in sorted(matched_skeys)]

        survey_facts.append({
            "response_key": r_idx,
            "date_key": 20240515,
            "role_key": r_key,
            "country_key": c_key,
            "seniority_key": sen_key,
            "source_key": 2,
            "salary_usd": sal_usd,
            "experience_years": round(float(exp_yrs), 1) if pd.notna(exp_yrs) else np.nan,
            "reported_skills_csv": ", ".join(reported_names),
        })

        for sk_key in matched_skeys:
            survey_skill_facts.append({
                "response_key": r_idx,
                "skill_key": sk_key,
            })

    df_fact_survey = pd.DataFrame(survey_facts)
    df_fact_survey_skill = pd.DataFrame(survey_skill_facts)
    df_fact_survey.to_parquet(os.path.join(SILVER_DIR, "silver_survey_responses.parquet"), index=False)
    print(
        f"      Built `fact_survey_response` ({len(df_fact_survey):,} / {so_raw_count:,} respondents) "
        f"and `fact_survey_skill` ({len(df_fact_survey_skill):,} respondent-skill links)."
    )

    # 5b. Process ALL 6 Stack Overflow Annual Surveys (2020-2025) into `fact_historical_skill_trend`
    print("[6b/8] Processing 2020-2025 Stack Overflow cohorts (`survey_2020..2025.parquet`)...")
    import pyarrow.parquet as pq

    so_source_map = {2020: 4, 2021: 5, 2022: 6, 2023: 7, 2024: 2, 2025: 8}
    so_yearly_raw_counts = {}
    hist_trend_rows = []
    silver_hist_rows = []
    all_skill_keys = sorted(df_skill["skill_key"].astype(int).tolist())

    for yr in [2020, 2021, 2022, 2023, 2024, 2025]:
        yr_path = os.path.join(BRONZE_DIR, f"survey_{yr}.parquet")
        pf = pq.ParquetFile(yr_path)
        all_cols = pf.schema_arrow.names
        tech_cols = [
            c for c in all_cols
            if (
                (c.lower().endswith("haveworkedwith") or c.lower().endswith("workedwith"))
                and "want" not in c.lower()
                and "desire" not in c.lower()
                and "admired" not in c.lower()
            )
            or c in ("OpSys", "OpSysProfessional use", "AIToolCurrently Using")
        ]
        sal_col = "ConvertedCompYearly" if "ConvertedCompYearly" in all_cols else ("ConvertedComp" if "ConvertedComp" in all_cols else None)
        read_cols = list(dict.fromkeys(tech_cols + ([sal_col] if sal_col else [])))
        df_yr = pd.read_parquet(yr_path, columns=read_cols)
        yr_tot = len(df_yr)
        so_yearly_raw_counts[yr] = yr_tot

        skill_cnt = {k: 0 for k in all_skill_keys}
        skill_sals = {k: [] for k in all_skill_keys}

        # Convert columns to Python lists for fast single-pass scanning
        tech_arrays = [df_yr[c].tolist() for c in tech_cols]
        sal_arr = pd.to_numeric(df_yr[sal_col], errors="coerce").tolist() if sal_col else [np.nan] * yr_tot

        for idx_row in range(yr_tot):
            matched_skeys = set()
            for arr in tech_arrays:
                cell = arr[idx_row]
                if cell is not None and isinstance(cell, str) and cell:
                    for tok in cell.split(";"):
                        k_found = so_token_to_skill_key.get(tok.strip().lower())
                        if k_found is not None:
                            matched_skeys.add(k_found)
            if not matched_skeys:
                continue
            if ml_sub_keys & matched_skeys:
                matched_skeys.add(ml_key)

            s_val = sal_arr[idx_row]
            valid_sal = s_val if (s_val is not None and not np.isnan(s_val) and 5000.0 <= s_val <= 750000.0) else None
            for sk_k in matched_skeys:
                skill_cnt[sk_k] += 1
                if valid_sal is not None:
                    skill_sals[sk_k].append(float(valid_sal))

        for sk_k in all_skill_keys:
            rcnt = skill_cnt[sk_k]
            s_list = skill_sals[sk_k]
            med_sal = round(float(np.median(s_list)), 2) if len(s_list) >= 10 else np.nan
            adopt = round((rcnt / max(1, yr_tot)) * 100.0, 2)
            row_dict = {
                "date_key": yr * 10000 + 515,
                "year_num": yr,
                "skill_key": sk_k,
                "source_key": so_source_map[yr],
                "respondent_count": int(rcnt),
                "year_total_respondents": int(yr_tot),
                "adoption_pct": adopt,
                "median_salary_usd": med_sal,
                "salary_sample_count": int(len(s_list)),
            }
            hist_trend_rows.append(row_dict)
            silver_hist_rows.append({"skill_name": extractor.key_to_name[sk_k], **row_dict})

    df_hist_trend = pd.DataFrame(hist_trend_rows).sort_values(["skill_key", "year_num"]).reset_index(drop=True)
    prev_adopt = df_hist_trend.groupby("skill_key")["adoption_pct"].shift(1)
    df_hist_trend["yoy_adoption_change_pp"] = (df_hist_trend["adoption_pct"] - prev_adopt).round(2)
    df_hist_trend["yoy_growth_pct"] = np.where(
        prev_adopt >= 0.20,
        ((df_hist_trend["adoption_pct"] - prev_adopt) / prev_adopt * 100.0).round(2),
        np.nan,
    )
    df_hist_trend.insert(0, "trend_key", range(1, len(df_hist_trend) + 1))

    df_silver_hist = pd.DataFrame(silver_hist_rows)
    df_silver_hist.to_parquet(os.path.join(SILVER_DIR, "silver_historical_survey_yearly.parquet"), index=False)
    total_so_hist = sum(so_yearly_raw_counts.values())
    print(f"      Built `fact_historical_skill_trend` ({len(df_hist_trend):,} rows spanning 2020-2025 across {total_so_hist:,} total respondents).")

    # 5c. Process ALL 2020-2025 Global Tech Salaries (`ai_jobs_salaries_2020_2025.csv`)
    ai_sal_csv = os.path.join(BRONZE_DIR, "ai_jobs_salaries_2020_2025.csv")
    df_ai_raw = pd.read_csv(ai_sal_csv, low_memory=False)
    ai_raw_count = len(df_ai_raw)
    df_ai = df_ai_raw[df_ai_raw["salary_in_usd"].between(12000, 750000)].copy()

    exp_map_ai = {"EN": 2, "MI": 4, "SE": 5, "EX": 6}
    mode_map_ai = {0: "On-Site", 50: "Hybrid", 100: "Remote"}

    df_ai["role_key"] = [map_title_to_role_key(t, "") for t in df_ai["job_title"]]
    df_ai["seniority_key"] = df_ai["experience_level"].astype(str).str.upper().map(exp_map_ai).fillna(7).astype(int)
    df_ai["country_key"] = df_ai["company_location"].astype(str).str.upper().map(loc_bundle["iso_to_ckey"]).fillna(loc_bundle["iso_to_ckey"]["GL"]).astype(int)
    df_ai["work_mode"] = pd.to_numeric(df_ai["remote_ratio"], errors="coerce").fillna(-1).astype(int).map(mode_map_ai).fillna("Hybrid")
    df_ai["year_num"] = df_ai["work_year"].astype(int)
    df_ai["date_key"] = df_ai["year_num"] * 10000 + 615

    df_ai.to_parquet(os.path.join(SILVER_DIR, "silver_ai_jobs_salaries.parquet"), index=False)

    df_hist_sal_bm = (
        df_ai.groupby(["date_key", "year_num", "role_key", "seniority_key", "country_key", "work_mode"], as_index=False)
        .agg(
            record_count=("salary_in_usd", "count"),
            median_salary_usd=("salary_in_usd", "median"),
            mean_salary_usd=("salary_in_usd", "mean"),
            p25_salary_usd=("salary_in_usd", lambda s: float(np.percentile(s, 25))),
            p75_salary_usd=("salary_in_usd", lambda s: float(np.percentile(s, 75))),
        )
    )
    df_hist_sal_bm["source_key"] = 9
    for c in ["median_salary_usd", "mean_salary_usd", "p25_salary_usd", "p75_salary_usd"]:
        df_hist_sal_bm[c] = df_hist_sal_bm[c].round(2)
    df_hist_sal_bm = df_hist_sal_bm[
        ["date_key", "year_num", "role_key", "seniority_key", "country_key", "source_key", "work_mode", "record_count", "median_salary_usd", "mean_salary_usd", "p25_salary_usd", "p75_salary_usd"]
    ].sort_values(["year_num", "role_key", "country_key"]).reset_index(drop=True)
    df_hist_sal_bm.insert(0, "benchmark_key", range(1, len(df_hist_sal_bm) + 1))
    print(f"      Built `fact_historical_salary_benchmark` ({len(df_hist_sal_bm):,} benchmark cells from {len(df_ai):,} / {ai_raw_count:,} salary records, 2020-2025).")

    # 6. Build Gold Layer Aggregates & Run AI Fuzzy Skill-Gap Recommender
    print("[7/8] Computing Gold Layer Aggregates & Running Fuzzy Skill-Gap Recommender...")

    fps_enriched = df_fact_posting_skill.merge(
        df_fact_posting[["posting_key", "date_key", "role_key", "seniority_key", "location_key", "salary_annual_usd", "is_remote"]],
        on="posting_key",
        how="left",
    ).merge(
        df_date[["date_key", "year_num", "month_num", "year_month"]],
        on="date_key",
        how="left",
    ).merge(
        df_skill[["skill_key", "skill_name", "category_key", "is_emerging"]],
        on="skill_key",
        how="left",
    )

    gold_monthly = (
        fps_enriched.groupby(["year_month", "year_num", "month_num", "skill_key", "skill_name"], as_index=False)
        .agg(
            posting_mentions=("posting_key", "nunique"),
            avg_salary_usd=("salary_annual_usd", "mean"),
        )
    )

    # Role-Skill Profiles (Gold table for Skills Mart & Fuzzy Recommender Knowledge Base)
    role_totals = fps_enriched.groupby("role_key")["posting_key"].nunique().to_dict()
    role_median_sal = df_fact_posting.groupby("role_key")["salary_annual_usd"].median().to_dict()
    overall_median_sal = float(df_fact_posting["salary_annual_usd"].median() or 83200.0)
    tech_fps = fps_enriched[fps_enriched["role_key"] != 17]
    total_postings_with_skills = max(1, tech_fps["posting_key"].nunique())
    global_skill_share = (
        df_fact_posting_skill.groupby("skill_key")["posting_key"].nunique() / total_postings_with_skills
    ).to_dict()

    # Global per-skill median salary & sample count (only used as fallback when >= 3 disclosed salaries exist)
    global_skill_sal_stats = (
        fps_enriched.dropna(subset=["salary_annual_usd"])
        .groupby("skill_key")["salary_annual_usd"]
        .agg(["count", "median"])
        .to_dict(orient="index")
    )

    role_skill_stats = (
        fps_enriched.groupby(["role_key", "skill_key", "skill_name"], as_index=False)
        .agg(
            posting_count=("posting_key", "nunique"),
            salary_sample_count=("salary_annual_usd", "count"),
            median_skill_salary_usd=("salary_annual_usd", "median"),
            mean_skill_salary_usd=("salary_annual_usd", "mean"),
        )
    )

    profile_rows = []
    for r in role_skill_stats.itertuples(index=False):
        r_key = int(r.role_key)
        sk_key = int(r.skill_key)
        p_cnt = int(r.posting_count)
        sal_cnt = int(r.salary_sample_count)
        r_tot = max(1, role_totals.get(r_key, 1))
        demand_pct = (p_cnt / r_tot) * 100.0

        base_sal = role_median_sal.get(r_key, overall_median_sal)
        if pd.isna(base_sal) or base_sal <= 0:
            base_sal = overall_median_sal

        sk_sal = r.median_skill_salary_usd
        # Honest salary premium: require >= 3 disclosed salary rows in role, else fallback to global skill median (if >= 3), else 0% premium (NO +8% fabrication)
        if sal_cnt >= 3 and pd.notna(sk_sal) and sk_sal > 0:
            effective_sal = float(sk_sal)
            premium_pct = ((effective_sal - base_sal) / base_sal) * 100.0
        elif sk_key in global_skill_sal_stats and global_skill_sal_stats[sk_key]["count"] >= 3:
            effective_sal = float(global_skill_sal_stats[sk_key]["median"])
            premium_pct = ((effective_sal - overall_median_sal) / overall_median_sal) * 100.0
        else:
            effective_sal = np.nan
            premium_pct = 0.0

        global_share = max(0.001, global_skill_share.get(sk_key, 0.01))
        lift = (p_cnt / r_tot) / global_share

        profile_rows.append({
            "role_key": r_key,
            "skill_key": sk_key,
            "skill_name": r.skill_name,
            "posting_count": p_cnt,
            "role_total_postings": r_tot,
            "demand_pct": round(demand_pct, 2),
            "salary_sample_count": sal_cnt,
            "median_skill_salary_usd": round(effective_sal, 2) if pd.notna(effective_sal) else np.nan,
            "role_base_salary_usd": round(float(base_sal), 2),
            "salary_premium_pct": round(float(np.clip(premium_pct, -25.0, 55.0)), 2),
            "role_lift": round(float(lift), 2),
            "is_core_skill": 1 if demand_pct >= 18.0 else 0,
            "is_differentiating": 1 if lift >= 1.45 else 0,
        })
    df_role_skill_profiles = pd.DataFrame(profile_rows)

    # Compute Skill Co-occurrence Pairs (Gold Layer)
    sk_postings = df_fact_posting_skill.groupby("skill_key")["posting_key"].apply(set).to_dict()
    cooc_rows = []
    skill_keys_sorted = sorted(sk_postings.keys())
    for i, k1 in enumerate(skill_keys_sorted):
        set1 = sk_postings[k1]
        if len(set1) < 5:
            continue
        for k2 in skill_keys_sorted[i + 1:]:
            set2 = sk_postings[k2]
            if len(set2) < 5:
                continue
            inter = len(set1 & set2)
            if inter >= 3:
                union = len(set1 | set2)
                jaccard = inter / union if union > 0 else 0.0
                cond_prob = inter / min(len(set1), len(set2))
                strength = round(min(1.0, 0.5 * jaccard + 0.5 * cond_prob), 4)
                cooc_rows.append({
                    "skill_key_a": int(k1),
                    "skill_name_a": extractor.key_to_name[int(k1)],
                    "skill_key_b": int(k2),
                    "skill_name_b": extractor.key_to_name[int(k2)],
                    "co_posting_count": int(inter),
                    "jaccard_index": round(jaccard, 4),
                    "conditional_prob": round(cond_prob, 4),
                    "cooccurrence_strength": strength,
                })
    df_cooccurrence = pd.DataFrame(cooc_rows).sort_values("co_posting_count", ascending=False)

    # Build Survey vs Market Gold Comparison Table
    so_resp_total = max(1, len(df_fact_survey))
    so_skill_counts = df_fact_survey_skill.groupby("skill_key")["response_key"].nunique().to_dict()
    so_skill_sal = (
        df_fact_survey_skill.merge(df_fact_survey[["response_key", "salary_usd"]], on="response_key")
        .groupby("skill_key")["salary_usd"]
        .median()
        .to_dict()
    )
    mkt_skill_counts = df_fact_posting_skill.groupby("skill_key")["posting_key"].nunique().to_dict()
    mkt_skill_sal = fps_enriched.groupby("skill_key")["salary_annual_usd"].median().to_dict()

    svm_rows = []
    for srow in df_skill.itertuples(index=False):
        sk_key = int(srow.skill_key)
        m_cnt = mkt_skill_counts.get(sk_key, 0)
        s_cnt = so_skill_counts.get(sk_key, 0)
        m_pct = round((m_cnt / total_postings_with_skills) * 100.0, 2)
        s_pct = round((s_cnt / so_resp_total) * 100.0, 2)
        m_sal = mkt_skill_sal.get(sk_key, np.nan)
        s_sal = so_skill_sal.get(sk_key, np.nan)
        svm_rows.append({
            "skill_key": sk_key,
            "skill_name": srow.skill_name,
            "category_key": int(srow.category_key),
            "market_posting_count": int(m_cnt),
            "market_demand_pct": m_pct,
            "survey_respondent_count": int(s_cnt),
            "survey_usage_pct": s_pct,
            "supply_demand_gap_pct": round(m_pct - s_pct, 2),
            "market_median_salary_usd": round(float(m_sal), 2) if pd.notna(m_sal) else None,
            "survey_median_salary_usd": round(float(s_sal), 2) if pd.notna(s_sal) else None,
        })
    df_survey_vs_market = pd.DataFrame(svm_rows)

    # Run Fuzzy Skill-Gap Recommender across representative learner personas & target roles
    recommender = FuzzySkillGapRecommender(
        role_skill_profiles_df=df_role_skill_profiles,
        cooccurrence_df=df_cooccurrence,
        skills_df=df_skill,
        roles_df=df_role,
    )

    sample_personas = [
        ("BSDS_Student_Karachi", "FAST-NUCES BS Data Science Student (Python, SQL, Pandas)", [n2k["Python"], n2k["SQL"], n2k["Pandas & NumPy"], n2k["Statistics & A/B Testing"], n2k["Excel"]]),
        ("Junior_BI_Analyst", "Junior BI Analyst (Excel, SQL, Power BI)", [n2k["SQL"], n2k["Power BI"], n2k["Excel"], n2k["Stakeholder Communication"]]),
        ("Web_Dev_Career_Changer", "Frontend Web Developer (JS, HTML/CSS, React, Git)", [n2k["JavaScript"], n2k["React"], n2k["HTML & CSS"], n2k["CI/CD & Git"]]),
        ("Backend_Python_Dev", "Python Backend Engineer (Python, SQL, FastAPI, Docker, Git)", [n2k["Python"], n2k["SQL"], n2k["FastAPI & Flask"], n2k["Docker"], n2k["CI/CD & Git"]]),
        ("Data_Analyst_to_DE", "Data Analyst Upskilling to Data Engineer (Python, SQL, Tableau, Excel)", [n2k["Python"], n2k["SQL"], n2k["Tableau"], n2k["Excel"]]),
    ]
    target_role_keys = [1, 2, 3, 4, 5, 7, 8, 9, 11, 12, 13, 14, 15, 18, 19, 20, 23, 25]

    gap_result_frames = []
    for prof_id, prof_label, known_keys in sample_personas:
        for t_role_key in target_role_keys:
            _, rec_df = recommender.recommend_for_profile(
                profile_id=prof_id,
                profile_label=prof_label,
                role_key=t_role_key,
                known_skill_keys=known_keys,
                top_n=12,
            )
            if not rec_df.empty:
                gap_result_frames.append(rec_df)

    df_fact_skill_gap = pd.concat(gap_result_frames, ignore_index=True)
    df_fact_skill_gap.insert(0, "gap_key", range(1, len(df_fact_skill_gap) + 1))
    print(f"      Generated `fact_skill_gap_result` ({len(df_fact_skill_gap):,} fuzzy skill-gap recommendations).")

    # 7. Run Data Quality & Reconciliation Gate before writing Gold
    tables_to_save = {
        "dim_industry": df_industry,
        "dim_country": df_country,
        "dim_role_family": df_role_family,
        "dim_skill_category": df_skill_cat,
        "dim_date": df_date,
        "dim_company": df_company,
        "dim_location": df_location,
        "dim_role": df_role,
        "dim_seniority": df_seniority,
        "dim_source": df_source,
        "dim_skill": df_skill,
        "fact_job_posting": df_fact_posting,
        "fact_posting_skill": df_fact_posting_skill,
        "fact_survey_response": df_fact_survey,
        "fact_survey_skill": df_fact_survey_skill,
        "fact_skill_gap_result": df_fact_skill_gap,
        "fact_historical_skill_trend": df_hist_trend,
        "fact_historical_salary_benchmark": df_hist_sal_bm,
        "gold_monthly_skill_demand": gold_monthly,
        "gold_skill_cooccurrence": df_cooccurrence,
        "gold_role_skill_profiles": df_role_skill_profiles,
        "gold_survey_vs_market": df_survey_vs_market,
    }

    bronze_counts = {
        "linkedin_job_postings_raw": raw_row_count,
        "stackoverflow_survey_2024_raw": so_raw_count,
        "stackoverflow_survey_2020_2025_total_raw": total_so_hist,
        "stackoverflow_survey_yearly_raw": so_yearly_raw_counts,
        "ai_jobs_salaries_2020_2025_raw": ai_raw_count,
        "esco_occupations_raw": esco_bronze_cnt,
        "geonames_cities_raw": int(len(pd.read_csv(os.path.join(BRONZE_DIR, "cities15000.txt"), sep="\t", usecols=[0], header=None))),
    }
    silver_counts = {
        "silver_job_postings": len(df_silver_postings),
        "silver_posting_skills": len(df_fact_posting_skill),
        "silver_survey_responses": len(df_fact_survey),
        "silver_historical_survey_yearly": len(df_silver_hist),
        "silver_ai_jobs_salaries": len(df_ai),
        "silver_esco_taxonomy": esco_bronze_cnt,
        "silver_geonames_cities": len(silver_geo),
    }

    reconciliation = run_quality_and_reconciliation_checks(bronze_counts, silver_counts, tables_to_save)
    with open(os.path.join(GOLD_DIR, "etl_quality_reconciliation.json"), "w", encoding="utf-8") as f:
        json.dump(reconciliation, f, indent=2)
    print(f"[8/8] Data Quality Gate PASSED ({reconciliation['checks_passed']}/{reconciliation['checks_total']} checks). Writing Gold Parquet & Power BI CSVs...")

    for name, df in tables_to_save.items():
        df.to_parquet(os.path.join(GOLD_DIR, f"{name}.parquet"), index=False)
        df.to_csv(os.path.join(PBI_EXPORT_DIR, f"{name}.csv"), index=False)

    elapsed = time.time() - t0
    print("=" * 76)
    print(f"PIPELINE COMPLETE IN {elapsed:.1f}s! Silver, Gold Parquet & Power BI CSV tables saved.")
    print("=" * 76)


if __name__ == "__main__":
    run_full_pipeline()
