import Link from 'next/link';
import { ArrowLeft, Check } from 'lucide-react';
import { Brand } from '@/components/brand';

export function AuthShell({ children, title, description }: { children: React.ReactNode; title: string; description: string }) {
  return (
    <main className="auth-page">
      <section className="auth-form-side">
        <div className="auth-top"><Brand/><Link href="/" className="auth-back"><ArrowLeft size={15}/> Back to BUILI</Link></div>
        <div className="auth-form-wrap"><h1>{title}</h1><p>{description}</p>{children}</div>
        <p className="auth-legal">By continuing, you agree to BUILI&apos;s Terms and acknowledge the Privacy Policy.</p>
      </section>
      <aside className="auth-context" aria-label="BUILI product benefits">
        <div className="auth-context-plan" aria-hidden>
          <span/><span/><span/><span/><i/><i/><b/>
        </div>
        <div className="auth-context-copy">
          <p className="eyebrow eyebrow--light"><span/> Evidence before assumption</p>
          <h2>Every construction decision, grounded in the record.</h2>
          <ul><li><Check/> Preserve every source and revision</li><li><Check/> Capture evidence where the condition exists</li><li><Check/> Keep a human reviewer in control</li></ul>
        </div>
      </aside>
    </main>
  );
}
