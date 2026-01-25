/**
 * Telegram转发器Web管理系统 - 主JavaScript文件
 * 提供通用的工具函数和交互功能
 */

// 全局配置
const CONFIG = {
    API_BASE_URL: '/api',
    REFRESH_INTERVAL: 30000,
    ANIMATION_DURATION: 300,
    TOAST_DURATION: 3000,
    REQUEST_TIMEOUT: 8000,
    GET_RETRY: 1
};

// 通用工具类
class Utils {
    static formatNumber(num) {
        if (num === null || num === undefined) return '0';
        return num.toLocaleString('zh-CN');
    }
    static formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    static formatTimeAgo(date) {
        const now = new Date();
        const diff = Math.floor((now - new Date(date)) / 1000);
        if (diff < 60) return '刚刚';
        if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`;
        if (diff < 604800) return `${Math.floor(diff / 86400)}天前`;
        return new Date(date).toLocaleDateString('zh-CN');
    }
    static deepClone(obj) { return JSON.parse(JSON.stringify(obj)); }
    static debounce(func, wait) { let timeout; return function (...args) { const later = () => { clearTimeout(timeout); func(...args); }; clearTimeout(timeout); timeout = setTimeout(later, wait); }; }
    static throttle(func, limit) { let inThrottle; return function () { const args = arguments; const context = this; if (!inThrottle) { func.apply(context, args); inThrottle = true; setTimeout(() => inThrottle = false, limit); } }; }
    static generateUUID() { return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) { const r = Math.random() * 16 | 0; const v = c == 'x' ? r : (r & 0x3 | 0x8); return v.toString(16); }); }
    static isValidEmail(email) { const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/; return regex.test(email); }
    static isValidTelegramHandle(handle) { const patterns = [/^@[a-zA-Z0-9_]{5,32}$/, /^https:\/\/t\.me\/[a-zA-Z0-9_]{5,32}$/, /^[a-zA-Z0-9_]{5,32}$/, /^-?\d+$/]; return patterns.some(p => p.test(handle)); }
    static async copyToClipboard(text) {
        try { await navigator.clipboard.writeText(text); if (window.notificationManager) notificationManager.success('已复制到剪贴板'); } catch (err) { if (window.notificationManager) notificationManager.error('复制失败'); }
    }
    static getCookie(name) {
        let value = "; " + document.cookie;
        let parts = value.split("; " + name + "=");
        if (parts.length === 2) return decodeURIComponent(parts.pop().split(";").shift());
        return null;
    }
}

// API请求管理类
class ApiManager {
    constructor() { this.baseURL = CONFIG.API_BASE_URL; this.headers = { 'Content-Type': 'application/json', 'Accept': 'application/json' }; this.timeout = CONFIG.REQUEST_TIMEOUT; }
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const method = (options.method || 'GET').toUpperCase();

        // 如果正在重定向，中止所有后续请求防止卡顿
        if (this.isRedirecting) return new Promise(() => { });

        const maxRetry = method === 'GET' ? (CONFIG.GET_RETRY || 0) : 0;
        let attempt = 0;
        let lastErr;
        while (attempt <= maxRetry) {
            const controller = new AbortController();
            const t = options.timeout || this.timeout;
            const timer = setTimeout(() => controller.abort(), t);
            try {
                const config = { headers: { ...this.headers }, credentials: 'include', cache: 'no-store', ...options, signal: options.signal || controller.signal };

                // 自动注入 CSRF Token (Phase 2 Security)
                const csrfToken = Utils.getCookie('csrf_token');
                if (csrfToken) {
                    config.headers['X-CSRF-Token'] = csrfToken;
                }

                const response = await fetch(url, config);

                // 处理 401 未授权
                if (response.status === 401) {
                    if (!this.isRedirecting && window.location.pathname !== '/login') {
                        this.isRedirecting = true;
                        window.location.href = '/login';
                    }
                    return new Promise(() => { }); // 中断后续流
                }

                const contentType = response.headers.get('content-type') || '';
                let data;
                if (contentType.includes('application/json')) {
                    data = await response.json();
                } else {
                    data = { success: response.ok };
                }

                if (!response.ok) {
                    const status = response.status;
                    if (method === 'GET' && (status === 502 || status === 503) && attempt < maxRetry) {
                        attempt++;
                        await new Promise(r => setTimeout(r, 500 * attempt));
                        continue;
                    }

                    // 提取更有意义的错误信息
                    let errMsg = `错误 (${status})`;
                    let traceId = data && data.trace_id ? data.trace_id : response.headers.get('X-Trace-ID');

                    if (data && data.error) errMsg = data.error;
                    else if (data && data.message) errMsg = data.message;
                    else if (status === 403) errMsg = "权限不足，访问被拒绝";
                    else if (status === 404) errMsg = "资源不存在";
                    else if (status === 500) errMsg = "服务器内部错误";

                    if (traceId) {
                        errMsg += ` [追踪ID: ${traceId}]`;
                    }

                    const error = new Error(errMsg);
                    error.status = status;
                    error.data = data;
                    error.traceId = traceId;
                    throw error;
                }
                return data;
            } catch (e) {
                lastErr = e;
                if (e.name === 'AbortError') throw new Error("请求超时，请稍后重试");
                if (method === 'GET' && attempt < maxRetry) {
                    attempt++;
                    await new Promise(r => setTimeout(r, 500 * attempt));
                    continue;
                }
                throw lastErr;
            } finally {
                clearTimeout(timer);
            }
        }
        throw lastErr;
    }
    async get(endpoint) { return this.request(endpoint, { method: 'GET' }); }
    async post(endpoint, data) { return this.request(endpoint, { method: 'POST', body: JSON.stringify(data) }); }
    async put(endpoint, data) { return this.request(endpoint, { method: 'PUT', body: JSON.stringify(data) }); }
    async delete(endpoint) { return this.request(endpoint, { method: 'DELETE' }); }
    // 业务方法
    getStatsOverview() { return this.get('/stats/overview'); }
    getStatsDistribution() { return this.get('/stats/distribution'); }
    getStatsSystemResources() { return this.get('/stats/system_resources'); }
    getRules(params) { const q = params ? ('?' + new URLSearchParams(params).toString()) : ''; return this.get('/rules' + q); }
    getRule(id) { return this.get(`/rules/${id}`); }
    createRule(payload) { return this.post('/rules', payload); }
    updateRule(id, payload) { return this.put(`/rules/${id}`, payload); }
    toggleRule(id) { return this.post(`/rules/${id}/toggle`, {}); }
    deleteRule(id) { return this.delete(`/rules/${id}`); }
    addKeywordsToRule(id, payload) { return this.post(`/rules/${id}/keywords`, payload); }
    deleteKeywordsFromRule(id, payload) { return this.delete(`/rules/${id}/keywords`, payload); }
    addReplaceRulesToRule(id, payload) { return this.post(`/rules/${id}/replace-rules`, payload); }
    deleteReplaceRulesFromRule(id, payload) { return this.delete(`/rules/${id}/replace-rules`, payload); }
    getChats() { return this.get('/chats'); }
    getConfig() { return this.get('/config'); }
    updateConfig(payload) { return this.post('/config', payload); }
    getVisualizationGraph() { return this.get('/visualization/graph'); }
    listLogFiles() { return this.get('/logs/files'); }
    tailLog(query) { const q = new URLSearchParams(query).toString(); return this.get(`/logs/tail?${q}`); }
    downloadLogFileUrl(file) { return `${this.baseURL}/logs/download?file=${encodeURIComponent(file)}`; }
    getStatsSeries(params) { const q = params ? ('?' + new URLSearchParams(params).toString()) : ''; return this.get('/stats/series' + q); }
    getUsers() { return this.get('/users'); }
    toggleUserAdmin(id) { return this.post(`/users/${id}/toggle_admin`, {}); }
    toggleUserActive(id) { return this.post(`/users/${id}/toggle_active`, {}); }
    deleteUser(id) { return this.delete(`/users/${id}`); }
    getUserSettings() { return this.get('/users/settings'); }
    updateUserSettings(payload) { return this.post('/users/settings', payload); }
    // 设置
    getSettings() { return this.get('/settings'); }
    updateSettings(payload) { return this.put('/settings', payload); }
    getSettingsMeta() { return this.get('/settings/meta'); }
    getCurrentUser() { return this.get('/users/me'); }
    // 系统监控与日志
    getTasks(params) { const q = params ? ('?' + new URLSearchParams(params).toString()) : ''; return this.get('/system/tasks' + q); }
    getAuditLogs(params) { const q = params ? ('?' + new URLSearchParams(params).toString()) : ''; return this.get('/system/audit/logs' + q); }
    listLogFiles() { return this.get('/system/logs/list'); }
    getLogView(filename) { return this.get(`/system/logs/view?filename=${encodeURIComponent(filename)}`); }
    getErrorLogs(limit = 20) { return this.get(`/system/logs/error_logs?limit=${limit}`); }

    // 归档系统
    getArchiveStatus() { return this.get('/system/archive-status'); }
    triggerArchive() { return this.post('/system/archive/trigger', {}); }
}

// 通知管理类
class NotificationManager {
    constructor() { this.container = this.createContainer(); }
    createContainer() { let container = document.getElementById('notification-container'); if (!container) { container = document.createElement('div'); container.id = 'notification-container'; container.className = 'position-fixed top-0 end-0 p-3'; container.style.zIndex = '1060'; document.body.appendChild(container); } return container; }
    show(message, type = 'info', duration = CONFIG.TOAST_DURATION) { const toast = this.createToast(message, type); this.container.appendChild(toast); setTimeout(() => { toast.classList.add('show'); }, 100); setTimeout(() => { this.hide(toast); }, duration); return toast; }
    createToast(message, type) {
        const toast = document.createElement('div'); toast.className = `toast align-items-center text-white bg-${type} border-0`; toast.setAttribute('role', 'alert'); const iconMap = { success: 'check-circle', error: 'exclamation-triangle', warning: 'exclamation-triangle', info: 'info-circle', danger: 'exclamation-triangle' }; const icon = iconMap[type] || 'info-circle'; toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    <i class="bi bi-${icon} me-2"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" 
                        data-bs-dismiss="toast" onclick="notificationManager.hide(this.closest('.toast'))"></button>
            </div>
        `; return toast;
    }
    hide(toast) { toast.classList.add('hiding'); setTimeout(() => { if (toast.parentNode) { toast.parentNode.removeChild(toast); } }, CONFIG.ANIMATION_DURATION); }
    success(m) { return this.show(m, 'success'); }
    error(m) { return this.show(m, 'danger'); }
    warning(m) { return this.show(m, 'warning'); }
    info(m) { return this.show(m, 'info'); }
}

// 加载管理类
class LoadingManager {
    constructor() { this.loadingElements = new Set(); }
    show(element, text = '加载中...') {
        if (typeof element === 'string') { element = document.querySelector(element); } if (!element) return;
        element.classList.add('loading'); element.setAttribute('data-original-text', element.textContent);
        if (element.tagName === 'BUTTON') {
            element.disabled = true;
            element.innerHTML = `<span class="spinner-border spinner-border-sm me-2" role="status"><span class="visually-hidden">Loading...</span></span>${text}`;
        }
        this.loadingElements.add(element);
    }
    hide(element) {
        if (typeof element === 'string') { element = document.querySelector(element); } if (!element) return;
        element.classList.remove('loading');
        if (element.tagName === 'BUTTON') {
            element.disabled = false; const originalText = element.getAttribute('data-original-text'); if (originalText) { element.textContent = originalText; element.removeAttribute('data-original-text'); }
        }
        this.loadingElements.delete(element);
    }
    hideAll() { this.loadingElements.forEach(el => this.hide(el)); }
}

// 主题管理类
class ThemeManager { constructor() { this.theme = localStorage.getItem('theme') || 'light'; this.apply(); } toggle() { this.theme = this.theme === 'light' ? 'dark' : 'light'; this.apply(); this.save(); } apply() { document.documentElement.setAttribute('data-theme', this.theme); const themeToggleBtn = document.getElementById('theme-toggle'); if (themeToggleBtn) { const icon = themeToggleBtn.querySelector('i'); if (icon) { icon.className = this.theme === 'light' ? 'bi bi-moon' : 'bi bi-sun'; } } } save() { localStorage.setItem('theme', this.theme); } }

// 表单验证类
class FormValidator {
    constructor(form, rules = {}) { this.form = typeof form === 'string' ? document.querySelector(form) : form; this.rules = rules; this.errors = {}; }
    validate() {
        this.errors = {};
        for (const [fieldName, rule] of Object.entries(this.rules)) {
            const field = this.form.querySelector(`[name="${fieldName}"]`);
            if (!field) continue;
            const value = field.value.trim();
            const result = this.validateField(value, rule);
            if (!result.valid) { this.errors[fieldName] = result.message; this.showFieldError(field, result.message); } else { this.clearFieldError(field); }
        }
        return Object.keys(this.errors).length === 0;
    }
    validateField(value, rule) {
        if (rule.required && !value) { return { valid: false, message: rule.message || '此字段为必填项' }; }
        if (!value && !rule.required) { return { valid: true }; }
        if (rule.minLength && value.length < rule.minLength) { return { valid: false, message: `最少需要${rule.minLength}个字符` }; }
        if (rule.maxLength && value.length > rule.maxLength) { return { valid: false, message: `最多只能输入${rule.maxLength}个字符` }; }
        if (rule.pattern && !rule.pattern.test(value)) { return { valid: false, message: rule.message || '格式不正确' }; }
        if (rule.validator && typeof rule.validator === 'function') { const result = rule.validator(value); if (result !== true) { return { valid: false, message: result || '验证失败' }; } }
        return { valid: true };
    }
    showFieldError(field, message) { this.clearFieldError(field); field.classList.add('is-invalid'); const errorDiv = document.createElement('div'); errorDiv.className = 'invalid-feedback'; errorDiv.textContent = message; field.parentNode.appendChild(errorDiv); }
    clearFieldError(field) { field.classList.remove('is-invalid'); const errorDiv = field.parentNode.querySelector('.invalid-feedback'); if (errorDiv) { errorDiv.remove(); } }
    clearAllErrors() { this.errors = {}; this.form.querySelectorAll('.is-invalid').forEach(field => this.clearFieldError(field)); }
}

// 数据表格管理类
class DataTableManager {
    constructor(tableId, options = {}) {
        this.table = document.getElementById(tableId);
        this.tbody = this.table.querySelector('tbody');
        this.options = { pageSize: 10, sortable: true, searchable: true, ...options };
        this.data = []; this.filteredData = []; this.currentPage = 1; this.sortColumn = null; this.sortDirection = 'asc';
        this.init();
    }
    init() { if (this.options.searchable) { this.setupSearch(); } if (this.options.sortable) { this.setupSort(); } this.setupPagination(); }
    setData(data) { this.data = data; this.filteredData = [...data]; this.render(); }
    setupSearch() { const selector = `[data-table-search="${this.table.id}"]`; const searchInput = document.querySelector(selector); if (searchInput) { searchInput.addEventListener('input', Utils.debounce((e) => { this.search(e.target.value); }, 300)); } }
    search(query) { if (!query.trim()) { this.filteredData = [...this.data]; } else { this.filteredData = this.data.filter(row => Object.values(row).some(value => String(value).toLowerCase().includes(query.toLowerCase()))); } this.currentPage = 1; this.render(); }
    setupSort() { const headers = this.table.querySelectorAll('th[data-sort]'); headers.forEach(header => { header.style.cursor = 'pointer'; header.addEventListener('click', () => { const column = header.getAttribute('data-sort'); this.sort(column); }); }); }
    sort(column) {
        if (this.sortColumn === column) { this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc'; } else { this.sortColumn = column; this.sortDirection = 'asc'; }
        this.filteredData.sort((a, b) => { const aValue = a[column]; const bValue = b[column]; if (aValue < bValue) return this.sortDirection === 'asc' ? -1 : 1; if (aValue > bValue) return this.sortDirection === 'asc' ? 1 : -1; return 0; });
        this.updateSortIcons(); this.render();
    }
    updateSortIcons() { this.table.querySelectorAll('th[data-sort] i').forEach(icon => { icon.className = 'bi bi-arrow-down-up text-muted'; }); if (this.sortColumn) { const header = this.table.querySelector(`th[data-sort="${this.sortColumn}"] i`); if (header) { header.className = `bi bi-arrow-${this.sortDirection === 'asc' ? 'up' : 'down'} text-primary`; } } }
    setupPagination() { /* 预留 */ }
    render() { this.tbody.innerHTML = ''; const startIndex = (this.currentPage - 1) * this.options.pageSize; const endIndex = startIndex + this.options.pageSize; const pageData = this.filteredData.slice(startIndex, endIndex); if (pageData.length === 0) { this.tbody.innerHTML = `<tr><td colspan="100%" class="text-center py-4 text-muted"><i class="bi bi-inbox icon-lg"></i><div class="mt-2">暂无数据</div></td></tr>`; return; } pageData.forEach(row => { const tr = document.createElement('tr'); if (this.options.rowRenderer) { tr.innerHTML = this.options.rowRenderer(row); } this.tbody.appendChild(tr); }); }
}

// 初始化实例与全局事件
const apiManager = new ApiManager();
const notificationManager = new NotificationManager();
const loadingManager = new LoadingManager();
const themeManager = new ThemeManager();

document.addEventListener('DOMContentLoaded', function () {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (el) { return new bootstrap.Tooltip(el); });
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (el) { return new bootstrap.Popover(el); });
    const themeToggleBtn = document.getElementById('theme-toggle');
    if (themeToggleBtn) { themeToggleBtn.addEventListener('click', () => { themeManager.toggle(); }); }
    document.addEventListener('click', function (e) { const confirmBtn = e.target.closest('[data-confirm]'); if (confirmBtn) { const message = confirmBtn.getAttribute('data-confirm'); if (!confirm(message)) { e.preventDefault(); e.stopPropagation(); return false; } } });
    const autoSaveForms = document.querySelectorAll('[data-auto-save]');
    autoSaveForms.forEach(form => {
        const formId = form.id || form.getAttribute('data-auto-save'); const savedData = localStorage.getItem(`form_${formId}`);
        if (savedData) { try { const data = JSON.parse(savedData); Object.keys(data).forEach(key => { const field = form.querySelector(`[name="${key}"]`); if (field) { field.value = data[key]; } }); } catch (error) { console.warn('无法恢复表单数据:', error); } }
        form.addEventListener('input', Utils.debounce(() => { const formData = new FormData(form); const data = {}; for (let [key, value] of formData.entries()) { data[key] = value; } localStorage.setItem(`form_${formId}`, JSON.stringify(data)); }, 1000));
    });
});

window.addEventListener('error', function (e) { console.error('全局错误:', e.error); notificationManager.error('系统发生错误，请稍后重试'); });
window.addEventListener('unhandledrejection', function (e) { console.error('未处理的Promise拒绝:', e.reason); notificationManager.error('网络请求失败，请检查连接'); });

// WebSocket 实时通信管理类
class WebSocketManager {
    constructor() {
        this.baseUrl = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        this.baseUrl += window.location.host + '/api/ws/realtime';
        this.ws = null;
        this.clientId = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000; // 初始延迟 1 秒
        this.maxReconnectDelay = 30000; // 最大延迟 30 秒
        this.reconnectTimer = null;
        this.heartbeatTimer = null;
        this.heartbeatInterval = 30000; // 30 秒心跳
        this.isConnecting = false;
        this.isManualClose = false;

        // 订阅的主题
        this.subscribedTopics = new Set();

        // 消息处理器 {topic: [handlers]}
        this.messageHandlers = new Map();

        // 离线消息缓冲
        this.messageBuffer = [];
        this.maxBufferSize = 100;

        // 连接状态回调
        this.onConnectCallbacks = [];
        this.onDisconnectCallbacks = [];
        this.onErrorCallbacks = [];

        // 统计信息
        this.stats = {
            messagesReceived: 0,
            messagesSent: 0,
            reconnectCount: 0,
            lastConnectedAt: null,
            lastDisconnectedAt: null
        };
    }

    /**
     * 连接到 WebSocket 服务器
     */
    connect() {
        if (this.ws && (this.ws.readyState === WebSocket.CONNECTING || this.ws.readyState === WebSocket.OPEN)) {
            console.log('[WebSocket] Already connected or connecting');
            return;
        }

        if (this.isConnecting) {
            console.log('[WebSocket] Connection in progress');
            return;
        }

        this.isConnecting = true;
        this.isManualClose = false;

        try {
            console.log(`[WebSocket] Connecting to ${this.baseUrl}...`);
            this.ws = new WebSocket(this.baseUrl);

            this.ws.onopen = (event) => this.handleOpen(event);
            this.ws.onmessage = (event) => this.handleMessage(event);
            this.ws.onerror = (event) => this.handleError(event);
            this.ws.onclose = (event) => this.handleClose(event);

        } catch (error) {
            console.error('[WebSocket] Connection error:', error);
            this.isConnecting = false;
            this.scheduleReconnect();
        }
    }

    /**
     * 断开连接
     */
    disconnect() {
        this.isManualClose = true;
        this.clearTimers();

        if (this.ws) {
            this.ws.close(1000, 'Client disconnect');
            this.ws = null;
        }

        console.log('[WebSocket] Disconnected');
    }

    /**
     * 订阅主题
     */
    subscribe(topic, handler) {
        if (!this.messageHandlers.has(topic)) {
            this.messageHandlers.set(topic, []);
        }
        this.messageHandlers.get(topic).push(handler);

        // 如果已连接，立即发送订阅请求
        if (this.isConnected()) {
            this.send({ action: 'subscribe', topic });
            this.subscribedTopics.add(topic);
        }

        console.log(`[WebSocket] Subscribed to topic: ${topic}`);
    }

    /**
     * 取消订阅主题
     */
    unsubscribe(topic, handler = null) {
        if (handler) {
            const handlers = this.messageHandlers.get(topic);
            if (handlers) {
                const index = handlers.indexOf(handler);
                if (index > -1) {
                    handlers.splice(index, 1);
                }
                if (handlers.length === 0) {
                    this.messageHandlers.delete(topic);
                }
            }
        } else {
            this.messageHandlers.delete(topic);
        }

        if (this.isConnected()) {
            this.send({ action: 'unsubscribe', topic });
            this.subscribedTopics.delete(topic);
        }

        console.log(`[WebSocket] Unsubscribed from topic: ${topic}`);
    }

    /**
     * 发送消息
     */
    send(data) {
        if (!this.isConnected()) {
            // 缓存消息
            if (this.messageBuffer.length < this.maxBufferSize) {
                this.messageBuffer.push(data);
                console.log('[WebSocket] Message buffered (offline)');
            } else {
                console.warn('[WebSocket] Message buffer full, dropping message');
            }
            return false;
        }

        try {
            this.ws.send(JSON.stringify(data));
            this.stats.messagesSent++;
            return true;
        } catch (error) {
            console.error('[WebSocket] Send error:', error);
            return false;
        }
    }

    /**
     * 检查是否已连接
     */
    isConnected() {
        return this.ws && this.ws.readyState === WebSocket.OPEN;
    }

    /**
     * 获取连接状态
     */
    getStatus() {
        if (!this.ws) return 'disconnected';
        switch (this.ws.readyState) {
            case WebSocket.CONNECTING: return 'connecting';
            case WebSocket.OPEN: return 'connected';
            case WebSocket.CLOSING: return 'closing';
            case WebSocket.CLOSED: return 'disconnected';
            default: return 'unknown';
        }
    }

    /**
     * 获取统计信息
     */
    getStats() {
        return {
            ...this.stats,
            status: this.getStatus(),
            subscribedTopics: Array.from(this.subscribedTopics),
            bufferedMessages: this.messageBuffer.length,
            reconnectAttempts: this.reconnectAttempts
        };
    }

    // ========== 内部方法 ==========

    handleOpen(event) {
        console.log('[WebSocket] Connected successfully');
        this.isConnecting = false;
        this.reconnectAttempts = 0;
        this.stats.lastConnectedAt = new Date().toISOString();

        // 启动心跳
        this.startHeartbeat();

        // 触发连接回调
        this.onConnectCallbacks.forEach(cb => {
            try { cb(event); } catch (e) { console.error('Connect callback error:', e); }
        });

        // 重新订阅所有主题
        this.subscribedTopics.forEach(topic => {
            this.send({ action: 'subscribe', topic });
        });

        // 发送缓冲的消息
        this.flushMessageBuffer();
    }

    handleMessage(event) {
        try {
            const message = JSON.parse(event.data);
            this.stats.messagesReceived++;

            // 处理特殊消息类型
            if (message.type === 'connected') {
                this.clientId = message.client_id;
                console.log(`[WebSocket] Client ID: ${this.clientId}`);
                return;
            }

            if (message.type === 'pong') {
                // 心跳响应
                return;
            }

            if (message.type === 'error') {
                console.error('[WebSocket] Server error:', message.message);
                if (window.notificationManager) {
                    notificationManager.error(`WebSocket: ${message.message}`);
                }
                return;
            }

            // 分发消息到对应主题的处理器
            const topic = message.topic || this.inferTopicFromMessage(message);
            if (topic && this.messageHandlers.has(topic)) {
                const handlers = this.messageHandlers.get(topic);
                handlers.forEach(handler => {
                    try {
                        handler(message);
                    } catch (e) {
                        console.error(`[WebSocket] Handler error for topic ${topic}:`, e);
                    }
                });
            }

            // 触发全局消息处理器
            if (this.messageHandlers.has('*')) {
                this.messageHandlers.get('*').forEach(handler => {
                    try { handler(message); } catch (e) { console.error('Global handler error:', e); }
                });
            }

        } catch (error) {
            console.error('[WebSocket] Message parse error:', error);
        }
    }

    handleError(event) {
        console.error('[WebSocket] Error:', event);
        this.onErrorCallbacks.forEach(cb => {
            try { cb(event); } catch (e) { console.error('Error callback error:', e); }
        });
    }

    handleClose(event) {
        console.log(`[WebSocket] Connection closed (code: ${event.code}, reason: ${event.reason})`);
        this.isConnecting = false;
        this.stats.lastDisconnectedAt = new Date().toISOString();

        this.clearTimers();

        // 触发断开回调
        this.onDisconnectCallbacks.forEach(cb => {
            try { cb(event); } catch (e) { console.error('Disconnect callback error:', e); }
        });

        // 自动重连 (除非是手动关闭)
        if (!this.isManualClose) {
            this.scheduleReconnect();
        }
    }

    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('[WebSocket] Max reconnect attempts reached');
            if (window.notificationManager) {
                notificationManager.error('实时连接已断开，请刷新页面重试');
            }
            return;
        }

        // 指数退避策略
        const delay = Math.min(
            this.reconnectDelay * Math.pow(2, this.reconnectAttempts),
            this.maxReconnectDelay
        );

        console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts + 1}/${this.maxReconnectAttempts})`);

        this.reconnectTimer = setTimeout(() => {
            this.reconnectAttempts++;
            this.stats.reconnectCount++;
            this.connect();
        }, delay);
    }

    startHeartbeat() {
        this.heartbeatTimer = setInterval(() => {
            if (this.isConnected()) {
                this.send({ action: 'ping' });
            }
        }, this.heartbeatInterval);
    }

    clearTimers() {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
    }

    flushMessageBuffer() {
        if (this.messageBuffer.length === 0) return;

        console.log(`[WebSocket] Flushing ${this.messageBuffer.length} buffered messages`);
        const buffer = [...this.messageBuffer];
        this.messageBuffer = [];

        buffer.forEach(msg => this.send(msg));
    }

    inferTopicFromMessage(message) {
        // 根据消息类型推断主题
        const type = message.type;
        if (type === 'stats_update') return 'stats';
        if (type === 'rule_change') return 'rules';
        if (type === 'system_event') return 'system';
        if (type === 'log') return 'logs';
        if (type === 'alert') return 'alerts';
        if (type === 'notification') return 'notifications';
        return null;
    }

    // ========== 事件监听器注册 ==========

    onConnect(callback) {
        this.onConnectCallbacks.push(callback);
    }

    onDisconnect(callback) {
        this.onDisconnectCallbacks.push(callback);
    }

    onError(callback) {
        this.onErrorCallbacks.push(callback);
    }
}

// 导出到全局作用域
window.Utils = Utils;
window.apiManager = apiManager;
window.notificationManager = notificationManager;
window.loadingManager = loadingManager;
window.themeManager = themeManager;
window.FormValidator = FormValidator;
window.DataTableManager = DataTableManager;
window.WebSocketManager = WebSocketManager;
window.wsManager = new WebSocketManager(); // 全局实例

// 全局 Logout 函数
window.handleLogout = async function () {
    try {
        // 尝试调用后端 Logout API 清除 Session (可选)
        await fetch('/api/auth/logout', { method: 'POST' });
    } catch (e) {
        console.warn('Logout API call failed:', e);
    } finally {
        // 强制前端跳转到 logout 路由 (由 PageRouter 处理 Cookie 清除)
        window.location.href = '/logout';
    }
};
