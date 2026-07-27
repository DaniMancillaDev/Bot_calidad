# Guía de Ejecución y Despliegue - Bot Calidad

Este documento detalla el proceso completo para levantar el proyecto localmente utilizando Docker. 
El proyecto está completamente funcional y todos los contenedores han sido validados exitosamente tras el refactor.

## 1. Requisitos
- **Docker**: Instalado y corriendo (`docker` o `docker compose` v2+).
- **uv**: (Opcional, aunque el contenedor de Python ya lo usa internamente para la instalación de dependencias, no es estricto tenerlo en el host).

## 2. Variables de Entorno
El proyecto necesita un archivo `.env` en la raíz del proyecto.
Puedes copiar el archivo `.env.example` o `.env.local` y renombrarlo a `.env`.
Asegúrate de que el `.env` contiene al menos:

```env
POSTGRES_DB=test_bot_calidad
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=alguna-clave-secreta-segura
```

*(El proyecto ya incluye un archivo `.env` configurado que permite levantarlo en local de inmediato)*.

## 3. Construir y Levantar el Proyecto

Dado que usamos imágenes de Alpine con Gunicorn, Celery, Redis y PostgreSQL, el proyecto se levanta con un solo comando:

```bash
# Opcional (si necesitas forzar una reconstrucción total, como cuando cambias el código o pyproject.toml):
docker compose build --no-cache

# Levantar los contenedores en modo detached (background):
docker compose up -d
```

### Servicios incluidos:
- **web**: Servidor Django bajo Gunicorn (expuesto en puerto local `:8000` internamente, pero balanceado por nginx en el `:80`).
- **celery**: Worker asíncrono para procesar Excels en 2do plano.
- **bot**: Proceso de polling continuo del bot de Telegram.
- **postgres**: Base de datos PostgreSQL (puerto `:5432`).
- **redis**: Broker para Celery (puerto `:6379`).
- **nginx**: Reverse proxy que sirve estáticos, media, y balancea la app en el puerto `:80`.

## 4. Migraciones
El contenedor de `web` incluye en su comando de inicio la ejecución automática de las migraciones de Django. 
Sin embargo, si necesitas correr una migración manualmente mientras el contenedor está vivo:

```bash
docker compose exec web uv run python web/manage.py migrate
```

## 5. Usuario Administrador
Para acceder al panel de administración de Django (`http://localhost/admin/`), necesitas un superusuario. 
Puedes crearlo con el siguiente comando interactivo:

```bash
docker compose exec web uv run python web/manage.py createsuperuser
```
*(Durante la validación de despliegue se ha creado un usuario temporal de pruebas `admin` con contraseña `admin`)*.

## 6. Cómo Ejecutar Celery
Celery se levanta **automáticamente** a través del archivo `docker-compose.yml` en el servicio `celery`. No es necesario levantarlo manualmente.
Si necesitas inspeccionar los logs de Celery para depurar la generación de archivos Excel:

```bash
docker compose logs -f celery
```

## 7. Verificando el estado de la aplicación (Smoke Test)
Una vez levantado todo con `docker compose up -d`, puedes verificar:
- **Aplicación principal / Login**: [http://localhost/login/](http://localhost/login/)
- **Panel de Admin**: [http://localhost/admin/](http://localhost/admin/)
- **Logs generales**:
  ```bash
  docker compose logs -f web bot celery
  ```

## 8. Cómo Detener el Proyecto

Para detener todos los servicios y contenedores de manera segura sin borrar los datos de la base de datos (Postgres y Redis):

```bash
docker compose down
```

Si por alguna razón necesitas hacer un "hard reset" del entorno y **borrar** las bases de datos (Postgres y volúmenes de medios/estáticos):

```bash
docker compose down -v
```
