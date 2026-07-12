import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DemoModeProvider } from './demo-mode';
import { SpatialWorkbench } from './spatial-workbench';

vi.mock('next/link', () => ({ default: ({href,children,...props}:React.AnchorHTMLAttributes<HTMLAnchorElement>&{href:string}) => <a href={href} {...props}>{children}</a> }));

function renderWorkbench() {
  return render(<DemoModeProvider demo organizationId="org" projectId="cooper" projectName="Cooper Residence" userName="Jordan Cho"><SpatialWorkbench /></DemoModeProvider>);
}

describe('SpatialWorkbench demo controls', () => {
  beforeEach(() => {
    Object.defineProperty(HTMLElement.prototype,'requestFullscreen',{configurable:true,value:vi.fn().mockResolvedValue(undefined)});
  });

  it('updates sheet revision metadata and viewer zoom controls', () => {
    renderWorkbench();
    expect(screen.getByText(/Sheet E1\.1 · Rev 03 · 100%/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button',{name:/A-202 Level 2 plan Rev 05/i}));
    expect(screen.getByText(/Sheet A-202 · Rev 05 · 100%/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button',{name:'Zoom in'}));
    expect(screen.getByText(/115%/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Center view'}));
    expect(screen.getByText(/100%/)).toBeInTheDocument();
  });

  it('routes inspector actions and supports keyboard issue-pin selection', () => {
    renderWorkbench();
    expect(screen.getByRole('link',{name:'Open issue'})).toHaveAttribute('href','/app/issues/BUI-1042?demo=1');
    expect(screen.getByRole('link',{name:'Start punch item'})).toHaveAttribute('href','/app/workflows?demo=1&action=punch&issue=BUI-1042');

    fireEvent.keyDown(screen.getByRole('button',{name:'Select BUI-1038'}),{key:'Enter'});
    expect(screen.getByRole('heading',{name:'Partition offset from A-202 layout'})).toBeInTheDocument();
    expect(screen.getByText('Additional evidence required')).toBeInTheDocument();
  });

  it('requests fullscreen from the viewer control', () => {
    renderWorkbench();
    fireEvent.click(screen.getByRole('button',{name:'Open fullscreen'}));
    expect(HTMLElement.prototype.requestFullscreen).toHaveBeenCalledOnce();
  });
});
