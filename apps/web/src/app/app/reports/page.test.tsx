import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DemoModeProvider } from '@/components/demo-mode';
import ReportsPage from './page';

function renderReports(){return render(<DemoModeProvider demo organizationId="org" projectId="cooper" projectName="Cooper Residence" userName="Jordan Cho"><ReportsPage/></DemoModeProvider>)}

describe('demo report workspace',()=>{
  beforeEach(()=>vi.stubGlobal('print',vi.fn()));

  it('switches reports without presenting an unbundled artifact as complete',()=>{
    renderReports();
    fireEvent.click(screen.getByRole('button',{name:/RFI draft \/ RFI-018/i}));
    expect(screen.getByRole('heading',{name:'Partition dimension conflict'})).toBeInTheDocument();
    expect(screen.getByText(/Only P-024 includes a bundled source-cited artifact/)).toBeInTheDocument();
    expect(screen.getByRole('button',{name:'PDF'})).toBeDisabled();
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
