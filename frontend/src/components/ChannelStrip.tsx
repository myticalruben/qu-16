import type { MixerChannel } from '../store/mixer'
import { FADER_MAX_DB, FADER_MIN_DB } from '../store/mixer'
import { MeterBar } from './MeterBar'

interface ChannelStripProps {
  channel: MixerChannel
  onFaderChange: (id: number, faderDb: number) => void
  onMuteToggle: (id: number) => void
}

/** Marcas de referencia del fader; el recorrido es lineal en dB. */
const FADER_TICKS = [10, 0, -12, -30, -48]

const tickTop = (db: number): number =>
  ((FADER_MAX_DB - db) / (FADER_MAX_DB - FADER_MIN_DB)) * 100

/** Formato de consola: −∞ en el mínimo y un decimal con signo. */
const formatDb = (db: number): string => {
  if (db <= FADER_MIN_DB + 0.05) return '−∞'
  if (Math.abs(db) < 0.05) return '0.0'
  return `${db > 0 ? '+' : '−'}${Math.abs(db).toFixed(1)}`
}

const ariaDb = (db: number): string =>
  db <= FADER_MIN_DB + 0.05 ? 'menos infinito' : `${db.toFixed(1)} dB`

export function ChannelStrip({
  channel,
  onFaderChange,
  onMuteToggle,
}: ChannelStripProps) {
  const { id, name, faderDb, meter, muted, accent } = channel
  const channelNumber = String(id).padStart(2, '0')

  return (
    <article
      data-accent={accent}
      aria-label={`Canal ${id}: ${name}`}
      className="channel-strip flex h-full flex-col overflow-hidden rounded-xl border border-console-line bg-console-panel/95 p-2.5"
    >
      <div className="flex items-center justify-between gap-1">
        <span className="font-mono text-[9px] leading-none tracking-[0.16em] text-console-faint tabular-nums">
          {channelNumber}
        </span>
        <span
          aria-hidden="true"
          className={`h-1.5 w-1.5 rounded-full ${
            muted
              ? 'bg-console-line-strong'
              : 'channel-led shadow-[0_0_7px_var(--channel-accent)]'
          }`}
        />
      </div>

      <h3
        className={`mt-1 truncate text-[12px] font-semibold uppercase leading-tight tracking-[0.04em] ${
          muted ? 'text-console-muted' : 'text-console-ink'
        }`}
        title={name}
      >
        {name}
      </h3>

      <p
        className="mt-0.5 font-mono text-[10px] leading-none tabular-nums text-[var(--channel-accent)]"
        aria-live="off"
      >
        <span className="sr-only">Ganancia: </span>
        {formatDb(faderDb)}
        <span className="ml-1 text-[8px] tracking-[0.08em] text-console-faint">
          dB
        </span>
      </p>

      <div className="mt-2 flex h-44 items-stretch justify-center gap-1.5">
        <MeterBar
          level={meter}
          muted={muted}
          label={`Medidor de ${name}`}
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
            onChange={(event) => onFaderChange(id, Number(event.target.value))}
            aria-label={`Fader de ${name}`}
            aria-valuetext={ariaDb(faderDb)}
            className="fader-range absolute left-1/2 top-1/2 h-8 w-44 -translate-x-1/2 -translate-y-1/2 -rotate-90"
          />
        </div>
      </div>

      <button
        type="button"
        aria-pressed={muted}
        aria-label={`${muted ? 'Activar' : 'Silenciar'} canal ${name}`}
        onClick={() => onMuteToggle(id)}
        className={`mt-2.5 flex w-full items-center justify-center gap-1.5 rounded-md border px-2 py-1.5 font-mono text-[9px] font-semibold uppercase tracking-[0.18em] transition-colors duration-150 ${
          muted
            ? 'border-signal-danger/55 bg-signal-danger/15 text-signal-danger shadow-[inset_0_0_12px_rgba(248,113,113,0.12)]'
            : 'border-console-line bg-console-void/60 text-console-faint hover:border-console-line-strong hover:text-console-muted'
        }`}
      >
        <span
          aria-hidden="true"
          className={`h-1.5 w-1.5 rounded-full ${
            muted
              ? 'bg-signal-danger shadow-[0_0_6px_#f87171]'
              : 'bg-console-line-strong'
          }`}
        />
        Mute
      </button>
    </article>
  )
}
