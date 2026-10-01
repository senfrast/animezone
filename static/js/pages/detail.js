window.PageDetail = (function () {
  async function render(container, slug) {
    container.innerHTML = '<div class="page">' + Skeleton.banner() + '</div>';
    let data;
    try {
      data = await API.title(slug);
    } catch (e) {
      if (e.status === 403) { Toast.error('18+ content is disabled'); Router.go('/'); return; }
      container.innerHTML = '<div class="page"><div class="empty-state"><div class="empty-state-emoji">😕</div><div class="empty-state-title">Title not found</div></div></div>';
      return;
    }
    const t = data.title;
    // track view
    API.click(t.title_id, 'view').catch(() => {});

    const page = H.el('div', { class: 'page slide-in-right' });

    // hero
    const hero = H.el('div', { class: 'detail-hero' });
    hero.innerHTML =
      `<div class="detail-hero-back"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6" stroke-linecap="round" stroke-linejoin="round"/></svg></div>
       <img class="detail-hero-bg" src="${t.image_url}" aria-hidden="true" onerror="this.remove()">
       <img class="detail-hero-image" src="${t.image_url}" onerror="this.src='/assets/placeholder.svg'">
       <div class="detail-hero-overlay"></div>`;
    hero.querySelector('.detail-hero-back').addEventListener('click', () => Router.back());
    // show the WHOLE cover (no cropping): match the hero box to the image's own
    // shape, clamped so ultra-tall/ultra-wide art still looks right.
    (function fitHero() {
      const img = hero.querySelector('.detail-hero-image');
      const apply = () => {
        const r = img.naturalWidth / img.naturalHeight;
        if (!r || !isFinite(r)) return;
        hero.style.aspectRatio = String(Math.min(Math.max(r, 0.78), 2.1));
      };
      if (img.complete && img.naturalWidth) apply();
      img.addEventListener('load', apply);
    })();
    page.appendChild(hero);

    // title + meta
    page.appendChild(H.el('div', { class: 'detail-title' }, t.title));
    const meta = H.el('div', { class: 'detail-meta' });
    meta.innerHTML =
      `<div class="detail-meta-item">${t.category_emoji || ''} ${H.esc(t.category_name || '')}</div>
       <div class="detail-meta-item">⭐ ${Number(t.rating || 0).toFixed(1)} (${t.rating_count || 0})</div>
       <div class="detail-meta-item">🌐 ${H.esc(t.language || '')}</div>
       <div class="detail-meta-item">📊 ${H.esc(t.status || '')}</div>
       ${H.unitLabel(t.category_name, t.episode_count) ? `<div class="detail-meta-item">${H.unitLabel(t.category_name, t.episode_count)}</div>` : ''}
       ${t.is_nsfw ? '<div class="detail-meta-item" style="color:var(--error)">🔞 18+</div>' : ''}`;
    page.appendChild(meta);

    // genres
    if (data.genres && data.genres.length) {
      const g = H.el('div', { style: 'margin-top:12px' });
      data.genres.forEach((x) => g.appendChild(H.el('span', { class: 'pill' }, `${x.emoji || ''} ${x.name}`)));
      page.appendChild(g);
    }

    // join button
    const join = H.el('button', { class: 'join-button', style: 'margin-top:16px' });
    join.innerHTML = '<span>🚀 Join Channel</span>';
    join.addEventListener('click', () => {
      Haptic.impact('medium');
      API.click(t.title_id, 'join').catch(() => {});
      TG.openTelegramLink(t.channel_link);
    });
    page.appendChild(join);

    // action row: save + share
    const actions = H.el('div', { class: 'action-row' });
    const saveBtn = H.el('button', { class: 'icon-button' + (data.is_bookmarked ? ' active' : '') });
    saveBtn.innerHTML = bookmarkIcon(data.is_bookmarked) + '<span>' + (data.is_bookmarked ? 'Saved' : 'Save') + '</span>';
    saveBtn.addEventListener('click', async () => {
      Haptic.impact('light');
      try {
        const r = await API.toggleBookmark(t.title_id);
        if (r.error === 'limit') { Toast.error('Bookmark limit reached'); return; }
        saveBtn.classList.toggle('active', r.bookmarked);
        saveBtn.innerHTML = bookmarkIcon(r.bookmarked) + '<span>' + (r.bookmarked ? 'Saved' : 'Save') + '</span>';
        Toast.success(r.bookmarked ? 'Saved to bookmarks' : 'Removed');
        API.invalidate();
      } catch (e) { Toast.error('Failed'); }
    });
    const shareBtn = H.el('button', { class: 'icon-button' });
    shareBtn.innerHTML = shareIcon() + '<span>Share</span>';
    shareBtn.addEventListener('click', () => {
      Haptic.impact('light');
      API.click(t.title_id, 'share').catch(() => {});
      const link = 'https://t.me/' + App.state.botUsername + '?start=title_' + t.slug;
      TG.share(link, t.title + ' on AnimeZone');
    });
    actions.appendChild(saveBtn);
    actions.appendChild(shareBtn);
    page.appendChild(actions);

    // description
    if (t.description) {
      const sec = H.el('div', { class: 'detail-section' });
      sec.innerHTML = `<div class="detail-section-title">Synopsis</div><div class="detail-desc">${H.esc(t.description)}</div>`;
      page.appendChild(sec);
    }

    // rating
    const rsec = H.el('div', { class: 'detail-section' });
    rsec.innerHTML = '<div class="detail-section-title">Rate this title</div>';
    const stars = H.el('div', { class: 'rating-stars' });
    for (let i = 1; i <= 5; i++) {
      const s = H.el('div', { html: starSvg(), dataset: { v: i } });
      if (data.user_rating && i <= data.user_rating) s.firstChild.classList.add('filled');
      s.addEventListener('click', async () => {
        Haptic.impact('light');
        try {
          const r = await API.rate(t.title_id, i);
          stars.querySelectorAll('svg').forEach((sv, idx) => sv.classList.toggle('filled', idx < i));
          Toast.success('Rated ' + i + '★ · avg ' + r.new_rating);
        } catch (e) { Toast.error('Failed'); }
      });
      stars.appendChild(s);
    }
    rsec.appendChild(stars);
    page.appendChild(rsec);

    // related
    if (data.related && data.related.length) {
      const sec = H.el('div', { class: 'section', style: 'margin-top:20px' });
      sec.innerHTML = '<div class="section-title">Related</div>';
      sec.appendChild(Card.row(data.related, 'poster'));
      page.appendChild(sec);
    }

    container.innerHTML = '';
    container.appendChild(page);
    window.scrollTo(0, 0);
  }

  function bookmarkIcon(active) {
    return `<svg viewBox="0 0 24 24" fill="${active ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2"><path d="M6 3h12a1 1 0 0 1 1 1v17l-7-4-7 4V4a1 1 0 0 1 1-1z" stroke-linejoin="round"/></svg>`;
  }
  function shareIcon() {
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="m8.6 13.5 6.8 4M15.4 6.5l-6.8 4" stroke-linecap="round"/></svg>`;
  }
  function starSvg() {
    return `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.9 6.3 6.9.6-5.2 4.5 1.6 6.8L12 17.3 5.8 20.8l1.6-6.8L2.2 8.9l6.9-.6z"/></svg>`;
  }
  return { render };
})();
