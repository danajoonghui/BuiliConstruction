'use client';
import { useEffect } from 'react';
export default function ErrorBoundary({error,reset}:{error:Error&{digest?:string};reset:()=>void}){useEffect(()=>console.error(error),[error]);return <main className="error-page"><span>Something changed</span><h1>We could not load this view.</h1><p>Your project data is safe. Retry the request or return to the workspace.</p><button className="button button--primary" onClick={reset}>Try again</button></main>}
