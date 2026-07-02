export interface SymbolLabelProps {
  code: string | null | undefined
  name?: string | null
  className?: string
  nameClassName?: string
  codeClassName?: string
}

export function symbolDisplayText({
  code,
  name,
}: Pick<SymbolLabelProps, 'code' | 'name'>): string {
  const cleanCode = String(code ?? '').trim()
  const cleanName = String(name ?? '').trim()
  if (cleanName && cleanName !== cleanCode) {
    return `${cleanName} ${cleanCode}`.trim()
  }
  return cleanCode
}

export default function SymbolLabel({
  code,
  name,
  className = '',
  nameClassName = '',
  codeClassName = '',
}: SymbolLabelProps) {
  const cleanCode = String(code ?? '').trim()
  const cleanName = String(name ?? '').trim()
  const hasName = Boolean(cleanName && cleanName !== cleanCode)

  if (!hasName) {
    return (
      <span className={`font-mono ${className} ${codeClassName}`.trim()}>
        {cleanCode || '-'}
      </span>
    )
  }

  return (
    <span className={`inline-flex min-w-0 items-baseline gap-1 ${className}`.trim()}>
      <span className={`min-w-0 truncate font-medium ${nameClassName}`.trim()}>
        {cleanName}
      </span>
      <span className={`shrink-0 font-mono text-xs text-slate-500 ${codeClassName}`.trim()}>
        {cleanCode}
      </span>
    </span>
  )
}
