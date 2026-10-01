window.Skeleton = (function () {
  function cards(n = 6) {
    let h = '<div class="horizontal-scroll">';
    for (let i = 0; i < n; i++) {
      h += '<div class="title-card"><div class="skeleton-box" style="width:100%;aspect-ratio:16/9"></div>' +
        '<div class="skeleton-box" style="width:100px;height:12px;margin-top:8px"></div></div>';
    }
    h += '</div>';
    return h;
  }
  function banner() {
    return '<div class="skeleton-box" style="width:100%;height:200px;border-radius:16px"></div>';
  }
  function grid(n = 6) {
    let h = '<div class="grid">';
    for (let i = 0; i < n; i++) {
      h += '<div class="grid-card"><div class="skeleton-box" style="width:100%;aspect-ratio:16/9"></div></div>';
    }
    h += '</div>';
    return h;
  }
  function home() {
    return '<div class="page">' + banner() +
      '<div class="section" style="margin-top:20px"><div class="skeleton-box" style="width:120px;height:16px;margin-bottom:12px"></div>' + cards() + '</div>' +
      '<div class="section"><div class="skeleton-box" style="width:120px;height:16px;margin-bottom:12px"></div>' + cards() + '</div></div>';
  }
  return { cards, banner, grid, home };
})();
