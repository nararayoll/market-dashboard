import yfinance as yf
import pandas as pd
import os
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

IS_CLOUD = bool(os.environ.get('GITHUB_ACTIONS'))
DATA_FILE = 'market_data.csv'

TICKERS = {
    "KOSPI":       "^KS11",
    "KOSDAQ":      "^KQ11",
    "S&P500":      "^GSPC",
    "NASDAQ":      "^IXIC",
    "다우존스":    "^DJI",
    "VIX":         "^VIX",
    "원달러환율":  "KRW=X",
    "미국10년금리":"^TNX",
}

SIGNALS = {
    "VIX":       {"위험": 30, "안정": 15},
    "KOSPI":     {"급락": -2.0, "급등": 2.0},
    "S&P500":    {"급락": -2.0, "급등": 2.0},
    "원달러환율": {"급등": 20, "급락": -20},
}


def fetch_data():
    today = {}
    for name, ticker in TICKERS.items():
        try:
            hist = yf.Ticker(ticker).history(period="2d")
            if len(hist) >= 1:
                close = hist['Close'].iloc[-1]
                prev  = hist['Close'].iloc[-2] if len(hist) >= 2 else close
                today[name] = {
                    "현재값":       round(close, 2),
                    "전일대비(%)":  round((close - prev) / prev * 100, 2),
                    "전일대비(절대)": round(close - prev, 2),
                }
        except Exception:
            today[name] = {"현재값": None, "전일대비(%)": None, "전일대비(절대)": None}
    return today


def save_to_csv(data):
    today_str = datetime.now().strftime("%Y-%m-%d")
    row = {"날짜": today_str}
    for name, vals in data.items():
        row[name] = vals["현재값"]
        row[f"{name}_변화율"] = vals["전일대비(%)"]

    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        df = df[df["날짜"] != today_str]
    else:
        df = pd.DataFrame()

    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.to_csv(DATA_FILE, index=False, encoding='utf-8-sig')
    return df


def detect_signals(data):
    alerts = []
    vix = data.get("VIX", {}).get("현재값")
    if vix:
        if vix >= SIGNALS["VIX"]["위험"]:
            alerts.append(f"VIX 위험 — {vix}")
        elif vix <= SIGNALS["VIX"]["안정"]:
            alerts.append(f"VIX 안정 — {vix}")
    for idx in ["KOSPI", "S&P500"]:
        chg = data.get(idx, {}).get("전일대비(%)")
        if chg is not None:
            if chg <= SIGNALS[idx]["급락"]:
                alerts.append(f"{idx} 급락 — {chg:+.2f}%")
            elif chg >= SIGNALS[idx]["급등"]:
                alerts.append(f"{idx} 급등 — {chg:+.2f}%")
    return alerts


if __name__ == "__main__":
    print("[1/2] 시장 데이터 수집 중...")
    data = fetch_data()
    print("[2/2] CSV 저장 중...")
    save_to_csv(data)
    print("완료")
