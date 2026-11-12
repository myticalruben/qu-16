interface MeterBarProps {
  /** Nivel normalizado de 0 a 1. */
  level: number
  label: string
  /** Pulso de maqueta mientras la mesa está conectada. */
  animated?: boolean
  /** Entero estable por canal para variar la fase del pulso. */
  seed?: number
  className?: string
}

const clampLevel = (level: number): number => {
  if (!Number.isFinite(level)) return 0
  return Math.min(1, Math.max(0, level))
}

/**
 * Medidor vertical dibujado con un único div de relleno y altura por CSS.
 * No usa canvas: es barato de repintar y encaja con la estética LED.
 *
 * `animated` solo pinta el pulso de maqueta de la Fase 2; cuando la mesa no
 * está conectada no se anima nada y el relleno queda a cero.
 */
export function MeterBar({
  level,
  label,
  animated = false,
  seed = 0,
  className = '',
}: MeterBarProps) {
  const normalized = clampLevel(level)
  const percent = Math.round(normalized * 100)

  // Cada canal pulsa a un ritmo ligeramente distinto para que el rack no
  // parezca un único bloque sincronizado.
  const demoStyle = animated
    ? {
        animationDuration: `${2.1 + (seed % 5) * 0.23}s`,
        animationDelay: `${-((seed % 7) * 0.19)}s`,
      }
    : undefined

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
        className={`meter-bar__fill absolute inset-x-0 bottom-0 ${
          animated ? 'meter-bar__fill--demo' : ''
        }`}
        style={{
          height: `${percent}%`,
          ...demoStyle,
        }}
      />
      {percent > 0 ? (
        <div
          className="meter-bar__peak absolute inset-x-0 h-px"
          style={{ bottom: `${Math.max(percent - 1, 0)}%` }}
        />
      ) : null}
      <div className="meter-bar__segments absolute inset-0" aria-hidden="true" />
    </div>
  )
}
