import type { Metadata } from 'next';
import { LegalPage } from '@/components/legal-page';

export const metadata: Metadata = { title: 'Privacy notice', description: 'How BUILI handles account, project, evidence, and service data.' };

export default function PrivacyPage() {
  return <LegalPage eyebrow="Trust & data" title="Privacy notice" updated="July 13, 2026">
    <p>This notice explains how BUILI Construction (“BUILI,” “we,” or “us”) handles information when you visit our website, create an account, or use the BUILI construction-verification service. A customer agreement or project-specific data-processing agreement may add stricter requirements.</p>
    <h2>Information we handle</h2>
    <p>We handle account identity and contact details; organization, membership, and permission records; project documents, drawings, models, field photos, video, voice, measurements, issues, comments, reports, and approvals; and security, device, access, audit, and service-performance logs. Google sign-in provides a stable account identifier, name, verified email, and profile image when available.</p>
    <h2>Why we use it</h2>
    <p>We use information to provide and secure the service, organize project records, process requested documents and evidence, generate review-required drafts, support users, investigate errors or misuse, preserve audit history, and meet contractual or legal obligations. BUILI does not treat an automated result as a final construction decision.</p>
    <h2>Service providers and external processing</h2>
    <p>We use infrastructure, identity, communications, monitoring, and security providers to operate BUILI. Google processes sign-in. External AI or 3D-generation providers are used only when the relevant feature is enabled and the project is permitted to use it. Generated provider files are copied into BUILI-controlled storage and remain review-required. We do not sell personal information.</p>
    <h2>Retention and security</h2>
    <p>Project records are retained according to the customer organization&apos;s configured retention and contractual requirements. Security and audit records may be retained longer where needed to protect the service or establish project history. We use encryption in transit, private object storage, project-scoped access controls, version history, and audited reviewer actions; no system can guarantee absolute security.</p>
    <h2>Your choices</h2>
    <p>Organization administrators control project access and may export or request deletion of eligible data. You may request access, correction, deletion, or account assistance at <a href="mailto:privacy@builiconstruction.com">privacy@builiconstruction.com</a>. Some project and audit records may need to be retained under a customer contract, legal obligation, or dispute hold.</p>
    <h2>International use and children</h2>
    <p>BUILI and its providers may process information in countries other than yours, subject to applicable contractual safeguards. BUILI is a business service and is not directed to children.</p>
    <h2>Changes</h2>
    <p>We will post material changes here and update the date above. Enterprise customers may receive additional notice as required by contract.</p>
  </LegalPage>;
}
