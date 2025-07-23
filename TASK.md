# Programming Task: Grafana KPI Extractor

## Objective

Create a Python script that queries KPI data from Grafana dashboards and exports the results into a google sheet.
The KPIs should be queried and stored in weekly periods

## Requirements

### 1. Script Functionality

Your script should:
- Query, Extract and process the KPI metrics
- Write the results to the excel sheet
- Handle errors gracefully
- Include proper logging

### 2. Data to Extract

#### From "Views and Edits Dashboard" (PostgreSQL datasource):
- General views (weekly totals for past 6 weeks)
- General edits (weekly totals for past 6 weeks)
- Internal views (weekly totals for past 6 weeks)
- Internal edits (weekly totals for past 6 weeks)

#### From "Alarms Dashboard" (Prometheus datasource):
- All alarm names and their total counts
- Get the data for each minute from the past 30 minutes (note that prometheus only exports while the docker compose is running)


### 4. Technical Requirements

- The code should have a clear documentation for setup, execution and results (not too much not too less)
- Implement proper exception handling
- Include informative log messages

Good luck! 