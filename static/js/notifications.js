/**
 * 通知功能模块
 * 处理通知的加载、显示和标记已读功能
 */

// 在全局命名空间中创建TweetAnalyst对象（如果不存在）
if (typeof TweetAnalyst === 'undefined') {
    window.TweetAnalyst = {};
}

// 创建通知模块
TweetAnalyst.notifications = (function() {
    // 私有变量
    let notificationBadge;
    let notificationsContainer;
    let readNotifications = [];
    let refreshInterval = 60000; // 默认刷新间隔：1分钟

    /**
     * 初始化通知功能
     * @param {Object} options - 配置选项
     * @param {string} options.badgeSelector - 通知徽章元素选择器
     * @param {string} options.containerSelector - 通知容器元素选择器
     * @param {number} options.refreshInterval - 刷新间隔（毫秒）
     */
    function init(options = {}) {
        // 获取DOM元素
        notificationBadge = document.getElementById(options.badgeSelector || 'notification-badge');
        notificationsContainer = document.getElementById(options.containerSelector || 'notifications-container');

        // 设置刷新间隔
        if (options.refreshInterval) {
            refreshInterval = options.refreshInterval;
        }

        // 从本地存储获取已读通知
        readNotifications = JSON.parse(localStorage.getItem('readNotifications') || '[]');

        // 初始加载通知
        loadNotifications();

        // 设置定时刷新
        setInterval(loadNotifications, refreshInterval);

        console.log('通知功能已初始化');
    }

    /**
     * 加载通知
     */
    function loadNotifications() {
        fetch('/api/notifications')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    updateNotifications(data.data, data.total_count);
                } else {
                    console.error('Failed to load notifications:', data.message);
                }
            })
            .catch(error => {
                console.error('Error loading notifications:', error);
            });
    }

    /**
     * 更新通知UI
     * @param {Array} notifications - 通知数据数组
     * @param {number} totalCount - 通知总数
     */
    function updateNotifications(notifications, totalCount) {
        console.log(`更新通知UI，总数: ${totalCount}`);

        // 清空容器
        notificationsContainer.innerHTML = '';

        // 添加标题
        const header = document.createElement('li');
        header.innerHTML = `<h6 class="dropdown-header">通知 (${totalCount || 0})</h6>`;
        notificationsContainer.appendChild(header);

        // 添加分隔线
        const divider = document.createElement('li');
        divider.innerHTML = '<hr class="dropdown-divider">';
        notificationsContainer.appendChild(divider);

        // 如果没有通知
        if (notifications.length === 0) {
            const emptyItem = document.createElement('li');
            emptyItem.innerHTML = '<a class="dropdown-item text-center" href="#">暂无通知</a>';
            notificationsContainer.appendChild(emptyItem);
            notificationBadge.classList.add('d-none');
            return;
        }

        // 计算未读通知数量
        let unreadCount = 0;

        // 计算未读通知数量并标记通知状态
        notifications.forEach(notification => {
            const isRead = readNotifications.includes(notification.id);
            notification.isRead = isRead;
            if (!isRead) {
                unreadCount++;
            }
        });

        console.log(`未读通知数量: ${unreadCount}`);

        // 优先显示未读通知，然后是最近的已读通知，总共最多显示10条
        const unreadNotifications = notifications.filter(notification => !notification.isRead);
        const recentReadNotifications = notifications.filter(notification => notification.isRead)
            .slice(0, Math.max(0, 10 - unreadNotifications.length));

        console.log(`未读通知: ${unreadNotifications.length}, 显示的已读通知: ${recentReadNotifications.length}`);

        // 合并未读和最近的已读通知，并按时间排序（最新的在前面）
        let notificationsToShow = [...unreadNotifications, ...recentReadNotifications];

        // 按时间排序，确保最新的通知显示在前面
        notificationsToShow.sort((a, b) => {
            const timeA = new Date(a.time).getTime();
            const timeB = new Date(b.time).getTime();
            return timeB - timeA; // 降序排列，最新的在前面
        });

        // 添加通知项
        notificationsToShow.forEach(notification => {
            // 使用通知对象上的isRead属性
            const isRead = notification.isRead;

            // 创建通知项
            const item = document.createElement('li');
            const notificationTime = new Date(notification.time);
            const timeString = notificationTime.toLocaleString('zh-CN', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });

            // 添加数据属性，用于标识通知
            item.setAttribute('data-notification-id', notification.id);

            item.innerHTML = `
                <a class="dropdown-item ${isRead ? 'text-muted' : 'fw-bold'}" href="${notification.url}">
                    <div class="d-flex w-100 justify-content-between">
                        <h6 class="mb-1">${notification.title}</h6>
                        <small>${timeString}</small>
                    </div>
                    <p class="mb-1 small">${notification.content}</p>
                </a>
            `;

            // 点击事件：标记为已读
            item.querySelector('a').addEventListener('click', function() {
                markAsRead(notification.id);
            });

            notificationsContainer.appendChild(item);
        });

        // 添加"全部标记为已读"按钮
        if (unreadCount > 0) {
            const markAllItem = document.createElement('li');
            markAllItem.innerHTML = '<hr class="dropdown-divider">';
            notificationsContainer.appendChild(markAllItem);

            const markAllButton = document.createElement('li');
            markAllButton.innerHTML = '<a class="dropdown-item text-center" href="#">全部标记为已读</a>';
            markAllButton.querySelector('a').addEventListener('click', function(e) {
                e.preventDefault();
                markAllAsRead(notifications);
            });
            notificationsContainer.appendChild(markAllButton);
        }

        // 更新未读数量徽章 - 使用未读通知数量而不是总数
        const countElement = notificationBadge.querySelector('.notification-count');
        if (countElement) {
            countElement.textContent = unreadCount > 99 ? '99+' : unreadCount;
        } else {
            notificationBadge.textContent = unreadCount > 99 ? '99+' : unreadCount;
        }

        // 只有在有未读通知时才显示徽章
        if (unreadCount > 0) {
            notificationBadge.classList.remove('d-none');
        } else {
            notificationBadge.classList.add('d-none');
        }

        // 记录日志
        console.log(`更新通知徽章: 未读通知数量=${unreadCount}, 总通知数量=${totalCount}`);

        // 更新页面标题中的通知数量 - 使用未读通知数量
        updatePageTitle(unreadCount);
    }

    /**
     * 标记单个通知为已读
     * @param {string} id - 通知ID
     */
    function markAsRead(id) {
        if (!readNotifications.includes(id)) {
            console.log(`标记通知为已读: ${id}`);
            readNotifications.push(id);
            localStorage.setItem('readNotifications', JSON.stringify(readNotifications));

            // 立即更新通知徽章 - 减少一个未读通知
            const countElement = notificationBadge.querySelector('.notification-count');
            const currentCount = parseInt(countElement ? countElement.textContent : notificationBadge.textContent);

            if (!isNaN(currentCount) && currentCount > 0) {
                const newCount = currentCount - 1;

                // 更新徽章数字
                if (countElement) {
                    countElement.textContent = newCount;
                } else {
                    notificationBadge.textContent = newCount;
                }

                // 如果没有未读通知了，隐藏徽章
                if (newCount <= 0) {
                    notificationBadge.classList.add('d-none');
                }

                // 更新页面标题
                updatePageTitle(newCount);
            }

            // 立即重新加载通知列表，不等待
            fetch('/api/notifications')
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        console.log('通知标记为已读后立即重新加载通知列表');
                        updateNotifications(data.data, data.total_count);
                    } else {
                        console.error('重新加载通知失败:', data.message);
                    }
                })
                .catch(error => {
                    console.error('重新加载通知时出错:', error);
                });
        }
    }

    /**
     * 标记所有通知为已读
     * @param {Array} notifications - 通知数据数组
     */
    function markAllAsRead(notifications) {
        // 计算新增的已读通知数量
        let newReadCount = 0;

        notifications.forEach(notification => {
            if (!readNotifications.includes(notification.id)) {
                readNotifications.push(notification.id);
                newReadCount++;
            }
        });

        localStorage.setItem('readNotifications', JSON.stringify(readNotifications));

        console.log(`标记所有通知为已读，新增已读通知: ${newReadCount}`);

        // 立即更新通知徽章 - 清零
        const countElement = notificationBadge.querySelector('.notification-count');
        if (countElement) {
            countElement.textContent = '0';
        } else {
            notificationBadge.textContent = '0';
        }

        // 隐藏徽章
        notificationBadge.classList.add('d-none');

        // 更新页面标题
        updatePageTitle(0);

        // 重新加载通知以更新UI
        loadNotifications();
    }

    /**
     * 更新页面标题，显示未读通知数量
     * @param {number} unreadCount - 未读通知数量
     */
    function updatePageTitle(unreadCount) {
        const originalTitle = document.title.replace(/^\(\d+\) /, '');
        if (unreadCount > 0) {
            document.title = `(${unreadCount}) ${originalTitle}`;
        } else {
            document.title = originalTitle;
        }
    }

    // 公开API
    return {
        init: init,
        loadNotifications: loadNotifications,
        markAsRead: markAsRead,
        markAllAsRead: markAllAsRead
    };
})();

// 当DOM加载完成后初始化通知功能
document.addEventListener('DOMContentLoaded', function() {
    // 只有在用户已登录的情况下初始化通知功能
    if (document.getElementById('notification-badge')) {
        TweetAnalyst.notifications.init({
            badgeSelector: 'notification-badge',
            containerSelector: 'notifications-container',
            refreshInterval: 60000 // 1分钟刷新一次
        });
    }
});
