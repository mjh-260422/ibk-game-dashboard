import pandas as pd
from models import UniqueEvent

def load_excel(filepath: str) -> pd.DataFrame:
    return pd.read_excel(filepath)

def deduplicate_events(df: pd.DataFrame) -> list:
    df = df.copy()
    df["처리일"] = df["처리일"].astype(str)
    df = df.sort_values("처리일", ascending=False)

    rebid_counts = df.groupby("견적번호").size().to_dict()
    unique_df = df.drop_duplicates(subset="견적번호", keep="first")

    events = []
    for _, row in unique_df.iterrows():
        events.append(UniqueEvent(
            quote_id=int(row["견적번호"]),
            quote_name=str(row["견적명"]).strip(),
            latest_date=str(row["처리일"]),
            rebid_count=int(rebid_counts.get(int(row["견적번호"]), 1)),
        ))
    return events
