COPY (
    WITH base AS (
        SELECT
            *,
            COALESCE(
                SUM(
                    CASE
                        WHEN category = 'Behavioral' AND is_opened THEN 1
                        ELSE 0
                    END
                ) OVER (
                    PARTITION BY client_id
                    ORDER BY sent_at, id
                    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                ),
                0
            ) AS beh_open_group
        FROM read_parquet(
            'C:/Users/82105/Desktop/push_analysis/data/processed/messages_mar_ignore.parquet'
        )
    )
    SELECT
        *,
        CAST(
            COALESCE(
                SUM(
                    CASE
                        WHEN category = 'Behavioral' AND NOT is_opened THEN 1
                        ELSE 0
                    END
                ) OVER (
                    PARTITION BY client_id, beh_open_group
                    ORDER BY sent_at, id
                    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                ),
                0
            )
            AS INTEGER
        ) AS beh_ignore_cnt
    FROM base
)
TO 'C:/Users/82105/Desktop/push_analysis/data/processed/messages_beh_ignore.parquet'
(FORMAT PARQUET, COMPRESSION ZSTD);