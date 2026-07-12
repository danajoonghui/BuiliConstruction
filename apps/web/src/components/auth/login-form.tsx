'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { FormEvent, useState } from 'react';
import { ArrowRight, Eye, EyeOff, LoaderCircle } from 'lucide-react';
import { authApi, ApiError } from '@/lib/api';
import { signInWithGoogle } from '@/lib/google-auth';

export function LoginForm() {
  const router = useRouter();
  const [visible, setVisible] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setLoading(true); setError('');
    const values = new FormData(event.currentTarget);
    try {
      await authApi.signIn({ email: String(values.get('email')), password: String(values.get('password')) });
      router.push(safeReturnPath()); router.refresh();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'We could not connect to BUILI. Try again or open the demo workspace.');
    } finally { setLoading(false); }
  }

  async function continueWithGoogle() { setLoading(true); setError(''); try { await signInWithGoogle(); router.push(safeReturnPath()); router.refresh(); } catch(cause) { setError(cause instanceof Error ? cause.message : 'Google sign-in could not be completed.'); } finally { setLoading(false); } }

  return (
    <>
      <button type="button" className="google-button" onClick={continueWithGoogle}><GoogleMark/> Continue with Google</button>
      <div className="auth-divider"><span>or continue with email</span></div>
      <form className="auth-form" onSubmit={submit}>
        <label>Email address<input name="email" type="email" autoComplete="email" placeholder="you@company.com" required/></label>
        <label>Password<span className="password-input"><input name="password" type={visible ? 'text' : 'password'} autoComplete="current-password" placeholder="Enter your password" minLength={8} required/><button type="button" onClick={() => setVisible(!visible)} aria-label={visible ? 'Hide password' : 'Show password'}>{visible ? <EyeOff/> : <Eye/>}</button></span></label>
        <div className="auth-form-row auth-form-row--end"><Link href="/forgot-password">Forgot password?</Link></div>
        {error && <p role="alert" className="form-error">{error}</p>}
        <button className="button button--primary button--large button--full" disabled={loading}>{loading ? <><LoaderCircle className="spin"/> Signing in...</> : <>Sign in <ArrowRight size={16}/></>}</button>
      </form>
      <Link className="demo-entry" href="/app/issues/BUI-1042?demo=1"><span><b>Explore the live demo</b><small>Open Jordan Cho&apos;s project workspace without an account</small></span><ArrowRight size={18}/></Link>
      <p className="auth-switch">New to BUILI? <Link href="/signup">Create an account</Link></p>
    </>
  );
}

function safeReturnPath() { const value = new URLSearchParams(window.location.search).get('returnTo'); return value?.startsWith('/app') && !value.startsWith('//') ? value : '/app'; }

function GoogleMark() { return <svg aria-hidden width="18" height="18" viewBox="0 0 18 18"><path fill="#4285F4" d="M17.6 9.2c0-.6-.1-1.2-.2-1.7H9v3.2h4.8a4.1 4.1 0 0 1-1.8 2.7v2.2h2.9c1.7-1.6 2.7-3.8 2.7-6.4Z"/><path fill="#34A853" d="M9 18c2.4 0 4.5-.8 6-2.2L12 13.5c-.8.5-1.8.9-3 .9a5.2 5.2 0 0 1-4.9-3.6h-3v2.3A9 9 0 0 0 9 18Z"/><path fill="#FBBC05" d="M4.1 10.8a5.4 5.4 0 0 1 0-3.5V5h-3A9 9 0 0 0 0 9c0 1.4.3 2.8 1 4l3-2.2Z"/><path fill="#EA4335" d="M9 3.6c1.3 0 2.5.5 3.5 1.4l2.6-2.6A8.7 8.7 0 0 0 9 0a9 9 0 0 0-8 5l3 2.3A5.2 5.2 0 0 1 9 3.6Z"/></svg>; }
