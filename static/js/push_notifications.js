/**
 * 推送通知管理页面的JavaScript
 */

// 当前页码和筛选状态
let currentPage = 1;
let currentStatus = 'all';
let searchQuery = '';

// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // 加载通知列表
    loadNotifications();

    // 加载统计信息
    loadStats();

    // 绑定刷新按钮事件
    document.getElementById('refresh-btn').addEventListener('click', function() {
        loadNotifications();
        loadStats();
    });

    // 绑定状态筛选按钮事件
    document.querySelectorAll('.status-filter').forEach(button => {
        button.addEventListener('click', function() {
            // 移除所有按钮的active类
            document.querySelectorAll('.status-filter').forEach(btn => {
                btn.classList.remove('active');
            });

            // 添加当前按钮的active类
            this.classList.add('active');

            // 更新当前状态并重新加载
            currentStatus = this.dataset.status;
            currentPage = 1;
            loadNotifications();
        });
    });

    // 绑定搜索按钮事件
    document.getElementById('search-btn').addEventListener('click', function() {
        searchQuery = document.getElementById('search-input').value.trim();
        currentPage = 1;
        loadNotifications();
    });

    // 绑定搜索输入框回车事件
    document.getElementById('search-input').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            searchQuery = this.value.trim();
            currentPage = 1;
            loadNotifications();
        }
    });

    // 绑定清理确认按钮事件
    document.getElementById('confirm-clean-btn').addEventListener('click', function() {
        const status = document.getElementById('clean-status').value;
        const days = document.getElementById('clean-days').value;

        cleanNotifications(status, days);
    });

    // 绑定保存配置按钮事件
    document.getElementById('save-notification-btn').addEventListener('click', function() {
        saveNotificationConfig();
    });

    // 绑定发送测试按钮事件
    document.getElementById('send-test-btn').addEventListener('click', function() {
        sendTestNotification();
    });

    // 设置定时刷新（每60秒）
    setInterval(function() {
        loadStats();
    }, 60000);
});

/**
 * 加载通知列表
 */
function loadNotifications() {
    // 显示加载中
    document.getElementById('notifications-table-body').innerHTML = `
        <tr>
            <td colspan="7" class="text-center py-4">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">加载中...</span>
                </div>
                <p class="mt-2">加载中...</p>
            </td>
        </tr>
    `;

    // 构建URL
    let url = `/api/push_notifications?page=${currentPage}`;

    // 添加状态筛选
    if (currentStatus !== 'all') {
        url += `&status=${currentStatus}`;
    }

    // 添加搜索查询
    if (searchQuery) {
        url += `&search=${encodeURIComponent(searchQuery)}`;
    }

    // 发送请求
    fetch(url)
        .then(response => response.json())
        .then(data => {
            renderNotifications(data);
        })
        .catch(error => {
            console.error('加载通知列表时出错:', error);
            document.getElementById('notifications-table-body').innerHTML = `
                <tr>
                    <td colspan="7" class="text-center py-4">
                        <div class="alert alert-danger">
                            加载通知列表时出错: ${error.message || '未知错误'}
                        </div>
                    </td>
                </tr>
            `;
        });
}

/**
 * 渲染通知列表
 */
function renderNotifications(data) {
    const tableBody = document.getElementById('notifications-table-body');

    // 如果没有数据
    if (!data.notifications || data.notifications.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center py-4">
                    <p>没有找到通知记录</p>
                </td>
            </tr>
        `;
        return;
    }

    // 渲染通知列表
    let html = '';

    data.notifications.forEach(notification => {
        // 格式化时间
        const createdAt = new Date(notification.created_at).toLocaleString();
        const sentAt = notification.sent_at ? new Date(notification.sent_at).toLocaleString() : '-';

        // 状态标签
        let statusBadge = '';
        switch (notification.status) {
            case 'pending':
                statusBadge = '<span class="badge bg-info">待处理</span>';
                break;
            case 'success':
                statusBadge = '<span class="badge bg-success">成功</span>';
                break;
            case 'failed':
                statusBadge = '<span class="badge bg-danger">失败</span>';
                break;
            case 'retrying':
                statusBadge = '<span class="badge bg-warning">重试中</span>';
                break;
            default:
                statusBadge = `<span class="badge bg-secondary">${notification.status}</span>`;
        }

        // 构建行HTML
        html += `
            <tr>
                <td class="ps-4">
                    <p class="text-xs font-weight-bold mb-0">${notification.id}</p>
                </td>
                <td>
                    <div class="d-flex px-2 py-1">
                        <div class="d-flex flex-column justify-content-center">
                            <h6 class="mb-0 text-sm">${notification.title || '无标题'}</h6>
                            <p class="text-xs text-secondary mb-0">${notification.message || '无内容'}</p>
                        </div>
                    </div>
                </td>
                <td>
                    ${statusBadge}
                </td>
                <td class="align-middle text-center text-sm">
                    <p class="text-xs font-weight-bold mb-0">${notification.success_urls || 0} / ${notification.total_urls || 3}</p>
                </td>
                <td class="align-middle text-center">
                    <span class="text-secondary text-xs font-weight-bold">${createdAt}</span>
                </td>
                <td class="align-middle text-center">
                    <span class="text-secondary text-xs font-weight-bold">${sentAt}</span>
                </td>
                <td class="align-middle">
                    <button class="btn btn-link text-secondary mb-0" onclick="showDetails(${notification.id})">
                        <i class="bi bi-info-circle"></i>
                    </button>
                    ${notification.status === 'failed' ?
                        `<button class="btn btn-link text-primary mb-0" onclick="retryNotification(${notification.id})">
                            <i class="bi bi-arrow-repeat"></i>
                        </button>` : ''}
                    <button class="btn btn-link text-danger mb-0" onclick="deleteNotification(${notification.id})">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            </tr>
        `;
    });

    tableBody.innerHTML = html;

    // 渲染分页
    renderPagination(data.current_page, data.pages, data.total);
}

/**
 * 渲染分页
 */
function renderPagination(currentPage, totalPages, totalItems) {
    const pagination = document.getElementById('pagination');

    // 如果只有一页，不显示分页
    if (totalPages <= 1) {
        pagination.innerHTML = '';
        return;
    }

    let html = '';

    // 上一页按钮
    html += `
        <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
            <a class="page-link" href="javascript:void(0)" onclick="goToPage(${currentPage - 1})" aria-label="Previous">
                <span aria-hidden="true">&laquo;</span>
            </a>
        </li>
    `;

    // 页码按钮
    const maxVisiblePages = 5;
    let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2));
    let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);

    // 调整startPage，确保显示maxVisiblePages个页码
    if (endPage - startPage + 1 < maxVisiblePages) {
        startPage = Math.max(1, endPage - maxVisiblePages + 1);
    }

    // 第一页
    if (startPage > 1) {
        html += `
            <li class="page-item">
                <a class="page-link" href="javascript:void(0)" onclick="goToPage(1)">1</a>
            </li>
        `;

        // 省略号
        if (startPage > 2) {
            html += `
                <li class="page-item disabled">
                    <a class="page-link" href="javascript:void(0)">...</a>
                </li>
            `;
        }
    }

    // 页码
    for (let i = startPage; i <= endPage; i++) {
        html += `
            <li class="page-item ${i === currentPage ? 'active' : ''}">
                <a class="page-link" href="javascript:void(0)" onclick="goToPage(${i})">${i}</a>
            </li>
        `;
    }

    // 最后一页
    if (endPage < totalPages) {
        // 省略号
        if (endPage < totalPages - 1) {
            html += `
                <li class="page-item disabled">
                    <a class="page-link" href="javascript:void(0)">...</a>
                </li>
            `;
        }

        html += `
            <li class="page-item">
                <a class="page-link" href="javascript:void(0)" onclick="goToPage(${totalPages})">${totalPages}</a>
            </li>
        `;
    }

    // 下一页按钮
    html += `
        <li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
            <a class="page-link" href="javascript:void(0)" onclick="goToPage(${currentPage + 1})" aria-label="Next">
                <span aria-hidden="true">&raquo;</span>
            </a>
        </li>
    `;

    pagination.innerHTML = html;
}

/**
 * 跳转到指定页
 */
function goToPage(page) {
    currentPage = page;
    loadNotifications();
}

/**
 * 加载统计信息
 */
function loadStats() {
    fetch('/api/push_notifications/stats')
        .then(response => response.json())
        .then(data => {
            // 更新统计数字
            document.getElementById('pending-count').textContent = data.pending_count;
            document.getElementById('retrying-count').textContent = data.retrying_count;
            document.getElementById('success-count').textContent = data.success_count;
            document.getElementById('failed-count').textContent = data.failed_count;
            document.getElementById('recent-count').textContent = data.recent_count;

            // 更新工作线程状态
            if (data.worker_status.running) {
                document.getElementById('worker-status').textContent = '运行中';
                document.getElementById('worker-status').className = 'font-weight-bolder text-success';
            } else {
                document.getElementById('worker-status').textContent = '已停止';
                document.getElementById('worker-status').className = 'font-weight-bolder text-danger';
            }

            // 更新处理间隔
            document.getElementById('worker-interval').textContent = `${data.worker_status.interval_seconds || 30}秒`;
        })
        .catch(error => {
            console.error('加载统计信息时出错:', error);
        });
}

/**
 * 显示通知详情
 */
function showDetails(id) {
    // 从通知列表中获取通知数据
    fetch(`/api/push_notifications?id=${id}`)
        .then(response => response.json())
        .then(data => {
            if (data.notifications && data.notifications.length > 0) {
                const notification = data.notifications[0];

                // 填充模态框
                document.getElementById('detail-title').value = notification.title || '无标题';
                document.getElementById('detail-message').value = notification.message || '无内容';
                document.getElementById('detail-status').value = getStatusText(notification.status);
                document.getElementById('detail-attempts').value = `${notification.success_urls || 0} / ${notification.total_urls || 3}`;
                document.getElementById('detail-error').value = notification.error_message || '无错误信息';

                // 显示/隐藏重试按钮
                const retryBtn = document.getElementById('retry-btn');
                if (notification.status === 'failed') {
                    retryBtn.style.display = 'block';
                    retryBtn.onclick = function() {
                        retryNotification(notification.id);
                    };
                } else {
                    retryBtn.style.display = 'none';
                }

                // 显示模态框
                new bootstrap.Modal(document.getElementById('detailModal')).show();
            }
        })
        .catch(error => {
            console.error('获取通知详情时出错:', error);
            alert('获取通知详情时出错: ' + (error.message || '未知错误'));
        });
}

/**
 * 重试通知
 */
function retryNotification(id) {
    if (!confirm('确定要重试此通知吗？')) {
        return;
    }

    fetch(`/api/push_notifications/${id}/retry`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('通知已加入重试队列');

                // 关闭详情模态框（如果打开）
                const detailModal = bootstrap.Modal.getInstance(document.getElementById('detailModal'));
                if (detailModal) {
                    detailModal.hide();
                }

                // 重新加载数据
                loadNotifications();
                loadStats();
            } else {
                alert('重试失败: ' + data.message);
            }
        })
        .catch(error => {
            console.error('重试通知时出错:', error);
            alert('重试通知时出错: ' + (error.message || '未知错误'));
        });
}

/**
 * 删除通知
 */
function deleteNotification(id) {
    if (!confirm('确定要删除此通知吗？此操作不可撤销。')) {
        return;
    }

    fetch(`/api/push_notifications/${id}/delete`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('通知已删除');

                // 重新加载数据
                loadNotifications();
                loadStats();
            } else {
                alert('删除失败: ' + data.message);
            }
        })
        .catch(error => {
            console.error('删除通知时出错:', error);
            alert('删除通知时出错: ' + (error.message || '未知错误'));
        });
}

/**
 * 清理通知
 */
function cleanNotifications(status, days) {
    if (!confirm(`确定要清理${getStatusText(status)}的${days}天前的通知吗？此操作不可撤销。`)) {
        return;
    }

    fetch('/api/push_notifications/clean', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            status: status,
            days: parseInt(days)
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(data.message);

                // 关闭清理模态框
                bootstrap.Modal.getInstance(document.getElementById('cleanModal')).hide();

                // 重新加载数据
                loadNotifications();
                loadStats();
            } else {
                alert('清理失败: ' + data.message);
            }
        })
        .catch(error => {
            console.error('清理通知时出错:', error);
            alert('清理通知时出错: ' + (error.message || '未知错误'));
        });
}

/**
 * 获取状态文本
 */
function getStatusText(status) {
    switch (status) {
        case 'pending':
            return '待处理';
        case 'success':
            return '成功';
        case 'failed':
            return '失败';
        case 'retrying':
            return '重试中';
        default:
            return status;
    }
}



/**
 * 保存推送配置
 */
function saveNotificationConfig() {
    // 获取表单数据
    const appriseUrls = document.getElementById('apprise-urls').value;
    const pushQueueEnabled = document.getElementById('push-queue-enabled').checked;
    const pushQueueInterval = parseInt(document.getElementById('push-queue-interval').value) || 30;
    const pushMaxAttempts = parseInt(document.getElementById('push-max-attempts').value) || 3;

    // 显示加载中
    const resultDiv = document.getElementById('notification-result');
    resultDiv.innerHTML = `
        <div class="alert alert-info">
            <i class="bi bi-hourglass-split me-2"></i>正在保存配置...
        </div>
    `;

    // 发送请求
    fetch('/api/push_notifications/config', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            apprise_urls: appriseUrls,
            push_queue_enabled: pushQueueEnabled,
            push_queue_interval: pushQueueInterval,
            push_max_attempts: pushMaxAttempts
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                resultDiv.innerHTML = `
                    <div class="alert alert-success">
                        <i class="bi bi-check-circle me-2"></i>${data.message}
                    </div>
                `;

                // 重新加载统计信息
                loadStats();
            } else {
                resultDiv.innerHTML = `
                    <div class="alert alert-danger">
                        <i class="bi bi-x-circle me-2"></i>${data.message}
                    </div>
                `;
            }
        })
        .catch(error => {
            console.error('保存推送配置时出错:', error);
            resultDiv.innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-x-circle me-2"></i>保存推送配置时出错: ${error.message || '未知错误'}
                </div>
            `;
        });
}

/**
 * 发送测试通知
 */
function sendTestNotification() {
    // 获取表单数据
    const title = document.getElementById('test-title').value;
    const message = document.getElementById('test-message').value;
    const tag = document.getElementById('test-tag').value;
    const url = document.getElementById('test-url').value;
    const useQueue = document.getElementById('test-use-queue').checked;

    // 显示加载中
    const resultDiv = document.getElementById('test-result');
    resultDiv.innerHTML = `
        <div class="alert alert-info">
            <i class="bi bi-hourglass-split me-2"></i>正在发送测试通知...
        </div>
    `;

    // 发送请求
    fetch('/api/push_notifications/test', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            title: title,
            message: message,
            tag: tag,
            url: url,
            use_queue: useQueue
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                resultDiv.innerHTML = `
                    <div class="alert alert-success">
                        <i class="bi bi-check-circle me-2"></i>${data.message}
                    </div>
                `;

                // 如果使用队列，添加查看链接
                if (useQueue && data.notification_id) {
                    resultDiv.innerHTML += `
                        <div class="alert alert-info">
                            <i class="bi bi-info-circle me-2"></i>
                            <a href="javascript:void(0)" onclick="showDetails(${data.notification_id})">查看通知详情</a>
                        </div>
                    `;
                }

                // 重新加载统计信息
                loadStats();
            } else {
                resultDiv.innerHTML = `
                    <div class="alert alert-danger">
                        <i class="bi bi-x-circle me-2"></i>${data.message}
                    </div>
                `;
            }
        })
        .catch(error => {
            console.error('发送测试通知时出错:', error);
            resultDiv.innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-x-circle me-2"></i>发送测试通知时出错: ${error.message || '未知错误'}
                </div>
            `;
        });
}
