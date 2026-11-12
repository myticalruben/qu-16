import { useMixerStore } from '../store/mixer'
import { ChannelStrip } from './ChannelStrip'

/**
 * Fila de canales. El grid mantiene un ancho mínimo legible y deja que el
 * contenedor haga scroll horizontal en pantallas estrechas.
 */
export function ChannelRack() {
  const channels = useMixerStore((state) => state.channels)
  const setChannelFader = useMixerStore((state) => state.setChannelFader)
  const toggleChannelMute = useMixerStore((state) => state.toggleChannelMute)

  return (
    <div className="rack-scroll -mx-1 overflow-x-auto px-1 pb-2">
      <div
        role="list"
        aria-label="Canales de entrada"
        className="grid min-w-[840px] grid-flow-col auto-cols-[minmax(100px,1fr)] gap-2"
      >
        {channels.map((channel) => (
          <div role="listitem" key={channel.id} className="min-w-0">
            <ChannelStrip
              channel={channel}
              onFaderChange={setChannelFader}
              onMuteToggle={toggleChannelMute}
            />
          </div>
        ))}
      </div>
    </div>
  )
}
