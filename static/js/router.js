// Hash-based SPA router.
window.Router = (function () {
  const container = () => document.getElementById('page-container');
  let current = '';

  const routes = [
    { re: /^\/?$/, handler: (c) => PageHome.render(c) },
    { re: /^\/search$/, handler: (c) => PageSearch.render(c) },
    { re: /^\/saved$/, handler: (c) => PageSaved.render(c) },
    { re: /^\/profile$/, handler: (c) => PageProfile.render(c) },
    { re: /^\/category\/(.+)$/, handler: (c, m) => PageCategory.render(c, m[1]) },
    { re: /^\/title\/(.+)$/, handler: (c, m) => PageDetail.render(c, m[1]) },
  ];

  function parse() {
    let h = location.hash.replace(/^#/, '');
    if (!h) h = '/';
    return h;
  }

  async function resolve() {
    Banner.stop();
    const path = parse();
    current = path;
    const c = container();
    for (const r of routes) {
      const m = path.match(r.re);
      if (m) {
        // native back button for sub-pages
        if (/^\/(title|category)\//.test(path)) TG.showBack(() => Router.back());
        else TG.hideBack();
        try { await r.handler(c, m); } catch (e) { console.error(e); }
        return;
      }
    }
    // fallback
    location.hash = '#/';
  }

  function go(path) {
    if (!path.startsWith('/')) path = '/' + path;
    if (('#' + path) === location.hash) { resolve(); return; }
    location.hash = '#' + path;
  }
  function back() {
    if (history.length > 1) history.back();
    else go('/');
  }
  function reload() { resolve(); }

  function start() {
    window.addEventListener('hashchange', resolve);
    resolve();
  }
  return { start, go, back, reload, current: () => current };
})();
