(() => {
    if (window.ServinnErrors) return;
    const dialog = document.getElementById('servinn-error-dialog');
    if (!dialog) return;
    const messageBox = document.getElementById('servinn-error-message');
    const close = document.getElementById('servinn-error-close');
    let previousFocus;
    let lastMessage = '';
    let lastShown = 0;
    const submissions = new Map();

    function restore() {
        submissions.forEach(({timer, buttons}) => {
            clearTimeout(timer);
            buttons.forEach(({button, disabled, text}) => {
                button.disabled = disabled;
                button.textContent = text;
                button.removeAttribute('aria-busy');
            });
        });
        submissions.clear();
        window.dispatchEvent(new Event('servinn:request-failed'));
    }
    function show(message) {
        message = String(message || 'Something went wrong. Please try again.').slice(0, 2000);
        restore();
        if (message === lastMessage && Date.now() - lastShown < 1500) return;
        lastMessage = message;
        lastShown = Date.now();
        messageBox.textContent = message;
        if (!dialog.open) {
            previousFocus = document.activeElement;
            dialog.showModal();
        }
        close.focus();
    }
    close.addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', () => {
        if (previousFocus?.isConnected) previousFocus.focus();
    });
    window.ServinnErrors = {show};

    // Preserve native form submissions and uploaded files. Recover the old page
    // when navigation hangs; never automatically repeat a potentially saved POST.
    document.addEventListener('submit', event => {
        const form = event.target;
        const buttons = [...form.querySelectorAll('button[type="submit"],button:not([type]),input[type="submit"]')]
            .map(button => ({button, disabled: button.disabled, text: button.textContent}));
        setTimeout(() => {
            if (event.defaultPrevented || !form.isConnected) return;
            const timer = setTimeout(() => {
                window.stop();
                show('This request took too long. Your information is still on this page. Check whether the action completed before submitting again.');
            }, 45000);
            submissions.set(form, {timer, buttons});
        }, 0);
    }, true);
    window.addEventListener('pageshow', restore);

    const nativeFetch = window.fetch.bind(window);
    window.fetch = async (input, options = {}) => {
        const url = new URL(input instanceof Request ? input.url : input, location.href);
        if (url.origin !== location.origin) return nativeFetch(input, options);
        const controller = new AbortController();
        const signal = options.signal || (input instanceof Request ? input.signal : undefined);
        const abort = () => controller.abort();
        if (signal?.aborted) controller.abort();
        else signal?.addEventListener('abort', abort, {once: true});
        let timedOut = false;
        const timer = setTimeout(() => { timedOut = true; controller.abort(); }, 30000);
        try {
            const response = await nativeFetch(input, {...options, signal: controller.signal});
            if (response.ok && response.headers.get('Content-Type')?.includes('application/json')) {
                // Keep the deadline active until a JSON response body is received.
                await response.clone().text();
            }
            if (!response.ok) {
                let message = response.status === 403
                    ? 'Your session or security token needs refreshing. Refresh the page and try again.'
                    : 'The request could not be completed. Check your details and try again.';
                if (response.headers.get('Content-Type')?.includes('application/json')) {
                    try {
                        const data = await response.clone().json();
                        if (typeof data.message === 'string') message = data.message;
                    } catch (_) { /* Keep the safe fallback. */ }
                }
                show(message);
            }
            return response;
        } catch (error) {
            if (!signal?.aborted) {
                show(timedOut
                    ? 'The request timed out. Check whether the action completed before trying again.'
                    : 'Unable to connect. Check your internet connection and try again.');
            }
            throw error;
        } finally {
            clearTimeout(timer);
            signal?.removeEventListener('abort', abort);
        }
    };
    window.addEventListener('unhandledrejection', () => {
        show('This action could not be completed. Check your connection and try again.');
    });
    window.addEventListener('error', event => {
        if (event.error) show('A page error occurred. Close this message and try again, or refresh the page.');
    });
    const initialErrors = [...document.querySelectorAll('#servinn-server-errors p, .errorlist li')]
        .map(item => item.textContent.trim()).filter(Boolean);
    const unique = [...new Set(initialErrors)];
    if (window.servinnPendingError) show(window.servinnPendingError);
    else if (unique.length) show(unique.join('\n'));
})();
