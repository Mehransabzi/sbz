(() => {
  'use strict';

  const navigation=document.querySelector('#main-nav'),mobileHost=document.querySelector('[data-mobile-navigation]'),headerActions=document.querySelector('.header-actions');
  const mobileNavigation=window.matchMedia('(max-width:760px)');
  function placeNavigation(){if(!navigation||!mobileHost||!headerActions)return;if(mobileNavigation.matches){mobileHost.append(navigation);}else{headerActions.before(navigation);}}
  placeNavigation();mobileNavigation.addEventListener('change',placeNavigation);
  const CART_KEY = 'sabzi-store-cart-v1';
  const digits = new Intl.NumberFormat('fa-IR');
  const priceFormat = new Intl.NumberFormat('fa-IR', { maximumFractionDigits: 0, useGrouping: true });
  const revealItems = document.querySelectorAll('[data-reveal]');
  if ('IntersectionObserver' in window && revealItems.length) {
    document.documentElement.classList.add('motion-ready');
    const revealObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });
    revealItems.forEach((item, index) => {
      item.style.setProperty('--reveal-delay', `${Math.min(index % 5, 4) * 65}ms`);
      revealObserver.observe(item);
    });
  }
  const safeReadCart = () => {
    try {
      const data = JSON.parse(localStorage.getItem(CART_KEY) || '[]');
      return Array.isArray(data) ? data.flatMap((row) => {
        if (!row || typeof row.code !== 'string') return [];
        const quantity = Math.floor(Number(row.quantity) || 0);
        if (quantity <= 0) return [];
        return [{ ...row, quantity: Math.min(999, quantity), price: Math.max(0, Number(row.price) || 0) }];
      }) : [];
    } catch {
      return [];
    }
  };
  let cart = document.querySelector('[data-order-confirmed]') ? [] : safeReadCart();
  if (document.querySelector('[data-order-confirmed]')) {
    try { localStorage.removeItem(CART_KEY); } catch { /* storage may be disabled */ }
  }

  const saveCart = () => {
    try { localStorage.setItem(CART_KEY, JSON.stringify(cart)); } catch { /* storage may be disabled */ }
    renderCart();
  };
  const money = (value) => `${priceFormat.format(Number(value) || 0)} ریال`;
  const safeImage = (value) => {
    try {
      const url = new URL(String(value || ''), window.location.origin);
      return value && ['http:', 'https:'].includes(url.protocol) ? url.href : '';
    } catch { return ''; }
  };
  let cartRefreshing = Boolean(document.querySelector('.checkout-cart-items') && cart.length);
  function renderCart() {
    const count = cart.reduce((sum, row) => sum + row.quantity, 0);
    const total = cart.reduce((sum, row) => sum + row.price * row.quantity, 0);
    document.querySelectorAll('.cart-count').forEach((node) => { node.textContent = digits.format(count); });
    const floating = document.querySelector('.floating-cart');
    if (floating) {
      floating.hidden = count === 0;
      floating.querySelector('.floating-cart-count').textContent = digits.format(count);
      floating.querySelector('.floating-cart-total').textContent = money(total);
    }
    document.querySelectorAll('[data-product-quantity]').forEach((node) => {
      const row = cart.find((item) => item.code === node.dataset.productQuantity);
      node.textContent = digits.format(row ? row.quantity : 0);
      const minus = node.parentElement?.querySelector('[data-delta="-1"]');
      if (minus) minus.disabled = !row;
    });
    const list = document.querySelector('.checkout-cart-items');
    if (!list) return;
    list.replaceChildren();
    const hidden = document.querySelector('#id_cart_items');
    const submit = document.querySelector('.submit-order');
    const totalNode = document.querySelector('.checkout-total');
    if (hidden) hidden.value = JSON.stringify(cart.map(({ code, quantity }) => ({ code, quantity })));
    document.querySelectorAll('.checkout-item-count').forEach(node => { node.textContent = digits.format(cart.length); });
    document.querySelectorAll('.checkout-unit-count').forEach(node => { node.textContent = digits.format(count); });
    if (!cart.length) {
      const empty = document.createElement('div'); empty.className = 'friendly-empty';
      const icon = document.createElement('span'); icon.textContent = '▧'; icon.setAttribute('aria-hidden', 'true');
      const title = document.createElement('h3'); title.textContent = 'سبد خریدتان منتظر انتخاب شماست';
      const hint = document.createElement('p'); hint.textContent = 'قطعات موردنیاز را از کاتالوگ انتخاب کنید.';
      const link = document.createElement('a'); link.className = 'button button-primary'; link.href = '/catalog/'; link.textContent = 'مشاهده قطعات ←';
      empty.append(icon, title, hint, link); list.append(empty);
    } else {
      cart.forEach((row, index) => {
        const line = document.createElement('article'); line.className = 'checkout-line cart-product' + (row.available === false ? ' cart-unavailable' : '');
        const photo = document.createElement('div'); photo.className = 'cart-product-photo';
        const placeholder = document.createElement('span'); placeholder.textContent = '▧'; placeholder.setAttribute('aria-hidden', 'true'); photo.append(placeholder);
        const imageUrl = safeImage(row.image);
        if (imageUrl) {
          const image = document.createElement('img'); image.src = imageUrl; image.alt = row.name; image.loading = 'lazy'; image.decoding = 'async';
          image.addEventListener('error', () => { image.remove(); placeholder.hidden = false; }, { once: true });
          placeholder.hidden = true; photo.append(image);
        }
        const info = document.createElement('div'); info.className = 'cart-product-info';
        const title = document.createElement('h3'); title.textContent = row.name;
        const meta = document.createElement('p'); meta.className = 'cart-product-code'; meta.textContent = 'کد ' + String(row.code).replace(/\d/g, digit => '۰۱۲۳۴۵۶۷۸۹'[Number(digit)]) + ' · ' + (row.unit || 'عدد');
        const price = document.createElement('p'); price.className = 'cart-unit-price'; price.textContent = 'قیمت واحد: ' + money(row.price);
        info.append(title, meta, price);
        if (row.available === false) { const note = document.createElement('p'); note.className = 'cart-unavailable-note'; note.textContent = 'این کالا دیگر در فهرست فروش نیست؛ آن را از سبد حذف کنید.'; info.append(note); }
        const tools = document.createElement('div'); tools.className = 'cart-product-controls';
        const stepper = document.createElement('div'); stepper.className = 'quantity-tools'; stepper.setAttribute('role', 'group'); stepper.setAttribute('aria-label', 'تعداد ' + row.name);
        const minus = document.createElement('button'); minus.type = 'button'; minus.textContent = '−'; minus.setAttribute('aria-label', 'کم کردن تعداد ' + row.name); minus.addEventListener('click', () => changeQuantity(index, -1));
        const quantity = document.createElement('span'); quantity.textContent = digits.format(row.quantity);
        const plus = document.createElement('button'); plus.type = 'button'; plus.textContent = '+'; plus.disabled = row.quantity >= 999 || row.available === false; plus.setAttribute('aria-label', 'افزودن تعداد ' + row.name); plus.addEventListener('click', () => changeQuantity(index, 1));
        stepper.append(minus, quantity, plus);
        const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'cart-remove'; remove.textContent = 'حذف کالا'; remove.setAttribute('aria-label', 'حذف ' + row.name); remove.addEventListener('click', () => { cart.splice(index, 1); saveCart(); });
        const subtotal = document.createElement('div'); subtotal.className = 'cart-line-total'; const label = document.createElement('small'); label.textContent = 'مبلغ این ردیف'; const amount = document.createElement('strong'); amount.textContent = money(row.price * row.quantity); subtotal.append(label, amount);
        tools.append(stepper, remove); line.append(photo, info, tools, subtotal); list.append(line);
      });
    }
    if (totalNode) totalNode.textContent = money(total);
    if (submit) submit.disabled = cart.length === 0 || cartRefreshing || cart.some(row => row.available === false);
  }

  async function refreshCartProducts() {
    if (!document.querySelector('.checkout-cart-items')) return;
    const status = document.querySelector('.cart-refresh-state');
    if (!cart.length) { cartRefreshing = false; if (status) status.hidden = true; renderCart(); return; }
    try {
      const codes = cart.map(row => row.code); const products = new Map();
      for (let offset = 0; offset < codes.length; offset += 80) {
        const url = new URL(document.body.dataset.cartProductsUrl, window.location.origin);
        codes.slice(offset, offset + 80).forEach(code => url.searchParams.append('code', code));
        const response = await fetch(url, { credentials: 'same-origin', cache: 'no-store', signal: AbortSignal.timeout(15000) });
        if (!response.ok) throw new Error('Cart refresh failed');
        const data = await response.json();
        if (!Array.isArray(data.products)) throw new Error('Invalid product data');
        data.products.forEach(row => products.set(row.code, row));
      }
      cart = cart.map(row => {
        const product = products.get(row.code);
        return product ? { ...row, name: product.name, image: product.image, price: Number(product.price) || 0, unit: product.unit, available: true } : { ...row, image: '', available: false };
      });
      if (status) { status.textContent = 'قیمت‌ها و تصاویر کالاها بروزرسانی شدند.'; status.classList.add('is-ready'); }
    } catch {
      if (status) { status.textContent = 'بررسی آنلاین سبد انجام نشد. مبلغ نهایی هنگام ثبت سفارش دوباره بررسی می‌شود.'; status.classList.add('is-warning'); }
    } finally {
      cartRefreshing = false; saveCart();
    }
  }

  function changeQuantity(index, delta) {
    if (!cart[index]) return;
    cart[index].quantity = Math.min(999, Math.max(0, cart[index].quantity + delta));
    if (cart[index].quantity === 0) cart.splice(index, 1);
    saveCart();
  }

  document.addEventListener('click', (event) => {
    const step = event.target.closest('.js-cart-step');
    if (step) {
      const code = step.dataset.code;
      if (!code) return;
      const existing = cart.find((row) => row.code === code);
      if (Number(step.dataset.delta) < 0) { if (existing) changeQuantity(cart.indexOf(existing), -1); }
      else if (existing) { existing.quantity = Math.min(999, existing.quantity + 1); saveCart(); }
      else { cart.push({ code, name: step.dataset.name || code, price: Number(step.dataset.price) || 0, unit: step.dataset.unit || 'عدد', image: safeImage(step.dataset.image), quantity: 1 }); saveCart(); }
      return;
    }
    const button = event.target.closest('.js-add-to-cart');
    if (!button) return;
    const code = button.dataset.code;
    if (!code) return;
    const existing = cart.find((row) => row.code === code);
    if (existing) existing.quantity = Math.min(999, existing.quantity + 1);
    else cart.push({ code, name: button.dataset.name || code, price: Number(button.dataset.price) || 0, unit: button.dataset.unit || 'عدد', image: safeImage(button.dataset.image), quantity: 1 });
    saveCart();
  });

  const menuToggle = document.querySelector('.menu-toggle');
  const nav = document.querySelector('.main-nav');
  menuToggle?.addEventListener('click', () => {
    const open = nav.classList.toggle('open');
    menuToggle.setAttribute('aria-expanded', String(open));
  });


  function initializeViews() { document.querySelectorAll('[data-view-switch]').forEach(container => {
    const key = 'sabzi-view-' + container.dataset.viewSwitch;
    const setView = (view) => {
      container.querySelectorAll('[data-view-panel]').forEach(panel => { panel.hidden = panel.dataset.viewPanel !== view; });
      container.querySelectorAll('[data-view]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.view === view)));
      try { localStorage.setItem(key, view); } catch {}
    };
    let view = 'cards'; try { if (localStorage.getItem(key) === 'table') view = 'table'; } catch {}
    setView(view);
    container.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => setView(button.dataset.view)));
  });
  }
  initializeViews();
  document.querySelectorAll('.main-nav a').forEach(link => {
    if (!link.hash && link.pathname === window.location.pathname) link.setAttribute('aria-current', 'page');
  });
  window.addEventListener('storage', event => { if (event.key === CART_KEY) { cart = safeReadCart(); renderCart(); refreshCartProducts(); } });
  const catalogForm=document.querySelector('.catalog-tools');
  if(catalogForm){
    const input=catalogForm.querySelector('[name="q"]');let timer,controller,version=0;
    const status=document.createElement('p');status.className='live-search-status';status.setAttribute('role','status');catalogForm.after(status);
    input.addEventListener('input',()=>{clearTimeout(timer);controller?.abort();const current=++version;timer=setTimeout(async()=>{
      controller=new AbortController();const url=new URL(catalogForm.action);url.search=new URLSearchParams(new FormData(catalogForm)).toString();status.textContent='در حال جست‌وجو…';
      try{const response=await fetch(url,{signal:controller.signal});if(!response.ok)throw new Error();const html=await response.text();if(current!==version)return;const doc=new DOMParser().parseFromString(html,'text/html');const old=document.querySelector('.catalog-results'),fresh=doc.querySelector('.catalog-results');if(!fresh)throw new Error();
        // Keep the focused form intact; replace only results below the access banner.
        [...old.children].filter(node=>!node.matches('.catalog-tools,.price-access-banner,.live-search-status')).forEach(node=>node.remove());
        [...fresh.children].filter(node=>!node.matches('.catalog-tools,.price-access-banner')).forEach(node=>old.append(node));
        old.querySelectorAll('[data-reveal]').forEach(node=>node.classList.add('is-visible'));initializeViews();renderCart();history.replaceState(null,'',url);status.textContent='نتایج بروزرسانی شد.';
      }catch(error){if(current===version&&error.name!=='AbortError')status.textContent='جست‌وجوی زنده انجام نشد؛ دکمه اعمال را بزنید.';}
    },500);});
  }
  renderCart();
  refreshCartProducts();
})();
