window.PageSearch = (function () {
  async function render(container) {
    Nav.setActive('search');
    const page = H.el('div', { class: 'page' });
    page.innerHTML =
      `<div class="search-wrap" style="margin-bottom:16px">
         <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3" stroke-linecap="round"/></svg>
         <input class="search-bar" id="search-input" placeholder="Search anime, movies, series…" autocomplete="off">
       </div>
       <div id="search-results"></div>`;
    container.innerHTML = '';
    container.appendChild(page);

    const input = page.querySelector('#search-input');
    const results = page.querySelector('#search-results');

    // trending suggestions
    try {
      const tr = await API.trendingSearches();
      if (tr.terms && tr.terms.length) {
        const box = H.el('div');
        box.innerHTML = '<div class="section-title">🔥 Popular</div>';
        const bar = H.el('div', { class: 'filter-bar' });
        tr.terms.slice(0, 8).forEach((term) => {
          const chip = H.el('div', { class: 'filter-chip' }, term);
          chip.addEventListener('click', () => { input.value = term; doSearch(term, results); });
          bar.appendChild(chip);
        });
        box.appendChild(bar);
        results.appendChild(box);
      }
    } catch (e) {}

    const run = H.debounce((q) => doSearch(q, results), 350);
    input.addEventListener('input', (e) => {
      const q = e.target.value.trim();
      if (q.length === 0) { results.innerHTML = ''; return; }
      results.innerHTML = Skeleton.grid(4);
      run(q);
    });
    setTimeout(() => input.focus(), 100);
  }

  async function doSearch(q, results) {
    if (!q) return;
    try {
      const data = await API.search(q);
      results.innerHTML = '';
      if (data.results.length) {
        results.appendChild(H.el('div', { class: 'subtitle', style: 'margin-bottom:10px' }, `${data.total} results for "${q}"`));
        results.appendChild(Card.row(data.results, 'grid'));
      } else {
        const empty = H.el('div', { class: 'empty-state' });
        empty.innerHTML = `<div class="empty-state-emoji">🔍</div>
          <div class="empty-state-title">No results</div>
          <div class="empty-state-subtitle">Can't find "${H.esc(q)}". Request it?</div>`;
        const btn = H.el('button', { class: 'join-button', style: 'max-width:220px' }, '📩 Request this title');
        btn.addEventListener('click', () => Modal.requestContent());
        empty.appendChild(btn);
        results.appendChild(empty);
      }
    } catch (e) {
      results.innerHTML = '<div class="empty-state"><div class="empty-state-title">Search failed</div></div>';
    }
  }
  return { render };
})();
