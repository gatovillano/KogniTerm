"""
CLI de administración del sistema de pagos: ``kogniterm pay <subcomando>``.

Pensado para operar el sistema sin editar JSON a mano ni depender del servidor
HTTP en marcha. Todos los subcomandos operate sobre el mismo
``~/.kogniterm/payments_data.json`` que usa el backend, así que la CLI y la
API ven siempre el mismo estado.

    kogniterm pay plans                      # catálogo
    kogniterm pay status                    # proveedores y salud del sistema
    kogniterm pay config --provider stripe --secret-key sk_...
    kogniterm pay sub alice                 # suscripción + créditos
    kogniterm pay grant alice 5000          # créditos de cortesía
    kogniterm pay consume alice 250         # consumo manual
    kogniterm pay refund tx_abc123          # reembolso total
    kogniterm pay history alice             # transacciones
    kogniterm pay ledger alice              # movimientos de créditos
    kogniterm pay reconcile                 # degradar suscripciones vencidas
    kogniterm pay audit                     # verificar bitácora
"""

from __future__ import annotations

import json
import sys
from typing import List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from kogniterm.server.payments import get_payment_service
from kogniterm.server.payments.errors import PaymentError
from kogniterm.server.payments.models import PaymentProviderType

console = Console()

HELP = """
[bold cyan]KogniTerm · Pagos[/bold cyan]

  [bold]planes[/bold]                       Lista el catálogo de planes y packs
  [bold]status[/bold]                       Estado de proveedores y del almacén
  [bold]config[/bold] [dim]opciones[/dim]   Configura credenciales de un proveedor
        --provider stripe|mock|mercadopago
        --secret-key <clave>  --webhook-secret <clave>  --disable
  [bold]sub[/bold] <usuario>                Suscripción, créditos y límites
  [bold]grant[/bold] <usuario> <n>          Otorga créditos
  [bold]consume[/bold] <usuario> <n>        Descuenta créditos
  [bold]refund[/bold] <tx_id> [n]           Reembolsa (n = centavos, opcional)
  [bold]history[/bold] <usuario>            Transacciones del usuario
  [bold]ledger[/bold] <usuario>             Movimientos de créditos
  [bold]reconcile[/bold]                    Degrada a Free las suscripciones vencidas
  [bold]audit[/bold]                        Verifica la cadena de la bitácora
"""


def handle_pay(args: List[str]) -> bool:
    """Punto de entrada del subcomando ``pay``."""
    if not args or args[0] in ("-h", "--help", "help"):
        console.print(HELP)
        return True

    command, rest = args[0], args[1:]
    try:
        service = get_payment_service()
    except Exception as exc:
        console.print(f"[bold red]❌ No se pudo iniciar el sistema de pagos:[/bold red] {exc}")
        return True

    try:
        if command == "plans":
            _plans(service)
        elif command == "status":
            _status(service)
        elif command == "config":
            _config(service, rest)
        elif command == "sub":
            _subscription(service, _require(rest, 0, "sub <usuario>"))
        elif command == "grant":
            _grant(service, _require(rest, 0, "grant <usuario> <n>"), _require(rest, 1, "grant <usuario> <n>"))
        elif command == "consume":
            _consume(service, _require(rest, 0, "consume <usuario> <n>"), _require(rest, 1, "consume <usuario> <n>"))
        elif command == "refund":
            _refund(service, rest)
        elif command == "history":
            _history(service, _require(rest, 0, "history <usuario>"))
        elif command == "ledger":
            _ledger(service, _require(rest, 0, "ledger <usuario>"))
        elif command == "reconcile":
            _reconcile(service)
        elif command == "audit":
            _audit(service)
        else:
            console.print(f"[bold red]✗ Subcomando desconocido:[/bold red] {command}")
            console.print(HELP)
    except PaymentError as exc:
        console.print(f"[bold red]❌ {exc.code}:[/bold red] {exc.message}")
        if exc.details:
            console.print(f"[dim]{json.dumps(exc.details, ensure_ascii=False)}[/dim]")
    except Exception as exc:
        console.print(f"[bold red]❌ Error inesperado:[/bold red] {exc}")

    return True


# ── Subcomandos ──────────────────────────────────────────────────────────────


def _plans(service) -> None:
    table = Table(title="Planes", show_lines=False, header_style="bold cyan")
    table.add_column("ID", style="cyan")
    table.add_column("Nombre")
    table.add_column("Precio", justify="right")
    table.add_column("Intervalo")
    table.add_column("Créditos", justify="right")

    for plan in service.get_plans():
        precio = "gratis" if plan.price_cents == 0 else plan.price_display()
        tabla = f"{plan.tier.value}"
        if plan.popular:
            tabla += " ★"
        table.add_row(plan.id, f"{plan.name} [{tabla}]", precio, plan.interval.value, f"{plan.credits_included:,}".replace(",", "."))
    console.print(table)

    packs = service.get_credit_packs()
    if packs:
        pack_table = Table(title="Paquetes de créditos", header_style="bold cyan")
        pack_table.add_column("ID", style="cyan")
        pack_table.add_column("Nombre")
        pack_table.add_column("Precio", justify="right")
        pack_table.add_column("Créditos", justify="right")
        for pack in packs:
            extra = f" (+{pack.bonus_credits:,} regalo)".replace(",", ".") if pack.bonus_credits else ""
            pack_table.add_row(
                pack.id,
                pack.name,
                f"{pack.price_cents / 100:,.2f} {pack.currency}",
                f"{pack.total_credits:,}".replace(",", ".") + extra,
            )
        console.print(pack_table)


def _status(service) -> None:
    status = service.provider_status()
    console.print(
        Panel(
            "\n".join(
                [
                    f"Proveedor activo : [bold cyan]{status['active_provider']}[/bold cyan]",
                    f"Operativo        : {'✅ sí' if status['ready'] else '❌ no'}",
                    f"Almacén          : [dim]{status['data_file']}[/dim]",
                    f"Esquema          : v{status['schema_version']}",
                    f"Bitácora íntegra : {'✅ sí' if status['audit_chain_valid'] else '❌ ROTA'}",
                ]
            ),
            title="Sistema de Pagos",
            border_style="cyan",
        )
    )

    table = Table(title="Proveedores", header_style="bold cyan")
    table.add_column("Proveedor", style="cyan")
    table.add_column("Configurado")
    table.add_column("Webhook")
    for name, info in status["credentials"].items():
        table.add_row(
            name,
            "✅" if info["configured"] else "❌",
            "✅" if info["webhook_configured"] else "❌",
        )
    console.print(table)


def _config(service, args: List[str]) -> None:
    provider = None
    secret_key = None
    webhook_secret = None
    disable = False

    i = 0
    while i < len(args):
        token = args[i]
        if token == "--provider" and i + 1 < len(args):
            provider = args[i + 1]
            i += 2
        elif token in ("--secret-key", "-k") and i + 1 < len(args):
            secret_key = args[i + 1]
            i += 2
        elif token == "--webhook-secret" and i + 1 < len(args):
            webhook_secret = args[i + 1]
            i += 2
        elif token == "--disable":
            disable = True
            i += 1
        else:
            i += 1

    if not provider:
        console.print("[bold red]❌ Falta --provider[/bold red] (stripe|mock|mercadopago)")
        return

    try:
        provider_enum = PaymentProviderType(provider.lower())
    except ValueError:
        console.print(f"[bold red]✗ Proveedor desconocido:[/bold red] {provider}")
        return

    service.credentials.set(
        provider_enum,
        secret_key=secret_key,
        webhook_secret=webhook_secret,
        enabled=not disable,
    )
    console.print(f"[green]✅ Credenciales de [bold]{provider_enum.value}[/bold] actualizadas.[/green]")
    console.print(f"[dim]   Archivo: {service.credentials.path} (permisos 0600)[/dim]")


def _subscription(service, user_id: str) -> None:
    summary = service.summary(user_id)
    sub = summary["subscription"]
    ent = summary["entitlements"]

    cuerpo = [
        f"Plan          : [bold cyan]{sub['plan_id']}[/bold cyan] ({ent['tier']})",
        f"Estado        : {sub['status']}",
        f"Proveedor     : {sub['provider']}",
        f"Créditos      : [bold]{sub['credits_remaining']:,}[/bold]".replace(",", ".")
        + f"  (otorgados {sub['credits_granted_total']:,} / consumidos {sub['credits_consumed_total']:,})".replace(",", "."),
    ]
    if sub.get("expires_at"):
        dias = ent.get("days_remaining")
        cuerpo.append(f"Expira        : en {dias} día(s)" if dias is not None else "Expira        : sin fecha")
    if sub.get("cancel_at_period_end"):
        cuerpo.append("⚠️  Cancelada al final del periodo en curso")

    cuerpo.append("")
    cuerpo.append("[bold]Límites efectivos[/bold]")
    for feature, value in ent["limits"].items():
        cuerpo.append(f"  · {feature:<26} {value}")

    console.print(Panel("\n".join(cuerpo), title=f"Suscripción · {user_id}", border_style="cyan"))


def _grant(service, user_id: str, amount: str) -> None:
    result = service.grant_credits(user_id, _int(amount, "cantidad"), reason="cli_grant")
    console.print(f"[green]✅ {result['granted']} créditos otorgados.[/green] Saldo: [bold]{result['balance']}[/bold]")


def _consume(service, user_id: str, amount: str) -> None:
    result = service.consume_credits(user_id, _int(amount, "cantidad"), reason="cli_consume")
    console.print(f"[green]✅ {result['consumed']} créditos consumidos.[/green] Saldo: [bold]{result['balance']}[/bold]")


def _refund(service, args: List[str]) -> None:
    tx_id = _require(args, 0, "refund <tx_id> [centavos]")
    amount = _int(args[1], "centavos") if len(args) > 1 else None
    result = service.refund(tx_id, amount)
    console.print(
        f"[green]✅ Reembolso emitido.[/green] "
        f"{result['amount_cents'] / 100:,.2f} {result['provider']} · "
        f"créditos revocados: {result['entitlement_change'].get('credits_revoked', 0)}"
    )


def _history(service, user_id: str) -> None:
    txs = service.store.transactions_for_user(user_id, limit=30)
    if not txs:
        console.print("[dim]Sin transacciones.[/dim]")
        return
    table = Table(title=f"Transacciones · {user_id}", header_style="bold cyan")
    table.add_column("ID", style="cyan")
    table.add_column("Item")
    table.add_column("Importe", justify="right")
    table.add_column("Estado")
    table.add_column("Fecha")
    import datetime

    for tx in txs:
        table.add_row(
            tx.id[:16],
            tx.plan_id,
            f"{tx.amount_cents / 100:,.2f} {tx.currency}",
            _status_style(tx.status.value),
            datetime.datetime.fromtimestamp(tx.created_at).strftime("%Y-%m-%d %H:%M"),
        )
    console.print(table)


def _ledger(service, user_id: str) -> None:
    entries = service.store.ledger_for_user(user_id, limit=30)
    if not entries:
        console.print("[dim]Sin movimientos de créditos.[/dim]")
        return
    table = Table(title=f"Libro de créditos · {user_id}", header_style="bold cyan")
    table.add_column("Delta", justify="right")
    table.add_column("Saldo", justify="right")
    table.add_column("Motivo")
    for entry in entries:
        delta = f"+{entry.delta}" if entry.delta > 0 else str(entry.delta)
        table.add_row(
            f"[green]{delta}[/green]" if entry.delta > 0 else f"[red]{delta}[/red]",
            str(entry.balance_after),
            entry.reason,
        )
    console.print(table)


def _reconcile(service) -> None:
    result = service.reconcile_expirations()
    if result["expired_count"]:
        console.print(
            f"[green]✅ {result['expired_count']} suscripción(es) degradada(s) a Free:[/green]\n"
            + "\n".join(f"  · {uid}" for uid in result["expired_users"])
        )
    else:
        console.print("[dim]Ninguna suscripción vencida.[/dim]")


def _audit(service) -> None:
    result = service.store.verify_audit_chain()
    if result["valid"]:
        console.print(f"[green]✅ Bitácora íntegra ({result['entries']} entradas).[/green]")
    else:
        console.print(
            f"[bold red]❌ Bitácora manipulada[/bold red] en la entrada #{result['broken_at']}: {result['reason']}"
        )
        sys.exit(1)


# ── Ayudas ───────────────────────────────────────────────────────────────────


def _require(args: List[str], index: int, usage: str) -> str:
    if len(args) <= index or not args[index]:
        console.print(f"[bold red]❌ Uso:[/bold red] kogniterm pay {usage}")
        raise SystemExit(0)
    return args[index]


def _int(value: str, label: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        console.print(f"[bold red]❌ {label} inválida:[/bold red] {value!r} (debe ser un entero)")
        raise SystemExit(0)


def _status_style(status: str) -> str:
    return {
        "completed": "[green]completado[/green]",
        "pending": "[yellow]pendiente[/yellow]",
        "failed": "[red]fallido[/red]",
        "refunded": "[magenta]reembolsado[/magenta]",
        "partially_refunded": "[magenta]parcial[/magenta]",
        "disputed": "[red]en disputa[/red]",
        "cancelled": "[dim]cancelado[/dim]",
    }.get(status, status)
