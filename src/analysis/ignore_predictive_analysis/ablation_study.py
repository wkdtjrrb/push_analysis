import duckdb
import gc
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, log_loss
from sklearn.preprocessing import StandardScaler

root = "C:/Users/82105/Desktop/push_analysis/data/processed"

data_path = f"{root}/ignore_predictive_data.parquet"
output_results = f"{root}/ablation_results.csv"
output_individual = f"{root}/ablation_individual_effects.csv"
output_summary = f"{root}/ablation_summary.csv"
output_matrix = f"{root}/ablation_contribution_matrix.csv"

category_features = {
    "Marketing": "mar_ignore_cnt",
    "Behavioral": "beh_ignore_cnt",
    "Interest": "interest_ignore_cnt",
    "Lifecycle": "life_ignore_cnt",
    "Transactional": "trans_ignore_cnt"
}

categories = list(category_features.keys())

fixed_features = [
    "avg_user_total_ignore_rate",
    "total_consecutive_ignore_cnt"
]

all_features = fixed_features + list(category_features.values())

results = []

con = duckdb.connect()

schema = con.execute(
    "DESCRIBE SELECT * FROM read_parquet(?)",
    [data_path]
).df()

available_columns = set(schema["column_name"])

required_columns = set(
    all_features + ["category", "dataset", "is_opened"]
)

missing_columns = required_columns - available_columns

if missing_columns:
    raise ValueError(
        f"Missing columns: {sorted(missing_columns)}"
    )

for category in categories:
    print(f"\n[Category] {category}", flush=True)

    columns = ", ".join(all_features + ["is_opened"])

    frames = {}

    for split in ["train", "val"]:
        df = con.execute(
            f"""
            SELECT {columns}
            FROM read_parquet(?)
            WHERE category = ?
              AND dataset = ?
            """,
            [data_path, category, split]
        ).df()

        if df.empty:
            raise ValueError(
                f"Empty dataset: {category}, {split}"
            )

        if df[all_features + ["is_opened"]].isna().any().any():
            raise ValueError(
                f"NULL values: {category}, {split}"
            )

        if not df["is_opened"].isin([0, 1]).all():
            raise ValueError(
                f"Invalid target: {category}, {split}"
            )

        if df["is_opened"].nunique() < 2:
            raise ValueError(
                f"Single target class: {category}, {split}"
            )

        frames[split] = df

    train = frames["train"]
    val = frames["val"]

    y_train = train["is_opened"].to_numpy(dtype=np.int8)
    y_val = val["is_opened"].to_numpy(dtype=np.int8)

    X_train = train[all_features].to_numpy(dtype=np.float64)
    X_val = val[all_features].to_numpy(dtype=np.float64)

    if not np.isfinite(X_train).all():
        raise ValueError(f"Non-finite train features: {category}")

    if not np.isfinite(X_val).all():
        raise ValueError(f"Non-finite val features: {category}")

    scaler = StandardScaler()

    X_train = scaler.fit_transform(X_train)
    X_val = scaler.transform(X_val)

    own_feature = category_features[category]

    baseline_features = fixed_features + [own_feature]

    other_features = [
        feature
        for target_category, feature in category_features.items()
        if target_category != category
    ]

    experiments = [
        ("Baseline", None, baseline_features)
    ]

    for source_category in categories:
        if source_category == category:
            continue

        experiments.append(
            (
                "Individual",
                source_category,
                baseline_features + [
                    category_features[source_category]
                ]
            )
        )

    experiments.append(
        (
            "All_Other",
            "All",
            baseline_features + other_features
        )
    )

    category_results = []

    for index, (experiment, source, features) in enumerate(
        experiments, start=1
    ):
        indices = [
            all_features.index(feature)
            for feature in features
        ]

        model = LogisticRegression(
            solver="lbfgs",
            max_iter=300,
            tol=1e-5
        )

        model.fit(
            X_train[:, indices],
            y_train
        )

        probabilities = model.predict_proba(
            X_val[:, indices]
        )[:, 1]

        auc = roc_auc_score(
            y_val,
            probabilities
        )

        loss = log_loss(
            y_val,
            probabilities,
            labels=[0, 1]
        )

        converged = bool(
            model.n_iter_[0] < model.max_iter
        )

        row = {
            "category": category,
            "experiment": experiment,
            "source_category": source,
            "n_features": len(features),
            "selected_features": ",".join(features),
            "train_messages": len(train),
            "val_messages": len(val),
            "roc_auc": auc,
            "log_loss": loss,
            "iterations": int(model.n_iter_[0]),
            "converged": converged
        }

        category_results.append(row)

        print(
            f"  [{index}/6] "
            f"{experiment:10s} "
            f"{str(source):15s} "
            f"AUC={auc:.5f} "
            f"LogLoss={loss:.5f} "
            f"Converged={converged}",
            flush=True
        )

        del model, probabilities

    baseline = next(
        row for row in category_results
        if row["experiment"] == "Baseline"
    )

    for row in category_results:
        row["auc_gain"] = (
            row["roc_auc"] - baseline["roc_auc"]
        )

        row["log_loss_reduction"] = (
            baseline["log_loss"] - row["log_loss"]
        )

        row["improved_both"] = (
            row["auc_gain"] > 0
            and row["log_loss_reduction"] > 0
        )

    results.extend(category_results)

    del frames, train, val, y_train, y_val
    del X_train, X_val, scaler
    gc.collect()

con.close()

result = pd.DataFrame(results)

individual = result[
    result["experiment"] == "Individual"
].copy()

summary = result[
    result["experiment"].isin(
        ["Baseline", "All_Other"]
    )
].copy()

matrix = individual.pivot(
    index="category",
    columns="source_category",
    values="auc_gain"
)

matrix = matrix.reindex(
    index=categories,
    columns=categories
)

result.to_csv(output_results, index=False)
individual.to_csv(output_individual, index=False)
summary.to_csv(output_summary, index=False)
matrix.to_csv(output_matrix)

print("\n[Baseline vs All Other Categories]")

print(
    summary[
        [
            "category",
            "experiment",
            "roc_auc",
            "auc_gain",
            "log_loss",
            "log_loss_reduction",
            "converged"
        ]
    ].round(5).to_string(index=False)
)

print("\n[Individual Cross-Category Effects]")

print(
    individual[
        [
            "category",
            "source_category",
            "auc_gain",
            "log_loss_reduction",
            "improved_both",
            "converged"
        ]
    ].round(5).to_string(index=False)
)

print("\n[AUC Contribution Matrix]")

print(
    matrix.round(5).to_string()
)

print("\n[Saved Files]")
print(output_results)
print(output_individual)
print(output_summary)
print(output_matrix)