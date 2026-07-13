import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DemoModeProvider } from './demo-mode';
import { SpatialWorkbench } from './spatial-workbench';

vi.mock('next/link', () => ({ default: ({href,children,...props}:React.AnchorHTMLAttributes<HTMLAnchorElement>&{href:string}) => <a href={href} {...props}>{children}</a> }));
vi.mock('./three-spatial-scene', () => ({ ThreeSpatialScene: ({selected}:{selected:string}) => <div aria-label="Coordinated 3D model">Selected {selected}</div> }));

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

    fireEvent.click(screen.getByRole('button',{name:/A1\.1 Ground floor architectural plan Rev 03/i}));
    expect(screen.getByText(/Sheet A1\.1 · Rev 03 · 100%/)).toBeInTheDocument();
    expect(screen.getByRole('img',{name:'Architectural ground floor contract drawing'})).toHaveAttribute('src','/demo/A1.1-preview.png');

    fireEvent.click(screen.getByRole('button',{name:'Zoom in'}));
    expect(screen.getByText(/115%/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Center view'}));
    expect(screen.getByText(/100%/)).toBeInTheDocument();
  });

  it('routes inspector actions and supports keyboard issue-pin selection', () => {
    renderWorkbench();
    expect(screen.getByRole('link',{name:'Open issue'})).toHaveAttribute('href','/app/issues/BUI-1042?demo=1');
    expect(screen.getByRole('link',{name:'Start punch item'})).toHaveAttribute('href','/app/workflows?demo=1&action=punch&issue=BUI-1042');

    fireEvent.click(screen.getByRole('button',{name:/A1\.1 Ground floor architectural plan Rev 03/i}));
    fireEvent.click(screen.getByRole('button',{name:'Select BUI-1038'}));
    expect(screen.getByRole('heading',{name:'Office partition offset from approved layout'})).toBeInTheDocument();
    expect(screen.getByText('Additional evidence required')).toBeInTheDocument();
  });

  it('renders the coordinated GLB scene in 3D mode', () => {
    renderWorkbench();
    fireEvent.click(screen.getByRole('tab',{name:'3D context'}));
    expect(screen.getByLabelText('Coordinated 3D model')).toHaveTextContent('BUI-1042');
  });

  it('requests fullscreen from the viewer control', () => {
    renderWorkbench();
    fireEvent.click(screen.getByRole('button',{name:'Open fullscreen'}));
    expect(HTMLElement.prototype.requestFullscreen).toHaveBeenCalledOnce();
  });
});
