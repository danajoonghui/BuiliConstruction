import { IssueDetailRouter } from '@/components/issue-detail-router';
export default async function IssueDetailPage({ params }: { params: Promise<{ id: string }> }) { const {id}=await params; return <IssueDetailRouter id={id}/>; }
