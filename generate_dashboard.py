import hashlib
import json
import os
from datetime import datetime

import pandas as pd
import yfinance as yf

from portfolio_analysis import fetch_portfolio, fetch_portfolio_history, fetch_news, get_signals

MARKET_TICKERS = {
    "KOSPI":       "^KS11",
    "KOSDAQ":      "^KQ11",
    "S&P500":      "^GSPC",
    "NASDAQ":      "^IXIC",
    "다우존스":    "^DJI",
    "VIX":         "^VIX",
    "원달러환율":  "KRW=X",
    "미국10년금리":"^TNX",
}

TICKER_GROUPS = {
    "한국 시장": ["KOSPI", "KOSDAQ"],
    "미국 시장": ["S&P500", "NASDAQ", "다우존스"],
    "공포지수": ["VIX"],
    "환율 / 금리": ["원달러환율", "미국10년금리"],
}

COLORS = {
    "KOSPI":      "#4fc3f7",
    "KOSDAQ":     "#81d4fa",
    "S&P500":     "#a5d6a7",
    "NASDAQ":     "#c5e1a5",
    "다우존스":    "#fff59d",
    "VIX":        "#ef9a9a",
    "원달러환율":  "#ffcc80",
    "미국10년금리":"#ce93d8",
}


def fetch_market_history():
    result = {}
    for name, ticker in MARKET_TICKERS.items():
        try:
            hist = yf.Ticker(ticker).history(period="3mo")["Close"].tail(60)
            result[name] = {
                "dates":  [d.strftime("%m/%d") for d in hist.index],
                "values": [round(float(v), 4) if pd.notna(v) else None for v in hist],
            }
        except Exception:
            pass
    return result


def build_dashboard(public: bool, password_hash: str = ""):
    data_file = "market_data.csv"
    out_file  = "index.html" if public else "private.html"

    if not os.path.exists(data_file):
        print(f"{data_file} 없음. market_summary.py 를 먼저 실행하세요.")
        return

    df = pd.read_csv(data_file, encoding="utf-8-sig")
    df["날짜"] = pd.to_datetime(df["날짜"])
    df = df.sort_values("날짜")
    latest    = df.iloc[-1]
    today_str = latest["날짜"].strftime("%Y년 %m월 %d일")

    print("포트폴리오 데이터 수집 중...")
    portfolio_results = fetch_portfolio()
    portfolio_signals = get_signals(portfolio_results)

    print("뉴스 수집 중...")
    news_list = fetch_news(max_per_stock=3)

    print("포트폴리오 히스토리 수집 중...")
    port_history = fetch_portfolio_history()

    # 공유용이면 개인 정보 제거
    if public:
        PRIVATE_FIELDS = ("avg_price", "qty", "pnl_pct", "pnl_abs")
        portfolio_results = [{k: v for k, v in r.items() if k not in PRIVATE_FIELDS}
                             for r in portfolio_results]
        port_history = {t: {k: v for k, v in d.items() if k != "avg_price"}
                        for t, d in port_history.items()}

    # 카드
    all_tickers = [t for g in TICKER_GROUPS.values() for t in g]
    cards = []
    for name in all_tickers:
        if name not in df.columns:
            continue
        val = latest.get(name)
        chg = latest.get(f"{name}_변화율")
        if pd.isna(val):
            continue
        cards.append({
            "name":   name,
            "value":  round(float(val), 2),
            "change": round(float(chg), 2) if chg and not pd.isna(chg) else 0,
        })

    # 시그널
    alerts = []
    vix_val = latest.get("VIX")
    if vix_val and not pd.isna(vix_val):
        if float(vix_val) >= 30:
            alerts.append({"type": "danger", "msg": f"VIX 위험 신호: {vix_val:.1f} (기준 30 이상)"})
        elif float(vix_val) <= 15:
            alerts.append({"type": "safe",   "msg": f"VIX 안정 구간: {vix_val:.1f} (기준 15 이하)"})
    for idx in ["KOSPI", "S&P500"]:
        chg = latest.get(f"{idx}_변화율")
        if chg and not pd.isna(chg):
            chg = float(chg)
            if chg <= -2.0:
                alerts.append({"type": "danger", "msg": f"{idx} 급락: {chg:+.2f}%"})
            elif chg >= 2.0:
                alerts.append({"type": "up",     "msg": f"{idx} 급등: {chg:+.2f}%"})

    # 시장 히스토리
    print("시장 지수 히스토리 수집 중...")
    market_hist   = fetch_market_history()
    chart_datasets = {n: {"dates": d["dates"], "values": d["values"]} for n, d in market_hist.items()}
    labels         = max((d["dates"] for d in market_hist.values()), key=len, default=[])

    # JSON
    cards_json        = json.dumps(cards,             ensure_ascii=False)
    alerts_json       = json.dumps(alerts,            ensure_ascii=False)
    labels_json       = json.dumps(labels,            ensure_ascii=False)
    datasets_json     = json.dumps(chart_datasets,    ensure_ascii=False)
    groups_json       = json.dumps(TICKER_GROUPS,     ensure_ascii=False)
    colors_json       = json.dumps(COLORS,            ensure_ascii=False)
    portfolio_json    = json.dumps(portfolio_results, ensure_ascii=False)
    port_signals_json = json.dumps(portfolio_signals, ensure_ascii=False)
    news_json         = json.dumps(news_list,         ensure_ascii=False)
    port_history_json = json.dumps(port_history,      ensure_ascii=False)

    # 비밀번호 오버레이 (개인용만)
    if not public:
        password_overlay = f"""
<div id="pw-overlay" style="position:fixed;inset:0;background:#0f1117;display:flex;align-items:center;justify-content:center;z-index:9999;">
  <div style="background:#1e2130;border-radius:16px;padding:40px;text-align:center;min-width:280px;box-shadow:0 8px 32px #000a;">
    <div style="font-size:2rem;margin-bottom:8px;">📊</div>
    <div style="color:#ccc;font-size:1rem;font-weight:600;margin-bottom:4px;">시장 대시보드</div>
    <div style="color:#555;font-size:0.8rem;margin-bottom:24px;">비공개 버전</div>
    <input id="pw-input" type="password" placeholder="비밀번호"
      style="width:100%;padding:10px 14px;border-radius:8px;border:1px solid #333;background:#0f1117;color:#fff;font-size:1rem;outline:none;margin-bottom:12px;box-sizing:border-box;">
    <button onclick="checkPw()"
      style="width:100%;padding:10px;border-radius:8px;border:none;background:#4fc3f7;color:#000;font-size:0.9rem;font-weight:700;cursor:pointer;">
      입장
    </button>
    <div id="pw-error" style="color:#f44336;font-size:0.8rem;margin-top:10px;display:none;">비밀번호가 틀렸습니다</div>
  </div>
</div>
<script>
async function checkPw() {{
  const pw  = document.getElementById('pw-input').value;
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(pw));
  const hex = Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2,'0')).join('');
  if (hex === '{password_hash}') {{
    document.getElementById('pw-overlay').style.display = 'none';
    sessionStorage.setItem('dash_auth','1');
  }} else {{
    document.getElementById('pw-error').style.display = 'block';
  }}
}}
document.getElementById('pw-input').addEventListener('keydown', e => e.key === 'Enter' && checkPw());
if (sessionStorage.getItem('dash_auth') === '1') document.getElementById('pw-overlay').style.display = 'none';
</script>"""
    else:
        password_overlay = ""

    # 포트폴리오 테이블 헤더/행 (개인용은 매입가·수익률 포함)
    if public:
        table_header = """
      <th>종목</th><th>현재가</th><th>전일대비</th>
      <th>RSI <span style="font-weight:400;color:#555">(Relative Strength Index)</span></th>
      <th>MA20 vs MA60</th><th>시그널</th>"""
        table_row = """
      <td>${{r.name}} <span style="color:#555;font-size:.72rem">${{r.ticker}}</span></td>
      <td>${{cur}}${{r.current_price.toLocaleString()}}</td>
      <td class="${{dayCls}}">${{dayArrow}} ${{Math.abs(r.day_chg).toFixed(2)}}%</td>
      <td>${{r.rsi}} ${{rsiBadge}}</td>
      <td>${{maStatus}} ${{maBadge}}</td>
      <td>${{sigCell}}</td>"""
        pnl_vars = ""
        mobile_hide = ".port-table th:nth-child(4), .port-table td:nth-child(4) { display: none; }"
    else:
        table_header = """
      <th>종목</th><th>현재가</th><th>전일대비</th><th>매입가</th><th>수익률</th>
      <th>RSI <span style="font-weight:400;color:#555">(Relative Strength Index)</span></th>
      <th>MA20 vs MA60</th><th>시그널</th>"""
        table_row = """
      <td>${{r.name}} <span style="color:#555;font-size:.72rem">${{r.ticker}}</span></td>
      <td>${{cur}}${{r.current_price.toLocaleString()}}</td>
      <td class="${{dayCls}}">${{dayArrow}} ${{Math.abs(r.day_chg).toFixed(2)}}%</td>
      <td style="color:#666">${{cur}}${{r.avg_price.toLocaleString()}}</td>
      <td class="${{pnlCls}}">${{pnlArrow}} ${{Math.abs(r.pnl_pct).toFixed(2)}}%</td>
      <td>${{r.rsi}} ${{rsiBadge}}</td>
      <td>${{maStatus}} ${{maBadge}}</td>
      <td>${{sigCell}}</td>"""
        pnl_vars = """
  const pnlCls   = r.pnl_pct >= 0 ? 'up' : 'down';
  const pnlArrow = r.pnl_pct >= 0 ? '▲' : '▼';"""
        mobile_hide = """.port-table th:nth-child(4), .port-table td:nth-child(4),
    .port-table th:nth-child(7), .port-table td:nth-child(7) {{ display: none; }}"""

    # 종목 차트 매입가 라인 (개인용만)
    if public:
        avg_line_dataset = ""
    else:
        avg_line_dataset = """
        {{ label: '매입가', data: d.dates.map(() => d.avg_price), borderColor: '#ffffff44', borderWidth: 1,
           pointRadius: 0, fill: false, tension: 0, spanGaps: true, borderDash: [6,3], order: 4 }},"""

    # 종목 차트 subtitle
    if public:
        chart_sub = "종가 · MA20 · MA60"
    else:
        chart_sub = "종가 · MA20 · MA60 · 매입가 ${{cur}}${{d.avg_price.toLocaleString()}}"

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>시장 대시보드 — {today_str}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f1117; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; padding: 24px; }}
  h1   {{ font-size: 1.5rem; margin-bottom: 4px; color: #fff; }}
  .subtitle {{ color: #888; font-size: 0.85rem; margin-bottom: 24px; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; margin-bottom: 24px; }}
  .card  {{ background: #1e2130; border-radius: 10px; padding: 16px 14px; }}
  .card .label  {{ font-size: 0.75rem; color: #888; margin-bottom: 6px; }}
  .card .value  {{ font-size: 1.25rem; font-weight: 700; color: #fff; }}
  .card .change {{ font-size: 0.8rem; margin-top: 4px; }}
  .up {{ color: #4caf50; }} .down {{ color: #f44336; }} .flat {{ color: #888; }}
  .alerts {{ margin-bottom: 24px; display: flex; flex-wrap: wrap; gap: 8px; }}
  .alert  {{ border-radius: 8px; padding: 8px 14px; font-size: 0.82rem; font-weight: 600; }}
  .alert.danger {{ background: #3b1a1a; color: #f44336; border: 1px solid #f44336; }}
  .alert.safe   {{ background: #1a3b1a; color: #4caf50; border: 1px solid #4caf50; }}
  .alert.up     {{ background: #1a2b3b; color: #4fc3f7; border: 1px solid #4fc3f7; }}
  .charts {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(480px, 1fr)); gap: 20px; }}
  .chart-box {{ background: #1e2130; border-radius: 10px; padding: 20px; }}
  .chart-box h2 {{ font-size: 0.9rem; color: #aaa; margin-bottom: 14px; }}
  canvas {{ width: 100% !important; }}
  .section-title {{ font-size: 1rem; color: #ccc; margin: 32px 0 12px; border-left: 3px solid #4fc3f7; padding-left: 10px; }}
  .port-table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; margin-bottom: 24px; }}
  .port-table th {{ color: #666; font-weight: 500; padding: 8px 10px; text-align: right; border-bottom: 1px solid #2a2a2a; }}
  .port-table th:first-child {{ text-align: left; }}
  .port-table td {{ padding: 9px 10px; text-align: right; border-bottom: 1px solid #1a1a2a; }}
  .port-table td:first-child {{ text-align: left; color: #e0e0e0; font-weight: 500; }}
  .port-table tr:hover td {{ background: #1a1f2e; }}
  .badge {{ display: inline-block; border-radius: 4px; padding: 2px 7px; font-size: 0.72rem; font-weight: 700; margin-left: 4px; }}
  .badge-buy  {{ background: #1a3b1a; color: #4caf50; }}
  .badge-sell {{ background: #3b1a1a; color: #f44336; }}
  .port-charts {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr)); gap: 16px; margin-bottom: 32px; }}
  .port-chart-box {{ background: #1e2130; border-radius: 10px; padding: 16px 18px; }}
  .port-chart-box h3 {{ font-size: 0.85rem; color: #ccc; margin-bottom: 4px; }}
  .port-chart-box .sub {{ font-size: 0.72rem; color: #555; margin-bottom: 12px; }}
  .news-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 12px; }}
  .news-card {{ background: #1e2130; border-radius: 8px; padding: 14px 16px; }}
  .news-card .stock-tag {{ font-size: 0.78rem; color: #4fc3f7; font-weight: 700; margin-bottom: 10px; }}
  .articles-list {{ display: flex; flex-direction: column; gap: 10px; }}
  .news-item {{ padding: 8px 10px; border-radius: 6px; background: #252840; border-left: 3px solid #444; }}
  .news-item.pos {{ border-left-color: #4caf50; background: #1a2a1e; }}
  .news-item.neg {{ border-left-color: #f44336; background: #2a1a1a; }}
  .news-sentence {{ font-size: 0.83rem; color: #dde; line-height: 1.45; display: block; margin-bottom: 5px; }}
  .news-item-meta {{ font-size: 0.70rem; color: #555; display: flex; align-items: center; gap: 8px; }}
  .news-link {{ font-size: 0.72rem; color: #4fc3f7; border: 1px solid #2a3a4a; border-radius: 4px; padding: 1px 8px; text-decoration: none; white-space: nowrap; }}
  .news-link:hover {{ background: #1a2a3a; }}
  .table-wrap {{ overflow-x: auto; -webkit-overflow-scrolling: touch; margin-bottom: 24px; }}
  .table-wrap .port-table {{ margin-bottom: 0; }}
  @media (max-width: 640px) {{
    body {{ padding: 12px; }} h1 {{ font-size: 1.15rem; }}
    .subtitle {{ font-size: 0.78rem; margin-bottom: 16px; }}
    .cards {{ grid-template-columns: repeat(2, 1fr); gap: 8px; }}
    .card .value {{ font-size: 1.05rem; }}
    .charts, .port-charts {{ grid-template-columns: 1fr; gap: 12px; }}
    .news-grid {{ grid-template-columns: 1fr; }}
    .section-title {{ margin: 20px 0 10px; font-size: 0.92rem; }}
    {mobile_hide}
    .port-table {{ font-size: 0.75rem; }}
    .port-table th, .port-table td {{ padding: 7px 6px; }}
    .badge {{ padding: 1px 5px; font-size: 0.68rem; }}
  }}
</style>
</head>
<body>
{password_overlay}
<h1>📊 시장 대시보드</h1>
<div class="subtitle">최종 업데이트: {today_str} &nbsp;|&nbsp; 최근 60일 추이</div>

<div class="alerts" id="alerts"></div>
<div class="cards"  id="cards"></div>
<div class="charts" id="charts"></div>

<div class="section-title">내 포트폴리오</div>
<div id="port-signals" style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px;"></div>
<div class="table-wrap">
<table class="port-table">
  <thead><tr>{table_header}</tr></thead>
  <tbody id="port-tbody"></tbody>
</table>
</div>

<div class="section-title">종목별 차트 (최근 60일)</div>
<div class="port-charts" id="port-charts"></div>

<div style="display:flex;align-items:center;gap:16px;margin:32px 0 12px;">
  <div class="section-title" style="margin:0;">관련 뉴스</div>
  <div style="display:flex;gap:12px;align-items:center;font-size:0.75rem;">
    <span style="display:flex;align-items:center;gap:5px;"><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#4caf50;"></span><span style="color:#888;">긍정적 뉴스</span></span>
    <span style="display:flex;align-items:center;gap:5px;"><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#f44336;"></span><span style="color:#888;">부정적 뉴스</span></span>
    <span style="display:flex;align-items:center;gap:5px;"><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#444;"></span><span style="color:#888;">중립</span></span>
  </div>
</div>
<div id="news-section" style="margin-bottom:32px;"></div>

<script>
const cards        = {cards_json};
const portHistory  = {port_history_json};
const alerts       = {alerts_json};
const labels       = {labels_json};
const datasets     = {datasets_json};
const groups       = {groups_json};
const colors       = {colors_json};
const portfolio    = {portfolio_json};
const portSignals  = {port_signals_json};
const newsList     = {news_json};

const alertsEl = document.getElementById('alerts');
if (alerts.length === 0) {{
  alertsEl.innerHTML = '<span style="color:#555;font-size:.82rem">오늘 특이 시그널 없음</span>';
}} else {{
  alerts.forEach(a => {{ const el = document.createElement('div'); el.className = `alert ${{a.type}}`; el.textContent = a.msg; alertsEl.appendChild(el); }});
}}

const cardsEl = document.getElementById('cards');
cards.forEach(c => {{
  const cls = c.change > 0 ? 'up' : c.change < 0 ? 'down' : 'flat';
  const arrow = c.change > 0 ? '▲' : c.change < 0 ? '▼' : '–';
  cardsEl.innerHTML += `<div class="card"><div class="label">${{c.name}}</div><div class="value">${{c.value.toLocaleString()}}</div><div class="change ${{cls}}">${{arrow}} ${{Math.abs(c.change).toFixed(2)}}%</div></div>`;
}});

const chartsEl = document.getElementById('charts');
Object.entries(groups).forEach(([groupName, tickers]) => {{
  const validTickers = tickers.filter(t => datasets[t]);
  if (!validTickers.length) return;
  const box = document.createElement('div');
  box.className = 'chart-box';
  box.innerHTML = `<h2>${{groupName}}</h2>`;
  validTickers.forEach(name => {{ box.innerHTML += `<canvas id="chart_${{name.replace(/[^a-zA-Z0-9]/g,'_')}}" height="120"></canvas>`; }});
  chartsEl.appendChild(box);
  validTickers.forEach(name => {{
    const ctx = document.getElementById('chart_' + name.replace(/[^a-zA-Z0-9]/g,'_')).getContext('2d');
    const color = colors[name] || '#aaa';
    const d = datasets[name];
    new Chart(ctx, {{
      type: 'line',
      data: {{ labels: d.dates || labels, datasets: [{{ label: name, data: d.values !== undefined ? d.values : d,
        borderColor: color, backgroundColor: color+'22', borderWidth: 2, pointRadius: 0, fill: true, tension: 0.3, spanGaps: true }}] }},
      options: {{ responsive: true, interaction: {{ intersect: false, mode: 'index' }},
        plugins: {{ legend: {{ labels: {{ color: '#aaa', font: {{ size: 11 }} }} }}, tooltip: {{ backgroundColor: '#2a2a3a', titleColor: '#fff', bodyColor: '#ccc' }} }},
        scales: {{ x: {{ ticks: {{ color: '#555', maxTicksLimit: 10 }}, grid: {{ color: '#2a2a2a' }} }}, y: {{ ticks: {{ color: '#555' }}, grid: {{ color: '#2a2a2a' }} }} }}
      }}
    }});
  }});
}});

const newsEl = document.getElementById('news-section');
if (newsList.length === 0) {{
  newsEl.innerHTML = '<span style="color:#555;font-size:.82rem">수집된 뉴스 없음</span>';
}} else {{
  const grouped = {{}};
  newsList.forEach(n => {{ const key = n.stock+'|'+n.ticker; if (!grouped[key]) grouped[key] = {{stock:n.stock,ticker:n.ticker,articles:[]}}; grouped[key].articles.push(n); }});
  const grid = document.createElement('div'); grid.className = 'news-grid';
  Object.values(grouped).forEach(g => {{
    let articlesHtml = '';
    g.articles.forEach(a => {{
      const cls = a.sentiment==='pos'?'pos':a.sentiment==='neg'?'neg':'';
      articlesHtml += `<div class="news-item ${{cls}}"><span class="news-sentence">${{a.title_ko}}</span><div class="news-item-meta">${{a.publisher}} · ${{a.date}}<a class="news-link" href="${{a.link}}" target="_blank">원문 →</a></div></div>`;
    }});
    grid.innerHTML += `<div class="news-card"><div class="stock-tag">${{g.stock}} <span style="color:#555">(${{g.ticker}})</span></div><div class="articles-list">${{articlesHtml}}</div></div>`;
  }});
  newsEl.appendChild(grid);
}}

const portChartsEl = document.getElementById('port-charts');
Object.entries(portHistory).forEach(([ticker, d]) => {{
  const box = document.createElement('div'); box.className = 'port-chart-box';
  const cur = d.currency === 'KRW' ? '₩' : '$';
  const canvasId = 'pchart_' + ticker.replace(/[^a-zA-Z0-9]/g,'_');
  box.innerHTML = `<h3>${{d.name}} <span style="color:#555;font-size:.72rem">${{ticker}}</span></h3><div class="sub">{chart_sub}</div><canvas id="${{canvasId}}" height="110"></canvas>`;
  portChartsEl.appendChild(box);
  const ctx = document.getElementById(canvasId).getContext('2d');
  new Chart(ctx, {{
    type: 'line',
    data: {{ labels: d.dates, datasets: [
      {{ label:'종가', data:d.prices, borderColor:'#4fc3f7', backgroundColor:'#4fc3f722', borderWidth:2, pointRadius:0, fill:true, tension:0.2, spanGaps:true, order:1 }},
      {{ label:'MA20', data:d.ma20, borderColor:'#ffb74d', borderWidth:1.5, pointRadius:0, fill:false, tension:0.2, spanGaps:true, borderDash:[4,2], order:2 }},
      {{ label:'MA60', data:d.ma60, borderColor:'#ce93d8', borderWidth:1.5, pointRadius:0, fill:false, tension:0.2, spanGaps:true, borderDash:[4,2], order:3 }},{avg_line_dataset}
    ]}},
    options: {{ responsive:true, interaction:{{intersect:false,mode:'index'}},
      plugins:{{ legend:{{labels:{{color:'#777',font:{{size:10}},boxWidth:20,padding:10}}}}, tooltip:{{backgroundColor:'#2a2a3a',titleColor:'#fff',bodyColor:'#ccc'}} }},
      scales:{{ x:{{ticks:{{color:'#555',maxTicksLimit:8}},grid:{{color:'#1a1a2a'}}}}, y:{{ticks:{{color:'#555'}},grid:{{color:'#1a1a2a'}}}} }}
    }}
  }});
}});

const portSigEl = document.getElementById('port-signals');
if (portSignals.length === 0) {{
  portSigEl.innerHTML = '<span style="color:#555;font-size:.82rem">포트폴리오 시그널 없음</span>';
}} else {{
  portSignals.forEach(s => {{ const el = document.createElement('div'); el.className = `alert ${{s.type==='buy'?'safe':'danger'}}`; el.textContent = (s.type==='buy'?'▲ 매수 | ':'▼ 매도 | ')+s.msg; portSigEl.appendChild(el); }});
}}

const tbody = document.getElementById('port-tbody');
portfolio.forEach(r => {{
  const dayCls  = r.day_chg >= 0 ? 'up' : 'down';
  const dayArrow = r.day_chg >= 0 ? '▲' : '▼';
  const cur = r.currency === 'KRW' ? '₩' : '$';{pnl_vars}
  let rsiBadge = '';
  if (r.rsi_signal === 'oversold')   rsiBadge = '<span class="badge badge-buy">매수</span>';
  if (r.rsi_signal === 'overbought') rsiBadge = '<span class="badge badge-sell">매도</span>';
  let maBadge = '';
  if (r.cross === 'golden') maBadge = '<span class="badge badge-buy">골든크로스</span>';
  if (r.cross === 'dead')   maBadge = '<span class="badge badge-sell">데드크로스</span>';
  const maStatus = r.ma60 ? (r.ma20 > r.ma60 ? '<span style="color:#4caf50">MA20 > MA60</span>' : '<span style="color:#f44336">MA20 < MA60</span>') : 'N/A';
  let sigCell = '<span style="color:#444">-</span>';
  if (r.cross==='golden'||r.rsi_signal==='oversold') sigCell='<span style="color:#4caf50;font-weight:700">▲ 매수 고려</span>';
  else if (r.cross==='dead'||r.rsi_signal==='overbought') sigCell='<span style="color:#f44336;font-weight:700">▼ 매도 고려</span>';
  tbody.innerHTML += `<tr>{table_row}</tr>`;
}});
</script>
</body>
</html>"""

    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"{'공유용' if public else '개인용'} 대시보드 생성 완료: {out_file}")


if __name__ == "__main__":
    raw_pw = os.environ.get("DASHBOARD_PASSWORD", "")
    pw_hash = hashlib.sha256(raw_pw.encode()).hexdigest() if raw_pw else ""

    build_dashboard(public=True)
    build_dashboard(public=False, password_hash=pw_hash)
