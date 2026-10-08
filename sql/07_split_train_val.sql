COPY (
    SELECT *
    FROM read_parquet(
        'C:/Users/82105/Desktop/push_analysis/data/processed/06_messages_train_val_features_clean.parquet'
    )
    WHERE sent_at >= TIMESTAMP '2022-04-01'
      AND sent_at < TIMESTAMP '2022-12-01'
)
TO 'C:/Users/82105/Desktop/push_analysis/data/processed/07_messages_train.parquet'
(FORMAT PARQUET, COMPRESSION ZSTD);

COPY (
    SELECT *
    FROM read_parquet(
        'C:/Users/82105/Desktop/push_analysis/data/processed/06_messages_train_val_features_clean.parquet'
    )
    WHERE sent_at >= TIMESTAMP '2022-12-01'
      AND sent_at < TIMESTAMP '2023-02-01'
)
TO 'C:/Users/82105/Desktop/push_analysis/data/processed/07_messages_val.parquet'
(FORMAT PARQUET, COMPRESSION ZSTD);