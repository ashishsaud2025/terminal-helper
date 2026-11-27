# Architecture

`th` watches your terminal and helps when things go wrong. It never runs a command for you. It only suggests what to type next.

## How it fits together

```mermaid
flowchart TD
    A[You type a command] --> B[Shell runs it]
    B --> C{Did it fail?}
    C -- Yes --> D[th records it]
    C -- No --> E[Done]
    D --> F[th checks rules]
    F --> G{Known fix?}
    G -- Yes --> H[Suggest fix]
    G -- No --> I[Optional LLM]
    I --> H
    H --> J[You decide]
    J --> K[Type it yourself]
```

**What each part does:**

- **Shell hook** : watches every command you run and notes whether it succeeded or failed.
- **Rules engine** : checks for simple mistakes first: typos, wrong flags, missing paths. Fast. No network.
- **LLM** : only called if rules cannot help, and only if you enable it. Runs locally via Ollama by default.
- **You** : always in control. `th` never runs anything. You press Enter.

## When a command fails

```mermaid
sequenceDiagram
    participant U as You
    participant S as Shell
    participant H as th hook
    participant R as Rules
    participant L as LLM

    U->>S: type command, press Enter
    S->>H: command ran, exit code = 1
    H->>R: is there a simple fix?
    alt known fix
        R-->>H: yes, try this
        H-->>U: suggestion appears
    else no fix
        H->>L: ask for help only if enabled
        L-->>H: suggested command
        H-->>U: suggestion appears
    end
    U->>U: read suggestion, press Enter to run
```

## Safety: what `th` will and won't do

```mermaid
flowchart TD
    A[Suggested command] --> B{Is it dangerous?}
    B -- Yes --> C[Show warning with ! marker]
    C --> D[Never insert into buffer]
    B -- No --> E[Offer as suggestion]
    E --> F[You press Enter to run]

    style C fill:#f96,stroke:#333
    style D fill:#f96,stroke:#333
```

`th` never blocks Enter. You always decide what runs.

## What `th` remembers

```mermaid
erDiagram
    COMMAND ||--o{ SUGGESTION : logs
    COMMAND {
        string id "unique id"
        datetime ts "when it ran"
        string cmd "what you typed"
        string cwd "where you ran it"
        int exit_code "0 equals success"
        string stderr_tail "error output"
    }
    SUGGESTION {
        string id "unique id"
        datetime ts "when suggested"
        string kind "fix, check, describe"
        string input "what went in"
        string output "what came out"
        boolean accepted "did you use it?"
    }
```

Everything stays on your computer in a SQLite database. Nothing leaves your machine unless you turn on a remote LLM backend.

## The fix flow

```mermaid
stateDiagram-v2
    [*] --> CommandRuns
    CommandRuns --> Failed: exit code not 0
    Failed --> CheckingRules: th looks for simple fix
    CheckingRules --> Found: typo, flag, path fix
    CheckingRules --> NoFix: nothing simple
    Found --> Suggested: show you
    NoFix --> LLMAsk: ask LLM if enabled
    LLMAsk --> Suggested: show you
    Suggested --> [*]: you decide

    state CheckingRules {
        [*] --> TypoCheck
        TypoCheck --> FlagCheck
        FlagCheck --> PathCheck
        PathCheck --> [*]
    }
```

## Install and remove

```mermaid
flowchart LR
    A[Run install.sh] --> B[Checks bash 4.4+]
    B --> C[Installs th package]
    C --> D[Adds hook to ~/.bashrc]
    D --> E[Restart shell]
    E --> F[th doctor verifies]

    G[Run uninstall.sh] --> H[Removes ~/.bashrc hook]
    H --> I[Optional: delete data dir]

    style E fill:#bbf,stroke:#333
```

## What you need

- **bash 4.4 or newer** for the hotkeys. Older bash still runs `th log`, `th help`, `th check`, `th doctor`.
- **Ollama** optional, only if you want LLM-powered fixes. Default model: `qwen3:4b`.
