import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { strategiesApi } from '../api/client';
import ErrorMessage from './ErrorMessage';

interface StrategyFormProps {
  mode: 'create' | 'edit';
  initialData?: {
    name: string;
    asset_class: string;
    enabled: boolean;
    description?: string;
    entry: { type: string; params: Record<string, unknown> };
    exit: { type: string; params: Record<string, unknown> };
    position: { type: string; params: Record<string, unknown> };
  };
  onSuccess?: () => void;
  onCancel?: () => void;
}

interface JSONSchema {
  type: string;
  properties: Record<
    string,
    {
      type: string;
      description?: string;
      default?: unknown;
      minimum?: number;
      maximum?: number;
      enum?: string[];
    }
  >;
  required?: string[];
  description?: string;
}

interface ValidationError {
  valid: boolean;
  errors: string[];
  warnings: string[];
  message: string;
}

const ENTRY_TYPES = [
  { value: 'mean_reversion', label: 'Mean Reversion' },
  { value: 'breakout', label: 'Breakout' },
  { value: 'opening_volume_surge', label: 'Opening Volume Surge' },
  { value: 'stochrsi_trend', label: 'StochRSI Trend' },
  { value: 'volume_accumulation', label: 'Volume Accumulation' },
  { value: 'trix_golden', label: 'TRIX Golden' },
  { value: 'rl_mppo', label: 'RL MPPO' },
];

const EXIT_TYPES = [
  { value: 'three_stage', label: 'Three Stage' },
  { value: 'momentum_decay', label: 'Momentum Decay' },
  { value: 'rl_mppo_exit', label: 'RL MPPO Exit' },
  { value: 'trix_golden_exit', label: 'TRIX Golden Exit' },
];

const POSITION_TYPES = [
  { value: 'fixed', label: 'Fixed' },
  { value: 'kelly', label: 'Kelly Criterion' },
  { value: 'risk_parity', label: 'Risk Parity' },
];

function StrategyForm({ mode, initialData, onSuccess, onCancel }: StrategyFormProps) {
  const queryClient = useQueryClient();
  const [name, setName] = useState(initialData?.name || '');
  const [assetClass, setAssetClass] = useState<'stock' | 'futures'>(
    (initialData?.asset_class as 'stock' | 'futures') || 'stock'
  );
  const [enabled, setEnabled] = useState(initialData?.enabled ?? true);
  const [description, setDescription] = useState(initialData?.description || '');

  const [entryType, setEntryType] = useState(initialData?.entry.type || 'mean_reversion');
  const [exitType, setExitType] = useState(initialData?.exit.type || 'three_stage');
  const [positionType, setPositionType] = useState(initialData?.position.type || 'fixed');

  const [entryParams, setEntryParams] = useState<Record<string, unknown>>(
    initialData?.entry.params || {}
  );
  const [exitParams, setExitParams] = useState<Record<string, unknown>>(
    initialData?.exit.params || {}
  );
  const [positionParams, setPositionParams] = useState<Record<string, unknown>>(
    initialData?.position.params || {}
  );

  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [validationWarnings, setValidationWarnings] = useState<string[]>([]);

  // Fetch schemas for current selections
  const { data: entrySchema } = useQuery<JSONSchema>({
    queryKey: ['schema', 'entry', entryType],
    queryFn: () =>
      strategiesApi.schema({ entry_type: entryType }).then((r) => r.data),
    enabled: !!entryType,
  });

  const { data: exitSchema } = useQuery<JSONSchema>({
    queryKey: ['schema', 'exit', exitType],
    queryFn: () =>
      strategiesApi.schema({ exit_type: exitType }).then((r) => r.data),
    enabled: !!exitType,
  });

  const { data: positionSchema } = useQuery<JSONSchema>({
    queryKey: ['schema', 'position', positionType],
    queryFn: () =>
      strategiesApi.schema({ position_type: positionType }).then((r) => r.data),
    enabled: !!positionType,
  });

  // Reset params when type changes
  useEffect(() => {
    if (entrySchema && mode === 'create') {
      const defaults: Record<string, unknown> = {};
      if (entrySchema.properties) {
        Object.entries(entrySchema.properties).forEach(([key, prop]) => {
          if (prop.default !== undefined) {
            defaults[key] = prop.default;
          }
        });
      }
      setEntryParams(defaults);
    }
  }, [entryType, entrySchema, mode]);

  useEffect(() => {
    if (exitSchema && mode === 'create') {
      const defaults: Record<string, unknown> = {};
      if (exitSchema.properties) {
        Object.entries(exitSchema.properties).forEach(([key, prop]) => {
          if (prop.default !== undefined) {
            defaults[key] = prop.default;
          }
        });
      }
      setExitParams(defaults);
    }
  }, [exitType, exitSchema, mode]);

  useEffect(() => {
    if (positionSchema && mode === 'create') {
      const defaults: Record<string, unknown> = {};
      if (positionSchema.properties) {
        Object.entries(positionSchema.properties).forEach(([key, prop]) => {
          if (prop.default !== undefined) {
            defaults[key] = prop.default;
          }
        });
      }
      setPositionParams(defaults);
    }
  }, [positionType, positionSchema, mode]);

  // Validate mutation
  const validateMutation = useMutation<ValidationError>({
    mutationFn: () =>
      strategiesApi
        .validate({
          asset_class: assetClass,
          config: {
            strategy: {
              name,
              asset_class: assetClass,
              enabled,
              description,
              entry: { type: entryType, params: entryParams },
              exit: { type: exitType, params: exitParams },
              position: { type: positionType, params: positionParams },
            },
          },
        })
        .then((r) => r.data),
    onSuccess: (data) => {
      setValidationErrors(data.errors);
      setValidationWarnings(data.warnings);
    },
  });

  // Save mutation
  const saveMutation = useMutation({
    mutationFn: () =>
      strategiesApi
        .save({
          asset_class: assetClass,
          name,
          config: {
            strategy: {
              name,
              asset_class: assetClass,
              enabled,
              description,
              entry: { type: entryType, params: entryParams },
              exit: { type: exitType, params: exitParams },
              position: { type: positionType, params: positionParams },
            },
          },
        })
        .then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
      if (onSuccess) {
        onSuccess();
      }
    },
  });

  const handleValidate = () => {
    validateMutation.mutate();
  };

  const handleSave = () => {
    if (!name.trim()) {
      setValidationErrors(['Strategy name is required']);
      return;
    }
    saveMutation.mutate();
  };

  const renderFormField = (
    key: string,
    schema: JSONSchema['properties'][string],
    value: unknown,
    onChange: (key: string, value: unknown) => void
  ) => {
    const isRequired = entrySchema?.required?.includes(key) || false;

    if (schema.type === 'boolean') {
      return (
        <div key={key} className="flex items-center">
          <input
            type="checkbox"
            checked={Boolean(value)}
            onChange={(e) => onChange(key, e.target.checked)}
            className="mr-2"
          />
          <label className="text-sm">
            {key}
            {isRequired && <span className="text-red-400 ml-1">*</span>}
          </label>
          {schema.description && (
            <span className="text-xs text-gray-500 ml-2">({schema.description})</span>
          )}
        </div>
      );
    }

    if (schema.enum) {
      return (
        <div key={key}>
          <label className="block text-sm text-gray-400 mb-1">
            {key}
            {isRequired && <span className="text-red-400 ml-1">*</span>}
          </label>
          {schema.description && (
            <div className="text-xs text-gray-500 mb-1">{schema.description}</div>
          )}
          <select
            value={String(value || '')}
            onChange={(e) => onChange(key, e.target.value)}
            className="bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm w-full"
          >
            <option value="">Select...</option>
            {schema.enum.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </div>
      );
    }

    if (schema.type === 'integer' || schema.type === 'number') {
      return (
        <div key={key}>
          <label className="block text-sm text-gray-400 mb-1">
            {key}
            {isRequired && <span className="text-red-400 ml-1">*</span>}
          </label>
          {schema.description && (
            <div className="text-xs text-gray-500 mb-1">{schema.description}</div>
          )}
          <input
            type="number"
            value={value !== undefined ? Number(value) : ''}
            onChange={(e) =>
              onChange(
                key,
                schema.type === 'integer' ? parseInt(e.target.value) : parseFloat(e.target.value)
              )
            }
            min={schema.minimum}
            max={schema.maximum}
            step={schema.type === 'integer' ? 1 : 0.01}
            className="bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm w-full"
          />
        </div>
      );
    }

    return (
      <div key={key}>
        <label className="block text-sm text-gray-400 mb-1">
          {key}
          {isRequired && <span className="text-red-400 ml-1">*</span>}
        </label>
        {schema.description && (
          <div className="text-xs text-gray-500 mb-1">{schema.description}</div>
        )}
        <input
          type="text"
          value={String(value || '')}
          onChange={(e) => onChange(key, e.target.value)}
          className="bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm w-full"
        />
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="text-lg font-medium mb-4">
          {mode === 'create' ? 'Create New Strategy' : 'Edit Strategy'}
        </h3>

        {/* Basic Info */}
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Strategy Name <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={mode === 'edit'}
                className="bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm w-full disabled:opacity-50"
                placeholder="my_strategy"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Asset Class <span className="text-red-400">*</span>
              </label>
              <select
                value={assetClass}
                onChange={(e) => setAssetClass(e.target.value as 'stock' | 'futures')}
                disabled={mode === 'edit'}
                className="bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm w-full disabled:opacity-50"
              >
                <option value="stock">Stock</option>
                <option value="futures">Futures</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm w-full"
              placeholder="Strategy description..."
            />
          </div>

          <div className="flex items-center">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
              className="mr-2"
            />
            <label className="text-sm">Enable this strategy</label>
          </div>
        </div>
      </div>

      {/* Entry Configuration */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="text-lg font-medium mb-4">Entry Configuration</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">
              Entry Type <span className="text-red-400">*</span>
            </label>
            <select
              value={entryType}
              onChange={(e) => setEntryType(e.target.value)}
              className="bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm w-full"
            >
              {ENTRY_TYPES.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </div>

          {entrySchema?.properties && (
            <div className="border-t border-gray-700 pt-4">
              <div className="text-sm font-medium text-gray-300 mb-3">Parameters</div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {Object.entries(entrySchema.properties).map(([key, schema]) =>
                  renderFormField(key, schema, entryParams[key], (k, v) =>
                    setEntryParams({ ...entryParams, [k]: v })
                  )
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Exit Configuration */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="text-lg font-medium mb-4">Exit Configuration</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">
              Exit Type <span className="text-red-400">*</span>
            </label>
            <select
              value={exitType}
              onChange={(e) => setExitType(e.target.value)}
              className="bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm w-full"
            >
              {EXIT_TYPES.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </div>

          {exitSchema?.properties && (
            <div className="border-t border-gray-700 pt-4">
              <div className="text-sm font-medium text-gray-300 mb-3">Parameters</div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {Object.entries(exitSchema.properties).map(([key, schema]) =>
                  renderFormField(key, schema, exitParams[key], (k, v) =>
                    setExitParams({ ...exitParams, [k]: v })
                  )
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Position Configuration */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="text-lg font-medium mb-4">Position Configuration</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">
              Position Type <span className="text-red-400">*</span>
            </label>
            <select
              value={positionType}
              onChange={(e) => setPositionType(e.target.value)}
              className="bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm w-full"
            >
              {POSITION_TYPES.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </div>

          {positionSchema?.properties && (
            <div className="border-t border-gray-700 pt-4">
              <div className="text-sm font-medium text-gray-300 mb-3">Parameters</div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {Object.entries(positionSchema.properties).map(([key, schema]) =>
                  renderFormField(key, schema, positionParams[key], (k, v) =>
                    setPositionParams({ ...positionParams, [k]: v })
                  )
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Validation Errors/Warnings */}
      {validationErrors.length > 0 && (
        <div className="bg-red-900/20 border border-red-700 rounded-lg p-4">
          <div className="text-red-400 font-medium mb-2">Validation Errors</div>
          <ul className="list-disc list-inside text-sm text-red-300 space-y-1">
            {validationErrors.map((error, i) => (
              <li key={i}>{error}</li>
            ))}
          </ul>
        </div>
      )}

      {validationWarnings.length > 0 && (
        <div className="bg-yellow-900/20 border border-yellow-700 rounded-lg p-4">
          <div className="text-yellow-400 font-medium mb-2">Warnings</div>
          <ul className="list-disc list-inside text-sm text-yellow-300 space-y-1">
            {validationWarnings.map((warning, i) => (
              <li key={i}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Save/Cancel Errors */}
      {saveMutation.isError && (
        <ErrorMessage
          message={
            saveMutation.error instanceof Error
              ? saveMutation.error.message
              : 'Failed to save strategy'
          }
          onRetry={() => saveMutation.reset()}
        />
      )}

      {/* Actions */}
      <div className="flex justify-end gap-3">
        <button
          onClick={handleValidate}
          disabled={validateMutation.isPending}
          className="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded transition-colors disabled:opacity-50"
        >
          {validateMutation.isPending ? 'Validating...' : 'Validate'}
        </button>
        {onCancel && (
          <button
            onClick={onCancel}
            className="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded transition-colors"
          >
            Cancel
          </button>
        )}
        <button
          onClick={handleSave}
          disabled={saveMutation.isPending || validationErrors.length > 0}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded transition-colors disabled:opacity-50"
        >
          {saveMutation.isPending ? 'Saving...' : mode === 'create' ? 'Create Strategy' : 'Save Changes'}
        </button>
      </div>
    </div>
  );
}

export default StrategyForm;
