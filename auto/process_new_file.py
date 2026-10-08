import duckdb
import sys
import os
from pathlib import Path


DB_PATH = "C:/Users/82105/Desktop/push_analysis/push_analysis.duckdb"
OUTPUT_DIR = "C:/Users/82105/Desktop/push_analysis/data/output"
CAMPAIGNS_PATH = "C:/Users/82105/Desktop/push_analysis/data/03_campaigns_categorized.csv"

file_path = sys.argv[1]
file_name = Path(file_path).name
file_ext = Path(file_path).suffix.lower()

if file_ext == ".csv":
    source_sql = "read_csv_auto(?, header=true)"
elif file_ext == ".parquet":
    source_sql = "read_parquet(?)"
else:
    raise ValueError("CSV 또는 Parquet 파일만 처리할 수 있습니다.")

con = duckdb.connect(DB_PATH)

con.execute("""
CREATE TABLE IF NOT EXISTS client_ignore_state (
    client_id BIGINT,
    mar_ignore_cnt INTEGER,
    beh_ignore_cnt INTEGER,
    interest_ignore_cnt INTEGER,
    life_ignore_cnt INTEGER,
    trans_ignore_cnt INTEGER,
    last_sent_at TIMESTAMP,
    last_id BIGINT
)
""")

con.execute("""
CREATE TABLE IF NOT EXISTS processed_file_log (
    file_name VARCHAR PRIMARY KEY,
    processed_at TIMESTAMP,
    min_sent_at TIMESTAMP,
    max_sent_at TIMESTAMP,
    row_count BIGINT,
    status VARCHAR
)
""")

already_processed = con.execute("""
SELECT COUNT(*)
FROM processed_file_log
WHERE file_name = ?
""", [file_name]).fetchone()[0]

if already_processed > 0:
    con.close()
    raise ValueError(f"이미 처리된 파일입니다: {file_name}")

con.execute(f"""
CREATE OR REPLACE TEMP TABLE new_raw AS
SELECT *
FROM {source_sql}
""", [file_path])

raw_count = con.execute("""
SELECT COUNT(*)
FROM new_raw
""").fetchone()[0]

if raw_count == 0:
    con.close()
    raise ValueError("새 파일에 데이터가 없습니다.")

required_columns = {
    row[0]
    for row in con.execute("DESCRIBE new_raw").fetchall()
}

required = {
    "id",
    "client_id",
    "sent_at",
    "is_opened",
    "campaign_id",
    "message_type"
}

missing = required - required_columns

if missing:
    con.close()
    raise ValueError(f"필수 컬럼이 없습니다: {', '.join(sorted(missing))}")

con.execute(f"""
CREATE OR REPLACE TEMP TABLE new_data AS
SELECT
    n.*,
    c.category
FROM new_raw n
LEFT JOIN read_csv_auto(?, header=true) c
    ON n.campaign_id = c.id
    AND n.message_type = c.campaign_type
WHERE n.client_id IS NOT NULL
  AND n.client_id <> 0
  AND n.sent_at IS NOT NULL
  AND c.category IN (
      'Marketing',
      'Behavioral',
      'Interest',
      'Lifecycle',
      'Transactional'
  )
ORDER BY n.client_id, n.sent_at, n.id
""", [CAMPAIGNS_PATH])

valid_count = con.execute("""
SELECT COUNT(*)
FROM new_data
""").fetchone()[0]

if valid_count == 0:
    con.close()
    raise ValueError("처리 가능한 데이터가 없습니다.")

invalid_count = raw_count - valid_count

late_count = con.execute("""
SELECT COUNT(*)
FROM (
    SELECT
        n.client_id,
        MIN(n.sent_at) AS min_sent_at,
        MAX(s.last_sent_at) AS previous_last_sent_at
    FROM new_data n
    LEFT JOIN client_ignore_state s
        ON n.client_id = s.client_id
    GROUP BY n.client_id
)
WHERE previous_last_sent_at IS NOT NULL
  AND min_sent_at <= previous_last_sent_at
""").fetchone()[0]

if late_count > 0:
    con.close()
    raise ValueError(
        f"기존 처리 데이터보다 과거 또는 같은 시각의 데이터가 "
        f"{late_count}명의 사용자에게 존재합니다."
    )

state_rows = con.execute("""
SELECT
    client_id,
    mar_ignore_cnt,
    beh_ignore_cnt,
    interest_ignore_cnt,
    life_ignore_cnt,
    trans_ignore_cnt,
    last_sent_at,
    last_id
FROM client_ignore_state
""").fetchall()

states = {
    row[0]: {
        "Marketing": row[1],
        "Behavioral": row[2],
        "Interest": row[3],
        "Lifecycle": row[4],
        "Transactional": row[5],
        "last_sent_at": row[6],
        "last_id": row[7]
    }
    for row in state_rows
}

columns = [
    row[0]
    for row in con.execute("DESCRIBE new_data").fetchall()
]

rows = con.execute("""
SELECT *
FROM new_data
ORDER BY client_id, sent_at, id
""").fetchall()

result_rows = []
latest_states = {}

for row in rows:
    row_dict = dict(zip(columns, row))

    client_id = row_dict["client_id"]
    category = row_dict["category"]
    is_opened = bool(row_dict["is_opened"])
    sent_at = row_dict["sent_at"]
    row_id = row_dict["id"]

    if client_id not in states:
        states[client_id] = {
            "Marketing": 0,
            "Behavioral": 0,
            "Interest": 0,
            "Lifecycle": 0,
            "Transactional": 0,
            "last_sent_at": None,
            "last_id": None
        }

    state = states[client_id]

    mar_cnt = state["Marketing"]
    beh_cnt = state["Behavioral"]
    interest_cnt = state["Interest"]
    life_cnt = state["Lifecycle"]
    trans_cnt = state["Transactional"]

    total_cnt = (
        mar_cnt
        + beh_cnt
        + interest_cnt
        + life_cnt
        + trans_cnt
    )

    if category == "Marketing":
        other_cnt = (
            beh_cnt
            + interest_cnt
            + life_cnt
            + trans_cnt
        )
    elif category == "Behavioral":
        other_cnt = (
            mar_cnt
            + interest_cnt
            + life_cnt
            + trans_cnt
        )
    elif category == "Interest":
        other_cnt = (
            mar_cnt
            + beh_cnt
            + life_cnt
            + trans_cnt
        )
    elif category == "Lifecycle":
        other_cnt = (
            mar_cnt
            + beh_cnt
            + interest_cnt
            + trans_cnt
        )
    else:
        other_cnt = (
            mar_cnt
            + beh_cnt
            + interest_cnt
            + life_cnt
        )

    result_rows.append(
        row
        + (
            mar_cnt,
            beh_cnt,
            interest_cnt,
            life_cnt,
            trans_cnt,
            total_cnt,
            other_cnt
        )
    )

    if is_opened:
        state[category] = 0
    else:
        state[category] += 1

    state["last_sent_at"] = sent_at
    state["last_id"] = row_id

    latest_states[client_id] = (
        state["Marketing"],
        state["Behavioral"],
        state["Interest"],
        state["Lifecycle"],
        state["Transactional"],
        state["last_sent_at"],
        state["last_id"]
    )

output_columns = columns + [
    "mar_ignore_cnt",
    "beh_ignore_cnt",
    "interest_ignore_cnt",
    "life_ignore_cnt",
    "trans_ignore_cnt",
    "total_ignore_cnt",
    "other_ignore_cnt"
]

con.execute("DROP TABLE IF EXISTS final_result")

column_types = con.execute("""
SELECT column_name, column_type
FROM (
    DESCRIBE new_data
)
""").fetchall()

column_type_map = {
    row[0]: row[1]
    for row in column_types
}

result_schema = ", ".join(
    f'"{column}" {column_type_map[column]}'
    for column in columns
)

result_schema += """
,
mar_ignore_cnt INTEGER,
beh_ignore_cnt INTEGER,
interest_ignore_cnt INTEGER,
life_ignore_cnt INTEGER,
trans_ignore_cnt INTEGER,
total_ignore_cnt INTEGER,
other_ignore_cnt INTEGER
"""

con.execute(f"""
CREATE TEMP TABLE final_result (
    {result_schema}
)
""")

placeholders = ", ".join(["?"] * len(output_columns))

con.executemany(
    f"""
    INSERT INTO final_result
    VALUES ({placeholders})
    """,
    result_rows
)

output_path = os.path.join(
    OUTPUT_DIR,
    f"{Path(file_path).stem}_processed.parquet"
)

os.makedirs(OUTPUT_DIR, exist_ok=True)

con.execute("""
COPY final_result
TO ?
(FORMAT PARQUET, COMPRESSION ZSTD)
""", [output_path])

con.execute("BEGIN TRANSACTION")

for client_id, state in latest_states.items():
    mar_cnt, beh_cnt, interest_cnt, life_cnt, trans_cnt, last_sent_at, last_id = state

    updated = con.execute("""
    UPDATE client_ignore_state
    SET
        mar_ignore_cnt = ?,
        beh_ignore_cnt = ?,
        interest_ignore_cnt = ?,
        life_ignore_cnt = ?,
        trans_ignore_cnt = ?,
        last_sent_at = ?,
        last_id = ?
    WHERE client_id = ?
    """, [
        mar_cnt,
        beh_cnt,
        interest_cnt,
        life_cnt,
        trans_cnt,
        last_sent_at,
        last_id,
        client_id
    ]).rowcount

    if updated == 0:
        con.execute("""
        INSERT INTO client_ignore_state
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            client_id,
            mar_cnt,
            beh_cnt,
            interest_cnt,
            life_cnt,
            trans_cnt,
            last_sent_at,
            last_id
        ])

min_sent_at, max_sent_at = con.execute("""
SELECT
    MIN(sent_at),
    MAX(sent_at)
FROM final_result
""").fetchone()

con.execute("""
INSERT INTO processed_file_log
VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, 'SUCCESS')
""", [
    file_name,
    min_sent_at,
    max_sent_at,
    valid_count
])

con.execute("COMMIT")

con.close()

print(f"처리 완료: {file_name}")
print(f"전체 입력 행: {raw_count:,}")
print(f"처리 행: {valid_count:,}")
print(f"제외 행: {invalid_count:,}")
print(f"결과 파일: {output_path}")