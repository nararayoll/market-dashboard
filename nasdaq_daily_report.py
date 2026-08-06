import yfinance as yf
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

def fetch_data():
    nasdaq = yf.Ticker("^IXIC")
    hist = nasdaq.history(period="30d")
    hist_1y = nasdaq.history(period="1y")

    latest = hist.iloc[-1]
    prev = hist.iloc[-2]
    close = round(float(latest["Close"]), 2)
    prev_close = round(float(prev["Close"]), 2)
    change = round(close - prev_close, 2)
    change_pct = round(change / prev_close * 100, 2)

    week52_high = round(float(hist_1y["High"].max()), 2)
    week52_low = round(float(hist_1y["Low"].min()), 2)
    week52_pos = round((close - week52_low) / (week52_high - week52_low) * 100, 1)

    recent = []
    for i in range(max(0, len(hist) - 10), len(hist)):
        d = hist.index[i].strftime("%m.%d")
        c = round(float(hist["Close"].iloc[i]), 2)
        pc = round(float(hist["Close"].iloc[i - 1]), 2) if i > 0 else c
        ch = round(c - pc, 2) if i > 0 else 0
        pct = round(ch / pc * 100, 2) if pc else 0
        recent.append({"date": d, "close": c, "change": ch, "pct": pct})

    reasons = []
    try:
        news_items = nasdaq.news or []
        for item in news_items[:5]:
            content = item.get("content", {})
            title = content.get("title", "") if isinstance(content, dict) else item.get("title", "")
            if title and len(title) > 5:
                reasons.append(title[:70])
            if len(reasons) >= 3:
                break
    except Exception:
        pass

    if len(reasons) < 3:
        direction = "상승" if change >= 0 else "하락"
        fallback = [
            f"나스닥 {direction} — 주요 기술주 주가 변동",
            "Fed 금리 정책 및 경제 지표 반영",
            "기업 실적 발표 및 투자자 심리 영향",
        ]
        for f in fallback:
            if len(reasons) < 3:
                reasons.append(f)

    return {
        "date": hist.index[-1].strftime("%Y.%m.%d"),
        "close": close,
        "open": round(float(latest["Open"]), 2),
        "high": round(float(latest["High"]), 2),
        "low": round(float(latest["Low"]), 2),
        "prev_close": prev_close,
        "change": change,
        "change_pct": change_pct,
        "week52_high": week52_high,
        "week52_low": week52_low,
        "week52_pos": week52_pos,
        "recent": recent,
        "reasons": reasons,
        "updated_at": datetime.now(KST).strftime("%Y.%m.%d %H:%M KST"),
    }


def color(pct):
    return "#e44b4b" if pct >= 0 else "#4b7be4"


def badge(pct):
    sign = "+" if pct >= 0 else ""
    bg = "#e44b4b" if pct >= 0 else "#4b7be4"
    return f'<span style="background:{bg};color:#fff;padding:3px 10px;border-radius:5px;font-size:13px;font-weight:700">{sign}{pct}%</span>'


def generate_html(d):
    up = d["change"] >= 0
    main_color = "#e44b4b" if up else "#4b7be4"
    arrow = "▲" if up else "▼"
    sign = "+" if up else ""

    rows = ""
    for r in reversed(d["recent"]):
        c = color(r["pct"])
        sign_r = "+" if r["pct"] >= 0 else ""
        ch_sign = "+" if r["change"] >= 0 else ""
        rows += f"""
        <tr>
          <td>{r["date"]}</td>
          <td><strong>{r["close"]:,.2f}</strong></td>
          <td style="color:{c}">{ch_sign}{r["change"]:,.2f}</td>
          <td>{badge(r["pct"])}</td>
        </tr>"""

    reason_cards = ""
    for i, reason in enumerate(d["reasons"], 1):
        reason_cards += f"""
        <div class="reason-card">
          <span class="reason-num">{i}</span>
          <span class="reason-text">{reason}</span>
        </div>"""

    pos = d["week52_pos"]

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>나스닥 일일 리포트</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f6f8; color: #111; max-width: 480px; margin: 0 auto; }}
  .header {{ background: #1a6fe8; color: #fff; padding: 20px 16px 18px; }}
  .header-title {{ font-size: 17px; font-weight: 600; margin-bottom: 8px; }}
  .header-price {{ font-size: 38px; font-weight: 700; letter-spacing: -1px; }}
  .header-change {{ font-size: 15px; margin-top: 4px; color: {main_color}; background: #fff; display: inline-block; padding: 3px 10px; border-radius: 6px; font-weight: 700; }}
  .section {{ background: #fff; margin: 10px 12px; border-radius: 12px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,.06); }}
  .section-title {{ font-size: 13px; color: #888; padding: 12px 14px 4px; font-weight: 600; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  td {{ padding: 11px 14px; border-bottom: 1px solid #f0f0f0; }}
  tr:last-child td {{ border-bottom: none; }}
  td:first-child {{ color: #666; }}
  td:nth-child(2) {{ text-align: right; }}
  td:nth-child(3) {{ text-align: right; }}
  td:nth-child(4) {{ text-align: right; }}
  .cards {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0; }}
  .card {{ padding: 13px 14px; border-bottom: 1px solid #f0f0f0; }}
  .card:nth-child(odd) {{ border-right: 1px solid #f0f0f0; }}
  .card-label {{ font-size: 11px; color: #999; margin-bottom: 4px; }}
  .card-value {{ font-size: 15px; font-weight: 700; }}
  .week52-wrap {{ padding: 14px 14px 16px; }}
  .week52-bar-bg {{ background: #e8e8e8; border-radius: 4px; height: 8px; margin: 8px 0; position: relative; }}
  .week52-bar-fill {{ background: #1a6fe8; height: 8px; border-radius: 4px; width: {pos}%; }}
  .week52-labels {{ display: flex; justify-content: space-between; font-size: 11px; color: #888; }}
  .week52-current {{ position: absolute; top: -20px; left: {pos}%; transform: translateX(-50%); font-size: 11px; color: #1a6fe8; font-weight: 700; white-space: nowrap; }}
  .reason-card {{ display: flex; align-items: flex-start; gap: 10px; padding: 11px 14px; border-bottom: 1px solid #f0f0f0; }}
  .reason-card:last-child {{ border-bottom: none; }}
  .reason-num {{ background: #1a6fe8; color: #fff; border-radius: 50%; width: 20px; height: 20px; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; flex-shrink: 0; margin-top: 1px; }}
  .reason-text {{ font-size: 13px; line-height: 1.5; color: #333; }}
  .updated {{ text-align: center; font-size: 11px; color: #bbb; padding: 14px; }}
</style>
</head>
<body>

<div class="header">
  <div class="header-title">나스닥 종합</div>
  <div class="header-price">{d["close"]:,.2f}</div>
  <div class="header-change">{arrow} {abs(d["change"]):,.2f} ({sign}{d["change_pct"]}%)</div>
</div>

<div class="section">
  <div class="section-title">최근 10일</div>
  <table>
    <thead>
      <tr style="background:#f9f9f9;">
        <td style="color:#999;font-size:12px;font-weight:600">날짜</td>
        <td style="color:#999;font-size:12px;font-weight:600;text-align:right">종가</td>
        <td style="color:#999;font-size:12px;font-weight:600;text-align:right">전일대비</td>
        <td style="color:#999;font-size:12px;font-weight:600;text-align:right">등락률</td>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</div>

<div class="section">
  <div class="section-title">주요 지표</div>
  <div class="cards">
    <div class="card"><div class="card-label">전일종가</div><div class="card-value">{d["prev_close"]:,.2f}</div></div>
    <div class="card"><div class="card-label">시가</div><div class="card-value">{d["open"]:,.2f}</div></div>
    <div class="card"><div class="card-label">고가</div><div class="card-value" style="color:#e44b4b">{d["high"]:,.2f}</div></div>
    <div class="card"><div class="card-label">저가</div><div class="card-value" style="color:#4b7be4">{d["low"]:,.2f}</div></div>
  </div>
  <div class="week52-wrap">
    <div class="card-label">52주 범위</div>
    <div class="week52-bar-bg">
      <div class="week52-bar-fill"></div>
      <div class="week52-current">{d["close"]:,.0f}</div>
    </div>
    <div class="week52-labels">
      <span>최저 {d["week52_low"]:,.2f}</span>
      <span>최고 {d["week52_high"]:,.2f}</span>
    </div>
  </div>
</div>

<div class="section">
  <div class="section-title">변화 이유</div>
  {reason_cards}
</div>

<div class="updated">업데이트: {d["updated_at"]}</div>

</body>
</html>"""


if __name__ == "__main__":
    data = fetch_data()
    html = generate_html(data)
    with open("nasdaq_daily.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Generated: {data['date']} | {data['close']:,.2f} ({data['change_pct']:+.2f}%)")
