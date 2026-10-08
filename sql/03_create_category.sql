-- campaings
COPY (
    SELECT
        *,
        CASE
            WHEN topic IN (
                'sale out',
                'event'
            ) THEN 'Marketing'
            WHEN topic IN (
                'abandoned cart',
                'abandoned view',
                'abandoned search',
                'abandoned category'
            ) THEN 'Behavioral'
            WHEN topic IN (
                'price drop',
                'added to wish list',
                'removed from wish list',
                'back in stock',
                'wish list status'
            ) THEN 'Interest'
            WHEN topic IN (
                'order created',
                'order shipped',
                'order ready for pickup',
                'order pickup still pending',
                'order reminder',
                'order cancelled'
            ) THEN 'Transactional'
            WHEN topic IN (
                'welcome campaign',
                'welcome letter',
                'subscribed',
                'profile updated',
                'user added to segment',
                'happy birthday',
                'recent purchase',
                'offer after purchase',
                'leave review',
                'bonuses expired',
                'double opt in'
            ) THEN 'Lifecycle'
            ELSE 'Uncategorized'
        END AS category
    FROM read_csv_auto(
        'C:/Users/82105/Desktop/push_analysis/data/campaigns.csv'
    )
)
TO 'C:/Users/82105/Desktop/push_analysis/data/03_campaigns_categorized.csv'
(FORMAT CSV, HEADER);