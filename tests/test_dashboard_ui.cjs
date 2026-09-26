// Durable handoff from the daily composer to the existing HTTP chat contract.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { randomUUID } = require('node:crypto');
const vm = require('node:vm');
const source = readFileSync('decision_room/web/static/app.js', 'utf8').split('window.addEventListener("hashchange"')[0];
function fixture() {
  const values = new Map(), chats = new Map(), messages = new Map(), calls = [];
  const sandbox = {
    document: { querySelector: () => ({}), addEventListener: () => {} }, crypto: { randomUUID }, FormData,
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
  vm.runInContext(source + '\nstate.business={id:"business-a"}; globalThis.ui={state,store,launchDashboardChat,dashboardSuggestions,shortChatTitle,chatResponse,reportState,scrollToChatTurn,sidebarHistoryMarkup,chatQueuePosition,deleteChat};', sandbox);
  return {sandbox, ...sandbox.ui, calls, chats, messages, values};
}
test('sending follows the pending assistant card above the fixed composer', () => {
  const f=fixture(), moves=[];
  const owner={getBoundingClientRect:()=>({top:700,bottom:780,height:80})};
  const reply={getBoundingClientRect:()=>({top:800,bottom:900,height:100})};
  const turn={querySelector:selector=>selector==='.chat-answer'?reply:owner};
  f.sandbox.document.querySelector=selector=>
    selector==='[data-chat-turn="new-turn"]'?turn:
    selector==='.chat-composer'?{getBoundingClientRect:()=>({top:760})}:
    selector==='.topbar'?{getBoundingClientRect:()=>({bottom:0})}:null;
  f.sandbox.innerHeight=1000;
  f.sandbox.scrollY=0;
  f.sandbox.scrollTo=options=>moves.push(options);
  f.sandbox.matchMedia=()=>({matches:false});
  f.scrollToChatTurn('new-turn');
  assert.equal(moves.length,1);
  assert.equal(moves[0].top,158);
  assert.equal(moves[0].behavior,'smooth');
});
test('the current chat is highlighted without moving an older chat into the recent order', () => {
  const f=fixture();
  f.state.chats=Array.from({length:7},(_,index)=>({id:`chat-${index+1}`,title:`Chat ${index+1}`}));
  f.sandbox.location.hash='#chat/chat-7';
  const html=f.sidebarHistoryMarkup();
  assert.ok(html.indexOf('href="#chat/chat-1"') < html.indexOf('href="#chat/chat-6"'));
  assert.ok(html.indexOf('href="#chat/chat-6"') < html.indexOf('CHAT ACTUAL'));
  assert.match(html,/class="history-row is-current"[^]*href="#chat\/chat-7"[^]*aria-current="page"/);
  f.sandbox.location.hash='#home';
  assert.doesNotMatch(f.sidebarHistoryMarkup(),/aria-current="page"/);
});
test('a lone queued message is not shown as waiting behind an old result', () => {
  const f=fixture();
  for (const status of ['completed','stale','failed','blocked','waiting'])
    assert.equal(f.chatQueuePosition([{status},{status:'queued'}],1),0);
  assert.equal(f.chatQueuePosition([{status:'queued'}],0),0);
  assert.equal(f.chatQueuePosition([{status:'processing'},{status:'queued'}],1),1);
  assert.equal(f.chatQueuePosition([{status:'processing'},{status:'queued'},{status:'queued'}],2),2);
});
test('deleting a chat waits for the in-app dialog and cancel sends no request', async () => {
  const f=fixture(), dialogs=[];
  f.state.chats=[{id:'chat-1',title:'Chat <privado>'}];
  f.sandbox.location.hash='#chat/chat-1';
  f.sandbox.document.body={append:()=>{}};
  f.sandbox.document.createElement=()=>{
    const handlers={};
    const dialog={
      returnValue:'', innerHTML:'', className:'',
      setAttribute:()=>{}, addEventListener:(name,callback)=>{handlers[name]=callback;},
      showModal:()=>{}, querySelector:()=>({focus:()=>{}}), remove:()=>{},
      close(value){this.returnValue=value;handlers.close();},
    };
    dialogs.push(dialog);
    return dialog;
  };
  const cancelled=f.deleteChat('chat-1');
  assert.equal(f.calls.length,0);
  assert.ok(dialogs[0].innerHTML.includes('Chat &lt;privado&gt;'));
  assert.ok(dialogs[0].innerHTML.includes('no podrás volver a acceder'));
  assert.ok(!dialogs[0].innerHTML.includes('recuperar'));
  dialogs[0].close('cancel');
  assert.equal(await cancelled,false);
  assert.equal(f.calls.length,0);
  const approved=f.deleteChat('chat-1');
  assert.equal(f.calls.length,0);
  dialogs[1].close('delete');
  assert.equal(await approved,true);
  assert.equal(f.calls.filter(call=>call.url==='/api/chats/chat-1/delete').length,1);
  assert.equal(f.sandbox.location.hash,'#chats');
});
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
  const html=f.chatResponse({kind:'evidence',title:'Ventas',paragraphs:['Se suman los importes <sin repetir filas>.'],metrics:[{metric:'technical_total_eur',value:'1255.0000000000'}],highlights:[{label:'Ventas netas',value:'1.255,00',unit:'EUR'}],scope:{},claims:[],charts:[],limitations:[]});
  assert.ok(html.includes('Ventas netas'));assert.ok(html.includes('1.255,00'));
  assert.ok(!html.includes('technical_total_eur'));assert.ok(!html.includes('1255.0000000000'));
  assert.ok(html.indexOf('Se suman los importes &lt;sin repetir filas&gt;') < html.indexOf('<details'));
  assert.ok(html.includes('<details class="chat-evidence"><summary>Ver datos y evidencia</summary>'));
});
test('memory answer reads naturally and does not add a technical empty-state paragraph', () => {
  const f=fixture();
  const empty=f.chatResponse({kind:'memory',text:'He revisado la información y aún no encuentro nada.',items:[]});
  assert.ok(empty.includes('He revisado'));
  assert.ok(!empty.includes('hechos declarados'));
  const facts=f.chatResponse({kind:'memory',text:'Esto es lo que sé:',items:[{status:'declared',content:{statement:'Cerramos los domingos.',scope:'business'}}]});
  assert.ok(facts.includes('Cerramos los domingos.'));
  assert.ok(!facts.includes('Declarado'));
  const previous=f.chatResponse({kind:'memory',text:'El mensaje está guardado. Estos son los recuerdos aplicables y su estado.',items:[]});
  assert.ok(previous.includes('En ese momento'));
  assert.ok(!previous.includes('recuerdos aplicables'));
});
test('an earlier greeting does not display a memory dump', () => {
  const f=fixture(); f.state.business.name='Papelería Bruma';
  const html=f.chatResponse({kind:'memory',text:'Esto es lo que me has contado sobre Papelería Bruma:',items:[{status:'declared',content:{statement:'Vende cuadernos.',scope:'business'}}]},'response','hola');
  assert.ok(html.includes('¡Hola!'));
  assert.ok(html.includes('Papelería Bruma'));
  assert.ok(!html.includes('Vende cuadernos'));
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
  vm.runInContext('businessForm = () => {globalThis.onboarded=true;}; globalThis.runRoute=route;',f.sandbox);
  await f.sandbox.runRoute();
  assert.equal(f.sandbox.onboarded,true);
  assert.equal(timers,0);
});

test('agent prose formats paragraphs and lists while escaping all model HTML', () => {
  const f = fixture();
  const html = f.chatResponse({kind:'grounded_answer', text:'**Ventas** y `importe`\n\n- <img src=x onerror=alert(1)>\n- Segundo dato', sources:[{label:'<script>bad</script>'}]});
  assert.match(html, /<strong>Ventas<\/strong>/);
  assert.match(html, /<code>importe<\/code>/);
  assert.match(html, /<ul><li>&lt;img/);
  assert.doesNotMatch(html, /<img|<script/);
});
