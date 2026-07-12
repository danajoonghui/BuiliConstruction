import { describe, expect, it } from 'vitest';
import { createCsv } from './csv';

describe('createCsv', () => {
  it('quotes values and prevents spreadsheet formula injection', () => {
    expect(createCsv(['Title','Value'],[['A, B','=HYPERLINK("bad")']]))
      .toBe('"Title","Value"\r\n"A, B","\'=HYPERLINK(""bad"")"');
  });
});
