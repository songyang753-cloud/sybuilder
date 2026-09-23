// 与 templates/base.html 配套的断言范例，也是「必测清单」的可执行版。
// 跑法: node scripts/selftest.mjs templates/base.html templates/asserts.example.js
// 新 demo 从这份改起：把选择器和场景名换成你自己的。

/* ---------- 1. 交付契约 ---------- */
check('零外链', !document.querySelector(
  'link[href^="http"],script[src^="http"],img[src^="http"]'));
check('无横向滚动', document.body.scrollWidth <= window.innerWidth + 1);

/* ---------- 2. 场景完整性 ---------- */
check('起手场景正确', state.page === 'home');

var targets = $$('[data-goto]').map(function (el) { return el.getAttribute('data-goto'); });
var dead = targets.filter(function (t) { return !PAGES[t]; });
check('无死链导航（' + targets.join(',') + '）', dead.length === 0);

var empty = Object.keys(PAGES).filter(function (p) {
  setPage(p);
  return $('#stage').textContent.trim().length === 0;
});
check('所有场景非空', empty.length === 0);

/* ---------- 3. 可达性 ---------- */
setPage('home');
check('当前导航项高亮', $('.nav .item.on') !== null);
check('不可用功能有 disabled 态而非死链', $('.btn[disabled]') !== null);

setPage('detail', { selectedId: 'c' });
check('切页参数生效', text('.h2') === '条目 C');
check('详情页有返回路径', $('[data-goto="home"]') !== null);

/* ---------- 4. 诚实占位 ---------- */
setPage('todo');
check('占位页有占位声明', $('#stage').textContent.indexOf('占位') >= 0);

/* ---------- 5. 交互后果 ---------- */
setPage('home');
$('[data-act="create"]').click();
check('抽屉可打开', $('#drawer').classList.contains('open'));
$('[data-act="close"]').click();
check('抽屉可关闭', !$('#drawer').classList.contains('open'));

setPage('detail');
$('[data-act="toast"]').click();
check('Toast 可触发', $('#toast').classList.contains('show'));
check('Toast 文案够短（≤20 字）', text('#toast').length <= 20);

/* ---------- 6. 几何（按设计稿还原时逐条加） ---------- */
setPage('home');
eq('卡片高 128', px('.card', 'height'), 128);
