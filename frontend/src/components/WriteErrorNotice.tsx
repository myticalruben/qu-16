import { useEffect } from 'react'

import { useMixerStore } from '../store/mixer'

/** Tiempo que el aviso de escritura permanece en pantalla. */
const ERROR_DISMISS_MS = 4_000

/**
 * Aviso discreto de fallo de escritura. Vive en el store (`lastError`) y se
 * retira solo a los 4 s; también se limpia al desmontarse la consola.
 */
export function WriteErrorNotice() {
  const lastError = useMixerStore((state) => state.lastError)
  const clearError = useMixerStore((state) => state.clearError)

  useEffect(() => {
    if (lastError === null) return

    const timer = setTimeout(clearError, ERROR_DISMISS_MS)
    return () => clearTimeout(timer)
  }, [lastError, clearError])

  if (lastError === null) return null

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="pointer-events-none fixed inset-x-4 bottom-4 z-40 mx-auto flex w-auto max-w-md items-start gap-2 rounded-lg border border-signal-danger/50 bg-console-panel/95 px-3 py-2.5 shadow-[0_18px_50px_-20px_rgba(0,0,0,0.95)] backdrop-blur-sm"
    >
      <span
        aria-hidden="true"
        className="mt-px grid h-4 w-4 shrink-0 place-items-center rounded-full border border-signal-danger/60 font-mono text-[9px] font-bold leading-none text-signal-danger"
      >
        !
      </span>
      <p className="font-mono text-[10px] leading-snug text-signal-danger">
        {lastError}
      </p>
    </div>
  )
}
