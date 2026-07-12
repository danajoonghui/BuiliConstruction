'use client';
import { createContext, useContext } from 'react';
type WorkspaceContextValue = { demo:boolean; organizationId:string; projectId:string; projectName:string; userName:string };
const WorkspaceContext = createContext<WorkspaceContextValue>({demo:false,organizationId:'',projectId:'',projectName:'',userName:''});
export function DemoModeProvider({ demo, organizationId, projectId, projectName, userName, children }: WorkspaceContextValue & { children: React.ReactNode }) { return <WorkspaceContext.Provider value={{demo,organizationId,projectId,projectName,userName}}>{children}</WorkspaceContext.Provider>; }
export function useWorkspace() { return useContext(WorkspaceContext); }
export function useDemoMode() { return useWorkspace().demo; }
