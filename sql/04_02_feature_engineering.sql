COPY (
    SELECT
        m.*,
        c.* EXCLUDE (id, campaign_type)
    FROM read_parquet(
        'C:/Users/82105/Desktop/push_analysis/data/processed/04_01_messages_category.parquet'
    ) m
    LEFT JOIN read_csv_auto(
        'C:/Users/82105/Desktop/push_analysis/data/campaigns.csv',
        header=true
    ) c
    ON m.campaign_id = c.id
    AND m.message_type = c.campaign_type
)
TO 'C:/Users/82105/Desktop/push_analysis/data/processed/04_02_messages_features.parquet'
(FORMAT PARQUET, COMPRESSION ZSTD);