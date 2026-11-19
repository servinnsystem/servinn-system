(() => {
  'use strict';
  const picker = document.getElementById('language-picker');
  if (!picker || window.servinnLanguages) return;
  const codes = ['en', 'tl', 'hil', 'ceb', 'ilo', 'war'];
  const names = {en: 'English', tl: 'Filipino (Tagalog)', hil: 'Hiligaynon (Ilonggo)',
    ceb: 'Cebuano (Bisaya)', war: 'Waray-Waray', ilo: 'Ilocano', pam: 'Kapampangan',
    pag: 'Pangasinan', bik: 'Bikol', akl: 'Aklanon', krj: 'Kinaray-a', tsg: 'Tausug',
    mrw: 'Maranao', mdh: 'Maguindanaon'};
  const normalize = text => text.replace(/\s+/g, ' ').trim();
  const key = text => normalize(text).toLocaleLowerCase('en');
  const dictionary = new Map();
  const add = (original, values) => dictionary.set(key(original), values);
  for (const [original, ...values] of window.servinnLegacyTranslations || []) {
    add(original, values);
    // English equivalents can also occur on other pages.
    if (!dictionary.has(key(values[0]))) add(values[0], values);
  }
  for (const row of (window.servinnLanguageCatalog || '').trim().split('\n')) {
    const values = row.split('|');
    if (values.length === 6) add(values[0], values);
  }
  const aliases = {'Sign In': 'Sign in', 'Sign Out': 'Sign out', 'Find Jobs': 'Find jobs',
    'Saved Jobs': 'Saved jobs', 'My Applications': 'My applications',
    'Posted jobs': 'Posted Jobs', 'Active jobs': 'Active Jobs'};
  for (const [alias, original] of Object.entries(aliases)) {
    if (dictionary.has(key(original))) add(alias, dictionary.get(key(original)));
  }
  function translate(text, language) {
    const original = normalize(text);
    const index = codes.indexOf(language);
    const values = dictionary.get(key(original));
    if (values) {
      if (index <= 0 && key(original) === key(values[0])) return original;
      return values[index] || values[0];
    }
    const applications = original.match(/^(\d+) applications$/);
    if (applications) return `${applications[1]} ${translate('Applications', language).toLowerCase()}`;
    return original;
  }
  // Retain originals so switching repeatedly never translates translated text.
  const textState = new WeakMap();
  const attributeState = new WeakMap();
  const excluded = 'script,style,textarea,code,pre,[translate="no"],[data-user-content],.notice,.alert,.profile h2,.name,.email,.user-name,.job-top h3,.company,.description,.skills,.application strong,.job-card h3,.job-card p,.job-symbol,.table-row td:nth-child(-n+2)';
  let current = 'en';
  function updateText(node) {
    if (!node.parentElement || node.parentElement.closest(excluded)) return;
    let state = textState.get(node);
    if (!state || state.last !== node.nodeValue) state = {original: node.nodeValue};
    const translated = translate(state.original, current);
    const original = normalize(state.original);
    // No replacement means preserve the original spacing exactly.
    const output = translated === original ? state.original
      : state.original.replace(/\S(?:[\s\S]*\S)?/, translated);
    if (output !== node.nodeValue) node.nodeValue = output;
    state.last = output;
    textState.set(node, state);
  }
  function updateAttributes(element) {
    if (element.closest(excluded)) return;
    let state = attributeState.get(element);
    if (!state) { state = {}; attributeState.set(element, state); }
    for (const attribute of ['placeholder', 'aria-label', 'title']) {
      const value = element.getAttribute(attribute);
      if (value === null) continue;
      if (!state[attribute] || state[attribute].last !== value) state[attribute] = {original: value};
      const output = translate(state[attribute].original, current);
      if (output !== value) element.setAttribute(attribute, output);
      state[attribute].last = output;
    }
  }
  function render() {
    observer.disconnect();
    // An option without a value submits its text: freeze it before translation.
    document.querySelectorAll('option:not([value])').forEach(option => {
      option.setAttribute('value', option.textContent);
    });
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) updateText(walker.currentNode);
    document.querySelectorAll('[placeholder],[aria-label],[title]').forEach(updateAttributes);
    document.documentElement.lang = current;
    document.querySelectorAll('main [lang]:not([translate="no"])').forEach(element => {
      if (!element.closest('[translate="no"]')) element.lang = current;
    });
    picker.value = current;
    picker.setAttribute('aria-label', `${translate('Languages', current)}: ${names[current]}`);
    document.title = translate(originalTitle, current);
    observer.observe(document.body, {childList: true, subtree: true, characterData: true,
      attributes: true, attributeFilter: ['placeholder','aria-label','title']});
  }
  const originalTitle = document.title;
  const observer = new MutationObserver(render);
  function select(language) {
    current = Object.hasOwn(names, language) ? language : 'en';
    render();
    try { localStorage.setItem('servinn-language', current); } catch (_) { /* Storage may be disabled. */ }
  }
  picker.addEventListener('change', event => select(event.target.value));
  window.addEventListener('storage', event => { if (event.key === 'servinn-language') select(event.newValue); });
  window.servinnLanguages = {select, translate, names};
  let saved = 'en';
  try { saved = localStorage.getItem('servinn-language') || 'en'; } catch (_) { /* Use English. */ }
  select(saved);
})();
