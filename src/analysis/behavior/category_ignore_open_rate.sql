
COPY (
    WITH source_data AS (
        SELECT
            category,
            is_opened,
            CASE category
                WHEN 'Marketing' THEN mar_ignore_cnt
                WHEN 'Behavioral' THEN beh_ignore_cnt
                WHEN 'Interest' THEN interest_ignore_cnt
                WHEN 'Lifecycle' THEN life_ignore_cnt
                WHEN 'Transactional' THEN trans_ignore_cnt
            END AS ignore_cnt
        FROM read_parquet([
            'data/processed/06_messages_train.parquet',
            'data/processed/06_messages_val.parquet'
        ])
    ),
    cleaned AS (
        SELECT
            category,
            CAST(is_opened AS INTEGER) AS is_opened,
            CAST(ignore_cnt AS BIGINT) AS ignore_cnt
        FROM source_data
        WHERE category IN (
            'Marketing',
            'Behavioral',
            'Interest',
            'Lifecycle',
            'Transactional'
        )
        AND ignore_cnt IS NOT NULL
        AND ignore_cnt >= 0
        AND is_opened IN (0, 1)
    ),
    grouped AS (
        SELECT
            category,
            LEAST(ignore_cnt, 20) AS ignore_cnt,
            COUNT(*) AS total_sends,
            SUM(is_opened) AS opened_sends
        FROM cleaned
        GROUP BY
            category,
            LEAST(ignore_cnt, 20)
    )
    SELECT
        category,
        ignore_cnt,
        CASE
            WHEN ignore_cnt = 20 THEN '20+'
            ELSE CAST(ignore_cnt AS VARCHAR)
        END AS ignore_group,
        total_sends,
        opened_sends,
        total_sends - opened_sends AS ignored_sends,
        ROUND(
            100.0 * opened_sends / NULLIF(total_sends, 0),
            2
        ) AS open_rate,
        ROUND(
            100.0 * (total_sends - opened_sends) / NULLIF(total_sends, 0),
            2
        ) AS ignore_rate
    FROM grouped
    ORDER BY
        category,
        ignore_cnt
)
TO 'data/processed/category_ignore_open_rate.csv'
(FORMAT CSV, HEADER TRUE);
