# Instancia en la laptop `ruben-alexander-laptop-ubuntu`

Corriendo en **`/opt/qu16-app`**, con acceso a la Qu-16 en `192.168.100.67`.

| Dato | Valor |
|---|---|
| Puerto | `8080` |
| Usuario | `deepseek` |
| Python | 3.14 (venv propio en `/opt/qu16-app/.venv`) |
| Arranque | `setsid nohup` — sobrevive al cierre de la sesión SSH |
| Escritura | habilitada en el servidor (`QU16_WRITE_ENABLED=true`); la interfaz sigue exigiendo pulsar **Control** |

## Entrar desde tu equipo

```bash
ssh -L 8080:localhost:8080 deepseek@ruben-alexander-laptop-ubuntu
```

Con esa sesión abierta, abre en el navegador:

```
http://localhost:8080
```

Si estás en la misma red que la laptop, también sirve directamente:

```
http://192.168.100.189:8080
```

## Gestión

```bash
cd /opt/qu16-app
./status.sh     # ¿está vivo? + estado de la mesa
./stop.sh       # detener
./start.sh      # arrancar
tail -f run/app.log
```

## Variables de entorno

Se pueden sobreescribir al arrancar, por ejemplo:

```bash
QU16_WRITE_ENABLED=false ./start.sh   # solo lectura
PORT=9000 ./start.sh
```

| Variable | Por defecto |
|---|---|
| `QU16_MIXER_HOST` | `192.168.100.67` |
| `QU16_MIXER_PORT` | `51326` |
| `QU16_AUTO_CONNECT` | `true` |
| `QU16_WRITE_ENABLED` | `true` en esta instancia |
| `QU16_POLL_INTERVAL` | `2` |
| `PORT` | `8080` |

## Comprobado en esta instancia

```
SPA:      200 text/html
canales:  60
WS:       hello, state (4) y meters (117 en 6 s)
medidores reales: canal 1 -18.9 dB, canal 3 -21.0 dB, canal 4 -23.7 dB
escritura: canal 16 a -20 dB aplicado y devuelto a -infinito
```

## Pendiente

- Arranque automático al encender la laptop: falta un servicio de `systemd`
  (requiere `sudo`). Mientras tanto, `./start.sh` tras cada reinicio.
- Actualizar tras un `git push`: volver a copiar el proyecto y reiniciar.
