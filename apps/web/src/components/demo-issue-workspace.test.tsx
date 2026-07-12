import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { DemoIssueWorkspace } from './demo-issue-workspace';

vi.mock('next/link',()=>({default:({href,children,...props}:React.AnchorHTMLAttributes<HTMLAnchorElement>&{href:string})=><a href={href} {...props}>{children}</a>}));
vi.mock('next/image',()=>({default:({fill:_fill,priority:_priority,...props}:React.ImgHTMLAttributes<HTMLImageElement>&{fill?:boolean;priority?:boolean})=><img {...props}/>}));

describe('DemoIssueWorkspace actions',()=>{
  it('opens the controlling-source section from the requirement and confirms approval routing',()=>{
    render(<DemoIssueWorkspace/>);
    fireEvent.click(screen.getByRole('button',{name:/Open E-1\.1/}));
    expect(screen.getByRole('heading',{name:'Source of truth'})).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab',{name:'overview'}));
    fireEvent.click(screen.getByRole('button',{name:'Send for PM approval'}));
    expect(screen.getByRole('button',{name:'Approval requested'})).toBeDisabled();
    expect(screen.getByRole('status')).toHaveTextContent('Demo approval request prepared');
  });
});
