import type { Metadata } from 'next';
import { LegalPage } from '@/components/legal-page';

export const metadata: Metadata = { title: 'Terms of use', description: 'Terms governing access to the BUILI website and evaluation service.' };

export default function TermsPage() {
  return <LegalPage eyebrow="Service terms" title="Terms of use" updated="July 13, 2026">
    <p>These terms govern access to the public BUILI website and any preview or evaluation workspace provided without a separate signed customer agreement. If your organization signs a customer agreement with BUILI, that agreement controls the paid service and prevails where it conflicts with these terms.</p>
    <h2>Accounts and authority</h2>
    <p>You must provide accurate account information, safeguard your access, and promptly report suspected compromise. You may upload or manage project information only when authorized by the relevant organization and project owner. Organization administrators control membership and project permissions.</p>
    <h2>Acceptable use</h2>
    <p>You may not bypass security controls, access another organization&apos;s data, probe or disrupt the service, upload malware, use BUILI to violate law or third-party rights, or represent an unreviewed automated result as an approved professional or contractual decision.</p>
    <h2>Project content</h2>
    <p>You retain rights in content you are authorized to provide. You grant BUILI the limited rights needed to host, process, transform, display, and export that content to operate the requested service. You are responsible for permissions, notices, and lawful collection of field images, voice, documents, and personal information.</p>
    <h2>Automated and generated output</h2>
    <p>2D-to-3D models, document extraction, spatial alignment, transcription, issue classification, and draft reports can be incomplete or wrong. Outputs remain non-authoritative until an authorized human reviews the governing source, revision, evidence, tolerances, and proposed action. BUILI does not provide architectural, engineering, legal, safety, cost, or claims advice.</p>
    <h2>Preview availability</h2>
    <p>Evaluation features may change, be limited, or be withdrawn. Do not rely on a demo workspace for production records. We may suspend access to protect users, projects, or the service, or to respond to unlawful or abusive use.</p>
    <h2>Intellectual property and feedback</h2>
    <p>BUILI and its licensors own the service, software, design, and documentation, excluding customer content. If you provide feedback, you allow BUILI to use it without restriction or compensation, provided we do not identify confidential customer content in doing so.</p>
    <h2>Disclaimers and liability</h2>
    <p>The preview service is provided on an “as available” basis without warranties to the extent permitted by law. BUILI is not responsible for construction decisions made without required professional and project review. Liability, governing law, service levels, indemnities, and commercial warranties for production customers must be set by a signed customer agreement.</p>
    <h2>Contact</h2>
    <p>Questions about these terms can be sent to <a href="mailto:legal@builiconstruction.com">legal@builiconstruction.com</a>.</p>
  </LegalPage>;
}
