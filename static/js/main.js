/**
 * TweetAnalyst 核心功能模块
 * 提供应用程序的核心功能和工具函数
 */

// 确保TweetAnalyst命名空间存在
if (typeof TweetAnalyst === 'undefined') {
    window.TweetAnalyst = {
        version: '1.0.0',
        components: {},
        utils: {}
    };
}

// 核心工具函数
TweetAnalyst.utils = TweetAnalyst.utils || {};

/**
 * 确认对话框
 * 显示确认对话框，如果用户确认则执行回调函数
 *
 * @param {string} message - 确认消息
 * @param {Function} callback - 确认后执行的回调函数
 * @deprecated 请使用 TweetAnalyst.toast.showConfirmDialog 代替
 */
TweetAnalyst.utils.confirmAction = function(message, callback) {
    console.warn('TweetAnalyst.utils.confirmAction已弃用，请使用TweetAnalyst.toast.showConfirmDialog代替');

    // 检查是否存在toast模块
    if (TweetAnalyst.toast && typeof TweetAnalyst.toast.showConfirmDialog === 'function') {
        // 使用toast模块显示确认对话框
        TweetAnalyst.toast.showConfirmDialog(message, '确认', callback);
    } else {
        // 如果toast模块不存在，使用原生confirm作为备用
        if (confirm(message)) {
            callback();
        }
    }
};

/**
 * 格式化日期时间
 * 将日期字符串格式化为本地日期时间格式
 *
 * @param {string} dateString - 日期字符串
 * @param {Object} options - 格式化选项
 * @returns {string} 格式化后的日期时间字符串
 */
TweetAnalyst.utils.formatDateTime = function(dateString, options = {}) {
    const date = new Date(dateString);

    // 默认选项
    const defaultOptions = {
        dateStyle: 'medium',
        timeStyle: 'medium'
    };

    // 合并选项
    const formatOptions = Object.assign({}, defaultOptions, options);

    try {
        // 使用Intl.DateTimeFormat进行格式化（更现代的方法）
        return new Intl.DateTimeFormat(navigator.language, formatOptions).format(date);
    } catch (error) {
        // 如果出错，回退到简单的toLocaleString方法
        return date.toLocaleString();
    }
};

/**
 * 显示通知
 * 在页面顶部显示通知消息
 *
 * @param {string} message - 通知消息
 * @param {string} type - 通知类型（info, success, warning, danger）
 * @deprecated 请使用 TweetAnalyst.toast.showToast 代替
 */
TweetAnalyst.utils.showNotification = function(message, type = 'info') {
    console.warn('TweetAnalyst.utils.showNotification已弃用，请使用TweetAnalyst.toast.showToast代替');

    // 检查是否存在toast模块
    if (TweetAnalyst.toast && typeof TweetAnalyst.toast.showToast === 'function') {
        // 使用toast模块显示通知
        TweetAnalyst.toast.showToast(message, type);
    } else {
        // 如果toast模块不存在，使用简单的通知作为备用
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        const container = document.querySelector('.container');
        if (container) {
            container.insertBefore(alertDiv, container.firstChild);

            // 5秒后自动关闭
            setTimeout(() => {
                alertDiv.classList.remove('show');
                setTimeout(() => alertDiv.remove(), 150);
            }, 5000);
        }
    }
};

// 为了向后兼容，保留全局函数，但将它们重定向到命名空间中的函数
window.confirmAction = function(message, callback) {
    console.warn('全局函数confirmAction已弃用，请使用TweetAnalyst.utils.confirmAction或TweetAnalyst.toast.showConfirmDialog代替');
    TweetAnalyst.utils.confirmAction(message, callback);
};

window.formatDateTime = function(dateString) {
    console.warn('全局函数formatDateTime已弃用，请使用TweetAnalyst.utils.formatDateTime代替');
    return TweetAnalyst.utils.formatDateTime(dateString);
};

window.showNotification = function(message, type = 'info') {
    console.warn('全局函数showNotification已弃用，请使用TweetAnalyst.utils.showNotification或TweetAnalyst.toast.showToast代替');
    TweetAnalyst.utils.showNotification(message, type);
};
