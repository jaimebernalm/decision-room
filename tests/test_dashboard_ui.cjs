// Durable handoff from the daily composer to the existing HTTP chat contract.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { randomUUID } = require('node:crypto');
const vm = require('node:vm');
const onboardingSource = readFileSync('decision_room/web/static/onboarding.js', 'utf8');
const source = readFileSync('decision_room/web/static/app.js', 'utf8').split('window.addEventListener("hashchange"')[0];
function fixture() {
  const values = new Map(), chats = new Map(), messages = new Map(), calls = [];
  const sandbox = {
    document: { querySelector: () => ({}) }, crypto: { randomUUID }, FormData,
    localStorage: { getItem: k => values.get(k), setItem: (k,v) => values.set(k,v), removeItem: k => values.delete(k) },
    location: { hash: '#home' },
    fetch: async (url, options) => {
      const data = JSON.parse(options.body); calls.push({url, data});
      const records = url === '/api/chats' ? chats : messages;
      if (!records.has(data.request_key)) records.set(data.request_key, {id: randomUUID()});
      if (sandbox.fail === url) { sandbox.fail = null; throw new Error('response lost after persistence'); }
      return {ok:true, json:async () => records.get(data.request_key)};
    }
  };
  vm.createContext(sandbox);
  vm.runInContext(onboardingSource + '\n' + source + '\nstate.business={id:"business-a"}; globalThis.ui={state,store,launchDashboardChat,dashboardSuggestions,shortChatTitle,chatResponse,reportState};', sandbox);
  return {sandbox, ...sandbox.ui, calls, chats, messages, values};
}
test('dashboard creates a chat and sends the original message without CSV', async () => {
  const f=fixture(); f.store.set('dr-home-prompt-business-a','Mi pregunta');
  const chat=await f.launchDashboardChat('Mi pregunta');
  assert.equal(f.sandbox.location.hash, '#chat/'+chat.id);
  assert.equal(f.calls[0].data.analysis_id, '');
  assert.equal(f.calls[1].data.text, 'Mi pregunta');
  assert.equal(f.calls[1].data.business_id, 'business-a');
  assert.equal(f.chats.size,1); assert.equal(f.messages.size,1);
  assert.equal(f.values.has('dr-home-prompt-business-a'),false);
});
test('lost creation response reuses the same chat after a retry', async () => {
  const f=fixture(); f.sandbox.fail='/api/chats';
  await assert.rejects(f.launchDashboardChat('Pregunta'));
  await f.launchDashboardChat('Pregunta');
  assert.equal(f.chats.size,1); assert.equal(f.messages.size,1);
});
test('lost message response reuses both durable identities', async () => {
  const f=fixture(); const realFetch=f.sandbox.fetch;
  let failed=false;
  f.sandbox.fetch=async (url,opts) => {
    if(url.endsWith('/messages') && !failed) {failed=true; f.sandbox.fail=url;}
    return realFetch(url,opts);
  };
  await assert.rejects(f.launchDashboardChat('Pregunta'));
  await f.launchDashboardChat('Pregunta');
  assert.equal(f.chats.size,1); assert.equal(f.messages.size,1);
  assert.equal(f.calls[1].data.request_key,f.calls[2].data.request_key);
  assert.equal(f.calls.filter(c=>c.url==='/api/chats').length,1);
});
test('double submit cannot create duplicate conversations', async () => {
  const f=fixture(); await Promise.all([f.launchDashboardChat('Pregunta'),f.launchDashboardChat('Pregunta')]);
  assert.equal(f.chats.size,1); assert.equal(f.messages.size,1);
});
test('navigation during send cannot redirect a different business or erase new draft', async () => {
  const f=fixture(), original=f.sandbox.fetch;
  f.sandbox.fetch=async (...args) => {
    const result=await original(...args);
    if(args[0]==='/api/chats') {
      f.state.generation++; f.state.business={id:'business-b'};
      f.store.set('dr-home-prompt-business-a','Otro borrador');
      f.sandbox.location.hash='#my-business';
    }
    return result;
  };
  await f.launchDashboardChat('Pregunta');
  assert.equal(f.calls[1].data.business_id,'business-a');
  assert.equal(f.sandbox.location.hash,'#my-business');
  assert.equal(f.store.get('dr-home-prompt-business-a'),'Otro borrador');
});
test('unconfigured model creates no empty conversation', async () => {
  const f=fixture(); f.state.configured=false;
  await assert.rejects(f.launchDashboardChat('Pregunta'), /Configura/);
  assert.equal(f.calls.length,0);
});
test('suggestions reflect available data without inventing metrics', () => {
  const f=fixture(); assert.equal(f.dashboardSuggestions().length,1);
  f.state.datasets={items:[{analysis_id:'a'}]}; assert.equal(f.dashboardSuggestions().length,2);
  f.state.dashboard={report:{title:'Ventas revisadas'}};
  assert.equal(f.dashboardSuggestions().length,2);
});

test('finding context survives a lost send and is not merged with another finding', async () => {
  const f=fixture(), original=f.sandbox.fetch;
  const context={analysis_id:'dataset-v2', finding_reference:{report_id:'review',report_version:'sha',claim_key:'sales'}, label:'Sales'};
  let failed=false;
  f.sandbox.fetch=async (url, opts) => {
    if(url.endsWith('/messages') && !failed) {failed=true;f.sandbox.fail=url;}
    return original(url,opts);
  };
  await assert.rejects(f.launchDashboardChat('Explain this', context));
  await f.launchDashboardChat('Explain this', context);
  assert.equal(f.chats.size,1); assert.equal(f.messages.size,1);
  assert.equal(f.calls[0].data.analysis_id,'dataset-v2');
  assert.deepEqual(f.calls[1].data.finding_reference,context.finding_reference);
  await f.launchDashboardChat('Explain this', {...context, finding_reference:{...context.finding_reference,claim_key:'cost'}});
  assert.equal(f.chats.size,2);
});
test('chat titles are short without losing the full submitted question', async () => {
  const f=fixture(), question='Analiza las ventas de septiembre y compara los resultados de cada una de las categorías disponibles.';
  await f.launchDashboardChat(question);
  assert.ok(f.calls[0].data.title.length <= 64);
  assert.equal(f.calls[1].data.text,question);
  assert.ok(f.calls[0].data.title.endsWith('…'));
});
test('chat renders reviewed labels and formatting instead of raw metrics', () => {
  const f=fixture();
  const html=f.chatResponse({kind:'evidence',title:'Ventas',metrics:[{metric:'technical_total_eur',value:'1255.0000000000'}],highlights:[{label:'Ventas netas',value:'1.255,00',unit:'EUR'}],scope:{},claims:[],charts:[],limitations:[]});
  assert.ok(html.includes('Ventas netas'));assert.ok(html.includes('1.255,00'));
  assert.ok(!html.includes('technical_total_eur'));assert.ok(!html.includes('1255.0000000000'));
});
test('withdrawn reports are distinct from pending and historical reports', () => {
  const f=fixture();
  assert.equal(f.reportState({status:'blocked',presentation_status:'withdrawn'}),'withdrawn');
  assert.equal(f.reportState({status:'completed',data_version:{superseded_by:'v3'}}),'historical');
  assert.equal(f.reportState({status:'waiting'}),'waiting');
});
test('first access keeps onboarding in place until a business is saved', async () => {
  const f=fixture(); let timers=0;
  f.sandbox.clearInterval=()=>{};
  f.sandbox.setInterval=()=>{timers++;};
  f.sandbox.window={scrollTo:()=>{}};
  f.sandbox.document={querySelector:()=>({setAttribute:()=>{},focus:()=>{}})};
  f.sandbox.fetch=async url => ({ok:true,json:async()=>url==='/api/workspace' ? {analyses:[],configured:false,business:null,businesses:[],memory:{}} : {business_id:null,conversations:[],datasets:{items:[]}}});
  vm.runInContext('onboardingBusiness = () => {globalThis.onboarded=true;}; globalThis.runRoute=route;',f.sandbox);
  await f.sandbox.runRoute();
  assert.equal(f.sandbox.onboarded,true);
  assert.equal(timers,0);
});

test('public entry opens the landing and the access link opens local login', async () => {
  const f=fixture();
  f.sandbox.clearInterval=()=>{};
  f.sandbox.document={querySelector:selector=>selector==='#reconnect' ? null : {setAttribute:()=>{},focus:()=>{}}};
  vm.runInContext(`api=async()=>{throw Object.assign(new Error('Access required'),{status:401})};
    landing=()=>{globalThis.screen='landing'}; login=()=>{globalThis.screen='login'};
    globalThis.runRoute=route;`,f.sandbox);
  await f.sandbox.runRoute();
  assert.equal(f.sandbox.screen,'landing');
  f.sandbox.location.hash='#login';
  await f.sandbox.runRoute();
  assert.equal(f.sandbox.screen,'login');
});

test('a saved business opens the current dashboard', async () => {
  const f=fixture();
  f.sandbox.clearInterval=()=>{};
  f.sandbox.setInterval=()=>{};
  f.sandbox.window={scrollTo:()=>{}};
  f.sandbox.document={querySelector:()=>({setAttribute:()=>{},focus:()=>{},textContent:''})};
  vm.runInContext(`api=async path=>path==='/api/workspace'
      ? {analyses:[],configured:false,business:{id:'business-a'},businesses:[],memory:{}}
      : path==='/api/chats' ? {business_id:'business-a',conversations:[],datasets:{items:[]}}
      : {selected_id:null,report:null};
    dashboardHome=()=>{globalThis.screen='dashboard'}; globalThis.runRoute=route;`,f.sandbox);
  await f.sandbox.runRoute();
  assert.equal(f.sandbox.screen,'dashboard');
});

test('a new business stays in the separate onboarding until its report is complete', async () => {
  const f=fixture();
  f.sandbox.clearInterval=()=>{};
  f.sandbox.setInterval=()=>{};
  f.sandbox.window={scrollTo:()=>{}};
  f.sandbox.document={querySelector:()=>({setAttribute:()=>{},focus:()=>{},textContent:''})};
  f.sandbox.fetch=async url => ({ok:true,json:async()=>url==='/api/workspace'
    ? {analyses:[],configured:true,business:{id:'business-a'},businesses:[],
       onboarding:{job_id:null,completed:false},memory:{}}
    : {business_id:'business-a',conversations:[],datasets:{items:[]}}});
  vm.runInContext('onboardingData=()=>{globalThis.screen="onboarding-data"}; dashboardHome=()=>{globalThis.screen="dashboard"}; globalThis.runRoute=route;',f.sandbox);
  await f.sandbox.runRoute();
  assert.equal(f.sandbox.screen,'onboarding-data');
});

test('unknown is exclusive and an old answer is not restored beside it', () => {
  const f=fixture();
  const html=vm.runInContext('answerFields({options:["Total de la fila"]},{text:"Total de la fila",disposition:"unknown"})',f.sandbox);
  assert.match(html,/type="radio" name="option" value="unknown" id="unknown" checked/);
  assert.doesNotMatch(html,/type="checkbox" id="unknown"/);
  assert.doesNotMatch(html,/<textarea[^>]*>Total de la fila<\/textarea>/);
  assert.doesNotMatch(html,/value="0" data-answer-option checked/);
  const selected=vm.runInContext('answerFields({options:["Total de la fila"]},{text:"Total de la fila",optionIndex:0,disposition:"answered"})',f.sandbox);
  assert.match(selected,/value="0" data-answer-option checked/);
  assert.doesNotMatch(selected,/<textarea[^>]*>Total de la fila<\/textarea>/);
});

test('data context highlights only columns explicitly named by the question', () => {
  const f=fixture();
  const indices=vm.runInContext('referencedColumns({text:"¿Qué representa ventas_eur?",reason:"Afecta al total"},["id","ventas_eur","total_ventas"])',f.sandbox);
  assert.deepEqual(Array.from(indices),[1]);
  const cited=vm.runInContext('referencedColumns({text:"¿Precio unitario o total de fila?",references:[{kind:"column",column:"amount"}]},["quantity","amount"])',f.sandbox);
  assert.deepEqual(Array.from(cited),[1]);
});
