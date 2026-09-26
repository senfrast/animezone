window.Nav = (function () {
  function init() {
    document.querySelectorAll('#bottom-nav .nav-item').forEach((item) => {
      item.addEventListener('click', () => {
        Haptic.selection();
        const page = item.dataset.page;
        Router.go('/' + (page === 'home' ? '' : page));
      });
    });
  }
  function setActive(page) {
    document.querySelectorAll('#bottom-nav .nav-item').forEach((item) => {
      item.classList.toggle('active', item.dataset.page === page);
    });
  }
  return { init, setActive };
})();
