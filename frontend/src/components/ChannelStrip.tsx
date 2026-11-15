import { useEffect, useRef, useState } from 'react'
import type { ChangeEvent, PointerEvent as ReactPointerEvent } from 'react'

import type { ChannelKind } from '../store/mixer'
import { FADER_MAX_DB, FADER_MIN_DB, useMixerStore } from '../store/mixer'
import { MeterBar } from './MeterBar'

interface ChannelStripProps {
  index: number
  name: string
  /** Nivel del fader en dB; `null` equivale a −∞. */
  faderDb: number | null
  kind: ChannelKind
  /** Nivel instantáneo del medidor en dB; `null` equivale a silencio. */
  meterDb: number | null
  /** `true` solo con el candado abierto y la mesa conectada. */
  interactive: boolean
  /** Envía el nivel elegido; se llama al soltar o al teclear. */
  onCommit: (index: number, db: number) => void
}

/** Marcas de referencia del fader; el recorrido es lineal en dB. */
const FADER_TICKS = [10, 0, -12, -30, -48]

/**
 * Freno del fader. Durante los primeros 400 ms de arrastre no se envía nada:
 * el operador está buscando el punto. A partir de ahí se manda como máximo una
 * vez cada 200 ms para que oiga el cambio en vivo, y al soltar se manda el
 * valor final. Así un arrastre de un segundo no genera decenas de POST.
 */
const DRAG_SEND_DELAY_MS = 400
const DRAG_SEND_INTERVAL_MS = 200

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

/** Un fader nulo ocupa el mínimo del recorrido, como en la consola real. */
const faderPosition = (faderDb: number | null): number =>
  faderDb === null ? FADER_MIN_DB : clamp(faderDb, FADER_MIN_DB, FADER_MAX_DB)

/** Formato de consola: −∞ en el mínimo y un decimal con signo. */
const formatDb = (faderDb: number | null): string => {
  if (faderDb === null || faderDb <= FADER_MIN_DB + 0.05) return '−∞'
  if (Math.abs(faderDb) < 0.05) return '0.0'
  return `${faderDb > 0 ? '+' : '−'}${Math.abs(faderDb).toFixed(1)}`
}

const ariaDb = (faderDb: number | null): string =>
  faderDb === null || faderDb <= FADER_MIN_DB + 0.05
    ? 'menos infinito'
    : `${faderDb.toFixed(1)} dB`

export function ChannelStrip({
  index,
  name,
  faderDb,
  kind,
  meterDb,
  interactive,
  onCommit,
}: ChannelStripProps) {
  const unnamed = name.trim() === ''
  const canDrag = interactive && !unnamed
  const displayName = unnamed ? '—' : name
  const channelNumber = String(index).padStart(2, '0')
  const accent = kind === 'stereo' ? 'amber' : 'cyan'
  const accessibleName = unnamed ? `canal ${index}` : name
  const kindLabel = KIND_LABELS[kind]
  const kindName = KIND_NAMES[kind]

  // Valor optimista mientras se arrastra: la tira sigue al dedo aunque el
  // volcado del WebSocket llegue con el nivel viejo.
  const [draftDb, setDraftDb] = useState<number | null>(null)
  const dragRef = useRef<{ startedAt: number; lastSentAt: number } | null>(null)
  const movedRef = useRef(false)
  const beginChannelDrag = useMixerStore((state) => state.beginChannelDrag)
  const endChannelDrag = useMixerStore((state) => state.endChannelDrag)

  const displayedDb = draftDb ?? faderDb
  const faderPositionDb = faderPosition(displayedDb)

  // El rack remonta la tira cuando cambia el candado (ver `key`), así que un
  // cierre a mitad de gesto no deja estados locales colgados. Al desmontar se
  // libera el canal para que el WebSocket vuelva a actualizarlo.
  useEffect(
    () => () => {
      if (dragRef.current !== null) endChannelDrag(index)
    },
    [index, endChannelDrag],
  )

  const handlePointerDown = (event: ReactPointerEvent<HTMLInputElement>) => {
    if (!canDrag) return
    // Solo el botón primario del ratón; el táctil y el lápiz siempre valen.
    if (event.pointerType === 'mouse' && event.button !== 0) return

    dragRef.current = { startedAt: performance.now(), lastSentAt: 0 }
    movedRef.current = false
    setDraftDb(faderPosition(faderDb))
    beginChannelDrag(index)
  }

  const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
    if (!canDrag) return

    const next = clamp(
      Number.parseFloat(event.target.value),
      FADER_MIN_DB,
      FADER_MAX_DB,
    )
    if (!Number.isFinite(next)) return

    const drag = dragRef.current

    // Cambio sin puntero (flechas del teclado): se aplica al momento y no se
    // retiene ningún borrador, para que el WebSocket siga mandando.
    if (drag === null) {
      onCommit(index, next)
      return
    }

    setDraftDb(next)

    movedRef.current = true
    const now = performance.now()
    if (now - drag.startedAt < DRAG_SEND_DELAY_MS) return
    if (now - drag.lastSentAt < DRAG_SEND_INTERVAL_MS) return

    drag.lastSentAt = now
    onCommit(index, next)
  }

  const finishDrag = (event: ReactPointerEvent<HTMLInputElement>) => {
    if (dragRef.current === null) return

    const next = clamp(
      Number.parseFloat(event.currentTarget.value),
      FADER_MIN_DB,
      FADER_MAX_DB,
    )
    const moved = movedRef.current
    dragRef.current = null
    movedRef.current = false
    setDraftDb(null)
    endChannelDrag(index)

    // Al soltar manda siempre el valor final, aunque el throttle ya hubiera
    // enviado uno intermedio: así la mesa queda exactamente donde se soltó.
    if (moved && Number.isFinite(next)) onCommit(index, next)
  }

  const cancelDrag = () => {
    if (dragRef.current === null) return
    dragRef.current = null
    movedRef.current = false
    setDraftDb(null)
    endChannelDrag(index)
  }

  const faderTitle = canDrag
    ? 'Arrastra para cambiar el nivel'
    : unnamed
      ? 'Canal sin nombre: fader no disponible'
      : 'Fader de solo lectura: activa el control para moverlo'

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
        {formatDb(displayedDb)}
        <span className="ml-1 text-[8px] tracking-[0.08em] text-console-faint">
          dB
        </span>
      </p>

      <div className="mt-2 flex h-44 items-stretch justify-center gap-1.5">
        <MeterBar
          levelDb={meterDb}
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
            value={faderPositionDb}
            disabled={!canDrag}
            title={faderTitle}
            aria-label={`Fader de ${accessibleName}`}
            aria-valuetext={ariaDb(displayedDb)}
            onPointerDown={handlePointerDown}
            onChange={handleChange}
            onPointerUp={finishDrag}
            onPointerCancel={cancelDrag}
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
