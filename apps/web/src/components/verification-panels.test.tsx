import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { VerificationPanels } from './verification-panels';

describe('VerificationPanels',()=>{
  it('expands a panel from keyboard focus',()=>{
    render(<VerificationPanels/>);
    const sourcePanel=screen.getByRole('button',{name:/resolve the record/i});
    expect(screen.getAllByRole('button').every(panel=>panel.getAttribute('aria-expanded')==='false')).toBe(true);
    expect(sourcePanel).toHaveAttribute('aria-expanded','false');
    fireEvent.focus(sourcePanel);
    expect(sourcePanel).toHaveAttribute('aria-expanded','true');
    fireEvent.keyDown(sourcePanel,{key:'Escape'});
    expect(sourcePanel).toHaveAttribute('aria-expanded','false');
  });
});
