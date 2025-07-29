# Google Sheets KPI Exporter - Solution Guide

This folder contains the complete solution for extracting KPIs from PostgreSQL and Prometheus and exporting them to Google Sheets. It includes:

- **`export_kpis.py`** - Main script that queries PostgreSQL and Prometheus data
- **`service_account.json`** - Google Sheets API credentials (must be download it)
- **`tests/`** - Test script for data fetching, export functions, transformation, and connection functions
- **`Dockerfile`** - Container configuration for the exporter service
- **`requirements.txt`** - Python dependencies

## Prerequisites

### 1. Get Google Service Account JSON File

**Required:** You need to download the `service_account.json` file before running the exporter.

**Gmail Credentials:**
- **Account:** studentapplication072025@gmail.com
- **Password:** Admin123!

**Steps:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **APIs & Services** → **Credentials**
3. Find the service account named **"export_kpis"**
4. Go to **Actions** → click the **Edit** button (pencil icon) → **Edit service account**
5. Go to the **Keys** tab
6. Click **Add Key** → **Create new key**
7. Select **JSON** format
8. Click **Create**
9. Save the downloaded file as `service_account.json` in the `solution/` folder
10. **Reference:** See the screenshot below for visual guidance

![Google Cloud Console - Service Account Keys Location](console_credentials.png)

### 2. Ensure Docker Environment is Running

Make sure the Docker environment is running:

```bash
docker compose up -d
```
(Wait ~30 seconds for initialization)

### 3. How to Run the solution

1. **Export KPIs:**
  ```bash
  docker compose run --rm sheets-exporter
  ```
- Fetches data from Prometheus and PostgreSQL, exports to the configured Google Sheet.

2. **Run Tests:**
  ```bash
  docker compose run --rm --entrypoint="" sheets-exporter pytest -v -s
  ```
- Runs all unit tests inside the exporter container.

## Architecture Overview

### Data Sources
- **PostgreSQL:** Views and edits metrics (6 weeks of historical data)
- **Prometheus:** Alarm metrics (15 different alarm types)

### Export Options
1. **Google Sheets Integration** (Primary)
   - Requires `service_account.json` credentials
   - Configured via `GOOGLE_SHEET_ID` in docker-compose.yml
   - Exports to specified Google Sheet
   - **Sheets created:**
     - `prometheus_alarms` - Alarm data from Prometheus
     - `postgres_metrics` - Views/edits data from PostgreSQL

2. **Local Excel Export** (Fallback)
   - Automatic fallback if Google Sheets fails
   - Creates `sheets.xlsx` in container/app directory
   - No additional configuration required

### Service Architecture
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │   Prometheus    │    │  Export Script  │
│  (Views/Edits) │───▶│   (Alarms)      │───▶│  (export_kpis)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
                                                       ▼
                                              ┌─────────────────┐
                                              │  Google Sheets  │
                                              │  or Excel File  │
                                              └─────────────────┘
```


## Cleanup

```bash
docker compose down -v
```

---

**Note:**
- All configuration (database, Google Sheet ID, etc.) is managed in `docker-compose.yml`.
- No `.env` file is needed.
- For general environment, dashboard, and troubleshooting info, see the main `README.md`.
- If you modify the solution code or change the requirements, rebuild the container:
   ```bash
   docker compose build kpi-exporter
   ```


### Example `service_account.json` content
```json
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "your-private-key-id",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "your-service-account@your-project.iam.gserviceaccount.com",
  "client_id": "your-client-id",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/your-service-account%40your-project.iam.gserviceaccount.com"
}
```