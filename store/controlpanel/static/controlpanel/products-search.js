(() => {
  const form = document.querySelector('[data-products-search]');
  if (!form) return;
  const input = form.elements.q;
  const results = document.querySelector('[data-products-results]');
  const status = document.querySelector('[data-products-search-status]');
  let timer;
  let controller;
  let version = 0;
  let composing = false;

  function cancelPending() {
    clearTimeout(timer);
    controller?.abort();
    version += 1;
  }

  function searchUrl() {
    const url = new URL(form.action || location.href);
    url.search = new URLSearchParams(new FormData(form)).toString();
    return url;
  }

  async function load(url) {
    cancelPending();
    const current = version;
    const request = new AbortController();
    controller = request;
    results.setAttribute('aria-busy', 'true');
    status.textContent = 'در حال جست‌وجو…';
    try {
      const response = await fetch(url, {
        signal: request.signal, cache: 'no-store', credentials: 'same-origin'
      });
      if (current !== version) return;
      if (response.redirected) {
        location.assign(response.url);
        return;
      }
      if (!response.ok) throw new Error('search');
      const page = new DOMParser().parseFromString(await response.text(), 'text/html');
      if (current !== version) return;
      const updated = page.querySelector('[data-products-results]');
      if (!updated) throw new Error('results');
      results.replaceChildren(...updated.childNodes);
      history.replaceState(history.state, '', url);
      status.textContent = 'نتایج جست‌وجو به‌روز شد.';
    } catch (error) {
      if (error.name !== 'AbortError' && current === version) {
        status.textContent = 'دریافت نتایج انجام نشد؛ دوباره تلاش کنید.';
      }
    } finally {
      if (current === version) results.removeAttribute('aria-busy');
    }
  }

  function schedule() {
    cancelPending();
    results.removeAttribute('aria-busy');
    status.textContent = '';
    if (!composing) timer = setTimeout(() => load(searchUrl()), 350);
  }
  input.addEventListener('input', schedule);
  input.addEventListener('compositionstart', () => { composing = true; cancelPending(); });
  input.addEventListener('compositionend', () => { composing = false; schedule(); });
  form.addEventListener('submit', event => {
    event.preventDefault();
    load(searchUrl());
  });
  results.addEventListener('click', event => {
    const link = event.target.closest('.cp-pagination a');
    if (!link || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    load(new URL(link.href));
  });
})();
