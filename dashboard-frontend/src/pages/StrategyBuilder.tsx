import { useMemo, useState, type ReactNode } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import HeaderBar from '../components/HeaderBar';
import ErrorMessage from '../components/ErrorMessage';
import SideBadge from '../components/SideBadge';
import { strategyBuilderApi } from '../api/client';
import { useAssetClass } from '../contexts/AssetClassContext';

type Operator =
  | 'greater_than'
  | 'less_than'
  | 'greater_equal'
  | 'less_equal'
  | 'equals'
  | 'cross_above'
  | 'cross_below';

type OperandType = 'indicator' | 'value' | 'price';
type SignalSide = 'BUY' | 'SELL' | 'HOLD';

interface IndicatorDefinition {
  id: string;
  name: string;
  name_ko: string;
  category: string;
  params: Array<{ name: string; default: number | string; min?: number; max?: number }>;
  outputs: Array<{ id: string; name: string }>;
  default_output: string;
}

interface BuilderIndicator {
  id: string;
  indicator_id: string;
  alias: string;
  params: Record<string, number | string>;
  output: string;
}

interface ConditionOperand {
  type: OperandType;
  indicator_alias?: string;
  indicator_output?: string;
  value?: number;
  price_field?: string;
}

interface BuilderCondition {
  id: string;
  left: ConditionOperand;
  operator: Operator;
  right: ConditionOperand;
}

interface BuilderSignal {
  signal_id: string;
  symbol: string;
  side: SignalSide;
  strength: number;
  reason: string;
  reference_price: number;
  orderability: string;
  matched_conditions: Array<{ label: string; passed: boolean; missing: string[] }>;
}

interface OrderTicket {
  ticket_id: string;
  symbol: string;
  side: SignalSide;
  quantity: number;
  order_amount: number;
  estimated_price: number;
  status: string;
  reason?: string;
}

interface PaperOrder {
  order_id: string;
  symbol: string;
  side: SignalSide;
  status: string;
  quantity: number;
  price: number;
  fill_id?: string;
  reason?: string;
}

const operatorLabels: Record<Operator, string> = {
  greater_than: '>',
  less_than: '<',
  greater_equal: '>=',
  less_equal: '<=',
  equals: '=',
  cross_above: 'cross above',
  cross_below: 'cross below',
};

function uid(prefix: string) {
  return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`;
}

function numberOrZero(value: string) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function StrategyBuilder() {
  const { selectedAsset } = useAssetClass();
  const [name, setName] = useState('Golden Cross Draft');
  const [symbols, setSymbols] = useState('');
  const [indicators, setIndicators] = useState<BuilderIndicator[]>([]);
  const [entryLogic, setEntryLogic] = useState<'AND' | 'OR'>('AND');
  const [exitLogic, setExitLogic] = useState<'AND' | 'OR'>('AND');
  const [entryConditions, setEntryConditions] = useState<BuilderCondition[]>([]);
  const [exitConditions, setExitConditions] = useState<BuilderCondition[]>([]);
  const [closeValues, setCloseValues] = useState('99000,101000');
  const [indicatorSeries, setIndicatorSeries] = useState<Record<string, string>>({});
  const [orderAmount, setOrderAmount] = useState('1000000');
  const [signals, setSignals] = useState<BuilderSignal[]>([]);
  const [selectedTicket, setSelectedTicket] = useState<OrderTicket | null>(null);
  const [lastOrder, setLastOrder] = useState<PaperOrder | null>(null);
  const [formError, setFormError] = useState('');

  const capabilities = useQuery({
    queryKey: ['strategy-builder-capabilities'],
    queryFn: () => strategyBuilderApi.getCapabilities().then((r) => r.data),
    staleTime: 60000,
  });

  const indicatorDefs: IndicatorDefinition[] = capabilities.data?.indicators || [];
  const operators: Operator[] = capabilities.data?.operators || [
    'greater_than',
    'less_than',
    'greater_equal',
    'less_equal',
    'equals',
    'cross_above',
    'cross_below',
  ];
  const priceFields: string[] = capabilities.data?.price_fields || ['close', 'open', 'high', 'low', 'volume'];

  const state = useMemo(
    () => ({
      metadata: {
        id: name.toLowerCase().replace(/[^a-z0-9]+/g, '_') || 'custom_strategy',
        name,
        description: '',
        category: 'custom',
        tags: ['strategy_builder'],
        author: 'STS',
      },
      asset_class: selectedAsset === 'futures' ? 'futures' : 'stock',
      indicators,
      entry: { logic: entryLogic, conditions: entryConditions },
      exit: { logic: exitLogic, conditions: exitConditions },
      risk: {
        order_amount: numberOrZero(orderAmount),
        stop_loss: { enabled: true, percent: 5 },
        take_profit: { enabled: false, percent: 10 },
        trailing_stop: { enabled: false, percent: 3 },
      },
    }),
    [
      entryConditions,
      entryLogic,
      exitConditions,
      exitLogic,
      indicators,
      name,
      orderAmount,
      selectedAsset,
    ],
  );

  const yamlPreview = useMutation({
    mutationFn: () => strategyBuilderApi.previewYaml(state).then((r) => r.data),
  });
  const codePreview = useMutation({
    mutationFn: () => strategyBuilderApi.previewCode(state).then((r) => r.data),
  });
  const previewSignals = useMutation({
    mutationFn: () => strategyBuilderApi.previewSignals(buildSignalPayload()).then((r) => r.data),
    onSuccess: (data) => {
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
    mutationFn: (signal: BuilderSignal) =>
      strategyBuilderApi
        .createOrderTicket(signal.signal_id, { order_amount: numberOrZero(orderAmount) })
        .then((r) => r.data),
    onSuccess: (ticket) => {
      setSelectedTicket(ticket);
      setLastOrder(null);
    },
  });
  const submitOrder = useMutation({
    mutationFn: (ticket: OrderTicket) =>
      strategyBuilderApi.submitPaperOrder(ticket.ticket_id).then((r) => r.data),
    onSuccess: (order) => setLastOrder(order),
  });

  function addIndicator(def: IndicatorDefinition) {
    const count = indicators.filter((indicator) => indicator.indicator_id === def.id).length + 1;
    const alias = `${def.id}_${count}`;
    const params = Object.fromEntries(def.params.map((param) => [param.name, param.default]));
    const indicator = {
      id: uid('ind'),
      indicator_id: def.id,
      alias,
      params,
      output: def.default_output,
    };
    setIndicators((current) => [...current, indicator]);
    setIndicatorSeries((current) => ({
      ...current,
      [`${alias}.${def.default_output}`]: '99,101',
    }));
  }

  function updateIndicator(id: string, updates: Partial<BuilderIndicator>) {
    setIndicators((current) =>
      current.map((indicator) => (indicator.id === id ? { ...indicator, ...updates } : indicator)),
    );
  }

  function addCondition(target: 'entry' | 'exit') {
    if (indicators.length === 0) {
      setFormError('Add at least one indicator first.');
      return;
    }
    const first = indicators[0];
    const condition: BuilderCondition = {
      id: uid('cond'),
      left: {
        type: 'indicator',
        indicator_alias: first.alias,
        indicator_output: first.output,
      },
      operator: 'greater_than',
      right: { type: 'value', value: 0 },
    };
    if (target === 'entry') {
      setEntryConditions((current) => [...current, condition]);
    } else {
      setExitConditions((current) => [...current, condition]);
    }
  }

  function updateCondition(target: 'entry' | 'exit', id: string, updates: Partial<BuilderCondition>) {
    const setter = target === 'entry' ? setEntryConditions : setExitConditions;
    setter((current) =>
      current.map((condition) => (condition.id === id ? { ...condition, ...updates } : condition)),
    );
  }

  function removeCondition(target: 'entry' | 'exit', id: string) {
    const setter = target === 'entry' ? setEntryConditions : setExitConditions;
    setter((current) => current.filter((condition) => condition.id !== id));
  }

  function buildSignalPayload() {
    const selectedSymbols = symbols
      .split(',')
      .map((symbol) => symbol.trim())
      .filter(Boolean);
    const close = parseSeries(closeValues);
    const indicatorsPayload = Object.fromEntries(
      Object.entries(indicatorSeries).map(([key, value]) => [key, parseSeries(value)]),
    );
    return {
      state,
      series: selectedSymbols.map((symbol) => ({
        symbol,
        fields: { close },
        indicators: indicatorsPayload,
      })),
    };
  }

  function runPreview() {
    const selectedSymbols = symbols.split(',').map((symbol) => symbol.trim()).filter(Boolean);
    if (selectedSymbols.length === 0) {
      setFormError('Enter at least one symbol.');
      return;
    }
    if (indicators.length === 0 || entryConditions.length === 0) {
      setFormError('Add indicators and at least one entry condition.');
      return;
    }
    setFormError('');
    yamlPreview.mutate();
    codePreview.mutate();
    previewSignals.mutate();
  }

  return (
    <>
      <HeaderBar />
      <div className="max-w-[1400px] mx-auto px-2 sm:px-4 lg:px-6 pt-2 pb-24 lg:pb-2">
        <div className="space-y-5">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h1 className="text-2xl font-bold">Strategy Builder</h1>
              <div className="text-sm text-gray-400">No-code technical indicator strategy design</div>
            </div>
            <button
              onClick={runPreview}
              disabled={previewSignals.isPending}
              className="h-10 px-4 rounded-md bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-sm font-medium"
            >
              Generate Signals
            </button>
          </div>

          {formError && <ErrorMessage message={formError} />}
          {capabilities.error && <ErrorMessage message="Strategy Builder capabilities are unavailable." />}

          <div className="grid grid-cols-1 xl:grid-cols-[360px_1fr_360px] gap-5">
            <section className="bg-gray-800 border border-gray-700 rounded-lg p-4 space-y-4">
              <TextField label="Strategy" value={name} onChange={setName} />
              <TextField label="Symbols" value={symbols} onChange={setSymbols} placeholder="symbol1,symbol2" />
              <TextField label="Close Series" value={closeValues} onChange={setCloseValues} placeholder="99000,101000" />
              <TextField label="Order Amount" value={orderAmount} onChange={setOrderAmount} />
              <div>
                <h2 className="text-sm font-semibold text-gray-200 mb-2">Indicator Catalog</h2>
                <div className="max-h-80 overflow-auto space-y-2">
                  {indicatorDefs.map((def) => (
                    <button
                      key={def.id}
                      onClick={() => addIndicator(def)}
                      className="w-full text-left rounded-md border border-gray-700 bg-gray-900 hover:bg-gray-700 px-3 py-2"
                    >
                      <div className="text-sm font-medium">{def.name_ko || def.name}</div>
                      <div className="text-xs text-gray-500">{def.category}</div>
                    </button>
                  ))}
                </div>
              </div>
            </section>

            <section className="space-y-5">
              <section className="bg-gray-800 border border-gray-700 rounded-lg p-4">
                <h2 className="text-sm font-semibold text-gray-200 mb-3">Indicators</h2>
                <div className="space-y-3">
                  {indicators.length === 0 ? (
                    <div className="text-sm text-gray-500">No indicators selected</div>
                  ) : (
                    indicators.map((indicator) => {
                      const def = indicatorDefs.find((item) => item.id === indicator.indicator_id);
                      return (
                        <IndicatorCard
                          key={indicator.id}
                          indicator={indicator}
                          definition={def}
                          seriesValue={indicatorSeries[`${indicator.alias}.${indicator.output}`] || ''}
                          onUpdate={(updates) => updateIndicator(indicator.id, updates)}
                          onSeries={(value) =>
                            setIndicatorSeries((current) => ({
                              ...current,
                              [`${indicator.alias}.${indicator.output}`]: value,
                            }))
                          }
                        />
                      );
                    })
                  )}
                </div>
              </section>

              <ConditionEditor
                title="Entry Conditions"
                target="entry"
                logic={entryLogic}
                conditions={entryConditions}
                indicators={indicators}
                operators={operators}
                priceFields={priceFields}
                onLogic={setEntryLogic}
                onAdd={() => addCondition('entry')}
                onUpdate={updateCondition}
                onRemove={removeCondition}
              />
              <ConditionEditor
                title="Exit Conditions"
                target="exit"
                logic={exitLogic}
                conditions={exitConditions}
                indicators={indicators}
                operators={operators}
                priceFields={priceFields}
                onLogic={setExitLogic}
                onAdd={() => addCondition('exit')}
                onUpdate={updateCondition}
                onRemove={removeCondition}
              />

              <SignalBoard
                signals={signals}
                onTicket={(signal) => createTicket.mutate(signal)}
                pending={createTicket.isPending}
              />
            </section>

            <section className="space-y-5">
              <Panel title="YAML Preview">
                <pre className="max-h-72 overflow-auto rounded-md bg-gray-950 p-3 text-xs text-gray-300">
                  {yamlPreview.data?.yaml || JSON.stringify(state, null, 2)}
                </pre>
              </Panel>
              <Panel title="Python Preview">
                <pre className="max-h-72 overflow-auto rounded-md bg-gray-950 p-3 text-xs text-gray-300">
                  {codePreview.data?.python || 'Generate signals to preview code.'}
                </pre>
              </Panel>
              <Panel title="Order Ticket">
                {selectedTicket ? (
                  <div className="space-y-3 text-sm">
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{selectedTicket.symbol}</span>
                      <SideBadge side={selectedTicket.side} />
                    </div>
                    <Metric label="Quantity" value={selectedTicket.quantity.toLocaleString()} />
                    <Metric label="Amount" value={selectedTicket.order_amount.toLocaleString()} />
                    {selectedTicket.reason && <div className="text-red-300">{selectedTicket.reason}</div>}
                    <button
                      onClick={() => submitOrder.mutate(selectedTicket)}
                      disabled={selectedTicket.status !== 'ready' || submitOrder.isPending}
                      className="w-full h-10 rounded-md bg-green-700 hover:bg-green-600 disabled:opacity-50"
                    >
                      Submit Paper Order
                    </button>
                  </div>
                ) : (
                  <div className="text-sm text-gray-500">No ticket selected</div>
                )}
              </Panel>
              <Panel title="Paper Fill">
                {lastOrder ? (
                  <div className="space-y-2 text-sm">
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{lastOrder.symbol}</span>
                      <SideBadge side={lastOrder.side} />
                    </div>
                    <Metric label="Status" value={lastOrder.status} />
                    <Metric label="Quantity" value={lastOrder.quantity.toLocaleString()} />
                    {lastOrder.fill_id && <div className="text-green-300">Fill {lastOrder.fill_id}</div>}
                    {lastOrder.reason && <div className="text-red-300">{lastOrder.reason}</div>}
                  </div>
                ) : (
                  <div className="text-sm text-gray-500">No paper order submitted</div>
                )}
              </Panel>
            </section>
          </div>
        </div>
      </div>
    </>
  );
}

function parseSeries(value: string) {
  return value
    .split(',')
    .map((item) => Number(item.trim()))
    .filter((item) => Number.isFinite(item));
}

function TextField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <div>
      <label className="block text-sm text-gray-400 mb-1">{label}</label>
      <input
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className="w-full bg-gray-900 border border-gray-600 rounded-md px-3 py-2 text-sm"
      />
    </div>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="bg-gray-800 border border-gray-700 rounded-lg p-4">
      <h2 className="text-sm font-semibold text-gray-200 mb-3">{title}</h2>
      {children}
    </section>
  );
}

function IndicatorCard({
  indicator,
  definition,
  seriesValue,
  onUpdate,
  onSeries,
}: {
  indicator: BuilderIndicator;
  definition?: IndicatorDefinition;
  seriesValue: string;
  onUpdate: (updates: Partial<BuilderIndicator>) => void;
  onSeries: (value: string) => void;
}) {
  return (
    <div className="rounded-lg border border-gray-700 bg-gray-900 p-3 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-medium">{definition?.name_ko || indicator.indicator_id}</div>
          <div className="text-xs text-gray-500">{indicator.alias}</div>
        </div>
        <select
          value={indicator.output}
          onChange={(event) => onUpdate({ output: event.target.value })}
          className="bg-gray-950 border border-gray-700 rounded-md px-2 py-1 text-xs"
        >
          {(definition?.outputs || [{ id: 'value', name: 'Value' }]).map((output) => (
            <option key={output.id} value={output.id}>
              {output.name}
            </option>
          ))}
        </select>
      </div>
      <div className="grid grid-cols-2 gap-2">
        {(definition?.params || []).map((param) => (
          <TextField
            key={param.name}
            label={param.name}
            value={String(indicator.params[param.name] ?? param.default)}
            onChange={(value) =>
              onUpdate({
                params: {
                  ...indicator.params,
                  [param.name]: Number.isFinite(Number(value)) ? Number(value) : value,
                },
              })
            }
          />
        ))}
      </div>
      <TextField label="Series" value={seriesValue} onChange={onSeries} placeholder="99,101" />
    </div>
  );
}

function ConditionEditor({
  title,
  target,
  logic,
  conditions,
  indicators,
  operators,
  priceFields,
  onLogic,
  onAdd,
  onUpdate,
  onRemove,
}: {
  title: string;
  target: 'entry' | 'exit';
  logic: 'AND' | 'OR';
  conditions: BuilderCondition[];
  indicators: BuilderIndicator[];
  operators: Operator[];
  priceFields: string[];
  onLogic: (logic: 'AND' | 'OR') => void;
  onAdd: () => void;
  onUpdate: (target: 'entry' | 'exit', id: string, updates: Partial<BuilderCondition>) => void;
  onRemove: (target: 'entry' | 'exit', id: string) => void;
}) {
  return (
    <section className="bg-gray-800 border border-gray-700 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-gray-200">{title}</h2>
        <div className="flex items-center gap-2">
          <select
            value={logic}
            onChange={(event) => onLogic(event.target.value as 'AND' | 'OR')}
            className="bg-gray-900 border border-gray-600 rounded-md px-2 py-1 text-xs"
          >
            <option value="AND">AND</option>
            <option value="OR">OR</option>
          </select>
          <button onClick={onAdd} className="h-8 px-3 rounded-md bg-gray-700 hover:bg-gray-600 text-xs">
            Add
          </button>
        </div>
      </div>
      <div className="space-y-3">
        {conditions.length === 0 ? (
          <div className="text-sm text-gray-500">No conditions</div>
        ) : (
          conditions.map((condition, index) => (
            <div key={condition.id} className="rounded-lg border border-gray-700 bg-gray-900 p-3">
              {index > 0 && <div className="mb-2 text-xs font-semibold text-blue-300">{logic}</div>}
              <div className="grid grid-cols-1 lg:grid-cols-[1fr_120px_1fr_36px] gap-2">
                <OperandEditor
                  operand={condition.left}
                  indicators={indicators}
                  priceFields={priceFields}
                  onChange={(operand) => onUpdate(target, condition.id, { left: operand })}
                />
                <select
                  value={condition.operator}
                  onChange={(event) =>
                    onUpdate(target, condition.id, { operator: event.target.value as Operator })
                  }
                  className="bg-gray-950 border border-gray-700 rounded-md px-2 py-2 text-sm"
                >
                  {operators.map((operator) => (
                    <option key={operator} value={operator}>
                      {operatorLabels[operator] || operator}
                    </option>
                  ))}
                </select>
                <OperandEditor
                  operand={condition.right}
                  indicators={indicators}
                  priceFields={priceFields}
                  onChange={(operand) => onUpdate(target, condition.id, { right: operand })}
                />
                <button
                  onClick={() => onRemove(target, condition.id)}
                  className="rounded-md bg-red-950/50 text-red-300 hover:bg-red-900/70"
                >
                  x
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

function OperandEditor({
  operand,
  indicators,
  priceFields,
  onChange,
}: {
  operand: ConditionOperand;
  indicators: BuilderIndicator[];
  priceFields: string[];
  onChange: (operand: ConditionOperand) => void;
}) {
  return (
    <div className="grid grid-cols-[92px_1fr] gap-2">
      <select
        value={operand.type}
        onChange={(event) => {
          const nextType = event.target.value as OperandType;
          if (nextType === 'value') onChange({ type: 'value', value: 0 });
          if (nextType === 'price') onChange({ type: 'price', price_field: 'close' });
          if (nextType === 'indicator') {
            const first = indicators[0];
            onChange({
              type: 'indicator',
              indicator_alias: first?.alias || '',
              indicator_output: first?.output || 'value',
            });
          }
        }}
        className="bg-gray-950 border border-gray-700 rounded-md px-2 py-2 text-sm"
      >
        <option value="indicator">Indicator</option>
        <option value="price">Price</option>
        <option value="value">Value</option>
      </select>
      {operand.type === 'indicator' && (
        <select
          value={operand.indicator_alias}
          onChange={(event) => {
            const selected = indicators.find((indicator) => indicator.alias === event.target.value);
            onChange({
              type: 'indicator',
              indicator_alias: event.target.value,
              indicator_output: selected?.output || 'value',
            });
          }}
          className="bg-gray-950 border border-gray-700 rounded-md px-2 py-2 text-sm"
        >
          {indicators.map((indicator) => (
            <option key={indicator.id} value={indicator.alias}>
              {indicator.alias}.{indicator.output}
            </option>
          ))}
        </select>
      )}
      {operand.type === 'price' && (
        <select
          value={operand.price_field}
          onChange={(event) => onChange({ type: 'price', price_field: event.target.value })}
          className="bg-gray-950 border border-gray-700 rounded-md px-2 py-2 text-sm"
        >
          {priceFields.map((field) => (
            <option key={field} value={field}>
              {field}
            </option>
          ))}
        </select>
      )}
      {operand.type === 'value' && (
        <input
          type="number"
          value={operand.value ?? 0}
          onChange={(event) => onChange({ type: 'value', value: numberOrZero(event.target.value) })}
          className="bg-gray-950 border border-gray-700 rounded-md px-2 py-2 text-sm"
        />
      )}
    </div>
  );
}

function SignalBoard({
  signals,
  onTicket,
  pending,
}: {
  signals: BuilderSignal[];
  onTicket: (signal: BuilderSignal) => void;
  pending: boolean;
}) {
  return (
    <section className="bg-gray-800 border border-gray-700 rounded-lg p-4">
      <h2 className="text-sm font-semibold text-gray-200 mb-3">Generated Signals</h2>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        {(['BUY', 'SELL', 'HOLD'] as SignalSide[]).map((side) => {
          const items = signals.filter((signal) => signal.side === side);
          return (
            <div key={side} className="rounded-lg border border-gray-700 bg-gray-900 p-3 min-h-[180px]">
              <div className="flex items-center justify-between mb-3">
                <SideBadge side={side} />
                <span className="text-xs text-gray-400">{items.length}</span>
              </div>
              <div className="space-y-2">
                {items.length === 0 ? (
                  <div className="text-sm text-gray-500">No signals</div>
                ) : (
                  items.map((signal) => (
                    <div key={signal.signal_id} className="rounded-md border border-gray-700 p-2">
                      <div className="flex items-center justify-between text-sm">
                        <span className="font-medium">{signal.symbol}</span>
                        <span>{(signal.strength * 100).toFixed(0)}%</span>
                      </div>
                      <div className="mt-1 text-xs text-gray-400">{signal.reason}</div>
                      {signal.matched_conditions.map((condition) => (
                        <div key={condition.label} className="mt-1 flex justify-between text-xs">
                          <span className={condition.passed ? 'text-green-300' : 'text-gray-500'}>
                            {condition.label}
                          </span>
                          <span>{condition.passed ? 'pass' : 'fail'}</span>
                        </div>
                      ))}
                      {signal.side !== 'HOLD' && (
                        <button
                          onClick={() => onTicket(signal)}
                          disabled={pending || signal.orderability !== 'paper_orderable'}
                          className="mt-2 w-full h-8 rounded-md bg-gray-700 hover:bg-gray-600 disabled:opacity-50 text-xs"
                        >
                          Create Ticket
                        </button>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-gray-500">{label}</span>
      <span className="text-gray-200">{value}</span>
    </div>
  );
}

export default StrategyBuilder;
