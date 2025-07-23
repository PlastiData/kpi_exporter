-- Create tables for KPI data
CREATE TABLE IF NOT EXISTS views_edits (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    type VARCHAR(20) NOT NULL, -- 'general' or 'internal'
    metric VARCHAR(20) NOT NULL, -- 'views' or 'edits'
    count INTEGER NOT NULL,
    week_start DATE NOT NULL,
    week_number INTEGER NOT NULL
);

-- Create index for better query performance
CREATE INDEX IF NOT EXISTS idx_views_edits_timestamp ON views_edits(timestamp);
CREATE INDEX IF NOT EXISTS idx_views_edits_type_metric ON views_edits(type, metric);
CREATE INDEX IF NOT EXISTS idx_views_edits_week ON views_edits(week_start);

-- Create a view for easier querying
CREATE OR REPLACE VIEW weekly_kpis AS
SELECT 
    type,
    metric,
    week_start,
    week_number,
    SUM(count) as total_count,
    EXTRACT(YEAR FROM week_start) as year,
    EXTRACT(WEEK FROM week_start) as week
FROM views_edits 
GROUP BY type, metric, week_start, week_number
ORDER BY week_start, type, metric; 