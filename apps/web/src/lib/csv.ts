function safeCell(value: unknown) {
  const raw=String(value ?? '');
  const protectedValue=/^[=+\-@]/.test(raw) ? `'${raw}` : raw;
  return `"${protectedValue.replaceAll('"','""')}"`;
}

export function createCsv(headers:string[], rows:unknown[][]) {
  return [headers.map(safeCell).join(','),...rows.map(row=>row.map(safeCell).join(','))].join('\r\n');
}

export function downloadCsv(filename:string, headers:string[], rows:unknown[][]) {
  const blob=new Blob([`\uFEFF${createCsv(headers,rows)}`],{type:'text/csv;charset=utf-8'});
  const url=URL.createObjectURL(blob);
  const anchor=document.createElement('a');
  anchor.href=url;
  anchor.download=filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
