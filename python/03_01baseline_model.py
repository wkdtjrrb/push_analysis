import pandas as pd

import lightgbm as lgb

from sklearn.metrics import roc_auc_score, average_precision_score

train_path = r"C:/Users/82105/Desktop/push_analysis/data/processed/08_train_final.parquet"

val_path = r"C:/Users/82105/Desktop/push_analysis/data/processed/08_val_final.parquet"

output_path = r"C:/Users/82105/Desktop/push_analysis/data/processed/messages_val_predictions_baseline.parquet"

features = [

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

boolean_features = [

    "subject_with_personalization",

    "subject_with_deadline",

    "subject_with_emoji",

    "subject_with_bonuses",

    "subject_with_discount",

    "subject_with_saleout"

]

train = pd.read_parquet(

    train_path,

    columns=features + ["is_opened", "is_clicked"]

)

val = pd.read_parquet(

    val_path,

    columns=features + ["is_opened", "is_clicked"]

)

for col in boolean_features:

    train[col] = train[col].astype("boolean").fillna(False).astype(bool)

    val[col] = val[col].astype("boolean").fillna(False).astype(bool)

train["channel"] = train["channel"].astype("category")

val["channel"] = val["channel"].astype("category")

val["channel"] = val["channel"].cat.set_categories(

    train["channel"].cat.categories

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

open_model.fit(X_train, y_open_train)

click_model.fit(X_train, y_click_train)

pred_open = open_model.predict_proba(X_val)[:, 1]

pred_click = click_model.predict_proba(X_val)[:, 1]

pred_ignore = 1 - pred_open

print("Open ROC-AUC:", round(

    roc_auc_score(y_open_val, pred_open), 4

))

print("Open PR-AUC:", round(

    average_precision_score(y_open_val, pred_open), 4

))

print("Click ROC-AUC:", round(

    roc_auc_score(y_click_val, pred_click), 4

))

print("Click PR-AUC:", round(

    average_precision_score(y_click_val, pred_click), 4

))

val["pred_open_prob"] = pred_open

val["pred_ignore_prob"] = pred_ignore

val["pred_click_prob"] = pred_click

val.to_parquet(

    output_path,

    index=False

)

print("Saved:", output_path)