
"""

[코드 요약]
카테고리별로 어떤 무시 이력 변수가 오픈 예측에 유용하고, 얼마나 성능 개선에 기여하는지 확인

[코드 내용]
1. 최적 변수 선택: 카테고리별 64개 변수 조합을 비교해 적합한 조합을 선택
2. 개별 기여도 분석: 다른 카테고리의 무시 이력을 하나씩 추가했을 때 AUC와 Log Loss가 얼마나 개선되는지 측정
3. 공동 기여도 분석: 다른 카테고리의 무시 이력을 모두 추가했을 때의 성능 개선 측정

"""

import gc
import itertools
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.preprocessing import StandardScaler

ROOT = Path("C:/Users/82105/Desktop/push_analysis/data/processed")
DATA_PATH = ROOT / "ignore_predictive_data.parquet"

CATEGORY_FEATURES = {
    "Marketing": "mar_ignore_cnt",
    "Behavioral": "beh_ignore_cnt",
    "Interest": "interest_ignore_cnt",
    "Lifecycle": "life_ignore_cnt",
    "Transactional": "trans_ignore_cnt"
}

CATEGORIES = list(CATEGORY_FEATURES)

FIXED_FEATURE = "avg_user_total_ignore_rate"

CANDIDATE_FEATURES = [
    "total_consecutive_ignore_cnt",
    *CATEGORY_FEATURES.values()
]

ALL_FEATURES = [FIXED_FEATURE, *CANDIDATE_FEATURES]

AUC_TOLERANCE = 0.001

OUTPUT_ALL = ROOT / "feature_selection_results.csv"
OUTPUT_BEST = ROOT / "feature_selection_best.csv"
OUTPUT_CONTRIBUTION = ROOT / "feature_contribution.csv"
OUTPUT_MATRIX = ROOT / "feature_contribution_matrix.csv"
OUTPUT_SUMMARY = ROOT / "feature_contribution_summary.csv"

con = duckdb.connect()

schema = con.execute(
    "DESCRIBE SELECT * FROM read_parquet(?)",
    [str(DATA_PATH)]
).df()

required = set(
    ALL_FEATURES + ["category", "dataset", "is_opened"]
)

missing = required - set(schema["column_name"])

if missing:
    raise ValueError(f"Missing columns: {sorted(missing)}")

combinations = [
    combo
    for size in range(len(CANDIDATE_FEATURES) + 1)
    for combo in itertools.combinations(CANDIDATE_FEATURES, size)
]

results = []

for category in CATEGORIES:
    print(f"\n[Category] {category}", flush=True)

    columns = ", ".join(ALL_FEATURES + ["is_opened"])

    frames = {}

    for split in ["train", "val"]:
        df = con.execute(
            f"""
            SELECT {columns}
            FROM read_parquet(?)
            WHERE category = ?
              AND dataset = ?
            """,
            [str(DATA_PATH), category, split]
        ).df()

        if df.empty:
            raise ValueError(f"Empty split: {category}, {split}")

        if df[ALL_FEATURES + ["is_opened"]].isna().any().any():
            raise ValueError(f"NULL values: {category}, {split}")

        if not np.isfinite(
            df[ALL_FEATURES].to_numpy(dtype=np.float64)
        ).all():
            raise ValueError(f"Non-finite values: {category}, {split}")

        if not df["is_opened"].isin([0, 1]).all():
            raise ValueError(f"Invalid target: {category}, {split}")

        if df["is_opened"].nunique() != 2:
            raise ValueError(f"Single target class: {category}, {split}")

        frames[split] = df

    train = frames["train"]
    val = frames["val"]

    y_train = train["is_opened"].to_numpy(dtype=np.int8)
    y_val = val["is_opened"].to_numpy(dtype=np.int8)

    X_train = train[ALL_FEATURES].to_numpy(dtype=np.float64)
    X_val = val[ALL_FEATURES].to_numpy(dtype=np.float64)

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_val = scaler.transform(X_val)

    feature_indices = {
        feature: index
        for index, feature in enumerate(ALL_FEATURES)
    }

    for number, combo in enumerate(combinations, start=1):
        features = [FIXED_FEATURE, *combo]
        indices = [feature_indices[f] for f in features]

        model = LogisticRegression(
            solver="lbfgs",
            max_iter=300,
            tol=1e-5
        )

        model.fit(X_train[:, indices], y_train)

        probabilities = model.predict_proba(
            X_val[:, indices]
        )[:, 1]

        iterations = int(model.n_iter_[0])
        converged = iterations < model.max_iter

        results.append({
            "category": category,
            "n_features": len(features),
            "selected_features": ",".join(features),
            "selected_candidates": ",".join(combo),
            "roc_auc": roc_auc_score(y_val, probabilities),
            "log_loss": log_loss(
                y_val,
                probabilities,
                labels=[0, 1]
            ),
            "train_messages": len(train),
            "val_messages": len(val),
            "iterations": iterations,
            "converged": converged
        })

        if number % 8 == 0 or number == 1:
            print(
                f"  {number}/64 combinations completed",
                flush=True
            )

        del model, probabilities

    del frames, train, val, y_train, y_val
    del X_train, X_val, scaler
    gc.collect()

con.close()

result = pd.DataFrame(results)

if not result["converged"].all():
    print(
        "\nWarning: Some models did not meet the convergence criterion."
    )

valid = result[result["converged"]].copy()

best_rows = []
contribution_rows = []
summary_rows = []

for category in CATEGORIES:
    subset = valid[valid["category"] == category].copy()

    if len(subset) != 64:
        raise RuntimeError(
            f"Expected 64 converged models for {category}, "
            f"found {len(subset)}"
        )

    max_auc = subset["roc_auc"].max()

    eligible = subset[
        subset["roc_auc"] >= max_auc - AUC_TOLERANCE
    ].copy()

    eligible = eligible.sort_values(
        ["log_loss", "n_features", "roc_auc"],
        ascending=[True, True, False]
    )

    best = eligible.iloc[0].copy()
    best["max_auc"] = max_auc
    best["auc_gap_from_max"] = max_auc - best["roc_auc"]

    best_rows.append(best)

    own_feature = CATEGORY_FEATURES[category]

    baseline_candidates = [
        "total_consecutive_ignore_cnt",
        own_feature
    ]

    baseline_key = ",".join(baseline_candidates)

    baseline = subset[
        subset["selected_candidates"] == baseline_key
    ]

    if len(baseline) != 1:
        raise RuntimeError(
            f"Baseline not found for {category}"
        )

    baseline = baseline.iloc[0]

    other_categories = [
        source
        for source in CATEGORIES
        if source != category
    ]

    for source in other_categories:
        source_feature = CATEGORY_FEATURES[source]

        selected_set = set(
            baseline_candidates + [source_feature]
        )

        selected_combo = [
            feature
            for feature in CANDIDATE_FEATURES
            if feature in selected_set
        ]

        key = ",".join(selected_combo)

        candidate = subset[
            subset["selected_candidates"] == key
        ]

        if len(candidate) != 1:
            raise RuntimeError(
                f"Individual model not found: {category}, {source}"
            )

        candidate = candidate.iloc[0]

        contribution_rows.append({
            "category": category,
            "source_category": source,
            "baseline_auc": baseline["roc_auc"],
            "extended_auc": candidate["roc_auc"],
            "auc_gain": (
                candidate["roc_auc"] - baseline["roc_auc"]
            ),
            "baseline_log_loss": baseline["log_loss"],
            "extended_log_loss": candidate["log_loss"],
            "log_loss_reduction": (
                baseline["log_loss"] - candidate["log_loss"]
            ),
            "improved_both": bool(
                candidate["roc_auc"] > baseline["roc_auc"]
                and candidate["log_loss"] < baseline["log_loss"]
            )
        })

    all_candidates = ",".join(CANDIDATE_FEATURES)

    full = subset[
        subset["selected_candidates"] == all_candidates
    ]

    if len(full) != 1:
        raise RuntimeError(
            f"Full model not found for {category}"
        )

    full = full.iloc[0]

    summary_rows.append({
        "category": category,
        "baseline_auc": baseline["roc_auc"],
        "all_other_auc": full["roc_auc"],
        "auc_gain": full["roc_auc"] - baseline["roc_auc"],
        "baseline_log_loss": baseline["log_loss"],
        "all_other_log_loss": full["log_loss"],
        "log_loss_reduction": (
            baseline["log_loss"] - full["log_loss"]
        ),
        "improved_both": bool(
            full["roc_auc"] > baseline["roc_auc"]
            and full["log_loss"] < baseline["log_loss"]
        )
    })

best = pd.DataFrame(best_rows)
contribution = pd.DataFrame(contribution_rows)
summary = pd.DataFrame(summary_rows)

matrix = contribution.pivot(
    index="category",
    columns="source_category",
    values="auc_gain"
).reindex(
    index=CATEGORIES,
    columns=CATEGORIES
)

result.to_csv(OUTPUT_ALL, index=False)
best.to_csv(OUTPUT_BEST, index=False)
contribution.to_csv(OUTPUT_CONTRIBUTION, index=False)
matrix.to_csv(OUTPUT_MATRIX)
summary.to_csv(OUTPUT_SUMMARY, index=False)

print("\n[Best Feature Combinations]")
print(
    best[
        [
            "category",
            "n_features",
            "selected_candidates",
            "roc_auc",
            "max_auc",
            "log_loss"
        ]
    ].round(5).to_string(index=False)
)

print("\n[Individual Cross-Category Contribution]")
print(
    contribution[
        [
            "category",
            "source_category",
            "auc_gain",
            "log_loss_reduction",
            "improved_both"
        ]
    ].round(5).to_string(index=False)
)

print("\n[AUC Contribution Matrix]")
print(matrix.round(5).to_string())

print("\n[All Other Categories vs Baseline]")
print(summary.round(5).to_string(index=False))

print("\n[Saved Files]")
for path in [
    OUTPUT_ALL,
    OUTPUT_BEST,
    OUTPUT_CONTRIBUTION,
    OUTPUT_MATRIX,
    OUTPUT_SUMMARY
]:
    print(path)
