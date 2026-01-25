/**
 * Command Panel - 命令行面板逻辑
 * 仿照Telegram Bot命令界面
 */

// 命令历史记录 (最多保存100条)
let commandHistory = JSON.parse(localStorage.getItem('commandHistory') || '[]');
let historyIndex = -1;

// 可用命令列表 (从后端获取或静态定义)
const availableCommands = [
    // 基础命令
    { cmd: '/start', desc: '开始使用', category: 'basic' },
    { cmd: '/help', alias: '/h', desc: '显示帮助信息', category: 'basic' },
    { cmd: '/changelog', alias: '/cl', desc: '查看更新日志', category: 'basic' },
    
    // 绑定和设置
    { cmd: '/bind', alias: '/b', desc: '绑定源聊天', params: '<源聊天> [目标聊天]', category: 'binding' },
    { cmd: '/settings', alias: '/s', desc: '管理转发规则', params: '[规则ID]', category: 'binding' },
    { cmd: '/switch', desc: '切换当前管理的规则', category: 'binding' },
    
    // 关键字管理
    { cmd: '/add', alias: '/a', desc: '添加普通关键字', params: '<关键字>', category: 'keyword' },
    { cmd: '/add_regex', alias: '/ar', desc: '添加正则表达式', params: '<正则>', category: 'keyword' },
    { cmd: '/list_keyword', alias: '/lk', desc: '列出所有关键字', category: 'keyword' },
    { cmd: '/remove_keyword', alias: '/rk', desc: '删除关键字', params: '<关键字>', category: 'keyword' },
    { cmd: '/remove_keyword_by_id', alias: '/rkbi', desc: '按ID删除关键字', params: '<ID>', category: 'keyword' },
    
    // 替换规则
    { cmd: '/replace', alias: '/r', desc: '添加替换规则', params: '<正则> [替换内容]', category: 'replace' },
    { cmd: '/list_replace', alias: '/lrp', desc: '列出所有替换规则', category: 'replace' },
    { cmd: '/remove_replace', alias: '/rr', desc: '删除替换规则', params: '<序号>', category: 'replace' },
    
    // 高级筛选
    { cmd: '/set_duration', desc: '设置时长范围', params: '<最小秒> [最大秒]', category: 'filter' },
    { cmd: '/set_resolution', desc: '设置分辨率', params: '<宽> <高>', category: 'filter' },
    { cmd: '/set_size', desc: '设置文件大小', params: '<最小> [最大]', category: 'filter' },
    
    // 去重管理
    { cmd: '/dedup', desc: '切换去重开关', category: 'dedup' },
    { cmd: '/dedup_scan', desc: '扫描重复消息', category: 'dedup' },
    
    // 数据库管理
    { cmd: '/db_info', desc: '查看数据库信息', category: 'database' },
    { cmd: '/db_backup', desc: '备份数据库', category: 'database' },
    { cmd: '/db_optimize', desc: '优化数据库', category: 'database' },
    { cmd: '/db_health', desc: '数据库健康检查', category: 'database' },
    
    // 转发记录
    { cmd: '/forward_stats', alias: '/fs', desc: '查看转发统计', params: '[日期]', category: 'stats' },
    { cmd: '/forward_search', alias: '/fsr', desc: '搜索转发记录', params: '[参数]', category: 'stats' },
];

/**
 * 初始化命令面板
 */
function initCommandPanel() {
    const input = document.getElementById('commandInput');
    if (!input) return;
    
    // 绑定键盘事件
    input.addEventListener('keydown', handleKeyDown);
    input.addEventListener('input', handleInput);
    
    // 加载历史记录
    loadCommandHistory();
    
    // 点击输出区域外部隐藏自动补全
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.command-input-wrapper')) {
            hideAutocomplete();
        }
    });
}

/**
 * 处理键盘事件
 */
function handleKeyDown(e) {
    const input = e.target;
    
    switch(e.key) {
        case 'Enter':
            e.preventDefault();
            executeCommand();
            break;
            
        case 'ArrowUp':
            e.preventDefault();
            navigateHistory('up');
            break;
            
        case 'ArrowDown':
            e.preventDefault();
            navigateHistory('down');
            break;
            
        case 'Tab':
            e.preventDefault();
            autocompleteCommand();
            break;
            
        case 'Escape':
            hideAutocomplete();
            break;
    }
}

/**
 * 处理输入事件 (自动补全)
 */
function handleInput(e) {
    const value = e.target.value;
    
    if (!value || !value.startsWith('/')) {
        hideAutocomplete();
        return;
    }
    
    // 提取命令部分 (第一个单词)
    const cmdPart = value.split(' ')[0].toLowerCase();
    
    // 过滤匹配的命令
    const matches = availableCommands.filter(c => 
        c.cmd.toLowerCase().startsWith(cmdPart) || 
        (c.alias && c.alias.toLowerCase().startsWith(cmdPart))
    );
    
    if (matches.length > 0) {
        showAutocomplete(matches);
    } else {
        hideAutocomplete();
    }
}

/**
 * 显示自动补全建议
 */
function showAutocomplete(matches) {
    const container = document.getElementById('autocompleteSuggestions');
    if (!container) return;
    
    container.innerHTML = matches.map((item, idx) => `
        <div class="suggestion-item ${idx === 0 ? 'active' : ''}" 
             onclick="selectSuggestion('${item.cmd}', '${item.params || ''}')">
            <code>${item.cmd}</code>
            ${item.alias ? `<span class="badge bg-secondary ms-1">${item.alias}</span>` : ''}
            ${item.params ? `<span class="text-muted ms-2">${item.params}</span>` : ''}
            <br><small class="text-muted">${item.desc}</small>
        </div>
    `).join('');
    
    container.classList.add('show');
}

/**
 * 隐藏自动补全
 */
function hideAutocomplete() {
    const container = document.getElementById('autocompleteSuggestions');
    if (container) {
        container.classList.remove('show');
    }
}

/**
 * 选择建议
 */
function selectSuggestion(cmd, params) {
    const input = document.getElementById('commandInput');
    if (!input) return;
    
    input.value = cmd + (params ? ' ' : '');
    input.focus();
    
    // 将光标移到末尾
    input.setSelectionRange(input.value.length, input.value.length);
    
    hideAutocomplete();
}

/**
 * 自动补全命令 (Tab键)
 */
function autocompleteCommand() {
    const input = document.getElementById('commandInput');
    if (!input) return;
    
    const value = input.value;
    const cmdPart = value.split(' ')[0].toLowerCase();
    
    // 查找第一个匹配
    const match = availableCommands.find(c => 
        c.cmd.toLowerCase().startsWith(cmdPart) || 
        (c.alias && c.alias.toLowerCase().startsWith(cmdPart))
    );
    
    if (match) {
        selectSuggestion(match.cmd, match.params || '');
    }
}

/**
 * 执行命令
 */
async function executeCommand() {
    const input = document.getElementById('commandInput');
    if (!input) return;
    
    const command = input.value.trim();
    if (!command) return;
    
    // 添加到历史记录
    addToHistory(command);
    
    // 显示命令到输出区域
    appendToOutput(`<span class="command-prompt">$</span> <span class="command-text">${escapeHtml(command)}</span>`);
    
    // 清空输入框
    input.value = '';
    historyIndex = -1;
    
    // 显示加载状态
    const loadingId = Date.now();
    appendToOutput(`<div id="loading-${loadingId}" class="command-result">⏳ 执行中...</div>`);
    
    try {
        // 调用后端API
        const response = await fetch('/api/command/execute', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ command })
        });
        
        const result = await response.json();
        
        // 移除加载状态
        const loadingEl = document.getElementById(`loading-${loadingId}`);
        if (loadingEl) loadingEl.remove();
        
        // 显示结果
        if (result.success) {
            appendToOutput(`<div class="command-result command-success">✅ ${escapeHtml(result.message || '执行成功')}</div>`);
            
            // 如果有数据，格式化显示
            if (result.data) {
                appendToOutput(`<div class="command-result">${formatData(result.data)}</div>`);
            }
        } else {
            appendToOutput(`<div class="command-result command-error">❌  ${escapeHtml(result.error || '执行失败')}</div>`);
        }
        
    } catch (error) {
        // 移除加载状态
        const loadingEl = document.getElementById(`loading-${loadingId}`);
        if (loadingEl) loadingEl.remove();
        
        appendToOutput(`<div class="command-result command-error">❌ 网络错误: ${escapeHtml(error.message)}</div>`);
        console.error('Command execution error:', error);
    }
    
    // 滚动到底部
    scrollToBottom();
}

/**
 * 添加到历史记录
 */
function addToHistory(command) {
    // 避免连续重复
    if (commandHistory[0] === command) return;
    
    commandHistory.unshift(command);
    
    // 限制历史记录数量
    if (commandHistory.length > 100) {
        commandHistory = commandHistory.slice(0, 100);
    }
    
    // 保存到localStorage
    localStorage.setItem('commandHistory', JSON.stringify(commandHistory));
    
    // 更新UI
    loadCommandHistory();
}

/**
 * 加载历史记录到UI
 */
function loadCommandHistory() {
    const container = document.getElementById('historyList');
    if (!container) return;
    
    if (commandHistory.length === 0) {
        container.innerHTML = '<div class="text-muted text-center py-3">暂无历史记录</div>';
        return;
    }
    
    container.innerHTML = commandHistory.slice(0, 10).map((cmd, idx) => `
        <div class="history-item" onclick="insertCommand('${escapeHtml(cmd)}')">
            <small class="text-muted">${idx + 1}.</small>
            <code>${escapeHtml(cmd)}</code>
        </div>
    `).join('');
}

/**
 * 浏览历史记录 (↑/↓)
 */
function navigateHistory(direction) {
    const input = document.getElementById('commandInput');
    if (!input || commandHistory.length === 0) return;
    
    if (direction === 'up') {
        if (historyIndex < commandHistory.length - 1) {
            historyIndex++;
        }
    } else {
        if (historyIndex > -1) {
            historyIndex--;
        }
    }
    
    if (historyIndex === -1) {
        input.value = '';
    } else {
        input.value = commandHistory[historyIndex];
        // 将光标移到末尾
        setTimeout(() => {
            input.setSelectionRange(input.value.length, input.value.length);
        }, 0);
    }
}

/**
 * 插入命令到输入框
 */
function insertCommand(command) {
    const input = document.getElementById('commandInput');
    if (!input) return;
    
    input.value = command;
    input.focus();
    
    // 将光标移到末尾
    input.setSelectionRange(input.value.length, input.value.length);
    
    // 关闭侧边栏
    const sidebar = bootstrap.Offcanvas.getInstance(document.getElementById('commandListSidebar'));
    if (sidebar) sidebar.hide();
}

/**
 * 添加输出到终端
 */
function appendToOutput(html) {
    const output = document.getElementById('commandOutput');
    if (!output) return;
    
    const line = document.createElement('div');
    line.className = 'command-line';
    line.innerHTML = html;
    
    output.appendChild(line);
}

/**
 * 滚动到底部
 */
function scrollToBottom() {
    const output = document.getElementById('commandOutput');
    if (!output) return;
    
    output.scrollTop = output.scrollHeight;
}

/**
 * 清空历史记录
 */
function clearCommandHistory() {
    if (!confirm('确定要清空所有命令历史记录吗？')) return;
    
    commandHistory = [];
    historyIndex = -1;
    localStorage.removeItem('commandHistory');
    loadCommandHistory();
    
    // 显示提示
    showToast('历史记录已清空', 'success');
}

/**
 * 切换命令列表侧边栏
 */
function toggleCommandList() {
    const sidebar = document.getElementById('commandListSidebar');
    if (!sidebar) return;
    
    const bsOffcanvas = new bootstrap.Offcanvas(sidebar);
    bsOffcanvas.toggle();
}

/**
 * 切换命令面板显示/隐藏
 */
function toggleCommandPanel() {
    const panel = document.getElementById('commandPanel');
    if (!panel) return;
    
    panel.classList.toggle('minimized');
    
    const icon = panel.querySelector('.command-panel-header i.bi-chevron-down, .command-panel-header i.bi-chevron-up');
    if (icon) {
        icon.classList.toggle('bi-chevron-down');
        icon.classList.toggle('bi-chevron-up');
    }
}

/**
 * 过滤命令列表
 */
function filterCommands(searchTerm) {
    const categories = document.querySelectorAll('.command-category');
    if (!categories) return;
    
    const term = searchTerm.toLowerCase();
    
    categories.forEach(category => {
        const items = category.querySelectorAll('.command-item');
        let hasVisible = false;
        
        items.forEach(item => {
            const text = item.textContent.toLowerCase();
            const isMatch = !term || text.includes(term);
            
            item.style.display = isMatch ? '' : 'none';
            if (isMatch) hasVisible = true;
        });
        
        // 隐藏没有可见项的分类
        category.style.display = hasVisible ? '' : 'none';
    });
}

/**
 * 格式化数据输出
 */
function formatData(data) {
    if (typeof data === 'string') {
        return escapeHtml(data);
    }
    
    if (Array.isArray(data)) {
        return `<pre>${JSON.stringify(data, null, 2)}</pre>`;
    }
    
    if (typeof data === 'object') {
        return `<pre>${JSON.stringify(data, null, 2)}</pre>`;
    }
    
    return String(data);
}

/**
 * HTML转义
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * 显示Toast通知
 */
function showToast(message, type = 'info') {
    // 这里应该调用全局的Toast组件
    // 暂时使用alert
    console.log(`[${type.toUpperCase()}] ${message}`);
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    initCommandPanel();
});

// 添加CSS样式 (如果命令面板最小化)
const style = document.createElement('style');
style.textContent = `
    .command-panel-wrapper.minimized {
        height: 60px;
        overflow: hidden;
    }
    
    .command-panel-wrapper.minimized .command-output,
    .command-panel-wrapper.minimized .command-input-wrapper,
    .command-panel-wrapper.minimized .quick-commands,
    .command-panel-wrapper.minimized .command-history {
        display: none;
    }
`;
document.head.appendChild(style);
