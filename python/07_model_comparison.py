import pandas as pd

from sklearn.metrics import roc_auc_score, average_precision_score

baseline_path = r"C:/Users/82105/Desktop/push_analysis/data/processed/messages_val_predictions_baseline.parquet"

full_path = r"C:/Users/82105/Desktop/push_analysis/data/processed/messages_val_predictions_multi.parquet"

baseline = pd.read_parquet(baseline_path)

full = pd.read_parquet(full_path)

y_open = baseline["is_opened"].astype(int)

y_click = baseline["is_clicked"].astype(int)

results = []

results.append({
    "model": "Baseline",
    "open_roc_auc": roc_auc_score(
        y_open,
        baseline["pred_open_prob"]
    ),
    "open_pr_auc": average_precision_score(
        y_open,
        baseline["pred_open_prob"]
    ),
    "click_roc_auc": roc_auc_score(
        y_click,
        baseline["pred_click_prob"]
    ),
    "click_pr_auc": average_precision_score(
        y_click,
        baseline["pred_click_prob"]
    )
})

results.append({
    "model": "Full",
    "open_roc_auc": roc_auc_score(
        y_open,
        full["pred_open_prob"]
    ),
    "open_pr_auc": average_precision_score(
        y_open,
        full["pred_open_prob"]
    ),
    "click_roc_auc": roc_auc_score(
        y_click,
        full["pred_click_prob"]
    ),
    "click_pr_auc": average_precision_score(
        y_click,
        full["pred_click_prob"]
    )
})

results_df = pd.DataFrame(results)

print(results_df.to_string(index=False))

baseline_result = results_df[
    results_df["model"] == "Baseline"
].iloc[0]

full_result = results_df[
    results_df["model"] == "Full"
].iloc[0]

print()
print("=== Improvement ===")
print(
    "Open ROC-AUC:",
    round(
        full_result["open_roc_auc"] -
        baseline_result["open_roc_auc"],
        4
    )
)

print(
    "Open PR-AUC:",
    round(
        full_result["open_pr_auc"] -
        baseline_result["open_pr_auc"],
        4
    )
)

print(
    "Click ROC-AUC:",
    round(
        full_result["click_roc_auc"] -
        baseline_result["click_roc_auc"],
        4
    )
)

print(
    "Click PR-AUC:",
    round(
        full_result["click_pr_auc"] -
        baseline_result["click_pr_auc"],
        4
    )
)

print()
print("=== Improvement Rate ===")

print(
    "Open PR-AUC:",
    round(
        (
            full_result["open_pr_auc"] /
            baseline_result["open_pr_auc"] - 1
        ) * 100,
        2
    ),
    "%"
)

print(
    "Click PR-AUC:",
    round(
        (
            full_result["click_pr_auc"] /
            baseline_result["click_pr_auc"] - 1
        ) * 100,
        2
    ),
    "%"
)