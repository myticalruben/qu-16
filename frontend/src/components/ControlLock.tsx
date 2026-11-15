import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'

import { useMixerStore } from '../store/mixer'

/** Icono de candado; la argolla se abre cuando el control está activo. */
function LockIcon({ open }: { open: boolean }) {
  return (
    <svg
      viewBox="0 0 16 16"
      aria-hidden="true"
      className="h-3.5 w-3.5"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="3.5" y="7" width="9" height="6.5" rx="1.4" />
      {open ? (
        <path d="M5.8 7V5.2a2.2 2.2 0 014.3-.8" />
      ) : (
        <path d="M5.8 7V5.2a2.2 2.2 0 014.4 0V7" />
      )}
    </svg>
  )
}

function WarningIcon() {
  return (
    <svg
      viewBox="0 0 16 16"
      aria-hidden="true"
      className="h-4 w-4"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M8 2.5l5.5 10h-11z" />
      <path d="M8 6.4v3" />
      <path d="M8 11.4h.01" />
    </svg>
  )
}

/**
 * Candado de escritura de la cabecera. Tres estados visibles:
 *
 * 1. apagado (solo lectura),
 * 2. pidiendo confirmación (diálogo),
 * 3. activo (los faders envían a la mesa).
 *
 * Solo se puede activar si `GET /api/mixer/config` publica
 * `write_enabled: true`; el estado vive en el store y no se persiste, así que
 * cada recarga vuelve a arrancar apagado.
 */
export function ControlLock() {
  const controlEnabled = useMixerStore((state) => state.controlEnabled)
  const controlPending = useMixerStore((state) => state.controlPending)
  const writeConfig = useMixerStore((state) => state.writeConfig)
  const setControlEnabled = useMixerStore((state) => state.setControlEnabled)
  const setControlPending = useMixerStore((state) => state.setControlPending)

  const writeAllowed = writeConfig?.write_enabled === true
  const triggerRef = useRef<HTMLButtonElement>(null)
  const confirmRef = useRef<HTMLButtonElement>(null)
  const wasPendingRef = useRef(false)

  // Al abrir, el foco va a la acción principal; al cerrar, vuelve al control.
  useEffect(() => {
    if (controlPending) {
      wasPendingRef.current = true
      confirmRef.current?.focus()
      return
    }
    if (wasPendingRef.current) {
      wasPendingRef.current = false
      triggerRef.current?.focus()
    }
  }, [controlPending])

  // Escape cierra la confirmación sin activar nada.
  useEffect(() => {
    if (!controlPending) return

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      event.preventDefault()
      setControlPending(false)
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [controlPending, setControlPending])

  const handleTrigger = () => {
    if (!writeAllowed) return
    if (controlEnabled) {
      setControlEnabled(false)
      return
    }
    setControlPending(true)
  }

  const statusLabel = controlPending
    ? 'Confirmar activación'
    : controlEnabled
      ? 'Control activo'
      : writeConfig === null
        ? 'Comprobando permiso'
        : writeAllowed
          ? 'Listo para activar'
          : 'Bloqueado en el servidor'

  const triggerClassName = controlEnabled
    ? 'border-accent-amber/60 bg-accent-amber/15 text-accent-amber hover:bg-accent-amber/25'
    : writeAllowed
      ? 'border-console-line bg-console-raised/80 text-console-muted hover:border-accent-amber/45 hover:bg-console-raised hover:text-console-ink'
      : 'cursor-not-allowed border-console-line/60 bg-console-void/40 text-console-faint'

  return (
    <>
      <div className="flex items-center gap-2">
        <button
          ref={triggerRef}
          type="button"
          disabled={!writeAllowed}
          aria-pressed={controlEnabled}
          title={
            !writeAllowed
              ? 'Escritura bloqueada por el servidor'
              : controlEnabled
                ? 'Pulsa para volver a solo lectura'
                : 'Activar escritura en la mesa real'
          }
          onClick={handleTrigger}
          className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 font-mono text-[10px] font-medium uppercase tracking-[0.12em] transition-colors duration-200 ${triggerClassName}`}
        >
          <LockIcon open={controlEnabled} />
          <span>Control</span>
          <span
            aria-hidden="true"
            className={`text-[8px] ${controlEnabled ? 'text-accent-amber' : 'text-console-faint'}`}
          >
            {controlEnabled ? 'ON' : 'OFF'}
          </span>
        </button>

        <span
          aria-live="polite"
          className={`max-w-[130px] font-mono text-[8px] uppercase leading-tight tracking-[0.14em] ${
            controlEnabled
              ? 'text-accent-amber'
              : writeConfig !== null && !writeAllowed
                ? 'text-signal-danger'
                : 'text-console-faint'
          }`}
        >
          {statusLabel}
        </span>
      </div>

      {controlPending
        ? createPortal(
            <div
              className="fixed inset-0 z-50 flex items-center justify-center bg-console-void/80 p-4 backdrop-blur-sm"
              onPointerDown={(event) => {
                if (event.target === event.currentTarget) setControlPending(false)
              }}
            >
              <div
                role="dialog"
                aria-modal="true"
                aria-labelledby="control-dialog-title"
                aria-describedby="control-dialog-description"
                onPointerDown={(event) => event.stopPropagation()}
                className="w-full max-w-md rounded-xl border border-accent-amber/45 bg-console-panel p-5 shadow-[0_30px_80px_-30px_rgba(0,0,0,0.95),0_0_40px_-18px_rgba(245,165,36,0.5)]"
              >
                <div className="flex items-start gap-3">
                  <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-accent-amber/40 bg-accent-amber/10 text-accent-amber">
                    <WarningIcon />
                  </span>
                  <div className="min-w-0">
                    <p className="font-mono text-[9px] uppercase tracking-[0.18em] text-accent-amber">
                      Mesa real
                    </p>
                    <h2
                      id="control-dialog-title"
                      className="mt-1 text-[14px] font-semibold leading-tight text-console-ink"
                    >
                      Activar control de escritura
                    </h2>
                    <p
                      id="control-dialog-description"
                      className="mt-2 text-[12px] leading-relaxed text-console-muted"
                    >
                      Vas a poder mover faders de la mesa real. El sonido
                      cambiará.
                    </p>
                    <p className="mt-2 font-mono text-[9px] uppercase tracking-[0.14em] text-console-faint">
                      {writeConfig?.model ?? 'QU-16'}
                      {writeConfig?.connected ? ' · enlazada' : ' · sin enlace'}
                    </p>
                  </div>
                </div>

                <div className="mt-5 flex flex-wrap justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setControlPending(false)}
                    className="rounded-md border border-console-line bg-console-raised/80 px-3 py-2 font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-console-muted transition-colors duration-200 hover:border-console-line-strong hover:text-console-ink"
                  >
                    Cancelar
                  </button>
                  <button
                    ref={confirmRef}
                    type="button"
                    onClick={() => setControlEnabled(true)}
                    className="rounded-md border border-accent-amber/60 bg-accent-amber/20 px-3 py-2 font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-accent-amber transition-colors duration-200 hover:bg-accent-amber/30"
                  >
                    Activar control
                  </button>
                </div>
              </div>
            </div>,
            document.body,
          )
        : null}
    </>
  )
}
