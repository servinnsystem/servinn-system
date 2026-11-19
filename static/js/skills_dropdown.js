(() => {
  document.querySelectorAll('.skills-dropdown').forEach(dropdown => {
    const summary = dropdown.querySelector('summary');
    const text = dropdown.querySelector('[data-skills-summary]');
    const otherField = dropdown.closest('.skills-control')?.querySelector('[data-other-skills]');
    const otherInput = otherField?.querySelector('input[name="other_skills"]');
    const update = () => {
      const names = Array.from(dropdown.querySelectorAll('input[type="checkbox"]:checked'))
        .map(input => input.closest('label')?.textContent.trim() || input.value);
      text.textContent = names.length ? names.join(', ') : 'Select skills';
      if (otherField && otherInput) {
        const other = dropdown.querySelector('input[type="checkbox"][value="Other"]');
        const selected = !!other?.checked && !other.disabled;
        otherField.hidden = !selected;
        otherInput.disabled = !selected;
        otherInput.required = selected;
      }
    };
    dropdown.addEventListener('change', update);
    dropdown.closest('.skills-control')?.addEventListener('skills-availability-change', update);
    dropdown.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        dropdown.open = false;
        summary.focus();
      }
    });
    document.addEventListener('click', event => {
      if (!dropdown.contains(event.target)) dropdown.open = false;
    });
    update();
  });
})();
