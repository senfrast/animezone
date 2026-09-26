window.PageProfile = (function () {
  async function render(container) {
    Nav.setActive('profile');
    const u = App.state.user || {};
    const page = H.el('div', { class: 'page' });

    const initial = (u.first_name || 'A').charAt(0).toUpperCase();
    const header = H.el('div', { class: 'profile-header' });
    header.innerHTML = `<div class="profile-avatar">${H.esc(initial)}</div>
      <div class="profile-name">${H.esc(u.first_name || 'AnimeZone User')}</div>
      <div class="subtitle">Member of AnimeZone 🎌</div>`;
    page.appendChild(header);

    const grid = H.el('div', { class: 'stat-grid' });
    grid.innerHTML =
      `<div class="stat-card"><div class="stat-value">${u.total_bookmarks || 0}</div><div class="stat-label">Bookmarks</div></div>
       <div class="stat-card"><div class="stat-value">${u.app_opens_count || 0}</div><div class="stat-label">App Opens</div></div>`;
    page.appendChild(grid);

    // settings
    const sec = H.el('div', { style: 'margin-top:24px' });
    sec.innerHTML = '<div class="section-title">⚙️ Preferences</div>';

    const nsfwRow = H.el('div', { class: 'setting-row' });
    nsfwRow.innerHTML = `<div><div style="font-weight:600">🔞 18+ Content</div><div class="subtitle">Show mature titles</div></div>`;
    const nsfwSwitch = H.el('div', { class: 'switch' + (App.state.user.show_nsfw ? ' on' : '') });
    nsfwSwitch.addEventListener('click', async () => {
      Haptic.impact('light');
      const newVal = !App.state.user.show_nsfw;
      if (newVal) {
        Modal.open(
          `<h3>⚠️ Age Verification</h3>
           <p style="color:var(--text-secondary);margin-bottom:16px">This shows 18+ content. By enabling, you confirm you are 18 or older.</p>
           <button class="join-button" id="nsfw-yes" style="margin-bottom:10px">✅ I am 18+ — Enable</button>
           <button class="icon-button" id="nsfw-no">❌ Cancel</button>`
        );
        document.getElementById('nsfw-yes').addEventListener('click', async () => {
          await API.toggleNsfw(true);
          App.state.user.show_nsfw = true;
          nsfwSwitch.classList.add('on');
          Modal.close();
          Toast.success('18+ enabled');
          API.invalidate();
          await App.reloadInit();
        });
        document.getElementById('nsfw-no').addEventListener('click', () => Modal.close());
      } else {
        await API.toggleNsfw(false);
        App.state.user.show_nsfw = false;
        nsfwSwitch.classList.remove('on');
        Toast.success('18+ disabled');
        API.invalidate();
        await App.reloadInit();
      }
    });
    nsfwRow.appendChild(nsfwSwitch);
    sec.appendChild(nsfwRow);

    const reqRow = H.el('div', { class: 'setting-row' });
    reqRow.innerHTML = `<div><div style="font-weight:600">📩 Request a Title</div><div class="subtitle">Can't find something?</div></div><div style="font-size:22px">›</div>`;
    reqRow.addEventListener('click', () => Modal.requestContent());
    sec.appendChild(reqRow);

    page.appendChild(sec);

    page.appendChild(H.el('div', { style: 'text-align:center;color:var(--text-tertiary);font-size:12px;margin-top:30px' },
      'AnimeZone · v1.0'));

    container.innerHTML = '';
    container.appendChild(page);
  }
  return { render };
})();
