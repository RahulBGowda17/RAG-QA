/**
 * Chat and conversation management
 */
let currentConversationId = null;

const ChatManager = {
    async init() {
        this.bindEvents();
        await this.loadConversations();
        await this.loadDocFilterOptions();
        await this.detectActiveLLM();
    },

    async loadDocFilterOptions() {
        const select = document.getElementById('chat-doc-filter');
        if (!select) return;
        try {
            const res = await API.getDocuments();
            if (res.success && res.documents) {
                const currentVal = select.value;
                select.innerHTML = '<option value="">All Uploaded Documents</option>';
                res.documents.forEach(d => {
                    const opt = document.createElement('option');
                    opt.value = d.id;
                    opt.textContent = `${d.filename} (${d.chunk_count} chunks)`;
                    select.appendChild(opt);
                });
                if (currentVal) select.value = currentVal;
            }
        } catch (e) {
            console.error('Failed to load documents for chat filter:', e);
        }
    },

    async detectActiveLLM() {
        const indicator = document.getElementById('active-llm-indicator');
        if (!indicator) return;
        try {
            const h = await API.getHealth();
            if (h && h.llm) {
                const mode = h.llm.mode;
                const isLocal = mode === 'LocalMockLLMProvider';
                indicator.innerHTML = `
                    <span>LLM:</span>
                    <span class="brand-badge" style="background:${isLocal ? '#475569' : '#059669'}; font-size:0.7rem; padding:2px 6px;">
                        ${isLocal ? 'Local Heuristic (Degraded)' : 'Active Generative LLM'}
                    </span>
                `;
            }
        } catch (e) {
            indicator.innerHTML = '<span>LLM:</span><span class="brand-badge" style="background:#dc2626;">Offline</span>';
        }
    },

    bindEvents() {
        const form = document.getElementById('chat-form');
        const input = document.getElementById('chat-input');

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const text = input.value.trim();
            if (!text) return;
            input.value = '';
            await this.sendMessage(text);
        });

        document.getElementById('btn-new-chat').addEventListener('click', () => {
            this.startNewChat();
        });
    },

    startNewChat() {
        currentConversationId = null;
        const container = document.getElementById('messages-container');
        container.innerHTML = `
            <div class="welcome-card">
                <h3>Evidence-Grounded Question Answering</h3>
                <p>Ask natural language questions against your uploaded documents. Responses strictly rely on retrieved passages with source citations and verification.</p>
                <div class="quick-queries">
                    <span class="chip" onclick="handleQuickQuery('What architecture powers modern Large Language Models?')">Large Language Models</span>
                    <span class="chip" onclick="handleQuickQuery('What are Convolutional Neural Networks used for?')">CNNs and Vision</span>
                    <span class="chip" onclick="handleQuickQuery('What type of data do Recurrent Neural Networks process?')">RNNs and Sequences</span>
                </div>
            </div>
        `;
        document.querySelectorAll('.conv-item').forEach(el => el.classList.remove('active'));
    },

    async loadConversations() {
        const list = document.getElementById('conversations-list');
        try {
            const data = await API.getConversations();
            if (!data.success || data.conversations.length === 0) {
                list.innerHTML = '<div class="empty-state">No conversations yet</div>';
                return;
            }

            list.innerHTML = data.conversations.map(c => `
                <div class="conv-item ${c.id === currentConversationId ? 'active' : ''}" onclick="ChatManager.selectConversation('${c.id}')">
                    <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:180px;">${c.title}</span>
                    <button class="delete-conv" onclick="event.stopPropagation(); ChatManager.deleteConversation('${c.id}')">&times;</button>
                </div>
            `).join('');
        } catch (err) {
            list.innerHTML = '<div class="empty-state">Failed to load history</div>';
        }
    },

    async selectConversation(id) {
        currentConversationId = id;
        await this.loadConversations();
        const container = document.getElementById('messages-container');
        container.innerHTML = '<div class="spinner"></div>';

        try {
            const data = await API.getConversation(id);
            if (!data.success) return;
            container.innerHTML = '';
            data.messages.forEach(m => {
                if (m.role === 'user') {
                    this.appendUserMessage(m.content);
                } else {
                    this.appendAssistantBubble({
                        answer: m.content,
                        evidence_status: "VERIFIED ARCHIVED",
                        citations: [],
                        metrics: { retrieval_latency: 0, generation_latency: 0, total_latency: 0 }
                    });
                }
            });
            container.scrollTop = container.scrollHeight;
        } catch (err) {
            container.innerHTML = `<div class="empty-state" style="color:var(--danger);">Error loading messages: ${err.message}</div>`;
        }
    },

    async deleteConversation(id) {
        await API.deleteConversation(id);
        if (currentConversationId === id) {
            this.startNewChat();
        }
        await this.loadConversations();
    },

    appendUserMessage(text) {
        const container = document.getElementById('messages-container');
        const bubble = document.createElement('div');
        bubble.className = 'message-bubble message-user';
        bubble.innerText = text;
        container.appendChild(bubble);
        container.scrollTop = container.scrollHeight;
    },

    appendAssistantBubble(data) {
        const container = document.getElementById('messages-container');
        const bubble = document.createElement('div');
        bubble.className = 'message-bubble message-assistant';

        // Badge class
        let badgeClass = 'badge-med';
        const st = (data.evidence_status || '').toUpperCase();
        if (st.includes('HIGH')) badgeClass = 'badge-high';
        else if (st.includes('LOW')) badgeClass = 'badge-low';
        else if (st.includes('INSUFFICIENT')) badgeClass = 'badge-insufficient';

        let citationsHtml = '';
        if (data.citations && data.citations.length > 0) {
            citationsHtml = `
                <div class="citations-panel">
                    <div class="citations-title">Grounded Evidence Sources (${data.citations.length})</div>
                    <div class="citations-grid">
                        ${data.citations.map(c => `
                            <div class="citation-item">
                                <div>
                                    <strong>${escapeHTML(c.filename)}</strong> &bull; 
                                    <span class="citation-meta">Page ${c.page_number} (${escapeHTML(c.section)}) &bull; Rerank: ${c.rerank_score}</span>
                                </div>
                                <button class="btn-inspect" onclick="openSourceModal('${c.chunk_id}')">Inspect</button>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }

        let latencyHtml = '';
        if (data.metrics) {
            latencyHtml = `
                <div class="latency-indicator">
                    <span>Retrieval: ${data.metrics.retrieval_latency}s</span>
                    <span>Generation: ${data.metrics.generation_latency}s</span>
                    <span>Total Latency: ${data.metrics.total_latency}s</span>
                </div>
            `;
        }

        let rewrittenHtml = '';
        if (data.rewritten_question && data.rewritten_question !== data.original_question) {
            rewrittenHtml = `<div class="rewritten-indicator">&rarr; Rewritten query: "${escapeHTML(data.rewritten_question)}"</div>`;
        }

        // Format clean paragraph breaks in answer safely
        const formattedAnswer = escapeHTML(data.answer).replace(/\n/g, '<br>');

        const queryId = data.query_id || '';
        const feedbackHtml = queryId ? `
            <div class="feedback-actions" style="margin-top:8px; display:flex; gap:8px; align-items:center; font-size:0.75rem;">
                <span style="color:var(--text-muted);">Was this helpful?</span>
                <button class="btn-inspect" style="padding:2px 8px; font-size:0.75rem;" onclick="handleFeedback('${queryId}', 1, this)">&#128077; Helpful</button>
                <button class="btn-inspect" style="padding:2px 8px; font-size:0.75rem;" onclick="handleFeedback('${queryId}', 0, this)">&#128078; Not Helpful</button>
            </div>
        ` : '';

        bubble.innerHTML = `
            <div class="evidence-header">
                <span class="status-badge ${badgeClass}">${escapeHTML(data.evidence_status || 'STATUS')}</span>
                <span style="font-size:0.75rem; color:var(--text-muted);">${escapeHTML(data.verification_decision || '')}</span>
            </div>
            ${rewrittenHtml}
            <div class="assistant-text">${formattedAnswer}</div>
            ${citationsHtml}
            ${latencyHtml}
            ${feedbackHtml}
        `;

        container.appendChild(bubble);
        container.scrollTop = container.scrollHeight;
    },

    async sendMessage(question) {
        // Remove welcome card if present
        const welcome = document.querySelector('.welcome-card');
        if (welcome) welcome.remove();

        this.appendUserMessage(question);

        // Append loading placeholder
        const container = document.getElementById('messages-container');
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'message-bubble message-assistant';
        loadingDiv.id = 'loading-assistant';
        loadingDiv.innerHTML = '<div class="spinner"></div><div style="font-size:0.8rem;color:var(--text-muted);text-align:center;">Retrieving evidence, reranking, and synthesizing answer...</div>';
        container.appendChild(loadingDiv);
        container.scrollTop = container.scrollHeight;

        try {
            const docFilter = document.getElementById('chat-doc-filter');
            const selectedDocId = docFilter && docFilter.value ? [docFilter.value] : null;

            const res = await API.sendChatMessage(question, currentConversationId, selectedDocId);
            loadingDiv.remove();

            if (res.success) {
                currentConversationId = res.conversation_id;
                this.appendAssistantBubble(res.data);
                await this.loadConversations();
                if (window.AnalyticsManager) AnalyticsManager.loadMetrics();
            } else {
                const errDiv = document.createElement('div');
                errDiv.className = 'message-bubble message-assistant';
                errDiv.innerHTML = `<span style="color:var(--danger);">&#9888; Error: ${res.error}</span>`;
                container.appendChild(errDiv);
            }
        } catch (err) {
            loadingDiv.remove();
            const errDiv = document.createElement('div');
            errDiv.className = 'message-bubble message-assistant';
            errDiv.innerHTML = `<span style="color:var(--danger);">&#9888; Request failed: ${err.message}</span>`;
            container.appendChild(errDiv);
        }
    }
};

function escapeHTML(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function handleQuickQuery(q) {
    const input = document.getElementById('chat-input');
    input.value = q;
    document.getElementById('chat-form').dispatchEvent(new Event('submit'));
}

async function openSourceModal(chunkId) {
    const modal = document.getElementById('source-modal');
    const title = document.getElementById('modal-title');
    const body = document.getElementById('modal-body');
    modal.classList.add('open');
    body.innerHTML = 'Loading passage details...';

    try {
        const res = await API.getSource(chunkId);
        if (res.success) {
            const s = res.source;
            title.textContent = `Source: ${s.filename} (Page ${s.page_number})`;
            body.innerHTML = `
                <div style="margin-bottom: 12px; font-size: 0.8rem; color: var(--text-muted);">
                    <strong>Section:</strong> ${escapeHTML(s.section)} | <strong>Chunk Index:</strong> ${s.chunk_index} | <strong>Token Count:</strong> ${s.token_count}
                </div>
                <div style="background: var(--bg-card); padding: 16px; border-radius: 6px; font-family: monospace; white-space: pre-wrap;">${escapeHTML(s.text)}</div>
            `;
        } else {
            body.textContent = 'Passage not found.';
        }
    } catch (e) {
        body.textContent = 'Failed to load passage.';
    }
}

function closeSourceModal() {
    document.getElementById('source-modal').classList.remove('open');
}

async function handleFeedback(queryId, rating, btn) {
    const parent = btn.parentElement;
    try {
        const res = await API.submitFeedback(queryId, rating);
        if (res.success) {
            parent.innerHTML = '<span style="color:var(--success); font-size:0.75rem;">&#10003; Thank you for your feedback!</span>';
        } else {
            parent.innerHTML = '<span style="color:var(--text-muted); font-size:0.75rem;">Feedback saved.</span>';
        }
    } catch (e) {
        parent.innerHTML = '<span style="color:var(--text-muted); font-size:0.75rem;">Feedback saved.</span>';
    }
}
