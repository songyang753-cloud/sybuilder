#!/usr/bin/env node
// Reproducible local teaching evidence, never a receipt for a live product or platform.
'use strict';
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {pathToFileURL}=require('node:url');
const {spawn}=require('node:child_process');
const {createHash}=require('node:crypto');
const assert=require('node:assert/strict');
const {connect,sleep,reclaim}=require('../../../scripts/_cdp.js');
const hash=p=>createHash('sha256').update(fs.readFileSync(p)).digest('hex');
async function main(){
  assert(process.argv.length===4&&process.argv[2]==='--out','Usage: node capture.cjs --out <new-evidence-directory>');
  const out=path.resolve(process.argv[3]);
  assert(!fs.existsSync(out),'Choose a new directory; existing evidence is never overwritten');
  const {findChrome}=await import('../../../scripts/_browser.mjs');
  const chrome=await findChrome();assert(chrome,'UNABLE: Chrome unavailable');
  const profile=fs.mkdtempSync(path.join(os.tmpdir(),'sybuilder-writing-demo-'));
  const child=spawn(chrome,['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check',
    '--remote-debugging-port=0',`--user-data-dir=${profile}`,pathToFileURL(path.join(__dirname,'demo.html')).href],{stdio:'ignore'});
  let c,port,spawnError;child.on('error',error=>{spawnError=error;});
  try{
    const portFile=path.join(profile,'DevToolsActivePort');
    for(let i=0;i<100&&!fs.existsSync(portFile);i++){if(spawnError)throw spawnError;if(child.exitCode!==null)throw Error('UNABLE: browser exited before initialization');await sleep(100);}
    assert(fs.existsSync(portFile),'UNABLE: browser did not expose a debugging port');
    port=Number(fs.readFileSync(portFile,'utf8').split('\n')[0]);
    c=await connect(port,{pick:'demo.html',minEls:3,tries:5});
    await c.send('Emulation.setDeviceMetricsOverride',{width:1100,height:1100,deviceScaleFactor:1,mobile:false});
    fs.mkdirSync(out,{recursive:true});
    const events=[];
    const click=sel=>c.evalJS(`document.querySelector(${JSON.stringify(sel)}).click()`);
    const type=value=>c.evalJS(`document.getElementById('name').value=${JSON.stringify(value)}`);
    async function check(id,action,condition,imageName){
      assert.equal(await c.evalJS(condition),true,`Behavior changed: ${id}`);
      const event={id,action,assertion:condition,result:'PASS'};
      if(imageName){
        await c.evalJS('document.fonts.ready.then(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))))');
        assert.equal(await c.evalJS('document.documentElement.scrollHeight<=innerHeight'),true,'UNABLE: screenshot would crop content; enlarge viewport before recapture');
        await c.shot(path.join(out,imageName));event.image=imageName;event.sha256=hash(path.join(out,imageName));
      }
      events.push(event);
    }
    await check('E01','打开教学应用',"document.querySelectorAll('.row').length===1",'initial.png');
    await click('#new');await type('   ');await click('#save');
    await check('E02','仅空白名称保存',"document.getElementById('error').textContent==='请输入任务名称' && items.length===1 && document.getElementById('name').value==='   '",'create-error.png');
    await type('一'.repeat(21));await click('#save');
    await check('E03','21 字名称保存',"document.getElementById('error').textContent==='任务名称不能超过 20 个字符' && items.length===1");
    await type('一'.repeat(20));await click('#save');
    await check('E04','20 字名称保存',"items.length===2 && items[1].name.length===20");
    await click('#new');await type(' 放弃的输入 ');await click('#cancel');await click('#new');
    await check('E05','取消后重新打开新建',"items.length===2 && document.getElementById('name').value===''");
    await type(' 核对需求 ');await click('#save');
    await check('E06','去空白后同名保存',"document.getElementById('error').textContent==='进行中已有同名任务' && items.length===2");
    await type(' 整理截图 ');await click('#save');
    await check('E07','带首尾空白名称保存',"items.length===3 && items[2].name==='整理截图' && document.getElementById('editor').hidden",'create-success.png');
    await click('[data-id="3"] [data-action="rename"]');await type('核对需求');await click('#save');
    await check('E08','重命名为另一进行中任务名',"items[2].name==='整理截图' && document.getElementById('error').textContent==='进行中已有同名任务'",'rename-error.png');
    await click('#cancel');await click('[data-id="3"] [data-action="rename"]');
    await check('E09','取消重命名后再打开',"document.getElementById('name').value==='整理截图'");
    await type('整理截图');await click('#save');
    await check('E10','保存自己的原名',"document.getElementById('editor').hidden && items[2].name==='整理截图'");
    await click('[data-id="3"] [data-action="rename"]');await type('整理图文');await click('#save');
    await check('E11','合法重命名',"items[2].name==='整理图文' && items.length===3",'rename-success.png');
    await click('[data-id="3"] [data-action="archive"]');
    await check('E12','归档进行中任务',"items[2].archived && !document.querySelector('[data-id=\"3\"]')",'archive-result.png');
    await click('#archived');
    await check('E13','在归档列表定位任务',"document.querySelector('[data-id=\"3\"] span').textContent==='整理图文'",'archive-list.png');
    await click('#new');await type('整理图文');await click('#save');
    await check('E14','已归档名称可被新任务使用',"items.length===4 && items[3].name===items[2].name && !items[3].archived");
    await click('#archived');await click('[data-id="3"] [data-action="restore"]');
    await check('E15','同名恢复冲突',"items[2].archived && document.getElementById('notice').textContent.includes('恢复失败')",'restore-error.png');
    await click('#active');await click('[data-id="4"] [data-action="rename"]');await type('整理图文第二版');await click('#save');
    await click('#archived');await click('[data-id="3"] [data-action="restore"]');
    await check('E16','冲突解除后恢复',"!items[2].archived && document.getElementById('list').textContent==='这里还没有任务'",'restore-result.png');
    await click('#active');
    await check('E17','进行中查看恢复结果',"document.querySelector('[data-id=\"3\"] span').textContent==='整理图文'",'restore-active.png');
    await c.send('Page.reload');await sleep(150);
    await check('E18','刷新后检查持久化',"items.length===1 && items[0].name==='核对需求'");
    const record={kind:'local-teaching-browser-evidence',source:'demo.html',sourceSha256:hash(path.join(__dirname,'demo.html')),
      browser:(await c.send('Browser.getVersion')).product,viewport:{width:1100,height:1100},events};
    fs.writeFileSync(path.join(out,'evidence.json'),JSON.stringify(record,null,2)+'\n');
    console.log(`PASS: ${events.length} real local browser checks; ${events.filter(e=>e.image).length} screenshots. Not live-product or cloud-delivery approval.`);
  }finally{
    if(c)c.close();
    if(c){const cleanup=await reclaim(child,port,true);assert(cleanup.ok,cleanup.why);}
    else if(child.pid&&child.exitCode===null&&child.signalCode===null){child.kill('SIGTERM');await sleep(1200);assert(child.exitCode!==null||child.signalCode!==null,'UNABLE: owned browser did not exit');}
    fs.rmSync(profile,{recursive:true,force:true});
  }
}
main().catch(e=>{console.error(e.message);process.exitCode=1;});
