// Generic helpers: debounce, throttle, formatters, DOM
window.H = (function () {
  function debounce(fn, wait) {
    let t;
    return function (...args) {
      clearTimeout(t);
      t = setTimeout(() => fn.apply(this, args), wait);
    };
  }
  function throttle(fn, limit) {
    let inThrottle;
    return function (...args) {
      if (!inThrottle) {
        fn.apply(this, args);
        inThrottle = true;
        setTimeout(() => (inThrottle = false), limit);
      }
    };
  }
  function humanInt(n) {
    n = Number(n) || 0;
    if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
    return String(n);
  }
  function el(tag, props = {}, children = []) {
    const e = document.createElement(tag);
    for (const k in props) {
      if (k === 'class') e.className = props[k];
      else if (k === 'html') e.innerHTML = props[k];
      else if (k.startsWith('on') && typeof props[k] === 'function')
        e.addEventListener(k.slice(2).toLowerCase(), props[k]);
      else if (k === 'dataset') Object.assign(e.dataset, props[k]);
      else e.setAttribute(k, props[k]);
    }
    (Array.isArray(children) ? children : [children]).forEach((c) => {
      if (c == null) return;
      e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    });
    return e;
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, (m) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[m]));
  }
  function stars(rating) {
    const r = Math.round(Number(rating) || 0);
    return '★'.repeat(r) + '☆'.repeat(5 - r);
  }
  function isMovieCategory(name) {
    const n = String(name || '').toLowerCase();
    return n.includes('movie') || n.includes('film');
  }
  // Films show "Parts"/"Full Movie"; series show "Episodes".
  function unitLabel(categoryName, count) {
    const n = Number(count) || 0;
    if (isMovieCategory(categoryName)) return n > 1 ? `🧩 ${n} Parts` : '🎬 Full Movie';
    return n > 0 ? `📺 ${n} Episodes` : '';
  }
  return { debounce, throttle, humanInt, el, esc, stars, isMovieCategory, unitLabel };
})();
