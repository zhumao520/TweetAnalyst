/**
 * 代理管理器JavaScript模块
 * 用于管理多个代理配置
 */

// 代理管理器对象
const ProxyManager = {
    // 初始化
    init: function() {
        console.log('初始化代理管理器');
        try {
            this.loadProxyList();
            this.setupEventListeners();
            this.checkAllProxies(); // 自动检查所有代理状态
        } catch (e) {
            console.error('代理管理器初始化错误:', e);
        }
    },

    // 设置事件监听器
    setupEventListeners: function() {
        try {
            // 检查所有代理按钮点击事件
            const checkProxiesBtn = document.getElementById('check-proxies-btn');
            if (checkProxiesBtn) {
                checkProxiesBtn.addEventListener('click', function() {
                    ProxyManager.checkAllProxies();
                });
            }
        } catch (e) {
            console.error('设置事件监听器错误:', e);
        }
    },

    // 加载代理列表
    loadProxyList: function() {
        try {
            const container = document.getElementById('proxy-list-container');
            if (!container) return;

            container.innerHTML = `
                <div class="d-flex align-items-center">
                    <div class="spinner-border spinner-border-sm text-primary me-2" role="status">
                        <span class="visually-hidden">加载中...</span>
                    </div>
                    <span>正在加载代理列表...</span>
                </div>
            `;

            // 发送请求获取代理列表
            fetch('/api/proxy/list')
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        this.renderProxyList(data.data);
                    } else {
                        container.innerHTML = `
                            <div class="alert alert-danger">
                                <i class="bi bi-exclamation-triangle-fill me-2"></i>
                                加载代理列表失败: ${data.message}
                            </div>
                        `;
                    }
                })
                .catch(error => {
                    container.innerHTML = `
                        <div class="alert alert-danger">
                            <i class="bi bi-exclamation-triangle-fill me-2"></i>
                            加载代理列表出错: ${error.message}
                        </div>
                    `;
                });
        } catch (e) {
            console.error('加载代理列表错误:', e);
        }
    },

    // 渲染代理列表
    renderProxyList: function(proxies) {
        const container = document.getElementById('proxy-list-container');
        const proxyCountBadge = document.getElementById('proxy-count');
        if (!container) return;

        // 更新代理数量
        if (proxyCountBadge) {
            proxyCountBadge.textContent = proxies ? proxies.length : 0;
        }

        if (!proxies || proxies.length === 0) {
            container.innerHTML = `
                <div class="alert alert-info">
                    <i class="bi bi-info-circle-fill me-2"></i>
                    暂无代理配置，请点击"添加代理"按钮添加代理。
                </div>
            `;
            return;
        }

        let html = '<div class="table-responsive"><table class="table table-hover table-bordered">';
        html += '<thead class="table-light"><tr>';
        html += '<th style="width: 40px;"><input type="checkbox" class="form-check-input" id="select-all-proxies" onclick="ProxyManager.toggleSelectAllProxies()"></th>';
        html += '<th>名称</th>';
        html += '<th>协议</th>';
        html += '<th>主机:端口</th>';
        html += '<th>优先级</th>';
        html += '<th>状态</th>';
        html += '<th>操作</th>';
        html += '</tr></thead>';
        html += '<tbody>';

        // 添加代理行
        proxies.forEach(proxy => {
            const statusClass = proxy.is_active ? 'success' : 'secondary';
            const statusText = proxy.is_active ? '启用' : '禁用';
            const lastCheckResult = proxy.last_check_result === true ?
                '<span class="badge bg-success"><i class="bi bi-check-circle-fill me-1"></i>可用</span>' :
                (proxy.last_check_result === false ?
                    '<span class="badge bg-danger"><i class="bi bi-x-circle-fill me-1"></i>不可用</span>' :
                    '<span class="badge bg-secondary"><i class="bi bi-question-circle-fill me-1"></i>未测试</span>');

            html += `<tr>
                <td class="text-center">
                    <input type="checkbox" class="form-check-input proxy-select" value="${proxy.id}" data-proxy-id="${proxy.id}">
                </td>
                <td>${proxy.name}</td>
                <td><span class="badge bg-info">${proxy.protocol.toUpperCase()}</span></td>
                <td>${proxy.host}:${proxy.port}</td>
                <td>${proxy.priority}</td>
                <td>
                    <span class="badge bg-${statusClass}">${statusText}</span>
                    ${lastCheckResult}
                </td>
                <td>
                    <div class="btn-group btn-group-sm" role="group">
                        <button type="button" class="btn btn-outline-primary" onclick="ProxyManager.editProxy(${proxy.id})" title="编辑">
                            <i class="bi bi-pencil"></i>
                        </button>
                        <button type="button" class="btn btn-outline-danger" onclick="ProxyManager.deleteProxy(${proxy.id})" title="删除">
                            <i class="bi bi-trash"></i>
                        </button>
                        <button type="button" class="btn btn-outline-success" onclick="ProxyManager.testProxy(${proxy.id})" title="测试">
                            <i class="bi bi-check2-circle"></i>
                        </button>
                    </div>
                </td>
            </tr>`;
        });

        html += '</tbody></table></div>';
        container.innerHTML = html;
    },

    // 切换全选代理
    toggleSelectAllProxies: function() {
        const selectAllCheckbox = document.getElementById('select-all-proxies');
        const proxyCheckboxes = document.querySelectorAll('.proxy-select');

        proxyCheckboxes.forEach(checkbox => {
            checkbox.checked = selectAllCheckbox.checked;
        });
    },

    // 检查所有代理
    checkAllProxies: function() {
        try {
            const statusContainer = document.getElementById('proxy-manager-status');
            if (!statusContainer) return;

            statusContainer.innerHTML = `
                <div class="d-flex align-items-center">
                    <div class="spinner-border spinner-border-sm text-primary me-2" role="status">
                        <span class="visually-hidden">检查中...</span>
                    </div>
                    <span>正在检查所有代理状态...</span>
                </div>
            `;

            // 获取CSRF令牌
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;

            // 发送请求检查所有代理
            fetch('/api/proxy/test_all', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken || ''
                },
                body: JSON.stringify({
                    url: 'https://www.google.com/generate_204'  // 添加默认测试URL
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    let html = '<div class="table-responsive"><table class="table table-sm table-bordered">';
                    html += '<thead><tr><th>代理名称</th><th>状态</th><th>响应时间</th></tr></thead>';
                    html += '<tbody>';

                    // 调试输出
                    console.log('检查所有代理结果:', data);

                    // 添加代理状态行
                    let successCount = 0;
                    data.data.forEach((result, index) => {
                        console.log(`代理 ${index} 检查结果:`, result);

                        const success = result.success;
                        if (success) successCount++;

                        const statusClass = success ? 'success' : 'danger';
                        const statusIcon = success ? 'check-circle-fill' : 'x-circle-fill';
                        const statusText = success ? '可用' : '不可用';

                        // 尝试从不同位置获取代理名称
                        const proxyName = result.data?.proxy?.name ||
                                         result.data?.name ||
                                         result.proxy?.name ||
                                         result.name ||
                                         `代理 ${index + 1}`;

                        const responseTime = result.data?.response_time ||
                                            result.response_time ||
                                            '-';

                        html += `<tr>
                            <td><i class="bi bi-hdd-network me-1"></i>${proxyName}</td>
                            <td><span class="badge bg-${statusClass}"><i class="bi bi-${statusIcon} me-1"></i>${statusText}</span></td>
                            <td>${responseTime}</td>
                        </tr>`;
                    });

                    html += '</tbody></table></div>';

                    // 添加摘要信息
                    html += `<div class="alert alert-${successCount > 0 ? 'success' : 'warning'} mt-2">
                        <i class="bi bi-info-circle-fill me-2"></i>
                        共测试 ${data.data.length} 个代理，${successCount} 个可用，${data.data.length - successCount} 个不可用
                    </div>`;

                    statusContainer.innerHTML = html;

                    // 重新加载代理列表
                    this.loadProxyList();
                } else {
                    statusContainer.innerHTML = `
                        <div class="alert alert-danger">
                            <i class="bi bi-exclamation-triangle-fill me-2"></i>
                            检查代理状态失败: ${data.message}
                        </div>
                    `;
                }
            })
            .catch(error => {
                statusContainer.innerHTML = `
                    <div class="alert alert-danger">
                        <i class="bi bi-exclamation-triangle-fill me-2"></i>
                        检查代理状态出错: ${error.message}
                    </div>
                `;
            });
        } catch (e) {
            console.error('检查所有代理错误:', e);
        }
    },

    // 注意：已移除saveDefaultProxy和testDefaultProxy函数，因为我们不再使用默认代理配置

    // 添加代理
    addProxy: function() {
        const name = document.getElementById('add-proxy-name').value;
        const protocol = document.getElementById('add-proxy-protocol').value;
        const host = document.getElementById('add-proxy-host').value;
        const port = parseInt(document.getElementById('add-proxy-port').value);
        const username = document.getElementById('add-proxy-username').value;
        const password = document.getElementById('add-proxy-password').value;
        const priority = parseInt(document.getElementById('add-proxy-priority').value);
        const isActive = document.getElementById('add-proxy-active').checked;

        // 验证输入
        if (!name || !host || !port) {
            alert('请填写必填字段：名称、主机地址和端口');
            return;
        }

        // 发送请求添加代理
        fetch('/api/proxy/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                name: name,
                host: host,
                port: port,
                protocol: protocol,
                username: username || null,
                password: password || null,
                priority: priority,
                is_active: isActive
            }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // 关闭模态框
                const modal = bootstrap.Modal.getInstance(document.getElementById('addProxyModal'));
                if (modal) modal.hide();

                // 重新加载代理列表
                this.loadProxyList();

                // 显示成功消息
                alert('代理添加成功');
            } else {
                alert(`添加代理失败: ${data.message}`);
            }
        })
        .catch(error => {
            alert(`请求错误: ${error.message}`);
        });
    },

    // 编辑代理
    editProxy: function(proxyId) {
        // 发送请求获取代理详情
        fetch(`/api/proxy/${proxyId}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const proxy = data.data;

                    // 填充表单
                    document.getElementById('edit-proxy-id').value = proxy.id;
                    document.getElementById('edit-proxy-name').value = proxy.name;
                    document.getElementById('edit-proxy-protocol').value = proxy.protocol;
                    document.getElementById('edit-proxy-host').value = proxy.host;
                    document.getElementById('edit-proxy-port').value = proxy.port;
                    document.getElementById('edit-proxy-username').value = proxy.username || '';
                    document.getElementById('edit-proxy-password').value = '';
                    document.getElementById('edit-proxy-priority').value = proxy.priority;
                    document.getElementById('edit-proxy-active').checked = proxy.is_active;

                    // 显示模态框
                    const modal = new bootstrap.Modal(document.getElementById('editProxyModal'));
                    modal.show();
                } else {
                    alert(`获取代理详情失败: ${data.message}`);
                }
            })
            .catch(error => {
                alert(`请求错误: ${error.message}`);
            });
    },

    // 更新代理
    updateProxy: function() {
        const proxyId = document.getElementById('edit-proxy-id').value;
        const name = document.getElementById('edit-proxy-name').value;
        const protocol = document.getElementById('edit-proxy-protocol').value;
        const host = document.getElementById('edit-proxy-host').value;
        const port = parseInt(document.getElementById('edit-proxy-port').value);
        const username = document.getElementById('edit-proxy-username').value;
        const password = document.getElementById('edit-proxy-password').value;
        const priority = parseInt(document.getElementById('edit-proxy-priority').value);
        const isActive = document.getElementById('edit-proxy-active').checked;

        // 验证输入
        if (!name || !host || !port) {
            alert('请填写必填字段：名称、主机地址和端口');
            return;
        }

        // 构建请求数据
        const data = {
            name: name,
            host: host,
            port: port,
            protocol: protocol,
            username: username || null,
            priority: priority,
            is_active: isActive
        };

        // 如果密码不为空，添加到请求数据中
        if (password) {
            data.password = password;
        }

        // 发送请求更新代理
        fetch(`/api/proxy/${proxyId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // 关闭模态框
                const modal = bootstrap.Modal.getInstance(document.getElementById('editProxyModal'));
                if (modal) modal.hide();

                // 重新加载代理列表
                this.loadProxyList();

                // 显示成功消息
                alert('代理更新成功');
            } else {
                alert(`更新代理失败: ${data.message}`);
            }
        })
        .catch(error => {
            alert(`请求错误: ${error.message}`);
        });
    },

    // 删除代理
    deleteProxy: function(proxyId) {
        if (!confirm('确定要删除此代理吗？此操作不可恢复。')) {
            return;
        }

        // 发送请求删除代理
        fetch(`/api/proxy/${proxyId}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // 重新加载代理列表
                this.loadProxyList();

                // 显示成功消息
                alert('代理删除成功');
            } else {
                alert(`删除代理失败: ${data.message}`);
            }
        })
        .catch(error => {
            alert(`请求错误: ${error.message}`);
        });
    },

    // 测试代理
    testProxy: function(proxyId) {
        const statusContainer = document.getElementById('proxy-manager-status');

        // 显示加载状态
        statusContainer.innerHTML = `
            <div class="d-flex align-items-center">
                <div class="spinner-border spinner-border-sm text-primary me-2" role="status">
                    <span class="visually-hidden">测试中...</span>
                </div>
                <span>正在测试代理...</span>
            </div>
        `;

        // 获取CSRF令牌
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;

        // 发送请求测试代理
        fetch(`/api/proxy/${proxyId}/test`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken || ''
            },
            body: JSON.stringify({
                url: 'https://www.google.com/generate_204'  // 添加默认测试URL
            })
        })
        .then(response => response.json())
        .then(data => {
            // 调试输出
            console.log('单个代理测试结果:', data);

            if (data.success) {
                // 尝试从不同位置获取代理名称和响应时间
                const proxyName = data.data?.proxy?.name ||
                                 data.data?.name ||
                                 data.proxy?.name ||
                                 data.name ||
                                 `代理 ${proxyId}`;

                const responseTime = data.data?.response_time ||
                                    data.response_time ||
                                    '-';

                statusContainer.innerHTML = `
                    <div class="alert alert-success">
                        <h5><i class="bi bi-check-circle-fill me-2"></i>代理测试成功</h5>
                        <p>代理: ${proxyName}</p>
                        <p>响应时间: ${responseTime}</p>
                    </div>
                `;

                // 重新加载代理列表
                this.loadProxyList();
            } else {
                statusContainer.innerHTML = `
                    <div class="alert alert-danger">
                        <h5><i class="bi bi-x-circle-fill me-2"></i>代理测试失败</h5>
                        <p>${data.message}</p>
                    </div>
                `;
            }
        })
        .catch(error => {
            statusContainer.innerHTML = `
                <div class="alert alert-danger">
                    <h5><i class="bi bi-exclamation-triangle-fill me-2"></i>请求错误</h5>
                    <p>${error.message}</p>
                </div>
            `;
        });
    },

    // 测试选中的代理
    testSelectedProxies: function() {
        try {
            const selectedProxies = document.querySelectorAll('.proxy-select:checked');
            const statusContainer = document.getElementById('proxy-manager-status');

            if (!statusContainer) {
                console.error('未找到代理管理器状态容器');
                return;
            }

            if (selectedProxies.length === 0) {
                statusContainer.innerHTML = `
                    <div class="alert alert-warning">
                        <i class="bi bi-exclamation-triangle-fill me-2"></i>
                        请先选择要测试的代理
                    </div>
                `;
                return;
            }

            // 显示加载状态
            statusContainer.innerHTML = `
                <div class="d-flex align-items-center">
                    <div class="spinner-border spinner-border-sm text-primary me-2" role="status">
                        <span class="visually-hidden">测试中...</span>
                    </div>
                    <span>正在测试选中的 ${selectedProxies.length} 个代理...</span>
                </div>
            `;

            // 收集所有选中的代理ID
            const proxyIds = Array.from(selectedProxies).map(checkbox => checkbox.value);

            // 获取CSRF令牌
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;

            // 创建测试任务
            const testTasks = proxyIds.map(proxyId =>
                fetch(`/api/proxy/${proxyId}/test`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken || ''
                    },
                    body: JSON.stringify({
                        url: 'https://www.google.com/generate_204'  // 添加默认测试URL
                    })
                })
                .then(response => response.json())
            );

            // 执行所有测试任务
            Promise.all(testTasks)
                .then(results => {
                    // 调试输出
                    console.log('代理测试结果:', results);

                    let html = '<div class="table-responsive"><table class="table table-sm table-bordered">';
                    html += '<thead><tr><th>代理名称</th><th>状态</th><th>响应时间</th></tr></thead>';
                    html += '<tbody>';

                    // 添加测试结果行
                    let successCount = 0;
                    results.forEach((result, index) => {
                        console.log(`代理 ${index} 测试结果:`, result);

                        // 尝试从结果中获取代理信息
                        const proxyId = proxyIds[index];
                        const proxyName = result.data?.proxy?.name ||
                                         result.data?.name ||
                                         `代理 ${proxyId}`;

                        if (result.success) {
                            successCount++;
                            html += `<tr>
                                <td><i class="bi bi-hdd-network me-1"></i>${proxyName}</td>
                                <td><span class="badge bg-success"><i class="bi bi-check-circle-fill me-1"></i>可用</span></td>
                                <td>${result.data?.response_time || '-'}</td>
                            </tr>`;
                        } else {
                            html += `<tr>
                                <td><i class="bi bi-hdd-network me-1"></i>${proxyName}</td>
                                <td><span class="badge bg-danger"><i class="bi bi-x-circle-fill me-1"></i>不可用</span></td>
                                <td>-</td>
                            </tr>`;
                        }
                    });

                    html += '</tbody></table></div>';

                    // 添加摘要信息
                    html += `<div class="alert alert-${successCount > 0 ? 'success' : 'warning'} mt-2">
                        <i class="bi bi-info-circle-fill me-2"></i>
                        共测试 ${results.length} 个代理，${successCount} 个可用，${results.length - successCount} 个不可用
                    </div>`;

                    statusContainer.innerHTML = html;

                    // 重新加载代理列表
                    this.loadProxyList();
                })
                .catch(error => {
                    statusContainer.innerHTML = `
                        <div class="alert alert-danger">
                            <h5><i class="bi bi-exclamation-triangle-fill me-2"></i>请求错误</h5>
                            <p>${error.message}</p>
                        </div>
                    `;
                });
        } catch (e) {
            console.error('测试选中代理错误:', e);
        }
    }
};

// 显示添加代理模态框
function showAddProxyModal() {
    // 重置表单
    document.getElementById('add-proxy-form').reset();

    // 显示模态框
    const modal = new bootstrap.Modal(document.getElementById('addProxyModal'));
    modal.show();
}

// 测试选中的代理
function testSelectedProxy() {
    ProxyManager.testSelectedProxies();
}

// 添加代理
function addProxy() {
    ProxyManager.addProxy();
}

// 更新代理
function updateProxy() {
    ProxyManager.updateProxy();
}

// 检查所有代理
function checkAllProxies() {
    ProxyManager.checkAllProxies();
}

// 页面加载完成后初始化代理管理器
document.addEventListener('DOMContentLoaded', function() {
    // 初始化代理管理器
    ProxyManager.init();
});
