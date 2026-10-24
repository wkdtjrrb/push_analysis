"""
[코드 요약]
Baseline과 Proposed의 발송 제외 임계값을 동일한 조건에서 최적화하고 Test에서 비교

[코드 내용]
1. Validation에서 모델별 카테고리 임계값을 공동 최적화
2. 클릭 손실 1%, 구매 손실 1% 조건에서 발송 제외량 최대화
3. 구매 손실 0.5%, 2% 민감도 분석
4. Test에서 확정된 임계값으로 발송 감소, 행동 손실, 수신 거부 집중도 평가
5. 최종 비교 및 상세 결과 CSV 저장
"""

import gc
from pathlib import Path

import duckdb
import joblib
import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix

ROOT = Path("C:/Users/82105/Desktop/push_analysis")
OUTPUT_DIR = ROOT / "src/modeling/outputs"
MODEL_DIR = OUTPUT_DIR / "models"
VALIDATION_PATH = OUTPUT_DIR / "validation_predictions.parquet"
TEST_PATH = ROOT / "data/processed/ignore_predictive_test.parquet"

CATEGORIES = ["Marketing", "Behavioral", "Interest", "Lifecycle", "Transactional"]
MODELS = ["Baseline", "Proposed"]
BEHAVIORS = ["is_opened", "is_clicked", "is_purchased", "is_unsubscribed"]
LABELS = {"is_opened": "open", "is_clicked": "click", "is_purchased": "purchase", "is_unsubscribed": "unsubscribe"}
CLICK_LIMIT = 0.01
PURCHASE_LIMITS = [0.005, 0.01, 0.02]
MAIN_PURCHASE_LIMIT = 0.01
THRESHOLD_STEP = 0.001
BATCH_SIZE = 100_000


def make_candidates(df, category, model, thresholds):
    probabilities = df["probability"].to_numpy(dtype=np.float64)
    if not np.isfinite(probabilities).all() or ((probabilities < 0) | (probabilities > 1)).any():
        raise ValueError(f"Invalid probabilities: {category}/{model}")
    order = np.argsort(probabilities, kind="stable")
    removed = np.searchsorted(probabilities[order], thresholds, side="left")
    data = {"category": category, "model": model, "threshold": thresholds, "removed_sends": removed, "total_sends": len(df)}
    for name in BEHAVIORS:
        values = df[name].to_numpy()
        if pd.isna(values).any() or not np.isin(values, [0, 1]).all():
            raise ValueError(f"Invalid {name}: {category}/{model}")
        prefix = np.concatenate(([0], np.cumsum(values[order].astype(np.int64))))
        data[f"removed_{name}"] = prefix[removed]
        data[f"total_{name}"] = int(prefix[-1])
    return pd.DataFrame(data)


def optimize(candidates, purchase_limit):
    frame = candidates.reset_index(drop=True)
    n = len(frame)
    matrix = lil_matrix((2 + len(CATEGORIES), n), dtype=np.float64)
    lower = np.full(2 + len(CATEGORIES), -np.inf)
    upper = np.full(2 + len(CATEGORIES), np.inf)
    totals = {name: int(frame.groupby("category")[f"total_{name}"].first().sum()) for name in BEHAVIORS}
    for row, (name, limit) in enumerate([("is_clicked", CLICK_LIMIT), ("is_purchased", purchase_limit)]):
        matrix[row, :] = frame[f"removed_{name}"].to_numpy(dtype=float)
        upper[row] = np.floor(totals[name] * limit)
    category_values = frame["category"].to_numpy()
    for j, category in enumerate(CATEGORIES):
        indices = np.flatnonzero(category_values == category)
        if len(indices) == 0:
            raise ValueError(f"Missing validation category: {category}")
        matrix[2 + j, indices] = 1.0
        lower[2 + j] = 1.0
        upper[2 + j] = 1.0
    result = milp(
        c=-frame["removed_sends"].to_numpy(dtype=np.float64),
        integrality=np.ones(n, dtype=np.int8),
        bounds=Bounds(np.zeros(n), np.ones(n)),
        constraints=LinearConstraint(matrix.tocsr(), lower, upper),
        options={"time_limit": 180, "mip_rel_gap": 0.0}
    )
    if result.x is None or result.status != 0:
        raise RuntimeError(f"MILP failed: {result.status}, {result.message}")
    chosen = frame.loc[result.x > 0.5].copy().sort_values("category")
    if len(chosen) != len(CATEGORIES):
        raise RuntimeError("Invalid threshold selection")
    return chosen, totals


def safe_pct(numerator, denominator):
    return 100.0 * numerator / denominator if denominator else np.nan


def validation_metrics(chosen, totals, model, purchase_limit):
    row = {
        "model": model,
        "purchase_loss_limit_pct": 100 * purchase_limit,
        "click_loss_limit_pct": 100 * CLICK_LIMIT,
        "validation_total_sends": int(chosen["total_sends"].sum()),
        "validation_removed_sends": int(chosen["removed_sends"].sum())
    }
    row["validation_send_reduction_pct"] = safe_pct(row["validation_removed_sends"], row["validation_total_sends"])
    for name in BEHAVIORS:
        label = LABELS[name]
        removed = int(chosen[f"removed_{name}"].sum())
        row[f"validation_removed_{label}"] = removed
        row[f"validation_{label}_loss_pct"] = safe_pct(removed, totals[name])
    row["validation_unsubscribe_capture_pct"] = row["validation_unsubscribe_loss_pct"]
    row["validation_unsubscribe_lift"] = (
        row["validation_unsubscribe_capture_pct"] / row["validation_send_reduction_pct"]
        if row["validation_send_reduction_pct"] > 0 else np.nan
    )
    for _, record in chosen.iterrows():
        row[f"threshold_{record['category'].lower()}"] = float(record["threshold"])
    return row


def prepare_batch(df, features):
    for name in features:
        if name in ("channel", "topic"):
            df[name] = df[name].astype("string").fillna("__MISSING__").astype(str)
        else:
            df[name] = pd.to_numeric(df[name], errors="coerce").replace([np.inf, -np.inf], np.nan)
    return df


def evaluate_test(con, thresholds_by_model):
    results = []
    for category in CATEGORIES:
        artifacts = {}
        all_features = []
        for model in MODELS:
            path = MODEL_DIR / f"{category.lower()}_{model.lower()}_model.joblib"
            if not path.exists():
                raise FileNotFoundError(path)
            artifacts[model] = joblib.load(path)
            if artifacts[model].get("model") != model or artifacts[model].get("category") != category:
                raise ValueError(f"Unexpected model metadata: {path}")
            all_features.extend(artifacts[model]["features"])
        all_features = list(dict.fromkeys(all_features))
        columns = all_features + BEHAVIORS
        select_columns = ", ".join(f'"{name}"' for name in columns)
        reader = con.execute(
            f"SELECT {select_columns} FROM read_parquet(?) WHERE category = ?",
            [str(TEST_PATH), category]
        ).fetch_record_batch(rows_per_batch=BATCH_SIZE)
        counts = {}
        for model in MODELS:
            counts[model] = {"model": model, "category": category, "threshold": thresholds_by_model[model][category], "before_sends": 0, "after_sends": 0}
            for name in BEHAVIORS:
                counts[model][f"before_{name}"] = 0
                counts[model][f"after_{name}"] = 0
        for batch in reader:
            df = batch.to_pandas()
            if df.empty:
                continue
            for name in BEHAVIORS:
                if df[name].isna().any() or not df[name].isin([0, 1]).all():
                    raise ValueError(f"Invalid Test {name}: {category}")
            df = prepare_batch(df, all_features)
            for model in MODELS:
                artifact = artifacts[model]
                features = artifact["features"]
                probs = artifact["pipeline"].predict_proba(df[features])[:, 1]
                keep = probs >= thresholds_by_model[model][category]
                record = counts[model]
                record["before_sends"] += len(df)
                record["after_sends"] += int(keep.sum())
                for name in BEHAVIORS:
                    values = df[name].to_numpy(dtype=np.int64)
                    record[f"before_{name}"] += int(values.sum())
                    record[f"after_{name}"] += int(values[keep].sum())
            del df
        results.extend(counts.values())
        print(f"Test complete: {category}", flush=True)
        del artifacts
        gc.collect()
    return pd.DataFrame(results)


def add_metrics(frame):
    result = frame.copy()
    result["removed_sends"] = result["before_sends"] - result["after_sends"]
    result["send_reduction_rate_pct"] = 100 * result["removed_sends"] / result["before_sends"].replace(0, np.nan)
    for name in BEHAVIORS:
        label = LABELS[name]
        before = result[f"before_{name}"]
        after = result[f"after_{name}"]
        result[f"removed_{label}"] = before - after
        result[f"{label}_loss_rate_pct"] = 100 * (before - after) / before.replace(0, np.nan)
        result[f"before_{label}_rate_pct"] = 100 * before / result["before_sends"].replace(0, np.nan)
        result[f"after_{label}_rate_pct"] = 100 * after / result["after_sends"].replace(0, np.nan)
    result["unsubscribe_capture_pct"] = result["unsubscribe_loss_rate_pct"]
    result["unsubscribe_lift"] = result["unsubscribe_capture_pct"] / result["send_reduction_rate_pct"].replace(0, np.nan)
    return result


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in [VALIDATION_PATH, TEST_PATH]:
        if not path.exists():
            raise FileNotFoundError(path)
    con = duckdb.connect()
    for path, required in [
        (VALIDATION_PATH, ["category", "model", "probability"] + BEHAVIORS),
        (TEST_PATH, ["category"] + BEHAVIORS)
    ]:
        available = set(con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(path)]).df()["column_name"])
        missing = set(required) - available
        if missing:
            raise ValueError(f"{path.name} missing columns: {sorted(missing)}")
    thresholds = np.round(np.arange(0, 1 + THRESHOLD_STEP / 2, THRESHOLD_STEP), 10)
    candidates_by_model = {model: [] for model in MODELS}
    for category in CATEGORIES:
        for model in MODELS:
            val = con.execute(
                "SELECT probability, is_opened, is_clicked, is_purchased, is_unsubscribed FROM read_parquet(?) WHERE category = ? AND model = ?",
                [str(VALIDATION_PATH), category, model]
            ).df()
            if val.empty:
                raise ValueError(f"Empty validation: {category}/{model}")
            candidates_by_model[model].append(make_candidates(val, category, model, thresholds))
            print(f"Validation candidates: {category}/{model} ({len(val):,})", flush=True)
            del val
            gc.collect()
    candidates_by_model = {model: pd.concat(parts, ignore_index=True) for model, parts in candidates_by_model.items()}
    scenario_rows = []
    threshold_rows = []
    thresholds_by_model = {}
    for model in MODELS:
        for purchase_limit in PURCHASE_LIMITS:
            chosen, totals = optimize(candidates_by_model[model], purchase_limit)
            scenario_rows.append(validation_metrics(chosen, totals, model, purchase_limit))
            if purchase_limit == MAIN_PURCHASE_LIMIT:
                thresholds_by_model[model] = dict(zip(chosen["category"], chosen["threshold"]))
                chosen = chosen.copy()
                chosen["purchase_loss_limit_pct"] = 100 * purchase_limit
                chosen["click_loss_limit_pct"] = 100 * CLICK_LIMIT
                chosen["validation_send_reduction_pct"] = 100 * chosen["removed_sends"] / chosen["total_sends"]
                for name in BEHAVIORS:
                    label = LABELS[name]
                    chosen[f"validation_{label}_loss_pct"] = 100 * chosen[f"removed_{name}"] / chosen[f"total_{name}"].replace(0, np.nan)
                threshold_rows.append(chosen)
            print(f"Optimized: {model}, purchase limit {100 * purchase_limit:.1f}%", flush=True)
    threshold_df = pd.concat(threshold_rows, ignore_index=True)
    threshold_path = OUTPUT_DIR / "optimized_thresholds.csv"
    threshold_df.to_csv(threshold_path, index=False, encoding="utf-8-sig")
    sensitivity_df = pd.DataFrame(scenario_rows)
    sensitivity_path = OUTPUT_DIR / "threshold_sensitivity.csv"
    sensitivity_df.to_csv(sensitivity_path, index=False, encoding="utf-8-sig")
    test = evaluate_test(con, thresholds_by_model)
    total_rows = []
    for model in MODELS:
        subset = test.loc[test["model"] == model]
        row = {"model": model, "category": "TOTAL", "threshold": np.nan}
        for name in ["before_sends", "after_sends"] + [f"{prefix}_{behavior}" for prefix in ("before", "after") for behavior in BEHAVIORS]:
            row[name] = int(subset[name].sum())
        total_rows.append(row)
    test = pd.concat([test, pd.DataFrame(total_rows)], ignore_index=True)
    test_results = add_metrics(test)
    result_path = OUTPUT_DIR / "optimized_push_results.csv"
    test_results.to_csv(result_path, index=False, encoding="utf-8-sig")
    comparison = test_results.loc[test_results["category"] == "TOTAL", [
        "model", "before_sends", "removed_sends", "send_reduction_rate_pct",
        "open_loss_rate_pct", "click_loss_rate_pct", "purchase_loss_rate_pct",
        "unsubscribe_capture_pct", "unsubscribe_lift"
    ]].copy()
    comparison_path = OUTPUT_DIR / "push_policy_comparison.csv"
    comparison.to_csv(comparison_path, index=False, encoding="utf-8-sig")
    con.close()
    print("\n[Validation sensitivity]")
    print(sensitivity_df[["model", "purchase_loss_limit_pct", "validation_send_reduction_pct", "validation_click_loss_pct", "validation_purchase_loss_pct"]].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print("\n[Final Test comparison]")
    print(comparison.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    for path in [threshold_path, sensitivity_path, result_path, comparison_path]:
        print(f"Saved: {path}")
    print("Historical observed actions are not causal effects of suppressing sends.")


if __name__ == "__main__":
    main()
