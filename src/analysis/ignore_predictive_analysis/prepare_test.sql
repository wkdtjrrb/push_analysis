
COPY (
    WITH campaigns AS (
        SELECT
            id,
            campaign_type
        FROM read_csv_auto(
            'C:/Users/82105/Desktop/push_analysis/data/campaigns_categorized.csv'
        )
    ),
    base AS (
        SELECT
            m.client_id,
            m.id,
            m.campaign_id,
            m.sent_at,
            m.category,
            c.campaign_type,
            m.channel_1 AS channel,
            m.topic,
            CAST(m.ab_test AS INTEGER) AS ab_test,
            CAST(m.warmup_mode AS INTEGER) AS warmup_mode,
            m.hour_limit,
            m.subject_length,
            CAST(m.subject_with_personalization AS INTEGER) AS subject_with_personalization,
            CAST(m.subject_with_deadline AS INTEGER) AS subject_with_deadline,
            CAST(m.subject_with_emoji AS INTEGER) AS subject_with_emoji,
            CAST(m.subject_with_bonuses AS INTEGER) AS subject_with_bonuses,
            CAST(m.subject_with_discount AS INTEGER) AS subject_with_discount,
            CAST(m.subject_with_saleout AS INTEGER) AS subject_with_saleout,
            m.mar_ignore_cnt,
            m.beh_ignore_cnt,
            m.interest_ignore_cnt,
            m.life_ignore_cnt,
            m.trans_ignore_cnt,
            CASE m.category
                WHEN 'Marketing' THEN m.mar_ignore_cnt
                WHEN 'Behavioral' THEN m.beh_ignore_cnt
                WHEN 'Interest' THEN m.interest_ignore_cnt
                WHEN 'Lifecycle' THEN m.life_ignore_cnt
                WHEN 'Transactional' THEN m.trans_ignore_cnt
            END AS own_ignore_cnt,
            m.other_ignore_cnt,
            m.total_consecutive_ignore_cnt,
            CAST(m.is_opened AS INTEGER) AS is_opened,
            CAST(m.is_clicked AS INTEGER) AS is_clicked,
            CAST(m.is_purchased AS INTEGER) AS is_purchased,
            CAST(m.is_unsubscribed AS INTEGER) AS is_unsubscribed
        FROM read_parquet(
            'C:/Users/82105/Desktop/push_analysis/data/processed/05_messages_ignore_features.parquet'
        ) m
        LEFT JOIN campaigns c
            ON m.campaign_id = c.id
        WHERE m.client_id IS NOT NULL
    ),
    features AS (
        SELECT
            *,
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
        campaign_id,
        sent_at,
        category,
        campaign_type,
        channel,
        topic,
        ab_test,
        warmup_mode,
        hour_limit,
        subject_length,
        subject_with_personalization,
        subject_with_deadline,
        subject_with_emoji,
        subject_with_bonuses,
        subject_with_discount,
        subject_with_saleout,
        mar_ignore_cnt,
        beh_ignore_cnt,
        interest_ignore_cnt,
        life_ignore_cnt,
        trans_ignore_cnt,
        own_ignore_cnt,
        other_ignore_cnt,
        total_consecutive_ignore_cnt,
        is_opened,
        is_clicked,
        is_purchased,
        is_unsubscribed,
        COALESCE(
            previous_ignores * 1.0 / NULLIF(previous_messages, 0),
            0
        ) AS avg_user_total_ignore_rate,
        'test' AS dataset
    FROM features
    WHERE sent_at >= '2023-02-01'
      AND sent_at < '2023-04-01'
      AND own_ignore_cnt IS NOT NULL
      AND other_ignore_cnt IS NOT NULL
      AND total_consecutive_ignore_cnt IS NOT NULL
      AND is_opened IS NOT NULL
)
TO 'C:/Users/82105/Desktop/push_analysis/data/processed/ignore_predictive_test.parquet'
(FORMAT PARQUET, COMPRESSION ZSTD, OVERWRITE_OR_IGNORE TRUE);
