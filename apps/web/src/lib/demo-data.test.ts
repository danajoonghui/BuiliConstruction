import { describe, expect, it } from 'vitest';
import { demoIssue, demoUser, issues } from './demo-data';

describe('canonical demo workspace', () => {
  it('uses one coherent persona and evidence-grounded issue', () => {
    expect(demoUser.name).toBe('Jordan Cho');
    expect(demoIssue.project).toBe('Cooper Residence Renovation');
    expect(demoIssue.measurement.observed).toBe('12 in. AFF');
    expect(demoIssue.measurement.required).toBe('18 in. AFF min.');
    expect(issues.find(issue => issue.id === 'BUI-1042')?.type).toBe('Punch');
  });
});
