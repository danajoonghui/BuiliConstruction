'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { FormEvent, useState } from 'react';
import { ArrowRight, LoaderCircle } from 'lucide-react';
import { authApi, ApiError } from '@/lib/api';
import { signInWithGoogle } from '@/lib/google-auth';
import { GoogleMark } from './google-mark';

export function SignupForm() {
  const router = useRouter(); const [loading, setLoading] = useState(false); const [error, setError] = useState('');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setLoading(true); setError(''); const values = new FormData(event.currentTarget);
    try {
      await authApi.signUp({ display_name: String(values.get('name')), email: String(values.get('email')), password: String(values.get('password')), organization_name: String(values.get('organization')) });
      router.push('/app/onboarding');
    } catch (cause) { setError(cause instanceof ApiError ? cause.message : 'We could not create your account. Please try again.'); }
    finally { setLoading(false); }
  }
  return (
    <>
      <button
        type="button"
        className="google-button"
        disabled={loading}
        aria-busy={loading}
        onClick={async () => {
          setLoading(true);
          setError('');
          try { await signInWithGoogle(); router.push('/app/onboarding'); }
          catch (cause) { setError(cause instanceof Error ? cause.message : 'Google sign-up could not be completed.'); }
          finally { setLoading(false); }
        }}
      >
        <GoogleMark/> Sign up with Google
      </button>
      <div className="auth-divider"><span>or use your work email</span></div>
      <form className="auth-form" method="post" action="/signup" onSubmit={submit}>
        <div className="field-pair"><label>Full name<input name="name" autoComplete="name" placeholder="Jordan Cho" required/></label><label>Company<input name="organization" autoComplete="organization" placeholder="Northstar Builders" required/></label></div>
        <label>Work email<input name="email" type="email" autoComplete="email" placeholder="you@company.com" required/></label>
        <label>Password<input name="password" type="password" autoComplete="new-password" placeholder="At least 12 characters" minLength={12} pattern="(?=.*[0-9])(?=.*[^A-Za-z0-9]).{12,}" title="Use at least 12 characters with a number and symbol" required/><small>Use 12+ characters with a number and symbol.</small></label>
        {error && <p role="alert" className="form-error">{error}</p>}
        <button className="button button--primary button--large button--full" disabled={loading}>{loading ? <><LoaderCircle className="spin"/> Creating workspace...</> : <>Create account <ArrowRight size={16}/></>}</button>
      </form>
      <p className="auth-switch">Already have an account? <Link href="/login">Sign in</Link></p>
      <Link className="auth-demo-link" href="/app/issues/BUI-1042?demo=1">Not ready to register? Explore the demo</Link>
    </>
  );
}
