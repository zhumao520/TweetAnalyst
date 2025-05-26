/**
 * AI提供商管理模块
 * 处理AI提供商的加载、显示、添加、编辑和删除功能
 */

const AIProviderManager = {
    // 存储当前加载的提供商列表
    providers: [],

    // 是否正在加载
    isLoading: false,

    // 上次加载时间
    lastLoadTime: 0,

    // 加载间隔（毫秒）
    loadInterval: 30000, // 增加到30秒，减少刷新频率

    /**
     * 初始化AI提供商管理器
     */
    init: function() {
        console.log('初始化AI提供商管理器');

        // 绑定事件处理程序
        this.bindEvents();

        // 加载AI提供商列表
        this.loadProviders();
    },

    /**
     * 绑定事件处理程序
     */
    bindEvents: function() {
        // 添加提供商按钮
        const addProviderBtn = document.getElementById('save-provider-btn');
        if (addProviderBtn) {
            addProviderBtn.addEventListener('click', () => {
                this.saveProvider();
            });
        }

        // 更新提供商按钮
        const updateProviderBtn = document.getElementById('update-provider-btn');
        if (updateProviderBtn) {
            updateProviderBtn.addEventListener('click', () => {
                this.updateProvider();
            });
        }
    },

    /**
     * 加载AI提供商列表
     * @param {boolean} force 是否强制加载，忽略时间间隔
     */
    loadProviders: function(force = false) {
        // 检查是否正在加载
        if (this.isLoading) {
            console.log('正在加载中，忽略重复请求');
            return;
        }

        // 检查时间间隔
        const now = Date.now();
        if (!force && now - this.lastLoadTime < this.loadInterval) {
            console.log('加载间隔过短，忽略请求');
            return;
        }

        // 更新状态
        this.isLoading = true;
        this.lastLoadTime = now;

        // 获取表格主体
        const tableBody = document.getElementById('ai-providers-table-body');
        if (!tableBody) {
            console.error('未找到表格主体元素');
            this.isLoading = false;
            return;
        }

        // 显示加载中
        tableBody.innerHTML = '<tr><td colspan="7" class="text-center py-3"><div class="spinner-border text-info" role="status"></div><p class="mt-2 text-muted">正在加载AI提供商列表...</p></td></tr>';

        // 发送请求
        fetch('/api/ai_provider/')
            .then(response => response.json())
            .then(data => {
                // 更新状态
                this.isLoading = false;

                if (data.success) {
                    // 存储提供商列表
                    this.providers = data.providers || [];

                    // 渲染提供商列表
                    this.renderProviders();
                } else {
                    tableBody.innerHTML = `<tr><td colspan="7" class="text-center py-3 text-danger"><i class="bi bi-exclamation-triangle me-2"></i>${data.message || '加载失败'}</td></tr>`;
                }
            })
            .catch(error => {
                // 更新状态
                this.isLoading = false;

                console.error('Error:', error);
                tableBody.innerHTML = `<tr><td colspan="7" class="text-center py-3 text-danger"><i class="bi bi-exclamation-triangle me-2"></i>加载失败: ${error.message}</td></tr>`;
            });
    },

    /**
     * 渲染AI提供商列表
     */
    renderProviders: function() {
        const tableBody = document.getElementById('ai-providers-table-body');
        if (!tableBody) {
            console.error('未找到表格主体元素');
            return;
        }

        // 检查是否有提供商
        if (!this.providers || this.providers.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="7" class="text-center py-3 text-muted"><i class="bi bi-info-circle me-2"></i>暂无AI提供商，请点击"添加提供商"按钮添加</td></tr>';
            return;
        }

        // 检查表格内容是否已经存在且相同（避免不必要的DOM更新）
        const currentProviderIds = this.providers.map(p => p.id).sort().join(',');
        if (tableBody.dataset.providerIds === currentProviderIds) {
            console.log('AI提供商列表未变化，跳过渲染');
            return;
        }

        // 构建HTML
        let html = '';
        this.providers.forEach(provider => {
            // 状态标签
            let statusBadge = provider.is_active
                ? '<span class="badge bg-success">已启用</span>'
                : '<span class="badge bg-secondary">已禁用</span>';

            // 媒体类型
            const mediaTypes = [];
            if (provider.supports_text) mediaTypes.push('<span class="badge bg-info me-1" title="文本"><i class="bi bi-chat-text"></i></span>');
            if (provider.supports_image) mediaTypes.push('<span class="badge bg-primary me-1" title="图片"><i class="bi bi-image"></i></span>');
            if (provider.supports_video) mediaTypes.push('<span class="badge bg-danger me-1" title="视频"><i class="bi bi-film"></i></span>');
            if (provider.supports_gif) mediaTypes.push('<span class="badge bg-warning me-1" title="GIF"><i class="bi bi-filetype-gif"></i></span>');

            // 使用次数
            let usageStats = '未使用';
            if (provider.usage_count > 0) {
                usageStats = `${provider.usage_count}次`;
                if (provider.success_count > 0) {
                    const successRate = Math.round((provider.success_count / provider.usage_count) * 100);
                    usageStats += ` (成功率: ${successRate}%)`;
                }
            }

            html += `
            <tr>
                <td>${provider.name}</td>
                <td>${provider.model}</td>
                <td>${provider.priority}</td>
                <td>${statusBadge}</td>
                <td>${mediaTypes.join('') || '<span class="text-muted">无</span>'}</td>
                <td>${usageStats}</td>
                <td>
                    <div class="btn-group btn-group-sm">
                        <button type="button" class="btn btn-outline-primary" onclick="AIProviderManager.editProvider(${provider.id})">
                            <i class="bi bi-pencil"></i>
                        </button>
                        <button type="button" class="btn btn-outline-danger" onclick="AIProviderManager.deleteProvider(${provider.id})">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                </td>
            </tr>`;
        });

        // 更新表格内容（只有在内容变化时才更新DOM）
        if (tableBody.innerHTML !== html) {
            tableBody.innerHTML = html;
            // 存储当前提供商ID列表，用于后续比较
            tableBody.dataset.providerIds = currentProviderIds;
        }
    },

    /**
     * 保存AI提供商
     */
    saveProvider: function() {
        // 实现保存逻辑
    },

    /**
     * 编辑AI提供商
     * @param {number} id 提供商ID
     */
    editProvider: function(id) {
        // 实现编辑逻辑
    },

    /**
     * 更新AI提供商
     */
    updateProvider: function() {
        // 实现更新逻辑
    },

    /**
     * 删除AI提供商
     * @param {number} id 提供商ID
     */
    deleteProvider: function(id) {
        // 实现删除逻辑
    }
};

// 当DOM加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    // 检查是否在AI提供商页面
    if (document.getElementById('ai-providers-table-body')) {
        AIProviderManager.init();
    }
});
