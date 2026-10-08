COPY (
    WITH base AS (
        SELECT
            *,
            COALESCE(
                SUM(
                    CASE
                        WHEN category = 'Transactional' AND is_opened THEN 1
                        ELSE 0
                    END
                ) OVER (
                    PARTITION BY client_id
                    ORDER BY sent_at, id
                    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                ),
                0
            ) AS trans_open_group
        FROM read_parquet(
            'C:/Users/82105/Desktop/push_analysis/data/processed/messages_life_ignore.parquet'
        )
    )
    SELECT
        *,
        CAST(
            COALESCE(
                SUM(
                    CASE
                        WHEN category = 'Transactional' AND NOT is_opened THEN 1
                        ELSE 0
                    END
                ) OVER (
                    PARTITION BY client_id, trans_open_group
                    ORDER BY sent_at, id
                    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                ),
                0
            )
            AS INTEGER
        ) AS trans_ignore_cnt
    FROM base
)
TO 'C:/Users/82105/Desktop/push_analysis/data/processed/messages_train_val_features.parquet'
(FORMAT PARQUET, COMPRESSION ZSTD);