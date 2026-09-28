import { it,expect,vi } from 'vitest';
import { render,screen,waitFor,act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AnalysisActivity } from './analysis-activity';
import { useActivity, type Activity } from '@/lib/activity';
import App from '@/App';
const task={id:'task',parent_id:null,status:'completed',text:'Comparación por producto completada',purpose:'Entender la evolución de los productos',kind:'execution',sequence:2,references:[{kind:'column',id:'table',column:'unidades'}],data_endpoint:'/api/jobs/job/data',started_at:'2026-09-28T12:00:00Z',finished_at:'2026-09-28T12:00:01Z'};
const page:Activity={schema_version:1,trace_id:'trace',status:'completed',headline:'Análisis completado · Ver proceso',terminal:true,history_complete:true,task_updates:[task],active_tasks:[],events:[{id:'event',task_id:'task',sequence:2,type:'execution.completed',status:'completed',recorded_at:'2026-09-28T12:00:01Z',reconstructed:false}],next_cursor:'trace:2',previous_cursor:null,has_more:false,worker_health:'idle'};
function response(data:unknown,status=200) {return new globalThis.Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}});}
it('keeps completed history, keyboard disclosure and related data in the conversation',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>url.startsWith('/api/jobs/job/data') ? response({tables:[{id:'table',name:'ventas.csv',row_count:1,column_count:1}],table_id:'table',columns:['unidades'],rows:[{number:1,values:['2']}],offset:0,column_offset:0,page_rows:50,page_columns:12,cell_characters:500}) : response(page)));
 render(<AnalysisActivity endpoint='/api/jobs/job/activity' traceId='trace' />);
 const button=await screen.findByRole('button',{name:'Análisis completado · Ver proceso'});
 expect(button).toHaveAttribute('aria-expanded','false');button.focus();await userEvent.keyboard('{Enter}');
 expect(button).toHaveAttribute('aria-expanded','true');await screen.findByText(task.text);
 await userEvent.click(screen.getByRole('button',{name:'Ver datos'}));await screen.findByRole('region',{name:'Filas del archivo'});
 expect(screen.getByText('unidades')).toBeInTheDocument();expect(screen.getByText('2')).toBeInTheDocument();
});
it('shares a single request across subscribers to the same process',async()=>{
 const fetch=vi.fn(async()=>response(page));vi.stubGlobal('fetch',fetch);
 function Consumer({endpoint}:{endpoint:string}){const p=useActivity(endpoint,'shared');return <span>{p.data?.headline}</span>;}
 const view=render(<><Consumer endpoint='/api/jobs/j/activity'/><Consumer endpoint='/api/chats/c/turns/t/activity'/></>);
 await waitFor(()=>expect(screen.getAllByText(page.headline)).toHaveLength(2));expect(fetch).toHaveBeenCalledTimes(1);
 view.unmount();
});
it('catches up pages without duplicate events or resetting a completed task',async()=>{
 const fetch=vi.fn(async(url:string)=>response(url.includes('after=') ? {...page,task_updates:[task],events:page.events} : {...page,terminal:false,has_more:true,next_cursor:'trace:1',task_updates:[{...task,status:'running',sequence:1}],events:[{...page.events[0],id:'start',sequence:1,status:'running'}]}));
 vi.stubGlobal('fetch',fetch);render(<AnalysisActivity endpoint='/api/jobs/paged/activity' traceId='paged'/>);
 const button=await screen.findByRole('button',{name:page.headline});await userEvent.click(button);
 await screen.findByText('Comparación por producto completada');expect(screen.getAllByText('Completado')).toHaveLength(1);
 expect(fetch.mock.calls.some(([url])=>String(url).includes('after='))).toBe(true);
});
it('preserves history after a network failure and refreshes on focus',async()=>{
 let fail=false;vi.stubGlobal('fetch',vi.fn(async()=>{if(fail) throw new Error('offline');return response(page);}));
 render(<AnalysisActivity endpoint='/api/jobs/reconnect/activity' traceId='reconnect'/>);
 const button=await screen.findByRole('button',{name:page.headline});await userEvent.click(button);fail=true;
 await act(async()=>{window.dispatchEvent(new Event('focus'));});await screen.findByText(/Reconectando con el progreso/);
 expect(screen.getByText(task.text)).toBeInTheDocument();fail=false;
 await act(async()=>{window.dispatchEvent(new Event('focus'));});await waitFor(()=>expect(screen.queryByText(/Reconectando con el progreso/)).toBeNull());
});
it('opens operator entry independently of customer login and retains no key in localStorage',async()=>{
 const calls:string[]=[];let authorized=false;
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>{
  calls.push(url);
  if(url==='/api/internal/session')return response(authorized?{authorized:true}:{error:'Introduce la clave interna'},authorized?200:401);
  if(url==='/api/internal/login'){authorized=true;return response({ok:true});}
  if(url.startsWith('/api/internal/investigations'))return response({items:[],has_more:false,next_offset:25});
  throw new Error(`Unexpected ${url}`);
 }));
 location.hash='#internal/investigations';render(<App/>);
 const input=await screen.findByLabelText('Clave interna');await userEvent.type(input,'test-operator-key');await userEvent.click(screen.getByRole('button',{name:'Entrar al monitor'}));
 await screen.findByText(/No hay procesos/);expect(calls).not.toContain('/api/workspace');expect(calls).not.toContain('/api/chats');
 expect(localStorage.getItem('internal-key')).toBeNull();
});
it('stops terminal polling, catches up after remount and tears timers down',async()=>{
 vi.useFakeTimers();const fetch=vi.fn(async()=>response(page));vi.stubGlobal('fetch',fetch);
 function Consumer(){const p=useActivity('/api/jobs/terminal/activity','terminal');return <span>{p.data?.headline}</span>;}
 const view=render(<Consumer/>);await act(async()=>{});
 expect(fetch).toHaveBeenCalledTimes(1);await act(async()=>{await vi.advanceTimersByTimeAsync(10000);});
 expect(fetch).toHaveBeenCalledTimes(1);view.unmount();
 const next=render(<Consumer/>);await act(async()=>{});expect(fetch).toHaveBeenCalledTimes(2);
 next.unmount();await act(async()=>{await vi.advanceTimersByTimeAsync(10000);});expect(fetch).toHaveBeenCalledTimes(2);
 vi.useRealTimers();
});
it('ignores an old pending response when the selected process changes',async()=>{
 let resolveOld:(value:Response)=>void=()=>{};let oldSignal:AbortSignal | undefined;
 vi.stubGlobal('fetch',vi.fn(async(url:string,options:RequestInit)=>{
  if(url.includes('/old/')){oldSignal=options.signal as AbortSignal;return new Promise<Response>((resolve)=>{resolveOld=resolve;});}
  return response({...page,trace_id:'new',headline:'Nuevo proceso'});
 }));
 function Consumer({id}:{id:string}){const p=useActivity(`/api/jobs/${id}/activity`,id);return <span>{p.data?.headline}</span>;}
 const view=render(<Consumer id='old'/>);view.rerender(<Consumer id='new'/>);
 await screen.findByText('Nuevo proceso');expect(oldSignal?.aborted).toBe(true);
 await act(async()=>{resolveOld(response(page));});expect(screen.queryByText(page.headline)).toBeNull();
});
it('removes diagnostic data and returns to internal login when authorization expires',async()=>{
 let expired=false;
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>{
  if(url==='/api/internal/session')return response(expired?{error:'Sesión caducada'}:{authorized:true},expired?401:200);
  if(url.includes('/api/internal/investigations/'))return response(expired?{error:'Sesión caducada'}:{...page,business:'Negocio interno',actors:[],resources:undefined},expired?401:200);
  throw new Error(`Unexpected ${url}`);
 }));
 location.hash='#internal/investigations/private';render(<App/>);await screen.findByText('Negocio interno');expired=true;
 await act(async()=>{window.dispatchEvent(new Event('focus'));});await screen.findByLabelText('Clave interna');
 expect(screen.queryByText('Negocio interno')).toBeNull();expect(screen.queryByLabelText('Eventos registrados')).toBeNull();
});
it('filters real actors and activities, opens evidence and preserves selection after refresh',async()=>{
 const branch={...task,id:'branch',kind:'branch',text:'Caída del canal físico',sequence:3,parent_id:'principal',references:[]};
 const main={...task,id:'principal',kind:'research',text:'Coordinación',sequence:1,references:[]};
 const events=[{...page.events[0],text:'Cálculo guardado'},{...page.events[0],id:'branch-event',task_id:'branch',sequence:3,text:'Investigación del canal'}];
 const actors=[{id:'principal',task_id:'principal',role:'research',status:'completed',parent_id:null},{id:'worker-one',task_id:'branch',role:'subanalyst',status:'completed',parent_id:'principal'},{id:'worker-one',task_id:'task',role:'subanalyst',status:'completed',parent_id:'branch'}];
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>{
  if(url==='/api/internal/session') return response({authorized:true});
  if(url.includes('/tasks/task')) return response({content:{code:'result = sum(rows)',metrics:{total:42}},truncated:false});
  if(url.includes('/api/internal/investigations/')) return response({...page,task_updates:[main,branch,task],events,actors,business:'Prueba del monitor'});
  throw new Error(`Unexpected ${url}`);
 }));
 const {InternalMonitor}=await import('./internal-monitor');
 render(<InternalMonitor route='internal/investigations/filter'/>);
 await screen.findByText('Prueba del monitor');
 const worker=screen.getByRole('button',{name:/Subanalista · 1/});await userEvent.click(worker);
 await userEvent.selectOptions(screen.getByLabelText('Filtrar tipo de actividad'),'execution');
 expect(screen.queryByRole('button',{name:/Investigación del canal/})).toBeNull();
 await userEvent.click(screen.getByRole('button',{name:/Cálculo guardado/}));await screen.findByText(/result = sum\(rows\)/);
 await userEvent.click(screen.getByRole('button',{name:'Actualizar'}));
 expect(screen.getByLabelText('Filtrar tipo de actividad')).toHaveValue('execution');
 expect(screen.getByText(/result = sum\(rows\)/)).toBeInTheDocument();
});
it('reduces work while hidden and catches up immediately when the page becomes visible',async()=>{
 vi.useFakeTimers();const hidden=vi.spyOn(document,'hidden','get').mockReturnValue(true);
 const fetch=vi.fn(async()=>response({...page,terminal:false,status:'running'}));vi.stubGlobal('fetch',fetch);
 function Consumer(){const p=useActivity('/api/jobs/visibility/activity','visibility');return <span>{p.data?.headline}</span>;}
 const view=render(<Consumer/>);await act(async()=>{});expect(fetch).toHaveBeenCalledTimes(1);
 await act(async()=>{await vi.advanceTimersByTimeAsync(6000);});expect(fetch).toHaveBeenCalledTimes(1);
 hidden.mockReturnValue(false);await act(async()=>{document.dispatchEvent(new Event('visibilitychange'));});
 expect(fetch).toHaveBeenCalledTimes(2);view.unmount();hidden.mockRestore();vi.useRealTimers();
});
it('keeps the process accessible from a report created within a chat',async()=>{
 const fetch=vi.fn(async(url:string)=>url.endsWith('/activity') ? response(page) : response({error:'Informe temporalmente no disponible'},503));vi.stubGlobal('fetch',fetch);
 const {Presentation}=await import('./overview');
 render(<Presentation path='/api/chats/chat/presentation/turn' exportUrl='/api/chats/chat/report/turn'/>);
 await screen.findByRole('button',{name:page.headline});
 expect(fetch.mock.calls.some(([url])=>url==='/api/chats/chat/turns/turn/activity')).toBe(true);
});
