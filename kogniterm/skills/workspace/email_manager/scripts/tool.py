import imaplib
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

def email_manager(
    action: str,
    imap_host: str,
    smtp_host: str,
    username: str,
    password: str,
    imap_port: int = 993,
    smtp_port: int = 465,
    use_ssl: bool = True,
    mailbox: str = "INBOX",
    limit: int = 10,
    subject_filter: str = "",
    body_filter: str = "",
    to_addr: str = "",
    cc_addr: str = "",
    bcc_addr: str = "",
    subject: str = "",
    body: str = "",
    attachments: List[str] = None,
    mark_as_read: bool = False
) -> Dict[str, Any]:
    """
    Gestiona correos electrónicos via IMAP/SMTP.
    
    Acciones:
    - list_folders: Lista carpetas IMAP
    - fetch_emails: Obtiene correos de una carpeta
    - send_email: Envía un correo por SMTP
    - check_connection: Verifica credenciales
    
    Args:
        action: Acción a realizar
        imap_host: Servidor IMAP (ej: imap.gmail.com)
        smtp_host: Servidor SMTP (ej: smtp.gmail.com)
        username: Correo electrónico completo
        password: Contraseña o app password
        imap_port: Puerto IMAP (default 993)
        smtp_port: Puerto SMTP (default 465)
        use_ssl: Usar SSL/TLS (default True)
        mailbox: Carpeta IMAP (default INBOX)
        limit: Máximo de correos a retornar (default 10)
        subject_filter: Filtrar por asunto (opcional)
        body_filter: Filtrar por cuerpo (opcional)
        to_addr: Destinatario (para send_email)
        cc_addr: Con copia (para send_email)
        bcc_addr: Con copia oculta (para send_email)
        subject: Asunto del correo (para send_email)
        body: Cuerpo del correo (para send_email)
        attachments: Lista de rutas de archivos adjuntos (para send_email)
        mark_as_read: Marcar como leídos al consultar (default False)
    
    Returns:
        Dict con resultado de la operación
    """
    try:
        if action == "list_folders":
            return _list_folders(imap_host, imap_port, username, password, use_ssl)
        
        elif action == "fetch_emails":
            return _fetch_emails(
                imap_host, imap_port, username, password, use_ssl,
                mailbox, limit, subject_filter, body_filter, mark_as_read
            )
        
        elif action == "send_email":
            return _send_email(
                smtp_host, smtp_port, username, password, use_ssl,
                to_addr, cc_addr, bcc_addr, subject, body, attachments or []
            )
        
        elif action == "check_connection":
            return _check_connection(
                imap_host, imap_port, smtp_host, smtp_port,
                username, password, use_ssl
            )
        
        else:
            return {
                "status": "error",
                "message": f"Acción no válida: {action}. Usa: list_folders, fetch_emails, send_email, check_connection"
            }
    
    except Exception as e:
        logger.error(f"Error en email_manager: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
            "type": type(e).__name__
        }


def _list_folders(imap_host, imap_port, username, password, use_ssl) -> Dict[str, Any]:
    """Lista carpetas disponibles en IMAP."""
    try:
        if use_ssl:
            conn = imaplib.IMAP4_SSL(imap_host, imap_port)
        else:
            conn = imaplib.IMAP4(imap_host, imap_port)
        
        conn.login(username, password)
        status, folders = conn.list()
        conn.logout()
        
        folder_list = []
        if status == "OK":
            for f in folders:
                # Parsear respuesta IMAP
                parts = f.decode().split(' "." ')
                if len(parts) >= 3:
                    folder_list.append(parts[2].strip('"'))
                else:
                    folder_list.append(f.decode())
        
        return {
            "status": "success",
            "action": "list_folders",
            "folders": folder_list,
            "count": len(folder_list)
        }
    except Exception as e:
        return {"status": "error", "message": f"Error listando carpetas: {e}"}


def _fetch_emails(imap_host, imap_port, username, password, use_ssl,
                  mailbox, limit, subject_filter, body_filter, mark_as_read) -> Dict[str, Any]:
    """Obtiene correos de una carpeta IMAP."""
    try:
        if use_ssl:
            conn = imaplib.IMAP4_SSL(imap_host, imap_port)
        else:
            conn = imaplib.IMAP4(imap_host, imap_port)
        
        conn.login(username, password)
        conn.select(mailbox)
        
        # Buscar correos
        search_criteria = "ALL"
        if subject_filter:
            search_criteria += f' SUBJECT "{subject_filter}"'
        
        status, messages = conn.search(None, search_criteria)
        if status != "OK":
            return {"status": "error", "message": "Error en búsqueda IMAP"}
        
        email_ids = messages[0].split()
        if not email_ids:
            return {
                "status": "success",
                "action": "fetch_emails",
                "count": 0,
                "emails": [],
                "message": "No se encontraron correos"
            }
        
        # Limitar resultados (los más recientes)
        email_ids = email_ids[-limit:]
        email_ids.reverse()  # Más recientes primero
        
        emails = []
        for eid in email_ids:
            status, msg_data = conn.fetch(eid, "(RFC822)")
            if status != "OK":
                continue
            
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            
            # Extraer campos
            subject = msg.get("Subject", "(sin asunto)")
            from_addr = msg.get("From", "(desconocido)")
            to_addr = msg.get("To", "")
            date = msg.get("Date", "")
            
            # Extraer cuerpo
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type == "text/plain":
                        try:
                            body = part.get_payload(decode=True).decode('utf-8', errors='replace')
                            break
                        except:
                            pass
                    elif content_type == "text/html" and not body:
                        try:
                            body = part.get_payload(decode=True).decode('utf-8', errors='replace')
                        except:
                            pass
            else:
                try:
                    body = msg.get_payload(decode=True).decode('utf-8', errors='replace')
                except:
                    body = str(msg.get_payload())
            
            # Filtrar por cuerpo si se especifica
            if body_filter and body_filter.lower() not in body.lower():
                continue
            
            # Marcar como leído
            if mark_as_read:
                conn.store(eid, '+FLAGS', '\\Seen')
            
            emails.append({
                "id": eid.decode(),
                "subject": subject,
                "from": from_addr,
                "to": to_addr,
                "date": date,
                "body_preview": body[:200] + "..." if len(body) > 200 else body,
                "body_length": len(body)
            })
        
        conn.close()
        conn.logout()
        
        return {
            "status": "success",
            "action": "fetch_emails",
            "mailbox": mailbox,
            "count": len(emails),
            "emails": emails,
            "filters_applied": {
                "subject": subject_filter or None,
                "body": body_filter or None,
                "limit": limit
            }
        }
    
    except Exception as e:
        return {"status": "error", "message": f"Error obteniendo correos: {e}"}


def _send_email(smtp_host, smtp_port, username, password, use_ssl,
                to_addr, cc_addr, bcc_addr, subject, body, attachments) -> Dict[str, Any]:
    """Envía un correo electrónico por SMTP."""
    try:
        # Validaciones
        if not to_addr:
            return {"status": "error", "message": "Destinatario (to_addr) requerido"}
        if not subject:
            return {"status": "error", "message": "Asunto (subject) requerido"}
        if not body:
            return {"status": "error", "message": "Cuerpo (body) requerido"}
        
        # Crear mensaje
        msg = MIMEMultipart()
        msg['From'] = username
        msg['To'] = to_addr
        if cc_addr:
            msg['Cc'] = cc_addr
        if bcc_addr:
            msg['Bcc'] = bcc_addr
        msg['Subject'] = subject
        
        # Cuerpo del mensaje
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # Adjuntos
        for filepath in attachments:
            if not os.path.exists(filepath):
                return {"status": "error", "message": f"Archivo no encontrado: {filepath}"}
            
            with open(filepath, "rb") as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename="{os.path.basename(filepath)}"'
                )
                msg.attach(part)
        
        # Conectar y enviar
        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()
        
        server.login(username, password)
        
        # Enviar
        recipients = [to_addr]
        if cc_addr:
            recipients.extend([addr.strip() for addr in cc_addr.split(',')])
        if bcc_addr:
            recipients.extend([addr.strip() for addr in bcc_addr.split(',')])
        
        server.sendmail(username, recipients, msg.as_string())
        server.quit()
        
        return {
            "status": "success",
            "action": "send_email",
            "message": "Correo enviado exitosamente",
            "details": {
                "to": to_addr,
                "cc": cc_addr or None,
                "bcc": bcc_addr or None,
                "subject": subject,
                "attachments": len(attachments)
            }
        }
    
    except Exception as e:
        return {"status": "error", "message": f"Error enviando correo: {e}"}


def _check_connection(imap_host, imap_port, smtp_host, smtp_port,
                      username, password, use_ssl) -> Dict[str, Any]:
    """Verifica conexión IMAP y SMTP."""
    results = {"imap": None, "smtp": None}
    
    # Probar IMAP
    try:
        if use_ssl:
            conn = imaplib.IMAP4_SSL(imap_host, imap_port)
        else:
            conn = imaplib.IMAP4(imap_host, imap_port)
        conn.login(username, password)
        conn.logout()
        results["imap"] = "OK"
    except Exception as e:
        results["imap"] = f"ERROR: {e}"
    
    # Probar SMTP
    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()
        server.login(username, password)
        server.quit()
        results["smtp"] = "OK"
    except Exception as e:
        results["smtp"] = f"ERROR: {e}"
    
    return {
        "status": "success",
        "action": "check_connection",
        "results": results,
        "credentials_valid": results["imap"] == "OK" and results["smtp"] == "OK"
    }


# Esquema de parámetros
parameters_schema = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["list_folders", "fetch_emails", "send_email", "check_connection"],
            "description": "Acción a realizar"
        },
        "imap_host": {
            "type": "string",
            "description": "Servidor IMAP (ej: imap.gmail.com, outlook.office365.com)"
        },
        "smtp_host": {
            "type": "string",
            "description": "Servidor SMTP (ej: smtp.gmail.com, smtp.office365.com)"
        },
        "username": {
            "type": "string",
            "description": "Correo electrónico completo (ej: usuario@gmail.com)"
        },
        "password": {
            "type": "string",
            "description": "Contraseña o app password del correo"
        },
        "imap_port": {
            "type": "integer",
            "description": "Puerto IMAP (default 993 para SSL, 143 para no SSL)",
            "default": 993
        },
        "smtp_port": {
            "type": "integer",
            "description": "Puerto SMTP (default 465 para SSL, 587 para STARTTLS)",
            "default": 465
        },
        "use_ssl": {
            "type": "boolean",
            "description": "Usar conexión SSL/TLS (default True)",
            "default": True
        },
        "mailbox": {
            "type": "string",
            "description": "Carpeta IMAP a consultar (default INBOX)",
            "default": "INBOX"
        },
        "limit": {
            "type": "integer",
            "description": "Cantidad máxima de correos a retornar (default 10)",
            "default": 10
        },
        "subject_filter": {
            "type": "string",
            "description": "Filtrar correos por asunto (opcional)"
        },
        "body_filter": {
            "type": "string",
            "description": "Filtrar correos por contenido en cuerpo (opcional)"
        },
        "to_addr": {
            "type": "string",
            "description": "Destinatario del correo (para send_email)"
        },
        "cc_addr": {
            "type": "string",
            "description": "Con copia (CC) - separar múltiples con comas (para send_email)"
        },
        "bcc_addr": {
            "type": "string",
            "description": "Con copia oculta (BCC) - separar múltiples con comas (para send_email)"
        },
        "subject": {
            "type": "string",
            "description": "Asunto del correo (para send_email)"
        },
        "body": {
            "type": "string",
            "description": "Cuerpo del correo en texto plano (para send_email)"
        },
        "attachments": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Lista de rutas de archivos adjuntos (para send_email)"
        },
        "mark_as_read": {
            "type": "boolean",
            "description": "Marcar correos como leídos al consultar (default False)",
            "default": False
        }
    },
    "required": ["action", "imap_host", "smtp_host", "username", "password"]
}
