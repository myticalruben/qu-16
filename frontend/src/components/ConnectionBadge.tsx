import type { ConnectionState } from '../store/mixer'

interface ConnectionBadgeProps {
  state: ConnectionState
  serverVersion?: string | null
  className?: string
}

interface BadgeStyle {
  label: string
  container: string
  dot: string
}

const BADGE_STYLES: Record<ConnectionState, BadgeStyle> = {
  disconnected: {
    label: 'Desconectado',
    container:
      'border-console-line-strong/70 bg-console-raised/80 text-console-muted',
    dot: 'bg-console-faint',
  },
  connecting: {
    label: 'Conectando…',
    container: 'border-signal-warn/35 bg-signal-warn/10 text-signal-warn',
    dot: 'bg-signal-warn',
  },
  connected: {
    label: 'Conectado',
    container: 'border-signal-ok/35 bg-signal-ok/10 text-signal-ok',
    dot: 'bg-signal-ok',
  },
}

/**
 * Insignia del enlace con el backend. Es puramente presentacional: el estado
 * llega del store para que los tests puedan recorrer los tres casos.
 */
export function ConnectionBadge({
  state,
  serverVersion = null,
  className = '',
}: ConnectionBadgeProps) {
  const { label, container, dot } = BADGE_STYLES[state]
  const showVersion = state === 'connected' && serverVersion !== null

  return (
    <span
      role="status"
      aria-live="polite"
      aria-label={`Enlace: ${label}`}
      className={`inline-flex items-center gap-2 rounded-full border px-2.5 py-1 font-mono text-[10px] font-medium uppercase tracking-[0.14em] transition-colors duration-200 ${container} ${className}`}
    >
      <span className="relative flex h-2 w-2" aria-hidden="true">
        {state === 'connecting' ? (
          <span
            className={`status-pulse absolute inline-flex h-full w-full rounded-full ${dot} opacity-60`}
          />
        ) : null}
        <span
          className={`relative inline-flex h-2 w-2 rounded-full ${dot} ${
            state === 'connected' ? 'shadow-[0_0_7px_rgba(52,211,153,0.9)]' : ''
          }`}
        />
      </span>
      <span>{label}</span>
      {showVersion ? (
        <span className="border-l border-console-line-strong pl-2 text-[9px] normal-case tracking-[0.06em] text-console-muted">
          v{serverVersion}
        </span>
      ) : null}
    </span>
  )
}
