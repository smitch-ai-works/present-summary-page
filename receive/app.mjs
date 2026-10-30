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

async function boot() {
  const request = parseRequest(location.search);
  const ticket = document.getElementById('ticket');
  const title = document.getElementById('bonus-title');
  const searchExample = document.getElementById('search-title');
  const help = document.getElementById('bonus-help');
  const copy = document.getElementById('copy-name');
  const status = document.getElementById('copy-status');
  let bonus;
  try { bonus = resolveBonus(await loadCatalog(), request); } catch { bonus = null; }
  ticket.setAttribute('aria-busy', 'false');
  if (!bonus) {
    title.textContent = 'InstagramのDMにある特典の案内をご確認ください。';
    searchExample.textContent = 'DMにある特典名を貼り付けます';
    help.textContent = '参加後は、DMにある特典名で一覧を検索してください。';
    copy.hidden = true;
    status.hidden = true;
    return;
  }
  const searchTitle = plainTitle(bonus.title);
  title.textContent = searchTitle;
  searchExample.textContent = searchTitle;
  help.textContent = '特典名をコピーして、参加後の特典一覧で検索してください。';
  document.title = `「${searchTitle}」受け取り方｜すみっち`;
  copy.disabled = false;
  copy.textContent = '特典名をコピーする';
  copy.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(searchTitle);
      copy.textContent = 'コピーしました';
      status.textContent = '検索欄に特典名を貼り付けてください。';
    } catch {
      status.textContent = `コピーできない場合は、検索欄に「${searchTitle}」と入力してください。`;
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
