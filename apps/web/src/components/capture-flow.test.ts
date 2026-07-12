import { describe, expect, it } from 'vitest';
import { captureFileError, captureValidationMessage } from './capture-flow';

const valid={room:'Garage',position:'East wall',assetCount:1,demoEvidence:false,note:'Box is below the noted elevation.',measurement:'12'};

describe('field capture validation',()=>{
  it('requires a grounded location',()=>expect(captureValidationMessage(1,{...valid,room:''})).toContain('space'));
  it('requires at least one media or voice asset',()=>expect(captureValidationMessage(2,{...valid,assetCount:0})).toContain('at least one'));
  it('accepts the explicit representative demo evidence set',()=>expect(captureValidationMessage(2,{...valid,assetCount:0,demoEvidence:true})).toBe(''));
  it('rejects zero and non-numeric measurements',()=>{
    expect(captureValidationMessage(3,{...valid,measurement:'0'})).toContain('positive');
    expect(captureValidationMessage(3,{...valid,measurement:'twelve'})).toContain('positive');
  });
  it('rejects unsupported, oversized, and excessive field media',()=>{
    expect(captureFileError([new File(['text'],'note.txt',{type:'text/plain'})],0)).toContain('not a supported');
    expect(captureFileError([new File([new Uint8Array(26*1024*1024)],'large.jpg',{type:'image/jpeg'})],0)).toContain('25 MB');
    expect(captureFileError([new File(['image'],'photo.jpg',{type:'image/jpeg'})],12)).toContain('no more than 12');
  });
});
