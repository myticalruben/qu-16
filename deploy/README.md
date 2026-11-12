# Despliegue en la laptop de la LAN de la mesa

Guía para ejecutar **qu16-control** con Docker Compose en la laptop Linux que
está conectada a la misma red que la Allen & Heath Qu-16.

## Requisitos

- Laptop Linux con Docker Engine 24+ y el plugin `docker compose` (v2).
- La laptop debe poder alcanzar la mesa por TCP: normalmente
  `192.168.100.67:51326` (protocolo CMNet). Compruébalo con:
  ```bash
  ping -c 2 192.168.100.67
  nc -vz 192.168.100.67 51326
  ```
- Repositorio clonado en la laptop (con los directorios `backend/` y
  `frontend/`, cada uno con su `Dockerfile`).

## 1. Crear la red externa de la LAN

El backend se conecta a la red `qu16-lan` para llegar a la mesa. Es externa, así
que hay que crearla una sola vez en el host:

```bash
docker network create qu16-lan
```

El comando falla si ya existe; en ese caso no hay nada que hacer. Se puede
comprobar con `docker network ls | grep qu16-lan`.

## 2. Apuntar a la IP real de la mesa

El valor por defecto es `192.168.100.67:51326`. Si tu mesa tiene otra IP, crea un
archivo `.env` en la raíz del repositorio (Compose lo carga automáticamente):

```bash
cat > .env <<'EOF'
QU16_MIXER_HOST=192.168.100.67
QU16_MIXER_PORT=51326
EOF
```

También puedes exportarlas en la sesión antes de levantar:

```bash
export QU16_MIXER_HOST=192.168.100.67
export QU16_MIXER_PORT=51326
```

Conviene reservar esa IP en el router (DHCP estático) para que no cambie.

## 3. Levantar el stack

```bash
docker compose up -d --build
```

- Frontend (nginx): <http://localhost:8080>
- Backend (API de depuración): <http://localhost:8000>

## 4. Comprobar que funciona

```bash
docker compose ps                       # backend debe aparecer "healthy"
curl -s http://localhost:8000/api/health
curl -s http://localhost:8080/api/health   # mismo endpoint vía nginx
docker compose logs -f backend
```

Si el contenedor aparece `unhealthy`, revisa los logs: casi siempre es que la
mesa no es alcanzable (IP incorrecta, firewall o red equivocada).

## Operación habitual

```bash
docker compose logs -f          # ver logs de ambos servicios
docker compose restart backend  # reiniciar solo la API
docker compose down             # parar y eliminar contenedores
git pull && docker compose up -d --build   # actualizar tras un cambio
```

## Alternativa: red del host

Si prefieres no crear `qu16-lan`, edita `docker-compose.yml`, comenta los
bloques `ports:` y `networks:` del servicio `backend` y descomenta
`network_mode: host`. En ese caso la API escucha directamente en el puerto 8000
del host y alcanza la mesa como cualquier proceso local; el frontend sigue
publicado en el 8080.

## Notas

- No expongas el puerto 8000 a Internet: la aplicación no tiene autenticación.
- El healthcheck usa el propio Python de la imagen contra `/api/health`.
- Solo el backend necesita estar en la LAN de la mesa; el frontend habla con él
  por la red interna `qu16-net`.
