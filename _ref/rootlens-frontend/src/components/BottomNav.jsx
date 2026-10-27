import { useEffect, useState } from 'react';
import { Bot } from 'lucide-react';
import { flowSteps } from '../navigation';
import Liquid from './ui/Liquid';
import { STATE_EVENT, openAssistant } from './AssistantDock';

// Floating pill with the three answers (where it breaks, what to change, how much it saves) and the AI assistant.
// Doubles as the phone bottom bar.
const BottomNav = ({ active, onSelect }) => {
  const [aiOpen, setAiOpen] = useState(false);
  useEffect(() => {
    const on = (e) => setAiOpen(Boolean(e.detail));
    addEventListener(STATE_EVENT, on);
    return () => removeEventListener(STATE_EVENT, on);
  }, []);
  return (
  <nav aria-label="Analysis steps" className="fixed bottom-4 left-1/2 z-40 -translate-x-1/2 lg:absolute">
    <ol className="flex items-center gap-0.5 glass-chip rounded-full p-1">
      {flowSteps.map(({ slug, label, icon: Icon }) => {
        const isActive = active === slug && !aiOpen;
        return (
          <li key={slug}>
            <button
              type="button"
              onClick={() => onSelect(slug)}
              aria-current={isActive ? 'step' : undefined}
              aria-label={label}
              className={`relative flex h-9 items-center gap-2 rounded-full px-3 text-sm font-medium transition-colors ${isActive ? 'text-on-accent' : 'text-white/60 hover:text-white'}`}
            >
              {isActive && <Liquid layoutId="bottom-nav-pill" axis="x" className="inset-0 rounded-full" />}
              <Icon size={16} className="relative shrink-0" />
              <span className={`relative whitespace-nowrap ${isActive ? '' : 'hidden md:inline'}`}>{label}</span>
            </button>
          </li>
        );
      })}
      <li className="ml-0.5 border-l border-white/15 pl-0.5">
        <button
          type="button"
          onClick={() => openAssistant()}
          aria-haspopup="dialog"
          aria-expanded={aiOpen}
          className={`relative flex h-9 items-center gap-2 rounded-full px-3 text-sm font-medium transition-colors ${aiOpen ? 'text-on-accent' : 'text-white/60 hover:text-white'}`}
        >
          {aiOpen && <Liquid layoutId="bottom-nav-pill" axis="x" className="inset-0 rounded-full" />}
          <Bot size={16} className="relative shrink-0" />
          <span className="relative whitespace-nowrap">AI assistant</span>
        </button>
      </li>
    </ol>
  </nav>
  );
};

export default BottomNav;
