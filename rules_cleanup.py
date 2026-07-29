#!/usr/bin/env python3
"""
Actual Budget Rules Manager and Cleanup Utility
Lists all rules, resolves UUIDs to names, detects duplicates/redundancies,
and deletes rules interactively.
"""

import os
import sys
import shutil
import json
from collections import defaultdict
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.text import Text

from actual import Actual
from actual.queries import (
    get_rules,
    get_payees,
    get_categories,
    get_accounts,
)
from actual.rules import Rule, Condition, Action

# Import connection config and translation helpers from categorize.py
from categorize import load_config, select_budget_file, t

console = Console()


def get_rule_signature(rule):
    """Computes a canonical signature tuple for duplicate detection."""
    conds = []
    for c in rule.conditions:
        op = c.op.value if hasattr(c.op, "value") else str(c.op)
        conds.append((c.field, op, str(c.value).lower().strip()))
    conds.sort()

    acts = []
    for a in rule.actions:
        op = a.op.value if hasattr(a.op, "value") else str(a.op)
        acts.append((a.field, op, str(a.value).lower().strip()))
    acts.sort()

    return (rule.stage, rule.operation, tuple(conds), tuple(acts))


def format_rule_conditions(rule, payee_by_id, category_by_id, account_by_id):
    """Formats rule conditions to be human-readable, resolving UUIDs to names."""
    cond_strs = []
    for c in rule.conditions:
        field = c.field
        op = c.op.value if hasattr(c.op, "value") else str(c.op)
        val = c.value

        # Resolve UUID values if applicable
        if field == "description" and val in payee_by_id:
            val = f"'{payee_by_id[val].name}'"
        elif field == "category" and val in category_by_id:
            val = f"'{category_by_id[val].name}'"
        elif field == "acct" and val in account_by_id:
            val = f"'{account_by_id[val].name}'"
        else:
            val = f"'{val}'"

        cond_strs.append(f"'{field}' {op} {val}")

    op_join = f" {rule.operation} "
    return op_join.join(cond_strs)


def format_rule_actions(rule, payee_by_id, category_by_id, account_by_id):
    """Formats rule actions to be human-readable, resolving UUIDs to names."""
    action_strs = []
    for a in rule.actions:
        field = a.field
        op = a.op.value if hasattr(a.op, "value") else str(a.op)
        val = a.value

        # Resolve UUID values if applicable
        if field == "description" and val in payee_by_id:
            val = f"'{payee_by_id[val].name}'"
        elif field == "category" and val in category_by_id:
            val = f"'{category_by_id[val].name}'"
        elif field == "acct" and val in account_by_id:
            val = f"'{account_by_id[val].name}'"
        else:
            val = f"'{val}'"

        action_strs.append(f"{op} '{field}' to {val}")

    return ", ".join(action_strs)


def detect_duplicates_and_redundancies(parsed_rules):
    """
    Identifies exact duplicates and redundant substring-based rules.
    Returns:
      exact_duplicates: list of parsed rule tuple indices to delete.
      redundancies: list of tuples (redundant_idx, main_idx) representing redundant rules.
    """
    exact_duplicates = []
    redundancies = []

    # 1. Detect exact duplicates
    sig_map = defaultdict(list)
    for idx, (db_rule, rule) in enumerate(parsed_rules):
        sig = get_rule_signature(rule)
        sig_map[sig].append(idx)

    for sig, indices in sig_map.items():
        if len(indices) > 1:
            # Keep the first one, mark the rest as exact duplicates to delete
            exact_duplicates.extend(indices[1:])

    # 2. Detect redundancies
    # Standard pre-import mapping rules: single 'imported_description' contains 'val' -> set payee
    for idx_a, (_, rule_a) in enumerate(parsed_rules):
        if idx_a in exact_duplicates:
            continue
        if len(rule_a.conditions) != 1 or len(rule_a.actions) != 1:
            continue

        c_a = rule_a.conditions[0]
        a_a = rule_a.actions[0]

        if c_a.field != "imported_description" or c_a.op.value != "contains":
            continue
        if a_a.field != "description" or a_a.op.value != "set":
            continue

        val_a = str(c_a.value).lower().strip()
        target_a = a_a.value

        for idx_b, (_, rule_b) in enumerate(parsed_rules):
            if idx_b == idx_a or idx_b in exact_duplicates:
                continue
            if len(rule_b.conditions) != 1 or len(rule_b.actions) != 1:
                continue

            c_b = rule_b.conditions[0]
            a_b = rule_b.actions[0]

            if c_b.field != "imported_description" or c_b.op.value != "contains":
                continue
            if a_b.field != "description" or a_b.op.value != "set":
                continue

            val_b = str(c_b.value).lower().strip()
            target_b = a_b.value

            # If they map to the same payee, and val_a is a substring of val_b, B is redundant!
            if target_a == target_b and val_a in val_b and val_a != val_b:
                # Add to redundancies if not already added
                if not any(r[0] == idx_b for r in redundancies):
                    redundancies.append((idx_b, idx_a))

    return exact_duplicates, redundancies


def run_rules_cleanup():
    console.print(f"[bold cyan]{t('rules_welcome')}[/bold cyan]\n")
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

            console.print(t("rules_scanning"))

            # Retrieve active lookups for formatting
            payee_by_id = {p.id: p for p in get_payees(actual.session)}
            category_by_id = {c.id: c for c in get_categories(actual.session)}
            account_by_id = {a.id: a for a in get_accounts(actual.session)}

            # Load active rules and parse them into high-level Rule objects
            db_rules = [r for r in get_rules(actual.session) if not r.tombstone]

            parsed_rules = []
            for dbr in db_rules:
                try:
                    r = Rule(
                        stage=dbr.stage,
                        operation=dbr.conditions_op,
                        conditions=json.loads(dbr.conditions),
                        actions=json.loads(dbr.actions),
                    )
                    parsed_rules.append((dbr, r))
                except Exception:
                    # Skip unparseable rules
                    pass

            if not parsed_rules:
                console.print(f"\n{t('rules_none')}")
                if backup_file.exists():
                    backup_file.unlink()
                return

            while True:
                console.print()
                menu_text = Text()
                menu_text.append(f"[1] {t('rules_opt_view')}\n", style="cyan")
                menu_text.append(f"[2] {t('rules_opt_cleanup')}\n", style="yellow")
                menu_text.append(f"[3] {t('rules_opt_delete_specific')}\n", style="magenta")
                menu_text.append(f"[Q] {t('menu_opt_quit')}\n", style="red")

                panel = Panel(
                    menu_text,
                    title=f"[bold white]{t('menu_opt_rules_cleanup')}[/bold white]",
                    expand=False,
                    border_style="blue",
                )
                console.print(panel)

                choice = Prompt.ask(
                    t("menu_prompt"),
                    choices=["1", "2", "3", "Q", "q"],
                    default="1",
                ).strip().upper()

                if choice == "1":
                    # View all rules
                    table = Table(title=t("rules_list_title"))
                    table.add_column(t("rules_col_idx"), style="dim")
                    table.add_column(t("rules_col_type"), style="cyan")
                    table.add_column(t("rules_col_conditions"), style="yellow")
                    table.add_column(t("rules_col_actions"), style="green")

                    for idx, (db_r, rule) in enumerate(parsed_rules, 1):
                        cond_str = format_rule_conditions(rule, payee_by_id, category_by_id, account_by_id)
                        act_str = format_rule_actions(rule, payee_by_id, category_by_id, account_by_id)
                        table.add_row(str(idx), db_r.stage or "pre", cond_str, act_str)

                    console.print(table)

                elif choice == "2":
                    # Detect and cleanup duplicates / redundancies
                    exact_dups, redundancies = detect_duplicates_and_redundancies(parsed_rules)

                    to_delete_indices = set(exact_dups + [r[0] for r in redundancies])

                    if not to_delete_indices:
                        console.print(f"\n{t('rules_dup_none')}")
                        continue

                    console.print(f"\n{t('rules_dup_detected', count=len(to_delete_indices))}")

                    # List exact duplicates
                    if exact_dups:
                        console.print("\n[bold red]Exact Duplicates:[/bold red]")
                        for idx in exact_dups:
                            db_r, rule = parsed_rules[idx]
                            cond_str = format_rule_conditions(rule, payee_by_id, category_by_id, account_by_id)
                            console.print(f"  - [{idx+1}] {cond_str}")

                    # List redundancies
                    if redundancies:
                        console.print("\n[bold yellow]Redundant Rules:[/bold yellow]")
                        for redundant_idx, main_idx in redundancies:
                            db_r_r, rule_r = parsed_rules[redundant_idx]
                            _, rule_m = parsed_rules[main_idx]
                            cond_str_r = format_rule_conditions(rule_r, payee_by_id, category_by_id, account_by_id)
                            cond_str_m = format_rule_conditions(rule_m, payee_by_id, category_by_id, account_by_id)
                            console.print(f"  - [{redundant_idx+1}] {cond_str_r} (covered by [{main_idx+1}] {cond_str_m})")

                    if Confirm.ask(
                        f"\n[bold cyan]{t('rules_confirm_dup_delete', count=len(to_delete_indices))}[/bold cyan]",
                        default=True,
                    ):
                        console.print(t("writing_changes"))
                        # Apply deletes
                        for idx in to_delete_indices:
                            db_r, _ = parsed_rules[idx]
                            db_r.tombstone = 1
                            actual.session.add(db_r)

                        actual.commit()
                        console.print(t("rules_delete_success", count=len(to_delete_indices)))

                        # Re-load remaining rules
                        db_rules = [r for r in get_rules(actual.session) if not r.tombstone]
                        parsed_rules = []
                        for dbr in db_rules:
                            try:
                                r = Rule(
                                    stage=dbr.stage,
                                    operation=dbr.conditions_op,
                                    conditions=json.loads(dbr.conditions),
                                    actions=json.loads(dbr.actions),
                                )
                                parsed_rules.append((dbr, r))
                            except Exception:
                                pass
                    else:
                        console.print(t("changes_discarded"))

                elif choice == "3":
                    # Delete specific rule(s)
                    del_choice = Prompt.ask(t("rules_delete_prompt")).strip()
                    if del_choice.upper() == "Q":
                        continue

                    try:
                        indices = [int(x.strip()) - 1 for x in del_choice.split(",") if x.strip()]
                        valid_indices = []
                        for idx in indices:
                            if 0 <= idx < len(parsed_rules):
                                valid_indices.append(idx)
                            else:
                                console.print(f"[red]Index {idx+1} out of bounds.[/red]")
                    except ValueError:
                        console.print("[red]Invalid format. Action canceled.[/red]")
                        continue

                    if not valid_indices:
                        continue

                    # List what will be deleted
                    console.print("\n[red]Rules selected for deletion:[/red]")
                    for idx in valid_indices:
                        db_r, rule = parsed_rules[idx]
                        cond_str = format_rule_conditions(rule, payee_by_id, category_by_id, account_by_id)
                        act_str = format_rule_actions(rule, payee_by_id, category_by_id, account_by_id)
                        console.print(f"  - [{idx+1}] {cond_str} -> {act_str}")

                    if Confirm.ask(
                        f"\n[bold cyan]{t('rules_confirm_delete', count=len(valid_indices))}[/bold cyan]",
                        default=False,
                    ):
                        console.print(t("writing_changes"))
                        for idx in valid_indices:
                            db_r, _ = parsed_rules[idx]
                            db_r.tombstone = 1
                            actual.session.add(db_r)

                        actual.commit()
                        console.print(t("rules_delete_success", count=len(valid_indices)))

                        # Re-load remaining rules
                        db_rules = [r for r in get_rules(actual.session) if not r.tombstone]
                        parsed_rules = []
                        for dbr in db_rules:
                            try:
                                r = Rule(
                                    stage=dbr.stage,
                                    operation=dbr.conditions_op,
                                    conditions=json.loads(dbr.conditions),
                                    actions=json.loads(dbr.actions),
                                )
                                parsed_rules.append((dbr, r))
                            except Exception:
                                pass
                    else:
                        console.print(t("changes_discarded"))

                elif choice == "Q":
                    # Quit and return to main menu
                    # Clean up local backup
                    if backup_file.exists():
                        backup_file.unlink()
                    break

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
        run_rules_cleanup()
    except KeyboardInterrupt:
        console.print(f"\n[yellow]{t('exiting_gracefully')}[/yellow]")
        sys.exit(0)
