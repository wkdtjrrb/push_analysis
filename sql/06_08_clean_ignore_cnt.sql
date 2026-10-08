COPY (
    SELECT
        id,
        client_id,
        campaign_id,
        message_type,
        sent_at,
        is_opened,
        is_clicked,
        category,
        channel,
        hour_limit,
        subject_length,
        subject_with_personalization,
        subject_with_deadline,
        subject_with_emoji,
        subject_with_bonuses,
        subject_with_discount,
        subject_with_saleout,
        CAST(mar_ignore_cnt AS INTEGER) AS mar_ignore_cnt,
        CAST(beh_ignore_cnt AS INTEGER) AS beh_ignore_cnt,
        CAST(interest_ignore_cnt AS INTEGER) AS interest_ignore_cnt,
        CAST(life_ignore_cnt AS INTEGER) AS life_ignore_cnt,
        CAST(trans_ignore_cnt AS INTEGER) AS trans_ignore_cnt,
        CAST(total_ignore_cnt AS INTEGER) AS total_ignore_cnt,
        CAST(other_ignore_cnt AS INTEGER) AS other_ignore_cnt
    FROM read_parquet(
        'C:/Users/82105/Desktop/push_analysis/data/processed/messages_train_val_other_ignore.parquet'
    )
)
TO 'C:/Users/82105/Desktop/push_analysis/data/processed/06_messages_train_val_features_clean.parquet'
(FORMAT PARQUET, COMPRESSION ZSTD);