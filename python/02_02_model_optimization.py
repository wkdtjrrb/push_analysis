import pandas as pd
import numpy as np

input_path = r"C:/Users/82105/Desktop/push_analysis/data/processed/messages_val_predictions_multi.parquet"
output_path = r"C:/Users/82105/Desktop/push_analysis/data/processed/multi_objective_optimization.csv"

df = pd.read_parquet(
    input_path,
    columns=[
        "is_opened",
        "is_clicked",
        "pred_ignore_prob",
        "pred_click_prob"
    ]
)

df["is_opened"] = df["is_opened"].astype(int)
df["is_clicked"] = df["is_clicked"].astype(int)

total_push = len(df)
total_open = df["is_opened"].sum()
total_click = df["is_clicked"].sum()

lambdas = np.round(
    np.arange(0.0, 3.01, 0.1),
    2
)

thresholds = np.round(
    np.arange(0.50, 1.00, 0.01),
    2
)

results = []

for lam in lambdas:

    df["decision_score"] = (
        df["pred_ignore_prob"]
        - lam * df["pred_click_prob"]
    )

    for threshold in thresholds:

        blocked = df["decision_score"] >= threshold

        blocked_df = df.loc[blocked]

        blocked_push = len(blocked_df)
        blocked_open = blocked_df["is_opened"].sum()
        blocked_click = blocked_df["is_clicked"].sum()

        push_reduction_rate = (
            blocked_push / total_push * 100
        )

        open_loss_rate = (
            blocked_open / total_open * 100
            if total_open > 0 else 0
        )

        click_loss_rate = (
            blocked_click / total_click * 100
            if total_click > 0 else 0
        )

        results.append({
            "lambda": lam,
            "threshold": threshold,
            "push_reduction_rate": push_reduction_rate,
            "open_loss_rate": open_loss_rate,
            "click_loss_rate": click_loss_rate,
            "blocked_push": blocked_push,
            "blocked_open": blocked_open,
            "blocked_click": blocked_click
        })

result = pd.DataFrame(results)

result[
    [
        "push_reduction_rate",
        "open_loss_rate",
        "click_loss_rate"
    ]
] = result[
    [
        "push_reduction_rate",
        "open_loss_rate",
        "click_loss_rate"
    ]
].round(4)

print("\n=== SEARCH COMPLETE ===")
print("Total combinations:", len(result))

limits = [5, 10, 15, 20, 25]

optimization_results = []

for open_limit in limits:

    for click_limit in limits:

        candidates = result[
            (result["open_loss_rate"] <= open_limit) &
            (result["click_loss_rate"] <= click_limit)
        ]

        if len(candidates) == 0:

            optimization_results.append({
                "open_loss_limit": open_limit,
                "click_loss_limit": click_limit,
                "lambda": None,
                "threshold": None,
                "push_reduction_rate": None,
                "open_loss_rate": None,
                "click_loss_rate": None,
                "blocked_push": None,
                "blocked_open": None,
                "blocked_click": None
            })

        else:

            best = candidates.loc[
                candidates["push_reduction_rate"].idxmax()
            ]

            optimization_results.append({
                "open_loss_limit": open_limit,
                "click_loss_limit": click_limit,
                "lambda": best["lambda"],
                "threshold": best["threshold"],
                "push_reduction_rate": best["push_reduction_rate"],
                "open_loss_rate": best["open_loss_rate"],
                "click_loss_rate": best["click_loss_rate"],
                "blocked_push": best["blocked_push"],
                "blocked_open": best["blocked_open"],
                "blocked_click": best["blocked_click"]
            })

optimization = pd.DataFrame(
    optimization_results
)

print("\n=== OPTIMAL SOLUTIONS ===")
print(
    optimization.to_string(
        index=False
    )
)

optimization.to_csv(
    output_path,
    index=False
)

print("\nSaved:", output_path)