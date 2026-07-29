# Actual Budget Utils (Italiano / English)

* [Versione Italiana](#actual-budget-utils-italiano)
* [English Version](#actual-budget-utils-english)

---

# Actual Budget Utils (Italiano)

**Actual Budget Utils** è una collezione di strumenti interattivi da riga di comando (CLI) progettata per pulire, organizzare e automatizzare la gestione del tuo server autogestito **Actual Budget**. 

Tutti gli strumenti sono accessibili tramite un pratico menu centralizzato lanciando:
```bash
uv run actualutils
```

Tutti gli strumenti eseguono automaticamente un backup del database locale (`db.sqlite.backup`) prima di apportare modifiche e lo ripristinano in caso di errore o annullamento, garantendo la massima sicurezza dei tuoi dati.

---

## Utility Disponibili

### 1. Categorizzazione Transazioni (Transaction Categorizer)
Ti aiuta a ispezionare e assegnare rapidamente una categoria a tutte le transazioni che ne sono prive:
- **Suggerimenti Intelligenti**: Analizza lo storico del budget e consiglia le categorie migliori basandosi su: corrispondenza esatta del beneficiario, presenza del nome del beneficiario nelle note/descrizione importata della banca, o corrispondenza fuzzy (approssimativa).
- **Prompt Interattivo**: Scorri le transazioni una alla volta. Premi **Invio** per accettare il primo consiglio consigliato, digita un numero per selezionare un altro suggerimento, inserisci del testo per cercare tra le categorie attive, o crea una nuova categoria/gruppo sul momento.
- **Salvataggio in Blocco (Bulk Commit)**: Rivedi tutte le modifiche in una tabella riassuntiva prima di sincronizzarle con il server.

### 2. Pulizia Beneficiari Duplicati (Payee Cleanup Wizard)
Consolida e pulisce l'elenco dei beneficiari nel tuo budget:
- **Clustering Automatico**: Raggruppa i beneficiari simili che differiscono solo per codici, date o numeri di fattura (es. "Coop Spesa N.123" e "Coop Spesa N.456").
- **Unione Sicura**: Ti permette di scegliere quale beneficiario mantenere come principale, decidere quali duplicati unire (con opzione di escludere singoli elementi) e aggiorna automaticamente tutte le transazioni collegate.
- **Regole Automatiche**: Crea in automatico regole di pre-importazione su Actual Budget per mappare le transazioni future direttamente sul beneficiario principale.
- **Ignora Persistente**: Ti permette di saltare e ignorare permanentemente specifici gruppi tramite il file locale `ignored_payees.json` premendo l'opzione `I`.

### 3. Rimozione Beneficiari Vuoti (Remove Empty Payees)
Pulisce l'elenco dei beneficiari eliminando i record non utilizzati:
- **Analisi Transazioni**: Trova tutti i beneficiari attivi che hanno esattamente `0` transazioni collegate nel budget.
- **Protezione Giroconti**: Esclude automaticamente tutti i beneficiari di trasferimento/giroconto del sistema per evitare malfunzionamenti.
- **Rimozione in Blocco**: Elenca i beneficiari trovati e li elimina in sicurezza solo dopo la tua conferma.

### 4. Gestione e Pulizia Regole (Rules Manager)
Fornisce un pannello per ispezionare e ripulire le regole del budget:
- **Risoluzione UUID**: Mostra le regole in modo leggibile sostituendo i codici UUID interni con i nomi reali di beneficiari, categorie e conti.
- **Rilevamento Duplicati**: Trova regole identiche (stesse condizioni e azioni) per eliminarle lasciandone solo una.
- **Regole Ridondanti**: Rileva se ci sono regole sovrapposte o ridondanti (es. una regola per `"Octopus"` e una per `"Octopus Energy"` che puntano allo stesso beneficiario) suggerendone l'eliminazione.
- **Eliminazione Singole Regole**: Consente di rimuovere singole regole o più regole contemporaneamente indicandone l'indice.

---

## Prerequisiti
- **Python**: Assicurati di avere installato Python 3.10+.
- **uv**: Questo progetto utilizza `uv` per la gestione rapida del virtual environment e delle dipendenze.

## Installazione e Configurazione
1. Clona questo repository sul tuo sistema.
2. Copia il file `.env.example` come `.env`:
   ```bash
   cp .env.example .env
   ```
3. Compila le variabili di connessione nel file `.env`:
   - `ACTUAL_SERVER_URL`: URL del tuo server Actual Budget (es. `https://budget.tuodominio.it`).
   - `ACTUAL_PASSWORD`: Password per accedere al server.
   - `ACTUAL_SYNC_ID`: Il file sync ID del tuo budget (opzionale, se omesso lo script ti mostrerà un elenco per sceglierlo).
   - `ACTUAL_ENCRYPTION_PASSWORD`: Password di crittografia (lascia vuoto se non attiva).
   - `ACTUAL_LANGUAGE`: Imposta `it` per l'italiano o `en` per l'inglese (default: `en`).

## Esecuzione
Lancia il menu principale:
```bash
uv run actualutils
```

*(In alternativa, puoi avviare direttamente le singole utility):*
- Categorizzazione: `uv run actualutils` -> Seleziona Opzione 1
- Pulizia Beneficiari: `uv run cleanup`
- Rimozione Beneficiari Vuoti: `uv run remove-empty-payees`
- Gestione Regole: `uv run rules-cleanup`

---

# Actual Budget Utils (English)

**Actual Budget Utils** is a collection of interactive command-line (CLI) tools designed to clean, organize, and automate the management of your self-hosted **Actual Budget** instance.

All tools are accessible through a single interactive main menu by running:
```bash
uv run actualutils
```

Every utility automatically creates a local database backup (`db.sqlite.backup`) before making any edits and restores it in case of errors or cancellation, ensuring maximum safety for your budget data.

---

## Available Utilities

### 1. Transaction Categorizer
Helps you quickly inspect and assign categories to all uncategorized transactions:
- **Smart Suggestions**: Analyzes budget history and suggests the best categories based on: exact payee matches, bank note substring occurrences, or fuzzy payee name matches.
- **Interactive Prompt**: Go through transactions one by one. Press **Enter** to accept the top recommendation, type a number to select another suggestion, enter text to search categories, or create a new category/group on the fly.
- **Bulk Save (Bulk Commit)**: Review all changes in a summary table before committing and syncing them to the server.

### 2. Payee Cleanup Wizard
Consolidates and cleans up the list of payees in your budget:
- **Automatic Clustering**: Groups similar payees that differ only by codes, invoice numbers, or dates (e.g. "Coop Store No.123" and "Coop Store No.456").
- **Safe Merge**: Choose which payee to keep as the main target, choose which duplicates to merge (with the option to exclude specific ones), and automatically updates all associated transactions.
- **Automated Rules**: Automatically creates pre-import mapping rules in Actual Budget to map future transactions to the target payee.
- **Persistent Ignore**: Skip and permanently ignore specific clusters via a local `ignored_payees.json` file by pressing `I`.

### 3. Remove Empty Payees
Cleans up the payee list by deleting unused records:
- **Transaction Scan**: Finds all active payees with exactly `0` associated transactions in your budget.
- **Transfer Protection**: Automatically excludes system transfer accounts to prevent breaking transfer functions.
- **Bulk Deletion**: Lists the empty payees found and deletes them safely only after your confirmation.

### 4. Rules Manager and Cleanup
Provides a panel to inspect and clean up budget rules:
- **UUID Resolution**: Displays rules in a readable format by replacing database UUIDs with actual payee, category, and account names.
- **Duplicate Detection**: Finds identical rules (same conditions and actions) to delete duplicates and keep only one.
- **Redundancy Scan**: Detects overlapping rules (e.g. a rule for `"Octopus"` and another for `"Octopus Energy"` mapping to the same payee) and suggests removing the redundant ones.
- **Specific Deletion**: Allows manual removal of rules by entering their indices.

---

## Prerequisites
- **Python**: Ensure Python 3.10+ is installed.
- **uv**: Lightning-fast Python package and dependency manager.

## Setup
1. Clone this repository and enter the directory.
2. Copy the `.env.example` file to `.env`:
   ```bash
   cp .env.example .env
   ```
3. Fill in your connection details in `.env`:
   - `ACTUAL_SERVER_URL`: Your Actual Budget server URL (e.g. `https://budget.yourdomain.com`).
   - `ACTUAL_PASSWORD`: Password to log in.
   - `ACTUAL_SYNC_ID`: Your budget's sync ID (optional, prompts to select if omitted).
   - `ACTUAL_ENCRYPTION_PASSWORD`: Encryption password (leave blank if not encrypted).
   - `ACTUAL_LANGUAGE`: Set to `it` for Italian or `en` for English (default: `en`).

## Running
Launch the central menu:
```bash
uv run actualutils
```

*(Alternatively, you can run each utility directly):*
- Transaction Categorizer: `uv run actualutils` -> Option 1
- Payee Cleanup: `uv run cleanup`
- Remove Empty Payees: `uv run remove-empty-payees`
- Rules Manager: `uv run rules-cleanup`
