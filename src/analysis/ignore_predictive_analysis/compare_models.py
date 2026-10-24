import duckdb
import gc
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, log_loss
from sklearn.preprocessing import StandardScaler

path = "C:/Users/82105/Desktop/push_analysis/data/processed/ignore_predictive_data.parquet"

categories = [
    "Marketing",
    "Behavioral",
    "Interest",
    "Lifecycle",
    "Transactional"
]

models = {
    "M0": ["avg_user_total_ignore_rate"],
    "M1": ["avg_user_total_ignore_rate", "own_ignore_cnt"],
    "M2": ["avg_user_total_ignore_rate", "other_ignore_cnt"],
    "M3": ["avg_user_total_ignore_rate", "total_consecutive_ignore_cnt"]
}

results = []
con = duckdb.connect()

for category in categories:
    print(f"\nCategory: {category}", flush=True)

    train = con.execute(
        """
        SELECT
            avg_user_total_ignore_rate,
            own_ignore_cnt,
            other_ignore_cnt,
            total_consecutive_ignore_cnt,
            is_opened
        FROM read_parquet(?)
        WHERE category = ?
          AND dataset = 'train'
        """,
        [path, category]
    ).df()

    val = con.execute(
        """
        SELECT
            avg_user_total_ignore_rate,
            own_ignore_cnt,
            other_ignore_cnt,
            total_consecutive_ignore_cnt,
            is_opened
        FROM read_parquet(?)
        WHERE category = ?
          AND dataset = 'val'
        """,
        [path, category]
    ).df()

    y_train = train["is_opened"].to_numpy(dtype=np.int8)
    y_val = val["is_opened"].to_numpy(dtype=np.int8)

    for model_name, features in models.items():
        print(f"  Running {model_name}", flush=True)

        X_train = train[features].to_numpy(dtype=np.float64)
        X_val = val[features].to_numpy(dtype=np.float64)

        scaler = StandardScaler()

        X_train = scaler.fit_transform(X_train)
        X_val = scaler.transform(X_val)

        model = LogisticRegression(
            solver="lbfgs",
            max_iter=300,
            tol=1e-5
        )

        model.fit(X_train, y_train)

        probabilities = model.predict_proba(X_val)[:, 1]

        results.append({
            "category": category,
            "model": model_name,
            "train_messages": len(train),
            "val_messages": len(val),
            "roc_auc": roc_auc_score(y_val, probabilities),
            "log_loss": log_loss(y_val, probabilities),
            "iterations": int(model.n_iter_[0])
        })

        del X_train, X_val, scaler, model, probabilities
        gc.collect()

    del train, val, y_train, y_val
    gc.collect()

con.close()

result = pd.DataFrame(results)

baseline = result[result["model"] == "M0"][
    ["category", "roc_auc", "log_loss"]
].rename(
    columns={
        "roc_auc": "baseline_auc",
        "log_loss": "baseline_log_loss"
    }
)

result = result.merge(baseline, on="category")

result["auc_gain"] = result["roc_auc"] - result["baseline_auc"]
result["log_loss_reduction"] = (
    result["baseline_log_loss"] - result["log_loss"]
)

print("\n[Model Comparison]")
print(
    result[
        [
            "category",
            "model",
            "roc_auc",
            "auc_gain",
            "log_loss",
            "log_loss_reduction",
            "iterations"
        ]
    ].round(5).to_string(index=False)
)

output = "C:/Users/82105/Desktop/push_analysis/data/processed/ignore_predictive_results.csv"
result.to_csv(output, index=False)

print(f"\nSaved: {output}")