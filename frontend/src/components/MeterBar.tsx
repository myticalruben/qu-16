interface MeterBarProps {
  /** Nivel normalizado de 0 a 1. */
  level: number
  label: string
  muted?: boolean
  className?: string
}

const clampLevel = (level: number): number => {
  if (!Number.isFinite(level)) return 0
  return Math.min(1, Math.max(0, level))
}

/**
 * Medidor vertical dibujado con un único div de relleno y altura por CSS.
 * No usa canvas: es barato de repintar y encaja con la estética LED.
 */
export function MeterBar({
  level,
  label,
  muted = false,
  className = '',
}: MeterBarProps) {
  const normalized = clampLevel(level)
  const percent = Math.round(normalized * 100)

  return (
    <div
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={percent}
      aria-valuetext={`${percent} %`}
      className={`meter-bar relative h-full w-2.5 shrink-0 overflow-hidden rounded-[2px] ${className}`}
    >
      <div
        className="meter-bar__fill absolute inset-x-0 bottom-0"
        style={{
          height: `${percent}%`,
          opacity: muted ? 0.28 : 1,
        }}
      />
      {percent > 0 ? (
        <div
          className="meter-bar__peak absolute inset-x-0 h-px"
          style={{
            bottom: `${Math.max(percent - 1, 0)}%`,
            opacity: muted ? 0.3 : 1,
          }}
        />
      ) : null}
      <div className="meter-bar__segments absolute inset-0" aria-hidden="true" />
    </div>
  )
}
