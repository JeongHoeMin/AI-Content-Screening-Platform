"""Static, dependency-free client for the recommendation history page."""

from __future__ import annotations


HISTORY_HTML: str = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><title>추천 이력</title>
<style>
:root{color-scheme:dark}body{font-family:system-ui,-apple-system,sans-serif;margin:0;background:#07111e;color:#edf3ff}main{max-width:1180px;margin:auto;padding:32px}.panel{background:#101d2d;border:1px solid #253852;border-radius:12px;padding:20px;margin:18px 0}.empty{color:#aec0d8}.buy{color:#7ae5a1}.sell{color:#ff8c9b}.positive{color:#7ae5a1}.negative{color:#ff8c9b}table{width:100%;border-collapse:collapse}td,th{padding:10px;border-bottom:1px solid #29415f;text-align:left}.run-header{display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px;align-items:baseline}.run-time{font-weight:700;font-size:17px}.run-summary{color:#c7d8ee;font-size:14px}nav a{color:#9fc2ff;margin-right:14px}
</style></head><body><main>
<h1>추천 이력</h1><p>과거 추천 실행(run)별로 매수·매도 종목의 진입가 대비 현재가 손익률을 확인합니다.</p>
<nav><a href="/">대시보드로 돌아가기</a><a href="/settings">정기 실행 설정</a></nav>
<section class="panel"><div id="runs"><p class="empty">이력을 불러오는 중입니다.</p></div></section>
<script>
const runsElement=document.querySelector('#runs');
const escapeHtml=value=>String(value).replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const empty=message=>`<p class="empty">${escapeHtml(message)}</p>`;
const priceErrorLabels={not_configured:'가격 조회 미설정',transport:'네트워크 오류',authentication:'인증 실패',rate_limit:'요청 한도 초과',server:'서버 오류',invalid_ticker:'종목코드 오류',invalid_payload:'응답 형식 오류',not_found:'가격 정보 없음'};
const priceErrorLabel=kind=>kind?(priceErrorLabels[kind]||kind):'사유 미상';
const formatKst=value=>{if(!value)return 'KST 시각 미확인';const parts=new Intl.DateTimeFormat('en-US',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date(value)).reduce((result,part)=>({...result,[part.type]:part.value}),{});return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute} KST`};
const formatPercent=value=>value===null||value===undefined?'-':`${value>=0?'+':''}${Number(value).toFixed(1)}%`;
const returnClass=value=>value===null||value===undefined?'':value>0?'positive':value<0?'negative':'';
const renderReturnCell=item=>{if(item.entry_price===null)return `가격 미확인 (사유: ${escapeHtml(priceErrorLabel(item.entry_error_kind))})`;if(item.return_percent===null)return `현재가 미확인 (사유: ${escapeHtml(priceErrorLabel(item.latest_error_kind))})`;return `<span class="${returnClass(item.return_percent)}">${escapeHtml(formatPercent(item.return_percent))}</span>`};
const renderRunTable=run=>run.items.length?`<table><thead><tr><th>종목</th><th>코드</th><th>추천</th><th>진입가</th><th>현재가</th><th>손익률</th></tr></thead><tbody>${run.items.map(item=>`<tr><td>${escapeHtml(item.company_name)}</td><td>${escapeHtml(item.ticker)}</td><td class="${item.action==='buy'?'buy':'sell'}">${escapeHtml(item.action)}</td><td>${item.entry_price===null?'-':escapeHtml(item.entry_price)+'원'}</td><td>${item.latest_price===null?'-':escapeHtml(item.latest_price)+'원'}</td><td>${renderReturnCell(item)}</td></tr>`).join('')}</tbody></table>`:empty('이 회차에는 매수·매도 추천이 없습니다.');
const renderRunSummary=summary=>{const winRate=summary.positive_win_rate===null?'-':`${Number(summary.positive_win_rate).toFixed(1)}%`,mean=summary.mean_return_percent===null?'-':`${Number(summary.mean_return_percent).toFixed(1)}%`;return `확인 ${escapeHtml(summary.confirmed_count)}건 · 미확인 ${escapeHtml(summary.unavailable_count)}건 · BUY ${escapeHtml(summary.buy_count)}건 · SELL ${escapeHtml(summary.sell_count)}건 · 승률 ${escapeHtml(winRate)} · 평균 ${escapeHtml(mean)}`};
const renderRuns=runs=>runs.length?runs.map(run=>`<article class="panel"><div class="run-header"><span class="run-time">${escapeHtml(formatKst(run.observed_at))}</span><span class="run-summary">${renderRunSummary(run.summary)}</span></div>${renderRunTable(run)}</article>`).join(''):empty('아직 가격이 기록된 추천 이력이 없습니다.');
async function load(){try{const response=await fetch('/api/runs/history');if(!response.ok)throw new Error('history_load_failed');const data=await response.json();runsElement.innerHTML=renderRuns(data.runs)}catch(_){runsElement.innerHTML=empty('이력을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.')}}
load();
</script>
</main></body></html>"""
