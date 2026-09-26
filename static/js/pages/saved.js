window.PageSaved = (function () {
  async function render(container) {
    Nav.setActive('saved');
    container.innerHTML = '<div class="page">' + Skeleton.grid() + '</div>';
    let data;
    try {
      data = await API.bookmarks();
    } catch (e) {
      container.innerHTML = '<div class="page"><div class="empty-state"><div class="empty-state-title">Failed to load</div></div></div>';
      return;
    }
    const page = H.el('div', { class: 'page' });
    page.innerHTML = '<div class="section-title" style="margin-bottom:16px">🔖 Saved Titles</div>';
    if (data.titles && data.titles.length) {
      page.appendChild(Card.row(data.titles, 'grid'));
    } else {
      const empty = H.el('div', { class: 'empty-state' });
      empty.innerHTML = `<div class="empty-state-emoji">🔖</div>
        <div class="empty-state-title">No saved titles</div>
        <div class="empty-state-subtitle">Tap the bookmark icon on any title to save it here.</div>`;
      const btn = H.el('button', { class: 'join-button', style: 'max-width:200px' }, 'Browse titles');
      btn.addEventListener('click', () => Router.go('/'));
      empty.appendChild(btn);
      page.appendChild(empty);
    }
    container.innerHTML = '';
    container.appendChild(page);
  }
  return { render };
})();
