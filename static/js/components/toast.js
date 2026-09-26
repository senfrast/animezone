window.Toast = (function () {
  function show(message, type = '') {
    const c = document.getElementById('toast-container');
    const t = H.el('div', { class: 'toast ' + type }, message);
    c.appendChild(t);
    setTimeout(() => {
      t.classList.add('out');
      setTimeout(() => t.remove(), 300);
    }, 2200);
  }
  return {
    show,
    success: (m) => show(m, 'success'),
    error: (m) => show(m, 'error'),
  };
})();
