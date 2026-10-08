import duckdb

DB_PATH = "C:/Users/82105/Desktop/push_analysis/push_analysis.duckdb"
INPUT_PATH = "C:/Users/82105/Desktop/push_analysis/data/processed/06_messages_train_val_features_clean.parquet"

con = duckdb.connect(DB_PATH)

con.execute("""
CREATE OR REPLACE TABLE client_ignore_state AS
WITH latest AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY client_id
            ORDER BY sent_at DESC, id DESC
        ) AS rn
    FROM read_parquet(?)
    WHERE sent_at IS NOT NULL
      AND client_id <> 0
)
SELECT
    client_id,
    CASE
        WHEN category = 'Marketing' AND is_opened THEN 0
        WHEN category = 'Marketing' AND NOT is_opened THEN mar_ignore_cnt + 1
        ELSE mar_ignore_cnt
    END AS mar_ignore_cnt,
    CASE
        WHEN category = 'Behavioral' AND is_opened THEN 0
        WHEN category = 'Behavioral' AND NOT is_opened THEN beh_ignore_cnt + 1
        ELSE beh_ignore_cnt
    END AS beh_ignore_cnt,
    CASE
        WHEN category = 'Interest' AND is_opened THEN 0
        WHEN category = 'Interest' AND NOT is_opened THEN interest_ignore_cnt + 1
        ELSE interest_ignore_cnt
    END AS interest_ignore_cnt,
    CASE
        WHEN category = 'Lifecycle' AND is_opened THEN 0
        WHEN category = 'Lifecycle' AND NOT is_opened THEN life_ignore_cnt + 1
        ELSE life_ignore_cnt
    END AS life_ignore_cnt,
    CASE
        WHEN category = 'Transactional' AND is_opened THEN 0
        WHEN category = 'Transactional' AND NOT is_opened THEN trans_ignore_cnt + 1
        ELSE trans_ignore_cnt
    END AS trans_ignore_cnt,
    sent_at AS last_sent_at,
    id AS last_id
FROM latest
WHERE rn = 1
""", [INPUT_PATH])

con.execute("""
CREATE TABLE IF NOT EXISTS processed_file_log (
    file_name VARCHAR PRIMARY KEY,
    processed_at TIMESTAMP,
    min_sent_at TIMESTAMP,
    max_sent_at TIMESTAMP,
    row_count BIGINT,
    status VARCHAR
)
""")

con.close()

print("초기 state 생성 완료")