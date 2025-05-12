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

        console.log('配置缓存已初始化', this.configCache);
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

        // LLM设置
        const llmBtn = document.getElementById('save-llm-btn');
        if (llmBtn) {
            llmBtn.addEventListener('click', () => {
                this.saveLLMSettings();
            });
        }

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
    },

    // 保存定时任务配置
    saveSchedulerSettings: function() {
        const interval = document.getElementById('scheduler-interval').value;
        const resultDiv = document.getElementById('scheduler-result');

        this.showLoading(resultDiv, '正在保存定时任务配置...');

        // 构建配置对象
        const configs = {
            'SCHEDULER_INTERVAL_MINUTES': {
                value: interval,
                description: '定时任务执行间隔（分钟）'
            }
        };

        // 批量保存配置
        this.batchSaveConfigs(configs, resultDiv, '定时任务配置已保存');
    },

    // 保存自动回复设置
    saveAutoReplySettings: function() {
        const enableAutoReply = document.getElementById('enable-auto-reply').checked;
        const autoReplyPrompt = document.getElementById('auto-reply-prompt').value;
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
        const username = document.getElementById('twitter-username').value;
        const password = document.getElementById('twitter-password').value;
        const session = document.getElementById('twitter-session').value;
        const resultDiv = document.getElementById('twitter-result');

        this.showLoading(resultDiv, '正在保存Twitter设置...');

        // 构建配置对象
        const configs = {};

        if (username) {
            configs['TWITTER_USERNAME'] = {
                value: username,
                description: 'Twitter用户名'
            };
        }

        if (password && !password.startsWith('******')) {
            configs['TWITTER_PASSWORD'] = {
                value: password,
                is_secret: true,
                description: 'Twitter密码'
            };
        }

        if (session && !session.startsWith('******')) {
            configs['TWITTER_SESSION'] = {
                value: session,
                is_secret: true,
                description: 'Twitter会话数据'
            };
        }

        // 批量保存配置
        this.batchSaveConfigs(configs, resultDiv, 'Twitter设置已保存');
    },

    // 保存LLM设置
    saveLLMSettings: function() {
        const apiKey = document.getElementById('llm-api-key').value;
        const apiModel = document.getElementById('llm-api-model').value;
        const apiBase = document.getElementById('llm-api-base').value;
        const resultDiv = document.getElementById('llm-result');

        this.showLoading(resultDiv, '正在保存LLM设置...');

        // 构建配置对象
        const configs = {};

        if (apiKey && !apiKey.startsWith('******')) {
            configs['LLM_API_KEY'] = {
                value: apiKey,
                is_secret: true,
                description: 'LLM API密钥'
            };
        }

        if (apiModel) {
            configs['LLM_API_MODEL'] = {
                value: apiModel,
                description: 'LLM API模型'
            };
        }

        if (apiBase) {
            configs['LLM_API_BASE'] = {
                value: apiBase,
                description: 'LLM API基础URL'
            };
        }

        // 批量保存配置
        this.batchSaveConfigs(configs, resultDiv, 'LLM设置已保存');
    },

    // 保存代理设置
    saveProxySettings: function() {
        const proxy = document.getElementById('http-proxy').value;
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
    },

    // 保存推送设置
    saveNotificationSettings: function() {
        const appriseUrls = document.getElementById('apprise-urls').value;
        const resultDiv = document.getElementById('notification-result');

        this.showLoading(resultDiv, '正在保存推送设置...');

        // 构建配置对象
        const configs = {
            'APPRISE_URLS': {
                value: appriseUrls,
                description: 'Apprise推送URLs'
            }
        };

        // 批量保存配置
        this.batchSaveConfigs(configs, resultDiv, '推送设置已保存');
    },

    // 保存数据库自动清理配置
    saveDbCleanSettings: function() {
        const autoCleanEnabled = document.getElementById('db-auto-clean-enabled').checked;
        const autoCleanTime = document.getElementById('db-auto-clean-time').value;
        const cleanByCount = document.getElementById('db-clean-by-count').checked;
        const maxRecords = document.getElementById('db-max-records').value;
        const retentionDays = document.getElementById('db-retention-days').value;
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
        const schedulerInterval = document.getElementById('scheduler-interval').value;
        if (schedulerInterval) {
            configs['SCHEDULER_INTERVAL_MINUTES'] = {
                value: schedulerInterval,
                description: '定时任务执行间隔（分钟）'
            };
        }

        // 自动回复设置
        const enableAutoReply = document.getElementById('enable-auto-reply').checked;
        configs['ENABLE_AUTO_REPLY'] = {
            value: enableAutoReply ? 'true' : 'false',
            description: '是否启用自动回复'
        };

        const autoReplyPrompt = document.getElementById('auto-reply-prompt').value;
        if (autoReplyPrompt) {
            configs['AUTO_REPLY_PROMPT'] = {
                value: autoReplyPrompt,
                description: '自动回复提示词模板'
            };
        }

        // Twitter设置
        const twitterUsername = document.getElementById('twitter-username').value;
        if (twitterUsername) {
            configs['TWITTER_USERNAME'] = {
                value: twitterUsername,
                description: 'Twitter用户名'
            };
        }

        const twitterPassword = document.getElementById('twitter-password').value;
        if (twitterPassword && !twitterPassword.startsWith('******')) {
            configs['TWITTER_PASSWORD'] = {
                value: twitterPassword,
                is_secret: true,
                description: 'Twitter密码'
            };
        }

        const twitterSession = document.getElementById('twitter-session').value;
        if (twitterSession && !twitterSession.startsWith('******')) {
            configs['TWITTER_SESSION'] = {
                value: twitterSession,
                is_secret: true,
                description: 'Twitter会话数据'
            };
        }

        // LLM设置
        const llmApiKey = document.getElementById('llm-api-key').value;
        if (llmApiKey && !llmApiKey.startsWith('******')) {
            configs['LLM_API_KEY'] = {
                value: llmApiKey,
                is_secret: true,
                description: 'LLM API密钥'
            };
        }

        const llmApiModel = document.getElementById('llm-api-model').value;
        if (llmApiModel) {
            configs['LLM_API_MODEL'] = {
                value: llmApiModel,
                description: 'LLM API模型'
            };
        }

        const llmApiBase = document.getElementById('llm-api-base').value;
        if (llmApiBase) {
            configs['LLM_API_BASE'] = {
                value: llmApiBase,
                description: 'LLM API基础URL'
            };
        }

        // 代理设置
        const httpProxy = document.getElementById('http-proxy').value;
        configs['HTTP_PROXY'] = {
            value: httpProxy,
            description: 'HTTP代理'
        };

        // 推送设置
        const appriseUrls = document.getElementById('apprise-urls').value;
        configs['APPRISE_URLS'] = {
            value: appriseUrls,
            description: 'Apprise推送URLs'
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
    }
};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    SettingsManager.init();
});
