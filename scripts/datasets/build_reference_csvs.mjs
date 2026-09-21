// Author bounded fixture tables with Artifact Tool; serialize range values to CSV.
// The public API has no documented CSV export, so the final encoding uses JS.
import fs from 'node:fs/promises';
import path from 'node:path';
import { Workbook } from '@oai/artifact-tool';

const root = process.env.REFERENCE_REPO_ROOT;
if (!root) throw new Error('Set REFERENCE_REPO_ROOT to the repository directory.');
const staging = path.join(root, '.tools/reference-cases');
const inputs = JSON.parse(await fs.readFile(path.join(staging, 'tables.json'), 'utf8'));
const quote = value => {
  const text = String(value ?? '');
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
};
for (const input of inputs) {
  const workbook = Workbook.create();
  const sheet = workbook.worksheets.add('Sales');
  const values = [input.header, ...input.rows];
  const width = input.header.length;
  const range = sheet.getRangeByIndexes(0, 0, values.length, width);
  range.values = values;
  range.format.font = { name: 'Arial', size: 11 };
  range.format.columnWidth = 23;
  range.format.rowHeight = 24;
  const header = sheet.getRangeByIndexes(0, 0, 1, width);
  header.format.font = { bold: true, color: '#FFFFFF' };
  header.format.fill = '#334155';
  for (let col = 0; col < width; col++) {
    if (input.header[col].includes('name')) sheet.getRangeByIndexes(0, col, values.length, 1).format.columnWidth = 48;
  }
  const result = range.values;
  if (JSON.stringify(result) !== JSON.stringify(values)) throw new Error(`Changed values: ${input.case}`);
  const output = path.join(root, 'data/reference-cases', input.case, input.file);
  await fs.mkdir(path.dirname(output), {recursive: true});
  await fs.writeFile(output, '\uFEFF' + result.map(row => row.map(quote).join(',')).join('\r\n') + '\r\n');
  const preview = await workbook.render({sheetName: 'Sales', range: `A1:${String.fromCharCode(64 + width)}${Math.min(values.length, 7)}`, scale: 1.5, format: 'png'});
  await fs.writeFile(path.join(staging, `${input.case}-${input.file.startsWith('input') ? 'base' : 'variant'}.png`), new Uint8Array(await preview.arrayBuffer()));
  console.log(`${input.case}/${input.file}: ${input.rows.length} rows`);
}
