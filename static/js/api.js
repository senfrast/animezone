// API communication + in-memory caching layer.
window.API = (function () {
  const base = '/api/v1';
  const cache = new Map();

  function headers() {
    return {
      'Content-Type': 'application/json',
      'X-Telegram-Init-Data': TG.initData(),
    };
  }

  async function get(path, { ttl = 0, key = null } = {}) {
    const ck = key || path;
    if (ttl > 0 && cache.has(ck)) {
      const c = cache.get(ck);
      if (Date.now() - c.at < ttl) return c.data;
    }
    const res = await fetch(base + path, { headers: headers() });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw Object.assign(new Error(err.error || 'request_failed'), { status: res.status, body: err });
    }
    const data = await res.json();
    if (ttl > 0) cache.set(ck, { at: Date.now(), data });
    return data;
  }

  async function post(path, body) {
    const res = await fetch(base + path, {
      method: 'POST', headers: headers(), body: JSON.stringify(body || {}),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw Object.assign(new Error(err.error || 'request_failed'), { status: res.status, body: err });
    }
    return res.json();
  }

  function invalidate(prefix) {
    for (const k of cache.keys()) if (!prefix || k.startsWith(prefix)) cache.delete(k);
  }

  return {
    init: () => get('/init'),
    home: () => get('/home', { ttl: 60000, key: 'home' }),
    category: (slug, params) => {
      const qs = new URLSearchParams(params || {}).toString();
      return get('/category/' + slug + (qs ? '?' + qs : ''));
    },
    title: (slug) => get('/title/' + slug),
    search: (q) => get('/search?q=' + encodeURIComponent(q)),
    bookmarks: () => get('/bookmarks'),
    toggleBookmark: (title_id) => post('/bookmark', { title_id }),
    click: (title_id, event_type) => post('/click', { title_id, event_type }),
    rate: (title_id, rating) => post('/rate', { title_id, rating }),
    request: (title, category) => post('/request', { title, category }),
    toggleNsfw: (show_nsfw) => post('/toggle-nsfw', { show_nsfw }),
    trendingSearches: () => get('/trending-searches', { ttl: 300000, key: 'trends' }),
    invalidate,
  };
})();
