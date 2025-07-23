#!/usr/bin/env python3

import os
import time
import random
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
from psycopg2.extras import execute_values

# Configuration
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
POSTGRES_DB = os.getenv('POSTGRES_DB', 'kpis')
POSTGRES_USER = os.getenv('POSTGRES_USER', 'admin')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'adminpass123')

def wait_for_postgres():
    """Wait for PostgreSQL to be ready"""
    print("Waiting for PostgreSQL to be ready...")
    max_retries = 30
    for i in range(max_retries):
        try:
            conn = psycopg2.connect(
                host=POSTGRES_HOST,
                database=POSTGRES_DB,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD
            )
            conn.close()
            print("PostgreSQL is ready!")
            return True
        except Exception as e:
            print(f"Attempt {i+1}/{max_retries}: PostgreSQL not ready yet... ({e})")
            time.sleep(5)
    
    print("Failed to connect to PostgreSQL after maximum retries")
    return False

def generate_views_and_edits_data():
    """Generate views and edits data for the past 6 weeks"""
    print("Generating views and edits data...")
    
    # Generate data for the past 6 weeks
    end_date = datetime.now()
    start_date = end_date - timedelta(weeks=6)
    
    data_points = []
    
    # Generate weekly data points
    current_date = start_date
    week_number = 1
    
    while current_date <= end_date:
        week_start = current_date
        week_end = min(current_date + timedelta(days=6), end_date)
        
        # Calculate week number
        year, week_num, _ = week_start.isocalendar()
        
        # Generate realistic data with some trends and variations
        base_general_views = 15000 + (week_number * 500) + random.randint(-2000, 3000)
        base_general_edits = 2500 + (week_number * 50) + random.randint(-300, 500)
        base_internal_views = 8000 + (week_number * 200) + random.randint(-1000, 1500)
        base_internal_edits = 1200 + (week_number * 25) + random.randint(-150, 250)
        
        # Create multiple data points throughout the week for better realism
        for day in range(7):
            point_date = week_start + timedelta(days=day)
            if point_date > end_date:
                break
                
            # Add some daily variation
            daily_variation = random.uniform(0.8, 1.2)
            
            # General views and edits
            general_views = int(base_general_views / 7 * daily_variation)
            general_edits = int(base_general_edits / 7 * daily_variation)
            
            # Internal views and edits
            internal_views = int(base_internal_views / 7 * daily_variation)
            internal_edits = int(base_internal_edits / 7 * daily_variation)
            
            # Add data points
            data_points.extend([
                (point_date, 'general', 'views', general_views, week_start.date(), week_num),
                (point_date, 'general', 'edits', general_edits, week_start.date(), week_num),
                (point_date, 'internal', 'views', internal_views, week_start.date(), week_num),
                (point_date, 'internal', 'edits', internal_edits, week_start.date(), week_num)
            ])
        
        current_date += timedelta(weeks=1)
        week_number += 1
    
    return data_points

def insert_data_to_postgres(data_points):
    """Insert data points into PostgreSQL"""
    print(f"Inserting {len(data_points)} data points into PostgreSQL...")
    
    try:
        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            database=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD
        )
        
        cursor = conn.cursor()
        
        # Clear existing data
        cursor.execute("DELETE FROM views_edits")
        
        # Insert new data
        insert_query = """
            INSERT INTO views_edits (timestamp, type, metric, count, week_start, week_number)
            VALUES %s
        """
        
        execute_values(cursor, insert_query, data_points)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("Data insertion completed successfully!")
        
    except Exception as e:
        print(f"Error inserting data: {e}")
        raise

def main():
    """Main function to generate and insert all data"""
    if not wait_for_postgres():
        print("Exiting due to PostgreSQL connection failure")
        return
    
    try:
        print("Starting data generation...")
        
        # Generate views/edits data
        data_points = generate_views_and_edits_data()
        
        # Insert data into PostgreSQL
        insert_data_to_postgres(data_points)
        
        print("Data generation completed successfully!")
        print(f"Generated data for views and edits over the past 6 weeks")
        print("Alarm data will be generated by the metrics-exporter service")
        
    except Exception as e:
        print(f"Error generating data: {e}")
        raise

if __name__ == "__main__":
    main() 