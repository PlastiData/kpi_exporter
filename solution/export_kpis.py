import requests
import pandas as pd
import os
import psycopg2
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import logging
import time
from requests.exceptions import RequestException, Timeout, ConnectionError
from psycopg2 import OperationalError, InterfaceError

PROM_URL = os.environ.get("PROM_URL", "http://prometheus:9090")

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# Prometheus connection with retry logic
def connect_prometheus(max_retries=3, timeout=10):
    for attempt in range(max_retries):
        try:
            resp = requests.get(f"{PROM_URL}/api/v1/status/runtimeinfo", timeout=timeout)
            resp.raise_for_status()
            logger.info("Prometheus connection successful.")
            return True
        except Timeout:
            logger.warning(f"Prometheus connection timeout (attempt {attempt + 1}/{max_retries})")
        except ConnectionError:
            logger.warning(f"Prometheus connection error (attempt {attempt + 1}/{max_retries})")
        except RequestException as e:
            logger.error(f"Prometheus request failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error connecting to Prometheus: {e}")
        
        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)  # Exponential backoff
    
    logger.error("Failed to connect to Prometheus after all retries")
    return False

# PostgreSQL connection with specific error handling
def connect_postgres():
    try:
        pg_host = os.environ["POSTGRES_HOST"]
        pg_db = os.environ["POSTGRES_DB"]
        pg_user = os.environ["POSTGRES_USER"]
        pg_password = os.environ["POSTGRES_PASSWORD"]
        pg_port = os.environ["POSTGRES_PORT"]
    except KeyError as e:
        logger.error(f"Missing required environment variable: {e}")
        return None
    
    try:
        conn = psycopg2.connect(
            host=pg_host,
            dbname=pg_db,
            user=pg_user,
            password=pg_password,
            port=pg_port,
            connect_timeout=10
        )
        logger.info("PostgreSQL connection successful.")
        return conn
    except OperationalError as e:
        logger.error(f"PostgreSQL operational error: {e}")
        return None
    except InterfaceError as e:
        logger.error(f"PostgreSQL interface error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error connecting to PostgreSQL: {e}")
        return None

# Fetch alarm data from Prometheus with validation
def fetch_alarm_data():
    try:
        # Fetch metric names with validation
        resp = requests.get(f"{PROM_URL}/api/v1/label/__name__/values", timeout=10)
        resp.raise_for_status()
        
        response_data = resp.json()
        if not response_data or "data" not in response_data:
            logger.error("Invalid response format from Prometheus")
            return pd.DataFrame()
        
        metric_names = response_data["data"]
        if not metric_names:
            logger.warning("No metrics found in Prometheus")
            return pd.DataFrame()
        
        # Filter alarm metrics
        alarm_metrics = [name for name in metric_names if name.startswith("alarm_total_") and name.endswith("_total")]
        if not alarm_metrics:
            logger.warning("No alarm metrics found")
            return pd.DataFrame()
        
        alarm_data = []
        for metric in alarm_metrics:
            try:
                query_url = f"{PROM_URL}/api/v1/query"
                params = {"query": f"increase({metric}[30m])"}
                r = requests.get(query_url, params=params, timeout=10)
                r.raise_for_status()
                
                result_data = r.json()
                if not result_data or "data" not in result_data or "result" not in result_data["data"]:
                    logger.warning(f"Invalid response for metric {metric}")
                    continue
                
                result = result_data["data"]["result"]
                if result and len(result) > 0:
                    value = float(result[0]["value"][1])
                    alarm_name = metric.replace("alarm_total_", "").replace("_total", "")
                    alarm_data.append({"alarm_name": alarm_name, "total_count_30m": value})
                    
            except (RequestException, ValueError, KeyError) as e:
                logger.warning(f"Error processing metric {metric}: {e}")
                continue
        
        df = pd.DataFrame(alarm_data)
        logger.info(f"Successfully fetched {len(alarm_data)} alarm metrics.")
        return df
        
    except RequestException as e:
        logger.error(f"Failed to fetch alarm data from Prometheus: {e}")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"Unexpected error fetching alarm data: {e}")
        return pd.DataFrame()

# Fetch data from PostgreSQL
def fetch_postgres_data(conn):
    query = """
        WITH last_6_weeks AS (
        SELECT DISTINCT week_start
        FROM views_edits
        ORDER BY week_start DESC
        LIMIT 6
        ),
        ranked_weeks AS (
        SELECT
            week_start,
            ROW_NUMBER() OVER (ORDER BY week_start) AS week_num
        FROM last_6_weeks
        )
        SELECT
        vw.week_start,
        rw.week_num,
        vw.metric,
        vw.type,
        SUM(vw.count) AS total_count
        FROM views_edits vw
        JOIN ranked_weeks rw ON vw.week_start = rw.week_start
        GROUP BY vw.week_start, rw.week_num, vw.metric, vw.type
        ORDER BY rw.week_num;

    """
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
            df_pg = pd.DataFrame(rows, columns=columns)
        logger.info("Successfully fetched weekly totals from PostgreSQL.")
        return df_pg
    except Exception as e:
        logger.error(f"Failed to query PostgreSQL: {e}")
        return None
    finally:
        conn.close()

# Create pivot table from PostgreSQL data with validation
def create_pivot(df_pg):
    # Validate input DataFrame
    if df_pg is None or df_pg.empty:
        logger.warning("Empty or None DataFrame provided to create_pivot")
        return pd.DataFrame()
    
    # Check for required columns
    required_cols = {'week_start', 'metric', 'type', 'total_count'}
    if not required_cols.issubset(df_pg.columns):
        missing_cols = required_cols - set(df_pg.columns)
        logger.error(f"Missing required columns: {missing_cols}")
        return pd.DataFrame()
    
    # Validate data types
    if not pd.api.types.is_numeric_dtype(df_pg['total_count']):
        logger.error("total_count column must be numeric")
        return pd.DataFrame()
    
    # Drop rows where any index column is None or NaN
    original_count = len(df_pg)
    df_pg = df_pg.dropna(subset=['week_start', 'metric', 'type'])
    if len(df_pg) < original_count:
        logger.warning(f"Dropped {original_count - len(df_pg)} rows with missing values")
    
    if df_pg.empty:
        logger.warning("No valid data remaining after cleaning")
        return pd.DataFrame()
    
    try:
        pivot = pd.pivot_table(
            df_pg,
            values='total_count',
            index=['week_start', 'metric'],
            columns='type',
            aggfunc='sum',
            fill_value=0
        )
        pivot = pivot.reset_index()
        logger.info(f"Successfully created pivot table with {len(pivot)} rows")
        return pivot
    except Exception as e:
        logger.error(f"Error creating pivot table: {e}")
        return pd.DataFrame()

# Export to Excel in case of error with Google Sheets
def export_to_excel(df, pivot, excel_path="sheets.xlsx"):
    with pd.ExcelWriter(excel_path) as writer:
        df.to_excel(writer, sheet_name='prometheus_alarms', index=False)
        pivot.to_excel(writer, sheet_name='postgres_metrics', index=False)
    logger.info(f"Successfully exported both tables to {excel_path}")

# Export to Google Sheets
def export_to_gsheet(df, pivot):
    svc_file = 'service_account.json'
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_file(svc_file, scopes=scopes)
    gc = gspread.authorize(creds)
    
    # Get sheet ID from environment variable
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    if not sheet_id:
        raise ValueError("GOOGLE_SHEET_ID environment variable is required")
    
    sh = gc.open_by_key(sheet_id)
    logger.info(f"Successfully connected to Google Sheet")
    
    # Define worksheet configurations
    worksheets = [
        {'name': 'prometheus_alarms', 'data': df},
        {'name': 'postgres_metrics', 'data': pivot}
    ]
    
    for ws_config in worksheets:
        ws_name = ws_config['name']
        data = ws_config['data']
        
        # Delete existing worksheet if it exists
        try:
            ws = sh.worksheet(ws_name)
            sh.del_worksheet(ws)
        except gspread.exceptions.WorksheetNotFound:
            logger.info(f"Worksheet '{ws_name}' not found, will create new.")
        except Exception as e:
            logger.error(f"Error handling worksheet '{ws_name}': {e}")
            raise
        
        # Calculate proper worksheet dimensions
        rows_needed = max(len(data) + 1, 100)  # +1 for header row
        cols_needed = max(len(data.columns), 100)  # Minimum 10 columns
        
        # Create new worksheet and populate data
        ws = sh.add_worksheet(title=ws_name, rows=str(rows_needed), cols=str(cols_needed))
        
        # Convert week_start to string if present
        if 'week_start' in data.columns:
            data['week_start'] = data['week_start'].astype(str)
        
        ws.update([data.columns.values.tolist()] + data.values.tolist())
        logger.info(f"Successfully exported {ws_name} worksheet")
    
    logger.info(f"Successfully exported both tables to Google Sheet")
    logger.info(f"Access sheet URL: https://docs.google.com/spreadsheets/d/{sheet_id}")

def main():
    logger.info("Starting KPI export process...")
    
    # Connect to Prometheus
    if not connect_prometheus():
        logger.error("Cannot proceed without Prometheus connection")
        return
    
    # Connect to PostgreSQL
    conn = connect_postgres()
    if conn is None: 
        logger.error("Cannot proceed without PostgreSQL connection")
        return
    
    # Fetch data with validation
    df = fetch_alarm_data()
    if df.empty:
        logger.warning("No alarm data available, will export only PostgreSQL data")
    
    df_pg = fetch_postgres_data(conn)
    if df_pg is None:
        logger.error("Cannot proceed without PostgreSQL data")
        return
    
    pivot = create_pivot(df_pg)
    if pivot.empty:
        logger.error("Cannot proceed without valid pivot data")
        return
    
    # Export data
    try:
        export_to_gsheet(df, pivot)
        logger.info("Export completed successfully")
    except Exception as e:
        logger.warning(f"Failed to connect to Google Sheets, metrics will be exported to an Excel file named sheets.xlsx. Error: {e}")
        export_to_excel(df, pivot)
        logger.info("Excel export completed successfully")

if __name__ == '__main__':
    main()