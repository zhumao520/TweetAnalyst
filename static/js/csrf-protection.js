/**
 * CSRF保护模块
 * 为所有AJAX请求添加CSRF令牌
 */

// 在全局命名空间中创建TweetAnalyst对象（如果不存在）
if (typeof TweetAnalyst === 'undefined') {
    window.TweetAnalyst = {};
}

// 创建CSRF保护模块
TweetAnalyst.csrfProtection = (function() {
    /**
     * 初始化CSRF保护
     * @param {string} csrfToken - CSRF令牌
     */
    function init(csrfToken) {
        if (!csrfToken) {
            console.error('CSRF令牌不能为空');
            return;
        }
        
        // 保存原始fetch函数
        const originalFetch = window.fetch;
        
        // 重写fetch函数，添加CSRF令牌
        window.fetch = function(url, options = {}) {
            // 如果是POST、PUT、DELETE或PATCH请求，添加CSRF令牌
            if (options.method && ['POST', 'PUT', 'DELETE', 'PATCH'].includes(options.method.toUpperCase())) {
                // 创建新的options对象
                options = Object.assign({}, options);
                
                // 确保headers存在
                options.headers = options.headers || {};
                
                // 如果headers是Headers对象，转换为普通对象
                if (options.headers instanceof Headers) {
                    const headersObj = {};
                    for (const [key, value] of options.headers.entries()) {
                        headersObj[key] = value;
                    }
                    options.headers = headersObj;
                }
                
                // 添加CSRF令牌到headers
                options.headers['X-CSRFToken'] = csrfToken;
            }
            
            // 调用原始fetch函数
            return originalFetch(url, options);
        };
        
        // 保存原始XMLHttpRequest.prototype.open方法
        const originalOpen = XMLHttpRequest.prototype.open;
        
        // 重写XMLHttpRequest.prototype.open方法
        XMLHttpRequest.prototype.open = function(method, url) {
            // 调用原始open方法
            originalOpen.apply(this, arguments);
            
            // 如果是POST、PUT、DELETE或PATCH请求，添加CSRF令牌
            if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method.toUpperCase())) {
                this.setRequestHeader('X-CSRFToken', csrfToken);
            }
        };
        
        console.log('CSRF保护已启用');
    }
    
    // 公开API
    return {
        init: init
    };
})();

// 当DOM加载完成后初始化CSRF保护
document.addEventListener('DOMContentLoaded', function() {
    // 从meta标签获取CSRF令牌
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
    
    if (csrfToken) {
        TweetAnalyst.csrfProtection.init(csrfToken);
    } else {
        console.warn('未找到CSRF令牌，CSRF保护未启用');
    }
});
