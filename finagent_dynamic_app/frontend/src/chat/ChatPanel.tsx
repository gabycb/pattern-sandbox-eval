import { useMemo, useState } from 'react';
import { Loader2, Play, X } from 'lucide-react';
import { apiClient, ChatConfirmRequest, ChatObjectiveResponse } from '../lib/api';
import { PlanPreview } from './PlanPreview';
import { RunStream } from './RunStream';
import type { ChatRunResult } from './chatTypes';
import { RunSummary } from './RunSummary';

interface ChatPanelProps {
  onClose: () => void;
}

type ViewState = 'idle' | 'planPreview' | 'running' | 'summary' | 'error';

export function ChatPanel({ onClose }: ChatPanelProps) {
  const [objective, setObjective] = useState('');
  const [ticker, setTicker] = useState('');
  const [isSubmitting, setSubmitting] = useState(false);
  const [view, setView] = useState<ViewState>('idle');
  const [planPayload, setPlanPayload] = useState<ChatObjectiveResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [completedResult, setCompletedResult] = useState<ChatRunResult | null>(null);
  const [isInjecting, setInjecting] = useState(false);

  const canSubmit = useMemo(() => objective.trim().length >= 5 && !isSubmitting, [objective, isSubmitting]);

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);

    try {
      const payload = await apiClient.createChatObjective({
        objective: objective.trim(),
        ticker: ticker.trim() || undefined,
      });
      setPlanPayload(payload);
      setView('planPreview');
    } catch (err) {
      console.error('Failed to create chat plan', err);
      setError('Unable to start chat session. Please try again.');
      setView('error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleContinue = async (
    action: 'modify' | 'continue',
    patches?: ChatConfirmRequest['steps']
  ) => {
    if (!planPayload) return;
    setSubmitting(true);
    setError(null);

    try {
      const confirmed = await apiClient.confirmChatPlan({
        task_id: planPayload.task_id,
        session_id: planPayload.session_id,
        action,
        steps: patches,
      });
      setPlanPayload(prev =>
        prev
          ? {
              ...prev,
              plan: confirmed.plan,
              session_id: confirmed.session_id,
            }
          : prev
      );
      if (action === 'continue') {
        setView('running');
      }
    } catch (err) {
      console.error('Failed to confirm plan', err);
      setError('Unable to confirm plan. Please retry.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleInjectTask = async (taskDescription: string) => {
    if (!planPayload) {
      return;
    }
    setInjecting(true);
    try {
      const currentPlan = planPayload.plan;
      await apiClient.injectTask({
        session_id: currentPlan.session_id,
        plan_id: currentPlan.id,
        task_request: taskDescription,
        objective: currentPlan.initial_goal,
        current_steps: currentPlan.steps.map(step => ({
          id: step.id,
          order: step.order ?? 0,
          action: step.action,
          agent: step.agent,
          status: step.status,
        })),
      });

      const refreshedPlan = await apiClient.getPlan(currentPlan.session_id, currentPlan.id);
      setPlanPayload(prev => (prev ? { ...prev, plan: refreshedPlan } : prev));
    } catch (err) {
      console.error('Failed to inject task into plan', err);
      throw err;
    } finally {
      setInjecting(false);
    }
  };

  return (
  <div className="fixed bottom-28 right-8 z-50 w-[80rem] rounded-2xl border border-slate-700 bg-slate-900/95 shadow-2xl backdrop-blur">
      <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
        <h2 className="text-sm font-semibold text-white">Research Chat (Preview)</h2>
        <button type="button" onClick={onClose} className="text-slate-400 transition hover:text-white">
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="max-h-[70vh] overflow-y-auto">
        {view === 'idle' && (
          <div className="space-y-4 px-4 py-5">
            <div>
              <label className="block text-xs font-semibold text-slate-300">Research Objective</label>
              <textarea
                className="mt-2 w-full rounded border border-slate-700 bg-slate-950 p-3 text-sm text-white focus:border-primary-500 focus:outline-none"
                rows={4}
                value={objective}
                onChange={event => setObjective(event.target.value)}
                placeholder="Summarize Tesla's recent performance and forecast the next quarter"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300">Ticker (optional)</label>
              <input
                className="mt-2 w-full rounded border border-slate-700 bg-slate-950 p-3 text-sm text-white focus:border-primary-500 focus:outline-none"
                value={ticker}
                onChange={event => setTicker(event.target.value)}
                placeholder="TSLA"
              />
            </div>

            <button
              type="button"
              onClick={handleSubmit}
              disabled={!canSubmit}
              className="inline-flex w-full items-center justify-center gap-2 rounded bg-primary-500 px-3 py-2 text-sm font-semibold text-white transition hover:bg-primary-400 disabled:opacity-50"
            >
              {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              <span>Generate Plan</span>
            </button>

            {error && <p className="text-xs text-red-400">{error}</p>}
          </div>
        )}

        {view === 'planPreview' && planPayload && (
          <PlanPreview
            plan={planPayload.plan}
            onContinue={() => handleContinue('continue')}
            onModify={(patches: ChatConfirmRequest['steps']) => handleContinue('modify', patches)}
            onInject={handleInjectTask}
            isSubmitting={isSubmitting}
            isInjecting={isInjecting}
          />
        )}

        {view === 'running' && planPayload && (
          <RunStream
            taskId={planPayload.task_id}
            sessionId={planPayload.session_id}
            hubUrl={planPayload.web_pubsub_url}
            group={planPayload.web_pubsub_group}
            onComplete={(result: ChatRunResult) => {
              setCompletedResult(result);
              setView('summary');
            }}
          />
        )}

        {view === 'summary' && completedResult && <RunSummary plan={completedResult.plan} messages={completedResult.messages} />}

        {view === 'error' && error && (
          <div className="px-4 py-6 text-sm text-red-400">
            <p>{error}</p>
          </div>
        )}
      </div>
    </div>
  );
}
