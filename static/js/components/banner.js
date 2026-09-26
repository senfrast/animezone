window.Banner = (function () {
  let timer = null;
  function render(featured) {
    if (timer) { clearInterval(timer); timer = null; }
    const wrap = H.el('div', { class: 'section' });
    const container = H.el('div', { class: 'banner-container' });
    featured.forEach((t) => {
      const slide = H.el('div', { class: 'banner-slide', dataset: { slug: t.slug } });
      slide.innerHTML =
        `<img class="banner-image" src="${t.image_url}" onerror="this.src='/assets/placeholder.svg'">
         <div class="banner-overlay">
           <div class="banner-cat">${t.category_emoji || ''} ${H.esc(t.category_name || 'Featured')}</div>
           <div class="banner-title">${H.esc(t.title)}</div>
           <div class="banner-meta">★ ${Number(t.rating || 0).toFixed(1)} · ${H.esc(t.language || '')} · ${H.esc(t.status || '')}</div>
         </div>`;
      slide.addEventListener('click', () => { Haptic.impact('light'); Router.go('/title/' + t.slug); });
      container.appendChild(slide);
    });
    const dots = H.el('div', { class: 'banner-dots' });
    featured.forEach((_, i) => {
      const d = H.el('div', { class: 'banner-dot' + (i === 0 ? ' active' : '') });
      dots.appendChild(d);
    });
    wrap.appendChild(container);
    wrap.appendChild(dots);

    // sync dots on scroll
    container.addEventListener('scroll', H.throttle(() => {
      const idx = Math.round(container.scrollLeft / container.clientWidth);
      dots.querySelectorAll('.banner-dot').forEach((d, i) => d.classList.toggle('active', i === idx));
    }, 100));

    // auto swipe
    if (featured.length > 1) {
      let idx = 0;
      timer = setInterval(() => {
        idx = (idx + 1) % featured.length;
        container.scrollTo({ left: idx * container.clientWidth, behavior: 'smooth' });
      }, 4000);
    }
    return wrap;
  }
  function stop() { if (timer) { clearInterval(timer); timer = null; } }
  return { render, stop };
})();
