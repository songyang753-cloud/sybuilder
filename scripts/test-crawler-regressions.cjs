// Offline DOM/CDP probes: never attach to a browser or use a personal profile.
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const os = require('node:os');
const { EventEmitter } = require('node:events');
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
  await test('sweep validates names and forwards exact policy while remaining serial', async () => {
    const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'sybuilder-sweep-test-'));
    try {
      const policy = path.join(temp, 'actions.json'); fs.writeFileSync(policy, '{}');
      const manifest = path.join(temp, 'manifest.json');
      const source = fs.readFileSync(path.join(scripts, 'competitor-sweep.mjs'), 'utf8')
        .replace(/^import .*;\n/gm, '').replaceAll('import.meta.url', JSON.stringify(path.join(scripts, 'competitor-sweep.mjs')));
      async function execute(entries, suffix) {
        fs.writeFileSync(manifest, JSON.stringify(entries));
        const proc = new EventEmitter();
        proc.argv = ['node', 'sweep', manifest, path.join(temp, suffix)];
        proc.execPath = process.execPath; proc.stderr = {write() {}};
        proc.exit = code => { const e = new Error('exit'); e.code = code; throw e; };
        let active = 0, maxActive = 0; const calls = [];
        const spawn = (bin, args) => {
          calls.push({bin, args}); active++; maxActive = Math.max(maxActive, active);
          const child = new EventEmitter(); child.kill = () => {};
          queueMicrotask(() => { active--; child.emit('close', 0); });
          return child;
        };
        let exit = 0;
        try { await vm.runInNewContext('(async()=>{' + source + '\n})()', {
          fs, path, fileURLToPath: x => x, process: proc, spawn, setTimeout, clearTimeout,
          console: {log() {}, error() {}}}); }
        catch (error) { if (error.code !== 2) throw error; exit = error.code; }
        return {calls, maxActive, exit};
      }
      for (const name of ['../escape', '/absolute', '', null]) {
        const r = await execute([{name, port: 9222}], 'rejected');
        assert.equal(r.exit, 2); assert.equal(r.calls.length, 0);
        assert(!fs.existsSync(path.join(temp, 'rejected')));
      }
      const duplicate = await execute([{name:'a',port:9222},{name:'a',port:9223}], 'duplicate');
      assert.equal(duplicate.exit, 2); assert.equal(duplicate.calls.length, 0);
      const r = await execute([{name:'a',port:9222,actions:'actions.json'}, {name:'b',port:9223}], 'valid');
      assert.equal(r.exit, 0); assert.equal(r.calls.length, 2); assert.equal(r.maxActive, 1);
      assert.deepEqual(Array.from(r.calls[0].args.slice(-2)), ['--actions', fs.realpathSync(policy)]);
      assert(!r.calls[1].args.includes('--actions'));
      assert.equal(r.calls[0].bin, process.execPath);
    } finally { fs.rmSync(temp, {recursive:true,force:true}); }
  });
  for (const fault of ['none', 'spawn', 'foreign', 'timeout', 'disconnect', 'exception', 'signal']) {
    await test('owned browser cleanup on ' + fault + ' (simulated transport)', async () => {
      // Run the actual transport implementation with synthetic process/CDP boundaries.
      // Real-browser layout checks remain in _browser.mjs --self-test.
      const browserSource = fs.readFileSync(path.join(scripts, '_browser.mjs'), 'utf8')
        .split('// ---------------------------------------------------------------- 自证')[0]
        .replace(/^import .*;\n/gm, '').replace(/^export /gm, '');
      const proc = new EventEmitter(); proc.pid = 424242; proc.exitCode = null;
      const owner = new EventEmitter(); owner.platform = 'darwin'; owner.env = {};
      const killed = [], removed = [], spawned = [];
      owner.kill = (pid, sig) => killed.push([pid, sig]);
      const temp = '/synthetic-browser-only/pb-owned';
      class Socket {
        static OPEN = 1;
        constructor() { this.readyState = 1; queueMicrotask(() => this.onopen?.()); }
        close() { this.readyState = 3; this.onclose?.(); }
        send(raw) {
          const msg = JSON.parse(raw);
          queueMicrotask(() => {
            if (fault === 'timeout') return;
            if (fault === 'disconnect') return this.close();
            if (fault === 'signal') return owner.emit('SIGTERM');
            const result = msg.method === 'Runtime.evaluate'
              ? fault === 'exception' ? {exceptionDetails:{text:'synthetic exception'}} : {result:{value:2}} : {};
            this.onmessage?.({data:JSON.stringify({id:msg.id,result})});
          });
        }
      }
      const context = {
        process:owner, WebSocket:Socket, URL, AbortSignal,
        existsSync:p => p === '/synthetic-fixture.html' || p.startsWith('/Applications/Google Chrome.app/'),
        readdirSync:() => [], mkdtempSync:() => temp, writeFileSync() {},
        readFileSync:() => '12345\n/devtools/browser/owned\n',
        rmSync:p => removed.push(p), join:path.join, resolve:path.resolve,
        pathToFileURL:require('node:url').pathToFileURL,
        tmpdir:() => '/synthetic-browser-only', homedir:() => '/synthetic-home',
        spawn:(bin,args) => { spawned.push({bin,args}); if (fault === 'spawn') queueMicrotask(() => proc.emit('error',new Error('synthetic spawn failure'))); return proc; },
        fetch:async url => ({json:async () => url.endsWith('/version')
          ? {webSocketDebuggerUrl:'ws://127.0.0.1:12345/devtools/browser/' + (fault==='foreign'?'wrong':'owned')}
          : [{type:'page',url:'file:///synthetic-fixture.html',webSocketDebuggerUrl:'ws://127.0.0.1:12345/devtools/page/owned'}]}),
        setTimeout:(fn,ms) => setTimeout(fn, [150,250,800,900].includes(ms) ? 1 : ms),
        clearTimeout
      };
      const {evalInPage} = vm.runInNewContext(browserSource+'\n;({evalInPage})', context);
      const started = Date.now();
      const result = evalInPage('/synthetic-fixture.html','800x600',['1+1'],{requestTimeoutMs:20,timeoutMs:1500});
      if (fault==='none') assert.deepEqual(Array.from(await result),[2]);
      else await assert.rejects(result);
      assert(Date.now()-started < 2500, 'failure must have a bounded deadline');
      assert.deepEqual(removed,[temp]);
      assert.deepEqual(killed,[[-424242,'SIGTERM'],[-424242,'SIGKILL']]);
      assert.equal(owner.listenerCount('SIGINT'),0); assert.equal(owner.listenerCount('SIGTERM'),0);
      assert(spawned[0].args.includes('--remote-debugging-port=0'));
      assert(spawned[0].args.includes('--remote-debugging-address=127.0.0.1'));
      assert(!spawned[0].args.some(a => a.includes('remote-allow-origins')));
    });
  }
  for (const fault of ['none','spawn','foreign','ambiguous','dialog','timeout','send','error','signal']) {
    await test('capture preserves permission UI and cleans owned resources: '+fault, async () => {
      const source = fs.readFileSync(path.join(scripts,'capture-live-ui.js'),'utf8').replace(/^#![^\n]*\n/,'');
      const owner = new EventEmitter();
      owner.platform='darwin'; owner.env={}; owner.argv=['node','capture','--root','/synthetic-app','--out','/synthetic-output'];
      owner.exit=code => { owner.exitCode=code; };
      const killed=[], removed=[], files=new Map(), commands=[];
      owner.kill=(pid,sig) => killed.push([pid,sig]);
      const child=new EventEmitter(); child.pid=424243;
      child.stdout=new EventEmitter(); child.stderr=new EventEmitter(); child.kill=() => {};
      class Socket extends EventEmitter {
        static OPEN=1;
        constructor() { super(); this.readyState=1; queueMicrotask(()=>this.emit('open')); }
        close() { this.readyState=3; this.emit('close'); }
        terminate() { this.close(); }
        send(raw) {
          const msg=JSON.parse(raw); commands.push(msg);
          if (fault==='send') throw new Error('synthetic send failure');
          queueMicrotask(()=>{
            if (fault==='timeout') return;
            if (fault==='error') return this.emit('error',new Error('synthetic socket error'));
            if (fault==='signal') return owner.emit('SIGTERM');
            let result={};
            if (msg.method==='Target.getTargets') result={targetInfos:Array.from({length:fault==='ambiguous'?2:1},
              (_,i)=>({type:'page',targetId:'page-'+i,url:'https://example.test/'}))};
            if (msg.method==='Target.attachToTarget') result={sessionId:'synthetic-session'};
            if (msg.method==='Page.captureScreenshot') result={data:'YQ=='};
            if (msg.method==='Runtime.evaluate') {
              const e=msg.params.expression;
              assert(!e.includes('.remove()'),'capture must not remove permission overlays');
              result={result:{value:e.includes('querySelectorAll(\'[role=dialog]') ? fault==='dialog'
                : e.includes('const SPEC') ? '{}' : e.includes('return e ?') ? null : '{}'}};
            }
            this.emit('message',JSON.stringify({id:msg.id,result}));
          });
        }
      }
      const fakeFs={existsSync:()=>true,mkdirSync(){},mkdtempSync:()=>'/synthetic-private-profile',
        writeFileSync:(p,b)=>files.set(p,b),rmSync:p=>removed.push(p)};
      const spawn=()=>{
        queueMicrotask(()=>fault==='spawn' ? child.emit('error',new Error('synthetic launch failure'))
          : child.stderr.emit('data','DevTools listening on ws://'+(fault==='foreign'?'203.0.113.1':'127.0.0.1')+':12345/devtools/browser/abcdef'));
        return child;
      };
      await vm.runInNewContext(source,{
        require:n=>n==='child_process'?{spawn}:n==='path'?path:n==='fs'?fakeFs:n==='os'?os:
          n==='./_cdp.js'?core:Socket,
        process:owner,URL,Buffer,console:{log(){},error(){}},
        setTimeout:(fn,ms)=>setTimeout(fn,ms===180000?200:ms===30000?10:ms===15000?100:1),clearTimeout
      });
      assert.equal(owner.exitCode,fault==='none'?undefined:2);
      assert.deepEqual(removed,['/synthetic-private-profile']);
      assert.deepEqual(killed,[[-424243,'SIGTERM'],[-424243,'SIGKILL']]);
      assert.equal(owner.listenerCount('SIGTERM'),0); assert.equal(owner.listenerCount('SIGINT'),0);
      if (fault!=='none') assert.equal(files.size,0,'blocked capture must not manufacture evidence');
      else assert(files.has('/synthetic-output/01-library.png'));
      if (fault==='dialog') assert(!commands.some(c=>c.method==='Page.captureScreenshot'));
    });
  }
  console.log(`${count} probes, ${failures.length} failures`);
  process.exitCode = failures.length ? 1 : 0;
})();
