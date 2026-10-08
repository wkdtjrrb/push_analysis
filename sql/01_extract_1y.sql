-- 2022-04~2023-04까지의 데이터만 추출

COPY (
    SELECT *
    FROM read_parquet(
        'C:/Users/82105/Desktop/push_analysis/data/processed/00_messages_all.parquet'
    )
    WHERE sent_at >= TIMESTAMP '2022-04-01'
      AND sent_at < TIMESTAMP '2023-04-01'
)
TO 'C:/Users/82105/Desktop/push_analysis/data/processed/01_messages_1y.parquet'
(FORMAT PARQUET, COMPRESSION ZSTD);