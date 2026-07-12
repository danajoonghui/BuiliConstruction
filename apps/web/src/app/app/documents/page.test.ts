import { describe,expect,it } from 'vitest';
import { uploadedRevisionRow } from '@/lib/document-revisions';

describe('document revision response adapter',()=>{
  it('maps the nested revision creation contract into a processing row',()=>{
    const row=uploadedRevisionRow({revision_id:'rev-1',job_id:'job-1',revision:{revision:'uploaded',status:'uploaded',sheet_number:null,issue_date:null}},'E1.1.pdf');
    expect(row).toMatchObject({id:'rev-1',title:'E1.1.pdf',revision:'uploaded',status:'Processing'});
  });
});
