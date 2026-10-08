COPY (
    SELECT
        *,
        CAST(
            CASE
                WHEN category = 'Marketing'
                    THEN beh_ignore_cnt
                       + interest_ignore_cnt
                       + life_ignore_cnt
                       + trans_ignore_cnt
                WHEN category = 'Behavioral'
                    THEN mar_ignore_cnt
                       + interest_ignore_cnt
                       + life_ignore_cnt
                       + trans_ignore_cnt
                WHEN category = 'Interest'
                    THEN mar_ignore_cnt
                       + beh_ignore_cnt
                       + life_ignore_cnt
                       + trans_ignore_cnt
                WHEN category = 'Lifecycle'
                    THEN mar_ignore_cnt
                       + beh_ignore_cnt
                       + interest_ignore_cnt
                       + trans_ignore_cnt
                WHEN category = 'Transactional'
                    THEN mar_ignore_cnt
                       + beh_ignore_cnt
                       + interest_ignore_cnt
                       + life_ignore_cnt
            END AS INTEGER
        ) AS other_ignore_cnt
    FROM read_parquet(
        'C:/Users/82105/Desktop/push_analysis/data/processed/messages_train_val_total_ignore.parquet'
    )
)
TO 'C:/Users/82105/Desktop/push_analysis/data/processed/messages_train_val_other_ignore.parquet'
(FORMAT PARQUET, COMPRESSION ZSTD);