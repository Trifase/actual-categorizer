#!/usr/bin/env python3
"""
Actual Budget Transaction Categorizer
An interactive CLI tool to inspect and categorize transactions that are missing categories.
Uses `actualpy` and `rich` for a beautiful, user-friendly interface.
"""

import os
import sys
import decimal
import datetime
import difflib
from collections import defaultdict, Counter
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich import print as rprint

from actual import Actual
from actual.queries import (
    get_transactions,
    get_categories,
    get_category_groups,
    create_category,
)

console = Console()


def load_config():
    """
    Loads connection configuration from environment or .env file.
    If details are missing, prompts the user and offers to save them.
    """
    load_dotenv()

    server_url = os.getenv("ACTUAL_SERVER_URL")
    password = os.getenv("ACTUAL_PASSWORD")
    token = os.getenv("ACTUAL_TOKEN")
    budget_file = os.getenv("ACTUAL_BUDGET_FILE")
    encryption_password = os.getenv("ACTUAL_ENCRYPTION_PASSWORD")
    cert_val = os.getenv("ACTUAL_CERT")

    # Parse cert config
    if cert_val is None:
        cert = True
    elif cert_val.strip().lower() in ("false", "0", "no"):
        cert = False
    elif cert_val.strip().lower() in ("true", "1", "yes", ""):
        cert = True
    else:
        cert = cert_val.strip()

    # If base settings are missing, interactively prompt the user
    env_file = Path(".env")
    prompted = False

    if not server_url:
        server_url = Prompt.ask(
            "[bold yellow]Actual Budget Server URL[/bold yellow]",
            default="http://localhost:5006",
        )
        prompted = True

    if not password and not token:
        login_type = Prompt.ask(
            "[bold yellow]Authenticate using[/bold yellow]",
            choices=["password", "token"],
            default="password",
        )
        if login_type == "password":
            password = Prompt.ask(
                "[bold yellow]Actual Server Password[/bold yellow]",
                password=True,
            )
        else:
            token = Prompt.ask("[bold yellow]Actual API Token[/bold yellow]")
        prompted = True

    # Save to .env if we prompted the user and they agree
    if prompted and not env_file.exists():
        if Confirm.ask(
            "[cyan]Would you like to save these connection details to a `.env` file for future runs?[/cyan]"
        ):
            with open(env_file, "w", encoding="utf-8") as f:
                f.write(f"ACTUAL_SERVER_URL={server_url}\n")
                if password:
                    f.write(f"ACTUAL_PASSWORD={password}\n")
                if token:
                    f.write(f"ACTUAL_TOKEN={token}\n")
                if budget_file:
                    f.write(f"ACTUAL_BUDGET_FILE={budget_file}\n")
                if encryption_password:
                    f.write(f"ACTUAL_ENCRYPTION_PASSWORD={encryption_password}\n")
            console.print("[green][OK] Connection details saved to `.env`.[/green]")

    return {
        "server_url": server_url,
        "password": password,
        "token": token,
        "budget_file": budget_file,
        "encryption_password": encryption_password,
        "cert": cert,
    }


def select_budget_file(config):
    """
    Connects to the server with file=None to list available files,
    allowing the user to choose one if not pre-configured.
    """
    console.print(
        "[cyan]Connecting to Actual Budget server to list available files...[/cyan]"
    )
    try:
        with Actual(
            base_url=config["server_url"],
            password=config["password"],
            token=config["token"],
            file=None,
            cert=config.get("cert", True),
        ) as actual:
            files_dto = actual.list_user_files()
            all_files = files_dto.data

            # Filter out deleted files
            active_files = [f for f in all_files if not getattr(f, "deleted", False)]

            if not active_files:
                console.print(
                    "[bold red]Error: No active budget files found on this server.[/bold red]"
                )
                sys.exit(1)

            if len(active_files) == 1:
                selected = active_files[0]
                console.print(
                    f"[green]Auto-selected the only available budget: [bold]{selected.name}[/bold][/green]"
                )
                config["budget_file"] = selected.file_id
                # Check encryption
                if getattr(selected, "encrypt_key_id", None) and not config.get(
                    "encryption_password"
                ):
                    config["encryption_password"] = Prompt.ask(
                        f"[bold yellow]Budget '{selected.name}' is encrypted. Enter budget encryption password[/bold yellow]",
                        password=True,
                    )
                return config

            # List and let user select
            table = Table(title="Available Budgets")
            table.add_column("No.", justify="right", style="cyan", no_wrap=True)
            table.add_column("Budget Name", style="magenta")
            table.add_column("Sync ID", style="dim")
            table.add_column("Encrypted?", style="yellow")

            for idx, f in enumerate(active_files, 1):
                is_enc = "Yes" if getattr(f, "encrypt_key_id", None) else "No"
                table.add_row(str(idx), f.name, f.file_id, is_enc)

            console.print(table)
            choice = Prompt.ask(
                "Select a budget file by number",
                choices=[str(i) for i in range(1, len(active_files) + 1)],
            )
            selected = active_files[int(choice) - 1]
            config["budget_file"] = selected.file_id

            if getattr(selected, "encrypt_key_id", None) and not config.get(
                "encryption_password"
            ):
                config["encryption_password"] = Prompt.ask(
                    f"[bold yellow]Budget '{selected.name}' is encrypted. Enter budget encryption password[/bold yellow]",
                    password=True,
                )

            # Ask to update .env
            env_file = Path(".env")
            if env_file.exists():
                with open(env_file, "a", encoding="utf-8") as f:
                    f.write(f"ACTUAL_BUDGET_FILE={config['budget_file']}\n")
                    if config.get("encryption_password"):
                        f.write(
                            f"ACTUAL_ENCRYPTION_PASSWORD={config['encryption_password']}\n"
                        )
                console.print(
                    "[green][OK] Budget file configuration appended to `.env`.[/green]"
                )

            return config

    except Exception as e:
        console.print(
            f"[bold red]Failed to connect or list files: {e}[/bold red]"
        )
        sys.exit(1)


def get_payee_display(t):
    """Returns a clean display name for the transaction payee."""
    if t.payee and t.payee.name:
        return t.payee.name
    if t.imported_description:
        return f"[Imported] {t.imported_description}"
    return "No Payee"


def build_suggestion_indices(categorized_txs):
    """
    Builds lookup indices from categorized transactions
    to quickly suggest categories for new transactions.
    """
    payee_id_categories = defaultdict(list)
    payee_name_categories = defaultdict(list)

    for t in categorized_txs:
        # Map payee ID to category IDs
        if t.payee_id:
            payee_id_categories[t.payee_id].append(t.category_id)
        # Map case-insensitive payee name to category IDs
        if t.payee and t.payee.name:
            payee_name_categories[t.payee.name.lower()].append(t.category_id)

    return payee_id_categories, payee_name_categories


def suggest_categories(tx, payee_id_categories, payee_name_categories, category_by_id):
    """
    Computes a score for each category based on payee matching and notes substring analysis.
    Returns a sorted list of tuples: (Category, score, reason).
    """
    suggestions = defaultdict(float)
    reasons = {}

    curr_payee_name = tx.payee.name.lower() if (tx.payee and tx.payee.name) else ""
    curr_notes = (tx.notes or "").lower()
    curr_imp = (tx.imported_description or "").lower()

    # 1. Exact Payee ID match (highest priority)
    if tx.payee_id and tx.payee_id in payee_id_categories:
        counts = Counter(payee_id_categories[tx.payee_id])
        total = sum(counts.values())
        for cat_id, cnt in counts.items():
            score = (cnt / total) * 10.0
            suggestions[cat_id] += score
            reasons[cat_id] = f"Exact payee match ({cnt}/{total} times in history)"

    # 2. Exact Payee Name match (case-insensitive)
    if curr_payee_name and curr_payee_name in payee_name_categories:
        counts = Counter(payee_name_categories[curr_payee_name])
        total = sum(counts.values())
        for cat_id, cnt in counts.items():
            score = (cnt / total) * 9.0
            suggestions[cat_id] += score
            if cat_id not in reasons or "history" not in reasons[cat_id]:
                reasons[cat_id] = f"Exact payee name match ({cnt}/{total} times in history)"

    # 3. Payee name as a substring in notes or imported description
    # This is common with raw card transaction descriptions
    for payee_name, cat_ids in payee_name_categories.items():
        if len(payee_name) >= 4:  # Avoid matching short words like "the", "bar", etc.
            if payee_name in curr_notes or payee_name in curr_imp:
                counts = Counter(cat_ids)
                total = sum(counts.values())
                for cat_id, cnt in counts.items():
                    score = (cnt / total) * 6.0
                    suggestions[cat_id] += score
                    if cat_id not in reasons:
                        reasons[cat_id] = f"Payee '{payee_name}' found in transaction text"

    # 4. Fuzzy Payee Name match
    if curr_payee_name:
        for payee_name, cat_ids in payee_name_categories.items():
            if payee_name == curr_payee_name:
                continue
            ratio = difflib.SequenceMatcher(None, curr_payee_name, payee_name).ratio()
            if ratio >= 0.7:
                counts = Counter(cat_ids)
                total = sum(counts.values())
                for cat_id, cnt in counts.items():
                    score = (cnt / total) * 5.0 * ratio
                    suggestions[cat_id] += score
                    if cat_id not in reasons:
                        reasons[cat_id] = f"Fuzzy payee match '{payee_name}' ({int(ratio*100)}% match)"

    # Sort suggestions by score descending
    sorted_suggs = sorted(suggestions.items(), key=lambda x: x[1], reverse=True)

    result = []
    for cat_id, score in sorted_suggs:
        cat = category_by_id.get(cat_id)
        if cat:
            result.append((cat, score, reasons.get(cat_id, "Similar transaction match")))

    return result


def display_categories_list(grouped_categories):
    """Prints a structured view of all active categories grouped by their group."""
    console.print("\n[bold cyan]=== Available Categories ===[/bold cyan]")
    for group_name in sorted(grouped_categories.keys()):
        console.print(f"\n[bold magenta]Group: {group_name}[/bold magenta]")
        cats = sorted(grouped_categories[group_name], key=lambda c: c.sort_order or 0)
        for c in cats:
            console.print(f"  • {c.name}")
    console.print()


def interactive_create_category(session, category_groups):
    """Interactively prompts the user to create a new category and group if needed."""
    console.print("\n[bold green]+ Creating a New Category[/bold green]")
    name = Prompt.ask("Enter new category name").strip()
    if not name:
        console.print("[red]Category name cannot be empty.[/red]")
        return None

    # Get active groups
    groups = [g for g in category_groups if not g.tombstone]
    groups.sort(key=lambda g: g.name or "")

    table = Table(title="Select Category Group")
    table.add_column("No.", justify="right", style="cyan", no_wrap=True)
    table.add_column("Group Name", style="magenta")

    for i, g in enumerate(groups, 1):
        table.add_row(str(i), g.name)
    # Add option to create a new group
    table.add_row("N", "[bold green]+ Create a new group[/bold green]")

    console.print(table)
    choice = Prompt.ask(
        "Select group by number or 'N' for a new group",
        choices=[str(i) for i in range(1, len(groups) + 1)] + ["n", "N"],
    )

    if choice.upper() == "N":
        group_name = Prompt.ask("Enter name for the new category group").strip()
        if not group_name:
            console.print("[red]Group name cannot be empty. Aborting creation.[/red]")
            return None
    else:
        group_name = groups[int(choice) - 1].name

    try:
        new_cat = create_category(session, name=name, group_name=group_name)
        console.print(
            f"[green][OK] Created category [bold]{name}[/bold] in group [bold]{group_name}[/bold][/green]"
        )
        return new_cat
    except Exception as e:
        console.print(f"[red]Error creating category: {e}[/red]")
        return None


def run_categorization():
    config = load_config()

    if not config.get("budget_file"):
        config = select_budget_file(config)

    console.print(
        f"[cyan]Connecting and downloading budget file [bold]{config['budget_file']}[/bold]...[/cyan]"
    )

    try:
        with Actual(
            base_url=config["server_url"],
            password=config["password"],
            token=config["token"],
            file=config["budget_file"],
            encryption_password=config.get("encryption_password"),
            cert=config.get("cert", True),
        ) as actual:

            # Retrieve active category lookup
            categories = get_categories(actual.session)
            category_groups = get_category_groups(actual.session)
            category_by_id = {c.id: c for c in categories if not c.tombstone}

            # Group active categories by group name for presentation
            grouped_categories = defaultdict(list)
            for c in categories:
                if c.tombstone or c.hidden:
                    continue
                group_name = c.group.name if c.group else "Usual Expenses"
                grouped_categories[group_name].append(c)

            # Retrieve all transactions
            console.print("[cyan]Analyzing transactions...[/cyan]")
            all_txs = get_transactions(actual.session)

            # Filter categorized vs uncategorized
            categorized_txs = []
            uncategorized_txs = []

            for t in all_txs:
                if t.tombstone:
                    continue
                # Exclude parent transactions (only hold splits, which are child transactions)
                if t.is_parent:
                    continue
                # Exclude transfers
                if t.transferred_id is not None:
                    continue
                # Exclude starting balances
                if t.starting_balance_flag:
                    continue
                # Exclude transactions in off-budget accounts
                if t.account and t.account.offbudget:
                    continue

                if t.category_id is not None:
                    categorized_txs.append(t)
                else:
                    uncategorized_txs.append(t)

            if not uncategorized_txs:
                console.print(
                    "[bold green][OK] All transactions are already categorized! Nothing to do.[/bold green]"
                )
                return

            console.print(
                f"[yellow]Found {len(uncategorized_txs)} uncategorized transactions.[/yellow]"
            )

            # Sort chronologically (oldest first)
            uncategorized_txs.sort(key=lambda t: t.date or 0)

            # Build suggestion indexes
            payee_id_categories, payee_name_categories = build_suggestion_indices(
                categorized_txs
            )

            # Keep track of local changes before committing
            changes = []  # List of tuples: (transaction, selected_category)
            skipped_count = 0

            # Loop through uncategorized transactions
            for idx, tx in enumerate(uncategorized_txs, 1):
                # Format transaction details
                try:
                    date_str = tx.get_date().strftime("%Y-%m-%d")
                except Exception:
                    date_str = str(tx.date)

                amount_decimal = tx.get_amount()
                amount_str = f"{amount_decimal:,.2f}"

                # Red for expenses, green for income
                amount_color = "red" if amount_decimal < 0 else "green"

                payee_str = get_payee_display(tx)
                notes_str = tx.notes or tx.imported_description or ""
                account_str = tx.account.name if tx.account else "Unknown"

                # Compute category suggestions
                suggs = suggest_categories(
                    tx,
                    payee_id_categories,
                    payee_name_categories,
                    category_by_id,
                )

                # Show transaction card
                tx_info = Text()
                tx_info.append(f"Date:    {date_str}\n", style="bold white")
                tx_info.append(f"Account: {account_str}\n", style="bold blue")
                tx_info.append(f"Payee:   {payee_str}\n", style="bold yellow")
                tx_info.append("Amount:  ", style="bold white")
                tx_info.append(amount_str + "\n", style=f"bold {amount_color}")
                tx_info.append(f"Notes:   {notes_str}", style="dim white")

                console.print()
                panel = Panel(
                    tx_info,
                    title=f"[cyan]Transaction {idx}/{len(uncategorized_txs)}[/cyan]",
                    border_style="cyan",
                    expand=False,
                )
                console.print(panel)

                # Prepare options
                # Default option is the first suggestion if available
                default_choice = "s"
                if suggs:
                    default_choice = "1"
                    console.print("[bold cyan]Suggested Categories:[/bold cyan]")
                    # List top suggestions
                    limit = min(3, len(suggs))
                    for s_idx in range(limit):
                        cat, score, reason = suggs[s_idx]
                        grp_name = cat.group.name if cat.group else "Usual Expenses"
                        console.print(
                            f"  [bold green][{s_idx + 1}][/bold green] {grp_name} -> {cat.name}  "
                            f"[dim]({reason})[/dim]"
                        )
                else:
                    console.print("[dim yellow]No historical suggestions found.[/dim yellow]")

                console.print("[bold white]Options:[/bold white]")
                console.print("  [bold green][S][/bold green] Skip this transaction")
                console.print("  [bold green][N][/bold green] Create a new category")
                console.print("  [bold green][A][/bold green] List all categories")
                console.print("  Or type a category name or fragment to search")

                # Prompt loop
                while True:
                    prompt_msg = "Select option"
                    if suggs:
                        prompt_msg += " [1]"

                    user_input = Prompt.ask(prompt_msg, default=default_choice).strip()

                    # Handle suggestions selection
                    if user_input.isdigit():
                        opt = int(user_input)
                        if suggs and 1 <= opt <= len(suggs):
                            selected_cat = suggs[opt - 1][0]
                            changes.append((tx, selected_cat))
                            console.print(
                                f"[green][OK] Selected suggestion: [bold]{selected_cat.name}[/bold][/green]"
                            )
                            break
                        else:
                            console.print(
                                f"[red]Invalid suggestion number. Please choose between 1 and {len(suggs)}.[/red]"
                            )
                            continue

                    user_input_upper = user_input.upper()

                    # Handle Skip
                    if user_input_upper == "S":
                        console.print("[yellow]Skipping transaction...[/yellow]")
                        skipped_count += 1
                        break

                    # Handle Create New Category
                    if user_input_upper == "N":
                        # We need to refresh the categories list if new categories are created
                        new_cat = interactive_create_category(
                            actual.session, category_groups
                        )
                        if new_cat:
                            changes.append((tx, new_cat))
                            # Add to local cache
                            category_by_id[new_cat.id] = new_cat
                            group_name = (
                                new_cat.group.name
                                if new_cat.group
                                else "Usual Expenses"
                            )
                            grouped_categories[group_name].append(new_cat)
                            break
                        else:
                            continue

                    # Handle List All Categories
                    if user_input_upper == "A":
                        display_categories_list(grouped_categories)
                        continue

                    # Handle text search
                    query = user_input.lower()
                    matches = []
                    for c in categories:
                        if c.tombstone or c.hidden:
                            continue
                        if query in c.name.lower():
                            matches.append(c)

                    if not matches:
                        console.print(
                            f"[red]No category matching '{user_input}' found. Try again.[/red]"
                        )
                        continue

                    if len(matches) == 1:
                        matched_cat = matches[0]
                        grp_name = (
                            matched_cat.group.name
                            if matched_cat.group
                            else "Usual Expenses"
                        )
                        if Confirm.ask(
                            f"Confirm selecting [bold cyan]{grp_name} -> {matched_cat.name}[/bold cyan]?",
                            default=True,
                        ):
                            changes.append((tx, matched_cat))
                            console.print(
                                f"[green][OK] Assigned category: [bold]{matched_cat.name}[/bold][/green]"
                            )
                            break
                        else:
                            continue
                    else:
                        console.print(
                            f"[yellow]Multiple matches found for '{user_input}':[/yellow]"
                        )
                        for m_idx, m_cat in enumerate(matches, 1):
                            m_grp = (
                                m_cat.group.name if m_cat.group else "Usual Expenses"
                            )
                            console.print(f"  [{m_idx}] {m_grp} -> {m_cat.name}")

                        sub_choice = Prompt.ask(
                            "Select match by number or press Enter to cancel",
                            choices=[str(i) for i in range(1, len(matches) + 1)]
                            + [""],
                            default="",
                        )
                        if sub_choice:
                            selected_cat = matches[int(sub_choice) - 1]
                            changes.append((tx, selected_cat))
                            console.print(
                                f"[green][OK] Selected category: [bold]{selected_cat.name}[/bold][/green]"
                            )
                            break
                        else:
                            continue

            # End of loop: Review Changes
            if not changes:
                console.print("\n[yellow]No changes were made.[/yellow]")
                return

            console.print("\n[bold cyan]=== Review Proposed Changes ===[/bold cyan]")
            review_table = Table()
            review_table.add_column("Date", style="dim")
            review_table.add_column("Payee", style="yellow")
            review_table.add_column("Amount", justify="right")
            review_table.add_column("Assigned Category", style="bold green")

            for tx, cat in changes:
                try:
                    d_str = tx.get_date().strftime("%Y-%m-%d")
                except Exception:
                    d_str = str(tx.date)
                a_dec = tx.get_amount()
                a_color = "red" if a_dec < 0 else "green"
                a_str = f"[{a_color}]{a_dec:,.2f}[/{a_color}]"

                grp_name = cat.group.name if cat.group else "Usual Expenses"
                review_table.add_row(
                    d_str,
                    get_payee_display(tx),
                    a_str,
                    f"{grp_name} -> {cat.name}",
                )

            console.print(review_table)
            console.print(
                f"[yellow]Categorized: {len(changes)} transactions, Skipped: {skipped_count} transactions.[/yellow]"
            )

            if Confirm.ask(
                "[bold cyan]Sync and commit these changes to your Actual Budget server?[/bold cyan]",
                default=True,
            ):
                console.print(
                    "[cyan]Writing changes to database and syncing with server...[/cyan]"
                )
                for tx, cat in changes:
                    tx.category_id = cat.id

                # Save and Sync
                actual.commit()
                console.print(
                    "[bold green][Success] Successfully synchronized categorized transactions![/bold green]"
                )
            else:
                console.print("[yellow]Changes discarded.[/yellow]")

    except Exception as e:
        console.print(
            f"[bold red]An error occurred during execution: {e}[/bold red]"
        )
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    try:
        run_categorization()
    except KeyboardInterrupt:
        console.print("\n[yellow]Exiting gracefully...[/yellow]")
        sys.exit(0)
