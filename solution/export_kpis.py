#!/usr/bin/env python3

import requests
import json
import pandas as pd
from datetime import datetime
import os
import gspread
from google.oauth2.service_account import Credentials
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# Configuration
GRAFANA_URL = os.environ.get("GRAFANA_URL", "http://grafana:3000")
GRAFANA_USER = os.environ.get("GRAFANA_USER", "admin")
GRAFANA_PASSWORD = os.environ.get("GRAFANA_PASSWORD", "admin")

class KPIExtractor:
    def __init__(self):
        self.session = requests.Session()
        self.session.auth = (GRAFANA_USER, GRAFANA_PASSWORD)
    
    def get_dashboards(self):
        """Get all available dashboards"""
        try:
            response = self.session.get(f"{GRAFANA_URL}/api/search")
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get dashboards: HTTP {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error getting dashboards: {e}")
            return []
    
    def get_dashboard_queries(self, uid):
        """Extract queries from dashboard"""
        try:
            response = self.session.get(f"{GRAFANA_URL}/api/dashboards/uid/{uid}")
            if response.status_code != 200:
                logger.error(f"Failed to get dashboard {uid}: HTTP {response.status_code}")
                return []
            
            dashboard = response.json().get('dashboard', {})
            queries = []
            
            # Use list comprehension instead of nested loops
            for panel in dashboard.get('panels', []):
                panel_title = panel.get('title', 'Unknown')
                datasource = panel.get('datasource', {})
                
                # Extract queries using list comprehension
                panel_queries = [
                    {
                        'panel_title': panel_title,
                        'datasource': datasource,
                        'query_type': 'PromQL' if 'expr' in target else 'SQL',
                        'query_text': target.get('expr') or target.get('rawSql')
                    }
                    for target in panel.get('targets', [])
                    if 'expr' in target or 'rawSql' in target
                ]
                queries.extend(panel_queries)
            
            return queries
        except Exception as e:
            logger.error(f"Error extracting queries from dashboard {uid}: {e}")
            return []
    
    def execute_query(self, query_info):
        """Execute query via Grafana API"""
        datasource_type = query_info['datasource'].get('type', 'unknown')
        
        if datasource_type == 'postgres':
            payload = {
                "queries": [{
                    "refId": "A",
                    "datasource": query_info['datasource'],
                    "rawSql": query_info['query_text'],
                    "format": "table"
                }],
                "from": "now-6w",
                "to": "now"
            }
        elif datasource_type == 'prometheus':
            payload = {
                "queries": [{
                    "refId": "A",
                    "datasource": query_info['datasource'],
                    "expr": query_info['query_text'],
                    "format": "time_series",
                    "instant": False,
                    "maxDataPoints": 31
                }],
                "from": "now-30m",
                "to": "now"
            }
        else:
            return None
        
        try:
            response = self.session.post(f"{GRAFANA_URL}/api/ds/query", json=payload)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Query execution failed: HTTP {response.status_code}")
                return None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection failed: Cannot connect to Grafana API")
            return None
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            return None
    
    def process_results(self, results, query_info):
        """Process query results into dataframe"""
        try:
            if not results or 'results' not in results:
                logger.error("Invalid results format")
                return None
            
            first_result = list(results['results'].values())[0]
            frames = first_result.get('frames', [])
            
            if not frames:
                logger.error("No frames found in results")
                return None
            
            # Process all frames at once 
            all_data = []
            for frame in frames:
                schema = frame.get('schema', {}).get('fields', [])
                values = frame.get('data', {}).get('values', [])
                
                if values and len(values) > 0:
                    # Create column names
                    columns = [col.get('name', f'col_{i}') for i, col in enumerate(schema)]
                    
                    # Convert to DataFrame 
                    df = pd.DataFrame(dict(zip(columns, values)))
                    
                    # Convert timestamps 
                    if 'time' in df.columns:
                        df['time'] = pd.to_datetime(df['time'], unit='ms').dt.strftime('%Y-%m-%d')
                    
                    all_data.append(df)
            
            if all_data:
                return pd.concat(all_data, ignore_index=True)
            return None
            
        except Exception as e:
            logger.error(f"Error processing results: {e}")
            return None
    
    def transform_prometheus_data(self, df):
        """Transform Prometheus time series"""
        if df.empty:
            return df
        
        # Get metric columns (exclude Time)
        metric_columns = [col for col in df.columns if col != 'Time']
        
        # Melt the dataframe to flatten it
        melted_df = df.melt(
            id_vars=['Time'], 
            value_vars=metric_columns,
            var_name='metric_name',
            value_name='cumulative_count'
        )
        
        # Clean up metric names and add metadata 
        melted_df['alarm_name'] = melted_df['metric_name'].str.replace('alarm_total_', '').str.replace('_total', '').str.replace('_', ' ').str.title()
        melted_df['timestamp'] = melted_df['Time']
        melted_df['date'] = pd.to_datetime(melted_df['Time'], unit='ms').dt.strftime('%Y-%m-%d %H:%M:%S')
        melted_df['minute'] = pd.to_datetime(melted_df['Time'], unit='ms').dt.strftime('%M')
        
        # Remove NaN values
        melted_df = melted_df.dropna(subset=['cumulative_count'])
        
        # Calculate minute-by-minute increases using pandas groupby and shift
        melted_df = melted_df.sort_values(['alarm_name', 'timestamp'])
        
        # Calculate increases for each alarm group
        result_data = []
        for alarm_name in melted_df['alarm_name'].unique():
            alarm_data = melted_df[melted_df['alarm_name'] == alarm_name].copy()
            
            # Skip first data point and calculate increases
            if len(alarm_data) > 1:
                alarm_data = alarm_data.iloc[1:]  # Remove first data point
                
                # Calculate increases using shift
                alarm_data['prev_count'] = alarm_data['cumulative_count'].shift(1)
                alarm_data['minute_increase'] = (alarm_data['cumulative_count'] - alarm_data['prev_count']).fillna(0)
                alarm_data['minute_increase'] = alarm_data['minute_increase'].clip(lower=0)
                
                # Add minute_from_end (descending from 30 to 1)
                alarm_data['minute_from_end'] = range(len(alarm_data), 0, -1)
                
                # Select final columns
                final_columns = ['alarm_name', 'cumulative_count', 'minute_increase', 'timestamp', 'date', 'minute', 'minute_from_end']
                result_data.append(alarm_data[final_columns])
        
        if result_data:
            return pd.concat(result_data, ignore_index=True)
        return pd.DataFrame()
    
    def extract_kpis(self):
        """Main function to extract KPIs"""
        print(" Extracting KPIs from Grafana dashboards...")
        
        # Get dashboards
        dashboards = self.get_dashboards()
        if not dashboards:
            print(" No dashboards found")
            return None, None
        
        postgres_data = []
        prometheus_data = []
        
        # Process each dashboard
        for dashboard in dashboards:
            uid = dashboard.get('uid')
            if not uid:
                continue
            
            queries = self.get_dashboard_queries(uid)
            
            for query_info in queries:
                results = self.execute_query(query_info)
                if results:
                    df = self.process_results(results, query_info)
                    if df is not None:
                        datasource_type = query_info['datasource'].get('type', 'unknown')
                        
                        if datasource_type == 'postgres':
                            postgres_data.append({
                                'panel_title': query_info['panel_title'],
                                'dataframe': df
                            })
                        elif datasource_type == 'prometheus':
                            prometheus_data.append({
                                'panel_title': query_info['panel_title'],
                                'dataframe': df
                            })
        
        # Transform Prometheus data
        if prometheus_data:
            merged_prometheus = pd.concat([df_info['dataframe'] for df_info in prometheus_data], ignore_index=True)
            final_prometheus = self.transform_prometheus_data(merged_prometheus)
        else:
            final_prometheus = None
        
        return postgres_data, final_prometheus
    
    def combine_postgres_simple(self, postgres_data):
        """Combination of PostgreSQL data"""
        try:
            general_data = None
            internal_data = None
            
            # Find general and internal data
            for df_info in postgres_data:
                df = df_info['dataframe']
                panel_title = df_info['panel_title'].lower()
                
                if 'general' in panel_title:
                    general_data = df
                elif 'internal' in panel_title:
                    internal_data = df
            
            if general_data is None or internal_data is None:
                logger.warning("Missing general or internal data")
                return None
            
            # Prepare data for merging
            def prepare_df(df, prefix):
                # Ensure time column exists
                time_col = 'time' if 'time' in df.columns else 'Time'
                if time_col not in df.columns:
                    return None
                
                # Convert time to string format
                df = df.copy()
                df[time_col] = pd.to_datetime(df[time_col]).dt.strftime('%Y-%m-%d')
                
                # Select and rename columns
                result_df = df[[time_col, 'Views', 'Edits']].copy()
                result_df.columns = ['week_start', f'{prefix}_views', f'{prefix}_edits']
                return result_df
            
            general_prepared = prepare_df(general_data, 'general')
            internal_prepared = prepare_df(internal_data, 'internal')
            
            if general_prepared is None or internal_prepared is None:
                return None
            
            # Merge dataframes on week_start
            combined_df = pd.merge(general_prepared, internal_prepared, on='week_start', how='outer')
            
            # Create long format using pandas melt
            views_data = combined_df[['week_start', 'general_views', 'internal_views']].copy()
            views_data['metric'] = 'views'
            views_data = views_data.rename(columns={'general_views': 'general', 'internal_views': 'internal'})
            
            edits_data = combined_df[['week_start', 'general_edits', 'internal_edits']].copy()
            edits_data['metric'] = 'edits'
            edits_data = edits_data.rename(columns={'general_edits': 'general', 'internal_edits': 'internal'})
            
            # Combine views and edits data
            final_df = pd.concat([views_data, edits_data], ignore_index=True)
            
            # Convert to safe integers
            final_df['general'] = pd.to_numeric(final_df['general'], errors='coerce').fillna(0).astype(int)
            final_df['internal'] = pd.to_numeric(final_df['internal'], errors='coerce').fillna(0).astype(int)
            
            return final_df.sort_values(['week_start', 'metric'])
            
        except Exception as e:
            logger.error(f"Error combining PostgreSQL data: {e}")
            return None

    def export_to_gsheet(self, postgres_data, prometheus_data):
        """Export data to Google Sheets"""
        try:
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
            
            # Prepare worksheets data
            worksheets = []
            
            # Add Prometheus data with custom columns
            if prometheus_data is not None and not prometheus_data.empty:
                # Check if required columns exist
                required_columns = ['alarm_name', 'date', 'cumulative_count']
                if all(col in prometheus_data.columns for col in required_columns):
                    prometheus_export = prometheus_data[required_columns].copy()
                    worksheets.append({'name': 'Alarms Dashboard', 'data': prometheus_export})
                else:
                    logger.warning(f"Prometheus data missing required columns. Available: {list(prometheus_data.columns)}")
            
            # Add PostgreSQL data in combined format
            if postgres_data:
                combined_df = self.combine_postgres_simple(postgres_data)
                if combined_df is not None:
                    worksheets.append({'name': 'Views and Edits', 'data': combined_df})
            
            # Process each worksheet
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
            
            logger.info(f"Successfully exported data to Google Sheet")
            logger.info(f"Access sheet URL: https://docs.google.com/spreadsheets/d/{sheet_id}")
            
        except Exception as e:
            logger.error(f"Failed to export to Google Sheets: {e}")
            raise

def main():
    """Main execution"""
    extractor = KPIExtractor()
    
    # Check connection to Grafana first
    try:
        print(" Checking connection to Grafana...")
        dashboards = extractor.get_dashboards()
        if not dashboards:
            print(" Connection failed: No dashboards found or cannot connect to Grafana")
            return
        print(f" Connection successful: Found {len(dashboards)} dashboards")
    except Exception as e:
        print(f" Connection failed: Cannot connect to Grafana API - {e}")
        return
    
    # Extract KPIs
    postgres_data, prometheus_data = extractor.extract_kpis()
    
    # Print principal debugging info
    print("\n KPI Extraction Results:")
    print(f"  PostgreSQL panels found: {len(postgres_data)}")
    
    if prometheus_data is not None and not prometheus_data.empty:
        if 'alarm_name' in prometheus_data.columns:
            print(f"  Prometheus alarms found: {len(prometheus_data['alarm_name'].unique())}")
        else:
            print(f"  Prometheus data found but no alarm names: {len(prometheus_data)} rows")
    else:
        print("  No Prometheus data found")
    
    # Check if we have any data to export
    if not postgres_data and prometheus_data is None:
        print("\n No data found to export. Extraction was not successful.")
        return
    
    # Export data
    try:
        print("\n Exporting data to Google Sheets...")
        extractor.export_to_gsheet(postgres_data, prometheus_data)
        print(" Successfully exported to Google Sheets!")
    except Exception as e:
        print(f" Failed to export to Google Sheets: {e}")

if __name__ == '__main__':
    main() 