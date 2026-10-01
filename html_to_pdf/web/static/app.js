document.addEventListener('DOMContentLoaded', () => {
    // Elements
    const tabs = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');
    const form = document.getElementById('convert-form');
    const btnConvert = document.getElementById('btn-convert');
    const btnText = btnConvert.querySelector('.btn-text');
    const spinner = document.getElementById('spinner');
    const btnDownload = document.getElementById('btn-download');
    const btnExternal = document.getElementById('btn-external');
    const metaTags = document.getElementById('meta-tags');
    const badgeTime = document.getElementById('badge-time');
    const badgeSize = document.getElementById('badge-size');
    const placeholder = document.getElementById('preview-placeholder');
    const pdfViewer = document.getElementById('pdf-viewer');
    const dropzone = document.getElementById('dropzone');
    const fileUpload = document.getElementById('input-file-upload');
    const dropzoneText = document.getElementById('dropzone-text');
    const scaleInput = document.getElementById('opt-scale');
    const scaleVal = document.getElementById('scale-val');
    const btnLoadReference = document.getElementById('btn-load-reference');
    const presetPills = document.querySelectorAll('.preset-pill');

    let currentBlobUrl = null;
    let activeTabId = 'tab-path';

    // Tabs logic
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tabPanes.forEach(p => p.classList.remove('active'));

            tab.classList.add('active');
            activeTabId = tab.dataset.tab;
            document.getElementById(activeTabId).classList.add('active');
        });
    });

    // Scale slider feedback
    scaleInput.addEventListener('input', (e) => {
        scaleVal.textContent = `${Math.round(e.target.value * 100)}%`;
    });

    // Presets
    const presets = {
        'receipt': {
            format: 'A4',
            media_type: 'screen',
            margin: '0mm',
            single_page: true,
            print_background: true
        },
        'screen-a4': {
            format: 'A4',
            media_type: 'screen',
            margin: '0mm',
            single_page: false,
            print_background: true
        },
        'print-a4': {
            format: 'A4',
            media_type: 'print',
            margin: '10mm',
            single_page: false,
            print_background: true
        }
    };

    presetPills.forEach(pill => {
        pill.addEventListener('click', () => {
            presetPills.forEach(p => p.classList.remove('active'));
            pill.classList.add('active');

            const presetKey = pill.dataset.preset;
            const config = presets[presetKey];
            if (config) {
                document.getElementById('opt-format').value = config.format;
                document.getElementById('opt-media').value = config.media_type;
                document.getElementById('opt-margins').value = config.margin;
                document.getElementById('opt-single-page').checked = config.single_page;
                document.getElementById('opt-background').checked = config.print_background;
            }
        });
    });

    // Dropzone logic
    if (dropzone && fileUpload) {
        dropzone.addEventListener('click', () => fileUpload.click());

        fileUpload.addEventListener('change', () => {
            if (fileUpload.files.length > 0) {
                dropzoneText.textContent = `Selected: ${fileUpload.files[0].name}`;
            }
        });

        dropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropzone.classList.add('dragover');
        });

        dropzone.addEventListener('dragleave', () => {
            dropzone.classList.remove('dragover');
        });

        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) {
                fileUpload.files = e.dataTransfer.files;
                dropzoneText.textContent = `Selected: ${e.dataTransfer.files[0].name}`;
            }
        });
    }

    // Load reference receipt shortcut
    if (btnLoadReference) {
        btnLoadReference.addEventListener('click', () => {
            // Activate local path tab
            document.querySelector('[data-tab="tab-path"]').click();
            // Select receipt preset
            document.querySelector('[data-preset="receipt"]').click();
            // Submit form
            form.requestSubmit();
        });
    }

    // Form submit
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        // Extract options
        const format = document.getElementById('opt-format').value;
        const media_type = document.getElementById('opt-media').value;
        const margin = document.getElementById('opt-margins').value;
        const scale = parseFloat(document.getElementById('opt-scale').value);
        const single_page = document.getElementById('opt-single-page').checked;
        const print_background = document.getElementById('opt-background').checked;
        const landscape = document.getElementById('opt-landscape').checked;
        const wait_delay = parseInt(document.getElementById('opt-delay').value, 10) || 200;
        const expand_collapsible = document.getElementById('opt-expand-collapsible')?.checked ?? true;
        const locale = document.getElementById('opt-locale')?.value || 'en-US';

        let url = '';
        let requestOptions = {};
        let defaultFilename = 'document.pdf';

        if (activeTabId === 'tab-path') {
            const filePath = document.getElementById('input-file-path').value.trim();
            if (!filePath) {
                showToast('Please provide a file path', 'error');
                return;
            }
            url = '/api/convert/path';
            defaultFilename = filePath.split('/').pop().replace(/\.[^/.]+$/, '') + '.pdf';
            requestOptions = {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    file_path: filePath,
                    format,
                    landscape,
                    single_page,
                    media_type,
                    print_background,
                    margin,
                    scale,
                    wait_delay,
                    expand_collapsible,
                    locale,
                }),
            };
        } else if (activeTabId === 'tab-url') {
            const webUrl = document.getElementById('input-url').value.trim();
            if (!webUrl) {
                showToast('Please provide a web URL (http:// or https://)', 'error');
                return;
            }
            url = '/api/convert/url';
            try {
                const u = new URL(webUrl);
                defaultFilename = (u.hostname.replace(/[^a-zA-Z0-9]/g, '_') || 'webpage') + '.pdf';
            } catch {
                defaultFilename = 'webpage.pdf';
            }
            const use_firefox = document.getElementById('opt-firefox-cookies')?.checked ?? true;
            requestOptions = {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: webUrl,
                    format,
                    landscape,
                    single_page,
                    media_type,
                    print_background,
                    margin,
                    scale,
                    wait_delay,
                    use_firefox_cookies: use_firefox,
                    expand_collapsible,
                    locale,
                }),
            };
        } else if (activeTabId === 'tab-upload') {
            if (!fileUpload.files || fileUpload.files.length === 0) {
                showToast('Please select an HTML file to upload', 'error');
                return;
            }
            url = '/api/convert/upload';
            const formData = new FormData();
            formData.append('file', fileUpload.files[0]);
            formData.append('format', format);
            formData.append('landscape', landscape);
            formData.append('single_page', single_page);
            formData.append('media_type', media_type);
            formData.append('print_background', print_background);
            formData.append('margin', margin);
            formData.append('scale', scale);
            formData.append('wait_delay', wait_delay);
            formData.append('expand_collapsible', expand_collapsible);
            formData.append('locale', locale);

            defaultFilename = fileUpload.files[0].name.replace(/\.[^/.]+$/, '') + '.pdf';
            requestOptions = {
                method: 'POST',
                body: formData,
            };
        } else if (activeTabId === 'tab-code') {
            const htmlContent = document.getElementById('input-html-code').value;
            if (!htmlContent.trim()) {
                showToast('Please enter some HTML code', 'error');
                return;
            }
            url = '/api/convert/html';
            defaultFilename = 'rendered_code.pdf';
            requestOptions = {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    html_content: htmlContent,
                    format,
                    landscape,
                    single_page,
                    media_type,
                    print_background,
                    margin,
                    scale,
                    wait_delay,
                    expand_collapsible,
                    locale,
                }),
            };
        }

        // Start loading
        setLoading(true);

        try {
            const response = await fetch(url, requestOptions);
            if (!response.ok) {
                let errorMsg = 'Failed to generate PDF';
                try {
                    const errorJson = await response.json();
                    errorMsg = errorJson.detail || errorMsg;
                } catch {
                    errorMsg = await response.text() || errorMsg;
                }
                throw new Error(errorMsg);
            }

            const blob = await response.blob();
            const conversionTime = response.headers.get('X-Conversion-Time') || 'done';
            const pdfSize = response.headers.get('X-PDF-Size') || blob.size;

            // Revoke old blob
            if (currentBlobUrl) {
                URL.revokeObjectURL(currentBlobUrl);
            }

            currentBlobUrl = URL.createObjectURL(blob);

            // Display in viewer
            placeholder.style.display = 'none';
            pdfViewer.classList.remove('hidden');
            pdfViewer.src = currentBlobUrl;

            // Update action buttons
            btnDownload.href = currentBlobUrl;
            btnDownload.download = defaultFilename;
            btnDownload.style.display = 'inline-flex';

            btnExternal.href = currentBlobUrl;
            btnExternal.style.display = 'inline-flex';

            // Update stats
            badgeTime.textContent = conversionTime;
            badgeSize.textContent = `${(pdfSize / 1024).toFixed(1)} KB`;
            metaTags.style.display = 'flex';

            showToast('PDF generated successfully!', 'success');
        } catch (err) {
            console.error('Conversion error:', err);
            showToast(err.message || 'Error converting HTML to PDF', 'error');
        } finally {
            setLoading(false);
        }
    });

    function setLoading(isLoading) {
        if (isLoading) {
            btnConvert.disabled = true;
            btnText.textContent = 'Rendering PDF...';
            spinner.classList.remove('hidden');
        } else {
            btnConvert.disabled = false;
            btnText.textContent = 'Generate PDF';
            spinner.classList.add('hidden');
        }
    }

    function showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(10px)';
            toast.style.transition = 'all 0.2s ease-out';
            setTimeout(() => toast.remove(), 250);
        }, 4000);
    }
});
