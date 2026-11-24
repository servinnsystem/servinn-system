/* Keep all steps in one form so going Back preserves entries and selected files.
   Without JavaScript, the complete form remains available. */
(() => {
  const form = document.getElementById('profile-form');
  if (!form) return;
  const pages = [...form.querySelectorAll('[data-profile-step]')];
  const nav = document.getElementById('profile-steps');
  const status = document.getElementById('profile-step-status');
  const back = document.getElementById('profile-back');
  const next = document.getElementById('profile-next');
  const submit = form.querySelector('button[type="submit"]');
  const review = document.getElementById('profile-review');
  let current = 0;
  const indicators = pages.map((page, index) => {
    const item = document.createElement('span');
    item.textContent = `${index + 1}. ${page.dataset.profileStep}`;
    nav.append(item);
    return item;
  });
  function updateReview() {
    review.replaceChildren();
    const skills = [];
    for (const field of form.elements) {
      if (!field.name || field.disabled || ['hidden', 'submit', 'button'].includes(field.type)
          || ['declaration', 'user_agreement'].includes(field.name)
          || field.closest('.hidden-field')) continue;
      if (field.type === 'checkbox') {
        if (field.name === 'skills' && field.checked) skills.push(field.value);
        continue;
      }
      const value = field.type === 'file'
        ? [...field.files].map(file => file.name).join(', ')
        : field.tagName === 'SELECT' ? field.selectedOptions[0]?.textContent : field.value;
      if (!value) continue;
      const label = field.labels?.[0]?.textContent.trim() || field.name.replaceAll('_', ' ');
      appendDetail(label, value);
    }
    if (skills.length) appendDetail('Skills', skills.join(', '));
  }
  function appendDetail(label, value) {
    const term = document.createElement('dt');
    const description = document.createElement('dd');
    term.textContent = label;
    description.textContent = value;
    review.append(term, description);
  }
  function show(index, focus = true) {
    current = index;
    pages.forEach((page, i) => { page.hidden = i !== index; });
    indicators.forEach((item, i) => {
      if (i === index) item.setAttribute('aria-current', 'step');
      else item.removeAttribute('aria-current');
    });
    status.textContent = `Step ${index + 1} of ${pages.length}: ${pages[index].dataset.profileStep}`;
    back.hidden = index === 0;
    next.hidden = index === pages.length - 1;
    submit.hidden = index !== pages.length - 1;
    if (index === pages.length - 1) updateReview();
    if (focus) {
      status.tabIndex = -1;
      status.focus();
      status.scrollIntoView({ block: 'start', behavior: 'smooth' });
    }
  }
  function validate(index) {
    const invalid = [...pages[index].querySelectorAll('input, select, textarea')]
      .find(field => field.willValidate && !field.checkValidity());
    if (!invalid) return true;
    show(index);
    invalid.closest('details')?.setAttribute('open', '');
    invalid.reportValidity();
    return false;
  }
  // Validation is performed on the visible step rather than hidden controls.
  form.noValidate = true;
  nav.hidden = status.hidden = document.getElementById('profile-navigation').hidden = false;
  next.addEventListener('click', () => { if (validate(current)) show(current + 1); });
  back.addEventListener('click', () => show(current - 1));
  // Run before the existing agreement dialog handler, including Enter submission.
  form.addEventListener('submit', event => {
    if (current < pages.length - 1) {
      event.preventDefault();
      event.stopImmediatePropagation();
      if (validate(current)) show(current + 1);
      return;
    }
    for (let index = 0; index < pages.length; index++) {
      if (!validate(index)) {
        event.preventDefault();
        event.stopImmediatePropagation();
        return;
      }
    }
  }, true);
  const errors = JSON.parse(document.getElementById('profile-error-fields')?.textContent || 'null') || [];
  const errorPage = pages.findIndex(page => [...page.querySelectorAll('[name]')]
    .some(field => errors.includes(field.name)));
  show(errorPage < 0 ? 0 : errorPage, false);
})();
