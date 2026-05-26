import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import HeaderBar from '../components/HeaderBar';
import ErrorMessage from '../components/ErrorMessage';
import SideBadge from '../components/SideBadge';
import { strategyLabApi } from '../api/client';
import { useAssetClass } from '../contexts/AssetClassContext';

type Operator = 'gt' | 'gte' | 'lt' | 'lte' | 'eq';
type SignalSide = 'BUY' | 'SELL' | 'HOLD';

interface LabSignal {
  signal_id: string;
  draft_id: string;
  strategy_name: string;
  asset_class: string;
  symbol: string;
  side: SignalSide;
  confidence: number;
  strength: number;
  reason: string;
  reference_price: number;
  orderability: string;
  status: string;
  matched_rules: Array<{
    label: string;
    passed: boolean;
    left_value?: number;
    right_value?: number;
    missing: string[];
  }>;
  indicator_values: Record<string, number>;
}

interface OrderTicket {
  ticket_id: string;
  signal_id: string;
  symbol: string;
  side: SignalSide;
  quantity: number;
  order_amount: number;
  estimated_price: number;
  position_impact: string;
  status: string;
  reason?: string;
}

interface PaperOrder {
  order_id: string;
  ticket_id: string;
  symbol: string;
  side: SignalSide;
  quantity: number;
  price: number;
  status: string;
  fill_id?: string;
  realized_pnl: number;
  reason?: string;
}

function numericValue(value: string, fallback: number) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function isNumeric(value: string) {
  return value.trim() !== '' && Number.isFinite(Number(value));
}

function symbolsFromInput(value: string) {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function StrategyLab() {
  const { selectedAsset } = useAssetClass();
  const [templateApplied, setTemplateApplied] = useState(false);
  const [strategyName, setStrategyName] = useState('Visual Pullback Draft');
  const [symbols, setSymbols] = useState('');
  const [entryIndicator, setEntryIndicator] = useState('rsi');
  const [entryOperator, setEntryOperator] = useState<Operator>('lte');
  const [entryValue, setEntryValue] = useState('30');
  const [exitIndicator, setExitIndicator] = useState('rsi');
  const [exitOperator, setExitOperator] = useState<Operator>('gte');
  const [exitValue, setExitValue] = useState('70');
  const [priceValue, setPriceValue] = useState('');
  const [rsiValue, setRsiValue] = useState('');
  const [sma20Value, setSma20Value] = useState('');
  const [volumeValue, setVolumeValue] = useState('');
  const [orderAmount, setOrderAmount] = useState('1000000');
  const [signals, setSignals] = useState<LabSignal[]>([]);
  const [draftId, setDraftId] = useState<string>('');
  const [selectedTicket, setSelectedTicket] = useState<OrderTicket | null>(null);
  const [lastOrder, setLastOrder] = useState<PaperOrder | null>(null);
  const [formError, setFormError] = useState<string>('');

  const capabilitiesQuery = useQuery({
    queryKey: ['strategy-lab-capabilities'],
    queryFn: () => strategyLabApi.getCapabilities().then((r) => r.data),
    staleTime: 60000,
  });

  useEffect(() => {
    if (!capabilitiesQuery.data || templateApplied) {
      return;
    }
    const template = capabilitiesQuery.data.builder_template;
    if (template?.entry) {
      setEntryIndicator(template.entry.left || 'rsi');
      setEntryOperator(template.entry.operator || 'lte');
      setEntryValue(String(template.entry.right ?? '30'));
    }
    if (template?.exit) {
      setExitIndicator(template.exit.left || 'rsi');
      setExitOperator(template.exit.operator || 'gte');
      setExitValue(String(template.exit.right ?? '70'));
    }
    if (capabilitiesQuery.data.default_order_amount) {
      setOrderAmount(String(capabilitiesQuery.data.default_order_amount));
    }
    setTemplateApplied(true);
  }, [capabilitiesQuery.data, templateApplied]);

  const indicatorOptions: string[] =
    capabilitiesQuery.data?.capabilities?.indicators || [
      'rsi',
      'close',
      'volume',
      'sma_20',
    ];
  const operatorOptions: Operator[] =
    capabilitiesQuery.data?.capabilities?.operators || ['gt', 'gte', 'lt', 'lte', 'eq'];

  const spec = useMemo(
    () => ({
      name: strategyName,
      asset_class: selectedAsset === 'futures' ? 'futures' : 'stock',
      entry: {
        operator: 'all',
        conditions: [
          {
            left: { kind: 'indicator', name: entryIndicator },
            operator: entryOperator,
            right: { kind: 'literal', value: numericValue(entryValue, 0) },
            label: `${entryIndicator} ${entryOperator} ${entryValue}`,
          },
        ],
      },
      exit: {
        operator: 'all',
        conditions: [
          {
            left: { kind: 'indicator', name: exitIndicator },
            operator: exitOperator,
            right: { kind: 'literal', value: numericValue(exitValue, 0) },
            label: `${exitIndicator} ${exitOperator} ${exitValue}`,
          },
        ],
      },
      risk: {
        order_amount: numericValue(orderAmount, 0),
      },
      tags: ['strategy_lab'],
    }),
    [
      entryIndicator,
      entryOperator,
      entryValue,
      exitIndicator,
      exitOperator,
      exitValue,
      orderAmount,
      selectedAsset,
      strategyName,
    ],
  );

  const payload = useMemo(() => {
    const selectedSymbols = symbolsFromInput(symbols);
    const marketData = Object.fromEntries(
      selectedSymbols.map((symbol) => [
        symbol,
        {
          symbol,
          price: numericValue(priceValue, 1),
          indicators: {
            rsi: numericValue(rsiValue, 0),
            close: numericValue(priceValue, 1),
            sma_20: numericValue(sma20Value, 0),
            volume: numericValue(volumeValue, 0),
          },
        },
      ]),
    );
    return {
      spec,
      symbols: selectedSymbols,
      market_data: marketData,
      source: 'preview',
    };
  }, [priceValue, rsiValue, sma20Value, spec, symbols, volumeValue]);

  const previewCode = useMutation({
    mutationFn: () => strategyLabApi.previewCode(spec).then((r) => r.data),
  });

  const previewSignal = useMutation({
    mutationFn: () => strategyLabApi.previewSignal(payload).then((r) => r.data),
    onSuccess: (data) => {
      setDraftId(data.draft_id);
      setSignals(data.signals);
      setSelectedTicket(null);
      setLastOrder(null);
      setFormError('');
    },
    onError: (error: any) => {
      setFormError(error?.response?.data?.detail || error.message || 'Signal preview failed');
    },
  });

  const createTicket = useMutation({
    mutationFn: (signal: LabSignal) =>
      strategyLabApi
        .createOrderTicket(signal.signal_id, {
          order_amount: numericValue(orderAmount, 0),
        })
        .then((r) => r.data),
    onSuccess: (ticket) => {
      setSelectedTicket(ticket);
      setLastOrder(null);
    },
  });

  const submitOrder = useMutation({
    mutationFn: (ticket: OrderTicket) =>
      strategyLabApi.submitPaperOrder(ticket.ticket_id).then((r) => r.data),
    onSuccess: (order) => {
      setLastOrder(order);
    },
  });

  function runPreview() {
    if (payload.symbols.length === 0) {
      setFormError('Enter at least one symbol.');
      return;
    }
    if (numericValue(priceValue, 0) <= 0) {
      setFormError('Enter a positive price.');
      return;
    }
    if (numericValue(orderAmount, 0) <= 0) {
      setFormError('Enter a positive order amount.');
      return;
    }
    if (![rsiValue, sma20Value, volumeValue].every(isNumeric)) {
      setFormError('Enter current indicator values.');
      return;
    }
    setFormError('');
    previewCode.mutate();
    previewSignal.mutate();
  }

  const groupedSignals = {
    BUY: signals.filter((signal) => signal.side === 'BUY'),
    SELL: signals.filter((signal) => signal.side === 'SELL'),
    HOLD: signals.filter((signal) => signal.side === 'HOLD'),
  };

  return (
    <>
      <HeaderBar />
      <div className="max-w-[1400px] mx-auto px-2 sm:px-4 lg:px-6 pt-2 pb-24 lg:pb-2">
        <div className="flex flex-col gap-5">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h1 className="text-2xl font-bold">Strategy Lab</h1>
              <div className="text-sm text-gray-400">
                {draftId || 'Draft not generated'}
              </div>
            </div>
            <button
              onClick={runPreview}
              disabled={previewSignal.isPending}
              className="h-10 px-4 rounded-md bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-sm font-medium"
            >
              Generate Signals
            </button>
          </div>

          {formError && <ErrorMessage message={formError} />}
          {capabilitiesQuery.error && (
            <ErrorMessage message="Strategy Lab capabilities are unavailable." />
          )}

          <div className="grid grid-cols-1 xl:grid-cols-[360px_1fr] gap-5">
            <section className="bg-gray-800 border border-gray-700 rounded-lg p-4">
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Strategy</label>
                  <input
                    value={strategyName}
                    onChange={(event) => setStrategyName(event.target.value)}
                    className="w-full bg-gray-900 border border-gray-600 rounded-md px-3 py-2 text-sm"
                  />
                </div>

                <div>
                  <label className="block text-sm text-gray-400 mb-1">Symbols</label>
                  <input
                    value={symbols}
                    onChange={(event) => setSymbols(event.target.value)}
                    placeholder="symbol1,symbol2"
                    className="w-full bg-gray-900 border border-gray-600 rounded-md px-3 py-2 text-sm"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <NumberField label="Price" value={priceValue} onChange={setPriceValue} />
                  <NumberField label="Order Amount" value={orderAmount} onChange={setOrderAmount} />
                  <NumberField label="RSI" value={rsiValue} onChange={setRsiValue} />
                  <NumberField label="SMA 20" value={sma20Value} onChange={setSma20Value} />
                  <NumberField label="Volume" value={volumeValue} onChange={setVolumeValue} />
                </div>

                <RuleBlock
                  title="Entry"
                  indicator={entryIndicator}
                  operator={entryOperator}
                  value={entryValue}
                  indicators={indicatorOptions}
                  operators={operatorOptions}
                  onIndicator={setEntryIndicator}
                  onOperator={setEntryOperator}
                  onValue={setEntryValue}
                />

                <RuleBlock
                  title="Exit"
                  indicator={exitIndicator}
                  operator={exitOperator}
                  value={exitValue}
                  indicators={indicatorOptions}
                  operators={operatorOptions}
                  onIndicator={setExitIndicator}
                  onOperator={setExitOperator}
                  onValue={setExitValue}
                />
              </div>
            </section>

            <section className="space-y-5">
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                {(['BUY', 'SELL', 'HOLD'] as SignalSide[]).map((side) => (
                  <SignalColumn
                    key={side}
                    title={side}
                    signals={groupedSignals[side]}
                    onTicket={(signal) => createTicket.mutate(signal)}
                    ticketPending={createTicket.isPending}
                  />
                ))}
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                <section className="bg-gray-800 border border-gray-700 rounded-lg p-4">
                  <h2 className="text-sm font-semibold text-gray-200 mb-3">Order Ticket</h2>
                  {selectedTicket ? (
                    <TicketView
                      ticket={selectedTicket}
                      onSubmit={() => submitOrder.mutate(selectedTicket)}
                      pending={submitOrder.isPending}
                    />
                  ) : (
                    <div className="text-sm text-gray-500">No ticket selected</div>
                  )}
                </section>

                <section className="bg-gray-800 border border-gray-700 rounded-lg p-4">
                  <h2 className="text-sm font-semibold text-gray-200 mb-3">Paper Fill</h2>
                  {lastOrder ? (
                    <OrderView order={lastOrder} />
                  ) : (
                    <div className="text-sm text-gray-500">No paper order submitted</div>
                  )}
                </section>
              </div>

              <section className="bg-gray-800 border border-gray-700 rounded-lg p-4">
                <h2 className="text-sm font-semibold text-gray-200 mb-3">Generated Preview</h2>
                <pre className="max-h-80 overflow-auto rounded-md bg-gray-950 p-3 text-xs text-gray-300">
                  {previewCode.data?.python || JSON.stringify(spec, null, 2)}
                </pre>
              </section>
            </section>
          </div>
        </div>
      </div>
    </>
  );
}

function NumberField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div>
      <label className="block text-sm text-gray-400 mb-1">{label}</label>
      <input
        type="number"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full bg-gray-900 border border-gray-600 rounded-md px-3 py-2 text-sm"
      />
    </div>
  );
}

function RuleBlock({
  title,
  indicator,
  operator,
  value,
  indicators,
  operators,
  onIndicator,
  onOperator,
  onValue,
}: {
  title: string;
  indicator: string;
  operator: Operator;
  value: string;
  indicators: string[];
  operators: Operator[];
  onIndicator: (value: string) => void;
  onOperator: (value: Operator) => void;
  onValue: (value: string) => void;
}) {
  return (
    <div className="border border-gray-700 rounded-lg p-3">
      <div className="text-sm font-semibold text-gray-200 mb-3">{title}</div>
      <div className="grid grid-cols-[1fr_90px_90px] gap-2">
        <select
          value={indicator}
          onChange={(event) => onIndicator(event.target.value)}
          className="bg-gray-900 border border-gray-600 rounded-md px-2 py-2 text-sm"
        >
          {indicators.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
        <select
          value={operator}
          onChange={(event) => onOperator(event.target.value as Operator)}
          className="bg-gray-900 border border-gray-600 rounded-md px-2 py-2 text-sm"
        >
          {operators.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
        <input
          type="number"
          value={value}
          onChange={(event) => onValue(event.target.value)}
          className="bg-gray-900 border border-gray-600 rounded-md px-2 py-2 text-sm"
        />
      </div>
    </div>
  );
}

function SignalColumn({
  title,
  signals,
  onTicket,
  ticketPending,
}: {
  title: SignalSide;
  signals: LabSignal[];
  onTicket: (signal: LabSignal) => void;
  ticketPending: boolean;
}) {
  return (
    <section className="bg-gray-800 border border-gray-700 rounded-lg p-4 min-h-[260px]">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-gray-200">{title}</h2>
        <span className="text-xs text-gray-400">{signals.length}</span>
      </div>
      <div className="space-y-3">
        {signals.length === 0 ? (
          <div className="text-sm text-gray-500">No signals</div>
        ) : (
          signals.map((signal) => (
            <div key={signal.signal_id} className="rounded-lg border border-gray-700 bg-gray-900 p-3">
              <div className="flex items-center justify-between gap-2">
                <div className="font-medium">{signal.symbol}</div>
                <SideBadge side={signal.side} />
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-gray-400">
                <Metric label="Price" value={signal.reference_price.toLocaleString()} />
                <Metric label="Strength" value={`${(signal.strength * 100).toFixed(0)}%`} />
              </div>
              <div className="mt-3 text-xs text-gray-300">{signal.reason}</div>
              <div className="mt-2 space-y-1">
                {signal.matched_rules.map((rule) => (
                  <div key={rule.label} className="flex items-center justify-between text-xs">
                    <span className={rule.passed ? 'text-green-300' : 'text-gray-500'}>
                      {rule.label}
                    </span>
                    <span className={rule.passed ? 'text-green-300' : 'text-gray-500'}>
                      {rule.passed ? 'pass' : 'fail'}
                    </span>
                  </div>
                ))}
              </div>
              {signal.side !== 'HOLD' && (
                <button
                  onClick={() => onTicket(signal)}
                  disabled={ticketPending || signal.orderability !== 'paper_orderable'}
                  className="mt-3 w-full h-9 rounded-md bg-gray-700 hover:bg-gray-600 disabled:opacity-50 text-sm"
                >
                  {signal.side === 'BUY' ? 'Create Buy Ticket' : 'Create Sell Ticket'}
                </button>
              )}
            </div>
          ))
        )}
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-gray-500">{label}</div>
      <div className="text-gray-200">{value}</div>
    </div>
  );
}

function TicketView({
  ticket,
  onSubmit,
  pending,
}: {
  ticket: OrderTicket;
  onSubmit: () => void;
  pending: boolean;
}) {
  return (
    <div className="space-y-3 text-sm">
      <div className="flex items-center justify-between">
        <span className="font-medium">{ticket.symbol}</span>
        <SideBadge side={ticket.side} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Metric label="Quantity" value={ticket.quantity.toLocaleString()} />
        <Metric label="Price" value={ticket.estimated_price.toLocaleString()} />
        <Metric label="Amount" value={ticket.order_amount.toLocaleString()} />
        <Metric label="Status" value={ticket.status} />
      </div>
      <div className="text-gray-300">{ticket.position_impact}</div>
      {ticket.reason && <div className="text-red-300">{ticket.reason}</div>}
      <button
        onClick={onSubmit}
        disabled={pending || ticket.status !== 'ready'}
        className="w-full h-10 rounded-md bg-green-700 hover:bg-green-600 disabled:opacity-50"
      >
        Submit Paper Order
      </button>
    </div>
  );
}

function OrderView({ order }: { order: PaperOrder }) {
  return (
    <div className="space-y-3 text-sm">
      <div className="flex items-center justify-between">
        <span className="font-medium">{order.symbol}</span>
        <SideBadge side={order.side} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Metric label="Status" value={order.status} />
        <Metric label="Quantity" value={order.quantity.toLocaleString()} />
        <Metric label="Price" value={order.price.toLocaleString()} />
        <Metric label="Realized PnL" value={order.realized_pnl.toLocaleString()} />
      </div>
      {order.fill_id && <div className="text-green-300">Fill {order.fill_id}</div>}
      {order.reason && <div className="text-red-300">{order.reason}</div>}
    </div>
  );
}

export default StrategyLab;
