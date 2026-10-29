/**
 * Story Weaver — main.js
 * - Draft: live word/character counter with localStorage draft saving
 * - Like / Save / Follow: fetch API with CSRF token
 * - SVG Story Tree: generational layout with gold connecting lines
 * - Prompt picker: click "Use this prompt" → fill textarea
 * - Copy link button
 */

// ── CSRF helper ────────────────────────────────────────────────────────────
function getCsrf() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.content : '';
}

// ── Draft (word counter + localStorage) ────────────────────────────────────
class Draft {
  constructor(textarea) {
    this.ta = textarea;
    this.key = 'draft:' + (textarea.dataset.draft || 'default');
    this.counterEl = document.getElementById('word-counter');
    this.labelEl   = document.getElementById('counter-label');
    // Limits are in characters, matching the server-side validation
    this.MIN = 20;
    this.MAX = 5000;

    // Restore saved draft
    try {
      const saved = localStorage.getItem(this.key);
      if (saved && !this.ta.value.trim()) this.ta.value = saved;
    } catch (_) {}

    this.ta.addEventListener('input', () => this._update());
    this._update();
  }

  get text()         { return this.ta.value; }
  get chars()        { return this.text.trim().length; }
  get words()        { return this.text.trim() === '' ? 0 : this.text.trim().split(/\s+/).length; }
  get readingMinutes(){ return Math.max(1, Math.round(this.words / 200)); }
  get tooShort()     { return this.chars < this.MIN; }
  get tooLong()      { return this.chars > this.MAX; }

  get label() {
    if (this.tooShort) return `${this.chars} / ${this.MIN} characters minimum`;
    if (this.tooLong)  return `${this.chars.toLocaleString()} / ${this.MAX.toLocaleString()} characters — too long`;
    return `${this.chars.toLocaleString()} characters · ~${this.readingMinutes} min read`;
  }

  _update() {
    if (this.counterEl) this.counterEl.textContent = `${this.words} words`;
    if (this.labelEl) {
      this.labelEl.textContent = this.label;
      this.labelEl.className = this.tooShort ? 'counter-warn'
                             : this.tooLong  ? 'counter-over'
                             : 'counter-ok';
    }
    try { localStorage.setItem(this.key, this.ta.value); } catch (_) {}
  }
}

// ── JSON fetch helper ───────────────────────────────────────────────────────
async function apiFetch(url, method = 'POST') {
  const res = await fetch(url, {
    method,
    headers: {
      'X-CSRF-Token': getCsrf(),
      'X-Requested-With': 'XMLHttpRequest',
    },
    credentials: 'same-origin',
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ── Like button ─────────────────────────────────────────────────────────────
function initLikes() {
  document.querySelectorAll('.like-btn[data-story-id]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.dataset.storyId;
      try {
        const data = await apiFetch(`/api/story/${id}/like`);
        btn.classList.toggle('liked', data.liked);
        const countEl = btn.querySelector('.like-count');
        if (countEl) countEl.textContent = data.likes;
      } catch (e) {
        console.error('Like failed', e);
      }
    });
  });
}

// ── Save / bookmark button ──────────────────────────────────────────────────
function initSaves() {
  document.querySelectorAll('.save-btn[data-story-id]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.dataset.storyId;
      try {
        const data = await apiFetch(`/api/story/${id}/save`);
        btn.classList.toggle('saved', data.saved);
        const label = btn.querySelector('span');
        if (label) label.textContent = data.saved ? '★ Saved' : '☆ Save';
        else btn.textContent = data.saved ? '★ Remove' : '☆ Save';
      } catch (e) {
        console.error('Save failed', e);
      }
    });
  });
}

// ── Follow button ───────────────────────────────────────────────────────────
function initFollow() {
  document.querySelectorAll('.follow-btn[data-username]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const username = btn.dataset.username;
      try {
        const data = await apiFetch(`/api/user/${encodeURIComponent(username)}/follow`);
        btn.classList.toggle('following', data.following);
        btn.textContent = data.following ? 'Following' : 'Follow';
      } catch (e) {
        console.error('Follow failed', e);
      }
    });
  });
}

// ── Copy link button ────────────────────────────────────────────────────────
function initCopyLinks() {
  document.querySelectorAll('.copy-btn[data-copy]').forEach(btn => {
    btn.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(btn.dataset.copy);
        const orig = btn.textContent;
        btn.textContent = '✓ Copied';
        setTimeout(() => { btn.textContent = orig; }, 1800);
      } catch (_) {}
    });
  });
}

// ── Prompt picker ────────────────────────────────────────────────────────────
function initPrompts() {
  document.querySelectorAll('.use-prompt').forEach(btn => {
    btn.addEventListener('click', () => {
      const card = btn.closest('.prompt-card');
      const text = card?.dataset.prompt;
      const ta   = document.getElementById('text');
      if (ta && text) {
        ta.value = text + '\n\n';
        ta.focus();
        ta.dispatchEvent(new Event('input'));
      }
    });
  });
}

// ── SVG Story Tree ────────────────────────────────────────────────────────────
async function initTree() {
  const container = document.getElementById('tree-container');
  if (!container) return;

  const storyId  = container.dataset.storyId;
  const currentId = container.dataset.currentId;
  if (!storyId) return;

  let data;
  try {
    const res = await fetch(`/api/story/${storyId}/tree.json`, { credentials: 'same-origin' });
    if (!res.ok) throw new Error(res.status);
    data = await res.json();
  } catch (e) {
    container.innerHTML = '<p style="padding:2rem;color:var(--text-dim)">Could not load story tree.</p>';
    return;
  }

  const nodes = data.nodes;
  if (!nodes || nodes.length === 0) {
    container.innerHTML = '<p style="padding:2rem;color:var(--text-dim)">No passages to display.</p>';
    return;
  }

  // Group by depth
  const byDepth = {};
  for (const n of nodes) {
    (byDepth[n.depth] = byDepth[n.depth] || []).push(n);
  }
  const depths = Object.keys(byDepth).map(Number).sort((a, b) => a - b);

  const NODE_W  = 140;
  const NODE_H  = 56;
  const COL_W   = 180;
  const ROW_H   = 88;
  const PAD     = 32;

  // Assign x positions within each depth column (spread evenly)
  for (const d of depths) {
    const list = byDepth[d];
    list.forEach((n, i) => {
      n._x = PAD + d * COL_W;
      n._y = PAD + i * ROW_H;
    });
  }

  const maxDepth = depths[depths.length - 1];
  const maxNodesAtDepth = Math.max(...depths.map(d => byDepth[d].length));
  const svgW = PAD * 2 + maxDepth * COL_W + NODE_W;
  const svgH = PAD * 2 + maxNodesAtDepth * ROW_H;

  // Build id→node map
  const idMap = {};
  for (const n of nodes) idMap[n.id] = n;

  // Build SVG
  const NS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', `0 0 ${svgW} ${svgH}`);
  svg.setAttribute('width', svgW);
  svg.setAttribute('height', svgH);
  svg.style.fontFamily = 'EB Garamond, Georgia, serif';

  const kindColor = { opening: '#c9a84c', continuation: '#8ab4c8', ending: '#c88ab4' };

  // Draw lines first (behind nodes)
  for (const n of nodes) {
    if (!n.parent_id) continue;
    const parent = idMap[n.parent_id];
    if (!parent) continue;
    const x1 = parent._x + NODE_W;
    const y1 = parent._y + NODE_H / 2;
    const x2 = n._x;
    const y2 = n._y + NODE_H / 2;
    const mx = (x1 + x2) / 2;

    const path = document.createElementNS(NS, 'path');
    path.setAttribute('d', `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`);
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke', '#6b5a2e');
    path.setAttribute('stroke-width', '1.5');
    svg.appendChild(path);
  }

  // Draw nodes
  for (const n of nodes) {
    const isCurrent = n.id === currentId;
    const color = kindColor[n.kind] || '#8b7d6b';

    const g = document.createElementNS(NS, 'g');
    g.style.cursor = 'pointer';
    g.addEventListener('click', () => { window.location.href = n.url; });

    // Node rectangle
    const rect = document.createElementNS(NS, 'rect');
    rect.setAttribute('x', n._x);
    rect.setAttribute('y', n._y);
    rect.setAttribute('width', NODE_W);
    rect.setAttribute('height', NODE_H);
    rect.setAttribute('rx', '4');
    rect.setAttribute('fill', '#2a2520');
    rect.setAttribute('stroke', isCurrent ? '#e0c060' : color);
    rect.setAttribute('stroke-width', isCurrent ? '2' : '1');
    if (isCurrent) rect.setAttribute('filter', 'url(#glow)');
    g.appendChild(rect);

    // Author text
    const tAuthor = document.createElementNS(NS, 'text');
    tAuthor.setAttribute('x', n._x + 8);
    tAuthor.setAttribute('y', n._y + 16);
    tAuthor.setAttribute('fill', '#8b7d6b');
    tAuthor.setAttribute('font-size', '9');
    tAuthor.textContent = n.author || '';
    g.appendChild(tAuthor);

    // Excerpt text (truncated)
    const excerpt = (n.excerpt || '').slice(0, 36) + (n.excerpt && n.excerpt.length > 36 ? '…' : '');
    const tExcerpt = document.createElementNS(NS, 'text');
    tExcerpt.setAttribute('x', n._x + 8);
    tExcerpt.setAttribute('y', n._y + 30);
    tExcerpt.setAttribute('fill', '#c8bfa8');
    tExcerpt.setAttribute('font-size', '10');
    tExcerpt.setAttribute('font-style', 'italic');
    tExcerpt.textContent = excerpt;
    g.appendChild(tExcerpt);

    // Kind dot
    const dot = document.createElementNS(NS, 'circle');
    dot.setAttribute('cx', n._x + NODE_W - 10);
    dot.setAttribute('cy', n._y + 10);
    dot.setAttribute('r', '4');
    dot.setAttribute('fill', color);
    g.appendChild(dot);

    // Likes
    const tLikes = document.createElementNS(NS, 'text');
    tLikes.setAttribute('x', n._x + 8);
    tLikes.setAttribute('y', n._y + NODE_H - 8);
    tLikes.setAttribute('fill', '#8b7d6b');
    tLikes.setAttribute('font-size', '9');
    tLikes.textContent = `♥ ${n.likes || 0}`;
    g.appendChild(tLikes);

    // Tooltip
    const title = document.createElementNS(NS, 'title');
    title.textContent = `${n.kind} by ${n.author}\n${n.excerpt}`;
    g.appendChild(title);

    svg.appendChild(g);
  }

  // Glow filter for current node
  const defs = document.createElementNS(NS, 'defs');
  defs.innerHTML = `<filter id="glow"><feGaussianBlur stdDeviation="3" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>`;
  svg.prepend(defs);

  container.innerHTML = '';
  container.appendChild(svg);
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Word counter / draft
  const ta = document.getElementById('text');
  if (ta) new Draft(ta);

  initLikes();
  initSaves();
  initFollow();
  initCopyLinks();
  initPrompts();
  initTree();

  // Clear draft on successful form submit
  document.querySelectorAll('form').forEach(form => {
    form.addEventListener('submit', () => {
      const ta = form.querySelector('textarea[data-draft]');
      if (ta) {
        try { localStorage.removeItem('draft:' + ta.dataset.draft); } catch (_) {}
      }
    });
  });
});
