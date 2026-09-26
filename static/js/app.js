// Main app controller + state management.
window.App = (function () {
  const state = {
    user: null,
    config: null,
    categories: [],
    bookmarkIds: [],
    botUsername: 'YC_Anime_Zone_bot',
  };

  async function reloadInit() {
    try {
      const data = await API.init();
      state.user = data.user;
      state.config = data.config;
      state.categories = data.categories;
      state.bookmarkIds = data.bookmark_ids || [];
    } catch (e) {
      console.error('init failed', e);
    }
  }

  async function boot() {
    TG.init();
    Nav.init();

    let initData;
    try {
      initData = await API.init();
    } catch (e) {
      if (e.status === 401) {
        showFatal('🔒 Please open AnimeZone from inside Telegram.',
          'This app must be launched from the bot.');
        return;
      }
      showFatal('😕 Connection error', 'Please try again shortly.');
      return;
    }

    state.user = initData.user;
    state.config = initData.config;
    state.categories = initData.categories;
    state.bookmarkIds = initData.bookmark_ids || [];

    // maintenance
    if (state.config.maintenance_mode) {
      showFatal('🔧 Under Maintenance', state.config.maintenance_message || 'Back soon!');
      return;
    }

    document.title = state.config.app_name || 'AnimeZone';

    // handle deep link start_param (title_<slug>)
    const sp = TG.startParam();
    if (sp && sp.indexOf('title_') === 0) {
      location.hash = '#/title/' + sp.slice(6);
    }

    Router.start();
    hideSplash();
  }

  function hideSplash() {
    const splash = document.getElementById('splash');
    const app = document.getElementById('app');
    setTimeout(() => {
      splash.classList.add('hide');
      app.style.display = 'block';
      setTimeout(() => (splash.style.display = 'none'), 400);
    }, 600);
  }

  function showFatal(title, subtitle) {
    const splash = document.getElementById('splash');
    splash.innerHTML = `<div class="empty-state">
      <div class="empty-state-emoji">${title.split(' ')[0]}</div>
      <div class="empty-state-title">${title.replace(/^\S+\s/, '')}</div>
      <div class="empty-state-subtitle">${subtitle}</div></div>`;
  }

  document.addEventListener('DOMContentLoaded', boot);
  return { state, reloadInit };
})();
