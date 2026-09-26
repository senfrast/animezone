// Haptic feedback wrapper (no-op in browsers).
window.Haptic = (function () {
  const hf = window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback
    ? window.Telegram.WebApp.HapticFeedback : null;
  function impact(style) { try { hf && hf.impactOccurred(style || 'light'); } catch (e) {} }
  function notify(type) { try { hf && hf.notificationOccurred(type || 'success'); } catch (e) {} }
  function selection() { try { hf && hf.selectionChanged(); } catch (e) {} }
  return { impact, notify, selection };
})();
