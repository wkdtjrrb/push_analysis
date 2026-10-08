COPY (
    WITH base AS (
        SELECT
            *,
            COALESCE(
                SUM(
                    CASE
                        WHEN category = 'Marketing' AND is_opened THEN 1
                        ELSE 0
                    END
                ) OVER (
                    PARTITION BY client_id
                    ORDER BY sent_at, id
                    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                ),
                0
            ) AS mar_open_group
        FROM read_parquet(
            'C:/Users/82105/Desktop/push_analysis/data/processed/05_messages_train_val_raw.parquet'
        )
    )
    SELECT
        *,
        CAST(
            COALESCE(
                SUM(
                    CASE
                        WHEN category = 'Marketing' AND NOT is_opened THEN 1
                        ELSE 0
                    END
                ) OVER (
                    PARTITION BY client_id, mar_open_group
                    ORDER BY sent_at, id
                    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                ),
                0
            )
            AS INTEGER
        ) AS mar_ignore_cnt
    FROM base
)
TO 'C:/Users/82105/Desktop/push_analysis/data/processed/messages_mar_ignore.parquet'
(FORMAT PARQUET, COMPRESSION ZSTD);