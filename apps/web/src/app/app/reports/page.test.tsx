import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DemoModeProvider } from '@/components/demo-mode';
import ReportsPage from './page';

function renderReports(){return render(<DemoModeProvider demo organizationId="org" projectId="cooper" projectName="Cooper Residence" userName="Jordan Cho"><ReportsPage/></DemoModeProvider>)}

describe('demo report workspace',()=>{
  beforeEach(()=>vi.stubGlobal('print',vi.fn()));

  it('switches reports and exposes bundled PDF and DOCX artifacts',()=>{
    renderReports();
    fireEvent.click(screen.getByRole('button',{name:/RFI draft \/ RFI-018/i}));
    expect(screen.getByRole('heading',{name:'Office partition dimension conflict at grid C'})).toBeInTheDocument();
    expect(screen.getByRole('link',{name:'PDF'})).toHaveAttribute('href','/demo/RFI-018-partition-dimension.pdf');
    expect(screen.getByRole('link',{name:'DOCX'})).toHaveAttribute('href','/demo/RFI-018-partition-dimension.docx');
    expect(screen.getByText('Please confirm the controlling reference and approved offset from grid C.')).toBeInTheDocument();
  });

  it('saves and approves the bundled demo report with explicit local-only feedback',()=>{
    renderReports();
    fireEvent.click(screen.getByRole('button',{name:/Save version/}));
    expect(screen.getByRole('status')).toHaveTextContent('Demo version 4 saved');
    expect(screen.getAllByText(/Version 4|V4/).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole('button',{name:/Approve & issue/}));
    expect(screen.getByRole('button',{name:'Approved'})).toBeDisabled();
    expect(screen.getByRole('status')).toHaveTextContent('No external system was contacted');
  });

  it('connects the print control to the browser print action',()=>{
    renderReports();
    fireEvent.click(screen.getByRole('button',{name:'Print'}));
    expect(window.print).toHaveBeenCalledOnce();
  });
});
