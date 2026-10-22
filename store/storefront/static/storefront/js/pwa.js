(() => {
  'use strict';

  const root = document.documentElement;
  const themeButton = document.querySelector('[data-theme-toggle]');
  const installButton = document.querySelector('[data-install-app]');
  const themeColor = document.querySelector('meta[name="theme-color"]');
  const themeLabel = (theme) => {
    const light = theme === 'light';
    if (themeButton) {
      themeButton.querySelector('span:last-child').textContent = light ? 'حالت تیره' : 'حالت روشن';
      themeButton.querySelector('[aria-hidden="true"]').textContent = light ? '☾' : '☀';
      themeButton.setAttribute('aria-label', light ? 'تغییر به حالت تیره' : 'تغییر به حالت روشن');
    }
    if (themeColor) themeColor.content = light ? '#f4f8f5' : '#080f18';
  };

  themeLabel(root.dataset.theme || 'dark');
  themeButton?.addEventListener('click', () => {
    const theme = root.dataset.theme === 'light' ? 'dark' : 'light';
    root.dataset.theme = theme;
    try { localStorage.setItem('sabzi-theme', theme); } catch { /* storage may be disabled */ }
    themeLabel(theme);
  });

  let installPrompt;
  const isIos = /iphone|ipad|ipod/i.test(navigator.userAgent);
  if (installButton) {
    installButton.hidden = false;
    if (window.matchMedia('(display-mode: standalone)').matches) installButton.hidden = true;
    installButton.addEventListener('click', async () => {
      if (installPrompt) {
        installPrompt.prompt();
        await installPrompt.userChoice;
        installPrompt = null;
        installButton.hidden = true;
        return;
      }
      const message = isIos
        ? 'در منوی اشتراک‌گذاری مرورگر، گزینه «افزودن به صفحه اصلی» را انتخاب کنید.'
        : 'از منوی مرورگر گزینه «نصب برنامه» یا «افزودن به صفحه اصلی» را انتخاب کنید.';
      window.alert(message);
    });
  }

  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault();
    installPrompt = event;
    if (installButton) installButton.hidden = false;
  });
  window.addEventListener('appinstalled', () => {
    installPrompt = null;
    if (installButton) installButton.hidden = true;
  });

  if ('serviceWorker' in navigator && window.isSecureContext) {
    window.addEventListener('load', () => navigator.serviceWorker.register('/service-worker.js').catch(() => {}));
  }
})();
