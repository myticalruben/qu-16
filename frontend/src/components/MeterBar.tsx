import { useEffect, useReducer, useRef, useState } from 'react'

interface MeterBarProps {
  /** Nivel instantáneo del medidor en dB; `null` equivale a silencio. */
  levelDb: number | null
  label: string
  className?: string
}

/** Suelo de la escala: −60 dB pinta 0 % y 0 dB pinta 100 %. */
const METER_FLOOR_DB = -60
/** dB que cae la línea de pico en cada paso de la caída suave. */
const PEAK_DECAY_DB_PER_STEP = 3
/** Cadencia del temporizador que continúa la caída sin mensajes nuevos. */
const PEAK_DECAY_TICK_MS = 160

/** dB → porcentaje de altura, lineal en dB y recortado a la escala. */
const meterPercent = (levelDb: number | null): number => {
  if (levelDb === null || !Number.isFinite(levelDb) || levelDb <= METER_FLOOR_DB)
    return 0
  if (levelDb >= 0) return 100
  return Math.round(((levelDb - METER_FLOOR_DB) / -METER_FLOOR_DB) * 100)
}

/** Umbrales de color: verde ≤ −12 dB, ámbar ≤ −3 dB, rojo por encima. */
const meterZone = (levelDb: number | null): 'green' | 'amber' | 'red' => {
  if (levelDb === null || !Number.isFinite(levelDb) || levelDb <= -12)
    return 'green'
  if (levelDb <= -3) return 'amber'
  return 'red'
}

/** Nivel de trabajo del pico: el suelo cuando la entrada es silencio. */
const meterDbOf = (levelDb: number | null): number =>
  levelDb !== null && Number.isFinite(levelDb) && levelDb > METER_FLOOR_DB
    ? levelDb
    : METER_FLOOR_DB

type PeakAction =
  | { type: 'rise'; level: number }
  | { type: 'decay'; target: number }

/** Sube al instante y baja en pasos de `PEAK_DECAY_DB_PER_STEP`. */
const peakReducer = (peakDb: number, action: PeakAction): number =>
  action.type === 'rise'
    ? Math.max(peakDb, action.level)
    : Math.max(action.target, peakDb - PEAK_DECAY_DB_PER_STEP)

/**
 * Lee la preferencia del sistema sin asumir que `matchMedia` exista (jsdom no
 * lo implementa) y escucha cambios para que el medidor deje de animarse en
 * caliente si el usuario la activa.
 */
function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() =>
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function'
      ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
      : false,
  )

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function')
      return

    const query = window.matchMedia('(prefers-reduced-motion: reduce)')
    const onChange = (event: MediaQueryListEvent) => setReduced(event.matches)

    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])

  return reduced
}

/**
 * Medidor vertical de nivel real. Escala −60 dB → 0 % y 0 dB → 100 %, lineal
 * en dB. Mantiene las capas de segmentos LED y la línea de pico; el relleno y
 * el pico se pintan con altura CSS, sin canvas.
 *
 * El pico es el máximo reciente con caída suave: sube al instante y, cuando la
 * señal queda por debajo, baja en pasos de baja frecuencia con `setTimeout`.
 * No usa `requestAnimationFrame` y deja de programar trabajo al alcanzar el
 * nivel, aunque no lleguen mensajes nuevos.
 */
export function MeterBar({ levelDb, label, className = '' }: MeterBarProps) {
  const reducedMotion = usePrefersReducedMotion()
  const currentDb = meterDbOf(levelDb)
  const [peakDb, dispatchPeak] = useReducer(peakReducer, currentDb)
  const currentRef = useRef(currentDb)

  const percent = meterPercent(levelDb)
  const zone = meterZone(levelDb)

  // El pico se engancha al nivel en cuanto sube, sin esperar al efecto. Con
  // movimiento reducido sigue al nivel en vivo y no se programa ninguna caída.
  const displayPeakDb = reducedMotion
    ? currentDb
    : Math.max(peakDb, currentDb)

  useEffect(() => {
    currentRef.current = currentDb
  }, [currentDb])

  useEffect(() => {
    // Solo se guarda un nuevo máximo cuando el nivel supera al pico; si no,
    // `displayPeakDb` ya sigue al nivel y no hace falta tocar el estado.
    if (reducedMotion || currentDb <= peakDb) return
    dispatchPeak({ type: 'rise', level: currentDb })
  }, [currentDb, peakDb, reducedMotion])

  const falling = !reducedMotion && displayPeakDb > currentDb + 0.5

  useEffect(() => {
    if (!falling) return

    // Caída por pasos con `setTimeout`: sin mensajes nuevos no hay ningún
    // temporizador activo y nunca se usa `requestAnimationFrame`.
    const timer = setTimeout(() => {
      dispatchPeak({ type: 'decay', target: currentRef.current })
    }, PEAK_DECAY_TICK_MS)

    return () => clearTimeout(timer)
  }, [falling, displayPeakDb, reducedMotion])

  const peakPercent = meterPercent(
    displayPeakDb > METER_FLOOR_DB ? displayPeakDb : null,
  )

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
        data-zone={zone}
        style={{ height: `${percent}%` }}
      />
      {peakPercent > 0 ? (
        <div
          className="meter-bar__peak absolute inset-x-0 h-px"
          style={{ bottom: `${peakPercent}%` }}
        />
      ) : null}
      <div className="meter-bar__segments absolute inset-0" aria-hidden="true" />
    </div>
  )
}
