import type { ChannelKind } from '../store/mixer'
import { FADER_MAX_DB, FADER_MIN_DB } from '../store/mixer'
import { MeterBar } from './MeterBar'

interface ChannelStripProps {
  index: number
  name: string
  /** Nivel real del backend en dB; `null` equivale a −∞. */
  levelDb: number | null
  kind: ChannelKind
  /** Nivel 0..1 de la maqueta animada de medidores. */
  meterLevel?: number
  /** Si es `false` (mesa desconectada), el medidor se queda a cero y quieto. */
  meterActive?: boolean
}

/** Marcas de referencia del fader; el recorrido es lineal en dB. */
const FADER_TICKS = [10, 0, -12, -30, -48]

const KIND_LABELS: Record<ChannelKind, string> = {
  input: 'IN',
  stereo: 'ST',
  other: 'OT',
}

const KIND_NAMES: Record<ChannelKind, string> = {
  input: 'Entrada mono',
  stereo: 'Canal estéreo',
  other: 'Otro tipo de canal',
}

const clamp = (value: number, min: number, max: number): number =>
  Math.min(max, Math.max(min, value))

const tickTop = (db: number): number =>
  ((FADER_MAX_DB - db) / (FADER_MAX_DB - FADER_MIN_DB)) * 100

/** Un `level_db` nulo ocupa el mínimo del recorrido, como en la consola real. */
const faderPosition = (levelDb: number | null): number =>
  levelDb === null ? FADER_MIN_DB : clamp(levelDb, FADER_MIN_DB, FADER_MAX_DB)

/** Formato de consola: −∞ en el mínimo y un decimal con signo. */
const formatDb = (levelDb: number | null): string => {
  if (levelDb === null || levelDb <= FADER_MIN_DB + 0.05) return '−∞'
  if (Math.abs(levelDb) < 0.05) return '0.0'
  return `${levelDb > 0 ? '+' : '−'}${Math.abs(levelDb).toFixed(1)}`
}

const ariaDb = (levelDb: number | null): string =>
  levelDb === null || levelDb <= FADER_MIN_DB + 0.05
    ? 'menos infinito'
    : `${levelDb.toFixed(1)} dB`

export function ChannelStrip({
  index,
  name,
  levelDb,
  kind,
  meterLevel = 0,
  meterActive = false,
}: ChannelStripProps) {
  const unnamed = name.trim() === ''
  const displayName = unnamed ? '—' : name
  const channelNumber = String(index).padStart(2, '0')
  const accent = kind === 'stereo' ? 'amber' : 'cyan'
  const faderDb = faderPosition(levelDb)
  const accessibleName = unnamed ? `canal ${index}` : name
  const kindLabel = KIND_LABELS[kind]
  const kindName = KIND_NAMES[kind]

  return (
    <article
      data-accent={accent}
      data-unnamed={unnamed ? 'true' : undefined}
      aria-label={`Canal ${index}: ${unnamed ? 'sin nombre' : name}`}
      className={`channel-strip flex h-full flex-col overflow-hidden rounded-xl border border-console-line bg-console-panel/95 p-2.5 ${
        unnamed ? 'opacity-60' : ''
      }`}
    >
      <div className="flex items-center justify-between gap-1">
        <span className="font-mono text-[9px] leading-none tracking-[0.16em] text-console-faint tabular-nums">
          {channelNumber}
        </span>
        <span
          aria-hidden="true"
          className={`h-1.5 w-1.5 rounded-full ${
            unnamed
              ? 'bg-console-line-strong'
              : 'channel-led shadow-[0_0_7px_var(--channel-accent)]'
          }`}
        />
      </div>

      <h3
        className={`mt-1 truncate text-[12px] font-semibold uppercase leading-tight tracking-[0.04em] ${
          unnamed ? 'text-console-faint' : 'text-console-ink'
        }`}
        title={unnamed ? `Canal ${index} sin nombre` : name}
      >
        {displayName}
      </h3>

      <p
        className="mt-0.5 font-mono text-[10px] leading-none tabular-nums text-[var(--channel-accent)]"
        aria-live="off"
      >
        <span className="sr-only">Ganancia: </span>
        {formatDb(levelDb)}
        <span className="ml-1 text-[8px] tracking-[0.08em] text-console-faint">
          dB
        </span>
      </p>

      <div className="mt-2 flex h-44 items-stretch justify-center gap-1.5">
        <MeterBar
          level={meterActive ? meterLevel : 0}
          animated={meterActive && meterLevel > 0}
          seed={index}
          label={`Medidor de ${accessibleName}`}
        />

        <div
          aria-hidden="true"
          className="relative w-4 shrink-0 font-mono text-[7px] leading-none text-console-faint tabular-nums"
        >
          {FADER_TICKS.map((db) => (
            <span
              key={db}
              className="absolute right-0 -translate-y-1/2"
              style={{ top: `${tickTop(db)}%` }}
            >
              {db > 0 ? `+${db}` : db}
            </span>
          ))}
        </div>

        <div className="relative w-8 shrink-0">
          <div
            aria-hidden="true"
            className="fader-ticks absolute inset-y-0 right-0 w-1.5 opacity-70"
          />
          <input
            type="range"
            min={FADER_MIN_DB}
            max={FADER_MAX_DB}
            step={0.5}
            value={faderDb}
            disabled
            title="Fader de solo lectura: los comandos llegan en la Fase 3"
            aria-label={`Fader de ${accessibleName}`}
            aria-valuetext={ariaDb(levelDb)}
            className="fader-range absolute left-1/2 top-1/2 h-8 w-44 -translate-x-1/2 -translate-y-1/2 -rotate-90 disabled:cursor-not-allowed"
          />
        </div>
      </div>

      <p
        className="mt-2.5 rounded-md border border-console-line/60 bg-console-void/40 px-2 py-1.5 text-center font-mono text-[8px] uppercase tracking-[0.18em] text-console-faint"
        title={kindName}
      >
        <span aria-hidden="true">{kindLabel}</span>
        <span className="sr-only">{kindName}</span>
      </p>
    </article>
  )
}
