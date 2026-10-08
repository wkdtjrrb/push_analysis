CREATE OR REPLACE TABLE train_user_ignore_rate AS
SELECT
    client_id,
    AVG(1.0 - CAST(is_opened AS DOUBLE)) AS avg_user_total_ignore_rate
FROM read_parquet(
    'C:/Users/82105/Desktop/push_analysis/data/processed/07_messages_train.parquet'
)
GROUP BY client_id;

COPY (
    SELECT
        t.*,
        u.avg_user_total_ignore_rate
    FROM read_parquet(
        'C:/Users/82105/Desktop/push_analysis/data/processed/07_messages_train.parquet'
    ) t
    LEFT JOIN train_user_ignore_rate u
        ON t.client_id = u.client_id
)
TO 'C:/Users/82105/Desktop/push_analysis/data/processed/08_train_final.parquet'
(FORMAT PARQUET, COMPRESSION ZSTD);

COPY (
    SELECT
        v.*,
        COALESCE(
            u.avg_user_total_ignore_rate,
            (SELECT AVG(avg_user_total_ignore_rate) FROM train_user_ignore_rate)
        ) AS avg_user_total_ignore_rate
    FROM read_parquet(
        'C:/Users/82105/Desktop/push_analysis/data/processed/07_messages_val.parquet'
    ) v
    LEFT JOIN train_user_ignore_rate u
        ON v.client_id = u.client_id
)
TO 'C:/Users/82105/Desktop/push_analysis/data/processed/08_val_final.parquet'
(FORMAT PARQUET, COMPRESSION ZSTD);