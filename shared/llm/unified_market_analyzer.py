"""
Unified Market Analyzer

KRX Open API와 FinanceDataReader를 결합한 종합 시장 분석기.
모든 설정값은 LLMConfig에서 로드 (하드코딩 없음).
"""

import json
import os
import re
from dataclasses import asdict
from datetime import datetime
from typing import List, Optional, Tuple

from .config import LLMConfig
from .data_classes import (
    BondData,
    ETFFlowData,
    FuturesData,
    IndexData,
    MarketAnalysis,
    MarketSignal,
    OptionsData,
    RiskMode,
)
from .krx_api_client import KRXOpenAPIClient
from .market_analyzers import (
    BondAnalyzer,
    ETFFlowAnalyzer,
    FuturesAnalyzer,
    IndexAnalyzer,
    OptionsAnalyzer,
    TechnicalAnalyzerForFutures,
)
from .prompt_cache import LLMPromptCache, PromptCacheConfig
from .schema import normalize_market_summary_payload

# Optional LLM imports
try:
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from anthropic import Anthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class UnifiedMarketAnalyzer:
    """
    통합 시장 분석기

    KRX Open API와 FinanceDataReader를 결합하여 종합 시장 분석 수행.
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        """
        초기화

        Args:
            config: LLMConfig 인스턴스. None이면 환경변수에서 로드
        """
        self.config = config or LLMConfig.from_env()

        # 분석기 초기화
        self.krx_client = KRXOpenAPIClient(self.config)
        self.etf_analyzer = ETFFlowAnalyzer(self.config)
        self.futures_analyzer = FuturesAnalyzer(self.config)
        self.options_analyzer = OptionsAnalyzer(self.config)
        self.bond_analyzer = BondAnalyzer(self.config)
        self.index_analyzer = IndexAnalyzer(self.config)
        self.technical_analyzer = TechnicalAnalyzerForFutures(self.config)

        # LLM 클라이언트 (선택적)
        self.llm_client = None
        self.prompt_cache = LLMPromptCache(
            PromptCacheConfig(
                enabled=bool(self.config.llm_prompt_cache_enabled),
                ttl_seconds=max(60, int(self.config.llm_prompt_cache_ttl_seconds)),
                key_prefix=self.config.llm_prompt_cache_prefix,
            )
        )
        provider = (self.config.llm_provider or "openai").lower()
        if self.config.api_key:
            if provider == "claude" and ANTHROPIC_AVAILABLE:
                self.llm_client = Anthropic(api_key=self.config.api_key)
            elif provider == "openai" and OPENAI_AVAILABLE:
                self.llm_client = OpenAI(api_key=self.config.api_key)

        # 출력 디렉토리 생성
        os.makedirs(self.config.output_dir, exist_ok=True)

    def run_analysis(
        self,
        mode: str = "all",
        verbose: bool = True,
        prompt_addendum: str = "",
    ) -> MarketAnalysis:
        """시장 분석 실행.

        Args:
            mode: 분석 모드 ("all", "etf", "futures", "options", "bonds", "indices").
            verbose: 상세 출력 여부.
            prompt_addendum: Optional extra text appended to the LLM system prompt.
                When non-empty, it is injected after the base system prompt so the
                LLM focuses on a specific asset class or trading context.  Loaded
                from ``config/llm.yaml::futures.prompt_addendum`` by
                :class:`~services.trading.llm_context_publisher.LLMContextPublisher`
                when ``asset_class="futures"``.

        Returns:
            MarketAnalysis 결과.
        """
        self._print_header(mode, verbose)

        etf_flows = self._run_etf_flow_analysis(mode, verbose)
        futures, technical = self._run_futures_analysis(mode, verbose)
        options = self._run_options_analysis(mode, verbose)
        bonds = self._run_bond_analysis(mode, verbose)
        indices = self._run_index_analysis(mode, verbose)

        overall_signal, risk_mode = self._determine_overall_signal(
            etf_flows, futures, options, bonds
        )
        sector_rotation = self._build_sector_rotation(etf_flows)

        if verbose:
            print("\n[LLM] Running AI analysis...")
        llm_summary, llm_strategy, key_points = self._run_llm_analysis(
            etf_flows, futures, options, bonds, indices, technical,
            prompt_addendum=prompt_addendum,
        )

        analysis = self._build_market_analysis(
            etf_flows,
            futures,
            options,
            bonds,
            indices,
            overall_signal,
            risk_mode,
            sector_rotation,
            llm_summary,
            llm_strategy,
            key_points,
        )

        self._print_footer(verbose, overall_signal, risk_mode, llm_summary)
        return analysis

    @staticmethod
    def _print_header(mode: str, verbose: bool) -> None:
        if not verbose:
            return
        print("\n" + "=" * 70)
        print("Unified Market Analyzer")
        print("=" * 70)
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Mode: {mode}")

    def _run_etf_flow_analysis(self, mode: str, verbose: bool) -> List[ETFFlowData]:
        if mode not in ("all", "etf"):
            return []
        if verbose:
            print("\n[1/5] ETF Flow Analysis...")
        etf_flows = self.etf_analyzer.analyze()
        if verbose:
            print(f"  Analyzed {len(etf_flows)} sectors")
        return etf_flows

    def _run_futures_analysis(
        self,
        mode: str,
        verbose: bool,
    ) -> tuple[Optional[FuturesData], dict]:
        if mode not in ("all", "futures"):
            return None, {}
        if verbose:
            print("\n[2/5] Futures Analysis...")
        futures = self.futures_analyzer.analyze()
        technical = self.technical_analyzer.analyze()
        if verbose:
            print(f"  KOSPI200: {futures.close_price:.2f}")
        return futures, technical

    def _run_options_analysis(self, mode: str, verbose: bool) -> Optional[OptionsData]:
        if mode not in ("all", "options"):
            return None
        if verbose:
            print("\n[3/5] Options Analysis...")
        options = self.options_analyzer.analyze()
        if verbose:
            print(f"  Put/Call Ratio: {options.put_call_ratio:.2f}")
        return options

    def _run_bond_analysis(self, mode: str, verbose: bool) -> Optional[BondData]:
        if mode not in ("all", "bonds"):
            return None
        if verbose:
            print("\n[4/5] Bond Analysis...")
        bonds = self.bond_analyzer.analyze()
        if verbose:
            print(f"  Risk Mode: {bonds.risk_mode.value}")
        return bonds

    def _run_index_analysis(self, mode: str, verbose: bool) -> List[IndexData]:
        if mode not in ("all", "indices"):
            return []
        if verbose:
            print("\n[5/5] Index Analysis...")
        indices = self.index_analyzer.analyze()
        if verbose:
            print(f"  Analyzed {len(indices)} indices")
        return indices

    @staticmethod
    def _build_sector_rotation(etf_flows: List[ETFFlowData]) -> dict:
        return {e.sector: e.signal for e in etf_flows}

    @staticmethod
    def _build_market_analysis(
        etf_flows: List[ETFFlowData],
        futures: Optional[FuturesData],
        options: Optional[OptionsData],
        bonds: Optional[BondData],
        indices: List[IndexData],
        overall_signal: MarketSignal,
        risk_mode: RiskMode,
        sector_rotation: dict,
        llm_summary: str,
        llm_strategy: str,
        key_points: List[str],
    ) -> MarketAnalysis:
        return MarketAnalysis(
            date=datetime.now().strftime("%Y-%m-%d"),
            etf_flows=etf_flows,
            futures=futures,
            options=options,
            bonds=bonds,
            indices=indices,
            overall_signal=overall_signal,
            risk_mode=risk_mode,
            sector_rotation=sector_rotation,
            llm_summary=llm_summary,
            llm_strategy=llm_strategy,
            key_points=key_points,
        )

    @staticmethod
    def _print_footer(
        verbose: bool,
        overall_signal: MarketSignal,
        risk_mode: RiskMode,
        llm_summary: str,
    ) -> None:
        if not verbose:
            return
        print("\n" + "=" * 70)
        print("Analysis Complete")
        print("=" * 70)
        print(f"Signal: {overall_signal.value}")
        print(f"Risk Mode: {risk_mode.value}")
        print(f"Summary: {llm_summary[:80]}...")

    def _determine_overall_signal(
        self,
        etf_flows: List[ETFFlowData],
        futures: Optional[FuturesData],
        options: Optional[OptionsData],
        bonds: Optional[BondData],
    ) -> Tuple[MarketSignal, RiskMode]:
        """종합 시장 신호 판단"""
        score = 0
        score += self._score_etf_flows(etf_flows)
        score += self._score_futures(futures)
        score += self._score_options(options)
        bond_score, risk_mode = self._score_bonds(bonds)
        score += bond_score

        signal = self._score_to_signal(score)
        return signal, risk_mode

    @staticmethod
    def _score_etf_flows(etf_flows: List[ETFFlowData]) -> int:
        if not etf_flows:
            return 0
        strong = len([e for e in etf_flows if e.signal in ("강세", "상승")])
        weak = len([e for e in etf_flows if e.signal in ("약세", "하락")])
        return (strong - weak) * 5

    @staticmethod
    def _score_futures(futures: Optional[FuturesData]) -> int:
        if not futures:
            return 0
        score = 0
        if futures.change_rate > 0.5:
            score += 15
        elif futures.change_rate > 0:
            score += 5
        elif futures.change_rate < -0.5:
            score -= 15
        elif futures.change_rate < 0:
            score -= 5

        if futures.basis > 0.5:
            score += 5  # 콘탱고
        elif futures.basis < -0.5:
            score -= 5  # 백워데이션
        return score

    @staticmethod
    def _score_options(options: Optional[OptionsData]) -> int:
        if not options:
            return 0
        if options.put_call_ratio > 1.2:
            return 10  # 극단적 비관 -> 반등 기대
        if options.put_call_ratio < 0.8:
            return -10  # 극단적 낙관 -> 조정 주의
        return 0

    @staticmethod
    def _score_bonds(bonds: Optional[BondData]) -> Tuple[int, RiskMode]:
        if not bonds:
            return 0, RiskMode.NEUTRAL

        if bonds.risk_mode == RiskMode.RISK_ON:
            return 10, bonds.risk_mode
        if bonds.risk_mode == RiskMode.RISK_OFF:
            return -10, bonds.risk_mode
        return 0, bonds.risk_mode

    @staticmethod
    def _score_to_signal(score: int) -> MarketSignal:
        if score >= 30:
            return MarketSignal.STRONG_BULLISH
        if score >= 10:
            return MarketSignal.BULLISH
        if score <= -30:
            return MarketSignal.STRONG_BEARISH
        if score <= -10:
            return MarketSignal.BEARISH
        return MarketSignal.NEUTRAL

    def _run_llm_analysis(
        self,
        etf_flows: List[ETFFlowData],
        futures: Optional[FuturesData],
        options: Optional[OptionsData],
        bonds: Optional[BondData],
        indices: List[IndexData],
        technical: dict,
        prompt_addendum: str = "",
    ) -> Tuple[str, str, List[str]]:
        """LLM 기반 분석.

        Args:
            etf_flows: ETF sector flow data.
            futures: Futures market data.
            options: Options market data.
            bonds: Bond market data.
            indices: Index data.
            technical: Technical indicator summary dict.
            prompt_addendum: Optional extra text appended to the base system prompt.
                Non-empty values override the generic analysis framing with an
                asset-class-specific focus (e.g., futures intraday risk/regime).
        """
        if not self.llm_client:
            return self._fallback_analysis(etf_flows, futures, options, bonds, indices)

        # 데이터 요약
        data_summary = self._prepare_data_summary(
            etf_flows, futures, options, bonds, indices, technical
        )

        try:
            base_system_prompt = (
                "당신은 전문 시장 분석가입니다. "
                "주어진 데이터를 바탕으로 간결하고 핵심적인 분석을 제공합니다. "
                "반드시 JSON 형식으로 응답하세요."
            )
            # Append futures-specific (or other asset-class) focus instructions
            # when provided. The addendum is config-driven from
            # config/llm.yaml::futures.prompt_addendum — never hardcoded here.
            addendum = (prompt_addendum or "").strip()
            system_prompt = (
                f"{base_system_prompt}\n\n{addendum}" if addendum else base_system_prompt
            )
            user_prompt = f"""다음 시장 데이터를 분석해주세요:

{data_summary}

다음 JSON 형식으로 응답:
{{
    "summary": "시장 상황 요약 (2-3문장)",
    "strategy": "추천 매매 전략 (2-3문장)",
    "key_points": ["핵심 포인트 1", "핵심 포인트 2", "핵심 포인트 3"]
}}"""

            provider = (self.config.llm_provider or "openai").lower()
            cache_key = LLMPromptCache.build_key(
                key_prefix=self.prompt_cache.config.key_prefix,
                provider=provider,
                model=self.config.model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                extra={
                    "temperature": self.config.temperature,
                    "max_tokens": self.config.max_tokens,
                },
            )
            cached = self.prompt_cache.get(cache_key)
            if cached:
                response_text = cached
            elif provider == "claude":
                response = self.llm_client.messages.create(
                    model=self.config.model,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )
                text_blocks = [b.text for b in response.content if getattr(b, "type", "") == "text"]
                response_text = "\n".join(text_blocks).strip()
                self.prompt_cache.set(cache_key, response_text)
            else:
                response = self.llm_client.chat.completions.create(
                    model=self.config.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )
                response_text = response.choices[0].message.content or ""
                self.prompt_cache.set(cache_key, response_text)

            json_match = re.search(r"\{[\s\S]*\}", response_text)
            if not json_match:
                raise ValueError("No JSON object found in LLM response")
            parsed = json.loads(json_match.group())
            if not isinstance(parsed, dict):
                raise ValueError("LLM payload is not an object")
            result = normalize_market_summary_payload(parsed)

            return (
                result["summary"],
                result["strategy"],
                result["key_points"],
            )

        except Exception as e:
            print(f"LLM analysis failed: {e}")
            return self._fallback_analysis(etf_flows, futures, options, bonds, indices)

    def _prepare_data_summary(
        self,
        etf_flows: List[ETFFlowData],
        futures: Optional[FuturesData],
        options: Optional[OptionsData],
        bonds: Optional[BondData],
        indices: List[IndexData],
        technical: dict,
    ) -> str:
        """데이터 요약 텍스트 생성"""
        summary = "=== Market Data Summary ===\n\n"

        # ETF 자금흐름
        if etf_flows:
            summary += "ETF Sector Flows:\n"
            for etf in etf_flows[:7]:
                summary += (
                    f"- {etf.sector}: {etf.price_change_5d:+.1f}% (5d), "
                    f"volume {etf.volume_ratio:.1f}x, {etf.signal}\n"
                )

        # 선물
        if futures:
            summary += f"\nKOSPI200 Futures:\n"
            summary += f"- Price: {futures.close_price:.2f}, Basis: {futures.basis:+.2f}pt\n"
            summary += f"- Open Interest: {futures.open_interest:,}\n"

        # 기술적 분석
        if technical:
            summary += f"\nTechnical:\n"
            summary += (
                f"- Trend: Short {technical.get('trend_short', 'N/A')} / "
                f"Mid {technical.get('trend_mid', 'N/A')} / "
                f"Long {technical.get('trend_long', 'N/A')}\n"
            )
            summary += f"- RSI: {technical.get('rsi', 'N/A')}\n"

        # 옵션
        if options:
            summary += f"\nOptions:\n"
            summary += f"- Put/Call Ratio: {options.put_call_ratio:.2f}\n"
            summary += f"- Signal: {options.signal}\n"

        # 채권
        if bonds:
            summary += f"\nBonds:\n"
            summary += f"- 3Y: {bonds.yield_3y:.2f}%, 10Y: {bonds.yield_10y:.2f}%\n"
            summary += f"- Spread: {bonds.yield_spread:.2f}%p\n"
            summary += f"- Risk Mode: {bonds.risk_mode.value}\n"

        # 지수
        if indices:
            summary += f"\nIndices:\n"
            for idx in indices[:3]:
                summary += (
                    f"- {idx.name}: {idx.price:,.2f} ({idx.change_5d:+.2f}%, "
                    f"RSI {idx.rsi:.0f}, {idx.trend})\n"
                )

        return summary

    def _fallback_analysis(
        self,
        etf_flows: List[ETFFlowData],
        futures: Optional[FuturesData],
        options: Optional[OptionsData],
        bonds: Optional[BondData],
        _indices: List[IndexData],
    ) -> Tuple[str, str, List[str]]:
        """LLM 없이 규칙 기반 분석"""
        strong, weak = self._fallback_sector_lists(etf_flows)
        summary = self._fallback_summary(strong, weak, options)
        strategy = self._fallback_strategy(bonds, strong)
        key_points = self._fallback_key_points(strong, weak, futures, options, bonds)
        return summary, strategy, key_points

    @staticmethod
    def _fallback_sector_lists(etf_flows: List[ETFFlowData]) -> tuple[List[str], List[str]]:
        strong = [e.sector for e in etf_flows if e.signal in ("강세", "상승")]
        weak = [e.sector for e in etf_flows if e.signal in ("약세", "하락")]
        return strong, weak

    @staticmethod
    def _fallback_summary(
        strong: List[str],
        weak: List[str],
        options: Optional[OptionsData],
    ) -> str:
        if len(strong) > len(weak):
            summary = f"시장은 상승 흐름. {', '.join(strong[:2])} 섹터가 강세. "
        elif len(weak) > len(strong):
            summary = f"시장은 하락 압력. {', '.join(weak[:2])} 섹터가 약세. "
        else:
            summary = "시장은 혼조세. 섹터별 차별화 진행 중. "

        if options:
            pcr_text = "비관적" if options.put_call_ratio > 1 else "낙관적"
            summary += f"풋콜비율 {options.put_call_ratio:.2f}로 {pcr_text} 심리."
        return summary

    @staticmethod
    def _fallback_strategy(bonds: Optional[BondData], strong: List[str]) -> str:
        if bonds and bonds.risk_mode == RiskMode.RISK_ON and strong:
            return f"적극적 매수 전략. {strong[0]} 섹터 ETF 비중 확대 권장."
        if bonds and bonds.risk_mode == RiskMode.RISK_OFF:
            return "방어적 전략. 현금 비중 확대, 채권/금 ETF 고려."
        return "선별적 접근. 강세 섹터 위주 선택적 매수."

    @staticmethod
    def _fallback_key_points(
        strong: List[str],
        weak: List[str],
        futures: Optional[FuturesData],
        options: Optional[OptionsData],
        bonds: Optional[BondData],
    ) -> List[str]:
        key_points = [
            f"강세 섹터: {', '.join(strong[:3]) if strong else '없음'}",
            f"약세 섹터: {', '.join(weak[:3]) if weak else '없음'}",
        ]
        if futures:
            basis_text = "콘탱고" if futures.basis > 0 else "백워데이션"
            key_points.append(f"베이시스: {futures.basis:+.2f}pt ({basis_text})")
        if options:
            key_points.append(f"풋콜비율: {options.put_call_ratio:.2f}")
        if bonds:
            key_points.append(f"리스크모드: {bonds.risk_mode.value}")
        return key_points

    def generate_report(self, analysis: MarketAnalysis) -> str:
        """마크다운 리포트 생성"""
        report = f"""# Market Analysis Report

**Date**: {analysis.date}
**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## Summary Dashboard

| Metric | Value |
|--------|-------|
| **Overall Signal** | {analysis.overall_signal.value} |
| **Risk Mode** | {analysis.risk_mode.value} |

---

## AI Analysis

### Market Summary
{analysis.llm_summary}

### Strategy Recommendation
{analysis.llm_strategy}

### Key Points
"""
        for point in analysis.key_points:
            report += f"- {point}\n"

        # Sector Rotation
        report += "\n---\n\n## Sector Rotation\n\n"
        report += "| Sector | Signal |\n|--------|--------|\n"

        for sector, signal in analysis.sector_rotation.items():
            emoji = "🔺" if signal in ("강세", "상승") else "🔻" if signal in ("약세", "하락") else "➖"
            report += f"| {sector} | {emoji} {signal} |\n"

        # ETF Details
        if analysis.etf_flows:
            report += "\n---\n\n## ETF Flow Details\n\n"
            report += "| Sector | 5D Change | Volume Ratio | Signal |\n"
            report += "|--------|-----------|--------------|--------|\n"

            for etf in sorted(analysis.etf_flows, key=lambda x: x.price_change_5d, reverse=True):
                report += (
                    f"| {etf.sector} | {etf.price_change_5d:+.1f}% | "
                    f"{etf.volume_ratio:.1f}x | {etf.signal} |\n"
                )

        # Futures
        if analysis.futures:
            report += "\n---\n\n## Futures Analysis\n\n"
            report += "| Metric | Value |\n|--------|-------|\n"
            report += f"| Price | {analysis.futures.close_price:.2f} |\n"
            report += f"| Change | {analysis.futures.change_rate:+.2f}% |\n"
            report += f"| Basis | {analysis.futures.basis:+.2f}pt |\n"
            report += f"| Open Interest | {analysis.futures.open_interest:,} |\n"

        # Options
        if analysis.options:
            report += "\n---\n\n## Options Analysis\n\n"
            report += "| Metric | Value |\n|--------|-------|\n"
            report += f"| Put/Call Ratio | {analysis.options.put_call_ratio:.2f} |\n"
            report += f"| Call Volume | {analysis.options.call_volume:,} |\n"
            report += f"| Put Volume | {analysis.options.put_volume:,} |\n"
            report += f"| Signal | {analysis.options.signal} |\n"

        # Bonds
        if analysis.bonds:
            report += "\n---\n\n## Bond Market\n\n"
            report += "| Metric | Value |\n|--------|-------|\n"
            report += f"| 3Y Yield | {analysis.bonds.yield_3y:.2f}% |\n"
            report += f"| 10Y Yield | {analysis.bonds.yield_10y:.2f}% |\n"
            report += f"| Spread | {analysis.bonds.yield_spread:.2f}%p |\n"
            report += f"| Risk Mode | {analysis.bonds.risk_mode.value} |\n"

        # Indices
        if analysis.indices:
            report += "\n---\n\n## Index Analysis\n\n"
            report += "| Index | Price | 5D Change | RSI | Trend |\n"
            report += "|-------|-------|-----------|-----|-------|\n"

            for idx in analysis.indices:
                emoji = "🔺" if idx.change_5d > 0 else "🔻" if idx.change_5d < 0 else "➖"
                report += (
                    f"| {idx.name} | {idx.price:,.2f} | "
                    f"{emoji} {idx.change_5d:+.2f}% | {idx.rsi:.0f} | {idx.trend} |\n"
                )

        report += "\n---\n\n*This report is AI-generated for reference purposes only.*\n"

        return report

    def save_analysis(self, analysis: MarketAnalysis) -> Tuple[str, str]:
        """분석 결과 저장"""
        date_str = datetime.now().strftime("%Y%m%d")

        # Markdown Report
        report = self.generate_report(analysis)
        md_path = os.path.join(self.config.output_dir, f"market_analysis_{date_str}.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(report)

        # JSON Data
        json_data = {
            "date": analysis.date,
            "overall_signal": analysis.overall_signal.value,
            "risk_mode": analysis.risk_mode.value,
            "sector_rotation": analysis.sector_rotation,
            "llm_summary": analysis.llm_summary,
            "llm_strategy": analysis.llm_strategy,
            "key_points": analysis.key_points,
            "etf_flows": [asdict(e) for e in analysis.etf_flows],
        }

        if analysis.futures:
            json_data["futures"] = asdict(analysis.futures)
        if analysis.options:
            json_data["options"] = asdict(analysis.options)
        if analysis.bonds:
            bonds_dict = asdict(analysis.bonds)
            bonds_dict["risk_mode"] = analysis.bonds.risk_mode.value
            json_data["bonds"] = bonds_dict
        if analysis.indices:
            json_data["indices"] = [asdict(i) for i in analysis.indices]

        json_path = os.path.join(self.config.output_dir, f"market_analysis_{date_str}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)

        return md_path, json_path


def run_market_analysis(
    config_path: Optional[str] = None,
    mode: str = "all",
    verbose: bool = True,
    save: bool = True,
) -> MarketAnalysis:
    """
    시장 분석 실행 헬퍼 함수

    Args:
        config_path: YAML 설정 파일 경로 (None이면 환경변수 사용)
        mode: 분석 모드
        verbose: 상세 출력 여부
        save: 결과 저장 여부

    Returns:
        MarketAnalysis 결과
    """
    if config_path:
        config = LLMConfig.from_yaml(config_path)
    else:
        config = LLMConfig.from_env()

    analyzer = UnifiedMarketAnalyzer(config)
    analysis = analyzer.run_analysis(mode=mode, verbose=verbose)

    if save:
        md_path, json_path = analyzer.save_analysis(analysis)
        if verbose:
            print(f"\nSaved: {md_path}")
            print(f"Saved: {json_path}")

    return analysis
