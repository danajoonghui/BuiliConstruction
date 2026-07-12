import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '@/lib/api';
import { DemoModeProvider } from './demo-mode';
import { IssueDetailRouter } from './issue-detail-router';

vi.mock('next/navigation',()=>({useSearchParams:()=>new URLSearchParams()}));
vi.mock('next/link',()=>({default:({href,children,...props}:React.AnchorHTMLAttributes<HTMLAnchorElement>&{href:string})=><a href={href} {...props}>{children}</a>}));

const issue={
  id:'8ac4d75f-840a-4bd7-90af-1fa9b521cab4',number:'BUI-1050',title:'Live issue title',description:'Review the installed condition.',issue_type:'field_deviation',status:'ready_for_review',priority:'normal',observed_condition:'Observed live condition',expected_condition:'Expected live requirement',difference:'A verified difference',classification:'unapproved_deviation',recommended_action:'punch',evidence_sufficiency:'sufficient',missing_evidence:[],location_json:{space:'Room 204'},assigned_to:null,approved_by:null,created_at:'2026-07-12T08:00:00Z',updated_at:'2026-07-12T09:00:00Z'
};

describe('IssueDetailRouter live response contract',()=>{
  beforeEach(()=>vi.restoreAllMocks());

  it('unwraps the issue from the evidence-and-sources detail payload',async()=>{
    vi.spyOn(api,'get').mockResolvedValue({issue,evidence:[],sources:[]});
    render(<DemoModeProvider demo={false} organizationId="org" projectId="project" projectName="Project" userName="Jordan"><IssueDetailRouter id={issue.id}/></DemoModeProvider>);

    expect(await screen.findByRole('heading',{name:'Live issue title'})).toBeInTheDocument();
    expect(screen.getByText('Observed live condition')).toBeInTheDocument();
    expect(screen.getByText('ready for review')).toBeInTheDocument();
  });

  it('refreshes from the same nested response after approval',async()=>{
    const approved={...issue,approved_by:'user-1',status:'approved'};
    vi.spyOn(api,'get').mockResolvedValueOnce({issue,evidence:[],sources:[]}).mockResolvedValueOnce({issue:approved,evidence:[],sources:[]});
    vi.spyOn(api,'post').mockResolvedValue({});
    render(<DemoModeProvider demo={false} organizationId="org" projectId="project" projectName="Project" userName="Jordan"><IssueDetailRouter id={issue.id}/></DemoModeProvider>);

    fireEvent.click(await screen.findByRole('button',{name:'Approve issue'}));
    await waitFor(()=>expect(screen.getByRole('button',{name:'Approved'})).toBeDisabled());
  });
});
