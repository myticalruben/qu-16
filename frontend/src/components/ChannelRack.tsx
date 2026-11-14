import { memo, useState } from 'react'

import type { Channel } from '../store/mixer'
import { levelFor, namedChannels, useMixerStore } from '../store/mixer'
import { ChannelStrip } from './ChannelStrip'

/**
 * Cada tira se suscribe a su propia posición de `levels`, no al array entero.
 * El selector devuelve un número (o `null`), así que a 20 mensajes/s solo se
 * vuelve a pintar el canal cuyo nivel cambió; el rack y el resto de tiras no
 * se re-renderizan. `memo` es la segunda barrera: aunque el rack se repinte
 * por un `state`, las tiras con el mismo `channel` no se tocan.
 */
const MeteredChannelStrip = memo(function MeteredChannelStrip({
  channel,
}: {
  channel: Channel
}) {
  const meterDb = useMixerStore((state) => levelFor(state, channel.index))

  return (
    <ChannelStrip
      index={channel.index}
      name={channel.name}
      faderDb={channel.levelDb}
      kind={channel.kind}
      meterDb={meterDb}
    />
  )
})

/** Aviso intermedio cuando hay canales pero ninguno tiene nombre. */
function UnnamedNotice({ onShowAll }: { onShowAll: () => void }) {
  return (
    <div className="rounded-xl border border-dashed border-console-line bg-console-panel/40 px-6 py-10 text-center">
      <p className="text-[12px] font-medium text-console-muted">
        La mesa no reporta ningún canal con nombre
      </p>
      <button
        type="button"
        onClick={onShowAll}
        className="mt-3 rounded-md border border-console-line bg-console-raised/80 px-2.5 py-1.5 font-mono text-[9px] uppercase tracking-[0.14em] text-console-muted transition-colors duration-200 hover:border-accent-cyan/45 hover:text-console-ink"
      >
        Mostrar todos los canales
      </button>
    </div>
  )
}

/** Estado vacío: el backend aún no ha entregado ningún volcado. */
function EmptyRack() {
  return (
    <div className="rounded-xl border border-dashed border-console-line bg-console-panel/40 px-6 py-12 text-center">
      <svg
        viewBox="0 0 24 24"
        aria-hidden="true"
        className="mx-auto h-8 w-8 text-console-line-strong"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinecap="round"
      >
        <path d="M4 6h16M4 12h16M4 18h16" />
        <rect x="7" y="4.5" width="2.6" height="3" rx="0.8" className="fill-console-line-strong" />
        <rect x="14.5" y="10.5" width="2.6" height="3" rx="0.8" className="fill-console-line-strong" />
        <rect x="9.5" y="16.5" width="2.6" height="3" rx="0.8" className="fill-console-line-strong" />
      </svg>
      <p className="mt-3 text-[13px] font-medium text-console-muted">
        Sin datos de la mesa — pulsa Conectar
      </p>
      <p className="mt-1.5 font-mono text-[9px] uppercase tracking-[0.16em] text-console-faint">
        Esperando el primer volcado por WebSocket
      </p>
    </div>
  )
}

/**
 * Fila de canales. El grid mantiene un ancho mínimo legible y deja que el
 * contenedor haga scroll horizontal en pantallas estrechas.
 *
 * Por defecto solo se pintan los canales con nombre; el backend puede enviar
 * decenas de canales vacíos y no interesa inundar el rack.
 */
export function ChannelRack() {
  const channels = useMixerStore((state) => state.channels)
  const namedCount = useMixerStore((state) => namedChannels(state).length)
  const [showAll, setShowAll] = useState(false)

  if (channels.length === 0) {
    return <EmptyRack />
  }

  const visibleChannels = showAll
    ? channels
    : channels.filter((channel) => channel.name.trim() !== '')

  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-3">
        <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-console-faint">
          {showAll ? 'Todos los canales' : 'Solo canales con nombre'}
          <span className="ml-2 text-console-line-strong" aria-hidden="true">
            /
          </span>
          <span className="ml-2 tabular-nums text-console-muted">
            {showAll ? channels.length : namedCount} de {channels.length}
          </span>
        </p>

        <label className="inline-flex cursor-pointer select-none items-center gap-2 font-mono text-[9px] uppercase tracking-[0.14em] text-console-faint transition-colors duration-150 hover:text-console-muted">
          <input
            type="checkbox"
            checked={showAll}
            onChange={(event) => setShowAll(event.target.checked)}
            className="h-3.5 w-3.5 cursor-pointer rounded-sm border border-console-line-strong bg-console-void accent-[#22d3ee]"
          />
          Mostrar todos
        </label>
      </div>

      {visibleChannels.length === 0 ? (
        <UnnamedNotice onShowAll={() => setShowAll(true)} />
      ) : (
        <div className="rack-scroll -mx-1 overflow-x-auto px-1 pb-2">
          <div
            role="list"
            aria-label="Canales de entrada"
            className="grid grid-flow-col auto-cols-[minmax(100px,132px)] justify-start gap-2"
          >
            {visibleChannels.map((channel) => (
              <div role="listitem" key={channel.index} className="min-w-0">
                <MeteredChannelStrip channel={channel} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
