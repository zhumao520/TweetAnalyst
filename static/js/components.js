/**
 * TweetAnalyst UI组件库
 * 提供统一的UI交互组件
 * 社交媒体监控与分析助手
 *
 * @version 1.1.0
 * @author TweetAnalyst Team
 */

// 命名空间
// 检查是否已经存在TweetAnalyst对象，避免覆盖
if (typeof TweetAnalyst === 'undefined') {
    window.TweetAnalyst = {
        // 版本信息
        version: '1.1.0',

        // 组件库
        components: {},

        // 工具函数
        utils: {},

        // 配置
        config: {
            // 默认动画持续时间（毫秒）
            animationDuration: 300,

            // 默认主题
            theme: 'light',

            // 调试模式
            debug: false
        },

        // 初始化
        init: function(options = {}) {
            // 合并配置
            this.config = Object.assign({}, this.config, options);

            // 初始化所有组件
            for (const name in this.components) {
                if (this.components[name].init) {
                    try {
                        this.components[name].init();
                    } catch (error) {
                        console.error(`初始化组件 ${name} 时出错:`, error);
                    }
                }
            }

            // 检测主题
            this.detectTheme();

            // 输出调试信息
            if (this.config.debug) {
                console.log(`TweetAnalyst UI组件库 v${this.version} 已初始化，配置:`, this.config);
            } else {
                console.log(`TweetAnalyst UI组件库 v${this.version} 已初始化`);
            }
        },

        // 检测主题
        detectTheme: function() {
            // 检查是否有data-theme属性
            const htmlElement = document.documentElement;
            const dataTheme = htmlElement.getAttribute('data-theme');

            if (dataTheme) {
                this.config.theme = dataTheme;
            } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
                // 检查系统主题
                this.config.theme = 'dark';
            }

            // 设置主题
            htmlElement.setAttribute('data-theme', this.config.theme);

            if (this.config.debug) {
                console.log(`当前主题: ${this.config.theme}`);
            }
        }
    };
} else {
    // 如果已经存在，确保components和utils对象存在
    if (!TweetAnalyst.components) TweetAnalyst.components = {};
    if (!TweetAnalyst.utils) TweetAnalyst.utils = {};
    if (!TweetAnalyst.config) {
        TweetAnalyst.config = {
            animationDuration: 300,
            theme: 'light',
            debug: false
        };
    }

    // 如果没有init方法，添加一个
    if (!TweetAnalyst.init) {
        TweetAnalyst.init = function(options = {}) {
            // 合并配置
            this.config = Object.assign({}, this.config, options);

            // 初始化所有组件
            for (const name in this.components) {
                if (this.components[name].init) {
                    try {
                        this.components[name].init();
                    } catch (error) {
                        console.error(`初始化组件 ${name} 时出错:`, error);
                    }
                }
            }

            // 检测主题
            if (typeof this.detectTheme === 'function') {
                this.detectTheme();
            }

            // 输出调试信息
            if (this.config.debug) {
                console.log(`TweetAnalyst UI组件库 v${this.version} 已初始化，配置:`, this.config);
            } else {
                console.log(`TweetAnalyst UI组件库 v${this.version} 已初始化`);
            }
        };
    }

    // 如果没有detectTheme方法，添加一个
    if (!TweetAnalyst.detectTheme) {
        TweetAnalyst.detectTheme = function() {
            // 检查是否有data-theme属性
            const htmlElement = document.documentElement;
            const dataTheme = htmlElement.getAttribute('data-theme');

            if (dataTheme) {
                this.config.theme = dataTheme;
            } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
                // 检查系统主题
                this.config.theme = 'dark';
            }

            // 设置主题
            htmlElement.setAttribute('data-theme', this.config.theme);

            if (this.config.debug) {
                console.log(`当前主题: ${this.config.theme}`);
            }
        };
    }
}

/**
 * 通知组件
 * 用于显示通知消息
 *
 * 注意：此组件已弃用，请使用TweetAnalyst.toast模块
 * 为了向后兼容，此组件现在使用TweetAnalyst.toast模块实现
 */
TweetAnalyst.components.notification = {
    // 配置
    config: {
        position: 'top-right',
        duration: 5000,
        maxCount: 5
    },

    // 初始化
    init: function() {
        console.warn('TweetAnalyst.components.notification已弃用，请使用TweetAnalyst.toast模块');
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

        // 检查是否存在toast模块
        if (TweetAnalyst.toast && typeof TweetAnalyst.toast.showToast === 'function') {
            // 使用toast模块显示通知
            return TweetAnalyst.toast.showToast(
                settings.message,
                settings.type,
                settings.title,
                settings.duration
            );
        } else {
            // 如果toast模块不存在，使用alert作为备用
            alert(`${settings.title ? settings.title + ': ' : ''}${settings.message}`);
            return null;
        }
    },

    // 关闭通知（为了兼容性保留，但不再需要）
    close: function(id) {
        // 不需要实现，toast模块会自动处理
    },

    // 成功通知
    success: function(message, title = '成功') {
        if (TweetAnalyst.toast && typeof TweetAnalyst.toast.showSuccessToast === 'function') {
            return TweetAnalyst.toast.showSuccessToast(message, title);
        } else {
            return this.show({
                type: 'success',
                title: title,
                message: message
            });
        }
    },

    // 错误通知
    error: function(message, title = '错误') {
        if (TweetAnalyst.toast && typeof TweetAnalyst.toast.showErrorToast === 'function') {
            return TweetAnalyst.toast.showErrorToast(message, title, 0);
        } else {
            return this.show({
                type: 'danger',
                title: title,
                message: message,
                duration: 0
            });
        }
    },

    // 警告通知
    warning: function(message, title = '警告') {
        if (TweetAnalyst.toast && typeof TweetAnalyst.toast.showWarningToast === 'function') {
            return TweetAnalyst.toast.showWarningToast(message, title);
        } else {
            return this.show({
                type: 'warning',
                title: title,
                message: message
            });
        }
    },

    // 信息通知
    info: function(message, title = '提示') {
        if (TweetAnalyst.toast && typeof TweetAnalyst.toast.showInfoToast === 'function') {
            return TweetAnalyst.toast.showInfoToast(message, title);
        } else {
            return this.show({
                type: 'info',
                title: title,
                message: message
            });
        }
    }
};

/**
 * 确认对话框组件
 * 用于显示确认对话框
 *
 * 注意：此组件已弃用，请使用TweetAnalyst.toast.showConfirmDialog
 * 为了向后兼容，此组件现在使用TweetAnalyst.toast模块实现
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

        console.warn('TweetAnalyst.components.confirm已弃用，请使用TweetAnalyst.toast.showConfirmDialog');

        // 检查是否存在toast模块
        if (TweetAnalyst.toast && typeof TweetAnalyst.toast.showConfirmDialog === 'function') {
            // 使用toast模块显示确认对话框
            TweetAnalyst.toast.showConfirmDialog(
                settings.message,
                settings.title,
                settings.onConfirm,
                settings.onCancel
            );
        } else {
            // 如果toast模块不存在，使用原生confirm作为备用
            if (confirm(`${settings.title}: ${settings.message}`)) {
                if (typeof settings.onConfirm === 'function') {
                    settings.onConfirm();
                }
            } else {
                if (typeof settings.onCancel === 'function') {
                    settings.onCancel();
                }
            }
        }
    }
};

/**
 * 加载器组件
 * 用于显示加载状态
 */
TweetAnalyst.components.loader = {
    // 显示加载器
    show: function(message = '加载中...') {
        // 检查是否已经存在加载器
        const existingLoader = document.querySelector('.ta-loader');
        if (existingLoader) {
            // 更新现有加载器的消息
            const textElement = existingLoader.querySelector('.ta-loader-text');
            if (textElement) {
                textElement.textContent = message;
            }
            return existingLoader;
        }

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

/**
 * 表格组件
 * 用于创建和管理动态表格
 */
TweetAnalyst.components.dataTable = {
    // 表格实例
    instances: {},

    // 配置
    config: {
        pageSize: 10,
        pageSizeOptions: [5, 10, 25, 50, 100],
        showPagination: true,
        showSearch: true,
        showInfo: true,
        language: {
            search: '搜索:',
            info: '显示 _START_ 到 _END_ 条，共 _TOTAL_ 条',
            infoEmpty: '没有数据',
            infoFiltered: '(从 _MAX_ 条数据中过滤)',
            lengthMenu: '每页显示 _MENU_ 条',
            zeroRecords: '没有找到匹配的数据',
            paginate: {
                first: '首页',
                last: '末页',
                next: '下一页',
                previous: '上一页'
            }
        }
    },

    // 初始化
    init: function() {
        // 查找所有带有data-table属性的表格
        const tables = document.querySelectorAll('table[data-table]');

        // 初始化每个表格
        tables.forEach(table => {
            const id = table.id || 'table-' + Math.random().toString(36).substr(2, 9);
            this.create(id, table);
        });
    },

    /**
     * 创建表格
     * @param {string} id - 表格ID
     * @param {HTMLElement|string} element - 表格元素或选择器
     * @param {Object} options - 配置选项
     * @returns {Object} 表格实例
     */
    create: function(id, element, options = {}) {
        // 获取表格元素
        const table = typeof element === 'string' ? document.querySelector(element) : element;

        if (!table) {
            console.error(`表格元素不存在: ${element}`);
            return null;
        }

        // 确保表格有ID
        if (!table.id) {
            table.id = id;
        }

        // 合并配置
        const config = Object.assign({}, this.config, options);

        // 创建表格实例
        const instance = {
            id: id,
            element: table,
            config: config,
            data: [],
            filteredData: [],
            currentPage: 1,
            totalPages: 1,
            searchTerm: '',

            // 初始化表格
            init: function() {
                // 添加表格类
                this.element.classList.add('ta-table');

                // 提取表格数据
                this.extractData();

                // 创建表格控件
                this.createControls();

                // 渲染表格
                this.render();

                return this;
            },

            // 提取表格数据
            extractData: function() {
                // 获取表头
                const headers = Array.from(this.element.querySelectorAll('thead th')).map(th => {
                    return {
                        text: th.textContent.trim(),
                        sortable: th.getAttribute('data-sortable') !== 'false',
                        searchable: th.getAttribute('data-searchable') !== 'false',
                        width: th.getAttribute('data-width') || ''
                    };
                });

                // 获取数据行
                const rows = Array.from(this.element.querySelectorAll('tbody tr')).map(tr => {
                    return Array.from(tr.querySelectorAll('td')).map(td => td.innerHTML);
                });

                // 存储数据
                this.data = {
                    headers: headers,
                    rows: rows
                };

                // 初始化过滤后的数据
                this.filteredData = Object.assign({}, this.data);

                // 计算总页数
                this.totalPages = Math.ceil(this.filteredData.rows.length / this.config.pageSize);
            },

            // 创建表格控件
            createControls: function() {
                // 创建控件容器
                const controlsContainer = document.createElement('div');
                controlsContainer.className = 'ta-table-controls';

                // 创建顶部控件
                const topControls = document.createElement('div');
                topControls.className = 'ta-table-controls-top';

                // 创建长度选择器
                if (this.config.showPagination) {
                    const lengthSelector = document.createElement('div');
                    lengthSelector.className = 'ta-table-length';

                    const lengthLabel = document.createElement('label');
                    lengthLabel.textContent = '每页显示: ';

                    const lengthSelect = document.createElement('select');
                    lengthSelect.className = 'ta-table-length-select';

                    this.config.pageSizeOptions.forEach(size => {
                        const option = document.createElement('option');
                        option.value = size;
                        option.textContent = size;
                        if (size === this.config.pageSize) {
                            option.selected = true;
                        }
                        lengthSelect.appendChild(option);
                    });

                    lengthSelect.addEventListener('change', () => {
                        this.config.pageSize = parseInt(lengthSelect.value);
                        this.currentPage = 1;
                        this.totalPages = Math.ceil(this.filteredData.rows.length / this.config.pageSize);
                        this.render();
                    });

                    lengthLabel.appendChild(lengthSelect);
                    lengthSelector.appendChild(lengthLabel);
                    topControls.appendChild(lengthSelector);
                }

                // 创建搜索框
                if (this.config.showSearch) {
                    const searchContainer = document.createElement('div');
                    searchContainer.className = 'ta-table-search';

                    const searchLabel = document.createElement('label');
                    searchLabel.textContent = this.config.language.search + ' ';

                    const searchInput = document.createElement('input');
                    searchInput.type = 'search';
                    searchInput.className = 'ta-table-search-input';

                    searchInput.addEventListener('input', () => {
                        this.searchTerm = searchInput.value.toLowerCase();
                        this.search();
                        this.currentPage = 1;
                        this.render();
                    });

                    searchLabel.appendChild(searchInput);
                    searchContainer.appendChild(searchLabel);
                    topControls.appendChild(searchContainer);
                }

                controlsContainer.appendChild(topControls);

                // 创建底部控件
                const bottomControls = document.createElement('div');
                bottomControls.className = 'ta-table-controls-bottom';

                // 创建信息显示
                if (this.config.showInfo) {
                    const info = document.createElement('div');
                    info.className = 'ta-table-info';
                    bottomControls.appendChild(info);
                }

                // 创建分页
                if (this.config.showPagination) {
                    const pagination = document.createElement('div');
                    pagination.className = 'ta-table-pagination';
                    bottomControls.appendChild(pagination);
                }

                controlsContainer.appendChild(bottomControls);

                // 插入控件
                this.element.parentNode.insertBefore(controlsContainer, this.element.nextSibling);

                // 存储控件引用
                this.controls = {
                    container: controlsContainer,
                    topControls: topControls,
                    bottomControls: bottomControls,
                    info: bottomControls.querySelector('.ta-table-info'),
                    pagination: bottomControls.querySelector('.ta-table-pagination')
                };
            },

            // 搜索
            search: function() {
                if (!this.searchTerm) {
                    this.filteredData = Object.assign({}, this.data);
                } else {
                    const searchableColumns = this.data.headers
                        .map((header, index) => header.searchable ? index : -1)
                        .filter(index => index !== -1);

                    this.filteredData = {
                        headers: this.data.headers,
                        rows: this.data.rows.filter(row => {
                            return searchableColumns.some(colIndex => {
                                const cellContent = row[colIndex].toString().toLowerCase();
                                return cellContent.includes(this.searchTerm);
                            });
                        })
                    };
                }

                this.totalPages = Math.ceil(this.filteredData.rows.length / this.config.pageSize);
            },

            // 渲染表格
            render: function() {
                // 渲染表格数据
                this.renderData();

                // 更新信息显示
                if (this.config.showInfo && this.controls.info) {
                    this.updateInfo();
                }

                // 更新分页
                if (this.config.showPagination && this.controls.pagination) {
                    this.updatePagination();
                }
            },

            // 渲染表格数据
            renderData: function() {
                // 获取表格主体
                const tbody = this.element.querySelector('tbody');
                if (!tbody) return;

                // 清空表格主体
                tbody.innerHTML = '';

                // 计算当前页的数据范围
                const start = (this.currentPage - 1) * this.config.pageSize;
                const end = Math.min(start + this.config.pageSize, this.filteredData.rows.length);

                // 如果没有数据，显示空行
                if (this.filteredData.rows.length === 0) {
                    const tr = document.createElement('tr');
                    const td = document.createElement('td');
                    td.colSpan = this.data.headers.length;
                    td.className = 'ta-table-empty';
                    td.textContent = this.config.language.zeroRecords;
                    tr.appendChild(td);
                    tbody.appendChild(tr);
                    return;
                }

                // 渲染当前页的数据
                for (let i = start; i < end; i++) {
                    const row = this.filteredData.rows[i];
                    const tr = document.createElement('tr');

                    row.forEach(cell => {
                        const td = document.createElement('td');
                        td.innerHTML = cell;
                        tr.appendChild(td);
                    });

                    tbody.appendChild(tr);
                }
            },

            // 更新信息显示
            updateInfo: function() {
                if (!this.controls.info) return;

                const start = this.filteredData.rows.length === 0 ? 0 : (this.currentPage - 1) * this.config.pageSize + 1;
                const end = Math.min(start + this.config.pageSize - 1, this.filteredData.rows.length);
                const total = this.filteredData.rows.length;
                const max = this.data.rows.length;

                let infoText = this.config.language.info
                    .replace('_START_', start)
                    .replace('_END_', end)
                    .replace('_TOTAL_', total);

                if (total === 0) {
                    infoText = this.config.language.infoEmpty;
                }

                if (this.searchTerm && total !== max) {
                    infoText += ' ' + this.config.language.infoFiltered.replace('_MAX_', max);
                }

                this.controls.info.textContent = infoText;
            },

            // 更新分页
            updatePagination: function() {
                if (!this.controls.pagination) return;

                // 清空分页
                this.controls.pagination.innerHTML = '';

                // 如果只有一页，不显示分页
                if (this.totalPages <= 1) return;

                // 创建分页列表
                const ul = document.createElement('ul');
                ul.className = 'ta-pagination';

                // 首页按钮
                const firstLi = document.createElement('li');
                firstLi.className = 'ta-page-item' + (this.currentPage === 1 ? ' disabled' : '');

                const firstLink = document.createElement('a');
                firstLink.className = 'ta-page-link';
                firstLink.href = '#';
                firstLink.textContent = this.config.language.paginate.first;

                firstLink.addEventListener('click', (e) => {
                    e.preventDefault();
                    if (this.currentPage !== 1) {
                        this.currentPage = 1;
                        this.render();
                    }
                });

                firstLi.appendChild(firstLink);
                ul.appendChild(firstLi);

                // 上一页按钮
                const prevLi = document.createElement('li');
                prevLi.className = 'ta-page-item' + (this.currentPage === 1 ? ' disabled' : '');

                const prevLink = document.createElement('a');
                prevLink.className = 'ta-page-link';
                prevLink.href = '#';
                prevLink.textContent = this.config.language.paginate.previous;

                prevLink.addEventListener('click', (e) => {
                    e.preventDefault();
                    if (this.currentPage > 1) {
                        this.currentPage--;
                        this.render();
                    }
                });

                prevLi.appendChild(prevLink);
                ul.appendChild(prevLi);

                // 页码按钮
                const maxPages = 5; // 最多显示5个页码
                let startPage = Math.max(1, this.currentPage - Math.floor(maxPages / 2));
                let endPage = Math.min(this.totalPages, startPage + maxPages - 1);

                if (endPage - startPage + 1 < maxPages) {
                    startPage = Math.max(1, endPage - maxPages + 1);
                }

                for (let i = startPage; i <= endPage; i++) {
                    const pageLi = document.createElement('li');
                    pageLi.className = 'ta-page-item' + (i === this.currentPage ? ' active' : '');

                    const pageLink = document.createElement('a');
                    pageLink.className = 'ta-page-link';
                    pageLink.href = '#';
                    pageLink.textContent = i;

                    pageLink.addEventListener('click', (e) => {
                        e.preventDefault();
                        this.currentPage = i;
                        this.render();
                    });

                    pageLi.appendChild(pageLink);
                    ul.appendChild(pageLi);
                }

                // 下一页按钮
                const nextLi = document.createElement('li');
                nextLi.className = 'ta-page-item' + (this.currentPage === this.totalPages ? ' disabled' : '');

                const nextLink = document.createElement('a');
                nextLink.className = 'ta-page-link';
                nextLink.href = '#';
                nextLink.textContent = this.config.language.paginate.next;

                nextLink.addEventListener('click', (e) => {
                    e.preventDefault();
                    if (this.currentPage < this.totalPages) {
                        this.currentPage++;
                        this.render();
                    }
                });

                nextLi.appendChild(nextLink);
                ul.appendChild(nextLi);

                // 末页按钮
                const lastLi = document.createElement('li');
                lastLi.className = 'ta-page-item' + (this.currentPage === this.totalPages ? ' disabled' : '');

                const lastLink = document.createElement('a');
                lastLink.className = 'ta-page-link';
                lastLink.href = '#';
                lastLink.textContent = this.config.language.paginate.last;

                lastLink.addEventListener('click', (e) => {
                    e.preventDefault();
                    if (this.currentPage !== this.totalPages) {
                        this.currentPage = this.totalPages;
                        this.render();
                    }
                });

                lastLi.appendChild(lastLink);
                ul.appendChild(lastLi);

                this.controls.pagination.appendChild(ul);
            }
        };

        // 初始化表格实例
        instance.init();

        // 存储表格实例
        this.instances[id] = instance;

        return instance;
    },

    /**
     * 获取表格实例
     * @param {string} id - 表格ID
     * @returns {Object} 表格实例
     */
    getInstance: function(id) {
        return this.instances[id] || null;
    },

    /**
     * 销毁表格实例
     * @param {string} id - 表格ID
     */
    destroy: function(id) {
        const instance = this.instances[id];
        if (instance) {
            // 移除控件
            if (instance.controls && instance.controls.container) {
                instance.controls.container.parentNode.removeChild(instance.controls.container);
            }

            // 移除表格类
            instance.element.classList.remove('ta-table');

            // 删除实例
            delete this.instances[id];
        }
    }
};

/**
 * 表单验证组件
 * 用于验证表单输入
 */
TweetAnalyst.components.formValidator = {
    // 验证规则
    rules: {
        required: {
            test: value => value.trim() !== '',
            message: '此字段是必填的'
        },
        email: {
            test: value => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value),
            message: '请输入有效的电子邮件地址'
        },
        url: {
            test: value => /^(https?:\/\/)?([\da-z.-]+)\.([a-z.]{2,6})([/\w.-]*)*\/?$/.test(value),
            message: '请输入有效的URL'
        },
        number: {
            test: value => !isNaN(parseFloat(value)) && isFinite(value),
            message: '请输入有效的数字'
        },
        integer: {
            test: value => /^-?\d+$/.test(value),
            message: '请输入有效的整数'
        },
        minLength: {
            test: (value, param) => value.length >= param,
            message: (param) => `请至少输入${param}个字符`
        },
        maxLength: {
            test: (value, param) => value.length <= param,
            message: (param) => `请不要超过${param}个字符`
        },
        min: {
            test: (value, param) => parseFloat(value) >= param,
            message: (param) => `请输入不小于${param}的值`
        },
        max: {
            test: (value, param) => parseFloat(value) <= param,
            message: (param) => `请输入不大于${param}的值`
        },
        pattern: {
            test: (value, param) => new RegExp(param).test(value),
            message: '请输入符合格式的值'
        }
    },

    // 初始化
    init: function() {
        // 查找所有带有data-validate属性的表单
        const forms = document.querySelectorAll('form[data-validate]');

        // 初始化每个表单
        forms.forEach(form => {
            this.initForm(form);
        });
    },

    /**
     * 初始化表单验证
     * @param {HTMLElement|string} form - 表单元素或选择器
     */
    initForm: function(form) {
        // 获取表单元素
        const formElement = typeof form === 'string' ? document.querySelector(form) : form;

        if (!formElement) {
            console.error(`表单元素不存在: ${form}`);
            return;
        }

        // 绑定提交事件
        formElement.addEventListener('submit', (e) => {
            // 验证表单
            if (!this.validateForm(formElement)) {
                e.preventDefault();
                e.stopPropagation();
            }
        });

        // 绑定输入事件
        const inputs = formElement.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            input.addEventListener('blur', () => {
                this.validateField(input);
            });

            input.addEventListener('input', () => {
                // 如果字段已经被标记为无效，则在输入时重新验证
                if (input.classList.contains('is-invalid')) {
                    this.validateField(input);
                }
            });
        });
    },

    /**
     * 验证表单
     * @param {HTMLElement} form - 表单元素
     * @returns {boolean} 验证结果
     */
    validateForm: function(form) {
        let isValid = true;

        // 验证所有字段
        const inputs = form.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            if (!this.validateField(input)) {
                isValid = false;
            }
        });

        return isValid;
    },

    /**
     * 验证字段
     * @param {HTMLElement} field - 字段元素
     * @returns {boolean} 验证结果
     */
    validateField: function(field) {
        // 获取验证规则
        const rules = field.getAttribute('data-validate');
        if (!rules) return true;

        // 获取字段值
        const value = field.value;

        // 解析规则
        const ruleList = rules.split('|');

        // 验证每个规则
        for (const rule of ruleList) {
            // 解析规则和参数
            const [ruleName, param] = rule.split(':');

            // 获取规则对象
            const ruleObj = this.rules[ruleName];
            if (!ruleObj) {
                console.warn(`未知的验证规则: ${ruleName}`);
                continue;
            }

            // 验证规则
            const isValid = ruleObj.test(value, param);

            if (!isValid) {
                // 获取错误消息
                let errorMessage = typeof ruleObj.message === 'function' ? ruleObj.message(param) : ruleObj.message;

                // 获取自定义错误消息
                const customMessage = field.getAttribute(`data-validate-${ruleName}-message`);
                if (customMessage) {
                    errorMessage = customMessage;
                }

                // 标记字段为无效
                field.classList.add('is-invalid');
                field.classList.remove('is-valid');

                // 显示错误消息
                let feedback = field.nextElementSibling;
                if (!feedback || !feedback.classList.contains('invalid-feedback')) {
                    feedback = document.createElement('div');
                    feedback.className = 'invalid-feedback';
                    field.parentNode.insertBefore(feedback, field.nextSibling);
                }

                feedback.textContent = errorMessage;

                return false;
            }
        }

        // 标记字段为有效
        field.classList.add('is-valid');
        field.classList.remove('is-invalid');

        // 移除错误消息
        const feedback = field.nextElementSibling;
        if (feedback && feedback.classList.contains('invalid-feedback')) {
            feedback.textContent = '';
        }

        return true;
    },

    /**
     * 添加自定义验证规则
     * @param {string} name - 规则名称
     * @param {Function} testFn - 验证函数
     * @param {string|Function} message - 错误消息
     */
    addRule: function(name, testFn, message) {
        this.rules[name] = {
            test: testFn,
            message: message
        };
    }
};

// 初始化组件库
document.addEventListener('DOMContentLoaded', function() {
    TweetAnalyst.init({
        debug: false
    });
});
