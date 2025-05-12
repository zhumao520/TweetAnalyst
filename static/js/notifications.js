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
                    updateNotifications(data.data);
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
     */
    function updateNotifications(notifications) {
        // 清空容器
        notificationsContainer.innerHTML = '';

        // 添加标题
        const header = document.createElement('li');
        header.innerHTML = '<h6 class="dropdown-header">通知</h6>';
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

        // 添加通知项
        notifications.forEach(notification => {
            // 检查是否已读
            const isRead = readNotifications.includes(notification.id);
            if (!isRead) {
                unreadCount++;
            }

            // 创建通知项
            const item = document.createElement('li');
            const notificationTime = new Date(notification.time);
            const timeString = notificationTime.toLocaleString('zh-CN', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });

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

        // 更新未读数量徽章
        const countElement = notificationBadge.querySelector('.notification-count');
        if (countElement) {
            countElement.textContent = unreadCount > 99 ? '99+' : unreadCount;
        } else {
            notificationBadge.textContent = unreadCount > 99 ? '99+' : unreadCount;
        }

        if (unreadCount > 0) {
            notificationBadge.classList.remove('d-none');
        } else {
            notificationBadge.classList.add('d-none');
        }

        // 更新页面标题中的通知数量
        updatePageTitle(unreadCount);
    }

    /**
     * 标记单个通知为已读
     * @param {string} id - 通知ID
     */
    function markAsRead(id) {
        if (!readNotifications.includes(id)) {
            readNotifications.push(id);
            localStorage.setItem('readNotifications', JSON.stringify(readNotifications));

            // 重新加载通知以更新未读数量
            loadNotifications();
        }
    }

    /**
     * 标记所有通知为已读
     * @param {Array} notifications - 通知数据数组
     */
    function markAllAsRead(notifications) {
        notifications.forEach(notification => {
            if (!readNotifications.includes(notification.id)) {
                readNotifications.push(notification.id);
            }
        });
        localStorage.setItem('readNotifications', JSON.stringify(readNotifications));

        // 更新UI
        document.querySelectorAll('#notifications-container .dropdown-item').forEach(item => {
            item.classList.remove('fw-bold');
            item.classList.add('text-muted');
        });

        notificationBadge.classList.add('d-none');

        // 更新页面标题
        updatePageTitle(0);
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
