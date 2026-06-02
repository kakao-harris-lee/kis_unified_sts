"use client";

import { useState, useCallback, useMemo, useEffect, useRef } from "react";
import {
  Upload,
  Sparkles,
  Save,
  BarChart3,
  Loader2,
  Info,
} from "lucide-react";
import { useToast } from "@/components/ui";
import { cn } from "@/lib/utils";
import { FileDropZone } from "@/components/file";
import {
  IndicatorSelector,
  ConditionBuilder,
  RiskManager,
  MetadataEditor,
  PreviewPanel,
  CustomStrategyList,
  RegisteredStrategiesPanel,
  ActiveStrategiesPanel,
  FunnelStage,
  StageRail,
  BuilderActionBar,
  type StageRailItem,
} from "@/components/builder";
import { useStrategyBuilder, INITIAL_STATE } from "@/hooks/useStrategyBuilder";
import { useLocalStrategies } from "@/hooks/useLocalStrategies";
import { listKisBuilderPresets, previewCodeFromState, registerPaperStrategy } from "@/lib/api";
import { parseYamlToBuilderState } from "@/lib/builder/yamlImporter";
import {
  computeStageStatuses,
  firstIncompleteStageId,
  type StageId,
} from "@/lib/builder/stageStatus";
import type { StrategyInfo } from "@/types/signal";
import type { BuilderState } from "@/types/builder";

interface BackendPresetStrategy {
  id: string;
  name: string;
  description: string;
  category: string;
  state: BuilderState;
}

export default function BuilderPage() {
  const [activeStage, setActiveStage] = useState<StageId>("metadata");
  const [registering, setRegistering] = useState(false);
  const [lastRegistered, setLastRegistered] = useState<{ name: string } | null>(null);
  const [showImport, setShowImport] = useState(false);
  const [showPreview, setShowPreview] = useState(false);

  const [presetStrategies, setPresetStrategies] = useState<BackendPresetStrategy[]>([]);
  const [isLoadingStrategies, setIsLoadingStrategies] = useState(true);

  // Python preview state
  const [pythonContent, setPythonContent] = useState<string>("");
  const [pythonLoading, setPythonLoading] = useState(false);
  const [pythonError, setPythonError] = useState<string>("");
  const pythonRequestRef = useRef(0);

  const builder = useStrategyBuilder();
  const localStrategies = useLocalStrategies();
  const toast = useToast();

  useEffect(() => {
    async function loadStrategies() {
      try {
        const response = await listKisBuilderPresets();
        const strategies: BackendPresetStrategy[] = (response.strategies || [])
          .filter((s: StrategyInfo) => s.builder_state)
          .map((s: StrategyInfo) => ({
            id: s.id,
            name: s.name,
            description: s.description,
            category: s.category,
            state: s.builder_state as BuilderState,
          }));
        setPresetStrategies(strategies);
      } catch {
        // silently fail - strategies will show as empty
      } finally {
        setIsLoadingStrategies(false);
      }
    }
    loadStrategies();
  }, []);

  // Reset python preview when builder state changes
  useEffect(() => {
    setPythonContent("");
    setPythonError("");
  }, [builder.state.entry, builder.state.exit, builder.state.indicators]);

  const STAGES = useMemo(
    () =>
      [
        { id: "metadata", stepNum: 1, label: "전략 정보", shortLabel: "정보" },
        { id: "indicators", stepNum: 2, label: "지표 선택", shortLabel: "지표" },
        { id: "entry", stepNum: 3, label: "진입 조건", shortLabel: "진입" },
        { id: "exit", stepNum: 4, label: "청산 조건", shortLabel: "청산" },
        { id: "risk", stepNum: 5, label: "리스크 관리", shortLabel: "리스크" },
      ] as const,
    [],
  );

  const stageStatuses = useMemo(
    () => computeStageStatuses(builder.state),
    [builder.state],
  );

  const railStages: StageRailItem[] = useMemo(
    () =>
      STAGES.map((s) => ({
        id: s.id,
        stepNum: s.stepNum,
        shortLabel: s.shortLabel,
        status: stageStatuses[s.id],
      })),
    [STAGES, stageStatuses],
  );

  const handleJumpToStage = useCallback((id: StageId) => {
    setActiveStage(id);
    document
      .getElementById(`stage-${id}`)
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  // Scroll-spy: keep the active StageRail chip in sync with the stage nearest
  // the top of the viewport as the user scrolls the funnel manually (not just
  // on chip click). Click-jump still sets activeStage immediately; this keeps
  // it correct afterwards.
  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return;
    const els = STAGES.map((s) => document.getElementById(`stage-${s.id}`)).filter(
      (el): el is HTMLElement => el !== null,
    );
    if (els.length === 0) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const topMost = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        if (topMost) {
          setActiveStage(topMost.target.id.replace("stage-", "") as StageId);
        }
      },
      { rootMargin: "-15% 0px -75% 0px" },
    );
    els.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [STAGES]);

  const handleRegisterDraft = useCallback(async () => {
    if (!builder.isValid) {
      toast.error(builder.validationErrors.join("\n"));
      const first = firstIncompleteStageId(builder.state);
      if (first) handleJumpToStage(first);
      return;
    }
    setRegistering(true);
    try {
      const result = await registerPaperStrategy({ builder_state: builder.state });
      setLastRegistered({ name: result.name });
      toast.success(`'${result.name}' 전략을 페이퍼에 등록했습니다.`);
    } catch (err) {
      toast.error(`등록 실패: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setRegistering(false);
    }
  }, [builder, toast, handleJumpToStage]);

  const handleImport = useCallback((_file: File, content: string) => {
    try {
      const { state: newState, warnings } = parseYamlToBuilderState(content);
      builder.loadState(newState);
      setShowImport(false);
      toast.success("전략을 불러왔습니다.");
      warnings.forEach((msg) => toast.warning(msg));
    } catch (error) {
      toast.error(
        `YAML 파싱 실패: ${error instanceof Error ? error.message : "알 수 없는 오류"}`
      );
    }
  }, [builder, toast]);

  const handleSelectCustomStrategy = useCallback(
    (strategy: { state: typeof INITIAL_STATE }) => {
      builder.loadState(strategy.state);
    },
    [builder]
  );

  const handleSelectPreset = useCallback(
    (preset: BackendPresetStrategy) => {
      builder.loadState(preset.state);
    },
    [builder]
  );

  const handleSaveCustomStrategy = useCallback(() => {
    if (!builder.isValid) {
      toast.error(builder.validationErrors.join("\n"));
      const first = firstIncompleteStageId(builder.state);
      if (first) handleJumpToStage(first);
      return;
    }
    localStrategies.save(builder.state);
    toast.success(`"${builder.state.metadata.name}" 전략이 저장되었습니다.`);
  }, [builder, localStrategies, toast, handleJumpToStage]);

  const handleCreateNew = useCallback(() => {
    // Auto-pick an unused "내 전략 N" so the user doesn't collide with
    // the previous draft or the default INITIAL_STATE name.
    const existingNames = new Set(
      localStrategies.strategies.map((s) => s.name),
    );
    let counter = 1;
    let newName = "내 전략 1";
    while (existingNames.has(newName)) {
      counter += 1;
      newName = `내 전략 ${counter}`;
    }

    // 1) Wipe back to INITIAL_STATE, 2) seed the unique name + a fresh
    // empty description so the user lands on a clearly-blank canvas,
    // 3) jump straight to the metadata step so they can rename or
    // describe before defining conditions.
    builder.reset();
    builder.setMetadata({
      name: newName,
      description: "",
      category: "custom",
      tags: [],
      author: "user",
    });
    handleJumpToStage("metadata");
    toast.success(`새 전략 "${newName}" — 정보를 입력하고 저장하세요.`);
  }, [builder, localStrategies.strategies, toast, handleJumpToStage]);

  // YAML export handler for PreviewPanel
  const handleExportYaml = useCallback(() => {
    const content = builder.toYamlString;
    if (!content) return;
    const filename = builder.state.metadata.name
      ? `${builder.state.metadata.name.toLowerCase().replace(/\s+/g, "_")}.kis.yaml`
      : "strategy.kis.yaml";
    const blob = new Blob([content], { type: "application/x-yaml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [builder.toYamlString, builder.state.metadata.name]);

  // Python export handler
  const handleExportPython = useCallback(() => {
    if (!pythonContent) return;
    const filename = builder.state.metadata.name
      ? `strategy_${builder.state.metadata.name.toLowerCase().replace(/\s+/g, "_")}.py`
      : "strategy.py";
    const blob = new Blob([pythonContent], { type: "text/x-python" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [pythonContent, builder.state.metadata.name]);

  // Python preview fetcher
  const handleRequestPython = useCallback(async () => {
    if (builder.state.entry.conditions.length === 0) return;

    const requestId = ++pythonRequestRef.current;
    setPythonLoading(true);
    setPythonError("");

    try {
      const response = await previewCodeFromState(builder.state);
      if (requestId !== pythonRequestRef.current) return; // stale request
      if (response.status === "success" && response.code) {
        setPythonContent(response.code);
      } else {
        setPythonError(response.message || "코드 생성 실패");
      }
    } catch (error) {
      if (requestId !== pythonRequestRef.current) return;
      setPythonError(error instanceof Error ? error.message : "API 오류");
    } finally {
      if (requestId === pythonRequestRef.current) {
        setPythonLoading(false);
      }
    }
  }, [builder.state]);

  const builderYamlContent = useMemo(() => {
    return builder.toYamlString;
  }, [builder.toYamlString]);

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-display text-slate-900 dark:text-white flex items-center gap-2">
            <Sparkles className="w-7 h-7 text-primary" aria-hidden="true" />
            전략 빌더
          </h1>
          <p className="text-body text-slate-500 dark:text-slate-400 mt-1">
            기술적 지표 기반 매매 전략을 시각적으로 구성하세요
          </p>
        </div>

        {/* Mobile preview toggle */}
        <button
          onClick={() => setShowPreview(!showPreview)}
          className={cn(
            "lg:hidden flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors focus-ring",
            showPreview
              ? "bg-primary text-white"
              : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"
          )}
          aria-label="미리보기 토글"
        >
          <Info className="w-4 h-4" aria-hidden="true" />
        </button>
      </div>

      {/* Main Layout */}
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Left: Strategy List */}
        <div className="lg:col-span-1 space-y-4">
          {/* Preset strategies */}
          <div className="card">
            <h2 className="text-subheading text-slate-900 dark:text-white mb-4 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-primary" aria-hidden="true" />
              기본 전략
              <span className="text-caption text-slate-400 font-normal">({presetStrategies.length})</span>
            </h2>
            <div className="space-y-2 max-h-[300px] overflow-y-auto scrollbar-thin">
              {isLoadingStrategies ? (
                <div className="flex items-center justify-center py-8 text-slate-400">
                  <Loader2 className="w-5 h-5 animate-spin mr-2" aria-hidden="true" />
                  <span className="text-sm">전략 로딩 중...</span>
                </div>
              ) : presetStrategies.length === 0 ? (
                <div className="text-center py-8 text-slate-400 text-sm">
                  전략이 없습니다
                </div>
              ) : (
                presetStrategies.map((preset) => (
                  <button
                    key={preset.id}
                    onClick={() => handleSelectPreset(preset)}
                    className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:border-primary hover:bg-primary/5 transition-all text-left focus-ring"
                    aria-label={`${preset.name} 전략 선택`}
                  >
                    <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                      <BarChart3 className="w-4 h-4 text-primary" aria-hidden="true" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-sm text-slate-900 dark:text-white truncate">
                        {preset.name}
                      </div>
                      <div className="text-xs text-slate-500 truncate">
                        {preset.category}
                      </div>
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>

          {/* My Strategies */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-subheading text-slate-900 dark:text-white flex items-center gap-2">
                <Save className="w-4 h-4 text-primary" aria-hidden="true" />
                내 전략
              </h2>
              <button
                onClick={() => setShowImport(!showImport)}
                className={cn(
                  "flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium transition-colors focus-ring",
                  showImport
                    ? "bg-primary text-white"
                    : "text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
                )}
                aria-label="YAML 파일 가져오기"
              >
                <Upload className="w-3.5 h-3.5" aria-hidden="true" />
                Import
              </button>
            </div>
            {showImport && (
              <div className="mb-3">
                <FileDropZone onFileSelect={handleImport} />
              </div>
            )}
            <CustomStrategyList
              strategies={localStrategies.strategies}
              selectedId={null}
              onSelect={handleSelectCustomStrategy}
              onDelete={localStrategies.remove}
              onDuplicate={localStrategies.duplicate}
              onCreateNew={handleCreateNew}
            />
          </div>

          {/* Active (runtime) strategies — read-only */}
          <ActiveStrategiesPanel assetClass={builder.state.assetClass} />

          {/* Registered paper-trading strategies */}
          <RegisteredStrategiesPanel />
        </div>

        {/* Right: Funnel Feed + Preview */}
        <div className="lg:col-span-2 grid lg:grid-cols-[auto_minmax(0,1fr)_minmax(0,340px)] gap-4">
          {/* Left mini-rail */}
          <StageRail stages={railStages} activeId={activeStage} onJump={handleJumpToStage} />

          {/* Funnel feed */}
          <div className={cn("min-w-0", showPreview && "hidden lg:block")}>
            {/* Asset Class Toggle */}
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">자산군</span>
              <div role="group" aria-label="자산군" className="inline-flex rounded-lg border border-slate-200 dark:border-slate-700 p-0.5">
                {(["stock", "futures"] as const).map((ac) => (
                  <button
                    key={ac}
                    type="button"
                    aria-pressed={builder.state.assetClass === ac}
                    onClick={() => builder.setAssetClass(ac)}
                    className={cn(
                      "px-3 py-1 text-sm rounded-md transition-colors",
                      builder.state.assetClass === ac
                        ? "bg-blue-600 text-white"
                        : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800",
                    )}
                  >
                    {ac === "stock" ? "주식" : "선물"}
                  </button>
                ))}
              </div>
              {builder.state.assetClass === "futures" && (
                <span className="text-xs text-amber-600 dark:text-amber-400">
                  선물은 long-only (Phase 1) · EOD 15:15·하드스톱 자동 적용
                </span>
              )}
            </div>

            <div className="space-y-1">
              <FunnelStage id="metadata" stepNum={1} title="전략 정보" status={stageStatuses.metadata}>
                <MetadataEditor metadata={builder.state.metadata} onChange={builder.setMetadata} />
              </FunnelStage>

              <FunnelStage id="indicators" stepNum={2} title="지표 선택" status={stageStatuses.indicators}>
                <IndicatorSelector
                  selectedIndicators={builder.state.indicators}
                  onAddIndicator={builder.addIndicatorWithAutoConditions}
                  onUpdateIndicator={builder.updateIndicator}
                  onRemoveIndicator={builder.removeIndicator}
                  createIndicator={builder.createIndicator}
                  assetClass={builder.state.assetClass}
                />
              </FunnelStage>

              <FunnelStage id="entry" stepNum={3} title="진입 조건" status={stageStatuses.entry}>
                <ConditionBuilder
                  title="진입 조건"
                  conditionGroup={builder.state.entry}
                  indicators={builder.state.indicators}
                  onAddCondition={builder.addEntryCondition}
                  onAddIndicator={builder.addIndicator}
                  createIndicator={builder.createIndicator}
                  onUpdateCondition={builder.updateEntryCondition}
                  onRemoveCondition={builder.removeEntryCondition}
                  onReorderConditions={builder.reorderEntryConditions}
                  onSetLogic={builder.setEntryLogic}
                />
              </FunnelStage>

              <FunnelStage id="exit" stepNum={4} title="청산 조건" status={stageStatuses.exit}>
                <ConditionBuilder
                  title="청산 조건"
                  conditionGroup={builder.state.exit}
                  indicators={builder.state.indicators}
                  onAddCondition={builder.addExitCondition}
                  onAddIndicator={builder.addIndicator}
                  createIndicator={builder.createIndicator}
                  onUpdateCondition={builder.updateExitCondition}
                  onRemoveCondition={builder.removeExitCondition}
                  onReorderConditions={builder.reorderExitConditions}
                  onSetLogic={builder.setExitLogic}
                />
              </FunnelStage>

              <FunnelStage id="risk" stepNum={5} title="리스크 관리" status={stageStatuses.risk} showConnector={false}>
                <RiskManager risk={builder.state.risk} onChange={builder.setRisk} />
              </FunnelStage>
            </div>

            <BuilderActionBar
              isValid={builder.isValid}
              validationErrors={builder.validationErrors}
              registering={registering}
              lastRegistered={lastRegistered}
              onSave={handleSaveCustomStrategy}
              onRegister={handleRegisterDraft}
              onDismissGuidance={() => setLastRegistered(null)}
            />
          </div>

          {/* Preview Panel */}
          <div className={cn("card self-start sticky top-20", !showPreview && "hidden lg:block")}>
            {showPreview && (
              <button
                onClick={() => setShowPreview(false)}
                className="lg:hidden mb-3 text-sm text-slate-500 hover:text-slate-700"
              >
                &larr; 빌더로 돌아가기
              </button>
            )}
            <PreviewPanel
              yamlContent={builderYamlContent}
              pythonContent={pythonContent}
              pythonLoading={pythonLoading}
              pythonError={pythonError}
              onExport={handleExportYaml}
              onExportPython={handleExportPython}
              onRequestPython={handleRequestPython}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
