-- 1년 내에서 첫 구매가 일어난 고객만 추출

COPY (
    WITH target_clients AS (
        SELECT
            client_id
        FROM read_csv_auto(
            'C:/Users/82105/Desktop/push_analysis/data/client_first_purchase_date.csv'
        )
        WHERE first_purchase_date >= DATE '2022-04-01'
          AND first_purchase_date < DATE '2023-04-01'
    )

    SELECT
        m.*
    FROM read_parquet(
        'C:/Users/82105/Desktop/push_analysis/data/processed/01_messages_1y.parquet'
    ) m
    INNER JOIN target_clients t
        ON m.client_id = t.client_id
)
TO 'C:/Users/82105/Desktop/push_analysis/data/processed/02_messages_1y_first_purchase.parquet'
(FORMAT PARQUET, COMPRESSION ZSTD);