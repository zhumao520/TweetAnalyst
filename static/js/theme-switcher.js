/**
 * TweetAnalyst主题切换器
 * 处理明亮/暗黑主题的切换和保存用户偏好
 */

(function() {
    // 主题切换器类
    class ThemeSwitcher {
        constructor() {
            this.themeKey = 'tweetanalyst-theme';
            this.darkTheme = 'dark';
            this.lightTheme = 'light';
            this.defaultTheme = this.lightTheme;
            this.themeToggle = document.getElementById('theme-toggle');

            this.init();
        }

        // 初始化
        init() {
            // 加载保存的主题
            this.loadSavedTheme();

            // 绑定事件
            if (this.themeToggle) {
                this.themeToggle.addEventListener('change', () => this.toggleTheme());

                // 设置初始状态
                this.themeToggle.checked = this.getCurrentTheme() === this.darkTheme;
            }

            // 监听系统主题变化
            this.listenForSystemThemeChanges();
        }

        // 加载保存的主题
        loadSavedTheme() {
            const savedTheme = localStorage.getItem(this.themeKey);

            if (savedTheme) {
                this.setTheme(savedTheme);
            } else {
                // 如果没有保存的主题，使用系统主题
                this.useSystemTheme();
            }
        }

        // 使用系统主题
        useSystemTheme() {
            // 默认使用明亮主题，不跟随系统
            this.setTheme(this.lightTheme);

            // 如果需要跟随系统主题，可以取消下面的注释
            /*
            if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
                this.setTheme(this.darkTheme);
            } else {
                this.setTheme(this.lightTheme);
            }
            */
        }

        // 监听系统主题变化
        listenForSystemThemeChanges() {
            if (window.matchMedia) {
                window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
                    // 只有当用户没有明确设置主题时，才跟随系统主题
                    if (!localStorage.getItem(this.themeKey)) {
                        this.setTheme(e.matches ? this.darkTheme : this.lightTheme);

                        // 更新切换按钮状态
                        if (this.themeToggle) {
                            this.themeToggle.checked = e.matches;
                        }
                    }
                });
            }
        }

        // 切换主题
        toggleTheme() {
            const currentTheme = this.getCurrentTheme();
            const newTheme = currentTheme === this.darkTheme ? this.lightTheme : this.darkTheme;

            this.setTheme(newTheme);
            this.saveTheme(newTheme);
        }

        // 获取当前主题
        getCurrentTheme() {
            return document.documentElement.getAttribute('data-theme') || this.defaultTheme;
        }

        // 设置主题
        setTheme(theme) {
            document.documentElement.setAttribute('data-theme', theme);

            // 更新切换按钮状态
            if (this.themeToggle) {
                this.themeToggle.checked = theme === this.darkTheme;
            }

            // 更新meta标签
            this.updateMetaTags(theme);

            // 应用主题到iframe和嵌入元素
            this.applyThemeToEmbeds(theme);

            // 触发主题变更事件
            this.dispatchThemeChangeEvent(theme);
        }

        // 更新meta标签
        updateMetaTags(theme) {
            // 更新theme-color
            const metaThemeColor = document.querySelector('meta[name="theme-color"]');
            if (metaThemeColor) {
                metaThemeColor.setAttribute('content', theme === this.darkTheme ? '#1E2029' : '#343a40');
            }

            // 更新apple-mobile-web-app-status-bar-style
            const metaStatusBar = document.querySelector('meta[name="apple-mobile-web-app-status-bar-style"]');
            if (metaStatusBar) {
                metaStatusBar.setAttribute('content', theme === this.darkTheme ? 'black' : 'black-translucent');
            }
        }

        // 应用主题到iframe和嵌入元素
        applyThemeToEmbeds(theme) {
            // 应用到iframe
            document.querySelectorAll('iframe').forEach(iframe => {
                try {
                    if (iframe.contentDocument && iframe.contentDocument.documentElement) {
                        iframe.contentDocument.documentElement.setAttribute('data-theme', theme);
                    }
                } catch (e) {
                    // 跨域iframe无法访问
                    console.log('无法应用主题到跨域iframe');
                }
            });

            // 应用到CodeMirror编辑器
            if (window.CodeMirror) {
                document.querySelectorAll('.CodeMirror').forEach(cm => {
                    if (cm.CodeMirror) {
                        cm.CodeMirror.setOption('theme', theme === this.darkTheme ? 'monokai' : 'default');
                    }
                });
            }
        }

        // 保存主题到localStorage
        saveTheme(theme) {
            localStorage.setItem(this.themeKey, theme);
        }

        // 触发主题变更事件
        dispatchThemeChangeEvent(theme) {
            const event = new CustomEvent('themechange', {
                detail: { theme: theme }
            });
            document.dispatchEvent(event);
        }
    }

    // 当DOM加载完成后初始化主题切换器
    document.addEventListener('DOMContentLoaded', () => {
        window.TweetAnalyst = window.TweetAnalyst || {};
        window.TweetAnalyst.themeSwitcher = new ThemeSwitcher();
    });
})();
