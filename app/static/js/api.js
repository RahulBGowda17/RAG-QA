/**
 * API client module for REST endpoints
 */
const API = {
    async getDocuments() {
        const res = await fetch('/api/documents');
        return await res.json();
    },

    async getDocument(id) {
        const res = await fetch(`/api/documents/${id}`);
        return await res.json();
    },

    async uploadDocument(formData) {
        const res = await fetch('/api/documents/upload', {
            method: 'POST',
            body: formData
        });
        return await res.json();
    },

    async deleteDocument(id) {
        const res = await fetch(`/api/documents/${id}`, {
            method: 'DELETE'
        });
        return await res.json();
    },

    async reindexAll() {
        const res = await fetch('/api/documents/rebuild', {
            method: 'POST'
        });
        return await res.json();
    },

    async sendChatMessage(question, conversationId = null, documentIds = null) {
        const payload = { question, conversation_id: conversationId };
        if (documentIds && documentIds.length > 0) {
            payload.document_ids = documentIds;
        }
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        return await res.json();
    },

    async getConversations() {
        const res = await fetch('/api/conversations');
        return await res.json();
    },

    async getConversation(id) {
        const res = await fetch(`/api/conversations/${id}`);
        return await res.json();
    },

    async deleteConversation(id) {
        const res = await fetch(`/api/conversations/${id}`, {
            method: 'DELETE'
        });
        return await res.json();
    },

    async getSource(chunkId) {
        const res = await fetch(`/api/sources/${chunkId}`);
        return await res.json();
    },

    async getAnalytics() {
        const res = await fetch('/api/analytics');
        return await res.json();
    },

    async runEvaluation() {
        const res = await fetch('/api/evaluation/run', {
            method: 'POST'
        });
        return await res.json();
    },

    async reindexDoc(id) {
        const res = await fetch(`/api/documents/${id}/reindex`, {
            method: 'POST'
        });
        return await res.json();
    },

    async getHealth() {
        const res = await fetch('/api/health');
        return await res.json();
    },

    async submitFeedback(queryId, rating) {
        const res = await fetch('/api/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query_id: queryId, rating: rating })
        });
        return await res.json();
    }
};
