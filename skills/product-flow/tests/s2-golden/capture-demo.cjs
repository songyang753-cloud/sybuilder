// Reproducible local GUI evidence only, never competitor or cloud evidence.
const {spawn}=require('node:child_process');
const fs=require('node:fs'), os=require('node:os'), path=require('node:path');
const {pathToFileURL}=require('node:url');
async function main(){
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'sybuilder-gui-fixture-'));
  const chrome=process.env.CHROME_BIN||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  const child=spawn(chrome,['--headless=new','--no-first-run','--disable-gpu','--remote-debugging-port=0','--user-data-dir='+folder,'--window-size=1100,800','about:blank'],{stdio:'ignore'});
  let socket;
  try {
    const active=path.join(folder,'DevToolsActivePort');
    for(let i=0;i<100&&!fs.existsSync(active);i++) await new Promise(r=>setTimeout(r,100));
    if(!fs.existsSync(active)) throw Error('Chrome did not start');
    const port=fs.readFileSync(active,'utf8').split('\n')[0];
    const tabs=await (await fetch('http://127.0.0.1:'+port+'/json/list')).json();
    const tab=tabs.find(t=>t.type==='page');
    socket=new WebSocket(tab.webSocketDebuggerUrl);
    await new Promise((r,j)=>{socket.onopen=r;socket.onerror=j;});
    let serial=0;
    const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++serial;const timer=setTimeout(()=>{socket.removeEventListener('message',listener);reject(Error('CDP timeout'));},5000);function listener(e){const v=JSON.parse(e.data);if(v.id!==id)return;clearTimeout(timer);socket.removeEventListener('message',listener);v.error?reject(Error(v.error.message)):resolve(v.result);}socket.addEventListener('message',listener);socket.send(JSON.stringify({id,method,params}));});
    await call('Page.enable'); await call('Page.navigate',{url:pathToFileURL(path.join(__dirname,'demo.html')).href});
    const evaluate=expression=>call('Runtime.evaluate',{expression,returnByValue:true});
    for(let i=0;i<40;i++){const v=await evaluate('document.readyState');if(v.result.value==='complete')break;await new Promise(r=>setTimeout(r,50));}
    await evaluate('document.querySelector("#create").click()');
    if((await evaluate('document.querySelector("#result").textContent')).result.value!=='请输入任务名称')throw Error('required-name branch failed');
    await evaluate('document.querySelector("#name").value="整理需求"; document.querySelector("#create").click()');
    if((await evaluate('document.querySelector("#tasks").textContent')).result.value!=='整理需求')throw Error('create branch failed');
    const image=await call('Page.captureScreenshot',{format:'png'});
    fs.writeFileSync(path.join(__dirname,'shot.png'),Buffer.from(image.data,'base64'));
    console.log('PASS: real local browser click + validation/recovery + screenshot; not a competitor claim');
  } finally {
    if(socket)socket.close();
    child.kill('SIGTERM');
    await new Promise(r=>{if(child.exitCode!==null||child.signalCode!==null)return r();const timer=setTimeout(()=>child.kill('SIGKILL'),2000);child.once('exit',()=>{clearTimeout(timer);r();});});
    fs.rmSync(folder,{recursive:true,force:true});
  }
}
main().catch(e=>{console.error('UNABLE: '+e.message);process.exitCode=2;});
