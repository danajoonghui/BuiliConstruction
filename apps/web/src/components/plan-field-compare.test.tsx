import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { PlanFieldCompare } from './plan-field-compare';

describe('PlanFieldCompare',()=>{
  it('allows the comparison split to be adjusted',()=>{
    render(<PlanFieldCompare/>);
    const control=screen.getByRole('slider',{name:/compare project record/i});
    fireEvent.change(control,{target:{value:'64'}});
    expect(control).toHaveValue('64');
  });
});
