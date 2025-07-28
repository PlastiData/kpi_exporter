import pandas as pd
import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from export_kpis import create_pivot, fetch_alarm_data, fetch_postgres_data, export_to_excel, export_to_gsheet


class TestConnectionFunctions:
    @patch('export_kpis.requests.get')
    def test_connect_prometheus_success(self, mock_get):
        # Arrange: mock a successful response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None  # No exception means success
        mock_get.return_value = mock_response

        # Act: call the function
        from export_kpis import connect_prometheus
        result = connect_prometheus()

        # Assert: should return True on success
        assert result is True
        mock_get.assert_called_once()
        mock_response.raise_for_status.assert_called_once()

    @patch('export_kpis.requests.get')
    def test_connect_prometheus_failure(self, mock_get):
        # Arrange: mock a failed response (simulate an exception)
        mock_get.side_effect = Exception("Connection error")

        # Act: call the function
        from export_kpis import connect_prometheus
        result = connect_prometheus()

        # Assert: should return False on failure
        assert result is False
        assert mock_get.call_count == 3  # <-- updated for retry logic

    @patch('export_kpis.psycopg2.connect')
    def test_connect_postgres_success(self, mock_connect):
        # mock a successful connection object
        mock_conn = Mock()
        mock_connect.return_value = mock_conn

        from export_kpis import connect_postgres
        conn = connect_postgres()

        assert conn == mock_conn
        mock_connect.assert_called_once()

    @patch('export_kpis.psycopg2.connect')
    def test_connect_postgres_failure(self, mock_connect):
        # Test failed PostgreSQL connection 
        mock_connect.side_effect = Exception("Connection error")

        from export_kpis import connect_postgres
        conn = connect_postgres()

        assert conn is None
        mock_connect.assert_called_once() 
    
class TestDataFetching:
    @patch('export_kpis.requests.get')
    def test_fetch_alarm_data_success(self, mock_get):
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": ["alarm_total_cpu_high_total", "alarm_total_memory_low_total", "other_metric"]
        }
        mock_get.return_value = mock_response
        
        # Mock query response for each alarm
        def mock_query_response(*args, **kwargs):
            query_mock = Mock()
            query_mock.json.return_value = {
                "data": {"result": [{"value": ["1234567890", "5.0"]}]}
            }
            return query_mock
        
        mock_get.side_effect = [mock_response, mock_query_response(), mock_query_response()]
        
        result = fetch_alarm_data()
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert 'alarm_name' in result.columns
        assert 'total_count_30m' in result.columns
        assert 'cpu_high' in result['alarm_name'].values
        assert 'memory_low' in result['alarm_name'].values

    @patch('export_kpis.requests.get')
    def test_fetch_alarm_data_no_alarms(self, mock_get):
        # Mock response with no alarm metrics
        mock_response = Mock()
        mock_response.json.return_value = {"data": ["other_metric", "another_metric"]}
        mock_get.return_value = mock_response
        
        result = fetch_alarm_data()
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    @patch('export_kpis.psycopg2.connect')
    def test_fetch_postgres_data_success(self, mock_connect):
        # Mock connection and cursor
        mock_conn = Mock()
        mock_cursor = Mock()
        
        # Mock cursor methods
        mock_cursor.fetchall.return_value = [
            ('2024-06-01', 1, 'views', 'general', 100),
            ('2024-06-01', 1, 'edits', 'internal', 50),
            ('2024-06-08', 2, 'views', 'general', 200),
        ]
        mock_cursor.description = [
            ('week_start',), ('week_num',), ('metric',), ('type',), ('total_count',)
        ]
        
        # Make cursor a context manager
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)
        
        # Mock the cursor context manager
        mock_conn.cursor.return_value = mock_cursor
        
        mock_connect.return_value = mock_conn
        
        result = fetch_postgres_data(mock_conn)
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3
        assert 'week_start' in result.columns
        assert 'metric' in result.columns
        assert 'type' in result.columns
        assert 'total_count' in result.columns

    def test_fetch_postgres_data_connection_error(self):
        # Test with a mock connection that raises an exception
        mock_conn = Mock()
        mock_conn.cursor.side_effect = Exception("Database error")
        
        result = fetch_postgres_data(mock_conn)
        
        assert result is None

class TestExportFunctions:
    def test_export_to_excel_success(self):
        # Mock data
        df = pd.DataFrame({'alarm_name': ['cpu_high'], 'total_count_30m': [5.0]})
        pivot = pd.DataFrame({'week_start': ['2024-06-01'], 'metric': ['views'], 'general': [100]})
        
        # Use a temporary file approach
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            temp_path = tmp.name
        
        try:
            export_to_excel(df, pivot, temp_path)
            
            # Check if file was created and has content
            assert os.path.exists(temp_path)
            assert os.path.getsize(temp_path) > 0
            
        finally:
            # Clean up
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    @patch('export_kpis.gspread.authorize')
    @patch('export_kpis.Credentials.from_service_account_file')
    def test_export_to_gsheet_success(self, mock_creds, mock_authorize):
        # Mock data
        df = pd.DataFrame({'alarm_name': ['cpu_high'], 'total_count_30m': [5.0]})
        pivot = pd.DataFrame({'week_start': ['2024-06-01'], 'metric': ['views'], 'general': [100]})
        
        # Mock Google Sheets objects
        mock_gc = Mock()
        mock_sh = Mock()
        mock_ws1 = Mock()
        mock_ws2 = Mock()
        
        mock_authorize.return_value = mock_gc
        mock_gc.open_by_key.return_value = mock_sh
        mock_sh.worksheet.side_effect = [mock_ws1, mock_ws2]
        mock_sh.add_worksheet.side_effect = [mock_ws1, mock_ws2]
        
        export_to_gsheet(df, pivot)
        
        # Verify Google Sheets operations
        mock_authorize.assert_called_once()
        mock_gc.open_by_key.assert_called_once()
        assert mock_sh.add_worksheet.call_count == 2
        assert mock_ws1.update.call_count == 1
        assert mock_ws2.update.call_count == 1

    @patch('export_kpis.gspread.authorize')
    @patch('export_kpis.Credentials.from_service_account_file')
    def test_export_to_gsheet_not_found(self, mock_creds, mock_authorize):
        # Mock data
        df = pd.DataFrame({'alarm_name': ['cpu_high'], 'total_count_30m': [5.0]})
        pivot = pd.DataFrame({'week_start': ['2024-06-01'], 'metric': ['views'], 'general': [100]})
        
        # Mock Google Sheets objects with WorksheetNotFound exception
        mock_gc = Mock()
        mock_sh = Mock()
        mock_ws1 = Mock()
        mock_ws2 = Mock()
        
        mock_authorize.return_value = mock_gc
        mock_gc.open_by_key.return_value = mock_sh
        
        # Import gspread to use the correct exception type
        import gspread
        
        # Mock worksheet to raise the correct exception type
        mock_sh.worksheet.side_effect = gspread.exceptions.WorksheetNotFound("Worksheet not found")
        mock_sh.add_worksheet.side_effect = [mock_ws1, mock_ws2]
        
        # Should handle the exception and continue
        export_to_gsheet(df, pivot)
        
        # Verify operations still completed
        assert mock_sh.add_worksheet.call_count == 2 

class TestDataTransformation:
    def test_transform_to_pivot(self):
        data = [
            {'week_start': '2024-06-01', 'metric': 'views', 'type': 'general', 'total_count': 10},
            {'week_start': '2024-06-01', 'metric': 'edits', 'type': 'internal', 'total_count': 5},
            {'week_start': '2024-06-08', 'metric': 'views', 'type': 'general', 'total_count': 20},
            {'week_start': '2024-06-08', 'metric': 'edits', 'type': 'internal', 'total_count': 15},
        ]
        df = pd.DataFrame(data)
        pivot = create_pivot(df)
        # Check columns
        assert 'general' in pivot.columns
        assert 'internal' in pivot.columns
        # Check that the pivot has the right shape
        assert pivot.shape[0] == 4  # 2 weeks x 2 metrics
        # Check values
        assert pivot[(pivot['week_start'] == '2024-06-01') & (pivot['metric'] == 'views')]['general'].iloc[0] == 10
        assert pivot[(pivot['week_start'] == '2024-06-08') & (pivot['metric'] == 'edits')]['internal'].iloc[0] == 15

    def test_handle_empty_dataframe(self):
        df = pd.DataFrame([])
        pivot = create_pivot(df)
        # Should return an empty DataFrame
        assert pivot.empty 

    def test_handle_missing_columns(self):
        # DataFrame missing 'total_count' column
        df = pd.DataFrame([
            {'week_start': '2024-06-01', 'metric': 'views', 'type': 'general'},
            {'week_start': '2024-06-01', 'metric': 'edits', 'type': 'internal'},
        ])
        pivot = create_pivot(df)
        # Should return an empty DataFrame due to missing required columns
        assert pivot.empty 

    def test_handle_nan_values_in_metrics(self):
        # DataFrame with NaN/None in total_count only
        df = pd.DataFrame([
            {'week_start': '2024-06-01', 'metric': 'views', 'type': 'general', 'total_count': 10},
            {'week_start': '2024-06-01', 'metric': 'edits', 'type': 'internal', 'total_count': None},
            {'week_start': '2024-06-08', 'metric': 'views', 'type': 'general', 'total_count': float('nan')},
        ])
        pivot = create_pivot(df)
        # Should handle NaN/None gracefully: missing values should be filled with 0
        assert 'general' in pivot.columns
        assert 'internal' in pivot.columns
        val = pivot[(pivot['week_start'] == '2024-06-01') & (pivot['metric'] == 'edits')]['internal']
        assert val.iloc[0] == 0 or pd.isna(val.iloc[0])
        val2 = pivot[(pivot['week_start'] == '2024-06-08') & (pivot['metric'] == 'views')]['general']
        assert val2.iloc[0] == 0 or pd.isna(val2.iloc[0])
        # Check that valid values are preserved
        val3 = pivot[(pivot['week_start'] == '2024-06-01') & (pivot['metric'] == 'views')]['general']
        assert val3.iloc[0] == 10 
