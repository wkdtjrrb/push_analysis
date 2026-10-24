"""
[코드 요약]
카테고리별 동일 발송 제한률에서 Baseline과 Proposed의 오픈·클릭·구매 보존율 비교

[코드 내용]
1. modeling.py가 저장한 10개 모델로 Test 오픈 확률 예측
2. 각 카테고리에서 예측 오픈 확률 하위 10%, 20%, 30%를 제외 대상으로 선정
3. 실제 오픈·클릭·구매 기록을 이용해 보존율 계산
4. 카테고리별 결과와 전체 결과를 suppression_results.csv 하나로 저장
"""

import gc
import tempfile
from pathlib import Path

import duckdb
import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
TEST_PATH = ROOT / "data/processed/ignore_predictive_test.parquet"
OUTPUT_DIR = ROOT / "src/modeling/outputs"
MODEL_DIR = OUTPUT_DIR / "models"
CATEGORIES = ["Marketing", "Behavioral", "Interest", "Lifecycle", "Transactional"]
MODELS = ["Baseline", "Proposed"]
RATES = [10, 20, 30]
BEHAVIORS = ["is_opened", "is_clicked", "is_purchased"]
BATCH_SIZE = 100_000


def prepare_batch(df, features):
    for name in features:
        if name in ("channel", "topic"):
            df[name] = df[name].astype("string").fillna("__MISSING__").astype(str)
        else:
            df[name] = pd.to_numeric(df[name], errors="coerce").replace([np.inf, -np.inf], np.nan)
    return df


def retention(total, removed):
    return 100.0 * (total - removed) / total if total else np.nan


def evaluate_category(con, category, temporary_dir):
    artifacts = {}
    features = []
    for model_name in MODELS:
        path = MODEL_DIR / f"{category.lower()}_{model_name.lower()}_model.joblib"
        if not path.exists():
            raise FileNotFoundError(path)
        artifact = joblib.load(path)
        if artifact.get("category") != category or artifact.get("model") != model_name:
            raise ValueError(f"Invalid model metadata: {path}")
        artifacts[model_name] = artifact
        features.extend(artifact["features"])
    features = list(dict.fromkeys(features))
    count = int(con.execute("SELECT COUNT(*) FROM read_parquet(?) WHERE category = ?", [str(TEST_PATH), category]).fetchone()[0])
    if not count:
        raise ValueError(f"Empty category: {category}")
    labels = {
        name: np.memmap(temporary_dir / f"{name}.dat", dtype=np.uint8, mode="w+", shape=(count,))
        for name in BEHAVIORS
    }
    probabilities = {
        name: np.memmap(temporary_dir / f"{name}.dat", dtype=np.float32, mode="w+", shape=(count,))
        for name in MODELS
    }
    columns = list(dict.fromkeys(features + BEHAVIORS))
    selected = ", ".join('"' + name.replace('"', '""') + '"' for name in columns)
    batches = con.execute(
        f"SELECT {selected} FROM read_parquet(?) WHERE category = ?",
        [str(TEST_PATH), category]
    ).fetch_record_batch(rows_per_batch=BATCH_SIZE)
    offset = 0
    for batch in batches:
        df = batch.to_pandas()
        end = offset + len(df)
        for name in BEHAVIORS:
            values = pd.to_numeric(df[name], errors="coerce").to_numpy()
            if not np.isfinite(values).all() or not np.isin(values, [0, 1]).all():
                raise ValueError(f"Invalid label: {category}/{name}")
            labels[name][offset:end] = values.astype(np.uint8)
        prepare_batch(df, features)
        for name in MODELS:
            artifact = artifacts[name]
            scores = artifact["pipeline"].predict_proba(df[artifact["features"]])[:, 1]
            if not np.isfinite(scores).all():
                raise ValueError(f"Invalid probabilities: {category}/{name}")
            probabilities[name][offset:end] = scores.astype(np.float32)
        offset = end
        del df
    if offset != count:
        raise RuntimeError(f"Row count mismatch: {category}: {offset} != {count}")

    totals = {name: int(np.sum(labels[name], dtype=np.int64)) for name in BEHAVIORS}
    results = []
    for name in MODELS:
        max_removed = count * max(RATES) // 100
        if max_removed:
            excluded = np.argpartition(probabilities[name], max_removed - 1)[:max_removed]
            excluded = excluded[np.argsort(probabilities[name][excluded], kind="stable")]
        else:
            excluded = np.empty(0, dtype=np.int64)
        prefixes = {
            behavior: np.concatenate(([0], np.cumsum(labels[behavior][excluded], dtype=np.int64)))
            for behavior in BEHAVIORS
        }
        for rate in RATES:
            removed = count * rate // 100
            result = {
                "category": category,
                "target_suppression_pct": rate,
                "model": name,
                "total_sends": count,
                "removed_sends": removed
            }
            for behavior, prefix in prefixes.items():
                label = behavior.removeprefix("is_").replace("opened", "open").replace("clicked", "click").replace("purchased", "purchase")
                result[f"total_{label}"] = totals[behavior]
                result[f"removed_{label}"] = int(prefix[removed])
                result[f"{label}_retention_pct"] = retention(totals[behavior], int(prefix[removed]))
            results.append(result)
        del excluded, prefixes
        gc.collect()
    del artifacts, labels, probabilities
    gc.collect()
    print(f"Completed {category}: {count:,} Test pushes", flush=True)
    return results


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not TEST_PATH.exists():
        raise FileNotFoundError(TEST_PATH)
    con = duckdb.connect()
    available = set(con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(TEST_PATH)]).df()["column_name"])
    required = set(["category"] + BEHAVIORS)
    if required - available:
        raise ValueError(f"Missing columns: {sorted(required - available)}")
    rows = []
    with tempfile.TemporaryDirectory(prefix="push_evaluation_") as temp:
        for category in CATEGORIES:
            directory = Path(temp) / category
            directory.mkdir()
            rows.extend(evaluate_category(con, category, directory))
    con.close()
    detail = pd.DataFrame(rows)
    count_columns = ["total_sends", "removed_sends", "total_open", "removed_open", "total_click", "removed_click", "total_purchase", "removed_purchase"]
    overall = detail.groupby(["target_suppression_pct", "model"], as_index=False)[count_columns].sum()
    overall.insert(0, "category", "TOTAL")
    for label in ("open", "click", "purchase"):
        overall[f"{label}_retention_pct"] = [
            retention(total, removed)
            for total, removed in zip(overall[f"total_{label}"], overall[f"removed_{label}"])
        ]
    result = pd.concat([overall, detail], ignore_index=True)
    columns = [
        "category", "target_suppression_pct", "model", "total_sends", "removed_sends",
        "open_retention_pct", "click_retention_pct", "purchase_retention_pct"
    ]
    result = result[columns].sort_values(["target_suppression_pct", "category", "model"]).reset_index(drop=True)
    result.to_csv(OUTPUT_DIR / "suppression_results.csv", index=False, encoding="utf-8-sig")
    print("\nFixed suppression results (Test; offline ranking):", flush=True)
    print(result.loc[result["category"] == "TOTAL", columns].to_string(index=False, float_format=lambda x: f"{x:.3f}"), flush=True)
    print("\nSaved: suppression_results.csv", flush=True)


if __name__ == "__main__":
    main()
