import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';
const root=fileURLToPath(new URL('../../', import.meta.url));
const output=path.join(root,'.tools/spreadsheets/final-previews');
await fs.mkdir(output,{recursive:true});
const plan=JSON.parse(await fs.readFile(path.join(root,'data/wide-world-importers/exports/metadata/excel-plan.json'),'utf8'));
for(const [group,sheets] of Object.entries(plan.groups)){
 const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(root,'.tools/spreadsheets/saved-previews',group+'.xlsx')));
 for(const p of sheets){
  const last=String.fromCharCode(64+Math.min(p.columns.length,6));
  const image=await wb.render({sheetName:p.sheet,range:`A1:${last}${Math.min(6,p.rows+1)}`,scale:1,format:'png'});
  await fs.writeFile(path.join(output,`${group}.${p.sheet}.png`),new Uint8Array(await image.arrayBuffer()));
 }
 for(const name of ['Read me','Columns']){
  const image=await wb.render({sheetName:name,range:name==='Read me'?'A1:B12':'A1:F8',scale:1,format:'png'});
  await fs.writeFile(path.join(output,`${group}.${name}.png`),new Uint8Array(await image.arrayBuffer()));
 }
 console.log('Rendered saved data',group);
}
