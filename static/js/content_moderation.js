(() => {
    const source = document.getElementById('servinn-content-rules');
    if (!source) return;
    const rules = JSON.parse(source.textContent);
    const fields = new Set(rules.fields);
    const substitutions = {'0': 'o', '1': 'i', '3': 'e', '4': 'a', '5': 's', '7': 't', '@': 'a', '$': 's'};
    const normalize = value => value.normalize('NFKD').toLowerCase()
        .replace(/[\p{M}\p{Cf}]/gu, '')
        .replace(/[013457@$]/g, character => substitutions[character])
        .replace(/(?<=[a-z])!(?=[a-z])/g, 'i')
        .replace(/([a-z])\1+/g, '$1');
    const patterns = rules.terms.map(term => new RegExp(
        '(?<![\\p{L}\\p{N}])' + [...normalize(term).replace(/ /g, '')]
            .join('[^\\p{L}\\p{N}]*') +
        '(?![\\p{L}\\p{N}])', 'u'));
    let sequence = 0;
    const checkers = new Map();
    document.querySelectorAll('input[name], textarea[name]').forEach(field => {
        if (!fields.has(field.name) || field.type === 'hidden' || field.type === 'file') return;
        const warning = document.createElement('small');
        warning.id = 'content-warning-' + ++sequence;
        warning.setAttribute('aria-live', 'polite');
        warning.style.cssText = 'display:none;color:#a03832;margin-top:6px;line-height:1.5';
        warning.hidden = true;
        field.insertAdjacentElement('afterend', warning);
        field.setAttribute('aria-describedby', [field.getAttribute('aria-describedby'), warning.id].filter(Boolean).join(' '));
        let blocked = false;
        const check = () => {
            const value = normalize(field.value);
            const offensive = !field.disabled && patterns.some(pattern => pattern.test(value));
            if (offensive) {
                field.setCustomValidity(rules.message);
                warning.textContent = rules.message;
                warning.hidden = false;
                warning.style.display = 'block';
                field.setAttribute('aria-invalid', 'true');
            } else if (blocked) {
                field.setCustomValidity('');
                warning.textContent = '';
                warning.hidden = true;
                warning.style.display = 'none';
                field.removeAttribute('aria-invalid');
            }
            blocked = offensive;
            return offensive;
        };
        checkers.set(field, check);
        field.addEventListener('invalid', event => {
            if (blocked) {
                event.preventDefault();
                window.ServinnErrors?.show(rules.message);
            }
        });
        field.addEventListener('input', check);
        field.addEventListener('change', check);
        check();
    });
    // Recheck autofill and values assigned by scripts before a submit attempt.
    document.addEventListener('click', event => {
        const submitter = event.target.closest('button, input[type="submit"]');
        const form = submitter?.form;
        if (!form || !['submit', 'image'].includes(submitter.type)) return;
        checkers.forEach((check, field) => { if (field.form === form) check(); });
    }, true);
    document.addEventListener('submit', event => {
        let offensive = false;
        checkers.forEach((check, field) => {
            if (field.form === event.target && check()) offensive = true;
        });
        if (offensive) {
            event.preventDefault();
            window.ServinnErrors?.show(rules.message);
        }
    }, true);
})();
