#!/usr/bin/env python3
"""
Actual Budget Remove Empty Payees
Finds and deletes payees that have 0 transactions associated with them.
"""

import os
import sys
import shutil
from collections import Counter
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm

from actual import Actual
from actual.queries import get_payees, get_transactions

# Import connection config and translation helpers from categorize.py
from categorize import load_config, select_budget_file, t

console = Console()


def run_remove_empty():
    console.print(f"[bold cyan]{t('remove_empty_welcome')}[/bold cyan]\n")
    config = load_config()

    if not config.get("budget_file"):
        config = select_budget_file(config)

    console.print(t("connecting_download", file=config["budget_file"]))

    backup_file = None
    db_file = None

    try:
        with Actual(
            base_url=config["server_url"],
            password=config["password"],
            token=config["token"],
            file=config["budget_file"],
            encryption_password=config.get("encryption_password"),
            cert=config.get("cert", True),
        ) as actual:

            # Resolve local database files
            db_file = Path(actual._data_dir) / "db.sqlite"
            backup_file = Path(actual._data_dir) / "db.sqlite.backup"

            # Create backup
            try:
                shutil.copy2(db_file, backup_file)
                console.print(t("cleanup_backup_created", path=backup_file))
            except Exception as e:
                console.print(t("cleanup_backup_error", err=e))
                sys.exit(1)

            console.print(t("remove_empty_scanning"))

            # Retrieve active payees and transactions
            active_payees = [p for p in get_payees(actual.session) if not p.tombstone]
            all_txs = get_transactions(actual.session)

            # Frequency map: payee_id -> count of transactions
            payee_tx_count = Counter(
                t_item.payee_id for t_item in all_txs if t_item.payee_id
            )

            # Filter for empty payees (excluding transfer payees)
            empty_payees = []
            for p in active_payees:
                # Skip transfer payees (which have transfer_acct populated or start with transfer:)
                if getattr(p, "transfer_acct", None) is not None or (p.id and p.id.startswith("transfer:")):
                    continue
                if payee_tx_count[p.id] == 0:
                    empty_payees.append(p)

            if not empty_payees:
                console.print(f"\n{t('remove_empty_none')}")
                if backup_file.exists():
                    backup_file.unlink()
                return

            console.print(f"\n{t('remove_empty_found', count=len(empty_payees))}")
            for p in empty_payees:
                console.print(f"  - {p.name}")

            # Prompt to confirm deletion
            if Confirm.ask(
                f"\n[bold cyan]{t('remove_empty_confirm', count=len(empty_payees))}[/bold cyan]",
                default=False,
            ):
                console.print(t("remove_empty_deleting"))
                for p in empty_payees:
                    p.tombstone = 1
                    actual.session.add(p)

                actual.commit()
                console.print(t("remove_empty_success", count=len(empty_payees)))

                # Clean up local backup after successful commit
                if backup_file.exists():
                    backup_file.unlink()
            else:
                console.print(t("changes_discarded"))
                # Restore backup
                if backup_file.exists():
                    shutil.copy2(backup_file, db_file)
                    backup_file.unlink()

    except Exception as e:
        # Restore backup if failure occurred before committing
        if backup_file and db_file and backup_file.exists():
            try:
                shutil.copy2(backup_file, db_file)
                backup_file.unlink()
                console.print(t("cleanup_restored", err=e))
            except Exception as restore_err:
                console.print(
                    f"[red]Failed to restore backup: {restore_err}[/red]"
                )
        else:
            console.print(
                f"[bold red]An error occurred: {e}[/bold red]"
            )

        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    try:
        run_remove_empty()
    except KeyboardInterrupt:
        console.print(f"\n[yellow]{t('exiting_gracefully')}[/yellow]")
        sys.exit(0)
