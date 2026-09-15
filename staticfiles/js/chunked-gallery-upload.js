/**
 * Chunked gallery uploader.
 *
 * Converting a 24MP frame costs about a second of single-threaded CPU, so a
 * request carrying a whole gallery cannot fit inside the gunicorn timeout.
 * This drives the server's three steps instead: create a draft, post the
 * images a few at a time, then publish — which is the only point the client
 * is emailed.
 *
 * A failed chunk is retried with backoff and then halts, leaving the draft
 * resumable. Silently skipping failures would ship an incomplete gallery to a
 * client, which is the one outcome worth stopping for.
 */
(function () {
    'use strict';

    const form = document.getElementById('chunked-gallery-upload-form');
    if (!form) return;

    const fileInput = form.querySelector('input[type="file"]');
    const reservationInput = form.querySelector('[name="reservation"]');
    const submitBtn = document.getElementById('chunked-upload-submit');
    const progress = document.getElementById('chunked-upload-progress');
    const progressBar = document.getElementById('chunked-upload-progress-bar');
    const statusEl = document.getElementById('chunked-upload-status');

    const TEXT = JSON.parse(document.getElementById('chunked-upload-text').textContent);
    const CHUNK_SIZE = Number(form.dataset.chunkSize) || 6;
    const MAX_RETRIES = 3;
    const RETRY_BASE_MS = 1000;

    function fileKey(name, size) {
        return name + '::' + size;
    }

    function setStatus(message, isError) {
        statusEl.textContent = message;
        statusEl.classList.toggle('is-error', Boolean(isError));
    }

    function setProgress(done, total) {
        const percent = total ? Math.round((done / total) * 100) : 0;
        progressBar.style.width = percent + '%';
        setStatus(TEXT.progress.replace('{done}', done).replace('{total}', total), false);
    }

    function post(fields, files) {
        const body = new FormData();
        body.append('csrfmiddlewaretoken', form.querySelector('[name="csrfmiddlewaretoken"]').value);
        Object.keys(fields).forEach((key) => body.append(key, fields[key]));
        (files || []).forEach((file) => body.append('images', file));

        // The formset's management form has to ride along on `create`, which
        // validates the same form the plain (non-JS) submit does.
        if (fields.step === 'create') {
            form.querySelectorAll('[name^="labels-"]').forEach((input) => {
                body.append(input.name, input.value);
            });
        }

        return fetch(form.action || window.location.href, {
            method: 'POST',
            body: body,
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
        }).then((response) => response.json().then((data) => ({ ok: response.ok, data })));
    }

    function sleep(ms) {
        return new Promise((resolve) => window.setTimeout(resolve, ms));
    }

    async function sendChunkWithRetries(galleryId, chunk) {
        let lastError = TEXT.genericError;
        for (let attempt = 0; attempt < MAX_RETRIES; attempt += 1) {
            if (attempt > 0) await sleep(RETRY_BASE_MS * Math.pow(2, attempt - 1));
            let result;
            try {
                result = await post({ step: 'chunk', gallery_id: galleryId }, chunk);
            } catch (err) {
                lastError = TEXT.networkError;
                continue;
            }
            if (result.ok && result.data.success) return result.data;
            lastError = result.data.error || TEXT.genericError;
        }
        throw new Error(lastError);
    }

    function alreadyUploadedKeys(entries) {
        return new Set((entries || []).map((entry) => fileKey(entry.name, entry.size)));
    }

    async function run(files) {
        submitBtn.disabled = true;
        progress.hidden = false;
        setStatus(TEXT.creating, false);

        let created;
        try {
            created = await post({ step: 'create', reservation: reservationInput.value });
        } catch (err) {
            setStatus(TEXT.networkError, true);
            submitBtn.disabled = false;
            return;
        }
        if (!created.ok || !created.data.success) {
            setStatus(created.data.error || TEXT.genericError, true);
            submitBtn.disabled = false;
            return;
        }

        const galleryId = created.data.gallery_id;
        const cap = created.data.cap;
        const chunkSize = created.data.chunk_size || CHUNK_SIZE;
        const seen = alreadyUploadedKeys(created.data.uploaded);

        // Refuse a selection that cannot fit before uploading a single byte.
        const incoming = files.filter((file) => !seen.has(fileKey(file.name, file.size)));
        if (seen.size + incoming.length > cap) {
            setStatus(TEXT.capExceeded.replace('{cap}', cap), true);
            submitBtn.disabled = false;
            return;
        }

        const total = files.length;
        let done = total - incoming.length;
        setProgress(done, total);

        for (let i = 0; i < incoming.length; i += chunkSize) {
            const chunk = incoming.slice(i, i + chunkSize);
            try {
                const data = await sendChunkWithRetries(galleryId, chunk);
                (data.errors || []).forEach((message) => window.console.warn(message));
            } catch (err) {
                setStatus(
                    TEXT.halted.replace('{done}', done).replace('{total}', total)
                        + ' ' + err.message,
                    true,
                );
                submitBtn.disabled = false;
                return;
            }
            done += chunk.length;
            setProgress(done, total);
        }

        setStatus(TEXT.publishing, false);
        const published = await post({ step: 'publish', gallery_id: galleryId });
        if (!published.ok || !published.data.success) {
            setStatus(published.data.error || TEXT.genericError, true);
            submitBtn.disabled = false;
            return;
        }
        window.location.href = form.dataset.doneUrl;
    }

    form.addEventListener('submit', (event) => {
        const files = Array.from(fileInput.files || []);
        if (!files.length || !reservationInput.value) return;  // let the server report it
        event.preventDefault();
        run(files);
    });

    // Drafts are never swept automatically — the photographer deletes them.
    document.querySelectorAll('.gallery-draft-discard').forEach((btn) => {
        btn.addEventListener('click', () => {
            if (!window.confirm(TEXT.discardConfirm)) return;
            btn.disabled = true;
            post({ step: 'discard', gallery_id: btn.dataset.galleryId }).then(({ ok, data }) => {
                if (ok && data.success) {
                    btn.closest('.gallery-draft-item').remove();
                    return;
                }
                btn.disabled = false;
                window.alert((data && data.error) || TEXT.genericError);
            });
        });
    });
})();
