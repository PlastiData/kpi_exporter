# Google Sheets KPI Exporter - Solution Guide

This folder contains the complete solution for extracting KPIs from Grafana dashboards and exporting them to Google Sheets. It includes:

- **`export_kpis.py`** - Main script that queries Grafana dashboards via API
- **`service_account.json`** - Google Sheets API credentials (must be downloaded)
- **`tests/`** - Test scripts for data fetching, export functions, transformation, and connection functions
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
(Wait ~2 minutes for initialization the alarms)

### 3. How to Run the solution

1. **Export KPIs via Grafana API:**
  ```bash
  docker compose run --rm sheets-exporter
  ```
- Extracts queries from Grafana dashboards and executes them via Grafana API

2. **Run Tests:**
  ```bash
  docker compose run --rm --entrypoint="" sheets-exporter pytest -v -s
  ```
- Runs all unit tests inside the exporter container.

## Architecture Overview

### Data Sources
- **Grafana Dashboards:** Views and edits metrics, alarm metrics via dashboard queries

### Export to Google Sheets

   - Requires `service_account.json` credentials
   - Configured via `GOOGLE_SHEET_ID` in docker-compose.yml
   - Exports to specified Google Sheet
   - **Sheets created:**
     - `Alarms Dashboard` - Alarm data from Prometheus with total counts for the past 30 minutes
     - `Views and Edits` - Views and edits data from PostgreSQL for the past 6 weeks with general and internal views


### Service Architecture

**Grafana API Flow (7 Steps):**

**Step-by-Step Flow:**
1. **Dashboard Discovery** - Connect to Grafana API and get available dashboards
2. **Query Extraction** - Extract PromQL/SQL queries from dashboard panels
3. **API Execution** - Execute queries via Grafana API with appropriate time ranges
4. **Data Processing** - Convert Grafana API responses to pandas DataFrames
5. **Data Transformation** - Transform Prometheus time series and combine PostgreSQL data
6. **Data Validation** - Ensure data quality and handle missing values
7. **Export** - Export to Google Sheets with proper formatting

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

## Tests

The solution includes comprehensive unit tests covering all major functionality:

### Test Classes

1. **TestConnectionFunctions**
   - `test_grafana_connection_success` - Tests successful Grafana API connection
   - `test_grafana_connection_failure` - Tests failed connection handling
   - `test_grafana_connection_exception` - Tests exception handling

2. **TestDashboardQueries**
   - `test_get_dashboard_queries_success` - Tests Prometheus query extraction
   - `test_get_dashboard_queries_postgres` - Tests PostgreSQL query extraction
   - `test_get_dashboard_queries_failure` - Tests failed dashboard retrieval

3. **TestQueryExecution**
   - `test_execute_prometheus_query_success` - Tests Prometheus query execution
   - `test_execute_postgres_query_success` - Tests PostgreSQL query execution
   - `test_execute_query_failure` - Tests failed query execution

4. **TestDataProcessing**
   - `test_process_results_success` - Tests valid results processing
   - `test_process_results_invalid_format` - Tests invalid format handling
   - `test_process_results_no_frames` - Tests empty results handling

5. **TestDataTransformation**
   - `test_transform_prometheus_data_success` - Tests Prometheus data transformation
   - `test_transform_prometheus_data_empty` - Tests empty data handling
   - `test_combine_postgres_simple_success` - Tests PostgreSQL data combination
   - `test_combine_postgres_simple_missing_data` - Tests missing data handling

6. **TestExportFunctions**
   - `test_export_to_gsheet_success` - Tests successful Google Sheets export
   - `test_export_to_gsheet_no_sheet_id` - Tests missing environment variable

7. **TestMainExtraction**
   - `test_extract_kpis_success` - Tests complete KPI extraction flow
   - `test_extract_kpis_no_dashboards` - Tests no dashboards scenario

8. **TestErrorHandling**
   - `test_handle_missing_columns_in_dataframe` - Tests missing column handling
   - `test_handle_nan_values` - Tests NaN value handling

### Test Coverage
- **22 total tests** covering all major functionality
- **Mock-based testing** for isolated unit testing
- **Error scenario testing** for robust error handling
- **Data transformation testing** for data quality assurance
- **Export functionality testing** for Google Sheets integration