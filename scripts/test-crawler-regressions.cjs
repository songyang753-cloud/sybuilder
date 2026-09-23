// Offline DOM/CDP probes: never attach to a browser or use a personal profile.
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const scripts = path.join(__dirname, '../skills/product-flow/scripts');
const core = require(path.join(scripts, '_cdp.js'));
const failures = [];
let count = 0;
async function test(name, fn) {
  count++;
  try { await fn(); console.log('PASS ' + name); }
  catch (error) { failures.push(name); console.error('FAIL ' + name + ': ' + error.message); }
}
function element(text, options = {}) {
  return {
    tagName: options.tag || 'BUTTON', id: '', type: options.type || '',
    innerText: text, value: options.value || '', className: '', disabled: false,
    getAttribute: key => ({'aria-label': options.label || '', role: options.role || 'tab',
      contenteditable: options.editable ? 'true' : ''})[key] || '',
    getBoundingClientRect: () => ({width: 120, height: 30, x: options.x || 0, y: 0}),
    closest: selector => selector.includes('[class*=history]') && options.history ? {} : null,
    scrollIntoView() {}, click: options.click || (() => {})
  };
}
function dom(els) {
  return {document: {querySelectorAll: () => els, title: 'Synthetic fixture'},
    location: {href: 'https://example.test/'}, URL,
    getComputedStyle: () => ({visibility: 'visible', display: 'block', opacity: '1'})};
}
const snap = els => vm.runInNewContext(core.ENUM_JS, dom(els));
async function run(kind, cdp) {
  const files = new Map();
  let exit = 0;
  const fakeFs = {mkdirSync() {}, writeFileSync: (p, data) => files.set(p, data),
    existsSync: p => files.has(p), statSync: p => ({size: (files.get(p) || '').length})};
  cdp.shot ||= async p => files.set(p, 'synthetic-image-bytes');
  let source = fs.readFileSync(path.join(scripts, kind), 'utf8').replace(/^#![^\n]*\n/, '');
  if (kind.endsWith('.mjs')) source = source.replace(/^import .*;\n/gm, '')
    .replace('const require = createRequire(import.meta.url);', '')
    .replaceAll('import.meta.url', '"synthetic-script"');
  const result = vm.runInNewContext('(async()=>{' + source + '\n})()', {
    require: name => name === 'fs' ? fakeFs : {...core, connect: async () => cdp},
    fs: fakeFs, path, URL,
    process: {argv: ['node', kind, '9222', '/synthetic-output'],
      exit: code => { exit = code; }, stderr: {write() {}}},
    console: {log() {}, error() {}}
  });
  await result;
  // The CJS entry starts an async main; let its queued continuations complete.
  for (let i = 0; i < 10000 && ![...files.keys()].some(p => /(?:deep-tree|transitions)\.json$/.test(p)); i++) await Promise.resolve();
  return {files, exit, record: JSON.parse(files.get('/synthetic-output/' +
    (kind.endsWith('.cjs') ? 'deep-tree.json' : 'transitions.json')) || '{}')};
}
function cdpFor(els) {
  return {enumerate: async () => snap(els), sleep: async () => {}, close() {},
    send: async () => {},
    evalJS: async expression => expression.includes('e.click()')
      ? vm.runInNewContext(expression, dom(els)) : true};
}
(async () => {
  await test('input values never enter text or signatures', () => {
    for (const tag of ['INPUT', 'TEXTAREA', 'DIV']) {
      const secret = 'SYNTHETIC_PRIVATE_INPUT';
      const result = snap([element(tag !== 'INPUT' ? secret : '',
        {tag, type: 'password', value: secret, label: 'Field', editable: tag === 'DIV'})]);
      assert(!JSON.stringify(result).includes(secret));
      assert.equal(result.els[0].txt, 'Field');
    }
  });
  await test('route-only navigation is captured even when controls are unchanged', async () => {
    let route = '/';
    const els = ['Overview', 'Details', 'About'].map(t => element(t, {click: () => {route = '/' + t;}}));
    const context = () => ({...dom(els), location: {href: 'https://example.test' + route}});
    const cdp = cdpFor(els);
    cdp.enumerate = async () => vm.runInNewContext(core.ENUM_JS, context());
    cdp.evalJS = async expression => {
      if (expression === 'location.reload()') {route = '/'; return true;}
      return expression.includes('e.click()') ? vm.runInNewContext(expression, context()) : true;
    };
    const result = await run('deep-walk.cjs', cdp);
    assert(result.record.transitions.length >= 3);
    assert(result.record.nodes.some(n => n.url.endsWith('/Details')));
  });
  await test('deep walk never clicks unapproved side effects', async () => {
    const clicks = [];
    const els = ['发送', '购买', '删除'].map(t => element(t, {click: () => clicks.push(t)}));
    const result = await run('deep-walk.cjs', cdpFor(els));
    assert.deepEqual(clicks, []);
    assert.equal(result.record.coverage.complete, false);
    assert(result.record.skipped.length >= 3);
  });
  await test('history entries are never clicked', async () => {
    const clicks = [];
    const els = [element('Private history', {history: true, click: () => clicks.push(60)}),
      element('Help', {x: 130, click: () => clicks.push(190)})];
    const cdp = cdpFor(els);
    cdp.send = async (_, p) => { if (p.type === 'mouseReleased') clicks.push(p.x); };
    await run('competitor-walk.mjs', cdp);
    assert(!clicks.includes(60));
    assert(clicks.includes(190), 'safe navigation must remain usable');
  });
  await test('disappeared controls never fall back to old coordinates', async () => {
    let changed = false;
    const clicks = [];
    const before = [element('Open menu', {click: () => { clicks.push('Open menu'); changed = true; }}),
      element('Help', {x: 130, click: () => clicks.push('Help')}), element('Info', {x: 260, click: () => clicks.push('Info')})];
    const after = [element('Open menu'), element('Delete', {x: 130, click: () => clicks.push('Delete')})];
    const cdp = cdpFor(before);
    cdp.enumerate = async () => snap(changed ? after : before);
    cdp.evalJS = async expression => vm.runInNewContext(expression, dom(changed ? after : before));
    cdp.send = async (_, p) => {
      if (p.type !== 'mouseReleased') return;
      const el = (changed ? after : before).find(e => e.getBoundingClientRect().x + 60 === p.x);
      clicks.push(el?.innerText || 'empty');
      if (el?.innerText === 'Open menu') changed = true;
    };
    await run('competitor-walk.mjs', cdp);
    assert.deepEqual(clicks, ['Open menu']);
  });
  for (const failure of ['reload', 'shot']) await test(failure + ' failure cannot claim completion', async () => {
    const cdp = cdpFor([element('Help')]);
    if (failure === 'reload') cdp.evalJS = async () => { throw new Error('fixture failure'); };
    else cdp.shot = async () => { throw new Error('fixture failure'); };
    const result = await run('deep-walk.cjs', cdp);
    assert.equal(result.record.coverage.complete, false);
    assert.equal(result.record.stat.shots, 0);
    assert.notEqual(result.exit, 0);
    assert(result.record.skipped.some(e => /failure/.test(e.reason)));
  });
  console.log(`${count} probes, ${failures.length} failures`);
  process.exitCode = failures.length ? 1 : 0;
})();
