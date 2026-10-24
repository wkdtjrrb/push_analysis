COPY (
    WITH base AS (
        SELECT
            client_id,
            id,
            sent_at,
            category,
            CASE category
                WHEN 'Marketing' THEN mar_ignore_cnt
                WHEN 'Behavioral' THEN beh_ignore_cnt
                WHEN 'Interest' THEN interest_ignore_cnt
                WHEN 'Lifecycle' THEN life_ignore_cnt
                WHEN 'Transactional' THEN trans_ignore_cnt
            END AS own_ignore_cnt,
            CAST(is_opened AS INTEGER) AS is_opened
        FROM read_parquet(
            'C:/Users/82105/Desktop/push_analysis/data/processed/05_messages_ignore_features.parquet'
        )
    ),
    features AS (
        SELECT
            client_id,
            sent_at,
            category,
            own_ignore_cnt,
            is_opened,
            COUNT(*) OVER (
                PARTITION BY client_id
                ORDER BY sent_at, id
                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
            ) AS previous_messages,
            SUM(
                CASE WHEN is_opened = 0 THEN 1 ELSE 0 END
            ) OVER (
                PARTITION BY client_id
                ORDER BY sent_at, id
                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
            ) AS previous_ignores
        FROM base
    )
    SELECT
        client_id,
        category,
        own_ignore_cnt,
        is_opened,
        COALESCE(
            previous_ignores * 1.0 / NULLIF(previous_messages, 0),
            0
        ) AS avg_user_total_ignore_rate
    FROM features
    WHERE sent_at >= '2022-04-01'
      AND sent_at < '2022-12-01'
      AND client_id IS NOT NULL
      AND own_ignore_cnt IS NOT NULL
      AND is_opened IS NOT NULL
)
TO 'C:/Users/82105/Desktop/push_analysis/data/processed/within_category_ignore_logistic_data.parquet'
(FORMAT PARQUET, COMPRESSION ZSTD, OVERWRITE_OR_IGNORE TRUE);