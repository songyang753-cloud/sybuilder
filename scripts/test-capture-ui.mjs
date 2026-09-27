// Real local Chromium fixture. No account, personal profile, or external website.
import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,rmSync} from 'node:fs';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {createRequire} from 'node:module';
import {evalInPage} from '../skills/product-flow/scripts/_browser.mjs';
const require=createRequire(import.meta.url);
const core=require('../skills/product-flow/scripts/_cdp.js');
const dir=mkdtempSync(join(tmpdir(),'sybuilder-capture-fixture-'));
try {
  const file=join(dir,'fixture.html');
  writeFileSync(file,`<!doctype html><title>SYNTHETIC_PRIVATE_PAGE</title>
    <style>.modal{position:fixed;left:20px;top:100px;width:300px;height:200px;background:white;z-index:10}</style>
    <div class="history"><button class="nav-item">SYNTHETIC_PRIVATE_TITLE</button></div>
    <button class="nav-item" id="search">Search</button>
    <div class="modal" role="dialog" style="visibility:hidden">Synthetic consent</div>`);
  const results=await evalInPage(file,'900x700',[
    core.VISIBLE_DIALOG_JS,
    `document.querySelector('.modal').style.cssText='opacity:0';${core.VISIBLE_DIALOG_JS}`,
    `document.querySelector('.modal').style.cssText='left:-1000px';${core.VISIBLE_DIALOG_JS}`,
    `document.querySelector('.modal').style.cssText='';${core.VISIBLE_DIALOG_JS}`,
    core.PRIVATE_NAV_JS,
    core.clickSelectorExpression('#search'),
    core.clickSelectorExpression('#missing')
  ]);
  assert.deepEqual(results.slice(0,4),[false,false,false,true]);
  assert(!JSON.stringify(results[4]).includes('SYNTHETIC_PRIVATE'));
  assert.equal(results[5].status,'BLOCKED');
  assert.equal(results[6].status,'ABSENT');
  console.log('PASS: real-browser hidden/transparent/offscreen/visible dialogs, privacy, blocked vs absent');
} finally {rmSync(dir,{recursive:true,force:true});}
