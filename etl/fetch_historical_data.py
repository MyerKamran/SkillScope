"""
SkillScope Authentic Multi-Year Historical Data Downloader (2020-2025)
Downloads verified public historical datasets into `data/bronze/`:
  1. Stack Overflow Annual Developer Surveys (2020, 2021, 2022, 2023, 2025)
     via HuggingFace `yeper/stack-overflow-developer-survey` (matching `survey_2024.parquet`).
  2. ai-jobs.net Global AI/ML/Data/Tech Salaries (2020-2025, 151k+ rows)
     via public GitHub CSV `foorilla/ai-jobs-net-salaries`.
Includes disk-space guardrails (aborts if C: drive < 250 MB free) and integrity checks.
"""

import os
import shutil
import sys
import urllib.request

import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRONZE_DIR = os.path.join(PROJECT_ROOT, "data", "bronze")
os.makedirs(BRONZE_DIR, exist_ok=True)

MIN_FREE_BYTES = 250 * 1024 * 1024  # 250 MB safety floor

HF_BASE = "https://huggingface.co/datasets/yeper/stack-overflow-developer-survey/resolve/main"
SURVEY_YEARS = [2020, 2021, 2022, 2023, 2025]
AI_JOBS_URL = "https://raw.githubusercontent.com/foorilla/ai-jobs-net-salaries/main/salaries.csv"


def check_free_space_mb(path: str) -> float:
    usage = shutil.disk_usage(path)
    return usage.free / (1024 * 1024)


def download_file(url: str, dest_path: str, min_bytes: int = 1_000_000) -> str:
    if os.path.exists(dest_path) and os.path.getsize(dest_path) >= min_bytes:
        return "SKIPPED (already exists)"

    free_bytes = shutil.disk_usage(BRONZE_DIR).free
    if free_bytes < MIN_FREE_BYTES:
        raise RuntimeError(
            f"Aborting download: only {free_bytes / (1024*1024):.1f} MB free on disk "
            f"(minimum required: {MIN_FREE_BYTES / (1024*1024):.0f} MB)."
        )

    tmp_path = dest_path + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": "SkillScope-ETL/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status} downloading {url}")
        with open(tmp_path, "wb") as out_f:
            while True:
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                out_f.write(chunk)

    if os.path.getsize(tmp_path) < min_bytes:
        os.remove(tmp_path)
        raise RuntimeError(f"Downloaded file too small (< {min_bytes} bytes): {dest_path}")

    os.replace(tmp_path, dest_path)
    return "DOWNLOADED"


def main():
    print("=" * 76)
    print("SKILLSCOPE HISTORICAL BRONZE DATA FETCHER (2020-2025)")
    print("=" * 76)
    print(f"Initial free disk space: {check_free_space_mb(BRONZE_DIR):.1f} MB")

    # 1. Stack Overflow Annual Developer Surveys (2020, 2021, 2022, 2023, 2025)
    for yr in SURVEY_YEARS:
        fname = f"survey_{yr}.parquet"
        dest = os.path.join(BRONZE_DIR, fname)
        url = f"{HF_BASE}/{fname}"
        status = download_file(url, dest, min_bytes=1_000_000)
        df_meta = pd.read_parquet(dest, columns=None)
        size_mb = os.path.getsize(dest) / (1024 * 1024)
        print(
            f"  [{status:22s}] {fname:24s} | {len(df_meta):>7,} rows x {len(df_meta.columns):>3} cols | {size_mb:6.2f} MB"
        )

    # Also report existing survey_2024.parquet for completeness
    s24 = os.path.join(BRONZE_DIR, "survey_2024.parquet")
    if os.path.exists(s24):
        df24 = pd.read_parquet(s24)
        print(
            f"  [{'EXISTING':22s}] {'survey_2024.parquet':24s} | {len(df24):>7,} rows x {len(df24.columns):>3} cols | {os.path.getsize(s24)/(1024*1024):6.2f} MB"
        )

    # 2. ai-jobs.net Global Tech Salaries (2020-2025)
    sal_dest = os.path.join(BRONZE_DIR, "ai_jobs_salaries_2020_2025.csv")
    sal_status = download_file(AI_JOBS_URL, sal_dest, min_bytes=1_000_000)
    df_sal = pd.read_csv(sal_dest, low_memory=False)
    sal_mb = os.path.getsize(sal_dest) / (1024 * 1024)
    yr_min, yr_max = int(df_sal["work_year"].min()), int(df_sal["work_year"].max())
    print(
        f"  [{sal_status:22s}] {'ai_jobs_salaries_2020_2025.csv':24s} | {len(df_sal):>7,} rows x {len(df_sal.columns):>3} cols | {sal_mb:6.2f} MB (years {yr_min}-{yr_max})"
    )

    free_after = check_free_space_mb(BRONZE_DIR)
    print(f"Remaining free disk space: {free_after:.1f} MB")
    print("=" * 76)


if __name__ == "__main__":
    main()
