window.PageCategory = (function () {
  const state = {};

  async function render(container, slug) {
    Nav.setActive('home');
    state.slug = slug;
    state.params = { page: 1, sort: 'popular', language: 'all', genre: 'all', status: 'all' };
    container.innerHTML = '<div class="page">' + Skeleton.grid() + '</div>';
    await load(container, true);
  }

  async function load(container, full) {
    let data;
    try {
      data = await API.category(state.slug, state.params);
    } catch (e) {
      if (e.status === 403) { Toast.error('18+ content is disabled'); Router.go('/'); return; }
      container.innerHTML = '<div class="page"><div class="empty-state"><div class="empty-state-emoji">😕</div><div class="empty-state-title">Not found</div></div></div>';
      return;
    }
    state.data = data;

    const page = H.el('div', { class: 'page' });
    const header = H.el('div', { class: 'page-header' });
    header.innerHTML = `<div class="back-btn"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6" stroke-linecap="round" stroke-linejoin="round"/></svg></div>
      <h1>${data.category.emoji} ${H.esc(data.category.name)}</h1>`;
    header.querySelector('.back-btn').addEventListener('click', () => Router.back());
    page.appendChild(header);

    // sort chips
    page.appendChild(Filter.chipBar([
      { label: '🔥 Popular', value: 'popular' },
      { label: '🆕 Newest', value: 'newest' },
      { label: '🔤 A-Z', value: 'alphabetical' },
      { label: '⭐ Rating', value: 'rating' },
    ], state.params.sort, (v) => { state.params.sort = v; state.params.page = 1; refresh(container); }));

    // language chips
    const langs = [{ label: 'All Languages', value: 'all' }].concat(
      (data.filters.languages || []).map((l) => ({ label: l, value: l })));
    page.appendChild(Filter.chipBar(langs, state.params.language, (v) => {
      state.params.language = v; state.params.page = 1; refresh(container);
    }));

    // genre chips
    const genres = [{ label: 'All Genres', value: 'all' }].concat(
      (data.filters.genres || []).map((g) => ({ label: g.name + ' (' + g.count + ')', value: g.slug })));
    if (genres.length > 1) {
      page.appendChild(Filter.chipBar(genres, state.params.genre, (v) => {
        state.params.genre = v; state.params.page = 1; refresh(container);
      }));
    }

    const count = H.el('div', { class: 'subtitle', style: 'margin:8px 0' }, `${data.total} titles`);
    page.appendChild(count);

    if (data.titles.length) {
      page.appendChild(Card.row(data.titles, 'grid'));
      // pagination
      if (data.total_pages > 1) {
        const pager = H.el('div', { style: 'display:flex;gap:10px;justify-content:center;margin:18px 0' });
        if (data.page > 1) {
          const prev = H.el('button', { class: 'filter-chip' }, '⬅️ Prev');
          prev.addEventListener('click', () => { state.params.page--; refresh(container); });
          pager.appendChild(prev);
        }
        pager.appendChild(H.el('div', { class: 'filter-chip active' }, `${data.page} / ${data.total_pages}`));
        if (data.page < data.total_pages) {
          const next = H.el('button', { class: 'filter-chip' }, 'Next ➡️');
          next.addEventListener('click', () => { state.params.page++; refresh(container); });
          pager.appendChild(next);
        }
        page.appendChild(pager);
      }
    } else {
      page.appendChild(H.el('div', { class: 'empty-state', html:
        `<div class="empty-state-emoji">🔍</div><div class="empty-state-title">No titles</div>
         <div class="empty-state-subtitle">Try different filters.</div>` }));
    }

    container.innerHTML = '';
    container.appendChild(page);
    window.scrollTo(0, 0);
  }

  async function refresh(container) { await load(container, false); }

  return { render };
})();
