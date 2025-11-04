import { MessageSquare } from 'lucide-react';
import { useState } from 'react';
import { ChatPanel } from './ChatPanel';
import { ChatFeatureGate } from './ChatFeatureGate';

export function ChatFab() {
  const [open, setOpen] = useState(false);

  return (
    <ChatFeatureGate>
      <div className="fixed bottom-8 right-8 z-40">
        {open && <ChatPanel onClose={() => setOpen(false)} />}
        <button
          type="button"
          onClick={() => setOpen(prev => !prev)}
          className="flex items-center gap-3 rounded-full bg-primary-500 px-6 py-4 text-base font-semibold text-white shadow-[0_12px_30px_rgba(56,189,248,0.35)] transition hover:bg-primary-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-200"
        >
          <MessageSquare className="h-6 w-6" />
          <div className="flex flex-col items-start leading-tight">
            <span>Research Chat</span>
            <span className="text-xs font-normal text-primary-100/80">An autonomous plan</span>
          </div>
        </button>
      </div>
    </ChatFeatureGate>
  );
}
