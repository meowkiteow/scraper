/**
 * Authenticated API client for the FastAPI backend.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class ApiClient {
    constructor() {
        this.token = null;
        if (typeof window !== 'undefined') {
            this.token = localStorage.getItem('token');
        }
    }

    setToken(token) {
        this.token = token;
        if (typeof window !== 'undefined') {
            localStorage.setItem('token', token);
        }
    }

    clearToken() {
        this.token = null;
        if (typeof window !== 'undefined') {
            localStorage.removeItem('token');
        }
    }

    getToken() {
        if (!this.token && typeof window !== 'undefined') {
            this.token = localStorage.getItem('token');
        }
        return this.token;
    }

    async fetch(path, options = {}) {
        const url = `${API_BASE}${path}`;
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers,
        };

        const token = this.getToken();
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const res = await fetch(url, { ...options, headers });

        if (res.status === 401) {
            this.clearToken();
            if (typeof window !== 'undefined') {
                window.location.href = '/login';
            }
            throw new Error('Unauthorized');
        }

        if (!res.ok) {
            const error = await res.json().catch(() => ({ detail: 'Request failed' }));
            throw new Error(error.detail || error.message || 'Request failed');
        }

        return res.json();
    }

    get(path) {
        return this.fetch(path);
    }

    post(path, data) {
        return this.fetch(path, { method: 'POST', body: JSON.stringify(data) });
    }

    put(path, data) {
        return this.fetch(path, { method: 'PUT', body: JSON.stringify(data) });
    }

    delete(path) {
        return this.fetch(path, { method: 'DELETE' });
    }

    // ── Auth ──
    async signup(email, password, fullName) {
        const data = await this.post('/api/auth/signup', { email, password, full_name: fullName });
        this.setToken(data.access_token);
        return data;
    }

    async login(email, password) {
        const data = await this.post('/api/auth/login', { email, password });
        this.setToken(data.access_token);
        return data;
    }

    logout() {
        this.clearToken();
        if (typeof window !== 'undefined') {
            window.location.href = '/login';
        }
    }

    getMe() {
        return this.get('/api/auth/me');
    }

    // ── Accounts ──
    getAccounts() { return this.get('/api/accounts'); }
    createAccount(data) { return this.post('/api/accounts', data); }
    updateAccount(id, data) { return this.put(`/api/accounts/${id}`, data); }
    deleteAccount(id) { return this.delete(`/api/accounts/${id}`); }
    testSmtp(id) { return this.post(`/api/accounts/${id}/test-smtp`); }
    sendTestEmail(id) { return this.post(`/api/accounts/${id}/send-test`); }
    checkDns(id) { return this.post(`/api/accounts/${id}/check-dns`); }
    toggleWarmup(id) { return this.post(`/api/accounts/${id}/warmup/toggle`); }
    getWarmupStats(id) { return this.get(`/api/accounts/${id}/warmup/stats`); }
    quickSend(id, data) { return this.post(`/api/accounts/${id}/quick-send`, data); }

    // ── Campaigns ──
    getCampaigns() { return this.get('/api/campaigns'); }
    createCampaign(data) { return this.post('/api/campaigns', data); }
    getCampaign(id) { return this.get(`/api/campaigns/${id}`); }
    updateCampaign(id, data) { return this.put(`/api/campaigns/${id}`, data); }
    deleteCampaign(id) { return this.delete(`/api/campaigns/${id}`); }
    startCampaign(id) { return this.post(`/api/campaigns/${id}/start`); }
    pauseCampaign(id) { return this.post(`/api/campaigns/${id}/pause`); }
    duplicateCampaign(id) { return this.post(`/api/campaigns/${id}/duplicate`); }
    getCampaignStats(id) { return this.get(`/api/campaigns/${id}/stats`); }

    // ── Steps ──
    addStep(campaignId, data) { return this.post(`/api/campaigns/${campaignId}/steps`, data); }
    updateStep(stepId, data) { return this.put(`/api/campaigns/steps/${stepId}`, data); }
    deleteStep(stepId) { return this.delete(`/api/campaigns/steps/${stepId}`); }

    // ── Leads ──
    getLeads(params = {}) {
        const q = new URLSearchParams(params).toString();
        return this.get(`/api/leads${q ? '?' + q : ''}`);
    }
    getCampaignLeads(campaignId, params = {}) {
        const q = new URLSearchParams(params).toString();
        return this.get(`/api/leads/campaigns/${campaignId}${q ? '?' + q : ''}`);
    }
    importLeads(campaignId, leads) {
        return this.post(`/api/leads/campaigns/${campaignId}`, { leads });
    }
    getSuppression() { return this.get('/api/leads/suppression'); }
    exportLeads(status) { return this.post('/api/leads/export', { status }); }

    // ── Inbox ──
    getInbox(params = {}) {
        const q = new URLSearchParams(params).toString();
        return this.get(`/api/inbox${q ? '?' + q : ''}`);
    }
    getMessage(id) { return this.get(`/api/inbox/${id}`); }
    setLabel(id, label) { return this.post(`/api/inbox/${id}/label`, { label }); }
    markRead(id) { return this.post(`/api/inbox/${id}/mark-read`); }
    syncInbox() { return this.post('/api/inbox/sync'); }

    // ── Analytics ──
    getOverview() { return this.get('/api/analytics/overview'); }
    getCampaignAnalytics(id) { return this.get(`/api/analytics/campaigns/${id}`); }
    getStepAnalytics(id) { return this.get(`/api/analytics/campaigns/${id}/steps`); }
    getAccountAnalytics(id) { return this.get(`/api/analytics/accounts/${id}`); }

    // ── Billing ──
    getPlans() { return this.get('/api/billing/plans'); }
    getSubscription() { return this.get('/api/billing/subscription'); }
    checkout(plan) { return this.post(`/api/billing/checkout?plan=${plan}`); }
    billingPortal() { return this.post('/api/billing/portal'); }

    // ── Health ──
    health() { return this.get('/api/health'); }
}

const api = new ApiClient();
export default api;
