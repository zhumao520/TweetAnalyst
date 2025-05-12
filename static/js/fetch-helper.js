/**
 * 安全的fetch函数，增强错误处理
 * 
 * 这个函数包装了原生fetch，添加了以下功能：
 * 1. 检查响应状态码，非2xx状态码会抛出错误
 * 2. 检查Content-Type是否为application/json
 * 3. 自动解析JSON响应
 * 4. 详细的错误信息
 * 
 * @param {string} url - 请求URL
 * @param {Object} options - fetch选项
 * @returns {Promise} - 返回解析后的JSON数据
 */
function safeFetch(url, options = {}) {
    return fetch(url, options)
        .then(response => {
            // 检查响应是否成功
            if (!response.ok) {
                throw new Error(`服务器返回错误: ${response.status} ${response.statusText}`);
            }
            
            // 检查Content-Type是否为application/json
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                throw new Error(`预期JSON响应，但收到: ${contentType}`);
            }
            
            return response.json();
        });
}

/**
 * 安全的POST请求函数
 * 
 * @param {string} url - 请求URL
 * @param {Object} data - 请求数据，将被转换为JSON
 * @returns {Promise} - 返回解析后的JSON数据
 */
function safePost(url, data = {}) {
    return safeFetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
    });
}

/**
 * 安全的GET请求函数
 * 
 * @param {string} url - 请求URL
 * @returns {Promise} - 返回解析后的JSON数据
 */
function safeGet(url) {
    return safeFetch(url);
}

// 导出函数，使其可以在其他模块中使用
window.safeFetch = safeFetch;
window.safePost = safePost;
window.safeGet = safeGet;
