WITH base AS (
    SELECT
        category,
        trigger_type,
        message_purpose,
        is_opened
    FROM read_parquet(
        'C:/Users/82105/Desktop/push_analysis/data/processed/06_messages_train.parquet'
    )
),
grouped AS (
    SELECT
        'Overall' AS dimension,
        'All' AS group_name,
        COUNT(*) AS messages,
        COUNT(*) FILTER (WHERE is_opened = TRUE) AS opens
    FROM base

    UNION ALL

    SELECT
        'Category',
        category,
        COUNT(*),
        COUNT(*) FILTER (WHERE is_opened = TRUE)
    FROM base
    GROUP BY category

    UNION ALL

    SELECT
        'Trigger Type',
        trigger_type,
        COUNT(*),
        COUNT(*) FILTER (WHERE is_opened = TRUE)
    FROM base
    GROUP BY trigger_type

    UNION ALL

    SELECT
        'Message Purpose',
        message_purpose,
        COUNT(*),
        COUNT(*) FILTER (WHERE is_opened = TRUE)
    FROM base
    GROUP BY message_purpose
)
SELECT
    dimension,
    group_name,
    messages,
    ROUND(100.0 * opens / NULLIF(messages, 0), 2) AS open_rate
FROM grouped
ORDER BY
    CASE dimension
        WHEN 'Overall' THEN 1
        WHEN 'Category' THEN 2
        WHEN 'Trigger Type' THEN 3
        WHEN 'Message Purpose' THEN 4
    END,
    messages DESC;