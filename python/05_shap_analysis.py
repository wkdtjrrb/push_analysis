import os

import pandas as pd
import lightgbm as lgb
import shap
import matplotlib.pyplot as plt

from sklearn.metrics import roc_auc_score, average_precision_score


train_path = r"C:/Users/82105/Desktop/push_analysis/data/processed/08_train_final.parquet"
val_path = r"C:/Users/82105/Desktop/push_analysis/data/processed/08_val_final.parquet"

output_dir = r"C:/Users/82105/Desktop/push_analysis/data/processed/shap"

os.makedirs(output_dir, exist_ok=True)


features = [
    "mar_ignore_cnt",
    "beh_ignore_cnt",
    "interest_ignore_cnt",
    "life_ignore_cnt",
    "trans_ignore_cnt",
    "total_ignore_cnt",
    "other_ignore_cnt",
    "avg_user_total_ignore_rate",
    "channel",
    "hour_limit",
    "subject_length",
    "subject_with_personalization",
    "subject_with_deadline",
    "subject_with_emoji",
    "subject_with_bonuses",
    "subject_with_discount",
    "subject_with_saleout"
]




categorical_features = [
    "channel"
]


train = pd.read_parquet(
    train_path,
    columns=features + ["is_opened", "is_clicked"]
)

val = pd.read_parquet(
    val_path,
    columns=features + [
        "is_opened",
        "is_clicked",
        "category"
    ]
)

boolean_features = [
    "subject_with_personalization",
    "subject_with_deadline",
    "subject_with_emoji",
    "subject_with_bonuses",
    "subject_with_discount",
    "subject_with_saleout"
]

for col in boolean_features:
    train[col] = train[col].fillna(False).astype(bool)
    val[col] = val[col].fillna(False).astype(bool)

channel_categories = train["channel"].dropna().unique()

train["channel"] = pd.Categorical(
    train["channel"],
    categories=channel_categories
)

val["channel"] = pd.Categorical(
    val["channel"],
    categories=channel_categories
)


X_train = train[features]
X_val = val[features]

y_open_train = train["is_opened"].astype(int)
y_open_val = val["is_opened"].astype(int)

y_click_train = train["is_clicked"].astype(int)
y_click_val = val["is_clicked"].astype(int)


open_model = lgb.LGBMClassifier(
    objective="binary",
    n_estimators=300,
    learning_rate=0.05,
    num_leaves=31,
    random_state=42,
    n_jobs=-1
)

click_model = lgb.LGBMClassifier(
    objective="binary",
    n_estimators=300,
    learning_rate=0.05,
    num_leaves=31,
    random_state=42,
    n_jobs=-1
)


print("\n=== TRAIN OPEN MODEL ===")

open_model.fit(
    X_train,
    y_open_train,
    categorical_feature=categorical_features
)


print("\n=== TRAIN CLICK MODEL ===")

click_model.fit(
    X_train,
    y_click_train,
    categorical_feature=categorical_features
)


pred_open = open_model.predict_proba(X_val)[:, 1]
pred_click = click_model.predict_proba(X_val)[:, 1]


print("\n=== MODEL PERFORMANCE ===")

print(
    "Open ROC-AUC:",
    round(roc_auc_score(y_open_val, pred_open), 4)
)

print(
    "Open PR-AUC:",
    round(average_precision_score(y_open_val, pred_open), 4)
)

print(
    "Click ROC-AUC:",
    round(roc_auc_score(y_click_val, pred_click), 4)
)

print(
    "Click PR-AUC:",
    round(average_precision_score(y_click_val, pred_click), 4)
)


open_explainer = shap.TreeExplainer(open_model)
click_explainer = shap.TreeExplainer(click_model)


categories = [
    "Marketing",
    "Behavioral",
    "Interest",
    "Lifecycle",
    "Transactional"
]


summary_results = []


def get_shap_values(explainer, X):
    shap_values = explainer.shap_values(X)

    if isinstance(shap_values, list):
        shap_values = shap_values[1]

    if hasattr(shap_values, "values"):
        shap_values = shap_values.values

    if shap_values.ndim == 3:
        shap_values = shap_values[:, :, 1]

    return shap_values


for category in categories:

    print("\n" + "=" * 70)
    print("CATEGORY:", category)
    print("=" * 70)

    category_df = val[
        val["category"] == category
    ].copy()

    if len(category_df) == 0:
        print("No data:", category)
        continue

    X_category = category_df[features]

    print("Rows:", f"{len(category_df):,}")


    open_shap = get_shap_values(
        open_explainer,
        X_category
    )

    open_mean_abs = pd.DataFrame({
        "feature": features,
        "mean_abs_shap": abs(open_shap).mean(axis=0)
    }).sort_values(
        "mean_abs_shap",
        ascending=False
    )

    open_direction = pd.DataFrame(
        open_shap,
        columns=features
    ).mean()

    open_mean_abs["mean_shap"] = (
        open_mean_abs["feature"].map(open_direction)
    )

    open_mean_abs["direction"] = open_mean_abs[
        "mean_shap"
    ].apply(
        lambda x: "increase_ignore"
        if x > 0
        else "decrease_ignore"
    )

    open_mean_abs["category"] = category
    open_mean_abs["target"] = "ignore"

    summary_results.append(
        open_mean_abs[
            [
                "category",
                "target",
                "feature",
                "mean_abs_shap",
                "mean_shap",
                "direction"
            ]
        ]
    )


    plt.figure(figsize=(10, 7))

    shap.summary_plot(
        open_shap,
        X_category,
        feature_names=features,
        plot_type="bar",
        show=False
    )

    plt.title(
        f"{category} - Ignore Model SHAP"
    )

    plt.tight_layout()

    plt.savefig(
        os.path.join(
            output_dir,
            f"{category.lower()}_ignore_shap_bar.png"
        ),
        dpi=200,
        bbox_inches="tight"
    )

    plt.close()


    plt.figure(figsize=(10, 7))

    shap.summary_plot(
        open_shap,
        X_category,
        feature_names=features,
        show=False
    )

    plt.title(
        f"{category} - Ignore Model SHAP"
    )

    plt.tight_layout()

    plt.savefig(
        os.path.join(
            output_dir,
            f"{category.lower()}_ignore_shap_summary.png"
        ),
        dpi=200,
        bbox_inches="tight"
    )

    plt.close()


    click_shap = get_shap_values(
        click_explainer,
        X_category
    )

    click_mean_abs = pd.DataFrame({
        "feature": features,
        "mean_abs_shap": abs(click_shap).mean(axis=0)
    }).sort_values(
        "mean_abs_shap",
        ascending=False
    )

    click_direction = pd.DataFrame(
        click_shap,
        columns=features
    ).mean()

    click_mean_abs["mean_shap"] = (
        click_mean_abs["feature"].map(click_direction)
    )

    click_mean_abs["direction"] = click_mean_abs[
        "mean_shap"
    ].apply(
        lambda x: "increase_click"
        if x > 0
        else "decrease_click"
    )

    click_mean_abs["category"] = category
    click_mean_abs["target"] = "click"

    summary_results.append(
        click_mean_abs[
            [
                "category",
                "target",
                "feature",
                "mean_abs_shap",
                "mean_shap",
                "direction"
            ]
        ]
    )


    plt.figure(figsize=(10, 7))

    shap.summary_plot(
        click_shap,
        X_category,
        feature_names=features,
        plot_type="bar",
        show=False
    )

    plt.title(
        f"{category} - Click Model SHAP"
    )

    plt.tight_layout()

    plt.savefig(
        os.path.join(
            output_dir,
            f"{category.lower()}_click_shap_bar.png"
        ),
        dpi=200,
        bbox_inches="tight"
    )

    plt.close()


    plt.figure(figsize=(10, 7))

    shap.summary_plot(
        click_shap,
        X_category,
        feature_names=features,
        show=False
    )

    plt.title(
        f"{category} - Click Model SHAP"
    )

    plt.tight_layout()

    plt.savefig(
        os.path.join(
            output_dir,
            f"{category.lower()}_click_shap_summary.png"
        ),
        dpi=200,
        bbox_inches="tight"
    )

    plt.close()


    print("\nIgnore TOP features")

    print(
        open_mean_abs[
            [
                "feature",
                "mean_abs_shap",
                "mean_shap",
                "direction"
            ]
        ].to_string(index=False)
    )


    print("\nClick TOP features")

    print(
        click_mean_abs[
            [
                "feature",
                "mean_abs_shap",
                "mean_shap",
                "direction"
            ]
        ].to_string(index=False)
    )


summary = pd.concat(
    summary_results,
    ignore_index=True
)


summary = summary.sort_values(
    [
        "target",
        "category",
        "mean_abs_shap"
    ],
    ascending=[
        True,
        True,
        False
    ]
)


summary_path = os.path.join(
    output_dir,
    "shap_summary_by_category.csv"
)


summary.to_csv(
    summary_path,
    index=False
)


print("\n" + "=" * 70)
print("SHAP ANALYSIS COMPLETE")
print("=" * 70)

print("Saved:", summary_path)
print("Output directory:", output_dir)