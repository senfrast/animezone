// Lightweight cache using Telegram CloudStorage when available, else localStorage.
window.Store = (function () {
  const cs = window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.CloudStorage
    ? window.Telegram.WebApp.CloudStorage : null;
  function set(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) {}
    if (cs) { try { cs.setItem(key, JSON.stringify(value)); } catch (e) {} }
  }
  function get(key, def) {
    try {
      const v = localStorage.getItem(key);
      return v ? JSON.parse(v) : def;
    } catch (e) { return def; }
  }
  return { set, get };
})();
