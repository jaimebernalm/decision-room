import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Workbook, SpreadsheetFile} from '@oai/artifact-tool';

const root = fileURLToPath(new URL('../../', import.meta.url));
const output = path.join(root, 'data/wide-world-importers/exports');
const temp = path.join(root, '.tools/spreadsheets/templates');
const previews = path.join(root, '.tools/spreadsheets/previews');
const plan = JSON.parse(await fs.readFile(path.join(output,'metadata/excel-plan.json'),'utf8'));
await fs.mkdir(temp,{recursive:true});
await fs.mkdir(previews,{recursive:true});
const source = 'https://github.com/microsoft/sql-server-samples/releases/tag/wide-world-importers-v1.0';
function col(j) {let n=j+1,s='';while(n){n--;s=String.fromCharCode(65+n%26)+s;n=Math.floor(n/26);}return s;}
function asValue(v,c) {
  if(v===null)return null;
  if(String(v).length>32767)return 'External value: see accompanying large-values folder';
  if(c.type==='date')return (Date.parse(v+'T00:00:00Z')-Date.UTC(1899,11,30))/86400000;
  if(c.type==='bit')return Number(v)===1;
  if(['int','bigint','decimal'].includes(c.type) && !c.name.endsWith('ID'))return Number(v);
  return "'"+String(v);
}
for (const [group,sheets] of Object.entries(plan.groups)) {
  const wb=Workbook.create();
  const intro=wb.worksheets.add('Read me');
  intro.getRange('A1:B12').values=[
    ['Wide World Importers',group+' data'],
    ['Data origin','Fictional Microsoft sample business; full source rows retained.'],
    ['Source',source],
    ['License','MIT; copyright Microsoft Corporation.'],
    ['Layout','Each data sheet is one source table; large tables are split into numbered sheets.'],
    ['Missing values','Blank cells mean SQL NULL. Explicit empty text values remain empty strings.'],
    ['Identifiers','Identifiers and codes are text; amounts and quantities are numeric.'],
    ['Dates','Date-only values are Excel dates. SQL timestamps remain exact ISO text to retain seven fractional digits.'],
    ['Large values','Values exceeding Excel’s cell-text limit are in the accompanying large-values folder; cells contain references.'],
    ['Binary and geography','SQL binary/spatial values are preserved as hexadecimal; large values are referenced externally.'],
    ['Computed fields','Eight source computed fields are reconstructed from their documented expressions; see Columns.'],
    ['Scope','This is a format conversion, not a cleaned or small-shop sample.']
  ];
  intro.getRange('A1:B12').format.font={name:'Helvetica',size:11};
  intro.getRange('A1:B1').format.font={name:'Helvetica',size:14,bold:true};
  intro.getRange('A1:A12').format.columnWidth=25;
  intro.getRange('B1:B12').format.columnWidth=100;
  intro.getRange('A1:B12').format.wrapText=true;
  intro.getRange('A1:B12').format.rowHeight=36;
  const dict=wb.worksheets.add('Columns');
  const dictRows=[['Table','Column','SQL type','Nullable','Computed','Expression']];
  for(const p of sheets.filter(x=>x.part===0))for(const c of p.columns)dictRows.push([p.table,c.name,c.type,c.nullable?'Yes':'No',c.computed?'Yes':'No',c.expression??'']);
  dict.getRange(`A1:F${dictRows.length}`).values=dictRows;
  dict.getRange(`A1:F${dictRows.length}`).format.font={name:'Helvetica',size:11};
  dict.getRange(`A1:F${dictRows.length}`).format.columnWidth=26;
  dict.getRange(`F1:F${dictRows.length}`).format.columnWidth=75;
  dict.getRange('A1:F1').format={fill:'#243B53',font:{name:'Helvetica',bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:32};
  dict.freezePanes.freezeRows(1);
  for(const p of sheets){
    const sh=wb.worksheets.add(p.sheet), last=col(p.columns.length-1);
    const rows=[p.columns.map(c=>c.name),...p.sample.map(r=>r.map((v,i)=>asValue(v,p.columns[i])))];
    sh.getRange(`A1:${last}${rows.length}`).values=rows;
    sh.getRange(`A1:${last}${Math.max(2,rows.length)}`).format.font={name:'Helvetica',size:11};
    sh.getRange(`A2:${last}${Math.max(2,rows.length)}`).format.wrapText=true;
    sh.getRange(`A2:${last}${Math.max(2,rows.length)}`).format.rowHeight=44;
    sh.getRange(`A1:${last}1`).format={fill:'#243B53',font:{name:'Helvetica',bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:42};
    sh.freezePanes.freezeRows(1);
    for(let j=0;j<p.columns.length;j++){
      const c=p.columns[j], letter=col(j), range=sh.getRange(`${letter}2:${letter}${Math.max(rows.length,2)}`);
      let width=Math.max(16,Math.min(34,c.name.length+3));
      if(c.type==='nvarchar')width=Math.min(42,Math.max(width,Math.min(38,p.max_characters[j])));
      if(c.type==='datetime2')width=34;
      sh.getRange(`${letter}1:${letter}${Math.max(2,rows.length)}`).format.columnWidth=width;
      if(c.type==='date')range.setNumberFormat('yyyy-mm-dd');
      else if(c.name.endsWith('ID') || !['int','bigint','decimal','bit'].includes(c.type))range.setNumberFormat('@');
      else if(c.type==='decimal')range.setNumberFormat('#,##0'+(Number(c.Scale)?'.'+'0'.repeat(Number(c.Scale)):''));
      else range.setNumberFormat('0');
    }
    console.log(group,p.sheet,(await wb.inspect({kind:'table',range:`'${p.sheet}'!A1:D3`,include:'values',tableMaxRows:3,tableMaxCols:4,maxChars:650})).ndjson);
    const preview=await wb.render({sheetName:p.sheet,range:`A1:${col(Math.min(5,p.columns.length-1))}${Math.min(6,rows.length)}`,scale:1,format:'png'});
    await fs.writeFile(path.join(previews,`${group}.${p.sheet}.png`),new Uint8Array(await preview.arrayBuffer()));
  }
  for(const name of ['Read me','Columns']){
    const img=await wb.render({sheetName:name,range:name==='Read me'?'A1:B12':'A1:F8',scale:1,format:'png'});
    await fs.writeFile(path.join(previews,`${group}.${name}.png`),new Uint8Array(await img.arrayBuffer()));
  }
  const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#SPILL!',options:{useRegex:true,maxResults:10},maxChars:1000});
  console.log('Error scan',group,errors.ndjson);
  await (await SpreadsheetFile.exportXlsx(wb)).save(path.join(temp,`${group}.xlsx`));
  console.log('Template saved',group);
}
