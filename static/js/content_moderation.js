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
        '(?<![\\p{L}\\p{N}_])' + [...normalize(term).replace(/ /g, '')]
            .map(character => character).join('[^\\p{L}\\p{N}]*') +
        '(?![\\p{L}\\p{N}_])', 'u'));
    let sequence = 0;
    document.querySelectorAll('input[name], textarea[name]').forEach(field => {
        if (!fields.has(field.name) || field.type === 'hidden' || field.type === 'file') return;
        const warning = document.createElement('small');
        warning.id = 'content-warning-' + ++sequence;
        warning.setAttribute('aria-live', 'polite');
        warning.style.cssText = 'display:block;color:#a03832;margin-top:6px;line-height:1.5';
        warning.hidden = true;
        field.insertAdjacentElement('afterend', warning);
        field.setAttribute('aria-describedby', [field.getAttribute('aria-describedby'), warning.id].filter(Boolean).join(' '));
        let blocked = false;
        const check = () => {
            const value = normalize(field.value);
            const offensive = patterns.some(pattern => pattern.test(value));
            if (offensive) {
                field.setCustomValidity(rules.message);
                warning.textContent = rules.message;
                warning.hidden = false;
                field.setAttribute('aria-invalid', 'true');
            } else if (blocked) {
                field.setCustomValidity('');
                warning.textContent = '';
                warning.hidden = true;
                field.removeAttribute('aria-invalid');
            }
            blocked = offensive;
        };
        field.addEventListener('input', check);
        field.addEventListener('change', check);
        check();
    });
})();
