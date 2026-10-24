"""
[코드 요약]
카테고리별 Baseline과 Proposed 오픈 예측 모델을 학습하고 Test 성능을 비교

[코드 내용]
1. 기존 Train 및 Validation 데이터를 결합하여 최종 모델 학습
2. Baseline은 푸시 특성만, Proposed는 푸시 특성과 누적 무시 이력 사용
3. 카테고리별 ROC-AUC와 Log Loss를 평가하고 모델 10개 저장
4. model_comparison.csv 저장
"""

import gc
from pathlib import Path

import duckdb
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[2]
TRAIN_PATH = ROOT / "data/processed/ignore_predictive_data.parquet"
TEST_PATH = ROOT / "data/processed/ignore_predictive_test.parquet"
OUTPUT_DIR = ROOT / "src/modeling/outputs"
MODEL_DIR = OUTPUT_DIR / "models"

COMMON_IGNORE_FEATURES = ["avg_user_total_ignore_rate", "total_consecutive_ignore_cnt"]
CATEGORY_IGNORE_FEATURES = {
    "Marketing": ["mar_ignore_cnt"],
    "Behavioral": ["beh_ignore_cnt"],
    "Interest": ["mar_ignore_cnt", "beh_ignore_cnt", "interest_ignore_cnt", "life_ignore_cnt"],
    "Lifecycle": ["beh_ignore_cnt", "interest_ignore_cnt", "life_ignore_cnt"],
    "Transactional": ["mar_ignore_cnt", "life_ignore_cnt", "trans_ignore_cnt"]
}
CATEGORICAL_FEATURES = ["channel", "topic"]
NUMERIC_PUSH_FEATURES = ["hour_limit", "subject_length"]
BOOLEAN_PUSH_FEATURES = [
    "ab_test", "warmup_mode", "subject_with_personalization",
    "subject_with_deadline", "subject_with_emoji", "subject_with_bonuses",
    "subject_with_discount", "subject_with_saleout"
]
PUSH_FEATURES = CATEGORICAL_FEATURES + NUMERIC_PUSH_FEATURES + BOOLEAN_PUSH_FEATURES


def prepare_features(df, features):
    for column in features:
        if column in CATEGORICAL_FEATURES:
            df[column] = df[column].astype("string").fillna("__MISSING__").astype(str)
        else:
            df[column] = pd.to_numeric(df[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
    return df


def build_model(ignore_features):
    numeric_features = NUMERIC_PUSH_FEATURES + BOOLEAN_PUSH_FEATURES + ignore_features
    preprocessor = ColumnTransformer(
        transformers=[
            ("numeric", Pipeline([
                ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
                ("scaler", StandardScaler())
            ]), numeric_features),
            ("categorical", OneHotEncoder(handle_unknown="ignore", min_frequency=20), CATEGORICAL_FEATURES)
        ],
        sparse_threshold=1.0
    )
    return Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", LogisticRegression(solver="lbfgs", max_iter=500, tol=1e-5))
    ])


def main():
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for path in (TRAIN_PATH, TEST_PATH):
        if not path.exists():
            raise FileNotFoundError(path)

    con = duckdb.connect()
    required = set(PUSH_FEATURES + COMMON_IGNORE_FEATURES + ["category", "is_opened"])
    for columns in CATEGORY_IGNORE_FEATURES.values():
        required.update(columns)
    for path in (TRAIN_PATH, TEST_PATH):
        available = set(con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(path)]).df()["column_name"])
        missing = required - available
        if missing:
            raise ValueError(f"{path.name} missing columns: {sorted(missing)}")
    available_train = set(con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(TRAIN_PATH)]).df()["column_name"])
    if "dataset" not in available_train:
        raise ValueError("Training parquet must contain dataset (train/val)")

    rows = []
    for category, selected in CATEGORY_IGNORE_FEATURES.items():
        ignore_features = COMMON_IGNORE_FEATURES + selected
        all_features = list(dict.fromkeys(PUSH_FEATURES + ignore_features))
        selected_columns = ", ".join(f'"{name}"' for name in all_features)
        train_df = con.execute(
            f'SELECT {selected_columns}, CAST(is_opened AS INTEGER) AS is_opened FROM read_parquet(?) WHERE category = ? AND dataset IN (\'train\', \'val\')',
            [str(TRAIN_PATH), category]
        ).df()
        test_df = con.execute(
            f'SELECT {selected_columns}, CAST(is_opened AS INTEGER) AS is_opened FROM read_parquet(?) WHERE category = ?',
            [str(TEST_PATH), category]
        ).df()
        if train_df.empty or test_df.empty:
            raise ValueError(f"Empty category: {category}")
        for split, frame in (("Train+Val", train_df), ("Test", test_df)):
            if frame["is_opened"].isna().any() or not frame["is_opened"].isin([0, 1]).all():
                raise ValueError(f"Invalid open label: {category}/{split}")
            if frame["is_opened"].nunique() != 2:
                raise ValueError(f"Single-class open label: {category}/{split}")
        prepare_features(train_df, all_features)
        prepare_features(test_df, all_features)
        numeric_columns = NUMERIC_PUSH_FEATURES + BOOLEAN_PUSH_FEATURES + ignore_features
        empty_columns = [name for name in numeric_columns if train_df[name].isna().all()]
        if empty_columns:
            print(f"[{category}] Entirely missing numeric features: {empty_columns}", flush=True)
        print(f"\n[{category}] Train+Val {len(train_df):,}, Test {len(test_df):,}", flush=True)
        for model_name in ("Baseline", "Proposed"):
            features = PUSH_FEATURES if model_name == "Baseline" else all_features
            selected_ignore = [] if model_name == "Baseline" else ignore_features
            model = build_model(selected_ignore)
            model.fit(train_df[features], train_df["is_opened"].to_numpy())
            probability = model.predict_proba(test_df[features])[:, 1]
            auc = roc_auc_score(test_df["is_opened"], probability)
            loss = log_loss(test_df["is_opened"], probability, labels=[0, 1])
            model_path = MODEL_DIR / f"{category.lower()}_{model_name.lower()}_model.joblib"
            joblib.dump({
                "category": category,
                "model": model_name,
                "features": features,
                "ignore_features": selected_ignore,
                "push_features": PUSH_FEATURES,
                "pipeline": model
            }, model_path)
            rows.append({
                "category": category,
                "model": model_name,
                "train_val_rows": len(train_df),
                "test_rows": len(test_df),
                "roc_auc": auc,
                "log_loss": loss
            })
            print(f"{model_name}: ROC-AUC={auc:.5f}, Log Loss={loss:.5f}", flush=True)
            del model, probability
            gc.collect()
        del train_df, test_df
        gc.collect()
    con.close()
    result = pd.DataFrame(rows)
    result.to_csv(OUTPUT_DIR / "model_comparison.csv", index=False, encoding="utf-8-sig")
    print("\nSaved: model_comparison.csv", flush=True)
    print(result.to_string(index=False, float_format=lambda x: f"{x:.5f}"), flush=True)


if __name__ == "__main__":
    main()
