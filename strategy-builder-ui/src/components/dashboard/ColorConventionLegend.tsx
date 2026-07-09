// 색상 관례 범례 — 한국 시장 관례: 빨강 = 상승/이익, 파랑 = 하락/손실.
// (미국 관례의 반대이므로 항상 표시하는 소형 범례로 명시.) text-profit/text-loss는
// globals.css의 --color-profit/--color-loss에 바인딩돼 팔레트 변경 시 자동 동기화된다.
export default function ColorConventionLegend() {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-xs font-medium text-slate-300"
      title="한국 시장 관례: 빨강 = 상승/이익, 파랑 = 하락/손실 (미국 관례와 반대)"
    >
      <span className="text-profit" aria-hidden="true">
        ●
      </span>
      상승/이익
      <span className="text-loss" aria-hidden="true">
        ●
      </span>
      하락/손실
    </span>
  );
}
