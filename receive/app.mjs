const HUB = 'https://smitch-ai-works.github.io/present-summary-page/';

export function parseRequest(search) {
  const params = new URLSearchParams(search);
  const raw = params.get('no')?.normalize('NFKC') ?? '';
  const key = params.get('key') ?? '';
  if (params.getAll('no').length > 1 || params.getAll('key').length > 1) return {invalid: true};
  if (raw && !/^[0-9]{1,4}$/.test(raw)) return {invalid: true};
  if (key && !/^[a-z0-9][a-z0-9-]{0,99}$/.test(key)) return {invalid: true};
  return {no: Number(raw) || null, key};
}

export function visibleBonuses(doc, now = Date.now()) {
  return doc.bonuses.filter(item => item.status === 'live' ||
    (item.status === 'scheduled' && Number.isFinite(Date.parse(item.publish_at)) && Date.parse(item.publish_at) <= now))
    .map((item, index) => ({...item, no: index + 1}));
}

export function resolveBonus(doc, request, now) {
  if (request.invalid) return null;
  const index = buildPublicNumberIndex(doc, now);
  return request.key ? index.byKey.get(request.key) ?? null : index.byNumber.get(request.no) ?? null;
}

// 特典一覧と同じ公開データから逆引きを作る。別の番号台帳を手入力で維持しない。
export function buildPublicNumberIndex(doc, now) {
  const visible = visibleBonuses(doc, now);
  return {
    byNumber: new Map(visible.map(item => [item.no, item])),
    byKey: new Map(visible.map(item => [item.slug, item]))
  };
}

export function plainTitle(value) {
  return String(value ?? '').replace(/<br\s*\/?\s*>/gi, ' ').replace(/<[^>]*>/g, '').trim();
}

async function loadCatalog() {
  const response = await fetch(`${HUB}bonuses.json`, {cache: 'no-store', signal: AbortSignal.timeout(4500)});
  if (!response.ok) throw new Error('catalog unavailable');
  const doc = await response.json();
  if (!Array.isArray(doc.bonuses)) throw new Error('invalid catalog');
  return doc;
}

function createGuidedReceipt() {
  const guide = document.getElementById('receipt-guide');
  const closing = document.getElementById('receipt-closing');
  if (!guide || !closing) return {start() {}};
  const steps = [...guide.querySelectorAll('.guide-step')];
  const progress = document.getElementById('guide-progress');
  const tail = document.getElementById('flow-tail');
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let revealed = 0;
  let started = false;
  let finished = false;
  let intentUntil = 0;
  let previousY = window.scrollY;
  let checking = false;

  function revealNext() {
    if (!started || finished) return;
    intentUntil = 0;
    if (revealed < steps.length) {
      const step = steps[revealed++];
      step.hidden = false;
      step.classList.add('is-entering');
      progress.textContent = `手順 ${revealed} / ${steps.length}`;
    } else {
      finished = true;
      closing.hidden = false;
      closing.classList.add('is-entering');
      tail.hidden = true;
      progress.textContent = '受け取りへ';
    }
  }

  // 自動スクロールやレイアウト変化だけでは、次の手順を開かない。
  function markIntent(event) {
    if (!event.isTrusted || !started || finished) return;
    if (event.type === 'wheel' && event.deltaY <= 0) return;
    if (event.type === 'keydown' && !['ArrowDown', 'PageDown', 'End', ' '].includes(event.key)) return;
    intentUntil = performance.now() + 1500;
  }
  window.addEventListener('wheel', markIntent, {passive: true});
  window.addEventListener('touchmove', markIntent, {passive: true});
  window.addEventListener('pointerdown', markIntent, {passive: true});
  window.addEventListener('keydown', markIntent);
  window.addEventListener('scroll', () => {
    if (checking) return;
    checking = true;
    requestAnimationFrame(() => {
      checking = false;
      const currentY = window.scrollY;
      const downward = currentY > previousY + 1;
      previousY = currentY;
      if (!started || finished || !downward || performance.now() > intentUntil) return;
      const marker = steps[revealed - 1]?.querySelector('[data-step-end]');
      if (marker && marker.getBoundingClientRect().bottom <= window.innerHeight - 28) revealNext();
    });
  }, {passive: true});

  steps.forEach((step, index) => {
    step.querySelector('[data-next]').addEventListener('click', () => {
      if (revealed !== index + 1 || finished) return;
      revealNext();
      const next = finished ? closing : steps[revealed - 1];
      next.scrollIntoView({behavior: reducedMotion.matches ? 'instant' : 'smooth', block: 'start'});
      const heading = next.querySelector('h2, h3');
      heading.setAttribute('tabindex', '-1');
      heading.focus({preventScroll: true});
    });
  });

  return {start() {
    if (started) return;
    started = true;
    intentUntil = 0;
    guide.hidden = false;
    revealNext();
    guide.scrollIntoView({behavior: reducedMotion.matches ? 'instant' : 'smooth', block: 'start'});
    document.getElementById('steps-heading').focus({preventScroll: true});
  }};
}

async function boot() {
  const request = parseRequest(location.search);
  const ticket = document.getElementById('ticket');
  const title = document.getElementById('bonus-title');
  const searchExample = document.getElementById('search-title');
  const help = document.getElementById('bonus-help');
  const copy = document.getElementById('copy-name');
  const status = document.getElementById('copy-status');
  const manualNext = document.getElementById('manual-next');
  const receipt = createGuidedReceipt();
  manualNext?.addEventListener('click', () => {
    manualNext.hidden = true;
    status.textContent = '特典名は、最後の検索欄に貼り付けます。';
    receipt.start();
  });
  let bonus;
  try { bonus = resolveBonus(await loadCatalog(), request); } catch { bonus = null; }
  ticket.setAttribute('aria-busy', 'false');
  if (!bonus) {
    title.textContent = 'InstagramのDMにある特典の案内をご確認ください。';
    searchExample.textContent = 'DMにある特典名を貼り付けます';
    help.textContent = 'DMにある特典名を控えてから、次へ進んでください。';
    copy.disabled = false;
    copy.textContent = 'DMの特典名を確認して進む';
    copy.addEventListener('click', () => receipt.start());
    return;
  }
  const searchTitle = plainTitle(bonus.title);
  title.textContent = searchTitle;
  searchExample.textContent = searchTitle;
  help.textContent = 'コピーすると、受け取り方が表示されます。';
  document.title = `「${searchTitle}」受け取り方｜すみっち`;
  copy.disabled = false;
  copy.textContent = '特典名をコピーして進む ↓';
  copy.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(searchTitle);
      copy.textContent = 'コピーしました';
      status.textContent = '特典名をコピーしました。次は受け取り方です。';
      if (manualNext) manualNext.hidden = true;
      receipt.start();
    } catch {
      status.textContent = '特典名を長押し・選択してコピーし、下の「コピーできたら次へ」を押してください。';
      if (manualNext) manualNext.hidden = false;
    }
  });
  if (/^assets\/[a-zA-Z0-9_./-]+\.(jpg|jpeg|png|webp)$/.test(bonus.image ?? '')) {
    const picture = document.getElementById('bonus-image');
    picture.addEventListener('error', () => {picture.hidden = true;});
    picture.src = new URL(bonus.image, HUB).href;
    picture.alt = `「${plainTitle(bonus.title)}」の特典画像`;
    picture.hidden = false;
  }
}

if (typeof document !== 'undefined') boot();
