#!/usr/bin/env python3
"""
Actual Budget Payee Cleanup and Rule Creation Wizard
Finds duplicate payees in the database, merges them interactively,
and automatically creates pre-import rules.
"""

import os
import sys
import re
import shutil
import difflib
from collections import defaultdict, Counter
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.text import Text

from actual import Actual
from actual.queries import (
    get_payees,
    get_transactions,
    create_rule,
)
from actual.rules import Rule, Condition, Action

# Import connection config and translation helpers from categorize.py
from categorize import load_config, select_budget_file, get_payee_display, t

console = Console()


def normalize_payee_name(name):
    """
    Normalizes payee names by removing billing numbers, invoice prefixes,
    and extra spaces to group duplicates.
    """
    if not name:
        return ""
    # Lowercase
    s = name.lower().strip()
    # Remove common invoice prefixes in IT/EN (e.g. "n:", "n.", "inv:", "fattura:", "fatt:")
    # Matches "n", "n.", "inv", "fattura" followed by optional colon/spaces and digits
    s = re.sub(r"\b(n|n\.|inv|fattura|fatt|no|n°|n\.o)\b[\s:]*\d+.*", "", s)
    # Remove standard numeric codes (strings of 5+ digits, with optional separators like / or -)
    s = re.sub(r"\b\d{5,}([\/\-]\d+)?\b", "", s)
    # Remove any trailing numbers, spaces, or punctuation/separators
    s = re.sub(r"[\s\d\-:\/\.]+$", "", s)
    # Strip extra spaces
    s = re.sub(r"\s+", " ", s).strip()
    return s


def get_default_search_term(name):
    """Computes a clean default search term for the pre-import rule."""
    s = name.strip()
    # Remove common corporate suffixes
    s = re.sub(
        r"\b(s\.?r\.?l\.?|s\.?p\.?a\.?|sr|inc|ltd|co|spa|srl)\b\.?",
        "",
        s,
        flags=re.IGNORECASE,
    )
    # Clean up trailing spaces and punctuation (dots, commas, dashes)
    s = re.sub(r"[\s\.,\-]+$", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def cluster_payees(active_payees):
    """
    Groups active payees into clusters of similar/duplicate names.
    Excludes transfer payees.
    """
    clusters = []
    for p in active_payees:
        # Skip transfer accounts
        if getattr(p, "transfer_acct", None) is not None:
            continue
        norm = normalize_payee_name(p.name)
        if not norm:
            continue

        found = False
        for cluster in clusters:
            rep = cluster[0]
            rep_norm = normalize_payee_name(rep.name)

            # 1. Exact normalized name match
            if norm == rep_norm:
                cluster.append(p)
                found = True
                break

            # 2. Fuzzy match or substring match
            ratio = difflib.SequenceMatcher(None, norm, rep_norm).ratio()
            # 0.85 ratio OR one is a substring of the other (if length >= 6)
            if ratio >= 0.85 or (
                (len(norm) >= 6 and norm in rep_norm)
                or (len(rep_norm) >= 6 and rep_norm in norm)
            ):
                cluster.append(p)
                found = True
                break

        if not found:
            clusters.append([p])

    # Keep only clusters that have actual duplicates (size > 1)
    return [c for c in clusters if len(c) > 1]


def run_cleanup():
    console.print(f"[bold cyan]{t('cleanup_welcome')}[/bold cyan]\n")
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

            # Retrieve active payees and transactions
            active_payees = [p for p in get_payees(actual.session) if not p.tombstone]
            all_txs = get_transactions(actual.session)

            # Frequency map: payee_id -> count of transactions
            payee_tx_count = Counter(
                t_item.payee_id for t_item in all_txs if t_item.payee_id
            )

            # Group payees into clusters
            clusters = cluster_payees(active_payees)

            if not clusters:
                console.print(f"\n{t('cleanup_no_duplicates')}")
                return

            proposed_merges = []  # List of tuples: (target_payee, [duplicate_payees], search_term)

            for c_idx, cluster in enumerate(clusters, 1):
                # Sort cluster items by transaction count descending so the most active is first
                cluster.sort(key=lambda p: payee_tx_count[p.id], reverse=True)

                console.print()
                panel_title = t("cleanup_cluster_header", idx=c_idx, total=len(clusters), name=cluster[0].name)
                console.print(f"[bold yellow]--- {panel_title} ---[/bold yellow]")

                # Print payees in this cluster
                for num, p in enumerate(cluster, 1):
                    tx_count = payee_tx_count[p.id]
                    console.print(t("cleanup_payee_row", num=num, name=p.name, tx_count=tx_count))

                # 1. Select the main Target Payee to keep
                choice = Prompt.ask(
                    t("cleanup_select_target", max=len(cluster)),
                    default="1",
                ).strip()

                if choice.upper() == "Q":
                    console.print("[yellow]Exiting wizard early. Moving to review phase.[/yellow]")
                    break

                if choice.upper() == "S":
                    console.print(t("cleanup_skipped"))
                    continue

                if choice.upper() == "N":
                    new_name = Prompt.ask(t("cleanup_new_payee_prompt")).strip()
                    if not new_name:
                        console.print("[red]Empty name. Skipping cluster.[/red]")
                        continue
                    
                    # Check if payee already exists in active_payees
                    existing_payee = None
                    new_name_lower = new_name.strip().lower()
                    for p in active_payees:
                        if p.name.strip().lower() == new_name_lower:
                            existing_payee = p
                            break

                    if existing_payee:
                        target_payee = existing_payee
                        console.print(t("cleanup_payee_exists", name=existing_payee.name))
                    else:
                        # Create the new payee in the database
                        from actual.queries import create_payee
                        target_payee = create_payee(actual.session, new_name)
                        console.print(t("cleanup_new_payee_created", name=new_name))
                        active_payees.append(target_payee)

                    # All current cluster members are candidates to be merged into this target payee
                    # (excluding the target payee itself if it happens to exist in this cluster)
                    candidates = [p for p in cluster if p.id != target_payee.id]
                else:
                    try:
                        target_idx = int(choice) - 1
                        if not (0 <= target_idx < len(cluster)):
                            raise ValueError()
                    except ValueError:
                        console.print("[red]Invalid selection. Skipping this cluster.[/red]")
                        continue
                    target_payee = cluster[target_idx]
                    # Get candidates for merging (all other payees in the cluster)
                    candidates = [p for i, p in enumerate(cluster) if i != target_idx]

                # 2. Select which ones to merge (allows exclusions)
                console.print(f"\n[cyan]Candidates for merging into '{target_payee.name}':[/cyan]")
                for num, p in enumerate(candidates, 1):
                    console.print(t("cleanup_payee_row", num=num, name=p.name, tx_count=payee_tx_count[p.id]))

                merge_choice = Prompt.ask(
                    t("cleanup_select_merge"),
                    default="",
                ).strip()

                to_merge = []
                if not merge_choice:
                    # Merge all candidates by default
                    to_merge = candidates
                else:
                    try:
                        indices = [int(x.strip()) - 1 for x in merge_choice.split(",") if x.strip()]
                        for idx in indices:
                            if 0 <= idx < len(candidates):
                                to_merge.append(candidates[idx])
                            else:
                                console.print(f"[red]Index {idx+1} out of bounds. Skipping it.[/red]")
                    except ValueError:
                        console.print("[red]Invalid format. Merging all other payees by default.[/red]")
                        to_merge = candidates

                if not to_merge:
                    console.print("[yellow]No payees selected to merge. Skipping cluster.[/yellow]")
                    continue

                # 3. Enter search term for rule
                default_search = get_default_search_term(target_payee.name)
                search_term = Prompt.ask(
                    t("cleanup_search_term_prompt", default=default_search),
                    default=default_search,
                ).strip()

                # 4. Confirm merge block
                if Confirm.ask(
                    t(
                        "cleanup_confirm_merge",
                        count=len(to_merge),
                        target=target_payee.name,
                        search=search_term,
                    ),
                    default=True,
                ):
                    proposed_merges.append((target_payee, to_merge, search_term))
                    console.print(t("cleanup_accepted"))
                else:
                    console.print(t("cleanup_skipped"))

            # End of loops: Review proposed changes
            if not proposed_merges:
                console.print(t("no_changes_made"))
                return

            console.print(f"\n[bold cyan]{t('cleanup_review_title')}[/bold cyan]")
            review_table = Table()
            review_table.add_column(t("cleanup_col_target"), style="green")
            review_table.add_column(t("cleanup_col_merged"), style="yellow")
            review_table.add_column(t("cleanup_col_rule"), style="cyan")

            total_merged_count = 0
            for target, duplicates, search in proposed_merges:
                dup_names = ", ".join(p.name for p in duplicates)
                review_table.add_row(target.name, dup_names, search)
                total_merged_count += len(duplicates)

            console.print(review_table)
            console.print(
                t(
                    "cleanup_summary",
                    merged_count=total_merged_count,
                    target_count=len(proposed_merges),
                    rules_count=len(proposed_merges),
                )
            )

            # Final confirmation
            if Confirm.ask(
                f"[bold cyan]{t('cleanup_confirm_commit')}[/bold cyan]",
                default=True,
            ):
                console.print(t("writing_changes"))

                # Apply modifications
                for target, duplicates, search in proposed_merges:
                    dup_ids = {p.id for p in duplicates}

                    # 1. Update transactions pointing to duplicate payees
                    for t_item in all_txs:
                        if t_item.payee_id in dup_ids:
                            t_item.payee_id = target.id

                    # 2. Tombstone duplicates
                    for dup in duplicates:
                        dup.tombstone = 1
                        actual.session.add(dup)

                    # 3. Create the pre-import rule
                    r = Rule(
                        stage="pre",
                        operation="and",
                        conditions=[
                            Condition(
                                field="imported_description",
                                op="contains",
                                value=search,
                            )
                        ],
                        actions=[
                            Action(
                                field="description",
                                op="set",
                                value=target.id,
                            )
                        ],
                    )
                    create_rule(actual.session, r)

                # Commit and Sync
                actual.commit()
                console.print(t("sync_success"))

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
        run_cleanup()
    except KeyboardInterrupt:
        console.print(f"\n[yellow]{t('exiting_gracefully')}[/yellow]")
        sys.exit(0)
