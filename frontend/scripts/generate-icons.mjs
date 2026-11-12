/**
 * Generador de iconos PWA sin dependencias externas.
 *
 * Dibuja un icono de consola (fondo oscuro + tres faders) muestreando formas
 * con supersampling y codifica el PNG a mano con zlib. Se ejecuta con:
 *
 *   npm run icons
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { deflateSync } from 'node:zlib'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const OUT_DIR = resolve(ROOT, 'public')
const ICONS_DIR = resolve(OUT_DIR, 'icons')

const COLORS = {
  bgTop: [7, 11, 14],
  bgBottom: [14, 21, 27],
  border: [37, 51, 61],
  groove: [36, 48, 57],
  grooveDark: [13, 20, 25],
  cyan: [34, 211, 238],
  amber: [245, 165, 36],
  capEdge: [255, 255, 255],
  notch: [8, 13, 17],
}

const clamp01 = (value) => Math.min(1, Math.max(0, value))
const mix = (a, b, t) => a + (b - a) * t
const mixColor = (a, b, t) => [
  mix(a[0], b[0], t),
  mix(a[1], b[1], t),
  mix(a[2], b[2], t),
]

/** Distancia con signo a un rectángulo redondeado. */
function sdRoundRect(px, py, cx, cy, halfWidth, halfHeight, radius) {
  const qx = Math.abs(px - cx) - halfWidth + radius
  const qy = Math.abs(py - cy) - halfHeight + radius
  return (
    Math.min(Math.max(qx, qy), 0) +
    Math.hypot(Math.max(qx, 0), Math.max(qy, 0)) -
    radius
  )
}

const CAPS = [
  { x: 0.3, y: 0.39, color: COLORS.cyan },
  { x: 0.5, y: 0.58, color: COLORS.amber },
  { x: 0.7, y: 0.45, color: COLORS.cyan },
]

/**
 * Calcula el color RGBA de una muestra normalizada (0..1).
 * `fullBleed` pinta el fondo cuadrado entero (maskable / apple-touch).
 */
function sample(x, y, fullBleed) {
  const baseDistance = fullBleed
    ? -1
    : sdRoundRect(x, y, 0.5, 0.5, 0.47, 0.47, 0.21)

  if (baseDistance > 0) return [0, 0, 0, 0]

  // Fondo con gradiente vertical y un leve halo cian arriba a la izquierda.
  const gradient = clamp01((y - 0.03) / 0.94)
  let color = mixColor(COLORS.bgTop, COLORS.bgBottom, gradient)
  const halo = clamp01(
    1 - Math.hypot(x - 0.16, y - 0.06) / 0.72,
  )
  color = mixColor(color, COLORS.cyan, halo * 0.075)

  // Borde interior del icono.
  if (baseDistance > -0.008) {
    color = mixColor(color, COLORS.border, 0.9)
  } else if (baseDistance > -0.018) {
    color = mixColor(color, COLORS.border, 0.4)
  }

  // Ranuras verticales del fader.
  for (const cap of CAPS) {
    const slot = sdRoundRect(x, y, cap.x, 0.5, 0.012, 0.3, 0.012)
    if (slot <= 0) {
      color = mixColor(color, COLORS.groove, 0.95)
      const core = sdRoundRect(x, y, cap.x, 0.5, 0.004, 0.285, 0.004)
      if (core <= 0) color = mixColor(color, COLORS.grooveDark, 0.9)
    }
  }

  // Halo y cuerpo de cada cap.
  for (const cap of CAPS) {
    const capDistance = sdRoundRect(x, y, cap.x, cap.y, 0.08, 0.037, 0.02)

    if (capDistance > 0 && capDistance < 0.055) {
      const glow = (1 - capDistance / 0.055) * 0.16
      color = mixColor(color, cap.color, glow)
    }

    if (capDistance <= 0) {
      const capGradient = clamp01((y - (cap.y - 0.037)) / 0.074)
      let capColor = mixColor(
        mixColor(cap.color, [255, 255, 255], 0.28),
        mixColor(cap.color, [0, 0, 0], 0.22),
        capGradient,
      )

      if (capDistance > -0.008) {
        capColor = mixColor(capColor, COLORS.capEdge, 0.35)
      }

      // Muesca central del cap.
      const notch = sdRoundRect(x, y, cap.x, cap.y, 0.052, 0.0045, 0.0045)
      if (notch <= 0) {
        capColor = mixColor(capColor, COLORS.notch, 0.72)
      }

      color = capColor
    }
  }

  return [color[0], color[1], color[2], 255]
}

/** Renderiza un icono RGBA con supersampling 2x2. */
function renderIcon(size, { fullBleed = false } = {}) {
  const pixels = Buffer.alloc(size * size * 4)
  const offsets = [0.25, 0.75]

  for (let py = 0; py < size; py += 1) {
    for (let px = 0; px < size; px += 1) {
      let r = 0
      let g = 0
      let b = 0
      let a = 0

      for (const oy of offsets) {
        for (const ox of offsets) {
          const x = (px + ox) / size
          const y = (py + oy) / size
          const [sr, sg, sb, sa] = sample(x, y, fullBleed)
          const alpha = sa / 255
          r += sr * alpha
          g += sg * alpha
          b += sb * alpha
          a += alpha
        }
      }

      const index = (py * size + px) * 4
      if (a > 0) {
        pixels[index] = Math.round(r / a)
        pixels[index + 1] = Math.round(g / a)
        pixels[index + 2] = Math.round(b / a)
        pixels[index + 3] = Math.round((a / 4) * 255)
      }
    }
  }

  return pixels
}

const CRC_TABLE = (() => {
  const table = new Uint32Array(256)
  for (let n = 0; n < 256; n += 1) {
    let c = n
    for (let k = 0; k < 8; k += 1) {
      c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
    }
    table[n] = c >>> 0
  }
  return table
})()

function crc32(buffer) {
  let crc = 0xffffffff
  for (const byte of buffer) {
    crc = CRC_TABLE[(crc ^ byte) & 0xff] ^ (crc >>> 8)
  }
  return (crc ^ 0xffffffff) >>> 0
}

function pngChunk(type, data) {
  const length = Buffer.alloc(4)
  length.writeUInt32BE(data.length, 0)

  const typeBuffer = Buffer.from(type, 'ascii')
  const crc = Buffer.alloc(4)
  crc.writeUInt32BE(crc32(Buffer.concat([typeBuffer, data])), 0)

  return Buffer.concat([length, typeBuffer, data, crc])
}

function encodePng(size, pixels) {
  const signature = Buffer.from([
    0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a,
  ])

  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(size, 0)
  ihdr.writeUInt32BE(size, 4)
  ihdr[8] = 8 // profundidad de bits
  ihdr[9] = 6 // RGBA
  ihdr[10] = 0 // deflate
  ihdr[11] = 0 // filtro adaptativo
  ihdr[12] = 0 // sin entrelazado

  const stride = size * 4
  const raw = Buffer.alloc((stride + 1) * size)
  for (let y = 0; y < size; y += 1) {
    raw[y * (stride + 1)] = 0
    pixels.copy(raw, y * (stride + 1) + 1, y * stride, (y + 1) * stride)
  }

  return Buffer.concat([
    signature,
    pngChunk('IHDR', ihdr),
    pngChunk('IDAT', deflateSync(raw, { level: 9 })),
    pngChunk('IEND', Buffer.alloc(0)),
  ])
}

function writeIcon(relativePath, size, options) {
  const target = resolve(OUT_DIR, relativePath)
  mkdirSync(dirname(target), { recursive: true })
  const png = encodePng(size, renderIcon(size, options))
  writeFileSync(target, png)
  console.log(`  ${relativePath} (${size}×${size}, ${png.length} B)`)
}

console.log('Generando iconos PWA…')
mkdirSync(ICONS_DIR, { recursive: true })
writeIcon('icons/icon-192.png', 192)
writeIcon('icons/icon-512.png', 512)
writeIcon('icons/icon-maskable-512.png', 512, { fullBleed: true })
writeIcon('apple-touch-icon.png', 180, { fullBleed: true })
console.log('Iconos listos.')
