# SupportGenie --- Email and AI-Assisted Support Ticket Management System

SupportGenie is a lightweight local web application built with **Python,
FastAPI, pyodbc, Microsoft SQL Server, HTML5, CSS3, and vanilla
JavaScript**.

It provides two integrated modules:

-   **Support Console (`/support`)** --- View dashboard metrics, filter
    and inspect support tickets, run rule-based NLP classification and
    root-cause analysis, review historical ticket matches, and save
    internal follow-up notes, chat replies, status updates, and
    resolution remarks.
-   **Email Console (`/email`)** --- Inspect ticket-linked email
    records, view email-originated tickets, and compose/send support
    emails through SMTP. When SMTP is not configured, the application
    reports that email delivery did not occur. Compose drafts are saved
    in browser `localStorage`.

## Features

### Support Console

-   Dashboard counts and ticket queue
-   Search and filter tickets
-   Ticket details and history
-   Rule-based ticket classification and root-cause analysis
-   Historical ticket matching
-   Internal follow-up notes and ticket chat
-   Status changes, associate assignment, and resolution remarks

### Email Console

-   Ticket-linked email inbox and sent-message views
-   Compose support emails
-   SMTP delivery when valid SMTP settings are configured
-   Clear reporting when SMTP is unavailable or a send attempt fails
-   Local browser draft saving

## Application workflow

1.  The user opens SupportGenie in a browser.
2.  The frontend calls the FastAPI backend.
3.  The backend loads application and database settings from `.env`.
4.  The backend connects to SQL Server through `pyodbc`.
5.  The Support Console loads ticket data and dashboard counts.
6.  A support associate opens a ticket and reviews its details and
    history.
7.  The associate can run rule-based analysis and review its
    classification, root-cause hypothesis, evidence, and missing
    information.
8.  The associate can update ticket details or add a chat message or
    internal follow-up note.
9.  The backend persists supported changes to SQL Server and reports the
    operation result.
10. For email sending, the backend validates the request and uses the
    configured SMTP transport. It must not report delivery when SMTP is
    unconfigured or the send fails.

## Requirements

-   Windows with PowerShell and VS Code
-   Python installed
-   Microsoft ODBC Driver 18 for SQL Server
-   Access to the SQL Server instance and application database
-   SQL Server credentials or Windows Authentication, depending on your
    configuration
-   SMTP credentials/settings only if you need to send real emails

## Setup and running instructions (VS Code on Windows)

Run commands from the directory that contains `run.py`,
`requirements.txt`, and the `supportgenie` package. If your repository
has an outer folder and a nested `SupportGenie` folder, use the inner
folder containing the `supportgenie` package.

### 1. Open the project directory

In VS Code, open the project folder containing `run.py` and
`requirements.txt`, then open **Terminal → New Terminal**.

### 2. Create and activate a virtual environment

``` powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation for the current terminal session, run:

``` powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

``` powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If the project uses `pyodbc`, ensure the Microsoft ODBC Driver 18 for
SQL Server is installed and visible to your Python environment.

### 4. Configure environment variables

Create a `.env` file in the project directory from which
`supportgenie/config.py` loads configuration. Keep `.env` private and do
not commit it to Git.

If `.env.example` is present:

``` powershell
Copy-Item .env.example .env
```

Configure the database settings to match the SQL Server instance and
database you actually use:

``` dotenv
DB_SERVER=127.0.0.1,18001
DB_NAME=jotdesk
DB_DRIVER=ODBC Driver 18 for SQL Server
DB_AUTH_MODE=sql
DB_USER=sa
DB_PASSWORD=replace_with_your_database_password
DB_ENCRYPT=yes
DB_TRUST_SERVER_CERTIFICATE=yes
```

The values above are examples based on a local SQL Server endpoint.
Replace them with your own working settings. If your SQL Server uses
Windows Authentication, configure `DB_AUTH_MODE=windows` and follow the
project's supported configuration. Do not commit passwords or
credentials.

**Configuration location:** `supportgenie/config.py` loads `.env`
relative to the project package directory. Put `.env` in the location
expected by that code. If your repository has nested project folders,
verify the path before testing the connection.

### 5. Test the database connection

From the directory containing the `supportgenie` package, run:

``` powershell
python -c "from supportgenie.database import db_manager; print(db_manager.check_connectivity())"
```

The result should report `connected: True` when the configured SQL
Server is reachable and authentication succeeds. If the schema
validation fails, check that the configured database is the intended
application database and that it contains the tables required by the
application.

### 6. Start the application

``` powershell
python run.py
```

Open the URLs printed in the terminal. By default, they are:

-   Support Console: http://127.0.0.1:8000/support
-   Email Console: http://127.0.0.1:8000/email
-   API documentation: http://127.0.0.1:8000/docs
-   Database health check: http://127.0.0.1:8000/health/db

Keep the terminal running while you use the application. Stop the server
with `Ctrl+C`.

## Configure email sending (optional)

SupportGenie does not simulate email delivery. Real email sending
requires a working SMTP configuration. If SMTP settings are missing or
incorrect, the application should report that the email was not sent.

For Gmail, the typical SMTP settings are:

``` dotenv
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_gmail_address@gmail.com
SMTP_PASSWORD=your_google_app_password
SMTP_USE_TLS=true
SMTP_FROM_EMAIL=your_gmail_address@gmail.com
SUPPORT_TEAM_EMAIL=your_gmail_address@gmail.com
```

Use a Google App Password only if your Google account supports it and
2-Step Verification is enabled. Never use or publish your regular
account password in the repository. For an organizational mailbox, use
the SMTP settings and authentication method approved by your
administrator.

After editing `.env`, restart SupportGenie so the application reloads
the configuration.

### Email logging and drafts

-   Compose drafts are stored in the browser's `localStorage`.
-   The application only records outbound email metadata after SMTP
    sending succeeds and when a valid ticket is linked, according to the
    application's current implementation.
-   Email metadata storage is not the same as storing the full email
    body or draft.
-   Use a valid existing ticket ID when testing ticket-linked email
    logging.

## Run tests

From the project directory, with the virtual environment activated:

``` powershell
pytest -v
```

## Troubleshooting

  ------------------------------------------------------------------------------------------------------
  Problem                                                 What to check
  ------------------------------------------------------- ----------------------------------------------
  `ModuleNotFoundError: No module named 'supportgenie'`   Run commands from the directory containing the
                                                          `supportgenie` package.

  `pyodbc` is missing                                     Activate the correct virtual environment and
                                                          run
                                                          `python -m pip install -r requirements.txt`.

  ODBC driver unavailable                                 Install Microsoft ODBC Driver 18 for SQL
                                                          Server and verify it with `pyodbc.drivers()`.

  SQL Server connection timeout                           Verify `DB_SERVER`, instance/port, SQL Server
                                                          availability, and network access.

  Login failed                                            Verify the configured authentication mode and
                                                          credentials.

  Database/schema validation fails                        Confirm that `DB_NAME` points to the intended
                                                          application database and that required
                                                          application objects exist.

  Email not sent because `SMTP_HOST` is empty             Configure a supported SMTP transport or
                                                          continue testing draft composition without
                                                          sending.

  Port 8000 is already in use                             Stop the other process or configure a
                                                          different application port if supported.
  ------------------------------------------------------------------------------------------------------

## Security notes

-   Keep `.env` out of version control.
-   Commit `.env.example` only with placeholder values and no secrets.
-   Do not expose database passwords, SMTP passwords, app passwords, or
    API keys in source code, screenshots, logs, or GitHub.
-   If a credential was committed or pushed, rotate it. Adding it to
    `.gitignore` does not remove it from earlier Git history.
-   Use only database instances and email accounts you are authorized to
    access.

## Technology stack

-   Python
-   FastAPI and Uvicorn
-   pyodbc
-   Microsoft SQL Server
-   HTML5, CSS3, and vanilla JavaScript
-   SMTP for optional outbound email
