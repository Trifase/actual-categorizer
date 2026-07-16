#!/usr/bin/env python3
"""
Actual Budget Transaction Categorizer
An interactive CLI tool to inspect and categorize transactions that are missing categories.
Uses `actualpy` and `rich` for a beautiful, user-friendly interface.
Supports internationalization via locales.
"""

import os
import sys
import json
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

# Load environment variables immediately so ACTUAL_LANGUAGE is available
load_dotenv()

console = Console()

# Fallback translations if locales/en.json is not found
_fallback_en = {
    "connection_url_prompt": "Actual Budget Server URL",
    "connection_auth_prompt": "Authenticate using",
    "connection_pwd_prompt": "Actual Server Password",
    "connection_token_prompt": "Actual API Token",
    "save_env_prompt": "Would you like to save these connection details to a `.env` file for future runs?",
    "env_saved": "[green][OK] Connection details saved to `.env`.[/green]",
    "connecting_list": "[cyan]Connecting to Actual Budget server to list available files...[/cyan]",
    "err_no_budgets": "[bold red]Error: No active budget files found on this server.[/bold red]",
    "auto_selected_budget": "[green][OK] Auto-selected the only available budget: [bold]{name}[/bold][/green]",
    "budget_encrypted_prompt": "Budget '{name}' is encrypted. Enter budget encryption password",
    "available_budgets_title": "Available Budgets",
    "col_no": "No.",
    "col_budget_name": "Budget Name",
    "col_sync_id": "Sync ID",
    "col_encrypted": "Encrypted?",
    "select_budget_prompt": "Select a budget file by number",
    "env_appended": "[green][OK] Budget file configuration appended to `.env`.[/green]",
    "err_connect_failed": "[bold red]Failed to connect or list files: {err}[/bold red]",
    "connecting_download": "[cyan]Connecting and downloading budget file [bold]{file}[/bold]...[/cyan]",
    "analyzing_txs": "[cyan]Analyzing transactions...[/cyan]",
    "all_categorized": "[bold green][OK] All transactions are already categorized! Nothing to do.[/bold green]",
    "found_uncategorized": "[yellow]Found {count} uncategorized transactions.[/yellow]",
    "label_date": "Date:    ",
    "label_account": "Account: ",
    "label_payee": "Payee:   ",
    "label_amount": "Amount:  ",
    "label_notes": "Notes:   ",
    "suggested_categories_title": "Suggested Categories:",
    "no_suggestions": "[dim yellow]No historical suggestions found.[/dim yellow]",
    "options_title": "Options:",
    "opt_skip": "Skip this transaction",
    "opt_new": "Create a new category",
    "opt_all": "List all categories",
    "opt_search_help": "Or type a category name or fragment to search",
    "prompt_select_option": "Select option",
    "err_invalid_sugg_no": "[red]Invalid suggestion number. Please choose between 1 and {max}.[/red]",
    "skipping_tx": "[yellow]Skipping transaction...[/yellow]",
    "display_categories_title": "=== Available Categories ===",
    "group_prefix": "Group: ",
    "create_cat_title": "+ Creating a New Category",
    "create_cat_name_prompt": "Enter new category name",
    "err_empty_cat_name": "[red]Category name cannot be empty.[/red]",
    "select_cat_group_title": "Select Category Group",
    "col_group_name": "Group Name",
    "opt_create_new_group": "+ Create a new group",
    "select_group_prompt": "Select group by number or 'N' for a new group",
    "create_group_name_prompt": "Enter name for the new category group",
    "err_empty_group_name": "[red]Group name cannot be empty. Aborting creation.[/red]",
    "cat_created_success": "[green][OK] Created category [bold]{name}[/bold] in group [bold]{group_name}[/bold][/green]",
    "err_create_cat_failed": "[red]Error creating category: {err}[/red]",
    "err_no_cat_match": "[red]No category matching '{query}' found. Try again.[/red]",
    "confirm_cat_selection": "Confirm selecting [bold cyan]{group} -> {category}[/bold cyan]?",
    "multiple_matches_title": "Multiple matches found for '{query}':",
    "select_match_prompt": "Select match by number or press Enter to cancel",
    "no_changes_made": "[yellow]No changes were made.[/yellow]",
    "review_changes_title": "=== Review Proposed Changes ===",
    "col_assigned_cat": "Assigned Category",
    "summary_counts": "[yellow]Categorized: {changes_count} transactions, Skipped: {skipped_count} transactions.[/yellow]",
    "confirm_commit_prompt": "Sync and commit these changes to your Actual Budget server?",
    "writing_changes": "[cyan]Writing changes to database and syncing with server...[/cyan]",
    "sync_success": "[bold green][Success] Successfully synchronized categorized transactions![/bold green]",
    "changes_discarded": "[yellow]Changes discarded.[/yellow]",
    "exiting_gracefully": "Exiting gracefully...",
    "reason_exact_payee_id": "Exact payee match ({cnt}/{total} times in history)",
    "reason_exact_payee_name": "Exact payee name match ({cnt}/{total} times in history)",
    "reason_payee_found_text": "Payee '{payee}' found in transaction text",
    "reason_fuzzy_payee_match": "Fuzzy payee match '{payee}' ({ratio}% match)",
    "reason_similar_tx": "Similar transaction match"
}

_translations = {}


def load_translations():
    """Loads translations from locales/ directory based on ACTUAL_LANGUAGE env variable."""
    global _translations
    lang = os.getenv("ACTUAL_LANGUAGE", "en").strip().lower()

    locales_dir = Path(__file__).parent / "locales"
    lang_file = locales_dir / f"{lang}.json"

    # Try loading selected language
    if lang_file.exists():
        try:
            with open(lang_file, "r", encoding="utf-8") as f:
                _translations = json.load(f)
        except Exception:
            pass

    # Try fallback to en.json if empty
    if not _translations and lang != "en":
        en_file = locales_dir / "en.json"
        if en_file.exists():
            try:
                with open(en_file, "r", encoding="utf-8") as f:
                    _translations = json.load(f)
            except Exception:
                pass


def t(key, **kwargs):
    """Retrieves translation for the key, formatting it with kwargs if needed."""
    val = _translations.get(key, _fallback_en.get(key, key))
    if kwargs:
        try:
            return val.format(**kwargs)
        except Exception:
            return val
    return val


# Initial translation load
load_translations()


def load_config():
    """
    Loads connection configuration from environment or .env file.
    If details are missing, prompts the user and offers to save them.
    """
    # Note: load_dotenv() is already run at the module level
    server_url = os.getenv("ACTUAL_SERVER_URL")
    password = os.getenv("ACTUAL_PASSWORD")
    token = os.getenv("ACTUAL_TOKEN")
    budget_file = os.getenv("ACTUAL_BUDGET_FILE")
    encryption_password = os.getenv("ACTUAL_ENCRYPTION_PASSWORD")
    cert_val = os.getenv("ACTUAL_CERT")
    lang_val = os.getenv("ACTUAL_LANGUAGE", "en")

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
            f"[bold yellow]{t('connection_url_prompt')}[/bold yellow]",
            default="http://localhost:5006",
        )
        prompted = True

    if not password and not token:
        login_type = Prompt.ask(
            f"[bold yellow]{t('connection_auth_prompt')}[/bold yellow]",
            choices=["password", "token"],
            default="password",
        )
        if login_type == "password":
            password = Prompt.ask(
                f"[bold yellow]{t('connection_pwd_prompt')}[/bold yellow]",
                password=True,
            )
        else:
            token = Prompt.ask(f"[bold yellow]{t('connection_token_prompt')}[/bold yellow]")
        prompted = True

    # Save to .env if we prompted the user and they agree
    if prompted and not env_file.exists():
        if Confirm.ask(
            f"[cyan]{t('save_env_prompt')}[/cyan]"
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
                f.write(f"ACTUAL_LANGUAGE={lang_val}\n")
            console.print(t("env_saved"))

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
    console.print(t("connecting_list"))
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
                console.print(t("err_no_budgets"))
                sys.exit(1)

            if len(active_files) == 1:
                selected = active_files[0]
                console.print(t("auto_selected_budget", name=selected.name))
                config["budget_file"] = selected.file_id
                # Check encryption
                if getattr(selected, "encrypt_key_id", None) and not config.get(
                    "encryption_password"
                ):
                    config["encryption_password"] = Prompt.ask(
                        f"[bold yellow]{t('budget_encrypted_prompt', name=selected.name)}[/bold yellow]",
                        password=True,
                    )
                return config

            # List and let user select
            table = Table(title=t("available_budgets_title"))
            table.add_column(t("col_no"), justify="right", style="cyan", no_wrap=True)
            table.add_column(t("col_budget_name"), style="magenta")
            table.add_column(t("col_sync_id"), style="dim")
            table.add_column(t("col_encrypted"), style="yellow")

            for idx, f in enumerate(active_files, 1):
                is_enc = "Yes" if getattr(f, "encrypt_key_id", None) else "No"
                table.add_row(str(idx), f.name, f.file_id, is_enc)

            console.print(table)
            choice = Prompt.ask(
                t("select_budget_prompt"),
                choices=[str(i) for i in range(1, len(active_files) + 1)],
            )
            selected = active_files[int(choice) - 1]
            config["budget_file"] = selected.file_id

            if getattr(selected, "encrypt_key_id", None) and not config.get(
                "encryption_password"
            ):
                config["encryption_password"] = Prompt.ask(
                    f"[bold yellow]{t('budget_encrypted_prompt', name=selected.name)}[/bold yellow]",
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
                console.print(t("env_appended"))

            return config

    except Exception as e:
        console.print(t("err_connect_failed", err=e))
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
            reasons[cat_id] = t("reason_exact_payee_id", cnt=cnt, total=total)

    # 2. Exact Payee Name match (case-insensitive)
    if curr_payee_name and curr_payee_name in payee_name_categories:
        counts = Counter(payee_name_categories[curr_payee_name])
        total = sum(counts.values())
        for cat_id, cnt in counts.items():
            score = (cnt / total) * 9.0
            suggestions[cat_id] += score
            if cat_id not in reasons or "history" not in reasons[cat_id]:
                reasons[cat_id] = t("reason_exact_payee_name", cnt=cnt, total=total)

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
                        reasons[cat_id] = t("reason_payee_found_text", payee=payee_name)

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
                        reasons[cat_id] = t("reason_fuzzy_payee_match", payee=payee_name, ratio=int(ratio * 100))

    # Sort suggestions by score descending
    sorted_suggs = sorted(suggestions.items(), key=lambda x: x[1], reverse=True)

    result = []
    for cat_id, score in sorted_suggs:
        cat = category_by_id.get(cat_id)
        if cat:
            result.append((cat, score, reasons.get(cat_id, t("reason_similar_tx"))))

    return result


def display_categories_list(grouped_categories):
    """Prints a structured view of all active categories grouped by their group."""
    console.print(f"\n[bold cyan]{t('display_categories_title')}[/bold cyan]")
    for group_name in sorted(grouped_categories.keys()):
        console.print(f"\n[bold magenta]{t('group_prefix')}{group_name}[/bold magenta]")
        cats = sorted(grouped_categories[group_name], key=lambda c: c.sort_order or 0)
        for c in cats:
            console.print(f"  • {c.name}")
    console.print()


def interactive_create_category(session, category_groups):
    """Interactively prompts the user to create a new category and group if needed."""
    console.print(f"\n[bold green]{t('create_cat_title')}[/bold green]")
    name = Prompt.ask(t("create_cat_name_prompt")).strip()
    if not name:
        console.print(t("err_empty_cat_name"))
        return None

    # Get active groups
    groups = [g for g in category_groups if not g.tombstone]
    groups.sort(key=lambda g: g.name or "")

    table = Table(title=t("select_cat_group_title"))
    table.add_column(t("col_no"), justify="right", style="cyan", no_wrap=True)
    table.add_column(t("col_group_name"), style="magenta")

    for i, g in enumerate(groups, 1):
        table.add_row(str(i), g.name)
    # Add option to create a new group
    table.add_row("N", f"[bold green]{t('opt_create_new_group')}[/bold green]")

    console.print(table)
    choice = Prompt.ask(
        t("select_group_prompt"),
        choices=[str(i) for i in range(1, len(groups) + 1)] + ["n", "N"],
    )

    if choice.upper() == "N":
        group_name = Prompt.ask(t("create_group_name_prompt")).strip()
        if not group_name:
            console.print(t("err_empty_group_name"))
            return None
    else:
        group_name = groups[int(choice) - 1].name

    try:
        new_cat = create_category(session, name=name, group_name=group_name)
        console.print(t("cat_created_success", name=name, group_name=group_name))
        return new_cat
    except Exception as e:
        console.print(t("err_create_cat_failed", err=e))
        return None


def run_categorization():
    config = load_config()

    if not config.get("budget_file"):
        config = select_budget_file(config)

    console.print(t("connecting_download", file=config['budget_file']))

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
            console.print(t("analyzing_txs"))
            all_txs = get_transactions(actual.session)

            # Filter categorized vs uncategorized
            categorized_txs = []
            uncategorized_txs = []

            for t_item in all_txs:
                if t_item.tombstone:
                    continue
                # Exclude parent transactions (only hold splits, which are child transactions)
                if t_item.is_parent:
                    continue
                # Exclude transfers
                if t_item.transferred_id is not None:
                    continue
                # Exclude starting balances
                if t_item.starting_balance_flag:
                    continue
                # Exclude transactions in off-budget accounts
                if t_item.account and t_item.account.offbudget:
                    continue

                if t_item.category_id is not None:
                    categorized_txs.append(t_item)
                else:
                    uncategorized_txs.append(t_item)

            if not uncategorized_txs:
                console.print(t("all_categorized"))
                return

            console.print(t("found_uncategorized", count=len(uncategorized_txs)))

            # Sort chronologically (oldest first)
            uncategorized_txs.sort(key=lambda x: x.date or 0)

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
                tx_info.append(t("label_date") + date_str + "\n", style="bold white")
                tx_info.append(t("label_account") + account_str + "\n", style="bold blue")
                tx_info.append(t("label_payee") + payee_str + "\n", style="bold yellow")
                tx_info.append(t("label_amount"), style="bold white")
                tx_info.append(amount_str + "\n", style=f"bold {amount_color}")
                tx_info.append(t("label_notes") + notes_str, style="dim white")

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
                    console.print(f"[bold cyan]{t('suggested_categories_title')}[/bold cyan]")
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
                    console.print(t("no_suggestions"))

                console.print(f"[bold white]{t('options_title')}[/bold white]")
                console.print(f"  [bold green][S][/bold green] {t('opt_skip')}")
                console.print(f"  [bold green][N][/bold green] {t('opt_new')}")
                console.print(f"  [bold green][A][/bold green] {t('opt_all')}")
                console.print(f"  {t('opt_search_help')}")

                # Prompt loop
                while True:
                    prompt_msg = t("prompt_select_option")
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
                            console.print(t("err_invalid_sugg_no", max=len(suggs)))
                            continue

                    user_input_upper = user_input.upper()

                    # Handle Skip
                    if user_input_upper == "S":
                        console.print(t("skipping_tx"))
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
                        console.print(t("err_no_cat_match", query=user_input))
                        continue

                    if len(matches) == 1:
                        matched_cat = matches[0]
                        grp_name = (
                            matched_cat.group.name
                            if matched_cat.group
                            else "Usual Expenses"
                        )
                        if Confirm.ask(
                            t("confirm_cat_selection", group=grp_name, category=matched_cat.name),
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
                        console.print(t("multiple_matches_title", query=user_input))
                        for m_idx, m_cat in enumerate(matches, 1):
                            m_grp = (
                                m_cat.group.name if m_cat.group else "Usual Expenses"
                            )
                            console.print(f"  [{m_idx}] {m_grp} -> {m_cat.name}")

                        sub_choice = Prompt.ask(
                            t("select_match_prompt"),
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
                console.print(t("no_changes_made"))
                return

            console.print(f"\n[bold cyan]{t('review_changes_title')}[/bold cyan]")
            review_table = Table()
            review_table.add_column(t("label_date").strip(), style="dim")
            review_table.add_column(t("label_payee").strip(), style="yellow")
            review_table.add_column(t("label_amount").strip(), justify="right")
            review_table.add_column(t("col_assigned_cat"), style="bold green")

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
            console.print(t("summary_counts", changes_count=len(changes), skipped_count=skipped_count))

            if Confirm.ask(
                f"[bold cyan]{t('confirm_commit_prompt')}[/bold cyan]",
                default=True,
            ):
                console.print(t("writing_changes"))
                for tx, cat in changes:
                    tx.category_id = cat.id

                # Save and Sync
                actual.commit()
                console.print(t("sync_success"))
            else:
                console.print(t("changes_discarded"))

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
        console.print(f"\n[yellow]{t('exiting_gracefully')}[/yellow]")
        sys.exit(0)
