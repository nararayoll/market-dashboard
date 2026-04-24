import yfinance as yf
import pandas as pd
import json
import os
from datetime import datetime

PORTFOLIO_FILE = 'portfolio.json'
PORTFOLIO_DATA = 'portfolio_data.csv'


def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def fetch_portfolio():
    with open(PORTFOLIO_FILE, encoding='utf-8') as f:
        portfolio = json.load(f)

    results = []
    for stock in portfolio["holdings"]:
        ticker = stock["ticker"]
        try:
            hist = yf.Ticker(ticker).history(period="3mo")
            if len(hist) < 2:
                continue
            close = hist["Close"]
            current_price = round(float(close.iloc[-1]), 4)
            avg = stock["avg_price"]
            pnl_pct = round((current_price - avg) / avg * 100, 2)
            pnl_abs = round((current_price - avg) * stock["qty"], 2)
            rsi = round(calc_rsi(close).iloc[-1], 1)
            ma20 = round(float(close.rolling(20).mean().iloc[-1]), 4)
            ma60 = round(float(close.rolling(60).mean().iloc[-1]), 4) if len(close) >= 60 else None
            ma20_prev = round(float(close.rolling(20).mean().iloc[-2]), 4)
            ma60_prev = round(float(close.rolling(60).mean().iloc[-2]), 4) if len(close) >= 60 else None
            cross = None
            if ma60 and ma60_prev:
                if ma20_prev <= ma60_prev and ma20 > ma60:
                    cross = "golden"
                elif ma20_prev >= ma60_prev and ma20 < ma60:
                    cross = "dead"
            rsi_signal = "overbought" if rsi >= 70 else ("oversold" if rsi <= 30 else None)
            prev_price = round(float(close.iloc[-2]), 4)
            day_chg = round((current_price - prev_price) / prev_price * 100, 2)
            results.append({
                "name": stock["name"], "ticker": ticker,
                "currency": stock["currency"], "qty": stock["qty"],
                "avg_price": avg, "current_price": current_price,
                "day_chg": day_chg, "pnl_pct": pnl_pct, "pnl_abs": pnl_abs,
                "rsi": rsi, "ma20": ma20, "ma60": ma60,
                "rsi_signal": rsi_signal, "cross": cross,
            })
        except Exception as e:
            print(f"  오류 ({ticker}): {e}")
    return results


def fetch_portfolio_history():
    with open(PORTFOLIO_FILE, encoding='utf-8') as f:
        portfolio = json.load(f)

    history = {}
    for stock in portfolio["holdings"]:
        ticker = stock["ticker"]
        try:
            hist = yf.Ticker(ticker).history(period="6mo")
            if len(hist) < 5:
                continue
            close = hist["Close"]
            ma20_full = close.rolling(20).mean()
            ma60_full = close.rolling(60).mean()
            close60 = close.tail(60)
            history[ticker] = {
                "name":      stock["name"],
                "dates":     [d.strftime("%m/%d") for d in close60.index],
                "prices":    [round(float(v), 4) if pd.notna(v) else None for v in close60],
                "ma20":      [round(float(v), 4) if pd.notna(v) else None for v in ma20_full.tail(60)],
                "ma60":      [round(float(v), 4) if pd.notna(v) else None for v in ma60_full.tail(60)],
                "avg_price": stock["avg_price"],
                "currency":  stock["currency"],
            }
        except Exception:
            pass
    return history


def _translate_ko(text):
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source='auto', target='ko').translate(text)
    except Exception:
        return text


def _sentiment(title):
    neg = ['loss','drop','fall','plunge','crash','decline','layoff','recall',
           'lawsuit','downgrade','miss','risk','warn','concern','weak','cut']
    pos = ['beat','surge','soar','jump','rise','rally','upgrade','profit',
           'revenue','dividend','buyback','strong','growth','record','gain']
    t = title.lower()
    if any(w in t for w in neg): return 'neg'
    if any(w in t for w in pos): return 'pos'
    return ''


def fetch_news(max_per_stock=3):
    with open(PORTFOLIO_FILE, encoding='utf-8') as f:
        portfolio = json.load(f)

    all_news = []
    seen = set()
    for stock in portfolio["holdings"]:
        ticker = stock["ticker"]
        name   = stock["name"]
        try:
            articles = yf.Ticker(ticker).news or []
            count = 0
            for a in articles:
                title = a.get("title") or a.get("content", {}).get("title", "")
                link  = a.get("link")  or a.get("content", {}).get("canonicalUrl", {}).get("url", "")
                pub   = a.get("publisher") or a.get("content", {}).get("provider", {}).get("displayName", "")
                ts    = a.get("providerPublishTime") or a.get("content", {}).get("pubDate", "")
                if not title or not link or link in seen:
                    continue
                seen.add(link)
                if isinstance(ts, (int, float)):
                    date_str = datetime.fromtimestamp(ts).strftime("%m/%d %H:%M")
                elif isinstance(ts, str) and ts:
                    try:
                        date_str = datetime.fromisoformat(ts[:19]).strftime("%m/%d %H:%M")
                    except Exception:
                        date_str = ts[:10]
                else:
                    date_str = ""
                all_news.append({
                    "stock": name, "ticker": ticker,
                    "title_ko": _translate_ko(title), "link": link,
                    "publisher": pub, "date": date_str,
                    "sentiment": _sentiment(title),
                })
                count += 1
                if count >= max_per_stock:
                    break
        except Exception:
            pass
    return all_news


def get_signals(results):
    signals = []
    for r in results:
        name = r["name"]
        if r["cross"] == "golden":
            signals.append({"type": "buy",  "msg": f"{name} 골든크로스 — MA20이 MA60 상향 돌파"})
        elif r["cross"] == "dead":
            signals.append({"type": "sell", "msg": f"{name} 데드크로스 — MA20이 MA60 하향 돌파"})
        if r["rsi_signal"] == "oversold":
            signals.append({"type": "buy",  "msg": f"{name} RSI 과매도 — RSI {r['rsi']}"})
        elif r["rsi_signal"] == "overbought":
            signals.append({"type": "sell", "msg": f"{name} RSI 과매수 — RSI {r['rsi']}"})
    return signals
