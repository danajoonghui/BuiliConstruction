import { createElement } from 'react';
import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { LoginForm, safeReturnPath } from './login-form';
import { SignupForm } from './signup-form';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() })
}));

describe('safeReturnPath', () => {
  it('allows only routes inside the product application', () => {
    expect(safeReturnPath('?returnTo=%2Fapp%2Fissues%3Fstatus%3Dopen')).toBe('/app/issues?status=open');
    expect(safeReturnPath('?returnTo=%2Fapp')).toBe('/app');
  });

  it('rejects external, ambiguous, and backslash return paths', () => {
    expect(safeReturnPath('?returnTo=https%3A%2F%2Fevil.example')).toBe('/app');
    expect(safeReturnPath('?returnTo=%2F%2Fevil.example')).toBe('/app');
    expect(safeReturnPath('?returnTo=%2Fapplication')).toBe('/app');
    expect(safeReturnPath('?returnTo=%2Fapp%5C%5Cevil.example')).toBe('/app');
  });

  it('uses POST as the pre-hydration fallback for credential forms', () => {
    const login = render(createElement(LoginForm));
    expect(login.container.querySelector('form')).toHaveAttribute('method', 'post');
    login.unmount();
    const signup = render(createElement(SignupForm));
    expect(signup.container.querySelector('form')).toHaveAttribute('method', 'post');
  });
});
