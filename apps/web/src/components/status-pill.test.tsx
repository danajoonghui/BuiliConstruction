import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { StatusPill } from './status-pill';

describe('StatusPill', () => {
  it('renders an accessible status label', () => {
    render(<StatusPill tone="green">Ready for review</StatusPill>);
    expect(screen.getByText('Ready for review')).toBeInTheDocument();
  });
});
