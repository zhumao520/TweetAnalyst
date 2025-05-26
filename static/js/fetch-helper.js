/**
 * TweetAnalyst前端API工具
 * 提供安全、可靠的API调用功能
 *
 * 包含以下功能：
 * 1. 错误处理和错误分类
 * 2. 自动重试
 * 3. 请求缓存
 * 4. 请求超时控制
 * 5. 统一的通知显示
 */

// 请求缓存
const _requestCache = {};
const _defaultCacheTTL = 60 * 1000; // 默认缓存有效期（毫秒）

// 错误类型（与后端utils/error_types.py保持一致）
const ErrorTypes = {
    NETWORK: 'network',
    TIMEOUT: 'timeout',
    SERVER: 'server',
    CLIENT: 'client',
    AUTH: 'auth',
    PARSE: 'parse',
    UNKNOWN: 'unknown',
    CONNECTION: 'connection',
    RATE_LIMIT: 'rate_limit'
};

// 错误消息模板（与后端保持一致）
const ErrorMessages = {
    [ErrorTypes.NETWORK]: "网络连接错误，请检查您的网络连接",
    [ErrorTypes.TIMEOUT]: "请求超时，服务器响应时间过长",
    [ErrorTypes.SERVER]: "服务器错误，请稍后重试",
    [ErrorTypes.CLIENT]: "请求错误，请检查请求参数",
    [ErrorTypes.AUTH]: "认证失败，请重新登录",
    [ErrorTypes.PARSE]: "无法解析服务器响应",
    [ErrorTypes.UNKNOWN]: "未知错误",
    [ErrorTypes.CONNECTION]: "连接错误，无法连接到服务器",
    [ErrorTypes.RATE_LIMIT]: "请求过于频繁，请稍后再试"
};

// 可重试的错误类型
const RetryableErrorTypes = new Set([
    ErrorTypes.NETWORK,
    ErrorTypes.TIMEOUT,
    ErrorTypes.SERVER,
    ErrorTypes.CONNECTION,
    ErrorTypes.RATE_LIMIT
]);

/**
 * 生成缓存键
 *
 * @param {string} url - 请求URL
 * @param {Object} options - 请求选项
 * @returns {string} - 缓存键
 */
function generateCacheKey(url, options = {}) {
    const method = options.method || 'GET';
    const body = options.body || '';
    return `${method}:${url}:${body}`;
}

/**
 * 根据HTTP状态码获取错误类型
 *
 * @param {number} statusCode - HTTP状态码
 * @returns {string} - 错误类型
 */
function getErrorTypeFromStatusCode(statusCode) {
    if (statusCode >= 400 && statusCode < 500) {
        if (statusCode === 401 || statusCode === 403) {
            return ErrorTypes.AUTH;
        } else if (statusCode === 429) {
            return ErrorTypes.RATE_LIMIT;
        } else {
            return ErrorTypes.CLIENT;
        }
    } else if (statusCode >= 500 && statusCode < 600) {
        if (statusCode === 504) {
            return ErrorTypes.TIMEOUT;
        } else {
            return ErrorTypes.SERVER;
        }
    } else {
        return ErrorTypes.UNKNOWN;
    }
}

/**
 * 获取错误消息
 *
 * @param {string} errorType - 错误类型
 * @param {number} statusCode - HTTP状态码
 * @param {string} customMessage - 自定义消息
 * @returns {string} - 错误消息
 */
function getErrorMessage(errorType, statusCode = null, customMessage = null) {
    if (customMessage) {
        return customMessage;
    }

    const baseMessage = ErrorMessages[errorType] || ErrorMessages[ErrorTypes.UNKNOWN];

    if (statusCode) {
        return `${baseMessage} (状态码: ${statusCode})`;
    }

    return baseMessage;
}

/**
 * 分类错误（与后端utils/error_types.py保持一致）
 *
 * @param {Error} error - 错误对象
 * @param {Response} response - 响应对象
 * @returns {Object} - 分类后的错误信息
 */
function classifyError(error, response) {
    let errorType = ErrorTypes.UNKNOWN;
    let statusCode = response ? response.status : null;

    // 检查错误名称和消息
    const errorMessage = error.message ? error.message.toLowerCase() : '';

    // 网络错误
    if (error.name === 'TypeError' && (errorMessage.includes('网络') || errorMessage.includes('network') || errorMessage.includes('fetch'))) {
        errorType = ErrorTypes.NETWORK;
    }
    // 超时错误
    else if (error.name === 'TimeoutError' || error.name === 'AbortError' || errorMessage.includes('timeout')) {
        errorType = ErrorTypes.TIMEOUT;
    }
    // 连接错误
    else if (errorMessage.includes('connection') || errorMessage.includes('连接')) {
        errorType = ErrorTypes.CONNECTION;
    }
    // 解析错误
    else if (error.name === 'SyntaxError' && errorMessage.includes('json')) {
        errorType = ErrorTypes.PARSE;
    }
    // 如果有响应对象，根据状态码分类
    else if (response && statusCode) {
        errorType = getErrorTypeFromStatusCode(statusCode);
    }

    // 构建错误信息对象
    const errorInfo = {
        type: errorType,
        message: getErrorMessage(errorType, statusCode, error.message),
        status: statusCode,
        retryable: RetryableErrorTypes.has(errorType),
        original: error
    };

    return errorInfo;
}

/**
 * 显示错误通知
 *
 * @param {Object} errorInfo - 错误信息
 */
function showErrorNotification(errorInfo) {
    // 检查是否存在Toast通知模块
    if (typeof TweetAnalyst !== 'undefined' && TweetAnalyst.toast) {
        // 根据错误类型设置标题
        let title = '错误';

        switch (errorInfo.type) {
            case ErrorTypes.NETWORK:
                title = '网络错误';
                break;
            case ErrorTypes.TIMEOUT:
                title = '请求超时';
                break;
            case ErrorTypes.SERVER:
                title = '服务器错误';
                break;
            case ErrorTypes.CLIENT:
                title = '请求错误';
                break;
            case ErrorTypes.AUTH:
                title = '认证错误';
                break;
            case ErrorTypes.PARSE:
                title = '解析错误';
                break;
        }

        // 显示Toast通知
        TweetAnalyst.toast.showErrorToast(errorInfo.message, title);
    } else if (typeof showNotification === 'function') {
        // 兼容旧的通知函数
        showNotification(errorInfo.message, 'danger', errorInfo.type);
    } else {
        // 如果没有通知函数，使用console.error
        console.error(`${errorInfo.type.toUpperCase()} ERROR:`, errorInfo.message);
    }
}

/**
 * 安全的fetch函数，增强错误处理
 *
 * 这个函数包装了原生fetch，添加了以下功能：
 * 1. 检查响应状态码，非2xx状态码会抛出错误
 * 2. 检查Content-Type是否为application/json
 * 3. 自动解析JSON响应
 * 4. 详细的错误信息
 * 5. 自动重试
 * 6. 请求缓存
 * 7. 请求超时控制
 *
 * @param {string} url - 请求URL
 * @param {Object} options - fetch选项
 * @param {Object} config - 额外配置选项
 * @param {boolean} config.useCache - 是否使用缓存
 * @param {number} config.cacheTTL - 缓存有效期（毫秒）
 * @param {number} config.timeout - 超时时间（毫秒）
 * @param {number} config.retries - 重试次数
 * @param {number} config.retryDelay - 重试延迟（毫秒）
 * @param {boolean} config.showErrors - 是否显示错误通知
 * @returns {Promise} - 返回解析后的JSON数据
 */
function safeFetch(url, options = {}, config = {}) {
    // 默认配置
    const {
        useCache = false,
        cacheTTL = _defaultCacheTTL,
        timeout = 30000,
        retries = 1,
        retryDelay = 1000,
        showErrors = true
    } = config;

    // 如果使用缓存且是GET请求，检查缓存
    if (useCache && (!options.method || options.method === 'GET')) {
        const cacheKey = generateCacheKey(url, options);
        const cachedResponse = _requestCache[cacheKey];

        if (cachedResponse) {
            // 检查缓存是否过期
            if (Date.now() - cachedResponse.timestamp < cacheTTL) {
                console.debug(`[API] 使用缓存的响应: ${url}`);
                return Promise.resolve(cachedResponse.data);
            } else {
                // 缓存过期，从缓存中删除
                delete _requestCache[cacheKey];
            }
        }
    }

    // 创建AbortController用于超时控制
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    // 合并选项
    const fetchOptions = {
        ...options,
        signal: controller.signal
    };

    // 执行请求，支持重试
    let attempt = 0;

    function attemptFetch() {
        return fetch(url, fetchOptions)
            .then(response => {
                // 清除超时计时器
                clearTimeout(timeoutId);

                // 检查响应是否成功
                if (!response.ok) {
                    // 创建错误对象
                    const error = new Error(`服务器返回错误: ${response.status} ${response.statusText}`);
                    error.response = response;
                    throw error;
                }

                // 检查Content-Type是否为application/json
                const contentType = response.headers.get('content-type');
                if (!contentType || !contentType.includes('application/json')) {
                    const error = new Error(`预期JSON响应，但收到: ${contentType}`);
                    error.response = response;
                    throw error;
                }

                return response.json();
            })
            .then(data => {
                // 如果使用缓存且是GET请求，缓存响应
                if (useCache && (!options.method || options.method === 'GET')) {
                    const cacheKey = generateCacheKey(url, options);
                    _requestCache[cacheKey] = {
                        data: data,
                        timestamp: Date.now()
                    };
                }

                return data;
            })
            .catch(error => {
                // 清除超时计时器
                clearTimeout(timeoutId);

                // 如果是AbortError，说明是超时
                if (error.name === 'AbortError') {
                    throw new Error('请求超时');
                }

                // 分类错误
                const errorInfo = classifyError(error, error.response);

                // 如果还有重试次数，且错误类型适合重试
                if (attempt < retries && errorInfo.retryable) {
                    // 增加尝试次数
                    attempt++;

                    // 计算重试延迟
                    const delay = retryDelay * attempt;

                    console.warn(`[API] 请求失败，将在 ${delay}ms 后重试 (${attempt}/${retries}): ${errorInfo.message}`);

                    // 延迟后重试
                    return new Promise(resolve => setTimeout(resolve, delay))
                        .then(attemptFetch);
                }

                // 如果配置了显示错误，且已经没有重试机会
                if (showErrors && attempt >= retries) {
                    showErrorNotification(errorInfo);
                }

                // 重新抛出错误
                throw error;
            });
    }

    return attemptFetch();
}

/**
 * 安全的POST请求函数
 *
 * @param {string} url - 请求URL
 * @param {Object} data - 请求数据，将被转换为JSON
 * @param {Object} config - 额外配置选项
 * @returns {Promise} - 返回解析后的JSON数据
 */
function safePost(url, data = {}, config = {}) {
    return safeFetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
    }, config);
}

/**
 * 安全的GET请求函数
 *
 * @param {string} url - 请求URL
 * @param {Object} config - 额外配置选项
 * @returns {Promise} - 返回解析后的JSON数据
 */
function safeGet(url, config = {}) {
    return safeFetch(url, {}, config);
}

/**
 * 清除请求缓存
 *
 * @param {string} urlPattern - URL模式，如果提供，只清除匹配的缓存
 */
function clearRequestCache(urlPattern) {
    if (urlPattern) {
        // 只清除匹配的缓存
        Object.keys(_requestCache).forEach(key => {
            if (key.includes(urlPattern)) {
                delete _requestCache[key];
            }
        });
        console.debug(`[API] 已清除匹配 "${urlPattern}" 的缓存`);
    } else {
        // 清除所有缓存
        Object.keys(_requestCache).forEach(key => {
            delete _requestCache[key];
        });
        console.debug('[API] 已清除所有缓存');
    }
}

// 导出函数，使其可以在其他模块中使用
window.safeFetch = safeFetch;
window.safePost = safePost;
window.safeGet = safeGet;
window.clearRequestCache = clearRequestCache;
