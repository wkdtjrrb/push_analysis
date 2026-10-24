import duckdb
import numpy as np
import pandas as pd
import statsmodels.api as sm

path = "C:/Users/82105/Desktop/push_analysis/data/processed/ignore_logistic_data.parquet"

categories = [
    "Marketing",
    "Behavioral",
    "Interest",
    "Lifecycle",
    "Transactional"
]

results = []

con = duckdb.connect()

for category in categories:
    df = con.execute(
        """
        SELECT
            client_id,
            other_ignore_cnt,
            avg_user_total_ignore_rate,
            is_opened
        FROM read_parquet(?)
        WHERE category = ?
          AND sent_at >= '2022-04-01'
          AND sent_at < '2022-12-01'
          AND client_id IS NOT NULL
          AND other_ignore_cnt IS NOT NULL
          AND avg_user_total_ignore_rate IS NOT NULL
          AND is_opened IS NOT NULL
        """,
        [path, category]
    ).df()

    y = df["is_opened"]

    models = {
        "Unadjusted": ["other_ignore_cnt"],
        "Adjusted": [
            "other_ignore_cnt",
            "avg_user_total_ignore_rate"
        ]
    }

    for model_name, variables in models.items():
        X = sm.add_constant(df[variables], has_constant="add")

        model = sm.GLM(
            y,
            X,
            family=sm.families.Binomial()
        )

        fit = model.fit(
            cov_type="cluster",
            cov_kwds={"groups": df["client_id"]}
        )

        beta = fit.params["other_ignore_cnt"]
        se = fit.bse["other_ignore_cnt"]
        p_value = fit.pvalues["other_ignore_cnt"]
        ci = fit.conf_int().loc["other_ignore_cnt"]

        results.append({
            "category": category,
            "model": model_name,
            "messages": len(df),
            "beta": beta,
            "odds_ratio": np.exp(beta),
            "cluster_se": se,
            "or_ci_lower": np.exp(ci.iloc[0]),
            "or_ci_upper": np.exp(ci.iloc[1]),
            "p_value": p_value
        })

    del df, X, y, model, fit

con.close()

result = pd.DataFrame(results)

print(
    result.round(5).to_string(index=False)
)