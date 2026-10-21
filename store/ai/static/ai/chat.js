(() => {
  'use strict';
  const chatForm = document.querySelector('[data-ai-chat]');
  const uploadForm = document.querySelector('[data-image-upload]');
  if (!chatForm && !uploadForm) return;

  const customerMode = chatForm?.dataset.chatKind === 'customer' || Boolean(uploadForm);
  const messages = document.querySelector('[data-ai-messages]');
  const chatStatus = document.querySelector('[data-ai-status]');
  const messageInput = chatForm?.querySelector('textarea[name="message"]');
  const sendButton = chatForm?.querySelector('button[type="submit"]');
  const newChatButton = document.querySelector('[data-chat-clear]');
  const history = [];
  const digits = new Intl.NumberFormat('fa-IR');
  const plainDigits = new Intl.NumberFormat('fa-IR', {useGrouping: false});
  const money = value => digits.format(Math.round(Number(value) || 0)) + ' ریال';
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let chatBusy = false;
  let imageBusy = false;
  let remainingImages = Number(uploadForm?.dataset.imageRemaining ?? 5);

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function icon(name) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    svg.classList.add('ai-icon');
    svg.setAttribute('aria-hidden', 'true');
    use.setAttribute('href', '#ai-icon-' + name);
    svg.append(use);
    return svg;
  }

  function actionButton(className, name, text, label) {
    const button = element('button', className);
    button.type = 'button';
    if (name) button.append(icon(name));
    if (text) button.append(element('span', '', text));
    if (label) button.setAttribute('aria-label', label);
    return button;
  }

  function syncControls() {
    if (sendButton) sendButton.disabled = chatBusy || !messageInput.value.trim();
    if (newChatButton) newChatButton.disabled = chatBusy || imageBusy;
  }

  async function apiRequest(form, payload, options = {}) {
    const headers = {'Accept': 'application/json', 'X-CSRFToken': form.querySelector('[name="csrfmiddlewaretoken"]').value};
    const isMultipart = payload instanceof FormData;
    if (!isMultipart) headers['Content-Type'] = 'application/json';
    const response = await fetch(options.endpoint || form.dataset.endpoint, {
      method: 'POST', credentials: 'same-origin', headers,
      body: isMultipart ? payload : JSON.stringify(payload), signal: options.signal
    });
    let data;
    try { data = await response.json(); }
    catch (_) { throw new Error('پاسخ آماده نشد. لطفاً کمی بعد دوباره تلاش کنید.'); }
    if (uploadForm && data.image_usage) updateImageUsage(data.image_usage);
    if (!response.ok) throw new Error(data.error || 'درخواست شما تکمیل نشد. دوباره تلاش کنید.');
    return data;
  }

  function scrollMessages() {
    messages?.scrollTo({top: messages.scrollHeight, behavior: reduceMotion ? 'auto' : 'smooth'});
  }

  function createMessage(role) {
    document.querySelector('[data-chat-welcome]')?.setAttribute('hidden', '');
    const article = element('article', 'ai-chat-message ' + role);
    const avatar = element('span', 'ai-message-avatar' + (role === 'user' ? ' user-avatar' : ''));
    if (role === 'user') avatar.textContent = 'ش'; else avatar.append(icon('bot'));
    const content = element('div', 'ai-message-content');
    const meta = element('div', 'ai-message-meta');
    meta.append(element('b', '', role === 'user' ? 'شما' : (customerMode ? 'دستیار سبزی' : 'تحلیل‌گر فروشگاه')));
    const time = element('time', '', new Intl.DateTimeFormat('fa-IR', {hour: '2-digit', minute: '2-digit'}).format(new Date()));
    meta.append(time);
    const bubble = element('div', 'ai-message-bubble');
    content.append(meta, bubble);
    article.append(avatar, content);
    messages.append(article);
    return {article, content, bubble};
  }

  function appendMessage(role, text, error = false) {
    const row = createMessage(role);
    row.bubble.append(element('p', '', text));
    if (error) row.article.classList.add('is-error');
    if (role === 'assistant' && !error) {
      const tools = element('div', 'ai-message-tools');
      const copy = actionButton('', 'copy', 'کپی پاسخ', 'کپی پاسخ ربات');
      copy.addEventListener('click', async () => {
        try {
          await navigator.clipboard.writeText(text);
          copy.querySelector('span').textContent = 'کپی شد';
        } catch (_) { copy.querySelector('span').textContent = 'کپی ممکن نشد'; }
        window.setTimeout(() => { copy.querySelector('span').textContent = 'کپی پاسخ'; }, 1800);
      });
      tools.append(copy);
      row.content.append(tools);
    }
    scrollMessages();
    return row;
  }

  function showTyping() {
    const row = createMessage('assistant');
    row.article.classList.add('ai-typing');
    const dots = element('span', 'ai-typing-dots');
    dots.setAttribute('aria-hidden', 'true');
    dots.append(element('i'), element('i'), element('i'));
    const text = element('span', 'ai-typing-copy', 'در حال آماده‌کردن پاسخ شما…');
    row.bubble.append(dots, text);
    const tips = ['در حال آماده‌کردن پاسخ شما…', 'کمی صبر کنید؛ درخواست شما در حال بررسی است.', 'از همراهی شما ممنونیم؛ پاسخ در حال آماده‌شدن است.'];
    let index = 0;
    const timer = window.setInterval(() => { text.textContent = tips[++index % tips.length]; }, 4500);
    scrollMessages();
    return () => { window.clearInterval(timer); row.article.remove(); };
  }

  function resizeInput() {
    if (!messageInput) return;
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(145, Math.max(44, messageInput.scrollHeight)) + 'px';
    syncControls();
  }

  messageInput?.addEventListener('input', resizeInput);
  messageInput?.addEventListener('keydown', event => {
    const desktopKeyboard = window.matchMedia('(min-width: 761px) and (pointer: fine)').matches;
    if (desktopKeyboard && event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      chatForm.requestSubmit();
    }
  });
  document.querySelectorAll('[data-chat-prompt]').forEach(button => button.addEventListener('click', () => {
    messageInput.value = button.dataset.chatPrompt;
    resizeInput();
    messageInput.focus();
  }));

  chatForm?.addEventListener('submit', async event => {
    event.preventDefault();
    const text = messageInput.value.trim();
    if (!text || chatBusy) return;
    chatBusy = true;
    syncControls();
    sendButton.classList.add('is-loading');
    sendButton.setAttribute('aria-busy', 'true');
    appendMessage('user', text);
    messageInput.value = '';
    resizeInput();
    if (chatStatus) chatStatus.textContent = '';
    const stopTyping = showTyping();
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 75000);
    try {
      let payload;
      if (customerMode) payload = {message: text, conversation_id: chatForm.dataset.conversationId};
      else {
        history.push({role: 'user', content: text});
        payload = {messages: history.slice(-12), ...(chatForm.dataset.conversationId ? {conversation_id: chatForm.dataset.conversationId} : {})};
      }
      const data = await apiRequest(chatForm, payload, {signal: controller.signal});
      if (!data.reply) throw new Error('پاسخی آماده نشد؛ دوباره تلاش کنید.');
      stopTyping();
      appendMessage('assistant', data.reply);
      if (!customerMode) history.push({role: 'assistant', content: data.reply});
      if (chatStatus && data.maintenance) chatStatus.textContent = 'دستیار در حال به‌روزرسانی است؛ پاسخ با اطلاعات ثبت‌شده فروشگاه آماده شد.';
    } catch (error) {
      stopTyping();
      if (!customerMode && history.at(-1)?.role === 'user') history.pop();
      const reply = error.name === 'AbortError' ? 'آماده‌شدن پاسخ بیشتر از معمول طول کشید. لطفاً دوباره تلاش کنید.' : error.message;
      const row = appendMessage('assistant', reply, true);
      const tools = element('div', 'ai-message-tools');
      const retry = actionButton('', 'retry', 'تلاش دوباره');
      retry.addEventListener('click', () => { messageInput.value = text; resizeInput(); messageInput.focus(); });
      tools.append(retry); row.content.append(tools);
    } finally {
      window.clearTimeout(timeout);
      chatBusy = false;
      sendButton.classList.remove('is-loading');
      sendButton.removeAttribute('aria-busy');
      syncControls();
    }
  });

  newChatButton?.addEventListener('click', async () => {
    if (chatBusy || imageBusy) return;
    if (!customerMode) { history.length = 0; messages.replaceChildren(); appendMessage('assistant', 'گفت‌وگوی تازه شروع شد. چه کمکی از دستم برمی‌آید؟'); return; }
    newChatButton.disabled = true;
    try {
      const response = await fetch(newChatButton.dataset.createEndpoint, {method: 'POST', credentials: 'same-origin', headers: {'X-CSRFToken': chatForm.querySelector('[name="csrfmiddlewaretoken"]').value}});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'گفت‌وگوی تازه ساخته نشد.');
      window.location.assign(data.url);
    } catch (error) { if (chatStatus) chatStatus.textContent = error.message; newChatButton.disabled = false; }
  });

  const tabs = Array.from(document.querySelectorAll('[data-ai-tab]'));
  function selectTab(button, focus = false) {
    tabs.forEach(tab => {
      const active = tab === button;
      tab.classList.toggle('is-active', active);
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
    });
    document.querySelectorAll('[data-ai-panel]').forEach(panel => {
      const active = panel.dataset.aiPanel === button.dataset.aiTab;
      panel.hidden = !active;
      panel.classList.toggle('is-active', active);
    });
    if (focus) button.focus();
  }
  tabs.forEach((button, index) => {
    button.addEventListener('click', () => selectTab(button));
    button.addEventListener('keydown', event => {
      let target;
      if (event.key === 'ArrowLeft') target = (index + 1) % tabs.length;
      if (event.key === 'ArrowRight') target = (index - 1 + tabs.length) % tabs.length;
      if (event.key === 'Home') target = 0;
      if (event.key === 'End') target = tabs.length - 1;
      if (target !== undefined) { event.preventDefault(); selectTab(tabs[target], true); }
    });
  });
  syncControls();
  if (!uploadForm) return;

  const fileInput = uploadForm.querySelector('[data-image-file]');
  const dropzone = uploadForm.querySelector('[data-dropzone]');
  const preview = uploadForm.querySelector('[data-image-preview]');
  const resetButton = uploadForm.querySelector('[data-image-reset]');
  const uploadButton = uploadForm.querySelector('[data-image-submit]');
  const processing = document.querySelector('[data-image-processing]');
  const processingMessage = document.querySelector('[data-processing-message]');
  const elapsedLabel = document.querySelector('[data-processing-elapsed]');
  const imageStatus = document.querySelector('[data-image-status]');
  const imageResult = document.querySelector('[data-image-result]');
  const tabLoading = document.querySelector('.ai-tab-loading');
  const modal = document.querySelector('[data-invoice-modal]');
  const itemsBox = document.querySelector('[data-invoice-items]');
  const totalBox = document.querySelector('[data-invoice-total]');
  const countBox = document.querySelector('[data-invoice-selected]');
  const confirmButton = document.querySelector('[data-invoice-confirm]');
  const modalFeedback = document.querySelector('[data-modal-feedback]');
  let selectedFile = null;
  let previewUrl = null;
  let imageController = null;
  let processingTimer = null;
  let invoiceRows = [];
  let modalReturnFocus = null;

  function updateImageUsage(usage) {
    remainingImages = Math.max(0, Number(usage.remaining) || 0);
    uploadForm.dataset.imageRemaining = String(remainingImages);
    const counter = document.querySelector('[data-quota-remaining]');
    if (counter) counter.textContent = plainDigits.format(remainingImages);
    document.querySelectorAll('.ai-quota-slots i').forEach((slot, index) => slot.classList.toggle('is-used', index < Number(usage.used)));
    uploadButton.disabled = imageBusy || !selectedFile || remainingImages <= 0;
  }

  async function refreshImageUsage() {
    try {
      const response = await fetch(uploadForm.dataset.endpoint, {credentials:'same-origin', cache:'no-store', signal:AbortSignal.timeout(8000)});
      if (response.ok) { const data = await response.json(); if (data.image_usage) updateImageUsage(data.image_usage); }
    } catch (_) { /* The server always enforces the quota even while this indicator is offline. */ }
  }
  window.addEventListener('focus', refreshImageUsage);
  refreshImageUsage();

  function setImageStatus(text = '', error = false) {
    imageStatus.textContent = text;
    imageStatus.hidden = !text;
    imageStatus.classList.toggle('is-error', error);
  }

  function cancelLookups() {
    invoiceRows.forEach(row => {
      window.clearTimeout(row.debounce);
      row.controller?.abort();
      row.version++;
      row.searching = false;
    });
  }

  function clearInvoice() {
    cancelLookups();
    invoiceRows = [];
    imageResult.hidden = true;
    itemsBox.replaceChildren();
  }

  function chooseFile(file) {
    if (!file || imageBusy) return;
    const types = {jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png', webp: 'image/webp'};
    const type = file.type || types[file.name.split('.').pop().toLowerCase()];
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(type)) { setImageStatus('لطفاً تصویر JPG، PNG یا WEBP انتخاب کنید.', true); return; }
    if (file.size > 6 * 1024 * 1024) { setImageStatus('حجم تصویر باید حداکثر ۶ مگابایت باشد.', true); return; }
    selectedFile = file.type ? file : new File([file], file.name, {type});
    clearInvoice();
    setImageStatus();
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = URL.createObjectURL(selectedFile);
    const frame = element('div', 'ai-preview-image');
    const img = element('img'); img.src = previewUrl; img.alt = 'پیش‌نمایش تصویر فاکتور انتخاب‌شده';
    const change = actionButton('ai-button ai-button-secondary ai-preview-change', 'image', 'تغییر تصویر');
    change.addEventListener('click', () => fileInput.click());
    frame.append(img, change);
    const details = element('div', 'ai-preview-details');
    const mark = element('span'); mark.append(icon('file'));
    const info = element('div'); info.append(element('strong', '', selectedFile.name), element('small', '', digits.format(Math.max(1, Math.round(selectedFile.size / 1024))) + ' کیلوبایت · آماده بررسی'));
    details.append(mark, info);
    preview.replaceChildren(frame, details);
    preview.hidden = false;
    dropzone.hidden = true;
    resetButton.hidden = false;
    uploadButton.disabled = remainingImages <= 0;
  }

  function clearFile() {
    if (imageBusy) return;
    selectedFile = null;
    fileInput.value = '';
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null;
    preview.replaceChildren(); preview.hidden = true;
    dropzone.hidden = false; resetButton.hidden = true; uploadButton.disabled = true;
    clearInvoice(); setImageStatus();
  }

  dropzone.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', () => chooseFile(fileInput.files?.[0]));
  resetButton.addEventListener('click', clearFile);
  ['dragenter', 'dragover'].forEach(eventName => dropzone.addEventListener(eventName, event => { event.preventDefault(); dropzone.classList.add('is-dragging'); }));
  ['dragleave', 'drop'].forEach(eventName => dropzone.addEventListener(eventName, event => { event.preventDefault(); dropzone.classList.remove('is-dragging'); }));
  dropzone.addEventListener('drop', event => chooseFile(event.dataTransfer.files?.[0]));

  function beginProcessing() {
    imageBusy = true; syncControls();
    uploadButton.disabled = true;
    processing.hidden = false; uploadForm.hidden = true; imageResult.hidden = true; tabLoading.hidden = false;
    setImageStatus();
    const tips = ['نام کالاها و تعدادشان را بررسی می‌کنیم…', 'پس از آماده‌شدن، می‌توانید همه اقلام را اصلاح کنید.', 'قیمت محصولات از کاتالوگ سایت خوانده می‌شود.', 'هیچ قلمی بدون تأیید شما به سبد اضافه نمی‌شود.', 'بررسی بعضی تصاویر به زمان بیشتری نیاز دارد؛ ممنون از شکیبایی شما.'];
    let seconds = 0;
    elapsedLabel.textContent = '۰';
    processingMessage.textContent = tips[0];
    processingTimer = window.setInterval(() => {
      elapsedLabel.textContent = plainDigits.format(++seconds);
      if (seconds % 5 === 0) {
        processingMessage.classList.remove('is-changing');
        processingMessage.textContent = tips[Math.floor(seconds / 5) % tips.length];
        window.requestAnimationFrame(() => processingMessage.classList.add('is-changing'));
      }
    }, 1000);
  }

  function endProcessing() {
    window.clearInterval(processingTimer);
    processingTimer = null;
    imageBusy = false;
    processing.hidden = true; uploadForm.hidden = false; tabLoading.hidden = true;
    uploadButton.disabled = !selectedFile || remainingImages <= 0;
    imageResult.hidden = !invoiceRows.length;
    syncControls();
  }

  document.querySelector('[data-image-cancel]').addEventListener('click', () => imageController?.abort('cancelled'));

  function parseQuantity(value) {
    const normalized = String(value).replace(/[۰-۹]/g, digit => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(digit))).replace(/[٠-٩]/g, digit => String('٠١٢٣٤٥٦٧٨٩'.indexOf(digit))).replace(/[^0-9]/g, '');
    return Math.min(999, Math.max(1, Number(normalized) || 1));
  }

  function updateInvoiceTotal() {
    let total = 0, lines = 0, units = 0, searching = false;
    invoiceRows.forEach(row => {
      if (row.removed) return;
      if (row.searching) searching = true;
      if (row.product && !row.searching) {
        total += Number(row.product.price) * row.quantity;
        lines++; units += row.quantity;
      }
      if (row.fields) {
        row.fields.price.replaceChildren(element('span', '', row.product && !row.searching ? money(Number(row.product.price) * row.quantity) : 'بدون انتخاب'), element('small', '', 'جمع این قلم'));
        row.fields.minus.disabled = row.quantity <= 1;
        row.fields.plus.disabled = row.quantity >= 999;
      }
    });
    totalBox.textContent = money(total);
    countBox.textContent = digits.format(lines) + ' قلم · ' + digits.format(units) + ' عدد';
    confirmButton.disabled = !lines || searching;
    confirmButton.querySelector('span').textContent = searching ? 'در حال جست‌وجوی کالا…' : 'افزودن به سبد خرید';
  }

  function renderSelectedProduct(row) {
    const node = row.fields.selected;
    node.replaceChildren();
    node.hidden = !row.product || row.searching;
    if (!row.product || row.searching) return;
    const product = row.product;
    const thumb = element('span', 'ai-product-thumb');
    if (product.image && /^https?:\/\//i.test(product.image)) {
      const img = element('img'); img.src = product.image; img.alt = ''; img.loading = 'lazy'; img.referrerPolicy = 'no-referrer';
      img.addEventListener('error', () => { thumb.replaceChildren(icon('image')); }, {once: true});
      thumb.append(img);
    } else thumb.append(icon('image'));
    const info = element('div'); info.append(element('strong', '', product.name), element('small', '', 'کد ' + product.code + ' · قیمت واحد: ' + money(product.price)));
    node.append(thumb, info);
  }

  function fillChoices(row, products, preserve = false) {
    const select = row.fields.select;
    row.choices = Array.isArray(products) ? products.filter(p => p && typeof p.code === 'string' && typeof p.name === 'string') : [];
    select.replaceChildren();
    const placeholder = element('option', '', row.choices.length ? 'محصول درست را از کاتالوگ انتخاب کنید' : 'محصولی با این نام پیدا نشد');
    placeholder.value = ''; select.append(placeholder);
    row.choices.forEach((product, index) => { const option = element('option', '', product.name + ' · ' + money(product.price)); option.value = String(index); select.append(option); });
    row.product = preserve && row.product ? row.choices.find(p => p.code === row.product.code) || row.choices[0] || null : row.choices[0] || null;
    select.value = row.product ? String(row.choices.indexOf(row.product)) : '';
    select.disabled = !row.choices.length;
    row.searching = false;
    row.fields.hint.classList.remove('is-error');
    row.fields.hint.textContent = row.choices.length ? 'محصول پیشنهادی را با تصویرتان تطبیق دهید.' : 'کالایی پیدا نشد؛ نام را اصلاح کنید یا این قلم را حذف کنید.';
    renderSelectedProduct(row); updateInvoiceTotal();
  }

  async function lookupProducts(row) {
    const query = row.query.trim();
    if (query.length < 2) { row.searching = false; fillChoices(row, []); row.fields.hint.textContent = 'برای جست‌وجو دست‌کم دو حرف وارد کنید.'; return; }
    const version = ++row.version;
    row.controller?.abort();
    row.controller = new AbortController();
    row.searching = true;
    row.product = null;
    row.fields.select.disabled = true;
    row.fields.hint.textContent = 'در حال یافتن کالاهای مشابه…';
    row.fields.hint.classList.remove('is-error');
    renderSelectedProduct(row); updateInvoiceTotal();
    try {
      const data = await apiRequest(uploadForm, {action: 'product_search', query, conversation_id: uploadForm.dataset.conversationId}, {endpoint: uploadForm.dataset.productSearchEndpoint, signal: row.controller.signal});
      if (version !== row.version || row.removed) return;
      fillChoices(row, data.products);
    } catch (error) {
      if (version !== row.version || error.name === 'AbortError') return;
      fillChoices(row, []);
      row.fields.hint.textContent = error.message;
      row.fields.hint.classList.add('is-error');
    }
  }

  function setQuantity(row, value) {
    row.quantity = parseQuantity(value);
    row.fields.quantity.value = plainDigits.format(row.quantity);
    updateInvoiceTotal();
  }

  function buildInvoiceRow(data, index) {
    const row = {query: data.recognized_name, quantity: parseQuantity(data.quantity), product: null, choices: [], removed: false, searching: false, version: 0};
    const card = element('article', 'ai-modal-item');
    const active = element('div', 'ai-item-active');
    const top = element('div', 'ai-modal-item-top');
    const badge = element('div', 'ai-read-badge'); badge.append(element('span', '', digits.format(index + 1)), element('small', '', 'متن تصویر: ' + data.recognized_name));
    const remove = actionButton('ai-remove-row', 'trash', 'حذف');
    top.append(badge, remove);
    const fields = element('div', 'ai-item-fields');
    const nameField = element('div', 'ai-item-field');
    const nameLabel = element('label', '', 'نام کالا را جست‌وجو یا اصلاح کنید'); nameLabel.htmlFor = 'ai-product-name-' + index;
    const searchWrap = element('div', 'ai-search-wrap'); searchWrap.append(icon('search'));
    const search = element('input'); search.id = nameLabel.htmlFor; search.type = 'search'; search.value = row.query; search.placeholder = 'نام یا کد محصول'; search.autocomplete = 'off'; search.maxLength = 255;
    searchWrap.append(search); nameField.append(nameLabel, searchWrap);
    const selectField = element('div', 'ai-item-field');
    const selectLabel = element('label', '', 'گزینه‌های کاتالوگ'); selectLabel.htmlFor = 'ai-product-choice-' + index;
    const select = element('select'); select.id = selectLabel.htmlFor; selectField.append(selectLabel, select);
    const hint = element('div', 'ai-search-hint'); hint.setAttribute('role', 'status');
    fields.append(nameField, selectField, hint);
    const selected = element('div', 'ai-selected-product');
    const bottom = element('div', 'ai-item-bottom');
    const qtyArea = element('div', 'ai-edit-quantity'); qtyArea.append(element('span', '', 'تعداد'));
    const tools = element('div', 'ai-invoice-qty');
    const minus = actionButton('', 'minus', '', 'کم‌کردن تعداد این قلم');
    const quantity = element('input'); quantity.type = 'text'; quantity.inputMode = 'numeric'; quantity.maxLength = 3; quantity.value = plainDigits.format(row.quantity); quantity.setAttribute('aria-label', 'تعداد ' + data.recognized_name);
    const plus = actionButton('', 'plus', '', 'افزودن تعداد این قلم'); tools.append(minus, quantity, plus); qtyArea.append(tools);
    const price = element('div', 'ai-item-price'); bottom.append(qtyArea, price);
    active.append(top, fields, selected, bottom);
    const removedNote = element('div', 'ai-removed-note'); removedNote.hidden = true;
    removedNote.append(element('span', '', data.recognized_name + ' حذف شد.'));
    const undo = actionButton('ai-text-button', 'retry', 'بازگردانی'); removedNote.append(undo);
    card.append(active, removedNote); itemsBox.append(card);
    row.fields = {card, active, removedNote, select, search, quantity, hint, selected, price, minus, plus};
    remove.addEventListener('click', () => { row.removed = true; window.clearTimeout(row.debounce); row.controller?.abort(); row.version++; row.searching = false; active.hidden = true; removedNote.hidden = false; card.classList.add('is-removed'); updateInvoiceTotal(); });
    undo.addEventListener('click', () => { row.removed = false; active.hidden = false; removedNote.hidden = true; card.classList.remove('is-removed'); if (!row.product) lookupProducts(row); updateInvoiceTotal(); });
    minus.addEventListener('click', () => setQuantity(row, row.quantity - 1));
    plus.addEventListener('click', () => setQuantity(row, row.quantity + 1));
    quantity.addEventListener('input', () => { row.quantity = parseQuantity(quantity.value); updateInvoiceTotal(); });
    quantity.addEventListener('blur', () => setQuantity(row, quantity.value));
    select.addEventListener('change', () => { row.product = select.value === '' ? null : row.choices[Number(select.value)] || null; renderSelectedProduct(row); updateInvoiceTotal(); });
    search.addEventListener('input', () => {
      row.query = search.value; row.version++; row.controller?.abort(); window.clearTimeout(row.debounce);
      row.product = null; row.searching = true; select.disabled = true; hint.textContent = 'در حال جست‌وجوی نام جدید…';
      renderSelectedProduct(row); updateInvoiceTotal();
      row.debounce = window.setTimeout(() => lookupProducts(row), 500);
    });
    row.initialChoices = data.matches || [];
    return row;
  }

  function openInvoice() {
    if (!invoiceRows.length) return;
    modalReturnFocus = document.activeElement;
    modalFeedback.hidden = true;
    document.body.classList.add('ai-modal-is-open');
    if (!modal.open) modal.showModal();
    modal.querySelector('[data-modal-close]').focus({preventScroll: true});
    invoiceRows.forEach(row => { if (!row.removed && !row.product && row.query.trim().length >= 2 && row.choices.length) lookupProducts(row); });
    updateInvoiceTotal();
  }

  function renderInvoice(data) {
    clearInvoice();
    invoiceRows = data.map(buildInvoiceRow);
    invoiceRows.forEach(row => fillChoices(row, row.initialChoices));
    document.querySelector('[data-invoice-count]').textContent = digits.format(data.length) + ' قلم از تصویر خوانده شد';
    imageResult.hidden = false;
    updateInvoiceTotal();
    openInvoice();
  }

  document.querySelectorAll('[data-modal-close]').forEach(button => button.addEventListener('click', () => modal.close()));
  document.querySelector('[data-invoice-reopen]').addEventListener('click', openInvoice);
  modal.addEventListener('close', () => { document.body.classList.remove('ai-modal-is-open'); cancelLookups(); updateInvoiceTotal(); modalReturnFocus?.focus({preventScroll: true}); });
  modal.addEventListener('click', event => { if (event.target !== modal) return; const rect = modal.getBoundingClientRect(); if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) modal.close(); });

  confirmButton.addEventListener('click', () => {
    const selected = invoiceRows.filter(row => !row.removed && row.product && !row.searching);
    if (!selected.length) { modalFeedback.textContent = 'دست‌کم یک محصول را از کاتالوگ انتخاب کنید.'; modalFeedback.hidden = false; return; }
    try {
      let cart;
      try { const saved = JSON.parse(localStorage.getItem('sabzi-store-cart-v1') || '[]'); cart = Array.isArray(saved) ? saved.filter(item => item && typeof item.code === 'string' && Number(item.quantity) > 0) : []; }
      catch (_) { cart = []; }
      selected.forEach(row => {
        const product = row.product;
        const existing = cart.find(item => item.code === product.code);
        if (existing) { existing.quantity = Math.min(999, Math.max(1, Math.floor(Number(existing.quantity) || 0)) + row.quantity); existing.name = product.name; existing.price = Number(product.price) || 0; existing.unit = product.unit || 'عدد'; }
        else cart.push({code: product.code, name: product.name, price: Number(product.price) || 0, unit: product.unit || 'عدد', quantity: row.quantity});
      });
      localStorage.setItem('sabzi-store-cart-v1', JSON.stringify(cart));
      confirmButton.disabled = true;
      confirmButton.querySelector('span').textContent = 'در حال بازکردن سبد خرید…';
      window.location.assign(uploadForm.dataset.checkoutUrl);
    } catch (_) { modalFeedback.textContent = 'سبد ذخیره نشد. تنظیمات ذخیره‌سازی مرورگر را بررسی و دوباره تلاش کنید.'; modalFeedback.hidden = false; }
  });

  uploadForm.addEventListener('submit', async event => {
    event.preventDefault();
    if (!selectedFile || imageBusy) return;
    if (remainingImages <= 0) { setImageStatus("سهمیه امروز شما تمام شده است. روزانه ۵ تصویر می‌توانید ارسال کنید.", true); return; }
    imageController = new AbortController();
    const controller = imageController;
    const timeout = window.setTimeout(() => controller.abort('timeout'), 85000);
    beginProcessing();
    try {
      const body = new FormData(); body.append('image', selectedFile); body.append('message', ''); body.append('conversation_id', uploadForm.dataset.conversationId);
      const data = await apiRequest(uploadForm, body, {signal: controller.signal});
      if (controller.signal.aborted) return;
      endProcessing();
      if (Array.isArray(data.invoice_items) && data.invoice_items.length) renderInvoice(data.invoice_items);
      else setImageStatus(data.reply || 'اقلامی پیدا نشد. تصویر واضح‌تری انتخاب کنید.');
    } catch (error) {
      endProcessing();
      if (error.name === 'AbortError') setImageStatus(controller.signal.reason === 'cancelled' ? 'بررسی متوقف شد. می‌توانید دوباره از همین تصویر شروع کنید.' : 'بررسی بیشتر از معمول طول کشید. لطفاً دوباره تلاش کنید.');
      else setImageStatus(error.message, true);
    } finally { window.clearTimeout(timeout); if (imageController === controller) imageController = null; refreshImageUsage(); }
  });
  window.addEventListener('pagehide', () => { window.clearInterval(processingTimer); imageController?.abort(); cancelLookups(); if (previewUrl) URL.revokeObjectURL(previewUrl); });
})();
