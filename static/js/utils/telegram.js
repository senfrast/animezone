// Telegram WebApp helpers with graceful browser fallback.
window.TG = (function () {
  const wa = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;

  function init() {
    if (wa) {
      try {
        wa.ready();
        wa.expand();
        wa.setHeaderColor && wa.setHeaderColor('#0a0a0f');
        wa.setBackgroundColor && wa.setBackgroundColor('#0a0a0f');
        wa.enableClosingConfirmation && wa.enableClosingConfirmation();
      } catch (e) {}
    }
  }
  function initData() {
    return wa ? wa.initData || '' : '';
  }
  function user() {
    return wa && wa.initDataUnsafe ? wa.initDataUnsafe.user : null;
  }
  function startParam() {
    return wa && wa.initDataUnsafe ? wa.initDataUnsafe.start_param : null;
  }
  function openTelegramLink(url) {
    if (wa && wa.openTelegramLink) wa.openTelegramLink(url);
    else window.open(url, '_blank');
  }
  function openLink(url) {
    if (wa && wa.openLink) wa.openLink(url);
    else window.open(url, '_blank');
  }
  function share(url, text) {
    const shareUrl = 'https://t.me/share/url?url=' + encodeURIComponent(url) +
      '&text=' + encodeURIComponent(text || '');
    openTelegramLink(shareUrl);
  }
  // Back button
  function showBack(cb) {
    if (wa && wa.BackButton) {
      wa.BackButton.show();
      wa.BackButton.onClick(cb);
    }
  }
  function hideBack() {
    if (wa && wa.BackButton) wa.BackButton.hide();
  }
  return { wa, init, initData, user, startParam, openTelegramLink, openLink, share, showBack, hideBack };
})();
