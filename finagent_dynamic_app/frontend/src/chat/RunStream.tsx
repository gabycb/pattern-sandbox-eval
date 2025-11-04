import { useEffect, useMemo, useRef, useState } from 'react';
import { CheckCircle2, Loader2, PlayCircle, RefreshCcw, StopCircle, WifiOff } from 'lucide-react';
import type { AgentMessage } from '../lib/api';
import { apiClient, type ChatStatusResponse } from '../lib/api';
import type { ChatRunResult } from './chatTypes';
import { useChatStream } from './useChatStream';

interface RunStreamProps {
  taskId: string;
  sessionId: string;
  hubUrl?: string;
  group?: string;
  onComplete: (result: ChatRunResult) => void;
}

export function RunStream({ taskId, sessionId, hubUrl, group, onComplete }: RunStreamProps) {
  const streamState = useChatStream({ taskId, sessionId, hubUrl, group });
  const [isPolling, setPolling] = useState(false);
  const [pollError, setPollError] = useState<string | null>(null);
  const [status, setStatus] = useState<'running' | 'failed' | 'done'>('running');
  const [fallbackMessages, setFallbackMessages] = useState<AgentMessage[]>([]);
  const [fallbackPlan, setFallbackPlan] = useState<ChatStatusResponse['plan'] | null>(null);
  const hasEmittedComplete = useRef(false);

  useEffect(() => {
    hasEmittedComplete.current = false;
    setStatus('running');
    setFallbackMessages([]);
    setFallbackPlan(null);
    setPollError(null);
  }, [taskId, sessionId]);

  useEffect(() => {
    let cancelled = false;
    let intervalId: ReturnType<typeof setInterval> | undefined;

    const fetchStatus = async () => {
      setPolling(true);
      try {
        const snapshot = await apiClient.getChatStatus(taskId, sessionId);
        if (!cancelled) {
          const { overall_status: overallStatus } = snapshot.plan;
          setFallbackPlan(snapshot.plan);
          setFallbackMessages(snapshot.messages);
          if (overallStatus === 'completed') {
            setStatus('done');
          } else if (overallStatus === 'failed' || overallStatus === 'cancelled') {
            setStatus('failed');
          } else {
            setStatus('running');
          }
        }
      } catch (error) {
        if (!cancelled) {
          console.warn('Chat status poll failed', error);
          setPollError('Unable to refresh status automatically.');
        }
      } finally {
        if (!cancelled) {
          setPolling(false);
        }
      }
    };

    if (!streamState.connected) {
      fetchStatus();
      intervalId = setInterval(fetchStatus, 5000);
    }

    return () => {
      cancelled = true;
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [streamState.connected, sessionId, taskId]);

  useEffect(() => {
    const currentStatus = streamState.plan?.overall_status;
    if (!currentStatus) {
      return;
    }
    if (currentStatus === 'completed') {
      setStatus('done');
    } else if (currentStatus === 'failed' || currentStatus === 'cancelled') {
      setStatus('failed');
    }
  }, [streamState.plan?.overall_status]);

  const messageList = useMemo(
    () => (streamState.connected ? streamState.messages : fallbackMessages),
    [streamState.connected, streamState.messages, fallbackMessages]
  );

  const activePlan = useMemo(() => streamState.plan ?? fallbackPlan, [streamState.plan, fallbackPlan]);

  const progress = useMemo(() => {
    const steps = activePlan?.steps ?? [];
    const total = steps.length;
    const completed = steps.filter(step => step.status === 'completed').length;
    const runningCount = steps.filter(step => step.status === 'executing').length;
    const pending = total - completed - runningCount;
    const percentage = total === 0 ? 0 : Math.round((completed / total) * 100);
    return { steps, total, completed, runningCount, pending, percentage };
  }, [activePlan?.steps]);

  const currentResult = useMemo<ChatRunResult | null>(() => {
    if (!activePlan) {
      return null;
    }
    return {
      plan: activePlan,
      messages: messageList,
    };
  }, [activePlan, messageList]);

  useEffect(() => {
    if (status === 'done' && currentResult && !hasEmittedComplete.current) {
      hasEmittedComplete.current = true;
      onComplete(currentResult);
    }
  }, [status, currentResult, onComplete]);

  return (
    <div className="space-y-5 px-5 py-6 text-sm text-slate-200">
      <header>
        <h3 className="text-base font-semibold text-white">Autonomous Execution</h3>
        <p className="text-xs text-slate-400">
          Follow live progress as the orchestrator executes each step. We will automatically switch to a summary once
          the workflow completes.
        </p>
      </header>

      {streamState.connectionError && (
        <div className="flex items-center gap-2 rounded border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200">
          <WifiOff className="h-4 w-4" />
          <span>{streamState.connectionError} We will fall back to periodic status checks.</span>
        </div>
      )}

      {pollError && <div className="text-xs text-red-400">{pollError}</div>}

      <section className="space-y-3 rounded-lg border border-slate-800 bg-slate-950 p-4">
        <div className="flex items-center justify-between text-xs text-slate-400">
          <span>Plan progress</span>
          <span>{progress.percentage}%</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
          <div
            className="h-full rounded-full bg-primary-500 transition-[width] duration-500 ease-out"
            style={{ width: `${progress.percentage}%` }}
          />
        </div>
        <div className="flex flex-wrap items-center gap-4 text-xs text-slate-400">
          <span className="flex items-center gap-1 text-primary-300">
            <CheckCircle2 className="h-3.5 w-3.5" /> {progress.completed}/{progress.total} completed
          </span>
          <span className="flex items-center gap-1 text-slate-300">
            <PlayCircle className="h-3.5 w-3.5" /> {progress.runningCount} in progress
          </span>
          <span className="flex items-center gap-1 text-slate-500">
            <StopCircle className="h-3.5 w-3.5" /> {progress.pending} pending
          </span>
        </div>
      </section>

      <section className="space-y-3">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Live timeline</h4>
        <div className="max-h-64 space-y-3 overflow-y-auto rounded border border-slate-800 bg-slate-950 p-3">
          {messageList.length === 0 && <p className="text-xs text-slate-500">Waiting for the first update...</p>}
          {messageList.map(message => (
            <article key={message.id} className="rounded border border-slate-800 bg-slate-900 p-3">
              <header className="mb-2 flex items-center justify-between text-xs text-slate-400">
                <span>{message.source ?? message.agent_name}</span>
                <span>{new Date(message.timestamp).toLocaleTimeString()}</span>
              </header>
              <div className="whitespace-pre-wrap text-xs text-slate-200">{message.content}</div>
            </article>
          ))}
        </div>
      </section>

      <footer className="flex items-center justify-between text-xs text-slate-400">
        <div className="flex items-center gap-2">
          {status === 'running' && <Loader2 className="h-4 w-4 animate-spin text-primary-400" />}
          <span>Status: {status === 'running' ? 'Executing plan...' : status === 'done' ? 'Completed' : 'Failed'}</span>
        </div>
        {isPolling && <RefreshCcw className="h-4 w-4 animate-spin" />}
      </footer>
    </div>
  );
}
