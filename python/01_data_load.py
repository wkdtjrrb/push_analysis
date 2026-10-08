import duckdb
import os
import time

INPUT = r"C:\Users\82105\Downloads\messages.csv.gz"

DB = r"C:\Users\82105\Desktop\push_analysis\push_analysis.duckdb"

OUTPUT = r"C:\Users\82105\Desktop\push_analysis\data\processed\messages_all.parquet"

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)

start = time.time()

con = duckdb.connect(DB)

con.execute("SET threads TO 4")
con.execute("SET memory_limit = '4GB'")
con.execute("SET enable_progress_bar = true")
con.execute("SET progress_bar_time = 1")

print("=" * 60)
print("전체 Push 데이터 추출 시작")
print("=" * 60)
print(f"Input : {INPUT}")
print(f"Output: {OUTPUT}")
print()

con.execute(f"""
COPY (
    SELECT *
    FROM read_csv(
        '{INPUT}',
        header = true,
        auto_detect = true,
        compression = 'gzip'
    )
)
TO '{OUTPUT}'
(
    FORMAT PARQUET,
    COMPRESSION ZSTD
);
""")

elapsed = time.time() - start

print()
print("=" * 60)
print("추출 완료")
print("=" * 60)
print(f"소요 시간: {elapsed / 60:.1f}분")

if os.path.exists(OUTPUT):
    size_gb = os.path.getsize(OUTPUT) / (1024 ** 3)
    print(f"Parquet 크기: {size_gb:.2f} GB")

count = con.execute(f"""
    SELECT COUNT(*)
    FROM read_parquet('{OUTPUT}')
""").fetchone()[0]

users = con.execute(f"""
    SELECT COUNT(DISTINCT client_id)
    FROM read_parquet('{OUTPUT}')
""").fetchone()[0]

print(f"행 수: {count:,}")
print(f"사용자 수: {users:,}")

con.close()