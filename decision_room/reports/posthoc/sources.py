"""Prepare immutable CSV snapshots and a bounded metadata allowlist.

Observed uniqueness is not business grain. No audit/oracle or report values are
accepted by this interface. Unit defaults are column names, not inferred business
meanings. Numeric values are never exported as categorical examples.
"""
from pathlib import Path
import re

import duckdb

from ...engine import calculations
from .inventory import canonical, sha
from .interpretation import save_new


def quote(name):
    return '"'+name.replace('"','""')+'"'


def prepare(csv_files,dest):
    dest=Path(dest);dest.mkdir(parents=True,exist_ok=False)
    sources={}; categorical_data={}
    if not 1<=len(csv_files)<=64:raise ValueError('Select 1–64 CSV files.')
    with duckdb.connect(config={'threads':1,'memory_limit':'256MB'}) as db:
        for index,filename in enumerate(csv_files):
            path=Path(filename);raw=path.read_bytes()
            if len(raw)>calculations.MAX_FILE_BYTES:raise ValueError('CSV exceeds calculation bound.')
            identifier='table_'+sha(raw)[:16]
            if identifier in sources:raise ValueError('Duplicate source snapshot.')
            db.execute('CREATE OR REPLACE TABLE incoming AS SELECT * FROM read_csv(?, all_varchar=true)',[str(path)])
            count=db.execute('SELECT count(*) FROM incoming').fetchone()[0]
            if not 0<count<=calculations.MAX_ROWS:raise ValueError('CSV outside row bound.')
            columns=[]
            for name,*_ in db.execute('DESCRIBE incoming').fetchall():
                values=[r[0] for r in db.execute('SELECT DISTINCT '+quote(name)+' FROM incoming WHERE '+quote(name)+' IS NOT NULL').fetchall()]
                numeric=bool(values);integer=True
                for value in values:
                    try:
                        number=calculations._amount(value)
                        integer=integer and number==number.to_integral_value()
                    except ValueError:
                        numeric=False;integer=False;break
                column={'name':name,'numeric':numeric,'integer':integer if numeric else False}
                if numeric:
                    column['unit']=name
                if (not numeric or re.search(r'(^id$|_id$)',name,re.I)) and len(values)<=256 and all(len(v)<=500 for v in values):
                    column['categories']=sorted(values)
                columns.append(column)
                if 'categories' in column:
                    categorical_data[(identifier,name)]=db.execute('SELECT '+quote(name)+' FROM incoming').fetchall()
            parquet=dest/(identifier+'.parquet')
            db.execute('COPY incoming TO ?',[str(parquet)])
            if path.read_bytes()!=raw:raise ValueError('CSV changed during preparation.')
            sources[identifier]={'table_id':identifier,'snapshot_sha256':sha(raw),
                'path':str(parquet.resolve()),'parquet_sha256':sha(parquet.read_bytes()),
                'columns':columns,'source_name':path.name}
    # Exact-name key correspondence and observed uniqueness only; never business grain.
    for source in sources.values():
        for column in source['columns']:
            key=column['name']
            if 'categories' not in column: continue
            matches={}
            for dimension in sources.values():
                if dimension is source:continue
                keys=[v[0] for v in categorical_data.get((dimension['table_id'],key),[])]
                if not keys or None in keys or len(set(keys))!=len(keys):continue
                if not set(column['categories'])<=set(keys):continue
                for label in dimension['columns']:
                    if label['name']==key or label['numeric'] or 'categories' not in label:continue
                    labels=[v[0] for v in categorical_data.get((dimension['table_id'],label['name']),[])]
                    for code,name in zip(keys,labels):
                        if name is None:continue
                        from .recipes import normalized
                        matches.setdefault(normalized(name),[]).append({'name':name,'code':code,
                            'dimension_sha256':dimension['snapshot_sha256'],'label_column':label['name']})
            aliases=[]
            for entries in matches.values():
                if len({v['code'] for v in entries})==1: aliases.append(entries[0])
            if aliases:column['aliases']=sorted(aliases,key=lambda a:(a['name'],a['code']))
    save_new(dest/'sources.json',sources)
    return sources
