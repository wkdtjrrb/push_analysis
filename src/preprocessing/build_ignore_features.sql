COPY (
    WITH base AS (
        SELECT
            *,
            COALESCE(SUM(CASE WHEN category = 'Marketing' AND is_opened THEN 1 ELSE 0 END)
                OVER w, 0) AS mar_open_group,
            COALESCE(SUM(CASE WHEN category = 'Behavioral' AND is_opened THEN 1 ELSE 0 END)
                OVER w, 0) AS beh_open_group,
            COALESCE(SUM(CASE WHEN category = 'Interest' AND is_opened THEN 1 ELSE 0 END)
                OVER w, 0) AS interest_open_group,
            COALESCE(SUM(CASE WHEN category = 'Lifecycle' AND is_opened THEN 1 ELSE 0 END)
                OVER w, 0) AS life_open_group,
            COALESCE(SUM(CASE WHEN category = 'Transactional' AND is_opened THEN 1 ELSE 0 END)
                OVER w, 0) AS trans_open_group,
            COALESCE(SUM(CASE WHEN is_opened THEN 1 ELSE 0 END)
                OVER w, 0) AS total_open_group
        FROM read_parquet(
            'C:/Users/82105/Desktop/push_analysis/data/processed/04_messages_category.parquet'
        )
        WINDOW w AS (
            PARTITION BY client_id
            ORDER BY sent_at, id
            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        )
    ),
    counts AS (
        SELECT
            * EXCLUDE (
                mar_open_group,
                beh_open_group,
                interest_open_group,
                life_open_group,
                trans_open_group,
                total_open_group
            ),
            CAST(COALESCE(SUM(CASE WHEN category = 'Marketing' AND NOT is_opened THEN 1 ELSE 0 END)
                OVER (PARTITION BY client_id, mar_open_group ORDER BY sent_at, id
                      ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS INTEGER) AS mar_ignore_cnt,
            CAST(COALESCE(SUM(CASE WHEN category = 'Behavioral' AND NOT is_opened THEN 1 ELSE 0 END)
                OVER (PARTITION BY client_id, beh_open_group ORDER BY sent_at, id
                      ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS INTEGER) AS beh_ignore_cnt,
            CAST(COALESCE(SUM(CASE WHEN category = 'Interest' AND NOT is_opened THEN 1 ELSE 0 END)
                OVER (PARTITION BY client_id, interest_open_group ORDER BY sent_at, id
                      ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS INTEGER) AS interest_ignore_cnt,
            CAST(COALESCE(SUM(CASE WHEN category = 'Lifecycle' AND NOT is_opened THEN 1 ELSE 0 END)
                OVER (PARTITION BY client_id, life_open_group ORDER BY sent_at, id
                      ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS INTEGER) AS life_ignore_cnt,
            CAST(COALESCE(SUM(CASE WHEN category = 'Transactional' AND NOT is_opened THEN 1 ELSE 0 END)
                OVER (PARTITION BY client_id, trans_open_group ORDER BY sent_at, id
                      ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS INTEGER) AS trans_ignore_cnt,
            CAST(COALESCE(SUM(CASE WHEN NOT is_opened THEN 1 ELSE 0 END)
                OVER (PARTITION BY client_id, total_open_group ORDER BY sent_at, id
                      ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS INTEGER) AS total_consecutive_ignore_cnt
        FROM base
    ),
    totals AS (
        SELECT
            *,
            mar_ignore_cnt + beh_ignore_cnt + interest_ignore_cnt
            + life_ignore_cnt + trans_ignore_cnt AS total_ignore_cnt
        FROM counts
    )
    SELECT
        *,
        total_ignore_cnt -
            CASE category
                WHEN 'Marketing' THEN mar_ignore_cnt
                WHEN 'Behavioral' THEN beh_ignore_cnt
                WHEN 'Interest' THEN interest_ignore_cnt
                WHEN 'Lifecycle' THEN life_ignore_cnt
                WHEN 'Transactional' THEN trans_ignore_cnt
            END AS other_ignore_cnt
    FROM totals
)
TO 'C:/Users/82105/Desktop/push_analysis/data/processed/05_messages_ignore_features.parquet'
(FORMAT PARQUET, COMPRESSION ZSTD);