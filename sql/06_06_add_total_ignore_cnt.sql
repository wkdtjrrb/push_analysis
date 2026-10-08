COPY (
    SELECT
        *,
        CAST(
            mar_ignore_cnt
            + beh_ignore_cnt
            + interest_ignore_cnt
            + life_ignore_cnt
            + trans_ignore_cnt
            AS INTEGER
        ) AS total_ignore_cnt
    FROM read_parquet(
        'C:/Users/82105/Desktop/push_analysis/data/processed/messages_train_val_features.parquet'
    )
)
TO 'C:/Users/82105/Desktop/push_analysis/data/processed/messages_train_val_total_ignore.parquet'
(FORMAT PARQUET, COMPRESSION ZSTD);