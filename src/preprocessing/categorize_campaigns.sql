COPY (
    SELECT
        c.*,
        COALESCE(t.category, 'Uncategorized') AS category,
        COALESCE(t.trigger_type, 'Unknown') AS trigger_type,
        COALESCE(t.message_purpose, 'Unknown') AS message_purpose
    FROM read_csv_auto(
        'C:/Users/82105/Desktop/push_analysis/data/campaigns.csv'
    ) c
    LEFT JOIN read_csv_auto(
        'C:/Users/82105/Desktop/push_analysis/configs/topic_mapping.csv'
    ) t
        ON LOWER(TRIM(c.topic)) = LOWER(TRIM(t.topic))
)
TO 'C:/Users/82105/Desktop/push_analysis/data/processed/03_campaigns_categorized.parquet'
(FORMAT PARQUET, COMPRESSION ZSTD);