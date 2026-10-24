COPY (
    SELECT
        m.* EXCLUDE (category),
        c.* EXCLUDE (id, campaign_type)
    FROM read_parquet(
        'C:/Users/82105/Desktop/push_analysis/data/processed/02_messages_1y_first_purchase.parquet'
    ) m
    INNER JOIN read_parquet(
        'C:/Users/82105/Desktop/push_analysis/data/processed/03_campaigns_categorized.parquet'
    ) c
        ON m.campaign_id = c.id
        AND m.message_type = c.campaign_type
    WHERE c.category IN (
        'Marketing',
        'Behavioral',
        'Interest',
        'Lifecycle',
        'Transactional'
    )
)
TO 'C:/Users/82105/Desktop/push_analysis/data/processed/04_messages_category.parquet'
(FORMAT PARQUET, COMPRESSION ZSTD);