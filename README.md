# Actual Budget Transaction Categorizer

An interactive Python script to inspect and categorize transactions in your self-hosted **Actual Budget** instance.

## Features

- **Automatic Recommendations**: Uses historical budget transactions to suggest categories based on exact payee matching, substring matching in notes/imported description, and fuzzy payee name matching.
- **Interactive Prompts**: Prompts you one transaction at a time. Press **Enter** to accept the default suggestion, type a number to pick another suggestion, skip, create a new category, or search for any category by typing its name.
- **Bulk Commits**: Review all your choices in a clean summary table before committing and syncing them to your home server.
- **Interactive Configuration**: Prompts you for connection details if they aren't configured and saves them securely in a local `.env` file.

## Prerequisites

- **Python**: Ensure Python 3.10+ is installed.
- **uv**: This project uses `uv` for lightning-fast dependency and virtual environment management.

## Setup

1. Clone or copy this repository to your system.
2. Copy the `.env.example` file to `.env`:
   ```bash
   cp .env.example .env
   ```
3. Open `.env` in a text editor and fill in your details:
   - `ACTUAL_SERVER_URL`: The URL of your Actual Budget server (e.g. `http://192.168.1.100:5006`).
   - `ACTUAL_PASSWORD`: Your password.
   - `ACTUAL_BUDGET_FILE`: Your budget file name or Sync ID (if left blank, the script will show a menu to choose from).
   - `ACTUAL_ENCRYPTION_PASSWORD`: Your budget file's encryption password (leave blank if not encrypted).

## Usage

Run the script using `uv`:

```bash
uv run categorize
```

### Interactive Commands

For each uncategorized transaction, you will see a box with transaction details and the following options:

- **`[1], [2], [3]`**: Choose one of the suggested categories.
- **`[Enter]`**: Confirms the top suggestion (usually option `[1]` if suggestions exist, otherwise skips).
- **`[S]`**: Skip this transaction (will keep it uncategorized for future runs).
- **`[N]`**: Create and assign a new category (prompts for name and category group).
- **`[A]`**: List all available categories grouped by category group.
- **`Any text`**: Type a keyword (like "gro" or "food") to search active categories. If there is a single match, it will prompt to confirm. If there are multiple, it will show a menu to select one.

## Interactive Console Preview

Here is an example of what the interactive CLI looks like when running the script:

```text
┌──────────────────────────────────────────────────────────┐
│ Transaction 1/2                                          │
├──────────────────────────────────────────────────────────┤
│ Date:    2026-07-20                                      │
│ Account: Visa Card                                       │
│ Payee:   Muzzica Food                                    │
│ Amount:  -15.50                                          │
│ Notes:   PAGAMENTO SU CIRCUITO INTERNAZIONALE...         │
└──────────────────────────────────────────────────────────┘

Suggested Categories:
  [1] Food & Dining -> Restaurants  (Exact payee name match (4/5 times in history))
  [2] Food & Dining -> Groceries    (Payee 'Muzzica Food' found in transaction text)

Options:
  [S] Skip this transaction
  [N] Create a new category
  [A] List all categories
  Or type a category name or fragment to search

Select option [1]: 1
[OK] Selected suggestion: Restaurants

┌──────────────────────────────────────────────────────────┐
│ Transaction 2/2                                          │
├──────────────────────────────────────────────────────────┤
│ Date:    2026-07-21                                      │
│ Account: Main Checking                                   │
│ Payee:   [Imported] Enel Energia S.p.A.                  │
│ Amount:  -85.30                                          │
│ Notes:   BOLLETTA LUCE GIUGNO 2026                       │
└──────────────────────────────────────────────────────────┘

Suggested Categories:
  [1] Housing -> Electricity  (Fuzzy payee match 'Enel Luce' (85% match))

Options:
  [S] Skip this transaction
  [N] Create a new category
  [A] List all categories
  Or type a category name or fragment to search

Select option [1]: s
Skipping transaction...

=== Review Proposed Changes ===
┌────────────┬──────────────┬────────┬───────────────────────────┐
│ Date       │ Payee        │ Amount │ Assigned Category         │
├────────────┼──────────────┼────────┼───────────────────────────┘
│ 2026-07-20 │ Muzzica Food │ -15.50 │ Food & Dining -> Restaur… │
└────────────┴──────────────┴────────┴───────────────────────────┘
Categorized: 1 transactions, Skipped: 1 transactions.

Sync and commit these changes to your Actual Budget server? [Y/n]: y
Writing changes to database and syncing with server...
[Success] Successfully synchronized categorized transactions!
```
