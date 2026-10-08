COPY (
    SELECT
        'Marketing' AS category,
        mar_ignore_cnt AS ignore_cnt,
        COUNT(*) AS push_cnt,
        ROUND(
            AVG(CASE WHEN NOT is_opened THEN 1.0 ELSE 0.0 END) * 100,
            2
        ) AS ignore_rate
    FROM read_parquet(
        'C:/Users/82105/Desktop/push_analysis/data/processed/08_messages_train.parquet'
    )
    WHERE category = 'Marketing'
    GROUP BY mar_ignore_cnt

    UNION ALL

    SELECT
        'Behavioral',
        beh_ignore_cnt,
        COUNT(*),
        ROUND(
            AVG(CASE WHEN NOT is_opened THEN 1.0 ELSE 0.0 END) * 100,
            2
        )
    FROM read_parquet(
        'C:/Users/82105/Desktop/push_analysis/data/processed/08_messages_train.parquet'
    )
    WHERE category = 'Behavioral'
    GROUP BY beh_ignore_cnt

    UNION ALL

    SELECT
        'Interest',
        interest_ignore_cnt,
        COUNT(*),
        ROUND(
            AVG(CASE WHEN NOT is_opened THEN 1.0 ELSE 0.0 END) * 100,
            2
        )
    FROM read_parquet(
        'C:/Users/82105/Desktop/push_analysis/data/processed/08_messages_train.parquet'
    )
    WHERE category = 'Interest'
    GROUP BY interest_ignore_cnt

    UNION ALL

    SELECT
        'Lifecycle',
        life_ignore_cnt,
        COUNT(*),
        ROUND(
            AVG(CASE WHEN NOT is_opened THEN 1.0 ELSE 0.0 END) * 100,
            2
        )
    FROM read_parquet(
        'C:/Users/82105/Desktop/push_analysis/data/processed/08_messages_train.parquet'
    )
    WHERE category = 'Lifecycle'
    GROUP BY life_ignore_cnt

    UNION ALL

    SELECT
        'Transactional',
        trans_ignore_cnt,
        COUNT(*),
        ROUND(
            AVG(CASE WHEN NOT is_opened THEN 1.0 ELSE 0.0 END) * 100,
            2
        )
    FROM read_parquet(
        'C:/Users/82105/Desktop/push_analysis/data/processed/08_messages_train.parquet'
    )
    WHERE category = 'Transactional'
    GROUP BY trans_ignore_cnt

    UNION ALL

    SELECT
        'Other',
        other_ignore_cnt,
        COUNT(*),
        ROUND(
            AVG(CASE WHEN NOT is_opened THEN 1.0 ELSE 0.0 END) * 100,
            2
        )
    FROM read_parquet(
        'C:/Users/82105/Desktop/push_analysis/data/processed/08_train_final.parquet'
    )
    GROUP BY other_ignore_cnt

    UNION ALL

    SELECT
        'Total',
        total_ignore_cnt,
        COUNT(*),
        ROUND(
            AVG(CASE WHEN NOT is_opened THEN 1.0 ELSE 0.0 END) * 100,
            2
        )
    FROM read_parquet(
        'C:/Users/82105/Desktop/push_analysis/data/processed/08_train_final.parquet'
    )
    GROUP BY total_ignore_cnt
)
TO 'C:/Users/82105/Desktop/push_analysis/data/processed/09_visualization_ignore_rate_by_cnt.csv'
(FORMAT CSV, HEADER, DELIMITER ',');