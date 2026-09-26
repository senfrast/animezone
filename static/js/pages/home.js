window.PageHome = (function () {
  async function render(container) {
    Nav.setActive('home');
    container.innerHTML = Skeleton.home();
    let data;
    try {
      data = await API.home();
    } catch (e) {
      container.innerHTML = errorState();
      return;
    }
    const page = H.el('div', { class: 'page' });

    // top bar
    const name = (App.state.user && App.state.user.first_name) || 'there';
    const top = H.el('div', { class: 'top-bar' });
    top.innerHTML = `<div><div class="greeting">Hey <span>${H.esc(name)}</span> 👋</div>
      <div class="subtitle">${H.esc((App.state.config && App.state.config.app_tagline) || 'Your Anime Universe')}</div></div>
      <div style="font-size:26px">🎌</div>`;
    page.appendChild(top);

    // featured banner
    if (data.featured && data.featured.length) {
      page.appendChild(Banner.render(data.featured));
    }

    // category icons
    if (App.state.categories && App.state.categories.length) {
      const sec = H.el('div', { class: 'section' });
      sec.innerHTML = '<div class="section-title">📂 Categories</div>';
      const grid = H.el('div', { class: 'category-icon-grid' });
      App.state.categories.forEach((c) => {
        const item = H.el('div', { class: 'category-icon' });
        item.innerHTML = `<div class="category-icon-circle">${c.emoji}</div>
          <div class="category-icon-label">${H.esc(c.name)}</div>
          <div class="category-icon-count">${c.title_count} titles</div>`;
        item.addEventListener('click', () => { Haptic.impact('light'); Router.go('/category/' + c.slug); });
        grid.appendChild(item);
      });
      sec.appendChild(grid);
      page.appendChild(sec);
    }

    page.appendChild(section('🔥 Trending Now', data.trending));
    page.appendChild(section('🆕 Recently Added', data.recently_added));
    page.appendChild(section('⭐ Most Popular', data.popular));

    if (isEmptyEverywhere(data)) {
      page.appendChild(emptyCatalog());
    }

    container.innerHTML = '';
    container.appendChild(page);
  }

  function section(title, titles) {
    const sec = H.el('div', { class: 'section' });
    if (!titles || !titles.length) { sec.style.display = 'none'; return sec; }
    sec.innerHTML = `<div class="section-title">${title}</div>`;
    sec.appendChild(Card.row(titles, 'poster'));
    return sec;
  }

  function isEmptyEverywhere(d) {
    return !(d.featured && d.featured.length) && !(d.trending && d.trending.length) &&
      !(d.recently_added && d.recently_added.length) && !(d.popular && d.popular.length);
  }

  function emptyCatalog() {
    return H.el('div', { class: 'empty-state', html:
      `<div class="empty-state-emoji">🎬</div>
       <div class="empty-state-title">No titles yet</div>
       <div class="empty-state-subtitle">The admin hasn't added content yet.<br>Check back soon!</div>` });
  }

  function errorState() {
    return `<div class="page"><div class="empty-state">
      <div class="empty-state-emoji">😕</div>
      <div class="empty-state-title">Couldn't load</div>
      <div class="empty-state-subtitle">Please try again in a moment.</div>
      <button class="join-button" style="max-width:200px" onclick="Router.reload()">Retry</button>
      </div></div>`;
  }

  return { render };
})();
