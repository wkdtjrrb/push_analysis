-- 데이터 분할
COPY (
    SELECT *
    FROM read_parquet(
        'C:/Users/82105/Desktop/push_analysis/data/processed/04_02_messages_features.parquet'
    )
    WHERE sent_at >= TIMESTAMP '2022-04-01'
      AND sent_at < TIMESTAMP '2023-02-01'
)
TO 'C:/Users/82105/Desktop/push_analysis/data/processed/05_messages_train_val_raw.parquet'
(FORMAT PARQUET, COMPRESSION ZSTD);

COPY (
    SELECT *
    FROM read_parquet(
        'C:/Users/82105/Desktop/push_analysis/data/processed/04_02_messages_features.parquet'
    )
    WHERE sent_at >= TIMESTAMP '2023-02-01'
      AND sent_at < TIMESTAMP '2023-04-01'
)
TO 'C:/Users/82105/Desktop/push_analysis/data/processed/05_messages_test_raw.parquet'
(FORMAT PARQUET, COMPRESSION ZSTD);