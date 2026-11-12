import { ChannelRack } from './components/ChannelRack'
import { ConnectionBadge } from './components/ConnectionBadge'
import { connectMixerSocket, disconnectMixerSocket } from './lib/ws'
import { useMixerStore } from './store/mixer'

const APP_VERSION = __APP_VERSION__

function BrandMark() {
  return (
    <div
      aria-hidden="true"
      className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-console-line-strong/70 bg-console-panel shadow-[inset_0_1px_0_rgba(255,255,255,0.06),0_0_26px_-10px_rgba(34,211,238,0.5)]"
    >
      <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none">
        <line
          x1="7"
          y1="4.5"
          x2="7"
          y2="19.5"
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinecap="round"
          className="text-console-line-strong"
        />
        <line
          x1="12"
          y1="4.5"
          x2="12"
          y2="19.5"
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinecap="round"
          className="text-console-line-strong"
        />
        <line
          x1="17"
          y1="4.5"
          x2="17"
          y2="19.5"
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinecap="round"
          className="text-console-line-strong"
        />
        <rect x="4.5" y="7" width="5" height="2.6" rx="0.9" className="fill-accent-cyan" />
        <rect x="9.5" y="12" width="5" height="2.6" rx="0.9" className="fill-accent-amber" />
        <rect x="14.5" y="9.5" width="5" height="2.6" rx="0.9" className="fill-accent-cyan" />
      </svg>
    </div>
  )
}

function LinkIcon({ engaged }: { engaged: boolean }) {
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
      {engaged ? (
        <path d="M5 5l6 6M11 5l-6 6" />
      ) : (
        <path d="M6.3 9.7l3.4-3.4M6.7 11.1l-1.2 1.2a2 2 0 01-2.8-2.8l1.2-1.2M9.3 4.9l1.2-1.2a2 2 0 012.8 2.8l-1.2 1.2" />
      )}
    </svg>
  )
}

function App() {
  const connectionState = useMixerStore((state) => state.connectionState)
  const serverVersion = useMixerStore((state) => state.serverVersion)

  const isEngaged = connectionState !== 'disconnected'
  const linkLabel =
    connectionState === 'connected'
      ? 'Desconectar'
      : connectionState === 'connecting'
        ? 'Cancelar'
        : 'Conectar'

  const handleLinkClick = () => {
    if (isEngaged) {
      disconnectMixerSocket()
    } else {
      connectMixerSocket()
    }
  }

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-20 border-b border-console-line/80 bg-console-black/85 backdrop-blur-md">
        <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <BrandMark />
            <div className="min-w-0">
              <h1 className="truncate text-[15px] font-semibold leading-tight tracking-[-0.01em] text-console-ink">
                Qu-16 Control
              </h1>
              <p className="mt-0.5 truncate font-mono text-[9px] uppercase tracking-[0.18em] text-console-faint">
                Allen &amp; Heath Qu-16 · CMNet
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <ConnectionBadge
              state={connectionState}
              serverVersion={serverVersion}
            />
            <button
              type="button"
              onClick={handleLinkClick}
              className="inline-flex items-center gap-1.5 rounded-md border border-console-line bg-console-raised/80 px-2.5 py-1.5 font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-console-muted transition-colors duration-200 hover:border-accent-cyan/45 hover:bg-console-raised hover:text-console-ink"
            >
              <LinkIcon engaged={isEngaged} />
              {linkLabel}
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 sm:py-8">
        <section aria-labelledby="channel-rack-title">
          <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-console-faint">
                Entradas · banco A
              </p>
              <h2
                id="channel-rack-title"
                className="mt-1 text-[13px] font-semibold tracking-[0.01em] text-console-ink"
              >
                Canales 1–8
              </h2>
            </div>

            <div className="flex items-center gap-2 font-mono text-[9px] uppercase tracking-[0.14em] text-console-faint">
              <span className="hidden items-center gap-1.5 sm:inline-flex">
                <span
                  aria-hidden="true"
                  className="h-1 w-1 rounded-full bg-accent-cyan/80"
                />
                Vista local
              </span>
              <span className="rounded border border-console-line bg-console-panel/70 px-2 py-1 tabular-nums text-console-muted">
                8 / 16
              </span>
            </div>
          </div>

          <ChannelRack />

          <div className="mt-4 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-console-line/80 bg-console-panel/45 px-3 py-2.5">
            <p className="flex items-center gap-2 font-mono text-[9px] uppercase tracking-[0.14em] text-console-faint">
              <span
                aria-hidden="true"
                className="h-1.5 w-1.5 rounded-full bg-accent-amber/80 shadow-[0_0_6px_rgba(245,165,36,0.45)]"
              />
              Maqueta de Fase 1 · los faders aún no envían comandos
            </p>
            <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-console-faint">
              Bucles de 16 canales · medidores en vivo pendientes
            </p>
          </div>
        </section>
      </main>

      <footer className="mt-auto border-t border-console-line/80 bg-console-void/60">
        <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-3 font-mono text-[9px] uppercase tracking-[0.14em] text-console-faint sm:px-6">
          <p>
            Qu-16 Control{' '}
            <span className="text-console-muted">v{APP_VERSION}</span>
          </p>
          <p className="flex flex-wrap items-center gap-2">
            <span className="h-1 w-1 rounded-full bg-accent-cyan/70" aria-hidden="true" />
            <span>Fase 1 · esqueleto UI</span>
            <span aria-hidden="true" className="text-console-line-strong">
              /
            </span>
            <span>React 19 · Tailwind 4</span>
          </p>
        </div>
      </footer>
    </div>
  )
}

export default App
