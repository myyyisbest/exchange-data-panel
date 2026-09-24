/**
 * 汇率数据面板 - 前端逻辑（统一视图版）
 *
 * 主表格：合并展示 CNY / IDR / HKD / USD 各基座的所有汇率对
 * 趋势图：可选输入货币 + 最多 5 个相对方货币
 */

// ============ 配置 ============
const BASE_DEFAULTS = {
    CNY: ['USD', 'EUR', 'JPY', 'GBP', 'AUD'],
    IDR: ['USD', 'EUR', 'JPY', 'SGD', 'AUD'],
    HKD: ['USD', 'EUR', 'JPY', 'GBP', 'AUD'],
    USD: ['CNY', 'EUR', 'JPY', 'HKD', 'SGD'],
};

const BASE_ICONS = { CNY: '¥', IDR: 'Rp', HKD: 'HK$', USD: '$' };

// 常用币种（10 个）：AED/CNY/EUR/GBP/HKD/IDR/JPY/KRW/SGD/USD
// 出现在主表格行的 base 或 target 中时算"常用"
const FAVORITE_CURRENCIES = new Set(['AED', 'CNY', 'EUR', 'GBP', 'HKD', 'IDR', 'JPY', 'KRW', 'SGD', 'USD']);
const FAV_STORAGE_KEY = 'exchange.favoriteOnly.v1';

// ============ 状态 ============
const state = {
    trendBase: 'CNY',          // 趋势图当前输入货币
    currentDate: null,         // 当前主表格日期
    currentRows: [],           // 当前主表格所有行
    baseDates: {},             // 每个基座自己的最新日期
    selectedCurrencies: [],    // 趋势图选中的相对方货币
    trendChart: null,
    sortKey: null,
    sortDir: -1,               // 1=升序, -1=降序
    trendDays: 30,
    tableBaseFilter: '',       // 主表格基座筛选（空=全部）
    favoriteOnly: true,        // 仅显示常用币种（默认开启）
};

// ============ 工具函数 ============
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function getBaseCurrencies(base) {
    return window.CURRENCIES_META[base] || [];
}

/** Toast 通知 */
function showToast(msg, type = 'primary', duration = 3500) {
    const container = $('#toast-container');
    const el = document.createElement('div');
    el.className = `toast-item ${type}`;
    el.textContent = msg;
    container.appendChild(el);
    el.addEventListener('click', () => el.remove());
    setTimeout(() => {
        el.style.transition = 'opacity .3s';
        el.style.opacity = '0';
        setTimeout(() => el.remove(), 300);
    }, duration);
}

/** 通用 fetch 封装 */
async function apiFetch(path, options = {}) {
    const base = window.API_BASE || '';
    const url = `${base}${path}`;
    const resp = await fetch(url, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
    });
    if (!resp.ok) {
        const body = await resp.json().catch(() => ({ error: resp.statusText }));
        throw new Error(body.error || `HTTP ${resp.status}`);
    }
    return resp.json();
}

/** 格式化汇率数值（展示原始官网单位） */
function fmtRate(v, unit) {
    if (v == null) return '--';
    const n = Number(v) * (unit || 1);
    if (n >= 10000) return n.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
    if (n >= 100)   return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 });
    if (n >= 10)    return n.toLocaleString('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 4 });
    return n.toLocaleString('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 6 });
}

/** 涨跌颜色 class */
function changeClass(pct) {
    if (pct == null) return 'change-flat';
    if (pct > 0.001) return 'change-up';
    if (pct < -0.001) return 'change-down';
    return 'change-flat';
}

/** 涨跌箭头符号 */
function arrow(cls) {
    if (cls === 'change-up')   return '▲';
    if (cls === 'change-down') return '▼';
    return '';
}

// ============ 主表格（统一视图）============
function renderUnifiedTable(rows) {
    const tbody = $('#rates-tbody');

    // 应用基座筛选
    let display = state.tableBaseFilter
        ? rows.filter(r => r.base === state.tableBaseFilter)
        : rows.slice();

    // 应用"仅常用币种"过滤：只看 target（base 是固定的 CNY/HKD/IDR）
    if (state.favoriteOnly) {
        display = display.filter(r => FAVORITE_CURRENCIES.has(r.target));
    }

    // 排序（按 sortKey）
    if (state.sortKey) {
        const dir = state.sortDir;
        display.sort((a, b) => {
            let va, vb;
            switch (state.sortKey) {
                case 'base':   va = a.base; vb = b.base; break;
                case 'target': va = a.target; vb = b.target; break;
                case 'rate':   va = a.rate ?? -Infinity; vb = b.rate ?? -Infinity; break;
                case 'change': va = a.diff ?? -Infinity; vb = b.diff ?? -Infinity; break;
                case 'pct':    va = a.pct ?? -Infinity; vb = b.pct ?? -Infinity; break;
            }
            if (typeof va === 'string') return va.localeCompare(vb) * dir;
            return (va - vb) * dir;
        });
    }

    if (!display.length) {
        const msg = state.favoriteOnly
            ? '当前基座筛选下没有常用币种数据（关闭 ⭐ 按钮可查看全部）'
            : '暂无数据';
        tbody.innerHTML = `<tr><td colspan="10" class="empty-hint">${msg}</td></tr>`;
        return;
    }

    tbody.innerHTML = '';
    display.forEach((r, idx) => {
        const cls = changeClass(r.pct);
        const unitLabel = r.unit === 100 ? '100' : '1';
        // 关闭"仅常用"模式时给常用行加 ⭐ 标记，方便用户识别
        const favMark = (!state.favoriteOnly && FAVORITE_CURRENCIES.has(r.target))
            ? '<span class="fav-row-mark" title="常用币种">★</span>' : '';
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td class="row-no">${idx + 1}</td>
            <td><span class="currency-code base-tag" data-base="${r.base}">${r.base}</span>${favMark}</td>
            <td><span class="currency-name" title="${r.base_name}">${r.base_name}</span></td>
            <td><span class="currency-code">${r.target}</span>${favMark}</td>
            <td><span class="currency-name" title="${r.target_name}">${r.target_name}</span></td>
            <td class="col-method"><span class="method-badge ${r.quote_method}">${r.quote_method_label}</span></td>
            <td class="col-unit">${unitLabel}</td>
            <td class="text-right"><span class="rate-val">${fmtRate(r.rate, r.unit)}</span></td>
            <td class="text-right ${cls}">
                ${r.diff != null ? (r.diff > 0 ? '+' : '') + (r.diff * (r.unit || 1)).toFixed(4) : '--'}
            </td>
            <td class="text-right ${cls}">
                ${r.pct != null ? arrow(cls) + (r.pct > 0 ? '+' : '') + r.pct.toFixed(3) + '%' : '--'}
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// ============ 排序绑定 ============
function initSortHandlers() {
    $$('.sortable').forEach(th => {
        th.addEventListener('click', () => {
            const key = th.dataset.sort;
            if (state.sortKey === key) {
                state.sortDir = -state.sortDir;
            } else {
                state.sortKey = key;
                state.sortDir = -1;  // 首次默认降序
            }
            $$('.sort-icon').forEach(i => i.textContent = '⇅');
            const icon = th.querySelector('.sort-icon');
            if (icon) icon.textContent = state.sortDir === 1 ? '↑' : '↓';

            if (state.currentRows.length) {
                renderUnifiedTable(state.currentRows);
            }
        });
    });
}

// ============ 主表格基座筛选 ============
function initBaseFilter() {
    $$('#base-filter .btn-base').forEach(btn => {
        btn.addEventListener('click', () => {
            $$('#base-filter .btn-base').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.tableBaseFilter = btn.dataset.base || '';
            if (state.currentRows.length) {
                renderUnifiedTable(state.currentRows);
            }
            const label = state.tableBaseFilter || '全部';
            showToast(`已筛选：${label}`, 'info', 1500);
        });
    });
}

// ============ 趋势图：输入货币切换 ============
async function switchTrendBase(base) {
    if (base === state.trendBase) return;
    state.trendBase = base;

    // 同步两个 base-selector（顶部筛选 + 趋势面板内）
    syncBaseButtons();

    // 重新生成相对方货币 picker
    renderCurrencyPicker();

    // 用该基座的默认（优先用户保存的）
    const available = getBaseCurrencies(base).map(c => c.code);
    const fallback = BASE_DEFAULTS[base] || available.slice(0, 5);
    state.selectedCurrencies = fallback.filter(c => available.includes(c));
    if (state.selectedCurrencies.length === 0) {
        state.selectedCurrencies = available.slice(0, 5);
    }
    renderSelectedChips();

    // 加载用户保存的偏好（异步覆盖）
    try {
        const r = await apiFetch(`/api/preferences/${base}`);
        if (r && Array.isArray(r.currencies) && r.currencies.length) {
            const filtered = r.currencies.filter(c => available.includes(c));
            if (filtered.length) {
                const same = filtered.length === state.selectedCurrencies.length &&
                             filtered.every(c => state.selectedCurrencies.includes(c));
                if (!same) {
                    state.selectedCurrencies = filtered;
                    renderCurrencyPicker();
                    renderSelectedChips();
                }
            }
        }
    } catch (e) { /* ignore */ }

    refreshTrendChart();
    showToast(`趋势图：${base} 视图`, 'success', 1500);
}

function syncBaseButtons() {
    // 趋势面板内的 base-selector
    $$('#trend-base-selector .btn-base').forEach(b => {
        b.classList.toggle('active', b.dataset.base === state.trendBase);
    });
}

function initTrendBaseSelector() {
    $$('#trend-base-selector .btn-base').forEach(btn => {
        btn.addEventListener('click', () => switchTrendBase(btn.dataset.base));
    });
}

// ============ 常用币种 toggle ============
function loadFavoriteOnly() {
    try {
        const v = localStorage.getItem(FAV_STORAGE_KEY);
        if (v === '0' || v === 'false') return false;
    } catch (e) { /* localStorage 不可用 */ }
    return true;  // 默认开启
}

function applyFavoriteToggleUI() {
    const btn = $('#btn-favorite-toggle');
    if (!btn) return;
    btn.setAttribute('aria-pressed', state.favoriteOnly ? 'true' : 'false');
    btn.classList.toggle('active', state.favoriteOnly);
    const label = state.favoriteOnly ? '仅常用币种' : '显示全部币种';
    btn.querySelector('.fav-label').textContent = label;
}

function initFavoriteToggle() {
    state.favoriteOnly = loadFavoriteOnly();
    // 动态写入常用币种数量
    const cnt = $('#fav-count');
    if (cnt) cnt.textContent = `(${FAVORITE_CURRENCIES.size})`;
    applyFavoriteToggleUI();
    const btn = $('#btn-favorite-toggle');
    if (!btn) return;
    btn.addEventListener('click', () => {
        state.favoriteOnly = !state.favoriteOnly;
        try { localStorage.setItem(FAV_STORAGE_KEY, state.favoriteOnly ? '1' : '0'); } catch (e) {}
        applyFavoriteToggleUI();
        if (state.currentRows.length) {
            renderUnifiedTable(state.currentRows);
            const favCount = state.currentRows.filter(r => FAVORITE_CURRENCIES.has(r.target)).length;
            const hidden = state.currentRows.length - (state.favoriteOnly ? favCount : 0);
            if (state.favoriteOnly) {
                showToast(`已显示常用币种 ${favCount} 行（隐藏 ${hidden} 条不常用）`, 'info', 1800);
            } else {
                showToast(`已显示全部 ${state.currentRows.length} 行`, 'info', 1500);
            }
        }
    });
}

// ============ 趋势图：相对方货币多选 ============
function renderCurrencyPicker() {
    const wrap = $('#currency-quick-pick');
    wrap.innerHTML = '';
    getBaseCurrencies(state.trendBase).forEach(c => {
        const btn = document.createElement('button');
        btn.className = 'currency-btn' + (state.selectedCurrencies.includes(c.code) ? ' active' : '');
        btn.dataset.code = c.code;
        btn.textContent = c.code;
        btn.title = c.name;
        btn.addEventListener('click', () => toggleCurrency(c.code));
        wrap.appendChild(btn);
    });
}

function toggleCurrency(code) {
    const idx = state.selectedCurrencies.indexOf(code);
    if (idx >= 0) {
        if (state.selectedCurrencies.length <= 1) {
            showToast('至少保留一个货币', 'warning');
            return;
        }
        state.selectedCurrencies.splice(idx, 1);
    } else {
        if (state.selectedCurrencies.length >= 5) {
            showToast('最多对比 5 个货币', 'warning');
            return;
        }
        state.selectedCurrencies.push(code);
    }
    renderCurrencyPicker();
    renderSelectedChips();
    refreshTrendChart();
}

function renderSelectedChips() {
    const wrap = $('#selected-currencies');
    if (!state.selectedCurrencies.length) {
        wrap.innerHTML = '<em class="text-muted">请选择货币</em>';
        return;
    }
    const baseCurrencies = getBaseCurrencies(state.trendBase);
    wrap.innerHTML = state.selectedCurrencies.map(code => {
        const c = baseCurrencies.find(x => x.code === code);
        return `<span class="badge">${code} · ${c ? c.name : code}</span>`;
    }).join('');
}

// ============ 用户偏好保存 ============
async function saveUserDefaults() {
    if (!state.selectedCurrencies.length) {
        showToast('当前未选择任何货币', 'warning');
        return;
    }
    try {
        const r = await apiFetch(`/api/preferences/${state.trendBase}`, {
            method: 'POST',
            body: JSON.stringify({ currencies: state.selectedCurrencies }),
        });
        if (r.status === 'success') {
            showToast(`已保存 ${state.trendBase} 的默认 ${r.count} 个货币`, 'success');
        } else {
            showToast('保存失败: ' + (r.error || '未知错误'), 'danger');
        }
    } catch (e) {
        showToast('保存失败: ' + e.message, 'danger');
    }
}

// ============ 趋势图 ============
const PALETTE = ['#dc2626', '#eab308', '#2563eb', '#16a34a', '#7c3aed'];

async function refreshTrendChart() {
    const days = state.trendDays;
    try {
        const data = await apiFetch(`/api/recent?days=${days}&base=${state.trendBase}`);
        const rows = data.rows;
        if (!rows.length) { showToast('暂无趋势数据', 'warning'); return; }

        const labels = rows.map(r => r.date);
        const currencies = getBaseCurrencies(state.trendBase);

        const datasets = state.selectedCurrencies.map((code, i) => {
            const c = currencies.find(x => x.code === code);
            const base = rows[0][code];
            const values = rows.map(r => {
                const v = r[code];
                if (v == null || base == null) return null;
                return +((v - base) / base * 100).toFixed(4);
            });
            return {
                label: `${code}（${c ? c.name : code}）`,
                data: values,
                borderColor: PALETTE[i % PALETTE.length],
                backgroundColor: PALETTE[i % PALETTE.length] + '18',
                tension: 0.3,
                borderWidth: 2,
                pointRadius: rows.length > 100 ? 0 : 2,
                pointHoverRadius: 5,
                fill: false,
                spanGaps: true,
            };
        });

        const options = {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                title: {
                    display: true,
                    text: `${state.trendBase} 相对期初变化百分比（近 ${days} 个交易日）`,
                    color: '#64748b',
                    font: { size: 12, weight: '400' },
                },
                legend: {
                    position: 'bottom',
                    labels: { font: { size: 11 }, boxWidth: 14, padding: 10 }
                },
                tooltip: {
                    callbacks: {
                        label: ctx => {
                            const v = ctx.parsed.y;
                            if (v == null) return '';
                            return `${ctx.dataset.label.split('（')[0]}: ${v >= 0 ? '+' : ''}${v.toFixed(3)}%`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    ticks: { callback: v => v + '%', font: { size: 11 } },
                    grid: { color: '#f1f5f9' },
                },
                x: {
                    ticks: {
                        maxRotation: 0, autoSkip: true,
                        maxTicksLimit: days > 100 ? 8 : 12,
                        font: { size: 10 },
                    },
                    grid: { display: false },
                }
            }
        };

        if (state.trendChart) {
            state.trendChart.data.labels = labels;
            state.trendChart.data.datasets = datasets;
            state.trendChart.options = options;
            state.trendChart.update('none');
        } else {
            const ctx = $('#trend-chart').getContext('2d');
            state.trendChart = new Chart(ctx, { type: 'line', data: { labels, datasets }, options });
        }
    } catch (e) {
        showToast('趋势图加载失败: ' + e.message, 'danger');
    }
}

// ============ 主表格数据加载 ============
async function loadUnifiedLatest() {
    try {
        const data = await apiFetch('/api/unified/latest');
        if (!data.rows || !data.rows.length) {
            $('#rates-tbody').innerHTML = '<tr><td colspan="10" class="empty-hint">数据库暂无数据</td></tr>';
            $('#table-date-label').textContent = '--';
            return;
        }
        state.currentDate = data.date;
        state.baseDates = data.base_dates || {};
        state.currentRows = data.rows;
        // 显示主日期 + 各基座日期
        const dateLabel = data.date
            ? `${data.date}`
            : '--';
        $('#table-date-label').textContent = dateLabel;
        if (data.date) $('#date-input').value = data.date;
        renderUnifiedTable(data.rows);
    } catch (e) {
        showToast('加载失败: ' + e.message, 'danger');
    }
}

async function loadUnifiedDate(dateStr) {
    try {
        const data = await apiFetch(`/api/unified/date/${dateStr}`);
        if (!data.rows || !data.rows.length) {
            $('#rates-tbody').innerHTML = `<tr><td colspan="10" class="empty-hint">${dateStr} 无数据</td></tr>`;
            $('#table-date-label').textContent = dateStr;
            return;
        }
        state.currentDate = data.date;
        state.currentRows = data.rows;
        $('#table-date-label').textContent = data.date;
        $('#date-input').value = data.date;
        renderUnifiedTable(data.rows);
    } catch (e) {
        showToast('加载失败: ' + e.message, 'danger');
    }
}

// ============ 历史日期列表（CNY 默认）============
async function renderHistoryList() {
    try {
        const data = await apiFetch('/api/dates?limit=60&base=CNY');
        const wrap = $('#history-list');
        if (!data.dates.length) {
            wrap.innerHTML = '<em class="text-muted">数据库暂无数据，请点击"抓取今日"或"回填30天"</em>';
            return;
        }
        wrap.innerHTML = '';
        data.dates.forEach(d => {
            const pill = document.createElement('span');
            pill.className = 'history-pill' + (d === state.currentDate ? ' active' : '');
            pill.textContent = d;
            pill.dataset.date = d;
            pill.addEventListener('click', () => loadUnifiedDate(d));
            wrap.appendChild(pill);
        });
    } catch (e) {
        console.warn('历史列表加载失败', e);
    }
}

// ============ 顶部统计 ============
async function refreshStats() {
    try {
        const s = await apiFetch('/api/stats');
        // 取三个基座中最新日期
        const dates = Object.values(s.sources || {}).map(x => x.latest_date).filter(Boolean);
        const maxDate = dates.length ? dates.reduce((a, b) => a > b ? a : b) : '--';
        $('#stat-latest-date').textContent = maxDate;
        const total = Object.values(s.sources || {}).reduce((acc, x) => acc + (x.total_records || 0), 0);
        $('#stat-total').textContent = total.toLocaleString();
        $('#stat-crawl-time').textContent =
            `${String(s.crawl_hour).padStart(2, '0')}:${String(s.crawl_minute).padStart(2, '0')}`;
    } catch (e) {
        console.warn('stats 加载失败', e);
    }
}

// ============ 手动操作 ============
async function crawlToday() {
    const btn = $('#btn-crawl-today');
    btn.disabled = true;
    btn.innerHTML = '<span class="loading-icon">↻</span> 抓取中...';
    showToast('正在抓取今日数据...', 'primary');
    try {
        const r = await apiFetch('/api/crawl', {
            method: 'POST',
            body: JSON.stringify({ source: 'CNY' }),
        });
        if (r.status === 'success') {
            showToast(`抓取成功，新增 ${r.inserted} 条数据`, 'success');
        } else if (r.status === 'empty') {
            showToast(r.message, 'warning');
        } else {
            showToast(r.message || '抓取失败', 'danger');
        }
        await refreshAll();
    } catch (e) {
        showToast('抓取失败: ' + e.message, 'danger');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span>↻</span> 抓取今日';
    }
}

async function backfill() {
    const btn = $('#btn-backfill');
    btn.disabled = true;
    btn.innerHTML = '<span class="loading-icon">⬇</span> 回填中...';
    showToast('正在回填最近30天...', 'primary');
    try {
        const r = await apiFetch('/api/backfill', {
            method: 'POST',
            body: JSON.stringify({ days: 30, source: 'CNY' }),
        });
        if (r.status === 'success') {
            showToast(`回填完成：${r.message}`, 'success');
        } else {
            showToast(r.message || '回填结束', 'info');
        }
        await refreshAll();
    } catch (e) {
        showToast('回填失败: ' + e.message, 'danger');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '⬇ 回填30天';
    }
}

// ============ 工具栏事件 ============
function initToolbar() {
    $('#btn-crawl-today').addEventListener('click', crawlToday);
    $('#btn-backfill').addEventListener('click', backfill);
    $('#btn-save-defaults').addEventListener('click', saveUserDefaults);

    // 单日查询
    $('#btn-query-date').addEventListener('click', () => {
        const v = $('#date-input').value;
        if (!v) { showToast('请选择日期', 'warning'); return; }
        loadUnifiedDate(v);
    });

    // 上一个交易日
    $('#btn-day-prev').addEventListener('click', () => stepDate(-1));
    // 下一个交易日
    $('#btn-day-next').addEventListener('click', () => stepDate(+1));

    // 最新数据
    $('#btn-query-latest').addEventListener('click', loadUnifiedLatest);

    // 趋势天数
    $('#trend-days').addEventListener('change', e => {
        state.trendDays = +e.target.value || 30;
        refreshTrendChart();
    });
}

/**
 * 跳到当前日期的相邻交易日（用 CNY 已有日期作为日历基准）
 * :param dir: -1=上一个交易日, +1=下一个交易日
 */
let _availableDatesCache = null;
async function stepDate(dir) {
    try {
        if (!_availableDatesCache) {
            const data = await apiFetch('/api/dates?limit=1000&base=CNY');
            _availableDatesCache = (data.dates || []).slice().sort();
        }
        const dates = _availableDatesCache;
        if (!dates.length) { showToast('暂无日期数据', 'warning'); return; }
        const cur = state.currentDate;
        let idx = cur ? dates.indexOf(cur) : -1;
        if (idx === -1) {
            // 当前日期不在列表里（理论上不会出现），选最近的
            if (dir > 0) idx = -1; else idx = dates.length;
        }
        const next = idx + dir;
        if (next < 0) { showToast('已是历史最早一天', 'info'); return; }
        if (next >= dates.length) { showToast('已是历史最新一天', 'info'); return; }
        await loadUnifiedDate(dates[next]);
    } catch (e) {
        showToast('日期切换失败: ' + e.message, 'danger');
    }
}

// ============ 启动 ============
async function refreshAll() {
    await Promise.all([loadUnifiedLatest(), renderHistoryList(), refreshStats()]);
}

function init() {
    initToolbar();
    initSortHandlers();
    initBaseFilter();
    initFavoriteToggle();
    initTrendBaseSelector();

    // 初始化 trend 选中（默认 CNY + 默认 5 个相对方货币）
    const base = state.trendBase;
    const available = getBaseCurrencies(base).map(c => c.code);
    state.selectedCurrencies = (BASE_DEFAULTS[base] || []).filter(c => available.includes(c));
    if (state.selectedCurrencies.length === 0) {
        state.selectedCurrencies = available.slice(0, 5);
    }
    renderCurrencyPicker();
    renderSelectedChips();
    refreshTrendChart();

    refreshAll();

    // 尝试加载用户保存的偏好（覆盖默认）
    apiFetch(`/api/preferences/${base}`).then(r => {
        if (r && Array.isArray(r.currencies) && r.currencies.length) {
            const filtered = r.currencies.filter(c => available.includes(c));
            if (filtered.length) {
                const same = filtered.length === state.selectedCurrencies.length &&
                             filtered.every(c => state.selectedCurrencies.includes(c));
                if (!same) {
                    state.selectedCurrencies = filtered;
                    renderCurrencyPicker();
                    renderSelectedChips();
                    refreshTrendChart();
                }
            }
        }
    }).catch(() => {});
}

document.addEventListener('DOMContentLoaded', init);
