(() => {
  const form = document.querySelector('[data-product-image-form]');
  if (!form) return;
  const input = form.querySelector('[data-product-image-input]');
  const preview = form.querySelector('[data-product-image-preview]');
  const status = form.querySelector('[data-product-image-status]');
  const button = form.querySelector('[type=submit]');
  let previewUrl;
  let busy = false;
  input.addEventListener('change', () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    const file = input.files[0];
    preview.hidden = !file;
    if (file) {
      previewUrl = URL.createObjectURL(file);
      preview.src = previewUrl;
    }
    status.textContent = '';
  });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (busy || !input.files.length) return;
    const file = input.files[0];
    if (file.size > 12 * 1024 * 1024) {
      status.textContent = 'حجم عکس حداکثر ۱۲ مگابایت باشد.';
      return;
    }
    const data = new FormData(form);
    busy = true;
    button.disabled = true;
    input.disabled = true;
    status.textContent = 'در حال آماده‌سازی و فشرده‌سازی عکس…';
    try {
      // The server validates and re-encodes every upload, including fallback uploads.
      let upload = file;
      let filename = file.name;
      try {
        if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) throw new Error('format');
        const image = await createImageBitmap(file);
        try {
          if (image.width * image.height > 25000000) throw new Error('dimensions');
          const scale = Math.min(1, 1200 / Math.max(image.width, image.height));
          const canvas = document.createElement('canvas');
          canvas.width = Math.max(1, Math.round(image.width * scale));
          canvas.height = Math.max(1, Math.round(image.height * scale));
          canvas.getContext('2d').drawImage(image, 0, 0, canvas.width, canvas.height);
          const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/webp', 0.8));
          if (blob?.type === 'image/webp') {
            upload = blob;
            filename = 'product.webp';
          }
        } finally {
          image.close();
        }
      } catch (_) { /* Older browsers send the original for conversion on the server. */ }
      data.set('image', upload, filename);
      status.textContent = 'در حال ارسال و ذخیره عکس…';
      const response = await fetch(form.action || location.href, {
        method: 'POST', body: data, credentials: 'same-origin'
      });
      if (response.redirected) {
        location.assign(response.url);
        return;
      }
      if (!response.ok) throw new Error('upload');
      const page = new DOMParser().parseFromString(await response.text(), 'text/html');
      const errors = page.querySelector('.cp-product-image-editor .errorlist');
      status.textContent = errors?.textContent || 'ذخیره انجام نشد؛ صفحه را تازه‌سازی و دوباره تلاش کنید.';
    } catch (_) {
      status.textContent = 'ارسال عکس انجام نشد؛ اتصال اینترنت را بررسی و دوباره تلاش کنید.';
    } finally {
      busy = false;
      input.disabled = false;
      button.disabled = false;
    }
  });
})();
