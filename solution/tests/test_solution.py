import pandas as pd
import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from export_kpis import KPIExtractor


class TestConnectionFunctions:
    @patch('export_kpis.requests.Session')
    def test_grafana_connection_success(self, mock_session):
        # Arrange: mock a successful session and response
        mock_session_instance = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{'uid': 'test-dashboard'}]
        mock_session_instance.get.return_value = mock_response
        mock_session.return_value = mock_session_instance

        # Act: create extractor and test connection
        extractor = KPIExtractor()
        result = extractor.get_dashboards()

        # Assert: should return dashboard list on success
        assert len(result) == 1
        assert result[0]['uid'] == 'test-dashboard'
        mock_session_instance.get.assert_called_once()

    @patch('export_kpis.requests.Session')
    def test_grafana_connection_failure(self, mock_session):
        # Arrange: mock a failed response
        mock_session_instance = Mock()
        mock_response = Mock()
        mock_response.status_code = 500
        mock_session_instance.get.return_value = mock_response
        mock_session.return_value = mock_session_instance

        # Act: create extractor and test connection
        extractor = KPIExtractor()
        result = extractor.get_dashboards()

        # Assert: should return empty list on failure
        assert result == []

    @patch('export_kpis.requests.Session')
    def test_grafana_connection_exception(self, mock_session):
        # Arrange: mock an exception
        mock_session_instance = Mock()
        mock_session_instance.get.side_effect = Exception("Connection error")
        mock_session.return_value = mock_session_instance

        # Act: create extractor and test connection
        extractor = KPIExtractor()
        result = extractor.get_dashboards()

        # Assert: should return empty list on exception
        assert result == []


class TestDashboardQueries:
    @patch('export_kpis.requests.Session')
    def test_get_dashboard_queries_success(self, mock_session):
        # Mock successful dashboard response with panels
        mock_session_instance = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'dashboard': {
                'panels': [
                    {
                        'title': 'Test Panel',
                        'datasource': {'type': 'prometheus'},
                        'targets': [
                            {'expr': 'alarm_total_cpu_high_total'}
                        ]
                    }
                ]
            }
        }
        mock_session_instance.get.return_value = mock_response
        mock_session.return_value = mock_session_instance

        extractor = KPIExtractor()
        result = extractor.get_dashboard_queries('test-uid')

        assert len(result) == 1
        assert result[0]['panel_title'] == 'Test Panel'
        assert result[0]['query_type'] == 'PromQL'
        assert result[0]['query_text'] == 'alarm_total_cpu_high_total'

    @patch('export_kpis.requests.Session')
    def test_get_dashboard_queries_postgres(self, mock_session):
        # Mock dashboard with PostgreSQL queries
        mock_session_instance = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'dashboard': {
                'panels': [
                    {
                        'title': 'PostgreSQL Panel',
                        'datasource': {'type': 'postgres'},
                        'targets': [
                            {'rawSql': 'SELECT * FROM views_edits'}
                        ]
                    }
                ]
            }
        }
        mock_session_instance.get.return_value = mock_response
        mock_session.return_value = mock_session_instance

        extractor = KPIExtractor()
        result = extractor.get_dashboard_queries('test-uid')

        assert len(result) == 1
        assert result[0]['panel_title'] == 'PostgreSQL Panel'
        assert result[0]['query_type'] == 'SQL'
        assert result[0]['query_text'] == 'SELECT * FROM views_edits'

    @patch('export_kpis.requests.Session')
    def test_get_dashboard_queries_failure(self, mock_session):
        # Mock failed dashboard response
        mock_session_instance = Mock()
        mock_response = Mock()
        mock_response.status_code = 404
        mock_session_instance.get.return_value = mock_response
        mock_session.return_value = mock_session_instance

        extractor = KPIExtractor()
        result = extractor.get_dashboard_queries('invalid-uid')

        assert result == []


class TestQueryExecution:
    @patch('export_kpis.requests.Session')
    def test_execute_prometheus_query_success(self, mock_session):
        # Mock successful Prometheus query execution
        mock_session_instance = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'results': {
                'A': {
                    'frames': [
                        {
                            'schema': {
                                'fields': [
                                    {'name': 'Time'},
                                    {'name': 'alarm_total_cpu_high_total'}
                                ]
                            },
                            'data': {
                                'values': [
                                    [1640995200000, 1640995260000],
                                    [10.0, 15.0]
                                ]
                            }
                        }
                    ]
                }
            }
        }
        mock_session_instance.post.return_value = mock_response
        mock_session.return_value = mock_session_instance

        query_info = {
            'datasource': {'type': 'prometheus'},
            'query_text': 'alarm_total_cpu_high_total'
        }

        extractor = KPIExtractor()
        result = extractor.execute_query(query_info)

        assert result is not None
        assert 'results' in result
        mock_session_instance.post.assert_called_once()

    @patch('export_kpis.requests.Session')
    def test_execute_postgres_query_success(self, mock_session):
        # Mock successful PostgreSQL query execution
        mock_session_instance = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'results': {
                'A': {
                    'frames': [
                        {
                            'schema': {
                                'fields': [
                                    {'name': 'time'},
                                    {'name': 'Views'},
                                    {'name': 'Edits'}
                                ]
                            },
                            'data': {
                                'values': [
                                    ['2024-06-01', '2024-06-08'],
                                    [100, 200],
                                    [50, 75]
                                ]
                            }
                        }
                    ]
                }
            }
        }
        mock_session_instance.post.return_value = mock_response
        mock_session.return_value = mock_session_instance

        query_info = {
            'datasource': {'type': 'postgres'},
            'query_text': 'SELECT * FROM views_edits'
        }

        extractor = KPIExtractor()
        result = extractor.execute_query(query_info)

        assert result is not None
        assert 'results' in result

    @patch('export_kpis.requests.Session')
    def test_execute_query_failure(self, mock_session):
        # Mock failed query execution
        mock_session_instance = Mock()
        mock_response = Mock()
        mock_response.status_code = 500
        mock_session_instance.post.return_value = mock_response
        mock_session.return_value = mock_session_instance

        query_info = {
            'datasource': {'type': 'prometheus'},
            'query_text': 'invalid_query'
        }

        extractor = KPIExtractor()
        result = extractor.execute_query(query_info)

        assert result is None


class TestDataProcessing:
    def test_process_results_success(self):
        # Test data processing with valid results
        results = {
            'results': {
                'A': {
                    'frames': [
                        {
                            'schema': {
                                'fields': [
                                    {'name': 'Time'},
                                    {'name': 'alarm_total_cpu_high_total'}
                                ]
                            },
                            'data': {
                                'values': [
                                    [1640995200000, 1640995260000],
                                    [10.0, 15.0]
                                ]
                            }
                        }
                    ]
                }
            }
        }

        query_info = {'datasource': {'type': 'prometheus'}}
        extractor = KPIExtractor()
        result = extractor.process_results(results, query_info)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert 'Time' in result.columns
        assert 'alarm_total_cpu_high_total' in result.columns

    def test_process_results_invalid_format(self):
        # Test processing with invalid results format
        results = {'invalid': 'format'}
        query_info = {'datasource': {'type': 'prometheus'}}
        
        extractor = KPIExtractor()
        result = extractor.process_results(results, query_info)

        assert result is None

    def test_process_results_no_frames(self):
        # Test processing with no frames
        results = {
            'results': {
                'A': {
                    'frames': []
                }
            }
        }
        query_info = {'datasource': {'type': 'prometheus'}}
        
        extractor = KPIExtractor()
        result = extractor.process_results(results, query_info)

        assert result is None


class TestDataTransformation:
    def test_transform_prometheus_data_success(self):
        # Test Prometheus data transformation
        df = pd.DataFrame({
            'Time': [1640995200000, 1640995260000, 1640995320000],
            'alarm_total_cpu_high_total': [10.0, 15.0, 20.0],
            'alarm_total_memory_low_total': [5.0, 8.0, 12.0]
        })

        extractor = KPIExtractor()
        result = extractor.transform_prometheus_data(df)

        assert isinstance(result, pd.DataFrame)
        assert 'alarm_name' in result.columns
        assert 'cumulative_count' in result.columns
        assert 'minute_increase' in result.columns
        assert 'date' in result.columns

    def test_transform_prometheus_data_empty(self):
        # Test transformation with empty dataframe
        df = pd.DataFrame()
        
        extractor = KPIExtractor()
        result = extractor.transform_prometheus_data(df)

        assert result.empty

    def test_combine_postgres_simple_success(self):
        # Test PostgreSQL data combination
        postgres_data = [
            {
                'panel_title': 'General Views and Edits',
                'dataframe': pd.DataFrame({
                    'time': ['2024-06-01', '2024-06-08'],
                    'Views': [100, 200],
                    'Edits': [50, 75]
                })
            },
            {
                'panel_title': 'Internal Views and Edits',
                'dataframe': pd.DataFrame({
                    'time': ['2024-06-01', '2024-06-08'],
                    'Views': [25, 40],
                    'Edits': [10, 15]
                })
            }
        ]

        extractor = KPIExtractor()
        result = extractor.combine_postgres_simple(postgres_data)

        assert isinstance(result, pd.DataFrame)
        assert 'week_start' in result.columns
        assert 'metric' in result.columns
        assert 'general' in result.columns
        assert 'internal' in result.columns

    def test_combine_postgres_simple_missing_data(self):
        # Test combination with missing data
        postgres_data = [
            {
                'panel_title': 'General Views and Edits',
                'dataframe': pd.DataFrame({
                    'time': ['2024-06-01'],
                    'Views': [100],
                    'Edits': [50]
                })
            }
        ]

        extractor = KPIExtractor()
        result = extractor.combine_postgres_simple(postgres_data)

        assert result is None


class TestExportFunctions:
    @patch('export_kpis.gspread.authorize')
    @patch('export_kpis.Credentials.from_service_account_file')
    @patch('export_kpis.os.environ.get')
    def test_export_to_gsheet_success(self, mock_env, mock_creds, mock_authorize):
        # Mock environment variable
        mock_env.return_value = 'test-sheet-id'
        
        # Mock Google Sheets objects
        mock_gc = Mock()
        mock_sh = Mock()
        mock_ws = Mock()
        
        mock_authorize.return_value = mock_gc
        mock_gc.open_by_key.return_value = mock_sh
        
        # Import gspread to use the correct exception type
        import gspread
        mock_sh.worksheet.side_effect = gspread.exceptions.WorksheetNotFound("Worksheet not found")
        mock_sh.add_worksheet.return_value = mock_ws
        
        # Mock data
        postgres_data = [
            {
                'panel_title': 'General Views and Edits',
                'dataframe': pd.DataFrame({
                    'time': ['2024-06-01'],
                    'Views': [100],
                    'Edits': [50]
                })
            }
        ]
        prometheus_data = pd.DataFrame({
            'alarm_name': ['cpu_high'],
            'date': ['2024-06-01'],
            'cumulative_count': [10]
        })

        extractor = KPIExtractor()
        extractor.export_to_gsheet(postgres_data, prometheus_data)

        # Verify Google Sheets operations
        mock_authorize.assert_called_once()
        mock_gc.open_by_key.assert_called_once_with('test-sheet-id')
        assert mock_sh.add_worksheet.call_count >= 1

    @patch('export_kpis.gspread.authorize')
    @patch('export_kpis.Credentials.from_service_account_file')
    @patch('export_kpis.os.environ.get')
    def test_export_to_gsheet_no_sheet_id(self, mock_env, mock_creds, mock_authorize):
        # Mock missing environment variable
        mock_env.return_value = None
        
        postgres_data = []
        prometheus_data = None

        extractor = KPIExtractor()
        
        with pytest.raises(ValueError, match="GOOGLE_SHEET_ID environment variable is required"):
            extractor.export_to_gsheet(postgres_data, prometheus_data)


class TestMainExtraction:
    @patch('export_kpis.KPIExtractor.get_dashboards')
    @patch('export_kpis.KPIExtractor.get_dashboard_queries')
    @patch('export_kpis.KPIExtractor.execute_query')
    @patch('export_kpis.KPIExtractor.process_results')
    @patch('export_kpis.KPIExtractor.transform_prometheus_data')
    def test_extract_kpis_success(self, mock_transform, mock_process, mock_execute, mock_queries, mock_dashboards):
        # Mock successful extraction flow
        mock_dashboards.return_value = [{'uid': 'test-dashboard'}]
        mock_queries.return_value = [
            {
                'panel_title': 'Test Panel',
                'datasource': {'type': 'prometheus'},
                'query_text': 'alarm_total_cpu_high_total'
            }
        ]
        mock_execute.return_value = {'results': {'A': {'frames': []}}}
        mock_process.return_value = pd.DataFrame({'Time': [1640995200000], 'alarm_total_cpu_high_total': [10.0]})
        mock_transform.return_value = pd.DataFrame({'alarm_name': ['cpu_high'], 'cumulative_count': [10]})

        extractor = KPIExtractor()
        postgres_data, prometheus_data = extractor.extract_kpis()

        assert isinstance(postgres_data, list)
        assert isinstance(prometheus_data, pd.DataFrame)

    @patch('export_kpis.KPIExtractor.get_dashboards')
    def test_extract_kpis_no_dashboards(self, mock_dashboards):
        # Mock no dashboards found
        mock_dashboards.return_value = []

        extractor = KPIExtractor()
        postgres_data, prometheus_data = extractor.extract_kpis()

        assert postgres_data is None
        assert prometheus_data is None


class TestErrorHandling:
    def test_handle_missing_columns_in_dataframe(self):
        # Test handling of dataframes with missing columns
        df = pd.DataFrame({
            'Time': [1640995200000],
            'some_column': [10.0]
        })

        extractor = KPIExtractor()
        result = extractor.transform_prometheus_data(df)

        # Should handle gracefully and return empty dataframe
        assert result.empty

    def test_handle_nan_values(self):
        # Test handling of NaN values in data
        df = pd.DataFrame({
            'Time': [1640995200000, 1640995260000],
            'alarm_total_cpu_high_total': [10.0, float('nan')]
        })

        extractor = KPIExtractor()
        result = extractor.transform_prometheus_data(df)

        # Should handle NaN values gracefully
        assert isinstance(result, pd.DataFrame) 