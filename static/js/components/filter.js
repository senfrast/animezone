window.Filter = (function () {
  // Renders a horizontal chip bar. options = [{label, value}], onSelect(value)
  function chipBar(options, current, onSelect) {
    const bar = H.el('div', { class: 'filter-bar' });
    options.forEach((o) => {
      const chip = H.el('div', {
        class: 'filter-chip' + (o.value === current ? ' active' : ''),
      }, o.label);
      chip.addEventListener('click', () => { Haptic.selection(); onSelect(o.value); });
      bar.appendChild(chip);
    });
    return bar;
  }
  return { chipBar };
})();
