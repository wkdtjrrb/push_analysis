
"""
[코드 요약]
카테고리별 최종 변수 구성으로 오픈 예측 모델을 학습하고 Test 성능을 평가한 뒤 모델을 저장

[코드 내용]
1. 최종 모델 학습: 카테고리별 확정 변수를 사용해 Train + Validation 데이터로 로지스틱 회귀 모델 학습
2. 최종 성능 평가: Test 데이터에서 카테고리별 ROC-AUC와 Log Loss 측정
3. 모델 저장: StandardScaler와 로지스틱 회귀를 결합한 Pipeline을 카테고리별로 저장
"""

import gc
from pathlib import Path

import duckdb
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path("C:/Users/82105/Desktop/push_analysis")

DATA_DIR = ROOT / "data" / "processed"
MODEL_DIR = ROOT / "src" / "analysis" / "ignore_predictive_analysis" / "modeling"
OUTPUT_DIR = MODEL_DIR / "outputs"

TRAIN_VAL_PATH = DATA_DIR / "ignore_predictive_data.parquet"
TEST_PATH = DATA_DIR / "ignore_predictive_test.parquet"

FIXED_FEATURES = [
    "avg_user_total_ignore_rate",
    "total_consecutive_ignore_cnt"
]

CATEGORY_FEATURES = {
    "Marketing": [
        "mar_ignore_cnt"
    ],
    "Behavioral": [
        "beh_ignore_cnt"
    ],
    "Interest": [
        "mar_ignore_cnt",
        "beh_ignore_cnt",
        "interest_ignore_cnt",
        "life_ignore_cnt"
    ],
    "Lifecycle": [
        "beh_ignore_cnt",
        "interest_ignore_cnt",
        "life_ignore_cnt"
    ],
    "Transactional": [
        "mar_ignore_cnt",
        "life_ignore_cnt",
        "trans_ignore_cnt"
    ]
}

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

for path in [TRAIN_VAL_PATH, TEST_PATH]:
    if not path.exists():
        raise FileNotFoundError(path)

results = []
con = duckdb.connect()

for category, category_features in CATEGORY_FEATURES.items():
    print(f"\n[Category] {category}", flush=True)

    features = FIXED_FEATURES + category_features
    columns = ", ".join(features + ["is_opened"])

    for path, required_extra in [
        (TRAIN_VAL_PATH, {"dataset", "category"}),
        (TEST_PATH, {"category"})
    ]:
        schema = con.execute(
            "DESCRIBE SELECT * FROM read_parquet(?)",
            [str(path)]
        ).df()

        missing = (
            set(features + ["is_opened"])
            | required_extra
        ) - set(schema["column_name"])

        if missing:
            raise ValueError(
                f"Missing columns in {path.name}: {sorted(missing)}"
            )

    train = con.execute(
        f"""
        SELECT {columns}
        FROM read_parquet(?)
        WHERE category = ?
          AND dataset IN ('train', 'val')
        """,
        [str(TRAIN_VAL_PATH), category]
    ).df()

    test = con.execute(
        f"""
        SELECT {columns}
        FROM read_parquet(?)
        WHERE category = ?
        """,
        [str(TEST_PATH), category]
    ).df()

    if train.empty or test.empty:
        raise ValueError(f"Empty dataset: {category}")

    for name, df in [("train_val", train), ("test", test)]:
        if df[features + ["is_opened"]].isna().any().any():
            raise ValueError(f"NULL values: {category}, {name}")

        if not df["is_opened"].isin([0, 1]).all():
            raise ValueError(f"Invalid target: {category}, {name}")

        if df["is_opened"].nunique() != 2:
            raise ValueError(f"Single target class: {category}, {name}")

        if not np.isfinite(
            df[features].to_numpy(dtype=np.float64)
        ).all():
            raise ValueError(
                f"Non-finite features: {category}, {name}"
            )

    X_train = train[features].astype(np.float64)
    y_train = train["is_opened"].to_numpy(dtype=np.int8)

    X_test = test[features].astype(np.float64)
    y_test = test["is_opened"].to_numpy(dtype=np.int8)

    model = Pipeline([
        ("scaler", StandardScaler()),
        (
            "classifier",
            LogisticRegression(
                solver="lbfgs",
                max_iter=300,
                tol=1e-5
            )
        )
    ])

    model.fit(X_train, y_train)

    probabilities = model.predict_proba(X_test)[:, 1]

    auc = roc_auc_score(y_test, probabilities)

    loss = log_loss(
        y_test,
        probabilities,
        labels=[0, 1]
    )

    classifier = model.named_steps["classifier"]

    iterations = int(classifier.n_iter_[0])
    converged = iterations < classifier.max_iter

    model_path = OUTPUT_DIR / f"{category.lower()}_model.joblib"

    joblib.dump(
        {
            "category": category,
            "features": features,
            "pipeline": model,
            "target": "is_opened"
        },
        model_path
    )

    results.append({
        "category": category,
        "n_features": len(features),
        "selected_features": ",".join(features),
        "train_val_messages": len(train),
        "test_messages": len(test),
        "test_open_rate": float(y_test.mean()),
        "roc_auc": auc,
        "log_loss": loss,
        "iterations": iterations,
        "converged": converged,
        "model_path": str(model_path)
    })

    print(f"  Features: {', '.join(features)}")
    print(f"  Test AUC: {auc:.5f}")
    print(f"  Test Log Loss: {loss:.5f}")
    print(f"  Converged: {converged}")
    print(f"  Saved: {model_path}", flush=True)

    del train, test, X_train, X_test
    del y_train, y_test, probabilities, model, classifier
    gc.collect()

con.close()

result = pd.DataFrame(results)

output_path = OUTPUT_DIR / "final_model_results.csv"

result.to_csv(output_path, index=False)

print("\n[Final Model Performance]")

print(
    result[
        [
            "category",
            "n_features",
            "roc_auc",
            "log_loss",
            "converged"
        ]
    ].round(5).to_string(index=False)
)

print("\n[Saved Results]")
print(output_path)

if not result["converged"].all():
    print(
        "\nWarning: Some models did not meet the convergence criterion."
    )
