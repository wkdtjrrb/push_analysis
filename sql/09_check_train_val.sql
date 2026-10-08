SELECT
    'train' AS dataset,
    COUNT(*) AS push_cnt,
    COUNT(DISTINCT client_id) AS client_cnt,
    MIN(sent_at) AS min_sent_at,
    MAX(sent_at) AS max_sent_at
FROM read_parquet(
    'C:/Users/82105/Desktop/push_analysis/data/processed/08_train_final.parquet'
)

UNION ALL

SELECT
    'validation',
    COUNT(*),
    COUNT(DISTINCT client_id),
    MIN(sent_at),
    MAX(sent_at)
FROM read_parquet(
    'C:/Users/82105/Desktop/push_analysis/data/processed/08_val_final.parquet'
);