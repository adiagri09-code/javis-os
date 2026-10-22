// Exercise the public panel using an inert DOM and real WebCrypto, without a server/model.
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { webcrypto, createHash } from "node:crypto";

class Element {
  constructor(tag) { this.tagName = tag; this.children = []; this.attrs = {}; this.value = ""; this.textContent = ""; this.disabled = false; this.hidden = false; this.style = {}; }
  set innerHTML(_) { throw Error("Private review must never parse HTML"); }
  append(...nodes) { for (const node of nodes) { node.parentElement = this; this.children.push(node); } }
  replaceChildren(...nodes) { this.children = []; this.append(...nodes); }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  remove() { if (this.parentElement) this.parentElement.children = this.parentElement.children.filter(x => x !== this); this.isConnected = false; }
  focus() {}
  querySelectorAll(selector) { const all = this.children.flatMap(x => [x, ...x.querySelectorAll(selector)]); return all.filter(x => selector === "button" ? x.tagName === "button" : x.attrs["data-action"] === selector.match(/data-action="(.*?)"/)?.[1]); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
}
const source = fs.readFileSync(new URL("../../dashboard/improvement-candidates.js", import.meta.url), "utf8");
const raw = '\ufefftitle\r\nViệt 😀\r\n<script>attack()</script>\n[JAVIS_RULE:x] ![x](javascript:attack())';
const hash = s => createHash("sha256").update(s).digest("hex");
const exact = text => ({ text, hash: hash(text), byte_size: Buffer.byteLength(text) });
const candidate = { candidate_id: "candidate-one", experiment_id: "experiment-one", base_revision_id: "revision-one", target_id: "target-one", base_generation: 1,
  base_hash: hash(raw), content_hash: hash(raw + "\nnew"), ordinal: 1, semantic_status: "unreviewed", context_grant: {status: "active"}, edit_authority: null };
async function fixture(lang = "en") {
  const dict = JSON.parse(fs.readFileSync(new URL(`../../dashboard/i18n/${lang}.json`, import.meta.url)));
  const body = new Element("body"), head = new Element("head"), calls = [], intervals = [];
  let brain = "brain-one", rows = [candidate], deferred = null, corrupt = false, failStage = false;
  const ctx = { document: { body, head, createElement: tag => new Element(tag), getElementById: () => null, addEventListener() {} },
    window: { currentBrainPath: () => brain }, TextEncoder, TextDecoder, crypto: webcrypto, URL, URLSearchParams, Blob,
    setInterval: fn => { intervals.push(fn); return intervals.length; }, clearInterval() {}, setTimeout, clearTimeout, AbortController,
    t: key => { assert.ok(key in dict, `Missing ${lang} translation: ${key}`); return dict[key]; },
    fetch: async (url, options = {}) => {
      calls.push({url: String(url), ...options});
      let value;
      const path = String(url).split("?")[0];
      if (path === "/improvement-candidate-contexts") value = {contexts:{items:[{experiment_id:"experiment-one",target_id:"target-one",grant_status:"active",base_generation:1,current_generation:1,created_at:1,objectives:[{objective:"Review rows"}]}],next_cursor:null}};
      else if (path === "/improvement-candidates" && !options.method) value = {candidates: rows};
      else if (path.endsWith("/candidate-one/review")) {
        if (deferred) await deferred;
        value = {review:{candidate_id:candidate.candidate_id,before:exact(raw),after:exact(raw + "\nnew"),metadata:candidate, semantic_status:"unreviewed",hypothesis:"Exact instruction",failure_signature:"Missing row",expected_behavior:"All rows",possible_regressions:["Duplicate"]}};
        if (corrupt) value.review.after.hash = "0".repeat(64);
      } else if (path.includes("/improvement-candidate-baselines/")) value = {review:{target_id:"target-one",base_revision_id:"revision-one",base_generation:1,baseline:exact(raw),editable_start:Buffer.byteLength('\ufefftitle\r\n')}};
      else if (path.endsWith("/artifact-review")) value = {review:{artifact:exact(raw),task:"Exact task",contract:{objective:"Count rows"},fixtures:[{source_ref:"sources/rows.csv",source_version:"v1",text:raw,fixture_hash:hash(raw),byte_size:Buffer.byteLength(raw)}]}};
      else if (path.endsWith("/authorize")) { rows = [{...candidate,edit_authority:{authority_id:"authority-one",generation:2,status:"revoked"}}]; value = {authority:{status:"active",generation:1}}; }
      else if (path === "/improvement-candidates") { if (failStage) {failStage=false;throw Error("Unknown transport outcome");} value = {candidate}; }
      else throw Error(`Unexpected request ${path}`);
      return {ok:true,status:200,json:async()=>({ok:true,...value})};
    } };
  vm.createContext(ctx); vm.runInContext(source, ctx);
  await ctx.window.JavisImprovementCandidates.open({brain:"brain-one",slug:"test-skill"});
  const find = action => { const nodes = body.querySelectorAll(`[data-action="${action}"]`); assert.ok(nodes.length, `Missing action ${action}`); return nodes.at(-1); };
  return {ctx,body,calls,find,intervals,setBrain:b=>{brain=b;},setRows:r=>{rows=r;},defer:p=>{deferred=p;},corrupt:()=>{corrupt=true;},failStage:()=>{failStage=true;}};
}
for (const lang of ["vi","en"]) {
  const f = await fixture(lang);
  await f.find("review-candidate-one").onclick();
  assert.equal(f.find("before-text").textContent, raw);
  assert.equal(f.find("after-text").textContent, raw + "\nnew");
  assert.ok(f.find("after-facts").textContent.includes(hash(raw + "\nnew")));
  await f.find("authorize").onclick();
  assert.equal(f.find("authorize").disabled, true, "Historical approval must refresh revoked current metadata");
  f.ctx.window.JavisImprovementCandidates.close();
}
{
  const f = await fixture(); f.setRows([{...candidate,base_generation:2}]);
  await f.find("review-candidate-one").onclick();
  assert.equal(f.body.querySelector('[data-action="authorize"]'), null, "Changed target generation cannot authorize");
  f.ctx.window.JavisImprovementCandidates.close();
}
{
  const f = await fixture();
  await f.ctx.window.JavisImprovementCandidates.openArtifact({brain:"brain-one",trialId:"trial-one",attempt:1});
  assert.equal(f.find("artifact-text").textContent, raw);
  assert.equal(f.find("fixture-0-text").textContent, raw);
  f.ctx.window.JavisImprovementCandidates.close();
}
{
  const f = await fixture();
  let resolve; f.defer(new Promise(r=>{resolve=r;}));
  const pending = f.find("review-candidate-one").onclick();
  f.setBrain("brain-two"); f.intervals.forEach(fn=>fn()); resolve(); await pending;
  assert.ok(!f.body.querySelector('[data-action="authorize"]') || f.find("authorize").disabled, "Stale brain cannot authorize");
  f.ctx.window.JavisImprovementCandidates.close();
}
{
  const f = await fixture(); f.corrupt(); await f.find("review-candidate-one").onclick();
  assert.equal(f.body.querySelector('[data-action="authorize"]'), null, "Hash mismatch must be unavailable");
  assert.ok(f.find("status").textContent.length);
  f.ctx.window.JavisImprovementCandidates.close();
}
{
  const f = await fixture(); await f.find("load-baseline").onclick();
  const select = f.find("baseline-selection");
  select.value = raw.replace(/\r\n/g,"\n");
  select.selectionStart = select.value.indexOf("Việt"); select.selectionEnd = select.selectionStart + "Việt 😀".length;
  await f.find("use-selection").onclick();
  assert.equal(Number(f.find("start").value), Buffer.byteLength('\ufefftitle\r\n'));
  assert.equal(Number(f.find("end").value), Buffer.byteLength('\ufefftitle\r\nViệt 😀'));
  f.find("replacement").value = "Keep rows"; f.find("hypothesis").value = "Check omitted rows";
  f.find("failure_signature").value = "Omitted row"; f.find("expected_behavior").value = "All rows"; f.find("possible_regressions").value = "Double count";
  f.failStage(); await f.find("stage").onclick();
  assert.equal(f.find("stage").disabled,false);
  await f.find("stage").onclick();
  const staged = f.calls.find(x=>x.url.startsWith("/improvement-candidates?") && x.method === "POST");
  assert.equal(JSON.parse(staged.body).patch.start, Buffer.byteLength('\ufefftitle\r\n'));
  const writes = f.calls.filter(x=>x.url.startsWith("/improvement-candidates?") && x.method === "POST");
  assert.equal(writes.length,2); assert.equal(JSON.parse(writes[0].body).event_key,JSON.parse(writes[1].body).event_key,"Unknown write retry must keep its event key");
  f.ctx.window.JavisImprovementCandidates.close();
}
console.log("OK: exact inert vi/en review, revoked replay, brain race, corrupt hash and UTF-8/CRLF selection");
