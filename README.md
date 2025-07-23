# Grafana KPI Extractor - Programming Task

This repository contains a complete Grafana setup with sample KPI data for evaluating programming candidates. The task involves creating a script to query KPIs from Grafana dashboards.

## Setup Instructions

### Prerequisites
- Docker and Docker Compose installed
- Ports 3000 (Grafana), 5432 (PostgreSQL), 9090 (Prometheus), and 8080 (Metrics Exporter) available

### Quick Start

1. **Start the environment:**
   ```bash
   docker compose up -d
   ```

2. **Wait for services to initialize** (approximately 30-60 seconds)

3. **Access Grafana:**
   - URL: http://localhost:3000
   - Username: `admin`
   - Password: `admin`

4. **Verify dashboards are loaded:**
   - Navigate to "Dashboards" in the left sidebar
   - You should see two dashboards:
     - "Views and Edits Dashboard"
     - "Alarms Dashboard"

### Architecture

- **Grafana**: Visualization and dashboard platform (port 3000)
- **PostgreSQL**: Relational database storing views and edits data (port 5432)
- **Prometheus**: Metrics collection system storing alarm data (port 9090)
- **Metrics Exporter**: Python service that generates 6 weeks of historical alarm metrics for Prometheus (port 8080)
- **Data Generator**: Python service that populates PostgreSQL with sample data

## Available Dashboards

### 1. Views and Edits Dashboard
- **URL**: http://localhost:3000/d/views-edits-dashboard
- **Content**: Two time-series charts showing:
  - General views and edits (weekly aggregation)
  - Internal views and edits (weekly aggregation)
- **Time Range**: Past 6 weeks
- **Data Points**: Daily data aggregated by week

### 2. Alarms Dashboard
- **URL**: http://localhost:3000/d/alarms-dashboard
- **Content**: Table showing:
  - Alarm Name
  - Total Count (based on selected time range)
- **Features**: 
  - Responsive to time range selection
  - Sorted by count (descending)
  - Color-coded based on alarm frequency

## Data Structure

### PostgreSQL Views/Edits Table
```sql
CREATE TABLE views_edits (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE,
    type VARCHAR(20), -- 'general' or 'internal'
    metric VARCHAR(20), -- 'views' or 'edits'
    count INTEGER,
    week_start DATE,
    week_number INTEGER
);
```

### Prometheus Alarm Metrics
```
# Counter metrics for total alarms
alarm_total_{alarm_type}_total

# Gauge metrics for current alarm rates
alarm_rate_{alarm_type}
```

## API Access Information

### Grafana API
- **Base URL**: http://localhost:3000
- **Authentication**: Basic Auth (admin:admin)
- **API Documentation**: http://localhost:3000/docs/http_api/

### PostgreSQL Database (Alternative)
- **Host**: localhost:5432
- **Database**: kpis
- **Username**: admin
- **Password**: adminpass123

### Prometheus API (Alternative)
- **Base URL**: http://localhost:9090
- **Query API**: http://localhost:9090/api/v1/query

## Troubleshooting

### Services not starting
```bash
# Check service status
docker compose ps

# View logs
docker compose logs grafana
docker compose logs postgres
docker compose logs prometheus
docker compose logs metrics-exporter
docker compose logs data-generator
```

### Dashboards not visible
```bash
# Restart Grafana to reload dashboards
docker compose restart grafana
```

### Reset environment
```bash
# Stop and remove all containers and volumes
docker compose down -v

# Start fresh
docker compose up -d
```

## Cleanup

```bash
# Stop services
docker compose down

# Remove volumes (deletes all data)
docker compose down -v
``` 