/**
 * TweetAnalyst Toast通知模块
 * 提供统一的Toast通知显示功能
 */

// 在全局命名空间中创建TweetAnalyst对象（如果不存在）
if (typeof TweetAnalyst === 'undefined') {
    window.TweetAnalyst = {};
}

// 创建Toast通知模块
TweetAnalyst.toast = (function() {
    // 通知类型
    const NotificationTypes = {
        SUCCESS: 'success',
        INFO: 'info',
        WARNING: 'warning',
        ERROR: 'danger'
    };

    // 通知容器ID
    const TOAST_CONTAINER_ID = 'toast-notification-container';

    // 通知计数器
    let notificationCounter = 0;

    /**
     * 确保通知容器存在
     *
     * @returns {HTMLElement} 通知容器元素
     */
    function ensureToastContainer() {
        let container = document.getElementById(TOAST_CONTAINER_ID);

        if (!container) {
            // 创建通知容器
            container = document.createElement('div');
            container.id = TOAST_CONTAINER_ID;
            container.className = 'toast-container position-fixed top-0 end-0 p-3';
            container.style.zIndex = '1080';

            // 添加到文档
            document.body.appendChild(container);
        }

        return container;
    }

    /**
     * 显示Toast通知
     *
     * @param {string} message - 通知消息
     * @param {string} type - 通知类型，可选值：success, info, warning, danger
     * @param {string} title - 通知标题
     * @param {number} duration - 通知显示时间（毫秒），0表示不自动关闭
     * @returns {string} 通知ID
     */
    function showToast(message, type = NotificationTypes.INFO, title = '', duration = 5000) {
        // 确保通知容器存在
        const container = ensureToastContainer();

        // 生成唯一ID
        const id = `toast-${Date.now()}-${notificationCounter++}`;

        // 创建Toast元素
        const toastElement = document.createElement('div');
        toastElement.id = id;
        toastElement.className = `toast align-items-center border-0 bg-${type}`;
        toastElement.role = 'alert';
        toastElement.setAttribute('aria-live', 'assertive');
        toastElement.setAttribute('aria-atomic', 'true');

        // 创建Toast内容
        let toastContent = '';

        // 如果有标题，使用标题和消息的组合
        if (title) {
            toastContent = `
                <div class="d-flex">
                    <div class="toast-body">
                        <strong>${title}</strong>: ${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
            `;
        } else {
            // 否则只使用消息
            toastContent = `
                <div class="d-flex">
                    <div class="toast-body">
                        ${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
            `;
        }

        // 设置内容
        toastElement.innerHTML = toastContent;

        // 添加到容器
        container.appendChild(toastElement);

        // 创建Bootstrap Toast对象
        const toast = new bootstrap.Toast(toastElement, {
            autohide: duration > 0,
            delay: duration
        });

        // 显示Toast
        toast.show();

        // 当Toast隐藏时移除元素
        toastElement.addEventListener('hidden.bs.toast', function() {
            toastElement.remove();
        });

        return id;
    }

    /**
     * 显示成功通知
     *
     * @param {string} message - 通知消息
     * @param {string} title - 通知标题
     * @param {number} duration - 通知显示时间（毫秒）
     * @returns {string} 通知ID
     */
    function showSuccessToast(message, title = '成功', duration = 5000) {
        return showToast(message, NotificationTypes.SUCCESS, title, duration);
    }

    /**
     * 显示信息通知
     *
     * @param {string} message - 通知消息
     * @param {string} title - 通知标题
     * @param {number} duration - 通知显示时间（毫秒）
     * @returns {string} 通知ID
     */
    function showInfoToast(message, title = '信息', duration = 5000) {
        return showToast(message, NotificationTypes.INFO, title, duration);
    }

    /**
     * 显示警告通知
     *
     * @param {string} message - 通知消息
     * @param {string} title - 通知标题
     * @param {number} duration - 通知显示时间（毫秒）
     * @returns {string} 通知ID
     */
    function showWarningToast(message, title = '警告', duration = 5000) {
        return showToast(message, NotificationTypes.WARNING, title, duration);
    }

    /**
     * 显示错误通知
     *
     * @param {string} message - 通知消息
     * @param {string} title - 通知标题
     * @param {number} duration - 通知显示时间（毫秒）
     * @returns {string} 通知ID
     */
    function showErrorToast(message, title = '错误', duration = 5000) {
        return showToast(message, NotificationTypes.ERROR, title, duration);
    }

    /**
     * 显示确认对话框
     *
     * @param {string} message - 对话框消息
     * @param {string} title - 对话框标题
     * @param {Function} onConfirm - 确认回调函数
     * @param {Function} onCancel - 取消回调函数
     */
    function showConfirmDialog(message, title = '确认', onConfirm = null, onCancel = null) {
        // 检查是否支持Bootstrap模态框
        if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
            // 创建模态框
            const modalId = `confirm-modal-${Date.now()}`;
            const modalHtml = `
                <div class="modal fade modal-stable" id="${modalId}" tabindex="-1" aria-labelledby="${modalId}-label" aria-hidden="true" data-bs-backdrop="static">
                    <div class="modal-dialog modal-dialog-centered">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title" id="${modalId}-label">${title}</h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                            </div>
                            <div class="modal-body">
                                ${message}
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                                <button type="button" class="btn btn-primary" id="${modalId}-confirm">确认</button>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            // 添加到文档
            const modalContainer = document.createElement('div');
            modalContainer.innerHTML = modalHtml;
            document.body.appendChild(modalContainer);

            // 获取模态框元素
            const modalElement = document.getElementById(modalId);

            // 创建模态框对象
            const modal = new bootstrap.Modal(modalElement);

            // 绑定确认按钮事件
            const confirmButton = document.getElementById(`${modalId}-confirm`);
            confirmButton.addEventListener('click', () => {
                modal.hide();
                if (onConfirm) {
                    onConfirm();
                }
            });

            // 绑定取消事件
            modalElement.addEventListener('hidden.bs.modal', () => {
                if (!confirmButton.clicked && onCancel) {
                    onCancel();
                }

                // 立即移除模态框，避免闪烁
                modalContainer.remove();
            });

            // 标记确认按钮点击状态
            confirmButton.addEventListener('click', () => {
                confirmButton.clicked = true;
            });

            // 显示模态框
            modal.show();
        } else {
            // 如果不支持Bootstrap模态框，使用原生confirm
            if (confirm(message)) {
                if (onConfirm) {
                    onConfirm();
                }
            } else {
                if (onCancel) {
                    onCancel();
                }
            }
        }
    }

    // 公开API
    return {
        showToast: showToast,
        showSuccessToast: showSuccessToast,
        showInfoToast: showInfoToast,
        showWarningToast: showWarningToast,
        showErrorToast: showErrorToast,
        showConfirmDialog: showConfirmDialog
    };
})();

// 为了向后兼容，添加全局函数
window.showToast = function(title, message, type) {
    return TweetAnalyst.toast.showToast(message, type, title);
};

window.showConfirmDialog = function(message, title, onConfirm, onCancel) {
    return TweetAnalyst.toast.showConfirmDialog(message, title, onConfirm, onCancel);
};
