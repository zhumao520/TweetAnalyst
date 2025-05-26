/**
 * AI设置页面的JavaScript
 * 处理AI设置页面的交互逻辑
 */

document.addEventListener('DOMContentLoaded', function() {
    // 初始化页面
    initPage();

    // 绑定事件
    bindEvents();

    // 加载AI提供商列表
    loadAIProviders();

    // 加载AI轮询状态
    loadAIPollingStatus();

    // 初始化时间间隔显示
    if (typeof updateIntervalDisplay === 'function') {
        updateIntervalDisplay();
    }

    // 每30秒刷新一次状态
    setInterval(function() {
        loadAIPollingStatus();
    }, 30000);

    // 为API基础URL输入框添加事件监听器
    const addProviderApiBaseInput = document.getElementById('provider-api-base');
    const editProviderApiBaseInput = document.getElementById('edit-provider-api-base');

    if (addProviderApiBaseInput) {
        addProviderApiBaseInput.addEventListener('change', function() {
            filterModelsByAPI('provider-api-base', 'provider-model-select', 'provider-model');
        });
        addProviderApiBaseInput.addEventListener('input', function() {
            filterModelsByAPI('provider-api-base', 'provider-model-select', 'provider-model');
        });
    }

    if (editProviderApiBaseInput) {
        editProviderApiBaseInput.addEventListener('change', function() {
            filterModelsByAPI('edit-provider-api-base', 'edit-provider-model-select', 'edit-provider-model');
        });
        editProviderApiBaseInput.addEventListener('input', function() {
            filterModelsByAPI('edit-provider-api-base', 'edit-provider-model-select', 'edit-provider-model');
        });
    }
});

/**
 * 初始化页面
 */
function initPage() {
    // 初始化提示工具
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}



/**
 * 绑定事件
 */
function bindEvents() {
    // AI轮询设置相关代码已删除

    // 保存所有设置
    document.getElementById('save-all-settings-btn').addEventListener('click', saveAllSettings);

    // 运行健康检查
    document.getElementById('run-health-check-btn').addEventListener('click', runHealthCheck);

    // 清空缓存
    document.getElementById('clear-cache-btn').addEventListener('click', clearCache);

    // 重置统计数据
    document.getElementById('reset-stats-btn').addEventListener('click', resetAllStats);

    // 添加AI提供商
    document.getElementById('add-provider-btn').addEventListener('click', showAddProviderModal);
}

/**
 * 加载AI提供商列表
 */
function loadAIProviders() {
    fetch('/api/ai_settings/providers')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                renderAIProviders(data.providers);
            } else {
                showAlert('ai-polling-result', 'danger', `加载AI提供商列表失败: ${data.message}`);
            }
        })
        .catch(error => {
            console.error('加载AI提供商列表出错:', error);
            showAlert('ai-polling-result', 'danger', `加载AI提供商列表出错: ${error.message}`);
        });
}

/**
 * 渲染AI提供商列表
 * @param {Array} providers AI提供商列表
 */
function renderAIProviders(providers) {
    const tableBody = document.getElementById('ai-providers-table-body');
    tableBody.innerHTML = '';

    if (providers.length === 0) {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td colspan="7" class="text-center">
                <div class="alert alert-info mb-0">
                    <i class="bi bi-info-circle me-2"></i>暂无AI提供商，请点击"添加提供商"按钮添加
                </div>
            </td>
        `;
        tableBody.appendChild(row);
        return;
    }

    providers.forEach(provider => {
        const row = document.createElement('tr');

        // 媒体类型
        const mediaTypes = [];
        if (provider.supports_text) mediaTypes.push('文本');
        if (provider.supports_image) mediaTypes.push('图片');
        if (provider.supports_video) mediaTypes.push('视频');
        if (provider.supports_gif) mediaTypes.push('GIF');

        // 简化健康状态显示，只显示可用和不可用
        let healthStatusHtml = '';
        if (provider.health_status === 'available') {
            healthStatusHtml = `
                <span class="badge bg-success">
                    <i class="bi bi-check-circle-fill me-1"></i>可用
                </span>
            `;
        } else if (provider.health_status === 'unavailable') {
            healthStatusHtml = `
                <span class="badge bg-danger">
                    <i class="bi bi-x-circle-fill me-1"></i>不可用
                </span>
            `;
        } else {
            healthStatusHtml = `
                <span class="badge bg-secondary">
                    <i class="bi bi-question-circle-fill me-1"></i>未知
                </span>
            `;
        }

        // 请求统计
        const statsHtml = `
            <div class="small">
                <div>请求: ${provider.request_count || 0}</div>
                <div>成功: ${provider.success_count || 0}</div>
                <div>错误: ${provider.error_count || 0}</div>
                <div>响应时间: ${provider.avg_response_time || 0}ms</div>
            </div>
        `;

        row.innerHTML = `
            <td>
                <div class="fw-bold">${provider.name}</div>
                <div class="small text-muted">${provider.api_base || ''}</div>
            </td>
            <td>${provider.model || ''}</td>
            <td>${provider.priority}</td>
            <td>
                <div class="form-check form-switch">
                    <input class="form-check-input provider-active-switch" type="checkbox"
                           data-provider-id="${provider.id}" ${provider.is_active ? 'checked' : ''}>
                    <label class="form-check-label">${provider.is_active ? '启用' : '禁用'}</label>
                </div>
            </td>
            <td>${mediaTypes.join(', ') || '无'}</td>
            <td>
                <div class="d-flex align-items-center">
                    ${healthStatusHtml}
                    <div class="ms-2">
                        ${statsHtml}
                    </div>
                </div>
            </td>
            <td>
                <div class="btn-group btn-group-sm">
                    <button type="button" class="btn btn-outline-primary edit-provider-btn" data-provider-id="${provider.id}">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button type="button" class="btn btn-outline-danger delete-provider-btn" data-provider-id="${provider.id}">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </td>
        `;

        tableBody.appendChild(row);
    });

    // 绑定提供商操作事件
    bindProviderEvents();
}

/**
 * 绑定提供商操作事件
 */
function bindProviderEvents() {
    // 编辑提供商
    document.querySelectorAll('.edit-provider-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const providerId = this.getAttribute('data-provider-id');
            editProvider(providerId);
        });
    });

    // 删除提供商
    document.querySelectorAll('.delete-provider-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const providerId = this.getAttribute('data-provider-id');
            deleteProvider(providerId);
        });
    });

    // 切换提供商状态
    document.querySelectorAll('.provider-active-switch').forEach(switchEl => {
        switchEl.addEventListener('change', function() {
            const providerId = this.getAttribute('data-provider-id');
            const isActive = this.checked;
            toggleProviderStatus(providerId, isActive);
        });
    });
}

/**
 * 加载AI轮询状态
 */
function loadAIPollingStatus() {
    // 加载轮询状态
    fetch('/api/ai_settings/polling_status')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                renderPollingStatus(data.status);
            }
        })
        .catch(error => {
            console.error('加载AI轮询状态出错:', error);
        });

    // 加载缓存统计
    fetch('/api/ai_settings/cache_stats')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                renderCacheStats(data.stats);
            }
        })
        .catch(error => {
            console.error('加载缓存统计出错:', error);
        });
}

/**
 * 渲染轮询状态
 * @param {Object} status 轮询状态
 */
function renderPollingStatus(status) {
    const pollingStatusEl = document.getElementById('polling-status');
    const healthCheckStatsEl = document.getElementById('health-check-stats');
    const batchStatsEl = document.getElementById('batch-stats');

    // 轮询状态
    let statusHtml = '';
    if (status.running) {
        statusHtml = `
            <div class="text-success mb-2">
                <i class="bi bi-check-circle-fill me-1"></i>
                <span class="fw-bold">正在运行</span>
            </div>
        `;
    } else {
        statusHtml = `
            <div class="text-danger mb-2">
                <i class="bi bi-x-circle-fill me-1"></i>
                <span class="fw-bold">未运行</span>
            </div>
        `;
    }

    statusHtml += `
        <div class="small text-muted">
            <div>上次运行: ${status.last_run_time ? new Date(status.last_run_time).toLocaleString() : '从未运行'}</div>
            <div>检查间隔: ${status.interval_seconds}秒</div>
        </div>
    `;

    pollingStatusEl.innerHTML = statusHtml;

    // 健康检查统计
    healthCheckStatsEl.innerHTML = `
        <div class="text-center">
            <div class="display-4 fw-bold text-success">${status.health_check_count}</div>
            <div class="text-muted">健康检查次数</div>
        </div>
    `;

    // 批处理统计
    batchStatsEl.innerHTML = `
        <div class="text-center">
            <div class="display-4 fw-bold text-warning">${status.batch_processed_count}</div>
            <div class="text-muted">批处理请求数</div>
        </div>
    `;
}

/**
 * 渲染缓存统计
 * @param {Object} stats 缓存统计
 */
function renderCacheStats(stats) {
    const cacheStatsEl = document.getElementById('cache-stats');

    let hitRate = 0;
    if (stats.cache_hit_count + stats.cache_miss_count > 0) {
        hitRate = (stats.cache_hit_count / (stats.cache_hit_count + stats.cache_miss_count) * 100).toFixed(1);
    }

    cacheStatsEl.innerHTML = `
        <div class="text-center">
            <div class="display-4 fw-bold text-info">${hitRate}%</div>
            <div class="text-muted">缓存命中率</div>
        </div>
        <div class="small text-muted mt-2">
            <div>缓存项: ${stats.cache_items}</div>
            <div>命中: ${stats.cache_hit_count}</div>
            <div>未命中: ${stats.cache_miss_count}</div>
            <div>大小: ${formatBytes(stats.cache_size_bytes)}</div>
        </div>
    `;
}

/**
 * 格式化字节数
 * @param {Number} bytes 字节数
 * @returns {String} 格式化后的字符串
 */
function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';

    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * 更新时间间隔显示
 */
function updateIntervalDisplay() {
    const intervalInput = document.getElementById('ai-health-check-interval');
    const displayEl = document.getElementById('interval-display');

    if (!intervalInput || !displayEl) return;

    const seconds = parseInt(intervalInput.value);
    const spanEl = displayEl.querySelector('span');

    if (isNaN(seconds) || seconds < 0) {
        spanEl.textContent = '请输入有效的时间间隔';
        return;
    }

    let displayText = '';

    if (seconds >= 86400) {
        const days = Math.floor(seconds / 86400);
        displayText = `相当于 ${days} 天`;
    } else if (seconds >= 3600) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);

        if (minutes > 0) {
            displayText = `相当于 ${hours} 小时 ${minutes} 分钟`;
        } else {
            displayText = `相当于 ${hours} 小时`;
        }
    } else if (seconds >= 60) {
        const minutes = Math.floor(seconds / 60);
        displayText = `相当于 ${minutes} 分钟`;
    } else {
        displayText = `${seconds} 秒`;
    }

    spanEl.textContent = displayText;
}

/**
 * 保存所有设置
 */
function saveAllSettings() {
    // 获取表单数据
    const form = document.getElementById('ai-polling-form');

    // 表单验证
    const healthCheckInterval = document.getElementById('ai-health-check-interval').value;
    const cacheTTL = document.getElementById('ai-cache-ttl').value;

    // 验证健康检查间隔
    if (healthCheckInterval < 10 || healthCheckInterval > 86400) {
        showAlert('ai-polling-result', 'danger', '健康检查间隔必须在10秒到86400秒（24小时）之间');
        return;
    }

    // 验证缓存有效期
    if (cacheTTL < 60 || cacheTTL > 86400) {
        showAlert('ai-polling-result', 'danger', '缓存有效期必须在60秒到86400秒（24小时）之间');
        return;
    }

    const formData = new FormData(form);
    const data = {};

    // 转换为JSON对象
    for (const [key, value] of formData.entries()) {
        data[key] = value;
    }

    // 处理复选框
    data.ai_polling_enabled = document.getElementById('ai-polling-enabled').checked ? 'true' : 'false';
    data.ai_auto_health_check_enabled = document.getElementById('ai-auto-health-check-enabled').checked ? 'true' : 'false';
    data.ai_cache_enabled = document.getElementById('ai-cache-enabled').checked ? 'true' : 'false';
    data.ai_batch_enabled = document.getElementById('ai-batch-enabled').checked ? 'true' : 'false';

    // 禁用保存按钮并显示加载状态
    const saveBtn = document.getElementById('save-all-settings-btn');
    const originalBtnText = saveBtn.innerHTML;
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> 正在保存...';

    // 发送请求
    fetch('/api/ai_settings/polling_settings', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('ai-polling-result', 'success', data.message);
            // 重新加载状态
            loadAIPollingStatus();
        } else {
            showAlert('ai-polling-result', 'danger', `保存设置失败: ${data.message}`);
        }
    })
    .catch(error => {
        console.error('保存设置出错:', error);
        showAlert('ai-polling-result', 'danger', `保存设置出错: ${error.message}`);
    })
    .finally(() => {
        // 恢复保存按钮状态
        saveBtn.disabled = false;
        saveBtn.innerHTML = originalBtnText;
    });
}



/**
 * 运行健康检查
 */
function runHealthCheck() {
    const btn = document.getElementById('run-health-check-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> 正在检查...';

    fetch('/api/ai_settings/run_health_check', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // 显示健康检查结果
            let resultHtml = '<div class="mb-3"><strong>健康检查结果:</strong></div>';
            resultHtml += '<div class="table-responsive"><table class="table table-sm table-bordered">';
            resultHtml += '<thead><tr><th>提供商</th><th>状态</th><th>响应时间</th><th>错误信息</th></tr></thead>';
            resultHtml += '<tbody>';

            let hasResults = false;
            for (const [providerId, result] of Object.entries(data.results)) {
                if (typeof result === 'object') {
                    hasResults = true;
                    const statusClass = result.is_success ? 'text-success' : 'text-danger';
                    const statusIcon = result.is_success ?
                        '<i class="bi bi-check-circle-fill text-success"></i>' :
                        '<i class="bi bi-x-circle-fill text-danger"></i>';

                    resultHtml += `<tr>
                        <td>${result.provider_name}</td>
                        <td class="${statusClass}">${statusIcon} ${result.is_success ? '可用' : '不可用'}</td>
                        <td>${result.response_time ? result.response_time.toFixed(2) + '秒' : 'N/A'}</td>
                        <td>${result.error_message || ''}</td>
                    </tr>`;
                }
            }

            if (!hasResults) {
                resultHtml += '<tr><td colspan="5" class="text-center">没有可用的AI提供商</td></tr>';
            }

            resultHtml += '</tbody></table></div>';

            // 显示结果
            const resultElement = document.getElementById('health-check-results');
            if (resultElement) {
                resultElement.innerHTML = resultHtml;
                resultElement.classList.remove('d-none');
            }

            showAlert('ai-polling-result', 'success', '健康检查已完成');

            // 重新加载AI提供商列表和状态
            loadAIProviders();
            loadAIPollingStatus();
        } else {
            showAlert('ai-polling-result', 'danger', `健康检查失败: ${data.message}`);
        }
    })
    .catch(error => {
        console.error('健康检查出错:', error);
        showAlert('ai-polling-result', 'danger', `健康检查出错: ${error.message}`);
    })
    .finally(() => {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-heart-pulse me-1"></i>运行健康检查';
    });
}

/**
 * 清空缓存
 */
function clearCache() {
    if (!confirm('确定要清空所有AI请求缓存吗？')) {
        return;
    }

    fetch('/api/ai_settings/clear_cache', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('ai-polling-result', 'success', `缓存已清空，共清除 ${data.count} 项缓存`);
            // 重新加载缓存统计
            loadAIPollingStatus();
        } else {
            showAlert('ai-polling-result', 'danger', `清空缓存失败: ${data.message}`);
        }
    })
    .catch(error => {
        console.error('清空缓存出错:', error);
        showAlert('ai-polling-result', 'danger', `清空缓存出错: ${error.message}`);
    });
}

/**
 * 重置所有统计数据
 */
function resetAllStats() {
    if (!confirm('确定要重置所有AI统计数据吗？这将清空所有请求记录和健康状态信息。')) {
        return;
    }

    fetch('/api/ai_settings/reset_stats', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({})
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('ai-polling-result', 'success', data.message);
            // 重新加载AI提供商列表和状态
            loadAIProviders();
            loadAIPollingStatus();
        } else {
            showAlert('ai-polling-result', 'danger', `重置统计数据失败: ${data.message}`);
        }
    })
    .catch(error => {
        console.error('重置统计数据出错:', error);
        showAlert('ai-polling-result', 'danger', `重置统计数据出错: ${error.message}`);
    });
}

/**
 * 显示添加提供商模态框
 */
function showAddProviderModal() {
    // 重置表单
    document.getElementById('add-provider-form').reset();

    // 初始化模态框
    const modal = new bootstrap.Modal(document.getElementById('addProviderModal'));

    // 绑定保存按钮事件
    document.getElementById('save-provider-btn').onclick = saveProvider;

    // 显示模态框
    modal.show();
}

/**
 * 保存提供商
 */
function saveProvider() {
    // 获取表单数据
    const form = document.getElementById('add-provider-form');
    const formData = new FormData(form);
    const data = {};

    // 转换为JSON对象
    for (const [key, value] of formData.entries()) {
        if (key === 'supports_text' || key === 'supports_image' || key === 'supports_video' || key === 'supports_gif' || key === 'is_active') {
            data[key] = true; // 复选框被选中时才会出现在formData中
        } else {
            data[key] = value;
        }
    }

    // 处理未选中的复选框
    if (!formData.has('supports_text')) data.supports_text = false;
    if (!formData.has('supports_image')) data.supports_image = false;
    if (!formData.has('supports_video')) data.supports_video = false;
    if (!formData.has('supports_gif')) data.supports_gif = false;
    if (!formData.has('is_active')) data.is_active = false;

    // 验证表单
    if (!data.name || !data.api_key || !data.api_base || !data.model) {
        showAlert('ai-polling-result', 'danger', '请填写所有必填字段');
        return;
    }

    // 禁用保存按钮
    const saveBtn = document.getElementById('save-provider-btn');
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> 保存中...';

    // 发送请求
    fetch('/api/ai_settings/providers', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // 关闭模态框
            bootstrap.Modal.getInstance(document.getElementById('addProviderModal')).hide();

            // 显示成功消息
            showAlert('ai-polling-result', 'success', data.message);

            // 重新加载提供商列表
            loadAIProviders();
        } else {
            showAlert('ai-polling-result', 'danger', `添加AI提供商失败: ${data.message}`);
        }
    })
    .catch(error => {
        console.error('添加AI提供商出错:', error);
        showAlert('ai-polling-result', 'danger', `添加AI提供商出错: ${error.message}`);
    })
    .finally(() => {
        // 恢复保存按钮
        saveBtn.disabled = false;
        saveBtn.innerHTML = '保存';
    });
}

/**
 * 编辑提供商
 * @param {String} providerId 提供商ID
 */
function editProvider(providerId) {
    // 获取提供商详情
    fetch(`/api/ai_settings/providers/${providerId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // 填充表单
                const provider = data.provider;
                document.getElementById('edit-provider-id').value = provider.id;
                document.getElementById('edit-provider-name').value = provider.name;
                document.getElementById('edit-provider-model').value = provider.model;
                document.getElementById('edit-provider-api-base').value = provider.api_base;
                document.getElementById('edit-provider-priority').value = provider.priority;
                document.getElementById('edit-provider-api-key').value = ''; // 不显示API密钥
                document.getElementById('edit-supports-text').checked = provider.supports_text;
                document.getElementById('edit-supports-image').checked = provider.supports_image;
                document.getElementById('edit-supports-video').checked = provider.supports_video;
                document.getElementById('edit-supports-gif').checked = provider.supports_gif;
                document.getElementById('edit-provider-is-active').checked = provider.is_active;

                // 初始化模态框
                const modal = new bootstrap.Modal(document.getElementById('editProviderModal'));

                // 绑定更新按钮事件
                document.getElementById('update-provider-btn').onclick = updateProvider;

                // 显示模态框
                modal.show();
            } else {
                showAlert('ai-polling-result', 'danger', `获取AI提供商详情失败: ${data.message}`);
            }
        })
        .catch(error => {
            console.error('获取AI提供商详情出错:', error);
            showAlert('ai-polling-result', 'danger', `获取AI提供商详情出错: ${error.message}`);
        });
}

/**
 * 更新提供商
 */
function updateProvider() {
    // 获取表单数据
    const form = document.getElementById('edit-provider-form');
    const formData = new FormData(form);
    const data = {};

    // 转换为JSON对象
    for (const [key, value] of formData.entries()) {
        if (key === 'supports_text' || key === 'supports_image' || key === 'supports_video' || key === 'supports_gif' || key === 'is_active') {
            data[key] = true; // 复选框被选中时才会出现在formData中
        } else {
            data[key] = value;
        }
    }

    // 处理未选中的复选框
    if (!formData.has('supports_text')) data.supports_text = false;
    if (!formData.has('supports_image')) data.supports_image = false;
    if (!formData.has('supports_video')) data.supports_video = false;
    if (!formData.has('supports_gif')) data.supports_gif = false;
    if (!formData.has('is_active')) data.is_active = false;

    // 验证表单
    if (!data.name || !data.api_base || !data.model) {
        showAlert('ai-polling-result', 'danger', '请填写所有必填字段');
        return;
    }

    // 获取提供商ID
    const providerId = data.id;

    // 禁用更新按钮
    const updateBtn = document.getElementById('update-provider-btn');
    updateBtn.disabled = true;
    updateBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> 更新中...';

    // 发送请求
    fetch(`/api/ai_settings/providers/${providerId}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // 关闭模态框
            bootstrap.Modal.getInstance(document.getElementById('editProviderModal')).hide();

            // 显示成功消息
            showAlert('ai-polling-result', 'success', data.message);

            // 重新加载提供商列表
            loadAIProviders();
        } else {
            showAlert('ai-polling-result', 'danger', `更新AI提供商失败: ${data.message}`);
        }
    })
    .catch(error => {
        console.error('更新AI提供商出错:', error);
        showAlert('ai-polling-result', 'danger', `更新AI提供商出错: ${error.message}`);
    })
    .finally(() => {
        // 恢复更新按钮
        updateBtn.disabled = false;
        updateBtn.innerHTML = '更新';
    });
}

/**
 * 删除提供商
 * @param {String} providerId 提供商ID
 */
function deleteProvider(providerId) {
    // 确认删除
    if (!confirm('确定要删除此AI提供商吗？此操作不可恢复。')) {
        return;
    }

    // 发送请求
    fetch(`/api/ai_settings/providers/${providerId}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('ai-polling-result', 'success', data.message);

            // 重新加载提供商列表
            loadAIProviders();
        } else {
            showAlert('ai-polling-result', 'danger', `删除AI提供商失败: ${data.message}`);
        }
    })
    .catch(error => {
        console.error('删除AI提供商出错:', error);
        showAlert('ai-polling-result', 'danger', `删除AI提供商出错: ${error.message}`);
    });
}

/**
 * 切换提供商状态
 * @param {String} providerId 提供商ID
 * @param {Boolean} isActive 是否启用
 */
function toggleProviderStatus(providerId, isActive) {
    // 发送请求
    fetch(`/api/ai_settings/providers/${providerId}/toggle`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            is_active: isActive
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('ai-polling-result', 'success', data.message);

            // 重新加载提供商列表
            loadAIProviders();
        } else {
            showAlert('ai-polling-result', 'danger', `切换AI提供商状态失败: ${data.message}`);

            // 恢复开关状态
            const switchEl = document.querySelector(`.provider-active-switch[data-provider-id="${providerId}"]`);
            if (switchEl) {
                switchEl.checked = !isActive;
                switchEl.nextElementSibling.textContent = !isActive ? '启用' : '禁用';
            }
        }
    })
    .catch(error => {
        console.error('切换AI提供商状态出错:', error);
        showAlert('ai-polling-result', 'danger', `切换AI提供商状态出错: ${error.message}`);

        // 恢复开关状态
        const switchEl = document.querySelector(`.provider-active-switch[data-provider-id="${providerId}"]`);
        if (switchEl) {
            switchEl.checked = !isActive;
            switchEl.nextElementSibling.textContent = !isActive ? '启用' : '禁用';
        }
    });
}

/**
 * 根据API基础URL提示可用模型
 * @param {String} apiBaseInputId API基础URL输入框ID
 * @param {String} modelSelectId 模型选择下拉框ID
 * @param {String} modelInputId 模型输入框ID
 */
function filterModelsByAPI(apiBaseInputId, modelSelectId, modelInputId) {
    const apiBaseInput = document.getElementById(apiBaseInputId);
    const modelSelect = document.getElementById(modelSelectId);
    const modelInput = document.getElementById(modelInputId);

    if (!apiBaseInput || !modelSelect || !modelInput) return;

    const apiBase = apiBaseInput.value.toLowerCase();

    // 更新模型下拉列表
    updateModelOptions(modelSelect, apiBase);

    // 显示提示信息，但不自动设置默认模型
    if (apiBase.includes('x.ai')) {
        showAlert('ai-polling-result', 'info', '检测到X.AI API，推荐模型: grok-3-latest, grok-3-mini-beta, grok-3-mini-fast-beta');
    } else if (apiBase.includes('openai.com')) {
        showAlert('ai-polling-result', 'info', '检测到OpenAI API，推荐模型: gpt-4o-2024-05-13, gpt-4-turbo-2024-04-09, gpt-3.5-turbo-0125');
    } else if (apiBase.includes('groq.com') || apiBase.includes('groq.io')) {
        showAlert('ai-polling-result', 'info', '检测到Groq API，推荐模型: llama3-70b-8192, llama3-8b-8192, gemma2-9b-it, llama-3.1-8b-instant');
    } else if (apiBase.includes('anthropic.com')) {
        showAlert('ai-polling-result', 'info', '检测到Anthropic API，推荐模型: claude-3-7-sonnet-20250219, claude-3-5-sonnet-20241022, claude-3-opus-20240229');
    } else if (apiBase.includes('mistral.ai')) {
        showAlert('ai-polling-result', 'info', '检测到Mistral AI API，推荐模型: mistral-saba-24b, mistral-large-latest, mistral-medium-latest');
    } else if (apiBase.includes('together.xyz')) {
        showAlert('ai-polling-result', 'info', '检测到Together AI API，推荐模型: meta-llama/llama-4-maverick-17b-128e-instruct, meta-llama/Llama-3-70b-chat-hf');
    } else if (apiBase.includes('googleapis.com')) {
        showAlert('ai-polling-result', 'info', '检测到Google Gemini API，推荐模型: gemini-2.5-pro-preview-05-06, gemini-1.5-pro');
    }
}

/**
 * 显示提示信息
 * @param {String} elementId 元素ID
 * @param {String} type 提示类型
 * @param {String} message 提示信息
 */
function showAlert(elementId, type, message) {
    const alertEl = document.getElementById(elementId);
    alertEl.className = `alert alert-${type}`;
    alertEl.style.display = 'block';
    alertEl.classList.remove('d-none');

    if (type === 'success') {
        alertEl.innerHTML = `<i class="bi bi-check-circle-fill me-2"></i>${message}`;
    } else if (type === 'danger') {
        alertEl.innerHTML = `<i class="bi bi-exclamation-triangle-fill me-2"></i>${message}`;
    } else if (type === 'info') {
        alertEl.innerHTML = `<i class="bi bi-info-circle-fill me-2"></i>${message}`;
    } else {
        alertEl.innerHTML = message;
    }

    // 5秒后自动隐藏
    setTimeout(() => {
        alertEl.classList.add('d-none');
    }, 5000);
}
