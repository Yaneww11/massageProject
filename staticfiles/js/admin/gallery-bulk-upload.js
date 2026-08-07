(function () {
    'use strict';

    const form = document.getElementById('gallery-bulk-upload-form');
    if (!form) return;

    const dropzone = document.getElementById('gallery-bulk-dropzone');
    const fileInput = document.getElementById('id_images');
    const grid = document.getElementById('gallery-bulk-preview-grid');
    const progress = document.getElementById('gallery-bulk-progress');
    const progressBar = document.getElementById('gallery-bulk-progress-bar');
    const progressLabel = document.getElementById('gallery-bulk-progress-label');
    const submitBtn = document.getElementById('gallery-bulk-submit');

    let selectedFiles = [];
    let previewUrls = [];

    function syncNativeInput() {
        const dt = new DataTransfer();
        selectedFiles.forEach((file) => dt.items.add(file));
        fileInput.files = dt.files;
    }

    function renderGrid() {
        previewUrls.forEach((url) => URL.revokeObjectURL(url));
        previewUrls = [];
        grid.innerHTML = '';
        selectedFiles.forEach((file, index) => {
            const thumb = document.createElement('div');
            thumb.className = 'gallery-bulk-thumb';

            const url = URL.createObjectURL(file);
            previewUrls.push(url);
            const img = document.createElement('img');
            img.src = url;
            img.alt = file.name;
            thumb.appendChild(img);

            const removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.className = 'gallery-bulk-thumb-remove';
            removeBtn.setAttribute('aria-label', 'Remove ' + file.name);
            removeBtn.textContent = '×';
            removeBtn.addEventListener('click', () => {
                selectedFiles.splice(index, 1);
                syncNativeInput();
                renderGrid();
            });
            thumb.appendChild(removeBtn);

            grid.appendChild(thumb);
        });
    }

    function addFiles(fileList) {
        Array.from(fileList).forEach((file) => selectedFiles.push(file));
        syncNativeInput();
        renderGrid();
    }

    dropzone.addEventListener('dragover', (event) => {
        event.preventDefault();
        dropzone.classList.add('is-dragover');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('is-dragover');
    });

    dropzone.addEventListener('drop', (event) => {
        event.preventDefault();
        dropzone.classList.remove('is-dragover');
        if (event.dataTransfer && event.dataTransfer.files.length) {
            addFiles(event.dataTransfer.files);
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length) addFiles(fileInput.files);
    });

    form.addEventListener('submit', (event) => {
        event.preventDefault();
        if (!selectedFiles.length) {
            form.submit();
            return;
        }

        const formData = new FormData();
        const csrfToken = form.querySelector('input[name="csrfmiddlewaretoken"]').value;
        formData.append('csrfmiddlewaretoken', csrfToken);
        selectedFiles.forEach((file) => formData.append('images', file));

        const xhr = new XMLHttpRequest();
        xhr.open('POST', form.action || window.location.href);
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');

        submitBtn.disabled = true;
        progress.hidden = false;
        progress.classList.remove('is-indeterminate');
        progressBar.style.width = '0%';
        progressLabel.textContent = '';

        xhr.upload.addEventListener('progress', (event) => {
            if (!event.lengthComputable) return;
            const percent = Math.round((event.loaded / event.total) * 100);
            progressBar.style.width = percent + '%';
            const label = form.dataset.uploadingText.replace('{count}', selectedFiles.length);
            progressLabel.textContent = label + ' (' + percent + '%)';
        });

        xhr.upload.addEventListener('load', () => {
            // The request body has fully reached the server; Image.save()
            // still has to write each file to Google Cloud Storage
            // synchronously before the response comes back, so switch to an
            // indeterminate state rather than leaving the bar frozen at 100%.
            progress.classList.add('is-indeterminate');
            progressLabel.textContent = form.dataset.savingText;
        });

        function fail() {
            submitBtn.disabled = false;
            progress.hidden = true;
            progressLabel.textContent = '';
            window.alert(form.dataset.uploadFailedText);
        }

        xhr.addEventListener('load', () => {
            if (xhr.status >= 200 && xhr.status < 400) {
                // The server responds with a redirect, but XHR follows
                // redirects transparently instead of navigating the browser
                // there — send the browser to the gallery change page
                // ourselves.
                window.location.href = form.dataset.successUrl;
            } else {
                fail();
            }
        });

        xhr.addEventListener('error', fail);

        xhr.send(formData);
    });
})();
