# Email Manager

Skill para gestionar correos electrónicos mediante IMAP/SMTP.

## Uso

Invoca la herramienta `email_manager` con los parámetros según la acción:

- `list_folders`: lista carpetas IMAP disponibles.
- `fetch_emails`: obtiene correos de una carpeta con filtros opcionales.
- `send_email`: envía un correo por SMTP con soporte de adjuntos.
- `check_connection`: verifica credenciales y conectividad IMAP/SMTP.

## Parámetros obligatorios

- `action`
- `imap_host`
- `smtp_host`
- `username`
- `password`

## Ejemplo rápido

```json
{
  "action": "fetch_emails",
  "imap_host": "imap.gmail.com",
  "smtp_host": "smtp.gmail.com",
  "username": "usuario@gmail.com",
  "password": "app_password",
  "limit": 5
}
```
