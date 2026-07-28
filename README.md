# Actual Budget Transaction Categorizer (Italiano / English)

* [Versione Italiana](#actual-budget-transaction-categorizer-italiano)
* [English Version](#actual-budget-transaction-categorizer-english)

---

# Actual Budget Transaction Categorizer (Italiano)

Uno script Python interattivo per ispezionare e categorizzare le transazioni prive di categoria all'interno del tuo server autogestito **Actual Budget**.

## Caratteristiche

- **Raccomandazioni Automatiche**: Utilizza lo storico delle transazioni per suggerire la categoria ideale basandosi su: corrispondenza esatta del beneficiario, presenza del nome beneficiario nelle note/descrizione importata della banca, e corrispondenza approssimativa (fuzzy) del nome del beneficiario.
- **Prompt Interattivo**: Ti guida attraverso le transazioni una alla volta. Premi **Invio** per confermare la categoria consigliata (solitamente l'opzione `[1]`), digita un numero per selezionare un altro suggerimento, salta la transazione, crea una nuova categoria o cerca una categoria digitandone il nome.
- **Salvataggio in Blocco (Bulk Commit)**: Rivedi tutte le tue scelte in una tabella riassuntiva prima di confermare il salvataggio e sincronizzarle con il tuo server Actual Budget.
- **Configurazione Interattiva**: Ti chiede i dettagli di connessione se non sono configurati e li salva in sicurezza nel file locale `.env`.
- **Supporto Multi-lingua (i18n)**: Tradotto completamente in italiano e inglese. Rileva la lingua impostata nella variabile `ACTUAL_LANGUAGE` nel file `.env`.
- **Pulizia Beneficiari Duplicati (Cleanup Wizard)**: Trova automaticamente i beneficiari duplicati che variano solo per numeri di fattura o codici simili, ti permette di scegliere il principale (con eventuali esclusioni) e crea in automatico le regole di pre-import.
- **Rimozione Beneficiari Vuoti (Remove Empty Payees)**: Trova e rimuove in modo sicuro tutti i beneficiari che hanno 0 transazioni collegate nel budget (escludendo i conti di trasferimento).

## Prerequisiti

- **Python**: Assicurati di avere installato Python 3.10+.
- **uv**: Questo progetto utilizza `uv` per la gestione rapida del virtual environment e delle dipendenze.

## Installazione e Configurazione

1. Clona o copia questo repository sul tuo sistema.
2. Copia il file `.env.example` come `.env`:
   ```bash
   cp .env.example .env
   ```
3. Apri il file `.env` ed inserisci i tuoi dettagli:
   - `ACTUAL_SERVER_URL`: L'URL del tuo server Actual Budget (es. `http://192.168.1.100:5006`).
   - `ACTUAL_PASSWORD`: La password del tuo server.
   - `ACTUAL_BUDGET_FILE`: Il nome o il Sync ID del tuo file di budget (se lasciato vuoto, lo script mostrerà un menu con i budget disponibili).
   - `ACTUAL_ENCRYPTION_PASSWORD`: La password di crittografia end-to-end del tuo budget (lascia vuoto se non crittografato).
   - `ACTUAL_CERT`: Imposta su `False` se il tuo server autogestito utilizza un certificato SSL auto-firmato.
   - `ACTUAL_LANGUAGE`: Imposta su `it` per l'italiano o `en` per l'inglese (default: `en`).

## Utilizzo

Esegui la categorizzazione interattiva:

```bash
uv run categorize
```

Esegui la pulizia e consolidamento dei beneficiari duplicati:

```bash
uv run cleanup
```

Esegui lo script per rimuovere i beneficiari vuoti (con 0 transazioni):

```bash
uv run remove-empty-payees
```

### Comandi Interattivi (Categorizzazione)

Per ogni transazione non categorizzata, vedrai una scheda con i dettagli della transazione e le seguenti opzioni:

- **`[1], [2], [3]`**: Seleziona una delle categorie consigliate.
- **`[Invio]`**: Conferma il primo consiglio (se presente, altrimenti salta).
- **`[S]`**: Salta la transazione attuale (rimarrà non categorizzata per le prossime esecuzioni).
- **`[N]`**: Crea e assegna una nuova categoria (ti chiederà il nome ed il gruppo in cui inserirla).
- **`[A]`**: Elenca tutte le categorie disponibili raggruppate per gruppo.
- **`Qualsiasi testo`**: Digita una parola chiave (es. "spesa" o "cibo") per cercare le categorie attive. Se c'è una sola corrispondenza, ti chiederà conferma (puoi premere **Invio** per confermare). Se ce ne sono di più, mostrerà un elenco tra cui scegliere.

### Comandi Interattivi (Pulizia Beneficiari)

Per ogni gruppo di beneficiari duplicati rilevati, lo script ti guiderà attraverso le seguenti scelte:

1. **Selezione del beneficiario da mantenere**:
   - **`[1], [2], ...`**: Scegli uno dei beneficiari esistenti nel gruppo come principale.
   - **`[N]`**: Crea un nuovo beneficiario (se inserisci un nome già esistente nel budget, lo script lo rileverà e lo riutilizzerà automaticamente, evitando doppioni).
   - **`[S]`**: Salta il gruppo attuale (verrà riproposto alla prossima esecuzione).
   - **`[I]`**: Ignora sempre (salva gli ID del gruppo nel file locale `ignored_payees.json` e non te lo proporrà mai più).
   - **`[Q]`**: Esci anticipatamente (interrompe il ciclo e ti porta direttamente alla fase di salvataggio per applicare le modifiche accumulate fino a quel momento).
2. **Selezione dei beneficiari da unire**:
   - **`[Invio]`**: Unisci tutti gli altri beneficiari del gruppo in quello principale.
   - **`Numeri separati da virgole (es. 1,3)`**: Scegli quali unire, escludendo gli altri dal merge.
3. **Impostazione della regola**:
   - **`[Invio]`**: Conferma la parola chiave di default (es. `"Octopus Energy"`).
   - **`Qualsiasi testo`**: Imposta una parola chiave personalizzata per la regola di pre-importazione su Actual Budget.

---

## Anteprima da Terminale

Ecco un esempio del terminale interattivo durante l'esecuzione del tool in italiano:

```text
┌──────────────────────────────────────────────────────────┐
│ Transazione 1/2                                          │
├──────────────────────────────────────────────────────────┤
│ Data:      2026-07-20                                    │
│ Conto:     Carta Visa                                    │
│ Benefic.:  Muzzica Food                                  │
│ Importo:   -15.50                                        │
│ Note:      PAGAMENTO SU CIRCUITO INTERNAZIONALE...       │
└──────────────────────────────────────────────────────────┘

Categorie Consigliate:
  [1] Cibo & Ristoranti -> Ristoranti  (Corrispondenza esatta nome beneficiario (4/5 volte nello storico))
  [2] Cibo & Ristoranti -> Spesa       (Beneficiario 'Muzzica Food' trovato nel testo della transazione)

Opzioni:
  [S] Salta questa transazione
  [N] Crea una nuova categoria
  [A] Elenca tutte le categorie
  Oppure digita il nome o parte di una categoria per cercare

Seleziona opzione [1]: 1
[OK] Selezionato suggerimento: Ristoranti

...

=== Revisione delle Modifiche Proposte ===
┌────────────┬──────────────┬────────┬───────────────────────────┐
│ Data       │ Benefic.     │ Importo│ Categoria Assegnata       │
├────────────┼──────────────┼────────┼───────────────────────────┤
│ 2026-07-20 │ Muzzica Food │ -15.50 │ Cibo & Ristoranti -> Rist…│
└────────────┴──────────────┴────────┴───────────────────────────┘
Categorizzate: 1 transazioni, Saltate: 1 transazioni.

Sincronizzare e salvare queste modifiche sul server Actual Budget? [Y/n]: y
Salvataggio delle modifiche nel database e sincronizzazione con il server...
[Success] Transazioni categorizzate sincronizzate con successo!
```

---

# Actual Budget Transaction Categorizer (English)

An interactive Python script to inspect and categorize transactions in your self-hosted **Actual Budget** instance.

## Features

- **Automatic Recommendations**: Uses historical budget transactions to suggest categories based on exact payee matching, substring matching in notes/imported description, and fuzzy payee name matching.
- **Interactive Prompts**: Prompts you one transaction at a time. Press **Enter** to accept the default suggestion, type a number to pick another suggestion, skip, create a new category, or search for any category by typing its name.
- **Bulk Commits**: Review all your choices in a clean summary table before committing and syncing them to your home server.
- **Interactive Configuration**: Prompts you for connection details if they aren't configured and saves them securely in a local `.env` file.
- **Multi-language Support (i18n)**: Fully translated to English and Italian. Detects the language set in the `ACTUAL_LANGUAGE` environment variable.
- **Duplicate Payees Cleanup (Cleanup Wizard)**: Automatically identifies duplicate payees (e.g. variations with invoice numbers), lets you choose the main target, exclude specific entries, and programmatically generates pre-import mapping rules.
- **Empty Payees Removal (Remove Empty Payees)**: Safely identifies and deletes payees with 0 associated transactions in your budget (excluding transfer payees).

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
   - `ACTUAL_CERT`: Set to `False` if your self-hosted instance uses self-signed SSL certificates.
   - `ACTUAL_LANGUAGE`: Set to `it` for Italian or `en` for English (default: `en`).

## Usage

Run the interactive categorizer:

```bash
uv run categorize
```

Run the interactive payee cleanup wizard:

```bash
uv run cleanup
```

Run the empty payees cleanup utility (to delete payees with 0 transactions):

```bash
uv run remove-empty-payees
```

### Interactive Commands (Categorization)

For each uncategorized transaction, you will see a box with transaction details and the following options:

- **`[1], [2], [3]`**: Choose one of the suggested categories.
- **`[Enter]`**: Confirms the top suggestion (usually option `[1]` if suggestions exist, otherwise skips).
- **`[S]`**: Skip this transaction (will keep it uncategorized for future runs).
- **`[N]`**: Create and assign a new category (prompts for name and category group).
- **`[A]`**: List all available categories grouped by category group.
- **`Any text`**: Type a keyword (like "gro" or "food") to search active categories. If there is a single match, it will prompt to confirm. If there are multiple, it will show a menu to select one.

### Interactive Commands (Payee Cleanup)

For each cluster of duplicate payees detected, the script will guide you through the following prompts:

1. **Select the target payee to keep**:
   - **`[1], [2], ...`**: Choose one of the existing payees in the cluster to keep as the target.
   - **`[N]`**: Create a new payee name (if you enter a name that already exists in your budget, it will be reused automatically, avoiding duplicates).
   - **`[S]`**: Skip this cluster for now (it will be proposed again next time).
   - **`[I]`**: Ignore always (saves the cluster IDs to a local `ignored_payees.json` file and never shows it again).
   - **`[Q]`**: Quit early (stops the wizard and moves directly to the review and commit stage to save what you have done so far).
2. **Select payees to merge**:
   - **`[Enter]`**: Merge all other payees in the cluster into the target.
   - **`Comma-separated numbers (e.g. 1,3)`**: Select specific payees to merge, excluding the others.
3. **Set the rule search term**:
   - **`[Enter]`**: Confirm the default search term (e.g. `"Octopus Energy"`).
   - **`Any text`**: Enter a custom search term for the automated pre-import mapping rule.

---

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

...

=== Review Proposed Changes ===
┌────────────┬──────────────┬────────┬───────────────────────────┐
│ Date       │ Payee        │ Amount │ Assigned Category         │
├────────────┼──────────────┼────────┼───────────────────────────┤
│ 2026-07-20 │ Muzzica Food │ -15.50 │ Food & Dining -> Restaur… │
└────────────┴──────────────┴────────┴───────────────────────────┘
Categorized: 1 transactions, Skipped: 1 transactions.

Sync and commit these changes to your Actual Budget server? [Y/n]: y
Writing changes to database and syncing with server...
[Success] Successfully synchronized categorized transactions!
```
