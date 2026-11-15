import { useEffect, useRef, useState } from 'react'

import {
  DEFAULT_VISIBLE_CHANNELS,
  INPUT_CHANNEL_LIMIT,
  useMixerStore,
} from '../store/mixer'

const PANEL_ID = 'channel-menu-panel'

/** Nombre real de los canales de entrada, indexado por su índice de protocolo. */
function channelNames(channels: { index: number; name: string }[]): Map<number, string> {
  const names = new Map<number, string>()
  for (const channel of channels) {
    if (channel.index < 0 || channel.index >= INPUT_CHANNEL_LIMIT) continue
    if (channel.name.trim() === '') continue
    names.set(channel.index, channel.name)
  }
  return names
}

/**
 * Selector de los canales de entrada que se pintan en el rack.
 *
 * La selección vive en el store y se persiste en `localStorage`; aquí solo se
 * dibuja el panel y se cierra al hacer clic fuera o con Escape.
 */
export function ChannelMenu() {
  const channels = useMixerStore((state) => state.channels)
  const visibleChannels = useMixerStore((state) => state.visibleChannels)
  const setVisibleChannels = useMixerStore((state) => state.setVisibleChannels)
  const hydrateVisibleChannels = useMixerStore(
    (state) => state.hydrateVisibleChannels,
  )
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)

  // La preferencia se relee al montar: en tests y recargas el módulo puede
  // haberse cargado antes de que existiera la clave.
  useEffect(() => {
    hydrateVisibleChannels()
  }, [hydrateVisibleChannels])

  useEffect(() => {
    if (!open) return

    const closeOnOutside = (event: Event) => {
      if (containerRef.current?.contains(event.target as Node)) return
      setOpen(false)
    }
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      event.preventDefault()
      setOpen(false)
      triggerRef.current?.focus()
    }

    document.addEventListener('pointerdown', closeOnOutside)
    document.addEventListener('mousedown', closeOnOutside)
    window.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('pointerdown', closeOnOutside)
      document.removeEventListener('mousedown', closeOnOutside)
      window.removeEventListener('keydown', closeOnEscape)
    }
  }, [open])

  const names = channelNames(channels)
  const selected = new Set(visibleChannels)
  const summary = `${visibleChannels.length}/${INPUT_CHANNEL_LIMIT}`

  const toggleChannel = (index: number, checked: boolean) => {
    const next = checked
      ? [...visibleChannels, index]
      : visibleChannels.filter((channel) => channel !== index)
    setVisibleChannels(next)
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        ref={triggerRef}
        type="button"
        aria-expanded={open}
        aria-controls={PANEL_ID}
        onClick={() => setOpen((current) => !current)}
        className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 font-mono text-[10px] font-medium uppercase tracking-[0.12em] transition-colors duration-200 ${
          open
            ? 'border-accent-cyan/45 bg-console-raised text-console-ink'
            : 'border-console-line bg-console-raised/80 text-console-muted hover:border-accent-cyan/45 hover:bg-console-raised hover:text-console-ink'
        }`}
      >
        Canales: <span className="tabular-nums">{summary}</span>
        <span
          aria-hidden="true"
          className={`text-[8px] text-console-faint transition-transform duration-200 ${
            open ? 'rotate-180' : ''
          }`}
        >
          ▾
        </span>
      </button>

      <div
        id={PANEL_ID}
        hidden={!open}
        role="group"
        aria-label="Canales a controlar"
        className="absolute right-0 top-full z-30 mt-2 w-72 max-w-[calc(100vw-2rem)] rounded-xl border border-console-line bg-console-panel p-3 shadow-[0_24px_60px_-24px_rgba(0,0,0,0.95),0_0_30px_-18px_rgba(34,211,238,0.4)]"
      >
        <div className="flex items-center justify-between gap-2">
          <p className="font-mono text-[9px] uppercase tracking-[0.18em] text-console-faint">
            Entradas 1-16
          </p>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setVisibleChannels(DEFAULT_VISIBLE_CHANNELS)}
              className="rounded border border-console-line bg-console-raised/80 px-2 py-1 font-mono text-[9px] uppercase tracking-[0.12em] text-console-muted transition-colors duration-150 hover:border-accent-cyan/45 hover:text-console-ink"
            >
              Todos
            </button>
            <button
              type="button"
              onClick={() => setVisibleChannels([])}
              className="rounded border border-console-line bg-console-raised/80 px-2 py-1 font-mono text-[9px] uppercase tracking-[0.12em] text-console-muted transition-colors duration-150 hover:border-accent-cyan/45 hover:text-console-ink"
            >
              Ninguno
            </button>
          </div>
        </div>

        <div className="mt-2.5 grid grid-cols-2 gap-1">
          {Array.from({ length: INPUT_CHANNEL_LIMIT }, (_, index) => {
            const name = names.get(index)
            const label = name === undefined
              ? `CH ${index + 1}`
              : `CH ${index + 1} · ${name}`
            return (
              <label
                key={index}
                title={label}
                className="flex min-w-0 cursor-pointer items-center gap-1.5 rounded px-1.5 py-1 font-mono text-[9px] uppercase tracking-[0.08em] text-console-muted transition-colors duration-150 hover:bg-console-raised/70 hover:text-console-ink"
              >
                <input
                  type="checkbox"
                  checked={selected.has(index)}
                  aria-label={label}
                  onChange={(event) =>
                    toggleChannel(index, event.target.checked)
                  }
                  className="h-3.5 w-3.5 shrink-0 cursor-pointer rounded-sm border border-console-line-strong bg-console-void accent-[#22d3ee]"
                />
                <span className="truncate">{label}</span>
              </label>
            )
          })}
        </div>

        <p className="mt-2.5 border-t border-console-line/70 pt-2 font-mono text-[8px] uppercase tracking-[0.14em] text-console-faint">
          Se recuerda en este navegador
        </p>
      </div>
    </div>
  )
}
