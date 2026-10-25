/* Baba Saleh 2027 — theme scripts
 * Native web components, no dependencies.
 */
(() => {
  const isRTL = document.documentElement.dir === 'rtl';
  const routes = window.theme?.routes ?? {};
  const strings = window.theme?.strings ?? {};

  /* ---------- Helpers ---------- */
  const parseHTML = (html) => new DOMParser().parseFromString(html, 'text/html');

  const debounce = (fn, wait = 300) => {
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), wait);
    };
  };

  const toast = (message) => {
    const el = document.querySelector('.toast');
    if (!el) return;
    el.textContent = message;
    el.hidden = false;
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => {
      el.hidden = true;
    }, 2600);
  };

  const updateCartCount = (count) => {
    for (const el of document.querySelectorAll('[data-cart-count]')) {
      el.textContent = count;
      el.classList.toggle('is-empty', count === 0);
      el.classList.remove('is-bumped');
      void el.offsetWidth;
      el.classList.add('is-bumped');
    }
  };

  /** Replace the inner HTML of `selector` in the page with the same element from `html`. */
  const swapFromHTML = (html, selector, root = document) => {
    const doc = parseHTML(html);
    const fresh = doc.querySelector(selector);
    const current = root.querySelector(selector);
    if (fresh && current) current.innerHTML = fresh.innerHTML;
  };

  const sectionIdsForCart = () => {
    const ids = [];
    if (document.getElementById('CartDrawer')) ids.push('cart-drawer');
    const page = document.querySelector('cart-page');
    if (page) ids.push(page.dataset.sectionId);
    return ids;
  };

  const renderCartSections = (sections) => {
    if (!sections) return;
    const drawer = document.getElementById('CartDrawer');
    if (sections['cart-drawer']) swapFromHTML(sections['cart-drawer'], '#CartDrawer .drawer__panel');
    const page = document.querySelector('cart-page');
    if (page && sections[page.dataset.sectionId]) {
      const doc = parseHTML(sections[page.dataset.sectionId]);
      // Swap only the dynamic parts so express checkout buttons are left alone.
      for (const selector of ['[data-cart-items]', '[data-cart-summary]']) {
        const fresh = doc.querySelector(selector);
        const current = page.querySelector(selector);
        if (fresh && current) current.innerHTML = fresh.innerHTML;
      }
      // Cart emptied: re-render the whole section to show the empty state.
      if (!doc.querySelector('[data-cart-items]') || !page.querySelector('[data-cart-items]')) {
        swapFromHTML(sections[page.dataset.sectionId], 'cart-page');
      }
    }
    // Keep keyboard focus inside the open drawer after its content is replaced.
    if (drawer?.hasAttribute('open') && !drawer.contains(document.activeElement)) {
      drawer.querySelector('.drawer__panel')?.focus();
    }
  };

  /** Read an Ajax API response; only show Shopify's own message for 422 errors. */
  const readCartResponse = async (response) => {
    let data = null;
    try {
      data = await response.json();
    } catch {
      throw new Error(strings.cartError);
    }
    if (!response.ok || data.status) {
      throw new Error((response.status === 422 && (data.description || data.message)) || strings.cartError);
    }
    return data;
  };

  /* ---------- Focus trap for dialogs ---------- */
  const focusable = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select, textarea, [tabindex]:not([tabindex="-1"])';

  /* ---------- Drawer ---------- */
  class DrawerPanel extends HTMLElement {
    connectedCallback() {
      this.addEventListener('click', (event) => {
        if (event.target.closest('[data-drawer-close]')) this.close();
      });
      this.addEventListener('keydown', (event) => {
        if (event.key === 'Tab') this.#trapFocus(event);
      });
      // Escape closes the drawer even if focus has left the panel.
      this.onKeyup = (event) => {
        if (event.key === 'Escape') this.close();
      };
    }

    disconnectedCallback() {
      document.removeEventListener('keyup', this.onKeyup);
    }

    open(opener) {
      this.opener = opener ?? document.activeElement;
      this.setAttribute('open', '');
      document.addEventListener('keyup', this.onKeyup);
      document.body.classList.add('scroll-lock');
      this.opener?.setAttribute?.('aria-expanded', 'true');
      requestAnimationFrame(() => this.querySelector('.drawer__panel')?.focus());
    }

    close() {
      if (!this.hasAttribute('open')) return;
      this.removeAttribute('open');
      document.removeEventListener('keyup', this.onKeyup);
      document.body.classList.remove('scroll-lock');
      if (!this.opener?.isConnected || this.opener.closest('[hidden]')) {
        this.opener = document.querySelector(`[data-drawer-open="${this.id}"]`);
      }
      this.opener?.setAttribute?.('aria-expanded', 'false');
      this.opener?.focus?.();
    }

    #trapFocus(event) {
      const items = [...this.querySelectorAll(focusable)].filter((el) => el.offsetParent !== null);
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  }
  customElements.define('drawer-panel', DrawerPanel);

  class CartDrawer extends DrawerPanel {
    connectedCallback() {
      super.connectedCallback();
      bindCartControls(this);
    }
  }
  customElements.define('cart-drawer', CartDrawer);

  document.addEventListener('click', (event) => {
    const opener = event.target.closest('[data-drawer-open]');
    if (!opener) return;
    const drawer = document.getElementById(opener.dataset.drawerOpen);
    if (!drawer) return;
    event.preventDefault();
    drawer.open(opener);
  });

  /* ---------- Cart line updates (drawer + page) ---------- */
  // Cart requests run one after another so line changes never race each other.
  let cartQueue = Promise.resolve();

  const changeLine = (key, quantity, scope) => {
    cartQueue = cartQueue.then(async () => {
      const item = scope.querySelector(`.cart-item[data-key="${CSS.escape(key)}"]`);
      item?.classList.add('is-loading');
      const tracked = item && readItem(item);
      try {
        const response = await fetch(`${routes.cartChange}.js`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify({ id: key, quantity, sections: sectionIdsForCart(), sections_url: window.location.pathname }),
        });
        const cart = await readCartResponse(response);
        if (tracked && quantity < tracked.quantity) {
          const removed = { ...tracked, quantity: tracked.quantity - quantity };
          pushEcommerce('remove_from_cart', { currency: currency(), value: removed.price * removed.quantity, items: [removed] });
        }
        renderCartSections(cart.sections);
        updateCartCount(cart.item_count);
      } catch (error) {
        item?.classList.remove('is-loading');
        const input = item?.querySelector('[data-cart-quantity]');
        if (input) input.value = input.defaultValue;
        toast(error.message || strings.cartError);
      }
    });
    return cartQueue;
  };

  function bindCartControls(scope) {
    const timers = new Map();
    scope.addEventListener('change', (event) => {
      const input = event.target.closest('[data-cart-quantity]');
      if (input) {
        const key = input.closest('.cart-item')?.dataset.key;
        if (key && input.value !== '') {
          clearTimeout(timers.get(key));
          timers.set(key, setTimeout(() => changeLine(key, Math.max(0, Number(input.value)), scope), 400));
        }
      }
      const note = event.target.closest('textarea[name="note"]');
      if (note) {
        fetch(`${routes.cartUpdate}.js`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ note: note.value }),
        });
      }
    });
    scope.addEventListener('click', (event) => {
      const remove = event.target.closest('[data-cart-remove]');
      const key = remove?.closest('.cart-item')?.dataset.key;
      if (key) changeLine(key, 0, scope);
    });
  }

  class CartPage extends HTMLElement {
    connectedCallback() {
      bindCartControls(this);
    }
  }
  customElements.define('cart-page', CartPage);

  /* ---------- Quantity input ---------- */
  class QuantityInput extends HTMLElement {
    connectedCallback() {
      this.input = this.querySelector('input');
      this.addEventListener('click', (event) => {
        const button = event.target.closest('button');
        if (!button) return;
        const min = Number(this.input.min || 0);
        const current = Number(this.input.value || 0);
        const next = button.name === 'plus' ? current + 1 : Math.max(min, current - 1);
        if (next === current) return;
        this.input.value = next;
        this.input.dispatchEvent(new Event('change', { bubbles: true }));
      });
    }
  }
  customElements.define('quantity-input', QuantityInput);

  /* ---------- Add to cart (all product forms) ---------- */
  document.addEventListener('submit', async (event) => {
    const form = event.target.closest('form[data-product-form]');
    if (!form) return;
    event.preventDefault();

    const submitter = event.submitter ?? form.querySelector('[type="submit"]');
    const buttons = [submitter];
    for (const button of document.querySelectorAll(`[form="${form.id}"][data-add-button]`)) buttons.push(button);
    for (const button of buttons) button?.classList.add('is-loading');

    const error = form.querySelector('[data-form-error]');
    if (error) error.hidden = true;

    const body = new FormData(form);
    if (submitter?.name === 'id') body.set('id', submitter.value);
    const sections = sectionIdsForCart();
    if (sections.length) {
      body.append('sections', sections.join(','));
      body.append('sections_url', window.location.pathname);
    }

    try {
      const response = await fetch(`${routes.cartAdd}.js`, {
        method: 'POST',
        headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        body,
      });
      const data = await readCartResponse(response);
      trackAddToCart(data);

      const cart = await (await fetch(`${routes.cart}.js`)).json();
      updateCartCount(cart.item_count);
      renderCartSections(data.sections);

      form.closest('quick-add')?.close?.();
      const drawer = document.getElementById('CartDrawer');
      if (drawer && window.theme.cartType === 'drawer') {
        drawer.open(submitter);
      } else {
        toast(strings.added);
      }
    } catch (err) {
      if (error) {
        error.textContent = err.message || strings.cartError;
        error.hidden = false;
      } else {
        toast(err.message || strings.cartError);
      }
    } finally {
      for (const button of buttons) button?.classList.remove('is-loading');
    }
  });

  /* ---------- Analytics (GTM dataLayer, GA4, Meta Pixel) ---------- */
  function trackAddToCart(item) {
    if (!item || !item.variant_id) return;
    const currency = window.Shopify?.currency?.active;
    const value = (item.final_line_price ?? item.price * item.quantity) / 100;
    const ecommerce = {
      currency,
      value,
      items: [{
        item_id: item.sku || String(item.product_id),
        item_name: item.product_title,
        item_brand: item.vendor,
        item_category: item.product_type,
        item_variant: item.variant_title || undefined,
        price: item.price / 100,
        quantity: item.quantity,
      }],
    };
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({ ecommerce: null });
    window.dataLayer.push({ event: 'add_to_cart', ecommerce });
    if (typeof window.gtag === 'function') window.gtag('event', 'add_to_cart', ecommerce);
    if (typeof window.fbq === 'function') {
      window.fbq('track', 'AddToCart', {
        content_ids: [String(item.variant_id)],
        content_name: item.product_title,
        content_type: 'product',
        value,
        currency,
      });
    }
  }

  /* ---------- Product list analytics (view_item_list, select_item, remove_from_cart) ---------- */
  const pushEcommerce = (event, ecommerce) => {
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({ ecommerce: null });
    window.dataLayer.push({ event, ecommerce });
    if (typeof window.gtag === 'function') window.gtag('event', event, ecommerce);
  };
  const readItem = (el) => {
    try {
      return JSON.parse(el.dataset.item);
    } catch {
      return null;
    }
  };
  const listName = (el) =>
    el.closest('section, .shopify-section')?.querySelector('h1, h2, [aria-selected="true"]')?.textContent.trim() || document.title;
  const currency = () => window.theme?.currency || window.Shopify?.currency?.active;

  const listObserver =
    'IntersectionObserver' in window
      ? new IntersectionObserver(
          (entries) => {
            for (const entry of entries) {
              if (!entry.isIntersecting) continue;
              listObserver.unobserve(entry.target);
              const name = listName(entry.target);
              const items = [...entry.target.querySelectorAll('[data-item]')]
                .map((card, index) => ({ ...readItem(card), index, item_list_name: name }))
                .filter((item) => item.item_id);
              if (items.length) pushEcommerce('view_item_list', { item_list_name: name, currency: currency(), items });
            }
          },
          { threshold: 0.25 }
        )
      : null;
  const observeLists = (root = document) => {
    for (const list of root.querySelectorAll('[data-product-grid], [data-slider]')) {
      if (list.dataset.listTracked || !list.querySelector('[data-item]')) continue;
      list.dataset.listTracked = 'true';
      listObserver?.observe(list);
    }
  };

  document.addEventListener('click', (event) => {
    const link = event.target.closest('.card__link');
    const card = link?.closest('[data-item]');
    const item = card && readItem(card);
    if (item) pushEcommerce('select_item', { item_list_name: listName(card), currency: currency(), items: [{ ...item, item_list_name: listName(card) }] });
  });

  /* ---------- Quick add on product cards ---------- */
  class QuickAdd extends HTMLElement {
    connectedCallback() {
      this.toggle = this.querySelector('[data-quick-add-toggle]');
      this.panel = this.querySelector('.quick-add__panel');
      if (!this.toggle || !this.panel) return;
      this.toggle.addEventListener('click', (event) => {
        event.preventDefault();
        this.panel.hidden ? this.open() : this.close();
      });
      this.onOutside = (event) => {
        if (!this.contains(event.target)) this.close();
      };
      this.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && !this.panel.hidden) {
          this.close();
          this.toggle.focus();
        }
      });
    }

    disconnectedCallback() {
      document.removeEventListener('click', this.onOutside);
    }

    open() {
      this.panel.hidden = false;
      this.toggle.setAttribute('aria-expanded', 'true');
      this.toggle.hidden = true;
      this.panel.querySelector('button')?.focus();
      document.addEventListener('click', this.onOutside);
    }

    close() {
      if (!this.panel) return;
      this.panel.hidden = true;
      this.toggle.hidden = false;
      this.toggle.setAttribute('aria-expanded', 'false');
      document.removeEventListener('click', this.onOutside);
    }
  }
  customElements.define('quick-add', QuickAdd);

  /* ---------- Frequently bought together (product page) ---------- */
  class BoughtTogether extends HTMLElement {
    connectedCallback() {
      this.mainPrice = Number(this.querySelector('[data-fbt-main-price]')?.dataset.price || 0);
      this.mainPrice = this.mainPrice || this.parsePrice();
      this.addEventListener('change', () => this.update());
      document.addEventListener('variant:change', (event) => {
        const v = event.detail?.variant;
        if (!v) return;
        this.mainPrice = v.price;
        const el = this.querySelector('[data-fbt-main-price]');
        if (el) el.textContent = this.money(v.price);
        this.update();
      });
      this.querySelector('[data-fbt-add]')?.addEventListener('click', () => this.add());
    }

    parsePrice() {
      const input = document.querySelector('[data-variant-id]');
      const v = JSON.parse(document.querySelector('[data-variants]')?.textContent || '[]').find((x) => String(x.id) === input?.value);
      return v?.price || 0;
    }

    money(cents) {
      const amount = cents / 100;
      const fmt = this.dataset.moneyFormat || '{{amount}}';
      return fmt.replace(/\{\{\s*(\w+)\s*\}\}/, (_, key) => {
        const decimals = /no_decimals/.test(key) ? 0 : 2;
        let text = amount.toFixed(decimals).replace(/\B(?=(\d{3})+(?!\d))/g, /comma_separator/.test(key) ? '.' : ',');
        if (/comma_separator/.test(key)) text = text.replace(/\.(\d{2})$/, ',$1');
        return text;
      });
    }

    picked() {
      return [...this.querySelectorAll('[data-fbt-item]')].filter((item) => item.querySelector('[data-fbt-toggle]').checked);
    }

    update() {
      let total = this.mainPrice;
      for (const item of this.querySelectorAll('[data-fbt-item]')) {
        const on = item.querySelector('[data-fbt-toggle]').checked;
        item.classList.toggle('is-off', !on);
        const variant = item.querySelector('[data-fbt-variant]');
        const option = variant.tagName === 'SELECT' ? variant.selectedOptions[0] : variant;
        const price = Number(option.dataset.price || 0);
        const priceEl = item.querySelector('.fbt__price');
        if (priceEl) priceEl.textContent = this.money(price);
        if (on) total += price;
      }
      const totalEl = this.querySelector('[data-fbt-total]');
      if (totalEl) totalEl.textContent = this.money(total);
      const button = this.querySelector('[data-fbt-add]');
      if (button) button.textContent = this.picked().length ? button.dataset.labelMany : button.dataset.labelOne;
    }

    async add() {
      const button = this.querySelector('[data-fbt-add]');
      const error = this.querySelector('[data-fbt-error]');
      const main = document.querySelector('[data-variant-id]');
      const items = [{ id: Number(main?.value), quantity: 1 }];
      for (const item of this.picked()) items.push({ id: Number(item.querySelector('[data-fbt-variant]').value), quantity: 1 });
      button.classList.add('is-loading');
      if (error) error.hidden = true;
      try {
        const sections = sectionIdsForCart();
        const response = await fetch(`${routes.cartAdd}.js`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify({ items, sections: sections.join(','), sections_url: window.location.pathname }),
        });
        const data = await readCartResponse(response);
        for (const line of data.items || []) trackAddToCart(line);
        const cart = await (await fetch(`${routes.cart}.js`)).json();
        updateCartCount(cart.item_count);
        renderCartSections(data.sections);
        const drawer = document.getElementById('CartDrawer');
        if (drawer && window.theme.cartType === 'drawer') drawer.open(button);
        else toast(strings.added);
      } catch (err) {
        if (error) {
          error.textContent = err.message || strings.cartError;
          error.hidden = false;
        }
      } finally {
        button.classList.remove('is-loading');
      }
    }
  }
  customElements.define('bought-together', BoughtTogether);

  /* ---------- Variant picker ---------- */
  class VariantPicker extends HTMLElement {
    connectedCallback() {
      this.variants = JSON.parse(this.querySelector('[data-variants]')?.textContent || '[]');
      this.section = this.closest('product-info');
      this.addEventListener('change', () => this.#onChange());
    }

    #selectedOptions() {
      return [...this.querySelectorAll('fieldset')].map((fieldset) => fieldset.querySelector('input:checked')?.value);
    }

    async #onChange() {
      const options = this.#selectedOptions();
      for (const [index, fieldset] of [...this.querySelectorAll('fieldset')].entries()) {
        const label = fieldset.querySelector('[data-selected-value]');
        if (label) label.textContent = options[index] ?? '';
      }

      const variant = this.variants.find((v) => v.options.every((value, i) => value === options[i]));
      const idInput = this.section?.querySelector('[data-variant-id]');
      const addButtons = this.section?.querySelectorAll('[data-add-button]') ?? [];

      const paymentButton = this.section?.querySelector('.product__payment');
      this.abort?.abort();

      if (!variant) {
        if (idInput) idInput.disabled = true;
        paymentButton?.setAttribute('hidden', '');
        for (const button of addButtons) {
          button.disabled = true;
          const label = button.querySelector('[data-add-label]');
          if (label) label.textContent = strings.unavailable;
        }
        return;
      }

      if (idInput) {
        idInput.disabled = false;
        idInput.value = variant.id;
      }
      paymentButton?.toggleAttribute('hidden', !variant.available);
      document.dispatchEvent(new CustomEvent('variant:change', { detail: { variant } }));
      for (const button of addButtons) {
        button.disabled = !variant.available;
        const label = button.querySelector('[data-add-label]');
        if (label) label.textContent = variant.available ? strings.addToCart : strings.soldOut;
      }

      const url = new URL(window.location.href);
      url.searchParams.set('variant', variant.id);
      window.history.replaceState({}, '', url);

      if (variant.featured_media) this.section?.showMedia(variant.featured_media.id);

      // Refresh price + option availability from the server-rendered section.
      const sectionId = this.dataset.sectionId;
      const productUrl = this.section?.dataset.url;
      if (!sectionId || !productUrl) return;
      this.abort = new AbortController();
      try {
        const response = await fetch(`${productUrl}?variant=${variant.id}&section_id=${sectionId}`, { signal: this.abort.signal });
        if (!response.ok) return;
        const html = await response.text();
        const doc = parseHTML(html);
        const freshPrices = doc.querySelectorAll('[data-price-container]');
        const currentPrices = this.section.querySelectorAll('[data-price-container]');
        for (const [i, el] of [...currentPrices].entries()) {
          if (freshPrices[i]) el.innerHTML = freshPrices[i].innerHTML;
        }
        const freshLabels = doc.querySelectorAll('variant-picker .option__label');
        const currentLabels = this.querySelectorAll('.option__label');
        for (const [i, el] of [...currentLabels].entries()) {
          if (freshLabels[i]) el.className = freshLabels[i].className;
        }
      } catch {
        /* price refresh is progressive enhancement */
      }
    }
  }
  customElements.define('variant-picker', VariantPicker);

  /* ---------- Product page ---------- */
  class ProductInfo extends HTMLElement {
    connectedCallback() {
      this.mediaList = this.querySelector('[data-media-list]');
      this.counter = this.querySelector('[data-media-current]');
      this.stickyBar = this.querySelector('[data-sticky-bar]');
      this.mainButton = this.querySelector('.product__add');

      if (this.mediaList && this.counter) {
        this.mediaList.addEventListener(
          'scroll',
          debounce(() => {
            const width = this.mediaList.clientWidth;
            const index = Math.round(Math.abs(this.mediaList.scrollLeft) / width);
            this.counter.textContent = index + 1;
          }, 60),
          { passive: true }
        );
      }

      if (this.stickyBar && this.mainButton) {
        const observer = new IntersectionObserver(([entry]) => {
          const show = !entry.isIntersecting && entry.boundingClientRect.top < 0;
          this.stickyBar.classList.toggle('is-visible', show);
          this.stickyBar.setAttribute('aria-hidden', String(!show));
          this.stickyBar.querySelector('button')?.setAttribute('tabindex', show ? '0' : '-1');
        });
        observer.observe(this.mainButton);
      }
    }

    showMedia(mediaId) {
      const item = this.querySelector(`[data-media-id="${mediaId}"]`);
      if (!item || !this.mediaList) return;
      if (window.matchMedia('(min-width: 990px)').matches) {
        this.mediaList.prepend(item);
      } else {
        this.mediaList.scrollTo({ left: item.offsetLeft - this.mediaList.offsetLeft, behavior: 'smooth' });
      }
    }
  }
  customElements.define('product-info', ProductInfo);

  /* ---------- Product reviews ---------- */
  // "Show more" reveals the next page of server-rendered reviews (no extra requests).
  class ProductReviews extends HTMLElement {
    connectedCallback() {
      this.more = this.querySelector('[data-reviews-more]');
      if (!this.more) return;
      this.more.hidden = false;
      this.more.addEventListener('click', () => {
        const hidden = [...this.querySelectorAll('[data-review][hidden]')];
        const next = hidden.slice(0, Number(this.dataset.pageSize) || 5);
        for (const review of next) review.hidden = false;
        next[0]?.focus({ preventScroll: true });
        if (hidden.length <= next.length) this.more.remove();
      });
    }
  }
  customElements.define('product-reviews', ProductReviews);

  // Review form = Shopify contact form (hCaptcha is added by Shopify). Extra bot checks:
  // a honeypot field people never see, and a minimum of 3 s between render and submit.
  class ReviewForm extends HTMLElement {
    connectedCallback() {
      this.renderedAt = Date.now();
      this.form = this.querySelector('form');
      this.error = this.querySelector('[data-review-error]');
      this.form?.addEventListener('submit', (event) => this.#onSubmit(event));

      // After the post Shopify reloads the page at #ReviewForm-…: show the outcome.
      const message = this.querySelector('[data-review-message]');
      if (message) {
        const details = this.querySelector('details');
        if (details) details.open = true;
        requestAnimationFrame(() => {
          message.scrollIntoView({ block: 'center' });
          message.focus({ preventScroll: true });
        });
      }
    }

    #onSubmit(event) {
      const honeypot = this.form.querySelector('[data-honeypot]');
      let reason = '';
      if (honeypot && honeypot.value.trim()) reason = this.dataset.errorBlocked;
      else if (Date.now() - this.renderedAt < 3000) reason = this.dataset.errorFast;
      if (reason) {
        event.preventDefault();
        if (this.error) {
          this.error.textContent = reason;
          this.error.hidden = false;
        }
        return;
      }
      if (this.error) this.error.hidden = true;
      this.form.querySelector('[type="submit"]')?.classList.add('is-loading');
    }
  }
  customElements.define('review-form', ReviewForm);

  /* ---------- Sliders (scroll-snap) ---------- */
  const bindSlider = (root) => {
    const slider = root.querySelector('[data-slider]:not([hidden] [data-slider])') ?? root.querySelector('[data-slider]');
    const prev = root.querySelector('[data-slider-prev]');
    const next = root.querySelector('[data-slider-next]');
    if (!prev || !next) return;

    const activeSlider = () => {
      for (const s of root.querySelectorAll('[data-slider]')) {
        if (s.offsetParent !== null) return s;
      }
      return slider;
    };

    const update = () => {
      const s = activeSlider();
      if (!s) return;
      const max = s.scrollWidth - s.clientWidth - 2;
      const position = Math.abs(s.scrollLeft);
      prev.disabled = position <= 2;
      next.disabled = position >= max;
    };

    const step = (direction) => {
      const s = activeSlider();
      if (!s) return;
      const amount = s.clientWidth * 0.8 * direction * (isRTL ? -1 : 1);
      s.scrollBy({ left: amount, behavior: 'smooth' });
    };

    prev.addEventListener('click', () => step(-1));
    next.addEventListener('click', () => step(1));
    for (const s of root.querySelectorAll('[data-slider]')) s.addEventListener('scroll', debounce(update, 50), { passive: true });
    root.addEventListener('slider:refresh', update);
    if ('ResizeObserver' in window) new ResizeObserver(() => update()).observe(root);
    update();
  };

  class ProductTabs extends HTMLElement {
    connectedCallback() {
      this.tabs = [...this.querySelectorAll('[role="tab"]')];
      for (const tab of this.tabs) {
        tab.addEventListener('click', () => this.select(tab));
        tab.addEventListener('keydown', (event) => this.#onKey(event, tab));
      }
      bindSlider(this);
    }

    select(tab) {
      for (const t of this.tabs) {
        const selected = t === tab;
        t.setAttribute('aria-selected', String(selected));
        t.tabIndex = selected ? 0 : -1;
        const panel = document.getElementById(t.getAttribute('aria-controls'));
        if (panel) panel.hidden = !selected;
        if (selected && panel) this.#loadCards(panel);
      }
      revealAll(this);
      this.dispatchEvent(new Event('slider:refresh'));
    }

    // Hidden tabs are rendered as a placeholder; fetch their cards the first time they open.
    async #loadCards(panel) {
      const lazy = panel.querySelector('[data-lazy-cards]');
      if (!lazy || lazy.dataset.loading) return;
      lazy.dataset.loading = 'true';
      try {
        const url = new URL(lazy.dataset.lazyCards, window.location.origin);
        const limit = Number(url.searchParams.get('limit')) || 12;
        const html = await (await fetch(url)).text();
        const doc = parseHTML(`<ul>${html}</ul>`);
        const items = [...doc.querySelectorAll('ul > li')].slice(0, limit);
        if (items.length) lazy.replaceWith(...items);
        revealAll(panel);
        this.dispatchEvent(new Event('slider:refresh'));
      } catch {
        delete lazy.dataset.loading;
      }
    }

    #onKey(event, tab) {
      const forward = isRTL ? 'ArrowLeft' : 'ArrowRight';
      const backward = isRTL ? 'ArrowRight' : 'ArrowLeft';
      if (event.key !== forward && event.key !== backward) return;
      const index = this.tabs.indexOf(tab);
      const next = this.tabs[(index + (event.key === forward ? 1 : -1) + this.tabs.length) % this.tabs.length];
      next.focus();
      this.select(next);
    }
  }
  customElements.define('product-tabs', ProductTabs);

  class ProductRecommendations extends HTMLElement {
    connectedCallback() {
      const observer = new IntersectionObserver(
        async ([entry]) => {
          if (!entry.isIntersecting) return;
          observer.disconnect();
          try {
            const html = await (await fetch(this.dataset.url)).text();
            const fresh = parseHTML(html).querySelector('product-recommendations');
            if (fresh && fresh.innerHTML.trim()) {
              this.innerHTML = fresh.innerHTML;
              revealAll(this);
            }
          } catch {
            /* ignore */
          }
        },
        { rootMargin: '0px 0px 400px 0px' }
      );
      observer.observe(this);
    }
  }
  customElements.define('product-recommendations', ProductRecommendations);

  /* ---------- Hero slideshow ---------- */
  class HeroSlideshow extends HTMLElement {
    connectedCallback() {
      this.track = this.querySelector('[data-track]');
      this.slides = [...this.querySelectorAll('.hero__slide')];
      this.dots = [...this.querySelectorAll('.hero__dot')];
      this.index = 0;
      this.interval = Number(this.dataset.interval) || 6000;
      this.style.setProperty('--hero-interval', `${this.interval}ms`);
      this.slides[0]?.classList.add('is-active');

      for (const dot of this.dots) {
        dot.addEventListener('click', () => {
          this.goTo(Number(dot.dataset.index));
          this.restart();
        });
      }

      this.track.addEventListener(
        'scroll',
        debounce(() => {
          const index = Math.round(Math.abs(this.track.scrollLeft) / this.track.clientWidth);
          if (index !== this.index) this.#setActive(index);
        }, 80),
        { passive: true }
      );

      const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      if (this.dataset.autoplay === 'true' && this.slides.length > 1 && !reduced) {
        this.play();
        this.addEventListener('mouseenter', () => this.pause());
        this.addEventListener('mouseleave', () => {
          if (!this.contains(document.activeElement)) this.play();
        });
        this.addEventListener('focusin', () => this.pause());
        this.addEventListener('focusout', (event) => {
          if (!this.contains(event.relatedTarget) && !this.matches(':hover')) this.play();
        });
      }
    }

    #setActive(index) {
      this.index = index;
      for (const [i, slide] of this.slides.entries()) slide.classList.toggle('is-active', i === index);
      for (const [i, dot] of this.dots.entries()) {
        dot.setAttribute('aria-selected', String(i === index));
        // restart progress animation
        const fill = dot.querySelector('.hero__dot-fill');
        if (fill && i === index) {
          fill.style.animation = 'none';
          void fill.offsetWidth;
          fill.style.animation = '';
        }
      }
    }

    goTo(index) {
      const target = (index + this.slides.length) % this.slides.length;
      const slide = this.slides[target];
      this.track.scrollTo({ left: slide.offsetLeft - this.track.offsetLeft, behavior: 'smooth' });
      this.#setActive(target);
    }

    play() {
      this.classList.remove('is-paused');
      clearInterval(this.timer);
      this.timer = setInterval(() => this.goTo(this.index + 1), this.interval);
    }

    pause() {
      this.classList.add('is-paused');
      clearInterval(this.timer);
    }

    restart() {
      if (this.dataset.autoplay === 'true' && this.timer && !this.classList.contains('is-paused')) this.play();
    }

    disconnectedCallback() {
      clearInterval(this.timer);
    }
  }
  customElements.define('hero-slideshow', HeroSlideshow);

  /* ---------- Countdown ---------- */
  class CountdownTimer extends HTMLElement {
    connectedCallback() {
      this.parts = {
        days: this.querySelector('[data-days]'),
        hours: this.querySelector('[data-hours]'),
        minutes: this.querySelector('[data-minutes]'),
        seconds: this.querySelector('[data-seconds]'),
      };
      // data-end is a Unix timestamp (seconds) rendered in the shop's time zone by Liquid.
      const end = Number(this.dataset.end) * 1000;
      this.fixedEnd = end > 0 ? end : null;
      this.cycle = Number(this.dataset.cycleHours) * 3600 * 1000 || 0;
      this.#tick();
      this.timer = setInterval(() => this.#tick(), 1000);
    }

    // With no (or a past) end date the timer restarts every `cycle` (e.g. 4½ days), counted from a
    // fixed start (1 Jan 2026, 00:00 Cairo) so every visitor sees the same time left;
    // with no cycle it runs to the next local midnight, every day.
    #target() {
      const now = Date.now();
      if (this.fixedEnd && this.fixedEnd > now) return this.fixedEnd;
      if (this.cycle > 0) {
        const start = Date.UTC(2025, 11, 31, 22);
        return start + (Math.floor((now - start) / this.cycle) + 1) * this.cycle;
      }
      const midnight = new Date();
      midnight.setHours(24, 0, 0, 0);
      return midnight.getTime();
    }

    #tick() {
      const remaining = Math.max(0, this.#target() - Date.now());
      const pad = (n) => String(n).padStart(2, '0');
      const total = Math.floor(remaining / 1000);
      this.parts.days.textContent = pad(Math.floor(total / 86400));
      this.parts.hours.textContent = pad(Math.floor((total % 86400) / 3600));
      this.parts.minutes.textContent = pad(Math.floor((total % 3600) / 60));
      this.parts.seconds.textContent = pad(total % 60);
    }

    disconnectedCallback() {
      clearInterval(this.timer);
    }
  }
  customElements.define('countdown-timer', CountdownTimer);

  /* ---------- Announcement bar ---------- */
  class AnnouncementBar extends HTMLElement {
    connectedCallback() {
      this.messages = [...this.querySelectorAll('.announcement__message')];
      if (this.messages.length < 2) return;
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
      this.index = 0;
      const start = () => {
        clearInterval(this.timer);
        this.timer = setInterval(() => this.#next(), Number(this.dataset.interval) || 5000);
      };
      const stop = () => clearInterval(this.timer);
      start();
      this.addEventListener('mouseenter', stop);
      this.addEventListener('mouseleave', () => {
        if (!this.contains(document.activeElement)) start();
      });
      this.addEventListener('focusin', stop);
      this.addEventListener('focusout', (event) => {
        if (!this.contains(event.relatedTarget)) start();
      });
    }

    #next() {
      const current = this.messages[this.index];
      this.index = (this.index + 1) % this.messages.length;
      const next = this.messages[this.index];
      current.classList.add('is-leaving');
      current.classList.remove('is-active');
      next.classList.remove('is-leaving');
      next.classList.add('is-active');
      setTimeout(() => current.classList.remove('is-leaving'), 500);
    }

    disconnectedCallback() {
      clearInterval(this.timer);
    }
  }
  customElements.define('announcement-bar', AnnouncementBar);

  /* ---------- Sticky header ---------- */
  class StickyHeader extends HTMLElement {
    connectedCallback() {
      this.mode = this.dataset.sticky;
      this.section = this.closest('.shopify-section');
      this.header = this.querySelector('.header');

      if (this.mode === 'none' || !this.section) return;
      this.section.classList.add('shopify-section-header-sticky');
      this.lastY = window.scrollY;
      this.onScroll = () => this.#onScroll();
      window.addEventListener('scroll', this.onScroll, { passive: true });
      this.#setOffset();
      if ('ResizeObserver' in window) {
        this.resizeObserver = new ResizeObserver(() => {
          if (!this.section.classList.contains('shopify-section-header-hidden')) this.#setOffset();
        });
        this.resizeObserver.observe(this);
      }
    }

    disconnectedCallback() {
      if (this.onScroll) window.removeEventListener('scroll', this.onScroll);
      this.resizeObserver?.disconnect();
    }

    #setOffset() {
      document.documentElement.style.setProperty('--header-offset', `${this.offsetHeight}px`);
    }

    #onScroll() {
      if (this.mode !== 'on-scroll-up') return;
      const y = window.scrollY;
      const hide = y > this.lastY && y > this.offsetHeight * 2 && !this.contains(document.activeElement);
      this.section.classList.toggle('shopify-section-header-hidden', hide);
      document.documentElement.style.setProperty('--header-offset', hide ? '0px' : `${this.offsetHeight}px`);
      this.lastY = y;
    }
  }
  customElements.define('sticky-header', StickyHeader);

  /* ---------- Predictive search ---------- */
  class PredictiveSearch extends HTMLElement {
    connectedCallback() {
      this.input = this.querySelector('input[type="search"]');
      this.results = this.querySelector('.search-form__results');
      this.controller = null;
      this.input.addEventListener('input', debounce(() => this.#search(), 250));
      this.input.addEventListener('focus', () => {
        if (this.results.innerHTML.trim() && this.input.value.trim()) this.#toggle(true);
      });
      this.addEventListener('focusout', () => {
        setTimeout(() => {
          if (!this.contains(document.activeElement)) this.#toggle(false);
        });
      });
      this.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
          this.#toggle(false);
          this.input.focus();
        }
      });
    }

    async #search() {
      const terms = this.input.value.trim();
      this.controller?.abort();
      if (!terms) {
        this.#toggle(false);
        return;
      }
      this.controller = new AbortController();
      try {
        const url = `${routes.predictiveSearch}?q=${encodeURIComponent(terms)}&resources[type]=product,collection,query&resources[limit]=10&section_id=predictive-search`;
        const response = await fetch(url, { signal: this.controller.signal });
        if (!response.ok) throw new Error(String(response.status));
        const html = await response.text();
        const fresh = parseHTML(html).querySelector('#predictive-search-results');
        this.results.innerHTML = fresh ? fresh.outerHTML : '';
        this.#toggle(Boolean(fresh));
      } catch (error) {
        if (error.name !== 'AbortError') this.#toggle(false);
      }
    }

    #toggle(open) {
      this.results.hidden = !open;
      this.input.setAttribute('aria-expanded', String(open));
    }
  }
  customElements.define('predictive-search', PredictiveSearch);

  /* ---------- Collection / search filtering ---------- */
  class FacetFilters extends HTMLElement {
    connectedCallback() {
      this.sectionId = this.dataset.sectionId;
      this.addEventListener('change', (event) => {
        if (event.target.closest('[data-facet-input]')) this.#onChange();
      });
      this.addEventListener('click', (event) => {
        const link = event.target.closest('[data-facet-link]');
        if (link) {
          event.preventDefault();
          this.#render(link.href);
        }
        const more = event.target.closest('[data-load-more]');
        if (more) {
          event.preventDefault();
          this.#loadMore(more);
        }
      });
      this.onPop = () => this.#render(window.location.href, false);
      window.addEventListener('popstate', this.onPop);
      this.#parkSoldOut();
      this.#watchMore();
    }

    disconnectedCallback() {
      window.removeEventListener('popstate', this.onPop);
      this.moreObserver?.disconnect();
    }

    /* Sold out last across the whole list, on every sort and on brand/type pages: while more
       pages are coming, sold-out cards wait here and are added after the last page. */
    #parkSoldOut() {
      this.parked = [];
      const grid = this.querySelector('[data-product-grid]');
      if (!grid || !this.querySelector('[data-load-more]')) return;
      for (const li of [...grid.children]) {
        if (li.querySelector('.card--sold-out')) {
          this.parked.push(li);
          li.remove();
        }
      }
    }

    /* Infinite scroll: load the next page as the shopper nears the end of the grid.
       The "Load more" link stays as a fallback (no JS, slow networks) and for crawlers. */
    #watchMore() {
      this.moreObserver?.disconnect();
      const more = this.querySelector('.collection__more');
      if (!more || !('IntersectionObserver' in window)) return;
      this.moreObserver = new IntersectionObserver(
        (entries) => {
          if (!entries.some((entry) => entry.isIntersecting) || this.loadingMore) return;
          const link = this.querySelector('[data-load-more]');
          if (link) this.#loadMore(link);
        },
        { rootMargin: '0px 0px 900px 0px' }
      );
      this.moreObserver.observe(more);
    }

    #onChange = debounce(() => {
      const form = this.querySelector('#FacetForm');
      const params = new URLSearchParams(new FormData(form));
      const sort = this.querySelector('select[name="sort_by"]');
      if (sort) params.set('sort_by', sort.value);
      for (const [key, value] of [...params.entries()]) {
        if (value === '') params.delete(key);
      }
      this.#render(`${form.action}?${params.toString()}`);
    }, 350);

    async #render(href, push = true) {
      const url = new URL(href, window.location.origin);
      const results = this.querySelector('[data-results]');
      results?.classList.add('is-loading');
      url.searchParams.set('section_id', this.sectionId);
      const active = document.activeElement;
      const focusName = this.contains(active) ? active.name : null;
      const focusValue = this.contains(active) ? active.value : null;
      try {
        const response = await fetch(url);
        if (!response.ok) throw new Error(String(response.status));
        const html = await response.text();
        const doc = parseHTML(html);
        const fresh = doc.querySelector('facet-filters');
        if (!fresh) return;
        const wasOpen = this.querySelector('#FilterDrawer')?.hasAttribute('open');
        const openGroups = [...this.querySelectorAll('#FacetForm details')].map((d) => d.open);

        // Swap everything except the open drawer panel, to keep focus stable.
        for (const selector of ['.collection__toolbar', '.collection__active', '[data-results]', '#FacetForm', '.facets__footer']) {
          const current = this.querySelector(selector);
          const next = fresh.querySelector(selector);
          if (current && next) current.innerHTML = next.innerHTML;
        }
        for (const [i, details] of [...this.querySelectorAll('#FacetForm details')].entries()) {
          if (openGroups[i] !== undefined) details.open = openGroups[i];
        }
        if (wasOpen) this.querySelector('#FilterDrawer')?.setAttribute('open', '');

        url.searchParams.delete('section_id');
        if (push) window.history.pushState({}, '', url);
        revealAll(this);
        this.#parkSoldOut();
        this.#watchMore();

        if (focusName) {
          const target = [...this.querySelectorAll(`[name="${CSS.escape(focusName)}"]`)].find(
            (el) => el.value === focusValue || el.type !== 'checkbox'
          );
          target?.focus();
        }
      } catch {
        url.searchParams.delete('section_id');
        window.location.href = url.toString();
      } finally {
        this.querySelector('[data-results]')?.classList.remove('is-loading');
      }
    }

    async #loadMore(link) {
      if (this.loadingMore) return;
      this.loadingMore = true;
      link.classList.add('is-loading');
      const url = new URL(link.href, window.location.origin);
      url.searchParams.set('section_id', this.sectionId);
      try {
        const response = await fetch(url);
        if (!response.ok) throw new Error(String(response.status));
        const html = await response.text();
        const doc = parseHTML(html);
        const grid = this.querySelector('[data-product-grid]');
        const freshGrid = doc.querySelector('[data-product-grid]');
        if (grid && freshGrid) {
          // Shopify's pages can overlap (search sorted by relevance): skip products already shown
          const key = (li) => li.querySelector('a[href*="/products/"]')?.getAttribute('href').split('?')[0];
          const seen = new Set([...grid.children, ...this.parked].map(key).filter(Boolean));
          for (const li of [...freshGrid.children]) {
            const k = key(li);
            if (k && seen.has(k)) continue;
            if (k) seen.add(k);
            if (li.querySelector('.card--sold-out')) this.parked.push(li);
            else grid.append(li);
          }
        }
        const more = this.querySelector('.collection__more');
        const freshMore = doc.querySelector('.collection__more');
        if (more) freshMore ? (more.innerHTML = freshMore.innerHTML) : more.remove();
        if (!freshMore && grid) {
          grid.append(...this.parked); // last page: now the sold-out items, at the very end
          this.parked = [];
        }
        revealAll(this);
      } catch {
        window.location.href = link.href;
      } finally {
        link.classList.remove('is-loading');
        this.loadingMore = false;
        this.#watchMore(); // re-arm: loads the next page right away if the end is still in view
      }
    }
  }
  customElements.define('facet-filters', FacetFilters);

  /* ---------- Scroll reveal ---------- */
  const revealObserver =
    'IntersectionObserver' in window
      ? new IntersectionObserver(
          (entries) => {
            for (const entry of entries) {
              if (!entry.isIntersecting) continue;
              entry.target.classList.add('is-revealed');
              revealObserver.unobserve(entry.target);
            }
          },
          { rootMargin: '0px 0px -8% 0px' }
        )
      : null;

  // Fallback: a fast scroll can skip past an element without it ever intersecting,
  // which would leave it invisible. Reveal anything that is already above the fold.
  window.addEventListener(
    'scroll',
    debounce(() => {
      for (const el of document.querySelectorAll('[data-reveal]:not(.is-revealed)')) {
        if (el.getBoundingClientRect().top < window.innerHeight) {
          el.classList.add('is-revealed');
          revealObserver?.unobserve(el);
        }
      }
    }, 120),
    { passive: true }
  );

  function revealAll(root = document) {
    observeLists(root);
    for (const el of root.querySelectorAll('[data-reveal]:not(.is-revealed)')) {
      if (revealObserver) revealObserver.observe(el);
      else el.classList.add('is-revealed');
    }
  }

  /* ---------- Info pages (about, contact, policies, careers) ---------- */
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  // Counts up to data-to when scrolled into view. The final value is already in the HTML.
  class CountUp extends HTMLElement {
    connectedCallback() {
      const to = Number(this.dataset.to);
      if (!Number.isFinite(to) || reducedMotion.matches || !('IntersectionObserver' in window)) return;
      const grouped = this.dataset.format === 'grouped';
      const format = (n) => (grouped ? new Intl.NumberFormat('en-US').format(n) : String(n));
      const from = grouped ? 0 : Math.round(to * 0.95); // years count up from close by
      this.textContent = format(from);
      const observer = new IntersectionObserver(
        ([entry]) => {
          if (!entry.isIntersecting) return;
          observer.disconnect();
          const start = performance.now();
          const tick = (now) => {
            const p = Math.min((now - start) / 1600, 1);
            this.textContent = format(Math.round(from + (to - from) * (1 - (1 - p) ** 3)));
            if (p < 1) requestAnimationFrame(tick);
          };
          requestAnimationFrame(tick);
        },
        { threshold: 0.6 }
      );
      observer.observe(this);
    }
  }
  customElements.define('count-up', CountUp);

  // Sets --progress (0–1) as the element scrolls by: reading progress (data-mode="read") or timeline fill.
  class ScrollProgress extends HTMLElement {
    connectedCallback() {
      this.onScroll = () => {
        this.frame ??= requestAnimationFrame(() => this.update());
      };
      window.addEventListener('scroll', this.onScroll, { passive: true });
      window.addEventListener('resize', this.onScroll, { passive: true });
      this.update();
    }

    disconnectedCallback() {
      window.removeEventListener('scroll', this.onScroll);
      window.removeEventListener('resize', this.onScroll);
    }

    update() {
      this.frame = null;
      const rect = this.getBoundingClientRect();
      const vh = window.innerHeight;
      const progress =
        this.dataset.mode === 'read' ? -rect.top / Math.max(rect.height - vh, 1) : (vh * 0.6 - rect.top) / rect.height;
      this.style.setProperty('--progress', Math.min(Math.max(progress, 0), 1).toFixed(4));
    }
  }
  customElements.define('scroll-progress', ScrollProgress);

  // "On this page" list built from the page body's headings, with scroll-spy.
  class PageToc extends HTMLElement {
    connectedCallback() {
      const body = document.getElementById(this.dataset.target);
      const headings = body ? [...body.querySelectorAll(this.dataset.levels || 'h2')] : [];
      if (headings.length < 2) return;
      const list = this.querySelector('ol');
      const links = new Map();
      headings.forEach((heading, index) => {
        if (!heading.id) heading.id = `section-${index + 1}`;
        const link = document.createElement('a');
        link.href = `#${heading.id}`;
        link.className = `page-toc__link${heading.tagName === 'H3' ? ' page-toc__link--sub' : ''}`;
        link.textContent = heading.textContent.trim();
        const item = document.createElement('li');
        item.append(link);
        list.append(item);
        links.set(heading, link);
      });
      this.hidden = false;

      const details = this.querySelector('details');
      const desktop = window.matchMedia('(min-width: 990px)');
      const sync = () => (details.open = desktop.matches);
      sync();
      desktop.addEventListener('change', sync);
      list.addEventListener('click', (event) => {
        if (event.target.closest('a') && !desktop.matches) details.open = false;
      });

      let current;
      const spy = () => {
        const line = window.innerHeight * 0.3;
        const active = headings.filter((h) => h.getBoundingClientRect().top < line).pop() ?? headings[0];
        if (active === current) return;
        links.get(current)?.removeAttribute('aria-current');
        current = active;
        const link = links.get(active);
        link.setAttribute('aria-current', 'true');
        if (list.scrollHeight > list.clientHeight) list.scrollTop = link.offsetTop - list.clientHeight / 2;
      };
      const observer = new IntersectionObserver(spy, { rootMargin: '0px 0px -70% 0px' });
      headings.forEach((h) => observer.observe(h));
      spy();
    }
  }
  customElements.define('page-toc', PageToc);

  // Instant search over FAQ questions and answers.
  class FaqFilter extends HTMLElement {
    connectedCallback() {
      const input = this.querySelector('[data-faq-search]');
      if (!input) return;
      input.closest('.faq__search').hidden = false;
      const items = [...this.querySelectorAll('[data-faq-item]')];
      const status = this.querySelector('[data-faq-status]');
      input.addEventListener(
        'input',
        debounce(() => {
          const query = input.value.trim().toLowerCase();
          let shown = 0;
          for (const item of items) {
            item.hidden = Boolean(query) && !item.textContent.toLowerCase().includes(query);
            if (!item.hidden) shown++;
          }
          status.textContent = shown ? '' : status.dataset.empty;
        }, 150)
      );
    }
  }
  customElements.define('faq-filter', FaqFilter);

  // Careers: location filter chips + "Apply" pre-fills role and branch in the form.
  class JobBoard extends HTMLElement {
    connectedCallback() {
      this.cards = [...this.querySelectorAll('.job-card')];
      this.status = this.querySelector('[data-job-status]');
      const filters = this.querySelector('[data-job-filters]');
      if (filters) {
        filters.hidden = false;
        filters.addEventListener('click', (event) => {
          const chip = event.target.closest('[data-location]');
          if (chip) this.filter(chip);
        });
      }
      this.addEventListener('click', (event) => {
        const apply = event.target.closest('[data-apply-role]');
        if (apply) this.prefill(apply);
      });
    }

    filter(chip) {
      for (const el of chip.parentElement.children) el.setAttribute('aria-pressed', String(el === chip));
      const location = chip.dataset.location;
      let shown = 0;
      for (const card of this.cards) {
        card.hidden = Boolean(location) && card.dataset.location !== location;
        if (!card.hidden) {
          shown++;
          card.classList.add('is-revealed');
        }
      }
      if (this.status) this.status.textContent = this.status.dataset.template.replace('[count]', shown);
    }

    prefill(button) {
      const role = this.querySelector('[data-apply-role-input]');
      const branch = this.querySelector('[data-apply-branch-select]');
      if (role) role.value = button.dataset.applyRole;
      const wanted = button.dataset.applyBranch.toLowerCase();
      const option = branch && [...branch.options].find((o) => wanted && o.value.toLowerCase() === wanted);
      if (option) branch.value = option.value;
      const form = this.querySelector('.jobs__form');
      form?.classList.remove('is-highlighted');
      void form?.offsetWidth;
      form?.classList.add('is-highlighted');
      requestAnimationFrame(() => this.querySelector('[data-apply-focus]')?.focus({ preventScroll: true }));
    }
  }
  customElements.define('job-board', JobBoard);

  // Cards with data-spotlight get a glow that follows the pointer (--mx / --my).
  document.addEventListener(
    'pointermove',
    (event) => {
      const card = event.target.closest?.('[data-spotlight]');
      if (!card || event.pointerType !== 'mouse') return;
      const rect = card.getBoundingClientRect();
      card.style.setProperty('--mx', `${event.clientX - rect.left}px`);
      card.style.setProperty('--my', `${event.clientY - rect.top}px`);
    },
    { passive: true }
  );

  // Branches: picking a branch shows it on the embedded map. The map loads only when scrolled near.
  class BranchMap extends HTMLElement {
    connectedCallback() {
      this.frame = this.querySelector('iframe');
      this.tabs = [...this.querySelectorAll('[data-map-src]')];
      for (const tab of this.tabs) tab.addEventListener('click', () => this.select(tab));
      if (!this.frame) return;
      const load = () => {
        if (!this.frame.src) this.frame.src = this.frame.dataset.src;
      };
      if (!('IntersectionObserver' in window)) return load();
      const observer = new IntersectionObserver(
        ([entry]) => {
          if (!entry.isIntersecting) return;
          observer.disconnect();
          load();
        },
        { rootMargin: '400px' }
      );
      observer.observe(this.frame);
    }

    select(tab) {
      for (const t of this.tabs) t.setAttribute('aria-pressed', String(t === tab));
      this.frame.classList.add('is-loading');
      this.frame.addEventListener('load', () => this.frame.classList.remove('is-loading'), { once: true });
      this.frame.src = tab.dataset.mapSrc;
      this.frame.title = tab.dataset.mapTitle;
    }
  }
  customElements.define('branch-map', BranchMap);

  // "Shop by sport" swiper: prev/next buttons and a "3/14" counter under the row.
  class CircleSlider extends HTMLElement {
    connectedCallback() {
      this.track = this.querySelector('[data-circle-track]');
      this.items = this.track ? [...this.track.children] : [];
      this.count = this.querySelector('[data-circle-count]');
      this.prev = this.querySelector('[data-circle-prev]');
      this.next = this.querySelector('[data-circle-next]');
      if (!this.track || this.items.length < 2) return;
      this.querySelector('.circle-slider__nav').hidden = false;
      this.prev.addEventListener('click', () => this.go(-1));
      this.next.addEventListener('click', () => this.go(1));
      this.track.addEventListener('scroll', () => (this.frame ??= requestAnimationFrame(() => this.update())), { passive: true });
      if ('ResizeObserver' in window) new ResizeObserver(() => this.update()).observe(this.track);
      this.update();
    }

    step() {
      const [a, b] = this.items;
      return b ? Math.abs(b.offsetLeft - a.offsetLeft) : a.offsetWidth;
    }

    perView() {
      return Math.max(1, Math.round(this.track.clientWidth / this.step()));
    }

    index() {
      return Math.round(Math.abs(this.track.scrollLeft) / this.step());
    }

    go(direction) {
      const left = this.step() * this.perView() * direction * (isRTL ? -1 : 1);
      this.track.scrollBy({ left, behavior: 'smooth' });
    }

    update() {
      this.frame = null;
      const total = this.items.length;
      const last = Math.max(total - this.perView(), 0);
      const first = Math.min(this.index(), last);
      this.count.textContent = `${first + 1}/${total}`;
      this.prev.disabled = first <= 0;
      this.next.disabled = first >= last;
    }
  }
  customElements.define('circle-slider', CircleSlider);

  document.addEventListener('click', (event) => {
    if (event.target.closest('[data-print]')) window.print();
  });

  /* ---------- Misc ---------- */
  const syncFooterDetails = () => {
    const desktop = window.matchMedia('(min-width: 750px)').matches;
    for (const details of document.querySelectorAll('[data-desktop-open]')) details.open = desktop;
  };

  document.addEventListener('change', (event) => {
    const select = event.target.closest('[data-autosubmit]');
    if (select) select.form?.submit();
  });

  const init = () => {
    revealAll();
    syncFooterDetails();
    window.matchMedia('(min-width: 750px)').addEventListener('change', syncFooterDetails);
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();

  // Theme editor support
  document.addEventListener('shopify:section:load', (event) => revealAll(event.target));
  document.addEventListener('shopify:block:select', (event) => {
    if (event.target.matches('details[data-faq-item]')) event.target.open = true;
    const slideshow = event.target.closest('hero-slideshow');
    if (slideshow) {
      slideshow.pause();
      slideshow.goTo(slideshow.slides.indexOf(event.target));
    }
  });
  document.addEventListener('shopify:block:deselect', (event) => {
    const slideshow = event.target.closest('hero-slideshow');
    if (slideshow && slideshow.dataset.autoplay === 'true') slideshow.play();
  });
})();
