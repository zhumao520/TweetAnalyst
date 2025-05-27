/**
 * TweetAnalyst 设置管理模块
 * 提供统一的设置管理功能
 */

// 设置管理对象
const SettingsManager = {
    // 配置缓存
    configCache: {},

    // 初始化
    init: function() {
        console.log('初始化设置管理模块');

        // 添加全局错误处理
        window.addEventListener('error', function(event) {
            console.error('全局错误:', event.message, event.filename, event.lineno, event.colno, event.error);
        });

        // 绑定保存按钮事件
        this.bindSaveEvents();

        // 初始化配置缓存
        this.initConfigCache();
    },

    // 初始化配置缓存
    initConfigCache: function() {
        // 从页面中获取配置
        const configElements = document.querySelectorAll('[data-config-key]');
        configElements.forEach(element => {
            const key = element.getAttribute('data-config-key');
            const value = element.value || element.getAttribute('data-config-value') || '';
            this.configCache[key] = value;
        });
    },

    // 绑定保存按钮事件
    bindSaveEvents: function() {
        // 定时任务配置
        const schedulerBtn = document.getElementById('save-scheduler-btn');
        if (schedulerBtn) {
            schedulerBtn.addEventListener('click', () => {
                this.saveSchedulerSettings();
            });
        }

        // 自动回复设置
        const autoReplyBtn = document.getElementById('save-auto-reply-btn');
        if (autoReplyBtn) {
            autoReplyBtn.addEventListener('click', () => {
                this.saveAutoReplySettings();
            });
        }

        // Twitter设置
        const twitterBtn = document.getElementById('save-twitter-btn');
        if (twitterBtn) {
            twitterBtn.addEventListener('click', () => {
                this.saveTwitterSettings();
            });
        }

        // LLM设置已移至AI设置页面

        // 代理设置
        const proxyBtn = document.getElementById('save-proxy-btn');
        if (proxyBtn) {
            proxyBtn.addEventListener('click', () => {
                this.saveProxySettings();
            });
        }

        // 推送设置
        const notificationBtn = document.getElementById('save-notification-btn');
        if (notificationBtn) {
            notificationBtn.addEventListener('click', () => {
                this.saveNotificationSettings();
            });
        }

        // 数据库自动清理配置
        const dbCleanBtn = document.getElementById('save-db-clean-btn');
        if (dbCleanBtn) {
            dbCleanBtn.addEventListener('click', () => {
                this.saveDbCleanSettings();
            });
        }

        // 账号设置
        const accountBtn = document.getElementById('save-account-btn');
        if (accountBtn) {
            accountBtn.addEventListener('click', () => {
                this.saveAccountSettings();
            });
        }

        // 保存所有设置
        const saveAllBtn = document.getElementById('save-all-settings-btn');
        if (saveAllBtn) {
            saveAllBtn.addEventListener('click', () => {
                this.saveAllSettings();
            });
        }

        // AI提供商管理已移至AI设置页面
    },

    // 保存定时任务配置
    saveSchedulerSettings: function() {
        const intervalElement = document.getElementById('scheduler-interval');
        const interval = intervalElement ? intervalElement.value : '';
        const autoFetchEnabledElement = document.getElementById('auto-fetch-enabled');
        const autoFetchEnabled = autoFetchEnabledElement ? autoFetchEnabledElement.checked : false;

        // 时间线任务配置
        const timelineIntervalElement = document.getElementById('timeline-interval');
        const timelineInterval = timelineIntervalElement ? timelineIntervalElement.value : '';
        const timelineFetchEnabledElement = document.getElementById('timeline-fetch-enabled');
        const timelineFetchEnabled = timelineFetchEnabledElement ? timelineFetchEnabledElement.checked : false;

        const resultDiv = document.getElementById('scheduler-result');

        this.showLoading(resultDiv, '正在保存定时任务配置...');

        // 构建配置对象
        const configs = {
            'SCHEDULER_INTERVAL_MINUTES': {
                value: interval,
                description: '账号抓取任务执行间隔（分钟）'
            },
            'AUTO_FETCH_ENABLED': {
                value: autoFetchEnabled ? 'true' : 'false',
                description: '是否启用账号抓取定时任务'
            },
            'TIMELINE_INTERVAL_MINUTES': {
                value: timelineInterval,
                description: '时间线抓取任务执行间隔（分钟）'
            },
            'TIMELINE_FETCH_ENABLED': {
                value: timelineFetchEnabled ? 'true' : 'false',
                description: '是否启用时间线抓取定时任务'
            }
        };

        // 批量保存配置
        this.batchSaveConfigs(configs, resultDiv, '定时任务配置已保存');
    },

    // 保存自动回复设置
    saveAutoReplySettings: function() {
        const enableAutoReplyElement = document.getElementById('enable-auto-reply');
        const enableAutoReply = enableAutoReplyElement ? enableAutoReplyElement.checked : false;
        const autoReplyPromptElement = document.getElementById('auto-reply-prompt');
        const autoReplyPrompt = autoReplyPromptElement ? autoReplyPromptElement.value : '';
        const resultDiv = document.getElementById('auto-reply-result');

        this.showLoading(resultDiv, '正在保存自动回复设置...');

        // 构建配置对象
        const configs = {
            'ENABLE_AUTO_REPLY': {
                value: enableAutoReply ? 'true' : 'false',
                description: '是否启用自动回复'
            }
        };

        if (autoReplyPrompt) {
            configs['AUTO_REPLY_PROMPT'] = {
                value: autoReplyPrompt,
                description: '自动回复提示词模板'
            };
        }

        // 批量保存配置
        this.batchSaveConfigs(configs, resultDiv, '自动回复设置已保存');
    },

    // 保存Twitter设置
    saveTwitterSettings: function() {
        const usernameElement = document.getElementById('twitter-username');
        const username = usernameElement ? usernameElement.value : '';
        const emailElement = document.getElementById('twitter-email');
        const email = emailElement ? emailElement.value : '';
        const passwordElement = document.getElementById('twitter-password');
        const password = passwordElement ? passwordElement.value : '';

        // 获取新的会话字段
        const authToken = document.getElementById('twitter-auth-token')?.value || '';
        const ct0 = document.getElementById('twitter-ct0')?.value || '';
        const csrfToken = document.getElementById('twitter-csrf-token')?.value || '';
        const sessionToken = document.getElementById('twitter-session-token')?.value || '';

        const resultDiv = document.getElementById('twitter-result');

        this.showLoading(resultDiv, '正在保存Twitter设置...');

        // 构建配置对象
        const configs = {};

        // 总是包含用户名配置（即使为空，用于清空）
        configs['TWITTER_USERNAME'] = {
            value: username || '',
            description: 'Twitter用户名'
        };

        // 总是包含邮箱配置（即使为空，用于清空）
        configs['TWITTER_EMAIL'] = {
            value: email || '',
            description: 'Twitter邮箱地址'
        };

        // 只有当密码不是占位符且有值时才更新密码
        if (password && !password.startsWith('******')) {
            configs['TWITTER_PASSWORD'] = {
                value: password,
                is_secret: true,
                description: 'Twitter密码'
            };
        } else if (!password || password.trim() === '') {
            // 如果密码字段为空，明确清空密码
            configs['TWITTER_PASSWORD'] = {
                value: '',
                is_secret: true,
                description: 'Twitter密码'
            };
        }

        // 构建会话JSON数据
        let sessionData = '';
        if (authToken && ct0) {
            const sessionObj = {
                auth_token: authToken,
                ct0: ct0
            };

            // 添加可选字段
            if (csrfToken) sessionObj.csrf_token = csrfToken;
            if (sessionToken) sessionObj.session_token = sessionToken;

            sessionData = JSON.stringify(sessionObj);
        }

        // 总是包含会话数据配置（即使为空，用于清空）
        configs['TWITTER_SESSION'] = {
            value: sessionData,
            is_secret: true,
            description: 'Twitter会话数据'
        };

        // 批量保存配置
        this.batchSaveConfigs(configs, resultDiv, 'Twitter设置已保存');
    },

    // LLM设置已移至AI设置页面

    // 保存代理设置（向后兼容）
    saveProxySettings: function() {
        const proxyElement = document.getElementById('http-proxy');
        const proxy = proxyElement ? proxyElement.value : '';
        const resultDiv = document.getElementById('proxy-result');

        this.showLoading(resultDiv, '正在保存代理设置...');

        // 构建配置对象
        const configs = {
            'HTTP_PROXY': {
                value: proxy,
                description: 'HTTP代理'
            }
        };

        // 批量保存配置
        this.batchSaveConfigs(configs, resultDiv, '代理设置已保存');

        // 如果存在代理管理器，尝试刷新代理列表
        if (typeof ProxyManager !== 'undefined' && ProxyManager.loadProxyList) {
            setTimeout(() => {
                try {
                    ProxyManager.loadProxyList();
                    console.log('已刷新代理列表');
                } catch (e) {
                    console.error('刷新代理列表失败:', e);
                }
            }, 1000);
        }
    },

    // 保存数据库自动清理配置
    saveDbCleanSettings: function() {
        const autoCleanEnabledElement = document.getElementById('db-auto-clean-enabled');
        const autoCleanEnabled = autoCleanEnabledElement ? autoCleanEnabledElement.checked : false;
        const autoCleanTimeElement = document.getElementById('db-auto-clean-time');
        const autoCleanTime = autoCleanTimeElement ? autoCleanTimeElement.value : '';
        const cleanByCountElement = document.getElementById('db-clean-by-count');
        const cleanByCount = cleanByCountElement ? cleanByCountElement.checked : false;
        const maxRecordsElement = document.getElementById('db-max-records');
        const maxRecords = maxRecordsElement ? maxRecordsElement.value : '';
        const retentionDaysElement = document.getElementById('db-retention-days');
        const retentionDays = retentionDaysElement ? retentionDaysElement.value : '';
        const cleanIrrelevantOnly = document.getElementById('db-clean-irrelevant-only')?.checked || false;
        const resultDiv = document.getElementById('db-clean-result');

        if (!resultDiv) {
            // 如果结果div不存在，创建一个
            const formElement = document.getElementById('db-clean-form');
            const newResultDiv = document.createElement('div');
            newResultDiv.id = 'db-clean-result';
            newResultDiv.className = 'alert mt-3';
            formElement.parentNode.insertBefore(newResultDiv, formElement.nextSibling);
            resultDiv = newResultDiv;
        }

        this.showLoading(resultDiv, '正在保存数据库自动清理配置...');

        // 构建配置对象
        const configs = {
            'DB_AUTO_CLEAN_ENABLED': {
                value: autoCleanEnabled ? 'true' : 'false',
                description: '是否启用数据库自动清理'
            },
            'DB_AUTO_CLEAN_TIME': {
                value: autoCleanTime,
                description: '数据库自动清理时间'
            },
            'DB_CLEAN_BY_COUNT': {
                value: cleanByCount ? 'true' : 'false',
                description: '是否基于数量清理'
            },
            'DB_MAX_RECORDS_PER_ACCOUNT': {
                value: maxRecords,
                description: '每个账号保留的最大记录数'
            },
            'DB_RETENTION_DAYS': {
                value: retentionDays,
                description: '数据保留天数'
            }
        };

        // 如果存在清理不相关数据的选项，添加到配置中
        if (document.getElementById('db-clean-irrelevant-only')) {
            configs['DB_CLEAN_IRRELEVANT_ONLY'] = {
                value: cleanIrrelevantOnly ? 'true' : 'false',
                description: '是否只清理不相关数据'
            };
        }

        // 批量保存配置
        this.batchSaveConfigs(configs, resultDiv, '数据库自动清理配置已保存');
    },

    // 批量保存配置
    batchSaveConfigs: function(configs, resultDiv, successMessage) {
        // 发送请求
        fetch('/api/settings/batch', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                configs: configs,
                update_env: true
            }),
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                this.showSuccess(resultDiv, successMessage, data.message);

                // 更新配置缓存
                for (const key in configs) {
                    this.configCache[key] = configs[key].value;
                }
            } else {
                this.showError(resultDiv, '保存失败', data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            this.showError(resultDiv, '请求错误', error.message);
        });
    },

    // 显示加载状态
    showLoading: function(element, message) {
        element.classList.remove('d-none', 'alert-success', 'alert-danger');
        element.classList.add('alert-info');
        element.innerHTML = `<h5><i class="bi bi-hourglass-split text-info"></i> 正在保存...</h5><p>${message}</p><div class="progress mt-2"><div class="progress-bar progress-bar-striped progress-bar-animated" role="progressbar" style="width: 100%"></div></div>`;
    },

    // 显示成功消息
    showSuccess: function(element, title, message) {
        element.classList.remove('d-none', 'alert-danger', 'alert-info');
        element.classList.add('alert-success');
        element.innerHTML = `<h5><i class="bi bi-check-circle-fill text-success"></i> ${title}</h5><p>${message}</p>`;
    },

    // 显示错误消息
    showError: function(element, title, message) {
        element.classList.remove('d-none', 'alert-success', 'alert-info');
        element.classList.add('alert-danger');
        element.innerHTML = `<h5><i class="bi bi-x-circle-fill text-danger"></i> ${title}</h5><p>${message}</p>`;
    },

    // 保存所有设置
    saveAllSettings: function() {
        // 创建全局结果显示区域
        let resultDiv = document.getElementById('global-settings-result');
        if (!resultDiv) {
            resultDiv = document.createElement('div');
            resultDiv.id = 'global-settings-result';
            resultDiv.className = 'alert mt-3';
            document.querySelector('.container').insertBefore(resultDiv, document.querySelector('.nav-tabs'));
        }

        this.showLoading(resultDiv, '正在保存所有设置...');

        // 收集所有配置
        const configs = {};

        // 定时任务配置
        const schedulerIntervalElement = document.getElementById('scheduler-interval');
        const schedulerInterval = schedulerIntervalElement ? schedulerIntervalElement.value : '';
        const autoFetchEnabledElement = document.getElementById('auto-fetch-enabled');
        const autoFetchEnabled = autoFetchEnabledElement ? autoFetchEnabledElement.checked : false;

        // 时间线任务配置
        const timelineIntervalElement = document.getElementById('timeline-interval');
        const timelineInterval = timelineIntervalElement ? timelineIntervalElement.value : '';
        const timelineFetchEnabledElement = document.getElementById('timeline-fetch-enabled');
        const timelineFetchEnabled = timelineFetchEnabledElement ? timelineFetchEnabledElement.checked : false;

        if (schedulerInterval) {
            configs['SCHEDULER_INTERVAL_MINUTES'] = {
                value: schedulerInterval,
                description: '账号抓取任务执行间隔（分钟）'
            };
        }

        configs['AUTO_FETCH_ENABLED'] = {
            value: autoFetchEnabled ? 'true' : 'false',
            description: '是否启用账号抓取定时任务'
        };

        if (timelineInterval) {
            configs['TIMELINE_INTERVAL_MINUTES'] = {
                value: timelineInterval,
                description: '时间线抓取任务执行间隔（分钟）'
            };
        }

        configs['TIMELINE_FETCH_ENABLED'] = {
            value: timelineFetchEnabled ? 'true' : 'false',
            description: '是否启用时间线抓取定时任务'
        };

        // 自动回复设置
        const enableAutoReplyElement = document.getElementById('enable-auto-reply');
        const enableAutoReply = enableAutoReplyElement ? enableAutoReplyElement.checked : false;
        configs['ENABLE_AUTO_REPLY'] = {
            value: enableAutoReply ? 'true' : 'false',
            description: '是否启用自动回复'
        };

        const autoReplyPromptElement = document.getElementById('auto-reply-prompt');
        const autoReplyPrompt = autoReplyPromptElement ? autoReplyPromptElement.value : '';
        if (autoReplyPrompt) {
            configs['AUTO_REPLY_PROMPT'] = {
                value: autoReplyPrompt,
                description: '自动回复提示词模板'
            };
        }

        // Twitter设置
        const twitterUsername = document.getElementById('twitter-username')?.value || '';
        const twitterEmail = document.getElementById('twitter-email')?.value || '';
        // 总是包含用户名配置（即使为空，用于清空）
        configs['TWITTER_USERNAME'] = {
            value: twitterUsername,
            description: 'Twitter用户名'
        };

        // 总是包含邮箱配置（即使为空，用于清空）
        configs['TWITTER_EMAIL'] = {
            value: twitterEmail,
            description: 'Twitter邮箱地址'
        };

        const twitterPassword = document.getElementById('twitter-password')?.value || '';
        // 只有当密码不是占位符且有值时才更新密码
        if (twitterPassword && !twitterPassword.startsWith('******')) {
            configs['TWITTER_PASSWORD'] = {
                value: twitterPassword,
                is_secret: true,
                description: 'Twitter密码'
            };
        } else if (!twitterPassword || twitterPassword.trim() === '') {
            // 如果密码字段为空，明确清空密码
            configs['TWITTER_PASSWORD'] = {
                value: '',
                is_secret: true,
                description: 'Twitter密码'
            };
        }

        // 构建会话JSON数据
        const authToken = document.getElementById('twitter-auth-token')?.value || '';
        const ct0 = document.getElementById('twitter-ct0')?.value || '';
        const csrfToken = document.getElementById('twitter-csrf-token')?.value || '';
        const sessionToken = document.getElementById('twitter-session-token')?.value || '';

        let twitterSessionData = '';
        if (authToken && ct0) {
            const sessionObj = {
                auth_token: authToken,
                ct0: ct0
            };

            // 添加可选字段
            if (csrfToken) sessionObj.csrf_token = csrfToken;
            if (sessionToken) sessionObj.session_token = sessionToken;

            twitterSessionData = JSON.stringify(sessionObj);
        }

        // 总是包含会话数据配置（即使为空，用于清空）
        configs['TWITTER_SESSION'] = {
            value: twitterSessionData,
            is_secret: true,
            description: 'Twitter会话数据'
        };

        // LLM设置已移至AI设置页面

        // 代理设置
        const httpProxyElement = document.getElementById('http-proxy');
        const httpProxy = httpProxyElement ? httpProxyElement.value : '';
        configs['HTTP_PROXY'] = {
            value: httpProxy,
            description: 'HTTP代理'
        };

        // 数据库自动清理配置
        const dbAutoCleanEnabled = document.getElementById('db-auto-clean-enabled');
        if (dbAutoCleanEnabled) {
            configs['DB_AUTO_CLEAN_ENABLED'] = {
                value: dbAutoCleanEnabled.checked ? 'true' : 'false',
                description: '是否启用数据库自动清理'
            };

            const dbAutoCleanTime = document.getElementById('db-auto-clean-time');
            if (dbAutoCleanTime) {
                configs['DB_AUTO_CLEAN_TIME'] = {
                    value: dbAutoCleanTime.value,
                    description: '数据库自动清理时间'
                };
            }

            const dbCleanByCount = document.getElementById('db-clean-by-count');
            if (dbCleanByCount) {
                configs['DB_CLEAN_BY_COUNT'] = {
                    value: dbCleanByCount.checked ? 'true' : 'false',
                    description: '是否基于数量清理'
                };
            }

            const dbMaxRecords = document.getElementById('db-max-records');
            if (dbMaxRecords) {
                configs['DB_MAX_RECORDS_PER_ACCOUNT'] = {
                    value: dbMaxRecords.value,
                    description: '每个账号保留的最大记录数'
                };
            }

            const dbRetentionDays = document.getElementById('db-retention-days');
            if (dbRetentionDays) {
                configs['DB_RETENTION_DAYS'] = {
                    value: dbRetentionDays.value,
                    description: '数据保留天数'
                };
            }

            const dbCleanIrrelevantOnly = document.getElementById('db-clean-irrelevant-only');
            if (dbCleanIrrelevantOnly) {
                configs['DB_CLEAN_IRRELEVANT_ONLY'] = {
                    value: dbCleanIrrelevantOnly.checked ? 'true' : 'false',
                    description: '是否只清理不相关数据'
                };
            }
        }

        // 批量保存配置
        this.batchSaveConfigs(configs, resultDiv, '所有设置已保存');
    },

    // AI提供商相关功能已移至AI设置页面

    // 关闭模态框
    closeModal: function(modalId) {
        console.log(`关闭模态框: ${modalId}`);

        try {
            // 优先使用jQuery方式关闭模态框
            if (typeof $ !== 'undefined') {
                try {
                    $(`#${modalId}`).modal('hide');
                    console.log(`使用jQuery关闭模态框: ${modalId}`);

                    // 确保模态框背景被移除
                    setTimeout(() => {
                        const backdrops = document.querySelectorAll('.modal-backdrop');
                        backdrops.forEach(backdrop => {
                            backdrop.remove();
                        });

                        // 确保body上的modal-open类被移除
                        document.body.classList.remove('modal-open');
                    }, 100);

                    return true;
                } catch (jqError) {
                    console.error(`jQuery关闭模态框失败: ${jqError.message}`);
                    // 继续尝试原生方式
                }
            }

            // 使用原生方式关闭模态框
            const modalEl = document.getElementById(modalId);
            if (modalEl) {
                modalEl.classList.remove('show');
                modalEl.style.display = 'none';
                document.body.classList.remove('modal-open');

                // 移除所有模态框背景
                const backdrops = document.querySelectorAll('.modal-backdrop');
                backdrops.forEach(backdrop => {
                    backdrop.remove();
                });

                console.log(`使用原生方式关闭模态框: ${modalId}`);
                return true;
            } else {
                console.error(`未找到模态框元素: ${modalId}`);
                return false;
            }
        } catch (error) {
            console.error(`关闭模态框错误: ${error.message}`);
            return false;
        }
    },

    // 添加AI提供商
    addAIProvider: function() {
        console.log('添加AI提供商');

        // 如果页面中有showAddProviderModal函数，则使用它
        if (typeof showAddProviderModal === 'function') {
            showAddProviderModal();
            return;
        }

        // 否则使用默认实现
        console.log('使用默认实现显示添加提供商模态框');

        // 首先检查模态框元素是否存在
        const modalEl = document.getElementById('addProviderModal');
        if (!modalEl) {
            console.error('未找到添加提供商模态框元素');
            if (typeof TweetAnalyst !== 'undefined' && TweetAnalyst.toast) {
                TweetAnalyst.toast.showErrorToast('未找到模态框元素。请刷新页面后重试。', '错误');
            } else {
                alert('错误：未找到模态框元素。请刷新页面后重试。');
            }
            return;
        }

        try {
            // 优先使用jQuery方式显示模态框
            if (typeof $ !== 'undefined') {
                try {
                    $('#addProviderModal').modal('show');
                } catch (jqError) {
                    console.error(`jQuery显示模态框失败: ${jqError.message}`);
                    // 回退到原生方式
                    modalEl.classList.add('show');
                    modalEl.style.display = 'block';
                    document.body.classList.add('modal-open');
                }
            } else {
                // 使用原生方式
                modalEl.classList.add('show');
                modalEl.style.display = 'block';
                document.body.classList.add('modal-open');
            }
        } catch (error) {
            console.error(`显示模态框错误: ${error.message}`);
            if (typeof TweetAnalyst !== 'undefined' && TweetAnalyst.toast) {
                TweetAnalyst.toast.showErrorToast(`显示模态框错误: ${error.message}`, '错误');
            } else {
                alert(`显示模态框错误: ${error.message}`);
            }
        }
    },

    saveAccountSettings: function() {
        // 目前未实现账号设置保存逻辑，防止报错
        // 你可以在这里实现具体保存逻辑
        console.log('账号设置保存功能暂未实现');
    }
};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    SettingsManager.init();
});
