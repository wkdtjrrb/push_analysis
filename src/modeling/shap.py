"""
[코드 요약]
전체 Test 데이터의 Proposed 모델 누적 무시 이력 SHAP 분석

[코드 내용]
카테고리별 데이터를 배치 처리하여 전체 평균을 기준으로 로그 오즈 SHAP 값을 계산하고
Power BI용 변수 중요도 및 누적 무시 횟수별 집계 CSV를 저장
"""

from pathlib import Path
from collections import defaultdict

import duckdb
import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
TEST_PATH = ROOT / "data/processed/ignore_predictive_test.parquet"
OUTPUT_DIR = ROOT / "src/modeling/outputs"
MODEL_DIR = OUTPUT_DIR / "models"
CATEGORIES = ["Marketing", "Behavioral", "Interest", "Lifecycle", "Transactional"]
BATCH_SIZE = 100000
MAX_DISPLAY_COUNT = 30


def batches(con, category, columns):
    names = ", ".join('"' + c.replace('"', '""') + '"' for c in columns)
    cursor = con.execute(
        f"SELECT {names} FROM read_parquet(?) WHERE category = ?",
        [str(TEST_PATH), category],
    )
    while True:
        frame = cursor.fetch_df_chunk(max(1, BATCH_SIZE // 2048))
        if frame.empty:
            break
        yield frame


def numeric_values(frame, numeric_features, transformer):
    numeric = frame[numeric_features].copy()
    for name in numeric_features:
        numeric[name] = pd.to_numeric(numeric[name], errors="coerce").replace([np.inf, -np.inf], np.nan)
    return transformer.transform(numeric)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    importance_rows = []
    dependence_rows = []

    for category in CATEGORIES:
        path = MODEL_DIR / f"{category.lower()}_proposed_model.joblib"
        artifact = joblib.load(path)
        if artifact.get("category") != category or artifact.get("model") != "Proposed":
            raise ValueError(f"Unexpected model metadata: {path}")

        ignore_features = artifact["ignore_features"]
        pipeline = artifact["pipeline"]
        preprocessor = pipeline.named_steps["preprocessor"]
        classifier = pipeline.named_steps["classifier"]
        numeric_names = list(preprocessor.transformers_[0][2])
        numeric_transformer = preprocessor.named_transformers_["numeric"]
        transformed_names = list(preprocessor.get_feature_names_out())
        coef = classifier.coef_[0]
        if classifier.classes_[1] != 1:
            raise ValueError(f"Unexpected target class: {category}")
        indices = [numeric_names.index(feature) for feature in ignore_features]
        coefficients = np.array([coef[transformed_names.index(f"numeric__{feature}")] for feature in ignore_features])

        total = 0
        scaled_sum = np.zeros(len(indices), dtype=np.float64)
        for frame in batches(con, category, numeric_names):
            scaled = numeric_values(frame, numeric_names, numeric_transformer)
            scaled_sum += np.asarray(scaled[:, indices], dtype=np.float64).sum(axis=0)
            total += len(frame)
        if total == 0:
            raise ValueError(f"No Test rows: {category}")
        reference = scaled_sum / total

        absolute_sums = np.zeros(len(indices), dtype=np.float64)
        signed_sums = np.zeros(len(indices), dtype=np.float64)
        groups = defaultdict(lambda: [0, 0.0])
        for frame in batches(con, category, numeric_names):
            scaled = numeric_values(frame, numeric_names, numeric_transformer)
            values = np.asarray(scaled[:, indices], dtype=np.float64)
            contributions = (values - reference) * coefficients
            absolute_sums += np.abs(contributions).sum(axis=0)
            signed_sums += contributions.sum(axis=0)
            for j, feature in enumerate(ignore_features):
                raw = pd.to_numeric(frame[feature], errors="coerce")
                bucket = np.floor(raw.clip(lower=0, upper=MAX_DISPLAY_COUNT)).fillna(-1).astype(int)
                partial = pd.DataFrame({"bucket": bucket, "shap": contributions[:, j]})
                summary = partial.groupby("bucket", sort=False)["shap"].agg(["size", "sum"])
                for key, row in summary.iterrows():
                    target = groups[(feature, int(key))]
                    target[0] += int(row["size"])
                    target[1] += float(row["sum"])

        for j, feature in enumerate(ignore_features):
            importance_rows.append({
                "category": category,
                "model": "Proposed",
                "feature": feature,
                "test_rows": total,
                "mean_abs_shap": absolute_sums[j] / total,
                "mean_shap": signed_sums[j] / total,
                "coefficient_log_odds": coefficients[j],
                "shap_scale": "log_odds",
            })
        for (feature, bucket), (count, shap_sum) in groups.items():
            dependence_rows.append({
                "category": category,
                "model": "Proposed",
                "feature": feature,
                "ignore_count_bucket": "Missing" if bucket == -1 else f"{MAX_DISPLAY_COUNT}+" if bucket == MAX_DISPLAY_COUNT else str(bucket),
                "bucket_order": bucket,
                "rows": count,
                "mean_shap": shap_sum / count,
                "shap_scale": "log_odds",
            })
        print(f"[{category}] {total:,} full Test rows, {len(ignore_features)} ignore features", flush=True)

    con.close()
    importance = pd.DataFrame(importance_rows).sort_values(["category", "mean_abs_shap"], ascending=[True, False])
    dependence = pd.DataFrame(dependence_rows).sort_values(["category", "feature", "bucket_order"])
    importance.to_csv(OUTPUT_DIR / "shap_importance.csv", index=False, encoding="utf-8-sig")
    dependence.to_csv(OUTPUT_DIR / "shap_dependence.csv", index=False, encoding="utf-8-sig")
    print("Saved: shap_importance.csv, shap_dependence.csv", flush=True)
    print(importance[["category", "feature", "mean_abs_shap"]].to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
