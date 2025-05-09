/**
 * TweetAnalyst UI组件库
 * 提供统一的UI交互组件
 */

// 命名空间
const TweetAnalyst = {
    // 版本信息
    version: '1.0.0',
    
    // 组件库
    components: {},
    
    // 工具函数
    utils: {},
    
    // 初始化
    init: function() {
        // 初始化所有组件
        for (const name in this.components) {
            if (this.components[name].init) {
                this.components[name].init();
            }
        }
        
        console.log(`TweetAnalyst UI组件库 v${this.version} 已初始化`);
    }
};

/**
 * 通知组件
 * 用于显示通知消息
 */
TweetAnalyst.components.notification = {
    // 配置
    config: {
        position: 'top-right',
        duration: 5000,
        maxCount: 5
    },
    
    // 通知计数
    count: 0,
    
    // 初始化
    init: function() {
        // 创建通知容器
        const container = document.createElement('div');
        container.className = 'ta-notification-container ta-notification-' + this.config.position;
        document.body.appendChild(container);
        this.container = container;
    },
    
    // 显示通知
    show: function(options) {
        // 默认选项
        const defaults = {
            type: 'info',
            title: '',
            message: '',
            duration: this.config.duration,
            closable: true
        };
        
        // 合并选项
        const settings = Object.assign({}, defaults, options);
        
        // 创建通知元素
        const notification = document.createElement('div');
        notification.className = 'ta-notification ta-notification-' + settings.type;
        notification.id = 'ta-notification-' + (++this.count);
        
        // 设置内容
        let html = '';
        if (settings.closable) {
            html += '<button type="button" class="ta-notification-close">&times;</button>';
        }
        if (settings.title) {
            html += '<h4 class="ta-notification-title">' + settings.title + '</h4>';
        }
        html += '<div class="ta-notification-message">' + settings.message + '</div>';
        notification.innerHTML = html;
        
        // 添加到容器
        this.container.appendChild(notification);
        
        // 限制最大数量
        const notifications = this.container.querySelectorAll('.ta-notification');
        if (notifications.length > this.config.maxCount) {
            this.container.removeChild(notifications[0]);
        }
        
        // 绑定关闭事件
        if (settings.closable) {
            const closeBtn = notification.querySelector('.ta-notification-close');
            closeBtn.addEventListener('click', () => {
                this.close(notification.id);
            });
        }
        
        // 自动关闭
        if (settings.duration > 0) {
            setTimeout(() => {
                this.close(notification.id);
            }, settings.duration);
        }
        
        // 显示动画
        setTimeout(() => {
            notification.classList.add('ta-notification-show');
        }, 10);
        
        return notification.id;
    },
    
    // 关闭通知
    close: function(id) {
        const notification = document.getElementById(id);
        if (notification) {
            notification.classList.remove('ta-notification-show');
            notification.classList.add('ta-notification-hide');
            
            // 移除元素
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }
    },
    
    // 成功通知
    success: function(message, title = '成功') {
        return this.show({
            type: 'success',
            title: title,
            message: message
        });
    },
    
    // 错误通知
    error: function(message, title = '错误') {
        return this.show({
            type: 'danger',
            title: title,
            message: message,
            duration: 0
        });
    },
    
    // 警告通知
    warning: function(message, title = '警告') {
        return this.show({
            type: 'warning',
            title: title,
            message: message
        });
    },
    
    // 信息通知
    info: function(message, title = '提示') {
        return this.show({
            type: 'info',
            title: title,
            message: message
        });
    }
};

/**
 * 确认对话框组件
 * 用于显示确认对话框
 */
TweetAnalyst.components.confirm = {
    // 显示确认对话框
    show: function(options) {
        // 默认选项
        const defaults = {
            title: '确认',
            message: '确定要执行此操作吗？',
            confirmText: '确定',
            cancelText: '取消',
            confirmClass: 'ta-btn-primary',
            cancelClass: 'ta-btn-secondary',
            onConfirm: null,
            onCancel: null
        };
        
        // 合并选项
        const settings = Object.assign({}, defaults, options);
        
        // 创建对话框元素
        const modal = document.createElement('div');
        modal.className = 'ta-modal';
        modal.innerHTML = `
            <div class="ta-modal-dialog">
                <div class="ta-modal-content">
                    <div class="ta-modal-header">
                        <h5 class="ta-modal-title">${settings.title}</h5>
                        <button type="button" class="ta-modal-close">&times;</button>
                    </div>
                    <div class="ta-modal-body">
                        <p>${settings.message}</p>
                    </div>
                    <div class="ta-modal-footer">
                        <button type="button" class="ta-btn ${settings.cancelClass} ta-modal-cancel">${settings.cancelText}</button>
                        <button type="button" class="ta-btn ${settings.confirmClass} ta-modal-confirm">${settings.confirmText}</button>
                    </div>
                </div>
            </div>
        `;
        
        // 添加到文档
        document.body.appendChild(modal);
        
        // 显示对话框
        setTimeout(() => {
            modal.classList.add('ta-modal-show');
        }, 10);
        
        // 绑定事件
        const closeBtn = modal.querySelector('.ta-modal-close');
        const cancelBtn = modal.querySelector('.ta-modal-cancel');
        const confirmBtn = modal.querySelector('.ta-modal-confirm');
        
        // 关闭函数
        const close = () => {
            modal.classList.remove('ta-modal-show');
            setTimeout(() => {
                document.body.removeChild(modal);
            }, 300);
        };
        
        // 关闭按钮
        closeBtn.addEventListener('click', () => {
            close();
            if (typeof settings.onCancel === 'function') {
                settings.onCancel();
            }
        });
        
        // 取消按钮
        cancelBtn.addEventListener('click', () => {
            close();
            if (typeof settings.onCancel === 'function') {
                settings.onCancel();
            }
        });
        
        // 确认按钮
        confirmBtn.addEventListener('click', () => {
            close();
            if (typeof settings.onConfirm === 'function') {
                settings.onConfirm();
            }
        });
        
        // 点击背景关闭
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                close();
                if (typeof settings.onCancel === 'function') {
                    settings.onCancel();
                }
            }
        });
    }
};

/**
 * 加载器组件
 * 用于显示加载状态
 */
TweetAnalyst.components.loader = {
    // 显示加载器
    show: function(message = '加载中...') {
        // 创建加载器元素
        const loader = document.createElement('div');
        loader.className = 'ta-loader';
        loader.innerHTML = `
            <div class="ta-loader-backdrop"></div>
            <div class="ta-loader-content">
                <div class="ta-loader-spinner"></div>
                <div class="ta-loader-text">${message}</div>
            </div>
        `;
        
        // 添加到文档
        document.body.appendChild(loader);
        
        // 显示加载器
        setTimeout(() => {
            loader.classList.add('ta-loader-show');
        }, 10);
        
        return loader;
    },
    
    // 隐藏加载器
    hide: function(loader) {
        if (loader) {
            loader.classList.remove('ta-loader-show');
            setTimeout(() => {
                if (loader.parentNode) {
                    loader.parentNode.removeChild(loader);
                }
            }, 300);
        } else {
            // 隐藏所有加载器
            const loaders = document.querySelectorAll('.ta-loader');
            loaders.forEach(loader => {
                loader.classList.remove('ta-loader-show');
                setTimeout(() => {
                    if (loader.parentNode) {
                        loader.parentNode.removeChild(loader);
                    }
                }, 300);
            });
        }
    }
};

// 初始化组件库
document.addEventListener('DOMContentLoaded', function() {
    TweetAnalyst.init();
});
