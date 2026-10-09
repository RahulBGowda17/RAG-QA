/**
 * Documents management tab logic
 */
const DocumentsManager = {
    async init() {
        this.bindEvents();
        await this.loadDocuments();
    },

    bindEvents() {
        const fileInput = document.getElementById('file-input');
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.handleUpload(e.target.files[0]);
            }
        });

        const dropzone = document.getElementById('dropzone');
        dropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropzone.style.borderColor = 'var(--primary)';
        });
        dropzone.addEventListener('dragleave', () => {
            dropzone.style.borderColor = 'var(--border-color)';
        });
        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.style.borderColor = 'var(--border-color)';
            if (e.dataTransfer.files.length > 0) {
                this.handleUpload(e.dataTransfer.files[0]);
            }
        });

        document.getElementById('btn-rebuild-all').addEventListener('click', async () => {
            const btn = document.getElementById('btn-rebuild-all');
            const originalText = btn.innerText;
            btn.innerText = 'Rebuilding Indices...';
            btn.disabled = true;
            try {
                const res = await API.reindexAll();
                if (res.success) {
                    alert('All FAISS vector embeddings and BM25 indices rebuilt successfully!');
                } else {
                    alert('Failed to rebuild indices: ' + res.error);
                }
                await this.loadDocuments();
            } finally {
                btn.innerText = originalText;
                btn.disabled = false;
            }
        });
    },

    async handleUpload(file) {
        const statusEl = document.getElementById('upload-status');
        statusEl.innerHTML = `<span style="color: var(--primary);">Uploading and indexing ${file.name}...</span>`;

        const formData = new FormData();
        formData.append('file', file);

        try {
            const data = await API.uploadDocument(formData);
            if (data.success) {
                statusEl.innerHTML = `<span style="color: var(--success);">&#10003; Indexed ${file.name} successfully (${data.document.chunk_count} chunks created).</span>`;
                await this.loadDocuments();
                if (window.ChatManager && typeof ChatManager.loadDocFilterOptions === 'function') {
                    ChatManager.loadDocFilterOptions();
                }
            } else {
                statusEl.innerHTML = `<span style="color: var(--danger);">&#9888; Upload failed: ${data.error}</span>`;
            }
        } catch (err) {
            statusEl.innerHTML = `<span style="color: var(--danger);">&#9888; Upload error: ${err.message}</span>`;
        }
    },

    async loadDocuments() {
        const tbody = document.getElementById('documents-tbody');
        const badge = document.getElementById('doc-count-badge');
        try {
            const data = await API.getDocuments();
            if (!data.success || data.documents.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8" class="text-center">No documents uploaded yet.</td></tr>';
                badge.innerText = '0';
                return;
            }

            badge.innerText = data.documents.length;
            tbody.innerHTML = data.documents.map(d => `
                <tr>
                    <td><strong>${escapeHTML(d.filename)}</strong></td>
                    <td><span class="brand-badge" style="background:#334155;color:#f8fafc;">${escapeHTML(d.file_type.toUpperCase())}</span></td>
                    <td>${(d.file_size / 1024).toFixed(1)} KB</td>
                    <td>${d.page_count}</td>
                    <td>${d.chunk_count}</td>
                    <td><span class="status-badge ${d.status === 'indexed' ? 'badge-high' : 'badge-low'}">${escapeHTML(d.status)}</span></td>
                    <td>${d.created_at ? escapeHTML(d.created_at.split(' ')[0]) : '-'}</td>
                    <td>
                        <div style="display:flex; gap:6px; flex-wrap:wrap;">
                            <button class="btn-inspect" onclick="DocumentsManager.viewDocChunks('${d.id}')">View Chunks</button>
                            <button class="btn-inspect" style="background:var(--primary-light, #1e40af); color:#fff;" onclick="DocumentsManager.reindexDoc('${d.id}')">Re-index</button>
                            <button class="btn-danger-sm" onclick="DocumentsManager.deleteDoc('${d.id}')">Delete</button>
                        </div>
                    </td>
                </tr>
            `).join('');
        } catch (err) {
            tbody.innerHTML = `<tr><td colspan="8" class="text-center" style="color:var(--danger);">Failed to load documents: ${escapeHTML(err.message)}</td></tr>`;
        }
    },

    async viewDocChunks(docId) {
        const modal = document.getElementById('source-modal');
        const title = document.getElementById('modal-title');
        const body = document.getElementById('modal-body');
        modal.classList.add('open');
        body.textContent = 'Loading document chunks...';

        try {
            const res = await API.getDocument(docId);
            if (res.success) {
                title.textContent = `Chunks for: ${res.document.filename} (${res.chunks.length} chunks)`;
                body.innerHTML = res.chunks.map(c => `
                    <div style="background:var(--bg-card); padding:12px; border-radius:6px; margin-bottom:12px;">
                        <div style="font-size:0.75rem; color:var(--text-muted); margin-bottom:6px;">
                            <strong>Chunk #${c.chunk_index}</strong> | Page: ${c.page_number} | Section: ${escapeHTML(c.section)} | Tokens: ${c.token_count}
                        </div>
                        <div style="font-family:monospace; font-size:0.85rem; white-space:pre-wrap;">${escapeHTML(c.text)}</div>
                    </div>
                `).join('');
            } else {
                body.textContent = 'Failed to load chunks.';
            }
        } catch (e) {
            body.textContent = 'Error: ' + e.message;
        }
    },

    async reindexDoc(id) {
        if (!confirm('Re-index this document? Its text chunks, embeddings, and BM25 postings will be refreshed.')) {
            return;
        }
        try {
            const res = await API.reindexDoc(id);
            if (res.success) {
                alert('Document re-indexed successfully!');
                await this.loadDocuments();
                if (window.AnalyticsManager) AnalyticsManager.loadMetrics();
                if (window.ChatManager && typeof ChatManager.loadDocFilterOptions === 'function') {
                    ChatManager.loadDocFilterOptions();
                }
            } else {
                alert('Failed to re-index: ' + (res.error || 'Unknown error'));
            }
        } catch (e) {
            alert('Error during re-indexing: ' + e.message);
        }
    },

    async deleteDoc(id) {
        if (!confirm('Are you sure you want to delete this document? The vector and keyword indices will be automatically updated.')) {
            return;
        }
        const data = await API.deleteDocument(id);
        if (data.success) {
            await this.loadDocuments();
            if (window.AnalyticsManager) AnalyticsManager.loadMetrics();
            if (window.ChatManager && typeof ChatManager.loadDocFilterOptions === 'function') {
                ChatManager.loadDocFilterOptions();
            }
        } else {
            alert('Failed to delete document: ' + data.error);
        }
    }
};
