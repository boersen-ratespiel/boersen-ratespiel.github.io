const bootSplash = document.getElementById('bootSplash');
if (bootSplash.style.display !== 'none') {
  setTimeout(() => {
    bootSplash.classList.add('hide');
    sessionStorage.setItem('boersenspiel_booted', '1');
    setTimeout(() => bootSplash.remove(), 550);
  }, 1300);
} else {
  bootSplash.remove();
}

const menu = document.getElementById('menu');
document.querySelectorAll('.menu-item[data-view]').forEach(btn => {
  btn.addEventListener('click', () => {
    menu.classList.add('hidden');
    document.getElementById(btn.dataset.view).classList.remove('hidden');
    if (btn.dataset.view === 'learn-view') resetLearnView();
    if (btn.dataset.view === 'game-view') newRound();
  });
});
document.querySelectorAll('.back-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const view = btn.closest('.view');
    view.classList.add('hidden');
    menu.classList.remove('hidden');
    if (view.id === 'depot-view') stopDepotLive();
    if (view.id === 'game-view') clearRoundTimer();
  });
});

const canvas = document.getElementById('chart');
const ctx = canvas.getContext('2d');
const W = canvas.width;
const H = canvas.height;

const HISTORY_POINTS = 90;
const FUTURE_POINTS = 25;

const btnUp = document.getElementById('btnUp');
const btnDown = document.getElementById('btnDown');
const btnNext = document.getElementById('btnNext');
const banner = document.getElementById('banner');

const roundEl = document.getElementById('round');
const scoreEl = document.getElementById('score');
const streakEl = document.getElementById('streak');
const bestEl = document.getElementById('best');
const multiplierBadge = document.getElementById('multiplierBadge');
const roundTimerBar = document.getElementById('roundTimerBar');
const streakToast = document.getElementById('streakToast');

const ROUND_TIME_MS = 6000;
const BASE_POINTS = 10;
const STREAK_MILESTONES = [3, 5, 10];

let round = 1;
let score = 0;
let streak = 0;
let best = Number(localStorage.getItem('boersenspiel_best') || 0);
bestEl.textContent = best;

let series = [];
let guessing = true;
let roundTimer = null;
let roundTimeLeft = ROUND_TIME_MS;

function getMultiplier(s) {
  if (s >= 10) return 3;
  if (s >= 5) return 2;
  if (s >= 3) return 1.5;
  return 1;
}

function updateMultiplierBadge() {
  const mult = getMultiplier(streak);
  if (mult > 1) {
    multiplierBadge.textContent = '🔥 ×' + mult;
    multiplierBadge.classList.remove('hidden');
  } else {
    multiplierBadge.classList.add('hidden');
  }
}

function startRoundTimer() {
  clearRoundTimer();
  roundTimeLeft = ROUND_TIME_MS;
  roundTimerBar.style.width = '100%';
  roundTimerBar.classList.remove('urgent');
  roundTimer = setInterval(() => {
    roundTimeLeft -= 100;
    const pct = Math.max(0, roundTimeLeft / ROUND_TIME_MS) * 100;
    roundTimerBar.style.width = pct + '%';
    roundTimerBar.classList.toggle('urgent', pct < 30);
    if (roundTimeLeft <= 0) {
      clearRoundTimer();
      if (guessing) revealAndScore(null, true);
    }
  }, 100);
}

function clearRoundTimer() {
  if (roundTimer) {
    clearInterval(roundTimer);
    roundTimer = null;
  }
}

function showStreakToast(streakCount, multiplier) {
  streakToast.textContent = `🔥 ${streakCount}er Serie! Punkte ×${multiplier}`;
  streakToast.classList.remove('hidden', 'pop');
  void streakToast.offsetWidth;
  streakToast.classList.add('pop');
  clearTimeout(showStreakToast._timer);
  showStreakToast._timer = setTimeout(() => streakToast.classList.add('hidden'), 1800);
}

function gaussianRandom() {
  let u = 0, v = 0;
  while (u === 0) u = Math.random();
  while (v === 0) v = Math.random();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

function generateSeries() {
  const total = HISTORY_POINTS + FUTURE_POINTS;
  const drift = (Math.random() - 0.45) * 0.006;
  const volatility = 0.012 + Math.random() * 0.022;
  const points = [100];
  for (let i = 1; i < total; i++) {
    const shock = gaussianRandom() * volatility;
    const next = points[i - 1] * (1 + drift + shock);
    points.push(Math.max(5, next));
  }
  return points;
}

function draw(visibleCount, opts = {}) {
  ctx.clearRect(0, 0, W, H);

  const visible = series.slice(0, visibleCount);
  const min = Math.min(...visible);
  const max = Math.max(...visible);
  const pad = (max - min) * 0.12 || 1;
  const yMin = min - pad;
  const yMax = max + pad;

  const historyEnd = Math.min(HISTORY_POINTS, visibleCount);
  const xStep = W / (HISTORY_POINTS + FUTURE_POINTS - 1);

  function toXY(i, price) {
    const x = i * xStep;
    const y = H - ((price - yMin) / (yMax - yMin)) * H;
    return [x, y];
  }

  // Gradient-Fläche unter dem bisherigen Kursverlauf
  const gradient = ctx.createLinearGradient(0, 0, 0, H);
  gradient.addColorStop(0, 'rgba(96, 165, 250, 0.28)');
  gradient.addColorStop(1, 'rgba(96, 165, 250, 0)');
  ctx.beginPath();
  for (let i = 0; i < historyEnd; i++) {
    const [x, y] = toXY(i, series[i]);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.lineTo(toXY(historyEnd - 1, series[historyEnd - 1])[0], H);
  ctx.lineTo(toXY(0, series[0])[0], H);
  ctx.closePath();
  ctx.fillStyle = gradient;
  ctx.fill();

  ctx.lineWidth = 2.5;
  ctx.lineJoin = 'round';

  ctx.shadowColor = 'rgba(96, 165, 250, 0.6)';
  ctx.shadowBlur = 8;
  ctx.strokeStyle = '#60a5fa';
  ctx.beginPath();
  for (let i = 0; i < historyEnd; i++) {
    const [x, y] = toXY(i, series[i]);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();
  ctx.shadowBlur = 0;

  if (visibleCount > HISTORY_POINTS) {
    const revealColor = opts.color || '#8b95ab';
    ctx.shadowColor = revealColor;
    ctx.shadowBlur = 10;
    ctx.strokeStyle = revealColor;
    ctx.beginPath();
    for (let i = HISTORY_POINTS - 1; i < visibleCount; i++) {
      const [x, y] = toXY(i, series[i]);
      if (i === HISTORY_POINTS - 1) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.shadowBlur = 0;
  }

  const dividerX = (HISTORY_POINTS - 1) * xStep;
  ctx.strokeStyle = 'rgba(255,255,255,0.15)';
  ctx.setLineDash([4, 4]);
  ctx.beginPath();
  ctx.moveTo(dividerX, 0);
  ctx.lineTo(dividerX, H);
  ctx.stroke();
  ctx.setLineDash([]);

  const [lx, ly] = toXY(visibleCount - 1, series[visibleCount - 1]);
  const dotColor = visibleCount > HISTORY_POINTS ? (opts.color || '#8b95ab') : '#60a5fa';
  ctx.shadowColor = dotColor;
  ctx.shadowBlur = 14;
  ctx.fillStyle = dotColor;
  ctx.beginPath();
  ctx.arc(lx, ly, 5, 0, Math.PI * 2);
  ctx.fill();
  ctx.shadowBlur = 0;
}

function newRound() {
  series = generateSeries();
  guessing = true;
  banner.classList.add('hidden');
  banner.classList.remove('correct', 'wrong');
  btnNext.classList.add('hidden');
  btnUp.disabled = false;
  btnDown.disabled = false;
  roundEl.textContent = round;
  updateMultiplierBadge();
  draw(HISTORY_POINTS);
  startRoundTimer();
}

function revealAndScore(guessUp, timedOut = false) {
  clearRoundTimer();
  guessing = false;
  btnUp.disabled = true;
  btnDown.disabled = true;

  const startPrice = series[HISTORY_POINTS - 1];
  const endPrice = series[series.length - 1];
  const actuallyUp = endPrice > startPrice;
  const pctChange = ((endPrice - startPrice) / startPrice) * 100;
  const correct = guessUp === actuallyUp;
  const revealColor = actuallyUp ? '#34d399' : '#fb7185';
  const suspenseColor = '#facc15';

  let frame = HISTORY_POINTS;
  const timer = setInterval(() => {
    frame++;
    const isLastFrame = frame >= series.length;
    // Während der Enthüllung bewusst eine neutrale Farbe zeigen, damit man
    // dem Ergebnis nicht schon an der Linienfarbe ansieht, bevor sie fertig
    // gezeichnet ist — erst im letzten Frame wird eingefärbt.
    draw(frame, { color: isLastFrame ? revealColor : suspenseColor });
    if (isLastFrame) {
      clearInterval(timer);
      showResult(correct, pctChange, timedOut);
    }
  }, 55);
}

const CONFETTI_COLORS = ['#34d399', '#60a5fa', '#a78bfa', '#fb7185', '#facc15'];

function burstConfetti() {
  const count = 28;
  for (let i = 0; i < count; i++) {
    const piece = document.createElement('div');
    piece.className = 'confetti-piece';
    const size = 6 + Math.random() * 6;
    piece.style.left = Math.random() * 100 + 'vw';
    piece.style.width = size + 'px';
    piece.style.height = size * 0.4 + 'px';
    piece.style.background = CONFETTI_COLORS[i % CONFETTI_COLORS.length];
    piece.style.animationDuration = (1.6 + Math.random() * 1.2) + 's';
    piece.style.animationDelay = (Math.random() * 0.15) + 's';
    document.body.appendChild(piece);
    piece.addEventListener('animationend', () => piece.remove());
  }
}

function bump(el) {
  el.classList.remove('bump');
  void el.offsetWidth;
  el.classList.add('bump');
}

function showResult(correct, pctChange, timedOut = false) {
  let points = 0;
  if (correct) {
    const multiplier = getMultiplier(streak);
    points = Math.round(BASE_POINTS * multiplier);
    score += points;
    streak++;
    if (streak > best) {
      best = streak;
      localStorage.setItem('boersenspiel_best', String(best));
    }
    burstConfetti();
    if (STREAK_MILESTONES.includes(streak)) {
      showStreakToast(streak, getMultiplier(streak));
    }
  } else {
    streak = 0;
  }

  updateMultiplierBadge();
  scoreEl.textContent = score;
  streakEl.textContent = streak;
  bestEl.textContent = best;
  [scoreEl, streakEl, bestEl].forEach(bump);

  const sign = pctChange >= 0 ? '+' : '';
  const resultText = timedOut ? '⏰ Zeit abgelaufen!' : correct ? `✅ Richtig! +${points} Punkte` : '❌ Falsch.';
  banner.textContent = `${resultText} ${sign}${pctChange.toFixed(1)}%`;
  banner.classList.remove('hidden');
  banner.classList.add(correct ? 'correct' : 'wrong');

  btnNext.classList.remove('hidden');
}

btnUp.addEventListener('click', () => { if (guessing) revealAndScore(true); });
btnDown.addEventListener('click', () => { if (guessing) revealAndScore(false); });
btnNext.addEventListener('click', () => {
  round++;
  newRound();
});

// --- Musterdepot ---

const DEPOT_STORAGE_KEY = 'boersenspiel_depot';
const DEPOT_START_CASH = 10000;
const DEPOT_BUY_AMOUNT = 500;

const DEPOT_STOCKS_DEFAULT = [
  { id: 'tech', name: 'TechCorp', price: 120 },
  { id: 'green', name: 'GreenEnergy AG', price: 45 },
  { id: 'handel', name: 'HandelsKette', price: 80 },
  { id: 'bio', name: 'BioPharma', price: 200 },
];

function loadDepot() {
  try {
    const saved = JSON.parse(localStorage.getItem(DEPOT_STORAGE_KEY));
    if (saved && typeof saved.cash === 'number' && saved.stocks) {
      return saved;
    }
  } catch (e) {}
  return {
    cash: DEPOT_START_CASH,
    stocks: DEPOT_STOCKS_DEFAULT.map(s => ({ ...s })),
    holdings: {},
  };
}

let depot = loadDepot();

function saveDepot() {
  localStorage.setItem(DEPOT_STORAGE_KEY, JSON.stringify(depot));
}

function formatEuro(n) {
  return n.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €';
}

function depotHoldingsValue() {
  return depot.stocks.reduce((sum, s) => sum + (depot.holdings[s.id] || 0) * s.price, 0);
}

function renderDepot() {
  const cashEl = document.getElementById('depotCash');
  const holdingsValueEl = document.getElementById('depotHoldingsValue');
  const totalEl = document.getElementById('depotTotal');
  const returnEl = document.getElementById('depotReturn');
  const list = document.getElementById('depotStocks');

  const holdingsValue = depotHoldingsValue();
  const total = depot.cash + holdingsValue;
  const returnPct = ((total - DEPOT_START_CASH) / DEPOT_START_CASH) * 100;

  cashEl.textContent = formatEuro(depot.cash);
  holdingsValueEl.textContent = formatEuro(holdingsValue);
  totalEl.textContent = formatEuro(total);
  returnEl.textContent = (returnPct >= 0 ? '+' : '') + returnPct.toFixed(1) + ' %';
  returnEl.style.color = returnPct > 0 ? 'var(--green)' : returnPct < 0 ? 'var(--red)' : '';

  list.innerHTML = '';
  depot.stocks.forEach(stock => {
    const shares = depot.holdings[stock.id] || 0;
    const value = shares * stock.price;
    const trend = depotTrends[stock.id];
    const trendClass = trend === 'up' ? 'flash-up' : trend === 'down' ? 'flash-down' : '';
    const trendArrow = trend === 'up' ? ' ▲' : trend === 'down' ? ' ▼' : '';

    const li = document.createElement('li');
    li.className = 'stock-row';
    li.innerHTML = `
      <div class="stock-info">
        <span class="stock-name">${stock.name}</span>
        <span class="stock-price ${trendClass}">${formatEuro(stock.price)} je Anteil${trendArrow}</span>
        ${shares > 0 ? `<span class="stock-position">${shares.toFixed(2)} Anteile · ${formatEuro(value)}</span>` : ''}
      </div>
      <div class="stock-actions">
        <button class="mini-btn buy" data-action="buy" data-id="${stock.id}">+ ${DEPOT_BUY_AMOUNT} €</button>
        <button class="mini-btn sell" data-action="sell" data-id="${stock.id}" ${shares > 0 ? '' : 'disabled'}>Verkaufen</button>
      </div>
    `;
    list.appendChild(li);
  });
}

document.getElementById('depotStocks').addEventListener('click', (e) => {
  const btn = e.target.closest('button[data-action]');
  if (!btn) return;
  const stock = depot.stocks.find(s => s.id === btn.dataset.id);
  if (!stock) return;

  if (btn.dataset.action === 'buy') {
    if (depot.cash < DEPOT_BUY_AMOUNT) return;
    depot.cash -= DEPOT_BUY_AMOUNT;
    depot.holdings[stock.id] = (depot.holdings[stock.id] || 0) + DEPOT_BUY_AMOUNT / stock.price;
  } else if (btn.dataset.action === 'sell') {
    const shares = depot.holdings[stock.id] || 0;
    depot.cash += shares * stock.price;
    depot.holdings[stock.id] = 0;
  }

  saveDepot();
  renderDepot();
});

let depotTrends = {};
let depotLiveTimer = null;
const DEPOT_TICK_MS = 1800;

function tickDepotPrices() {
  depot.stocks.forEach(stock => {
    const oldPrice = stock.price;
    const volatility = 0.03;
    const shock = gaussianRandom() * volatility;
    stock.price = Math.max(1, stock.price * (1 + shock));
    depotTrends[stock.id] = stock.price > oldPrice ? 'up' : stock.price < oldPrice ? 'down' : null;
  });
  saveDepot();
  renderDepot();
}

function startDepotLive() {
  if (depotLiveTimer) return;
  tickDepotPrices();
  depotLiveTimer = setInterval(tickDepotPrices, DEPOT_TICK_MS);
  const toggleBtn = document.getElementById('depotToggle');
  toggleBtn.textContent = '⏸ Pausieren';
  toggleBtn.classList.remove('start');
  toggleBtn.classList.add('stop');
  document.getElementById('depotLiveHint').classList.remove('hidden');
}

function stopDepotLive() {
  if (!depotLiveTimer) return;
  clearInterval(depotLiveTimer);
  depotLiveTimer = null;
  const toggleBtn = document.getElementById('depotToggle');
  toggleBtn.textContent = '▶️ Simulation starten';
  toggleBtn.classList.remove('stop');
  toggleBtn.classList.add('start');
  document.getElementById('depotLiveHint').classList.add('hidden');
}

document.getElementById('depotToggle').addEventListener('click', () => {
  if (depotLiveTimer) stopDepotLive(); else startDepotLive();
});

function showConfirm(message, onConfirm) {
  const overlay = document.getElementById('confirmModal');
  document.getElementById('confirmModalText').textContent = message;
  overlay.classList.remove('hidden');

  const okBtn = document.getElementById('confirmModalOk');
  const cancelBtn = document.getElementById('confirmModalCancel');

  function cleanup() {
    overlay.classList.add('hidden');
    okBtn.removeEventListener('click', onOk);
    cancelBtn.removeEventListener('click', onCancel);
    overlay.removeEventListener('click', onOverlayClick);
  }
  function onOk() { cleanup(); onConfirm(); }
  function onCancel() { cleanup(); }
  function onOverlayClick(e) { if (e.target === overlay) cleanup(); }

  okBtn.addEventListener('click', onOk);
  cancelBtn.addEventListener('click', onCancel);
  overlay.addEventListener('click', onOverlayClick);
}

document.getElementById('depotReset').addEventListener('click', () => {
  showConfirm('Depot wirklich zurücksetzen? Dein virtuelles Guthaben und alle Positionen gehen verloren.', () => {
    stopDepotLive();
    depot = {
      cash: DEPOT_START_CASH,
      stocks: DEPOT_STOCKS_DEFAULT.map(s => ({ ...s })),
      holdings: {},
    };
    depotTrends = {};
    saveDepot();
    renderDepot();
  });
});

renderDepot();

// --- KI-Berater ---

function generateDepotAdvice() {
  const holdingsEntries = depot.stocks
    .map(s => ({ ...s, shares: depot.holdings[s.id] || 0, value: (depot.holdings[s.id] || 0) * s.price }))
    .filter(s => s.shares > 0);
  const holdingsValue = depotHoldingsValue();
  const total = depot.cash + holdingsValue;
  const returnPct = ((total - DEPOT_START_CASH) / DEPOT_START_CASH) * 100;

  const messages = [];

  if (holdingsEntries.length === 0) {
    messages.push('Dein Depot ist noch komplett in Cash. Wie wäre es mit einer ersten Position, um zu starten? 🚀');
  } else if (holdingsEntries.length === 1) {
    messages.push(`Du hältst aktuell nur ${holdingsEntries[0].name}. Eine zweite Aktie aus einer anderen Branche würde dein Risiko streuen.`);
  } else {
    messages.push(`Du bist in ${holdingsEntries.length} verschiedene Aktien investiert — solide Diversifikation für den Anfang.`);
  }

  if (holdingsEntries.length > 0) {
    const largest = holdingsEntries.reduce((a, b) => (b.value > a.value ? b : a));
    const concentration = (largest.value / holdingsValue) * 100;
    if (concentration > 60) {
      messages.push(`Achtung: ${concentration.toFixed(0)}% deines Depotwerts stecken allein in ${largest.name}. Das ist ein Klumpenrisiko.`);
    }
  }

  const cashRatio = (depot.cash / total) * 100;
  if (cashRatio > 70 && holdingsEntries.length > 0) {
    messages.push(`${cashRatio.toFixed(0)}% deines Vermögens liegen noch als Cash da — ungenutztes Potenzial fürs Depot.`);
  }

  if (returnPct > 5) {
    messages.push(`Deine Rendite von +${returnPct.toFixed(1)}% läuft gut — bleib diszipliniert und handle nicht überstürzt. 📈`);
  } else if (returnPct < -5) {
    messages.push(`Aktuell ${returnPct.toFixed(1)}% im Minus — ganz normal bei schwankenden Kursen. Langfristig zählt der Zeithorizont, nicht ein einzelner Tag.`);
  } else {
    messages.push(`Deine Rendite liegt bei ${returnPct >= 0 ? '+' : ''}${returnPct.toFixed(1)}% — im neutralen Bereich, gut zu beobachten.`);
  }

  return messages.slice(0, 4);
}

function showTypingBubble(container) {
  const bubble = document.createElement('div');
  bubble.className = 'ai-bubble ai-typing-bubble';
  bubble.innerHTML = '<span class="ai-typing-dots"><span></span><span></span><span></span></span>';
  container.appendChild(bubble);
  return bubble;
}

function openAiAdvisor() {
  const overlay = document.getElementById('aiModal');
  const body = document.getElementById('aiChatBody');
  body.innerHTML = '';
  overlay.classList.remove('hidden');

  const typingBubble = showTypingBubble(body);

  setTimeout(() => {
    typingBubble.remove();
    const advice = generateDepotAdvice();
    advice.forEach((text, i) => {
      setTimeout(() => {
        const bubble = document.createElement('div');
        bubble.className = 'ai-bubble';
        bubble.textContent = text;
        body.appendChild(bubble);
        body.scrollTop = body.scrollHeight;
      }, i * 450);
    });
  }, 1100);
}

document.getElementById('aiAdvisorBtn').addEventListener('click', openAiAdvisor);
document.getElementById('aiModalClose').addEventListener('click', () => {
  document.getElementById('aiModal').classList.add('hidden');
});
document.getElementById('aiModal').addEventListener('click', (e) => {
  if (e.target.id === 'aiModal') document.getElementById('aiModal').classList.add('hidden');
});

// --- News ---

const NEWS_POOL = [
  { headline: 'DAX unter Druck', desc: 'Steigende Ölpreise belasten die Märkte, der DAX hat zuletzt deutlich nachgegeben.', category: 'Markt', sentiment: 'bearish', impact: 3 },
  { headline: 'Fed signalisiert Zinssenkung', desc: 'Die Notenbank stellt eine lockerere Geldpolitik in Aussicht — die Börsen reagieren erleichtert.', category: 'Politik', sentiment: 'bullish', impact: 3 },
  { headline: 'Öl auf Jahreshoch', desc: 'Geopolitische Spannungen treiben die Rohstoffpreise weiter nach oben.', category: 'Markt', sentiment: 'bearish', impact: 2 },
  { headline: 'BASF plant Börsengang der Agrarsparte', desc: 'Das Agrargeschäft soll 2027 an die Frankfurter Börse gebracht werden — mögliche Bewertung: 20–30 Mrd. Euro.', category: 'Unternehmen', sentiment: 'bullish', impact: 2 },
  { headline: 'Sartorius im Plus', desc: 'Die Vorzugsaktie von Sartorius legte deutlich um +4,36% zu.', category: 'Unternehmen', sentiment: 'bullish', impact: 1 },
  { headline: 'Tech-Aktien unter Verkaufsdruck', desc: 'Sorge vor überzogenen Bewertungen im KI-Sektor lässt Kurse fallen.', category: 'Trend', sentiment: 'bearish', impact: 2 },
  { headline: 'Neuer Rekord beim DAX in Sicht?', desc: 'Analysten sehen nach starken Quartalszahlen weiteres Kurspotenzial.', category: 'Markt', sentiment: 'bullish', impact: 2 },
  { headline: 'Kryptomarkt in Bewegung', desc: 'Bitcoin schwankt stark, viele Anleger bleiben vorsichtig an der Seitenlinie.', category: 'Trend', sentiment: 'neutral', impact: 1 },
  { headline: 'Inflation überrascht positiv', desc: 'Verbraucherpreise steigen langsamer als erwartet — Entspannung an den Märkten.', category: 'Politik', sentiment: 'bullish', impact: 2 },
  { headline: 'Übernahmegerüchte belasten Branche', desc: 'Spekulationen um eine mögliche Fusion sorgen für Unsicherheit bei Investoren.', category: 'Unternehmen', sentiment: 'bearish', impact: 1 },
];

const SENTIMENT_META = {
  bullish: { icon: '🟢', label: 'Bullish' },
  bearish: { icon: '🔴', label: 'Bearish' },
  neutral: { icon: '⚪', label: 'Neutral' },
};

function pickRandomNews(count) {
  const shuffled = [...NEWS_POOL].sort(() => Math.random() - 0.5);
  return shuffled.slice(0, count);
}

function renderNewsAiFazit(items) {
  const counts = { bullish: 0, bearish: 0, neutral: 0 };
  items.forEach(item => counts[item.sentiment]++);

  let text;
  if (counts.bullish > counts.bearish && counts.bullish >= 2) {
    text = 'Überwiegend positive Signale — die Chancen scheinen aktuell zu überwiegen.';
  } else if (counts.bearish > counts.bullish && counts.bearish >= 2) {
    text = 'Vorsicht angesagt — mehrere belastende Faktoren dominieren gerade das Bild.';
  } else {
    text = 'Gemischtes Bild — positive und negative Signale halten sich in etwa die Waage.';
  }

  document.getElementById('newsAiFazit').innerHTML = `<span class="ai-badge">🤖 KI-Fazit</span> ${text}`;
}

function renderNews() {
  const items = pickRandomNews(4);
  const [topStory, ...rest] = items;

  renderNewsAiFazit(items);

  const topEl = document.getElementById('newsTop');
  const sentiment = SENTIMENT_META[topStory.sentiment];
  topEl.innerHTML = `
    <div class="news-top-ribbon">🔥 Top Story</div>
    <span class="news-chip category">${topStory.category}</span>
    <span class="news-chip sentiment">${sentiment.icon} ${sentiment.label}</span>
    <h3>${topStory.headline}</h3>
    <p>${topStory.desc}</p>
  `;

  const listEl = document.getElementById('newsList');
  listEl.innerHTML = '';
  rest.forEach(item => {
    const s = SENTIMENT_META[item.sentiment];
    const li = document.createElement('li');
    li.innerHTML = `
      <div class="news-meta">
        <span class="news-chip category">${item.category}</span>
        <span class="news-chip sentiment">${s.icon}</span>
        <span class="news-impact" title="Marktrelevanz">${'🔥'.repeat(item.impact)}</span>
      </div>
      <span class="info-headline">${item.headline}</span>
      <span class="info-desc">${item.desc}</span>
    `;
    listEl.appendChild(li);
  });

  const trackEl = document.getElementById('tickerTrack');
  const tickerText = NEWS_POOL.map(n => `${SENTIMENT_META[n.sentiment].icon} ${n.headline}`).join('   ★   ');
  trackEl.textContent = tickerText + '   ★   ' + tickerText;
}

document.getElementById('newsShuffle').addEventListener('click', renderNews);
renderNews();

// --- Lernen: Quiz ---

const LEARN_BEST_KEY = 'boersenspiel_learn_best';
const QUIZ_START_LIVES = 3;

const LEVELS = [
  { id: 'leicht', name: 'Leicht', icon: '🌱', points: 10, desc: 'Die Grundlagen' },
  { id: 'mittel', name: 'Mittel', icon: '⚡', points: 20, desc: 'Für Fortgeschrittene' },
  { id: 'schwer', name: 'Schwer', icon: '🔥', points: 30, desc: 'Echte Profi-Fragen' },
];

const QUIZ_DATA = {
  leicht: [
    { q: 'Was ist eine Aktie?', options: ['Ein Anteil an einem Unternehmen', 'Ein Kredit an den Staat', 'Eine Versicherung gegen Kursverluste'], correct: 0, explain: 'Eine Aktie ist ein Anteilsschein — du wirst Miteigentümer des Unternehmens.' },
    { q: 'Was bedeutet "Diversifikation"?', options: ['Alles Geld in eine Aktie stecken', 'Geld auf mehrere Anlagen verteilen', 'Geld nur in bar halten'], correct: 1, explain: 'Streuung über mehrere Anlagen reduziert das Risiko einzelner Rückschläge.' },
    { q: 'Was ist ein ETF?', options: ['Ein börsengehandelter Fonds, der einen Index nachbildet', 'Eine Kryptowährung', 'Ein Sparbuch der Bank'], correct: 0, explain: 'ETF = Exchange Traded Fund. Er bündelt viele Aktien in einem Produkt.' },
    { q: 'Was ist der DAX?', options: ['Eine deutsche Bank', 'Der wichtigste deutsche Aktienindex', 'Eine Steuer auf Aktiengewinne'], correct: 1, explain: 'Der DAX bildet die größten deutschen Unternehmen an der Börse ab.' },
    { q: 'Was passiert beim Zinseszins?', options: ['Das Geld bleibt immer gleich', 'Zinsen erwirtschaften wieder Zinsen', 'Das Geld verliert automatisch an Wert'], correct: 1, explain: 'Zinseszins lässt dein Vermögen umso stärker wachsen, je länger du investiert bleibst.' },
  ],
  mittel: [
    { q: 'Was ist Volatilität?', options: ['Die Dividendenhöhe', 'Das Ausmaß der Kursschwankungen', 'Die Anzahl der Aktionäre'], correct: 1, explain: 'Volatilität beschreibt, wie stark ein Kurs schwankt.' },
    { q: 'Was ist eine Dividende?', options: ['Eine Gewinnbeteiligung für Aktionäre', 'Eine Strafe für den Verkauf', 'Der Kaufpreis einer Aktie'], correct: 0, explain: 'Unternehmen schütten damit einen Teil ihres Gewinns an Aktionäre aus.' },
    { q: 'Was bedeutet "Bärenmarkt"?', options: ['Ein Markt mit steigenden Kursen', 'Ein Markt mit fallenden Kursen über längere Zeit', 'Ein Markt nur für Rohstoffe'], correct: 1, explain: 'Ein Bärenmarkt beschreibt eine anhaltende Abwärtsphase.' },
    { q: 'Warum hilft ein langer Anlagehorizont?', options: ['Kurzfristige Schwankungen gleichen sich eher aus', 'Man zahlt automatisch weniger Steuern', 'Aktien werden mit der Zeit garantiert günstiger'], correct: 0, explain: 'Je länger der Zeitraum, desto eher gleichen sich kurzfristige Ausschläge aus.' },
    { q: 'Was unterscheidet Sparen von Investieren?', options: ['Kein Unterschied', 'Sparen ist risikofrei, Investieren trägt Risiko für höhere Renditechancen', 'Investieren ist immer sicherer'], correct: 1, explain: 'Investieren bedeutet, für die Chance auf höhere Rendite Risiko einzugehen.' },
  ],
  schwer: [
    { q: 'Was misst die Sharpe Ratio?', options: ['Rendite im Verhältnis zum eingegangenen Risiko', 'Die Dividendenrendite', 'Die Marktkapitalisierung'], correct: 0, explain: 'Die Sharpe Ratio zeigt, wie viel Rendite pro Risikoeinheit erzielt wurde.' },
    { q: 'Was ist ein Rebalancing?', options: ['Das Zurücksetzen des Depots auf die Ursprungsgewichtung', 'Der Verkauf aller Positionen', 'Eine Steuerstrategie'], correct: 0, explain: 'Rebalancing stellt die ursprünglich geplante Aufteilung des Depots wieder her.' },
    { q: 'Was zeigt das Kurs-Gewinn-Verhältnis (KGV)?', options: ['Verhältnis von Aktienkurs zu Gewinn je Aktie', 'Verhältnis von Umsatz zu Mitarbeitern', 'Verhältnis von Dividende zu Kurs'], correct: 0, explain: 'Das KGV setzt den Aktienkurs ins Verhältnis zum Gewinn je Aktie.' },
    { q: 'Was ist ein "Blue Chip"?', options: ['Eine besonders volatile Kleinstaktie', 'Eine etablierte, finanzstarke Standardaktie', 'Ein spezieller Anleihe-Typ'], correct: 1, explain: 'Blue Chips sind große, etablierte Unternehmen mit stabiler Marktstellung.' },
    { q: 'Was besagt die Effizienzmarkthypothese?', options: ['Märkte reagieren nie auf neue Informationen', 'Alle verfügbaren Informationen spiegeln sich bereits im Kurs wider', 'Nur institutionelle Anleger können den Markt schlagen'], correct: 1, explain: 'Sie besagt, dass Kurse verfügbare Informationen bereits einpreisen.' },
  ],
};

function loadLearnBest() {
  try {
    const saved = JSON.parse(localStorage.getItem(LEARN_BEST_KEY));
    if (saved) return saved;
  } catch (e) {}
  return {};
}

let learnBest = loadLearnBest();
let quiz = null;

function resetLearnView() {
  document.getElementById('learnQuiz').classList.add('hidden');
  document.getElementById('learnResult').classList.add('hidden');
  document.getElementById('learnLevels').classList.remove('hidden');
  renderLevels();
}

function renderLevels() {
  const list = document.getElementById('learnLevelList');
  list.innerHTML = '';
  LEVELS.forEach(level => {
    const total = QUIZ_DATA[level.id].length;
    const best = learnBest[level.id] || 0;
    const li = document.createElement('li');
    li.className = 'level-row';
    li.innerHTML = `
      <button class="menu-item level-btn" data-level="${level.id}">
        <span class="menu-icon">${level.icon}</span>
        <span class="menu-text">
          <span class="menu-label">${level.name}</span>
          <span class="menu-sub">${level.desc} · ${total} Fragen · ${level.points} Punkte/Antwort</span>
        </span>
        <span class="menu-arrow">${best > 0 ? `🏆 ${best}` : '→'}</span>
      </button>
    `;
    list.appendChild(li);
  });
  list.querySelectorAll('.level-btn').forEach(btn => {
    btn.addEventListener('click', () => startQuiz(btn.dataset.level));
  });
}

function startQuiz(levelId) {
  quiz = {
    levelId,
    questions: QUIZ_DATA[levelId],
    index: 0,
    score: 0,
    lives: QUIZ_START_LIVES,
    answered: false,
  };
  document.getElementById('learnLevels').classList.add('hidden');
  document.getElementById('learnResult').classList.add('hidden');
  document.getElementById('learnQuiz').classList.remove('hidden');
  renderQuestion();
}

function renderQuestion() {
  const level = LEVELS.find(l => l.id === quiz.levelId);
  const question = quiz.questions[quiz.index];
  quiz.answered = false;

  document.getElementById('quizProgress').textContent = `${quiz.index + 1}/${quiz.questions.length}`;
  document.getElementById('quizScore').textContent = quiz.score;
  document.getElementById('quizLives').textContent = '❤️'.repeat(quiz.lives) + '🖤'.repeat(QUIZ_START_LIVES - quiz.lives);
  document.getElementById('quizProgressBar').style.width = (quiz.index / quiz.questions.length * 100) + '%';

  document.getElementById('quizQuestion').textContent = question.q;
  document.getElementById('quizExplanation').classList.add('hidden');
  document.getElementById('quizNext').classList.add('hidden');

  const answersEl = document.getElementById('quizAnswers');
  answersEl.innerHTML = '';
  question.options.forEach((option, i) => {
    const li = document.createElement('li');
    const btn = document.createElement('button');
    btn.className = 'answer-btn';
    btn.textContent = option;
    btn.dataset.index = i;
    btn.addEventListener('click', () => selectAnswer(i));
    li.appendChild(btn);
    answersEl.appendChild(li);
  });
}

function selectAnswer(i) {
  if (quiz.answered) return;
  quiz.answered = true;

  const level = LEVELS.find(l => l.id === quiz.levelId);
  const question = quiz.questions[quiz.index];
  const correct = i === question.correct;

  document.querySelectorAll('#quizAnswers .answer-btn').forEach((btn, idx) => {
    btn.disabled = true;
    if (idx === question.correct) btn.classList.add('correct');
    else if (idx === i) btn.classList.add('wrong');
  });

  if (correct) {
    quiz.score += level.points;
    burstConfetti();
  } else {
    quiz.lives--;
  }

  document.getElementById('quizScore').textContent = quiz.score;
  bump(document.getElementById('quizScore'));
  document.getElementById('quizLives').textContent = '❤️'.repeat(Math.max(quiz.lives, 0)) + '🖤'.repeat(QUIZ_START_LIVES - Math.max(quiz.lives, 0));

  const explanationEl = document.getElementById('quizExplanation');
  explanationEl.textContent = (correct ? '✅ Richtig! ' : '❌ Leider falsch. ') + question.explain;
  explanationEl.classList.remove('hidden');
  explanationEl.classList.add(correct ? 'correct' : 'wrong');

  const nextBtn = document.getElementById('quizNext');
  const isLastQuestion = quiz.index >= quiz.questions.length - 1;
  const isGameOver = quiz.lives <= 0;
  nextBtn.textContent = (isLastQuestion || isGameOver) ? 'Ergebnis ansehen →' : 'Weiter →';
  nextBtn.classList.remove('hidden');
}

document.getElementById('quizNext').addEventListener('click', () => {
  const isLastQuestion = quiz.index >= quiz.questions.length - 1;
  const isGameOver = quiz.lives <= 0;
  if (isLastQuestion || isGameOver) {
    finishQuiz();
  } else {
    quiz.index++;
    document.getElementById('quizExplanation').classList.remove('correct', 'wrong');
    renderQuestion();
  }
});

function finishQuiz() {
  const level = LEVELS.find(l => l.id === quiz.levelId);
  const total = quiz.questions.length;
  const maxScore = total * level.points;
  const gameOver = quiz.lives <= 0;
  const perfect = quiz.score === maxScore;

  if (!learnBest[quiz.levelId] || quiz.score > learnBest[quiz.levelId]) {
    learnBest[quiz.levelId] = quiz.score;
    localStorage.setItem(LEARN_BEST_KEY, JSON.stringify(learnBest));
  }

  document.getElementById('learnQuiz').classList.add('hidden');
  document.getElementById('learnResult').classList.remove('hidden');

  document.getElementById('resultEmoji').textContent = gameOver ? '💔' : perfect ? '🏆' : '🎉';
  document.getElementById('resultTitle').textContent = gameOver ? 'Game Over' : perfect ? 'Perfekt!' : 'Geschafft!';
  document.getElementById('resultSummary').textContent =
    `${quiz.score} von ${maxScore} Punkten · Level "${level.name}"` +
    (gameOver ? ' — keine Leben mehr übrig. Versuch es nochmal!' : perfect ? ' — alle Fragen richtig beantwortet!' : '.');

  if (perfect) burstConfetti();
}

document.getElementById('resultRetry').addEventListener('click', () => startQuiz(quiz.levelId));
document.getElementById('resultBack').addEventListener('click', resetLearnView);

// --- PWA: Service Worker ---

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('sw.js').catch(() => {});
  });
}
