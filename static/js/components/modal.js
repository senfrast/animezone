window.Modal = (function () {
  function open(html) {
    close();
    const overlay = H.el('div', { class: 'modal-overlay', id: 'modal-overlay' });
    const content = H.el('div', { class: 'modal-content' });
    content.innerHTML = html;
    overlay.appendChild(content);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
    document.body.appendChild(overlay);
    return content;
  }
  function close() {
    const m = document.getElementById('modal-overlay');
    if (m) m.remove();
  }
  function requestContent() {
    const c = open(
      `<h3>📩 Request a Title</h3>
       <input class="modal-input" id="req-title" placeholder="Title name (e.g. Dragon Ball Super)">
       <input class="modal-input" id="req-cat" placeholder="Category (Anime / Movies / Web Series)">
       <button class="join-button" id="req-send">Send Request</button>`
    );
    c.querySelector('#req-send').addEventListener('click', async () => {
      const title = c.querySelector('#req-title').value.trim();
      const cat = c.querySelector('#req-cat').value.trim();
      if (!title) { Toast.error('Enter a title'); return; }
      try {
        await API.request(title, cat);
        Haptic.notify('success');
        Toast.success('Request sent! 🙌');
        close();
      } catch (e) { Toast.error('Could not send'); }
    });
  }
  return { open, close, requestContent };
})();
