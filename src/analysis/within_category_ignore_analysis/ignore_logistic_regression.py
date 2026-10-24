import duckdb
import numpy as np
import pandas as pd
import statsmodels.api as sm

path = "C:/Users/82105/Desktop/push_analysis/data/processed/within_category_ignore_logistic_data.parquet"

categories = [
    "Marketing",
    "Behavioral",
    "Interest",
    "Lifecycle",
    "Transactional"
]

results = []
failures = []

con = duckdb.connect()

for category in categories:
    df = con.execute(
        """
        SELECT
            client_id,
            own_ignore_cnt,
            avg_user_total_ignore_rate,
            is_opened
        FROM read_parquet(?)
        WHERE category = ?
          AND client_id IS NOT NULL
          AND own_ignore_cnt IS NOT NULL
          AND avg_user_total_ignore_rate IS NOT NULL
          AND is_opened IS NOT NULL
        """,
        [path, category]
    ).df()

    y = df["is_opened"]

    models = {
        "Unadjusted": ["own_ignore_cnt"],
        "Adjusted": [
            "own_ignore_cnt",
            "avg_user_total_ignore_rate"
        ]
    }

    for model_name, variables in models.items():
        print(f"Running: {category} / {model_name}", flush=True)

        X = sm.add_constant(df[variables], has_constant="add")

        try:
            model = sm.GLM(
                y,
                X,
                family=sm.families.Binomial()
            )

            fit = model.fit(
                cov_type="cluster",
                cov_kwds={"groups": df["client_id"]}
            )

            beta = fit.params["own_ignore_cnt"]
            se = fit.bse["own_ignore_cnt"]
            p_value = fit.pvalues["own_ignore_cnt"]
            ci = fit.conf_int().loc["own_ignore_cnt"]

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

            print("Success", flush=True)

        except np.linalg.LinAlgError as e:
            failures.append({
                "category": category,
                "model": model_name,
                "error": str(e)
            })

            print(f"Failed: {e}", flush=True)

    del df

con.close()

print("\n[Regression Results]")

if results:
    print(pd.DataFrame(results).round(5).to_string(index=False))
else:
    print("No successful models")

print("\n[Failures]")

if failures:
    print(pd.DataFrame(failures).to_string(index=False))
else:
    print("None")  