window.Card = (function () {
  function poster(t) {
    const card = H.el('div', { class: 'title-card', dataset: { slug: t.slug } });
    const badge = t.category_emoji ? `<div class="title-card-badge">${t.category_emoji}</div>` : '';
    const nsfw = t.is_nsfw ? `<div class="title-card-nsfw">18+</div>` : '';
    card.innerHTML =
      `<div class="title-card-image-wrap">
         <img class="card-image-bg" loading="lazy" aria-hidden="true" src="${t.image_url}" onerror="this.remove()">
         <img class="title-card-image img-blur" loading="lazy" src="${t.image_url}" onload="this.classList.add('img-clear')" onerror="this.src='/assets/placeholder.svg'">
         ${badge}${nsfw}
       </div>
       <div class="title-card-title">${H.esc(t.title)}</div>
       <div class="title-card-meta">${H.esc(t.language || '')} · ${H.esc(t.status || '')}</div>
       ${t.rating ? `<div class="title-card-rating">★ ${Number(t.rating).toFixed(1)}</div>` : ''}`;
    card.addEventListener('click', () => { Haptic.impact('light'); Router.go('/title/' + t.slug); });
    return card;
  }
  function grid(t) {
    const card = H.el('div', { class: 'grid-card', dataset: { slug: t.slug } });
    const nsfw = t.is_nsfw ? `<div class="title-card-nsfw">18+</div>` : '';
    card.innerHTML =
      `<div class="title-card-image-wrap">
         <img class="card-image-bg" loading="lazy" aria-hidden="true" src="${t.image_url}" onerror="this.remove()">
         <img class="grid-card-image img-blur" loading="lazy" src="${t.image_url}" onload="this.classList.add('img-clear')" onerror="this.src='/assets/placeholder.svg'">
         ${nsfw}
       </div>
       <div class="title-card-title">${H.esc(t.title)}</div>
       <div class="title-card-meta">${H.esc(t.language || '')} · ★ ${Number(t.rating || 0).toFixed(1)}</div>`;
    card.addEventListener('click', () => { Haptic.impact('light'); Router.go('/title/' + t.slug); });
    return card;
  }
  function row(titles, mode = 'poster') {
    const wrap = H.el('div', { class: mode === 'grid' ? 'grid' : 'horizontal-scroll' });
    titles.forEach((t, i) => {
      const c = mode === 'grid' ? grid(t) : poster(t);
      c.classList.add('card-enter');
      c.style.animationDelay = Math.min(i * 40, 400) + 'ms';
      wrap.appendChild(c);
    });
    return wrap;
  }
  return { poster, grid, row };
})();
