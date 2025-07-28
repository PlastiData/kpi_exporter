# Google Sheets KPI Exporter - Solution Guide

This folder contains the complete solution for extracting KPIs from PostgreSQL and Prometheus and exporting them to Google Sheets. It includes:

- **`export_kpis.py`** - Main script that queries PostgreSQL and Prometheus data
- **`service_account.json`** - Google Sheets API credentials (included in repo just for exam purposes)
- **`tests/`** - Test script for data fetching, export functions, transformation, and connection functions
- **`Dockerfile`** - Container configuration for the exporter service
- **`requirements.txt`** - Python dependencies

## Prerequisites

- Docker environment running (see main `README.md` for setup)
```bash
docker compose up -d
```
(Wait ~30 seconds for initialization)

## How to Run

1. **Export KPIs:**
  ```bash
  docker compose run --rm google-sheets-exporter
  ```
- Fetches data from Prometheus and PostgreSQL, exports to the configured Google Sheet.

2. **Run Tests:**
  ```bash
  docker compose run --rm --entrypoint="" google-sheets-exporter pytest -v -s
  ```
- Runs all unit tests inside the exporter container.

## Google Sheets Integration

- **Sheet ID:** Configure in `docker-compose.yml` as `GOOGLE_SHEET_ID` 
- **Service Account:** Place `service_account.json` in `kpi_extractor/solution/` (I'm giving it for this student task but I will be removed after 1 week)
- **Sheet ID:** 1EGVPWB4kc49Fqo4genpmdU9Zol3wNMycvQlzR74yCPA (Personal ID, can be modified for other google sheet ID)

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



## Cleanup

```bash
docker compose down -v
```

---

**Note:**
- All configuration (database, Google Sheet ID, etc.) is managed in `docker-compose.yml`.
- No `.env` file is needed.
- For general environment, dashboard, and troubleshooting info, see the main `README.md`.
- If you modify the solution code, rebuild the container:
   ```bash
   docker compose build google-sheets-exporter
   ```
