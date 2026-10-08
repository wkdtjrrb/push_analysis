-- 메세지 카테고리 부여
COPY (
    SELECT
        m.id,
        m.client_id,
        m.campaign_id,
        m.message_type,
        m.sent_at,
        m.is_opened,
        m.is_clicked,
        c.category
    FROM read_parquet(
        'C:/Users/82105/Desktop/push_analysis/data/processed/02_messages_1y_first_purchase.parquet'
    ) m
    INNER JOIN read_csv_auto(
        'C:/Users/82105/Desktop/push_analysis/data/03_campaigns_categorized.csv'
    ) c
        ON c.id = m.campaign_id
        AND c.campaign_type = m.message_type
    WHERE c.category IN (
        'Marketing',
        'Behavioral',
        'Interest',
        'Lifecycle',
        'Transactional'
    )
)
TO 'C:/Users/82105/Desktop/push_analysis/data/processed/04_01_messages_category.parquet'
(FORMAT PARQUET, COMPRESSION ZSTD);