import { useMemo, useState } from 'react';
import type { Plan, ChatConfirmRequest } from '../lib/api';

interface PlanPreviewProps {
  plan: Plan;
  onContinue: () => Promise<void> | void;
  onModify: (patches: ChatConfirmRequest['steps']) => Promise<void> | void;
  onInject: (taskDescription: string) => Promise<void>;
  isSubmitting: boolean;
  isInjecting: boolean;
}

export function PlanPreview({ plan, onContinue, onModify, onInject, isSubmitting, isInjecting }: PlanPreviewProps) {
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [draftTask, setDraftTask] = useState('');
  const [injectSuccess, setInjectSuccess] = useState<string | null>(null);
  const [injectError, setInjectError] = useState<string | null>(null);

  const editableSteps = useMemo(() => plan.steps.map(step => ({ ...step })), [plan.steps]);

  const patches = useMemo(
    () => Object.entries(edits).map(([id, action]) => ({ id, action })),
    [edits]
  );

  const handleInject = async () => {
    const trimmed = draftTask.trim();
    if (!trimmed) {
      return;
    }
    setInjectError(null);
    setInjectSuccess(null);
    try {
      await onInject(trimmed);
      setDraftTask('');
      setInjectSuccess('Task added to the plan. Regenerated steps are displayed above.');
    } catch (error) {
      console.error('Failed to inject task', error);
      setInjectError('Unable to add task. Please try again.');
    }
  };

  return (
    <div className="space-y-6 px-5 py-6">
      <header className="space-y-2">
        <h3 className="text-base font-semibold text-white">Autonomous Plan</h3>
        <p className="text-xs text-slate-400">
          Review the generated steps. You can tweak titles or descriptions before running the autonomous execution, or
          inject additional tasks using the assistant below.
        </p>
      </header>

      <div className="space-y-3">
        {editableSteps.map(step => (
          <div key={step.id} className="rounded-xl border border-slate-800 bg-slate-950 p-4">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>Step {(step.order ?? 0) + 1}</span>
              <span>{step.agent}</span>
            </div>
            <textarea
              className="mt-3 w-full rounded border border-slate-800 bg-slate-900 p-3 text-sm text-white focus:border-primary-500 focus:outline-none"
              rows={3}
              defaultValue={step.action}
              onChange={event => setEdits(prev => ({ ...prev, [step.id]: event.target.value }))}
            />
          </div>
        ))}

        <section className="space-y-3 rounded-xl border border-slate-800 bg-slate-950 p-4">
          <header className="space-y-1">
            <p className="text-xs uppercase tracking-wide text-slate-400">Need another step?</p>
            <p className="text-xs text-slate-500">
              Describe the additional analysis you want. The orchestrator will weave it into the plan in the right
              position.
            </p>
          </header>
          <textarea
            className="w-full rounded border border-slate-800 bg-slate-900 p-3 text-sm text-white focus:border-primary-500 focus:outline-none"
            rows={3}
            value={draftTask}
            placeholder="e.g., Compare the company against top peers"
            onChange={event => setDraftTask(event.target.value)}
            disabled={isInjecting}
          />
          {injectError && <p className="text-xs text-red-400">{injectError}</p>}
          {injectSuccess && <p className="text-xs text-emerald-300">{injectSuccess}</p>}
          <div className="flex items-center justify-end">
            <button
              type="button"
              onClick={handleInject}
              disabled={isInjecting || !draftTask.trim()}
              className="rounded bg-slate-800 px-3 py-2 text-xs font-semibold text-slate-200 transition hover:bg-slate-700 disabled:opacity-50"
            >
              {isInjecting ? 'Adding task…' : 'Add task to plan'}
            </button>
          </div>
        </section>
      </div>

      <div className="space-y-2">
        <button
          type="button"
          onClick={() => onContinue()}
          disabled={isSubmitting || isInjecting}
          className="inline-flex w-full items-center justify-center gap-2 rounded bg-primary-500 px-4 py-3 text-sm font-semibold text-white transition hover:bg-primary-400 disabled:opacity-50"
        >
          Run autonomously
        </button>
        <button
          type="button"
          onClick={() => onModify(patches)}
          disabled={isSubmitting || isInjecting}
          className="inline-flex w-full items-center justify-center gap-2 rounded border border-slate-700 px-4 py-3 text-sm font-semibold text-slate-200 transition hover:border-primary-400 hover:text-primary-300 disabled:opacity-50"
        >
          Save modifications
        </button>
      </div>
    </div>
  );
}
