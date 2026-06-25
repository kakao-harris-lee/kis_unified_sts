"use client";

import { type KeyboardEvent } from 'react';

export type TradesTab = 'live' | 'history';

interface TradesTabListProps {
  activeTab: TradesTab;
  onChange: (tab: TradesTab) => void;
}

export function TradesTabList({ activeTab, onChange }: TradesTabListProps) {
  const selectTab = (tab: TradesTab) => {
    onChange(tab);
    document.getElementById(tab === 'live' ? 'trades-live-tab' : 'trades-history-tab')?.focus();
  };

  const handleTabKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
      event.preventDefault();
      selectTab(activeTab === 'live' ? 'history' : 'live');
    } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
      event.preventDefault();
      selectTab(activeTab === 'history' ? 'live' : 'history');
    } else if (event.key === 'Home') {
      event.preventDefault();
      selectTab('live');
    } else if (event.key === 'End') {
      event.preventDefault();
      selectTab('history');
    }
  };

  return (
    <div
      role="tablist"
      aria-label="Trade history data source"
      onKeyDown={handleTabKeyDown}
      className="flex w-fit rounded-lg overflow-hidden border border-slate-300"
    >
      <button
        type="button"
        role="tab"
        aria-selected={activeTab === 'live'}
        aria-controls="trades-live-panel"
        id="trades-live-tab"
        onClick={() => selectTab('live')}
        className={`px-4 py-2 text-sm font-medium transition-colors ${
          activeTab === 'live'
            ? 'bg-blue-600 text-white'
            : 'bg-white text-slate-600 hover:bg-slate-100 hover:text-slate-900'
        }`}
      >
        Live (Redis)
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={activeTab === 'history'}
        aria-controls="trades-history-panel"
        id="trades-history-tab"
        onClick={() => selectTab('history')}
        className={`px-4 py-2 text-sm font-medium transition-colors ${
          activeTab === 'history'
            ? 'bg-blue-600 text-white'
            : 'bg-white text-slate-600 hover:bg-slate-100 hover:text-slate-900'
        }`}
      >
        History (DB)
      </button>
    </div>
  );
}
