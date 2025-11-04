import { useMemo } from 'react';
import { marked } from 'marked';
import type { AgentMessage, Plan } from '../lib/api';

interface RunSummaryProps {
  plan: Plan;
  messages: AgentMessage[];
}

function formatStatus(status: Plan['steps'][number]['status']) {
  switch (status) {
    case 'completed':
      return { label: 'Completed', className: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40' };
    case 'executing':
      return { label: 'Running', className: 'bg-primary-500/10 text-primary-200 border-primary-400/30' };
    case 'failed':
      return { label: 'Failed', className: 'bg-red-500/15 text-red-300 border-red-400/40' };
    case 'awaiting_feedback':
    case 'action_requested':
      return { label: 'Awaiting review', className: 'bg-amber-500/15 text-amber-200 border-amber-300/40' };
    default:
      return { label: 'Pending', className: 'bg-slate-500/15 text-slate-200 border-slate-400/40' };
  }
}

function renderMarkdown(content: string) {
  return { __html: marked.parse(content) as string };
}

export function RunSummary({ plan, messages }: RunSummaryProps) {
  const groupedByStep = useMemo(() => {
    const map = new Map<string, AgentMessage[]>();
    messages.forEach(message => {
      const key = message.step_id ?? 'plan';
      map.set(key, [...(map.get(key) ?? []), message]);
    });
    return map;
  }, [messages]);

  const planLevelMessages = groupedByStep.get('plan') ?? [];
  const orderedSteps = useMemo(() => [...plan.steps].sort((a, b) => (a.order ?? 0) - (b.order ?? 0)), [plan.steps]);

  return (
    <div className="space-y-5 px-5 py-6 text-sm text-slate-100">
      <header className="space-y-2">
        <h3 className="text-base font-semibold text-white">Execution Summary</h3>
        <p className="text-xs text-slate-400">
          Autonomous run complete. Review each step and the agent outputs below.
        </p>
      </header>

      <section className="space-y-3 rounded-xl border border-slate-800 bg-slate-950 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-400">Objective</p>
            <h4 className="text-sm font-semibold text-white">{plan.initial_goal}</h4>
          </div>
          <span className="rounded-full border border-primary-500/40 bg-primary-500/10 px-3 py-1 text-xs font-medium text-primary-200">
            {plan.overall_status.replace('_', ' ')}
          </span>
        </div>
        {plan.summary && (
          <article className="prose prose-invert max-w-none text-xs leading-relaxed" dangerouslySetInnerHTML={renderMarkdown(plan.summary)} />
        )}
      </section>

      <section className="space-y-3">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Step breakdown</h4>
        <div className="space-y-4">
          {orderedSteps.map((step, index) => {
            const statusMeta = formatStatus(step.status);
            const stepMessages = groupedByStep.get(step.id) ?? [];
            return (
              <article key={step.id} className="rounded-xl border border-slate-800 bg-slate-950 p-4">
                <header className="mb-3 flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-wide text-slate-400">Step {index + 1}</p>
                    <h5 className="text-sm font-semibold text-white">{step.action}</h5>
                    <p className="text-xs text-slate-400">Agent: {step.agent}</p>
                  </div>
                  <span className={`rounded-full border px-3 py-1 text-xs font-medium ${statusMeta.className}`}>
                    {statusMeta.label}
                  </span>
                </header>

                {stepMessages.length > 0 && (
                  <div className="space-y-2">
                    {stepMessages.map(message => (
                      <div key={message.id} className="rounded-lg border border-slate-800/70 bg-slate-900/80 p-3">
                        <p className="mb-1 text-[11px] uppercase tracking-wide text-slate-500">
                          {message.message_type.replace('_', ' ')} · {new Date(message.timestamp).toLocaleTimeString()}
                        </p>
                        <div className="prose prose-invert max-w-none text-xs leading-relaxed" dangerouslySetInnerHTML={renderMarkdown(message.content)} />
                      </div>
                    ))}
                  </div>
                )}
              </article>
            );
          })}
        </div>
      </section>

      {planLevelMessages.length > 0 && (
        <section className="space-y-2">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Final outputs</h4>
          <div className="space-y-3 rounded-xl border border-slate-800 bg-slate-950 p-4">
            {planLevelMessages.map(message => (
              <article key={message.id}>
                <p className="mb-1 text-[11px] uppercase tracking-wide text-slate-500">
                  {message.message_type.replace('_', ' ')} · {new Date(message.timestamp).toLocaleTimeString()}
                </p>
                <div className="prose prose-invert max-w-none text-xs leading-relaxed" dangerouslySetInnerHTML={renderMarkdown(message.content)} />
              </article>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
