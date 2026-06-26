"use client";

import { useState } from 'react';
import HeaderBar from '@/components/dashboard/HeaderBar';
import { HistoryTradesTab } from './components/HistoryTradesTab';
import { LiveTradesTab } from './components/LiveTradesTab';
import { TradesTabList, type TradesTab } from './components/TradesTabList';

function Trades() {
  const [activeTab, setActiveTab] = useState<TradesTab>('live');

  return (
    <>
      <HeaderBar />
      <div className="max-w-[1400px] mx-auto px-2 sm:px-4 lg:px-6 pt-2 pb-24 lg:pb-2">
        <div className="space-y-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <h1 className="text-2xl font-bold">Trade History</h1>
            <TradesTabList activeTab={activeTab} onChange={setActiveTab} />
          </div>

          <div
            id={activeTab === 'live' ? 'trades-live-panel' : 'trades-history-panel'}
            role="tabpanel"
            aria-labelledby={activeTab === 'live' ? 'trades-live-tab' : 'trades-history-tab'}
          >
            {activeTab === 'live' ? <LiveTradesTab /> : <HistoryTradesTab />}
          </div>
        </div>
      </div>
    </>
  );
}

export default Trades;
