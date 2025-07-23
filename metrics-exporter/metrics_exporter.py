#!/usr/bin/env python3

import time
import random
import threading
import sys
from datetime import datetime, timedelta
from flask import Flask
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

# Define alarm types and their base frequencies per 10 seconds
ALARM_TYPES = [
    "database_connection_timeout",
    "high_cpu_usage", 
    "memory_leak_detected",
    "disk_space_low",
    "api_response_time_high",
    "authentication_failure",
    "service_unavailable",
    "network_latency_high",
    "cache_miss_rate_high",
    "queue_overflow",
    "ssl_certificate_expiring",
    "backup_failed",
    "log_file_size_exceeded",
    "user_session_timeout",
    "rate_limit_exceeded"
]

# Create Prometheus metrics
alarm_counters = {}
alarm_gauges = {}

# Initialize counters and gauges for each alarm type
for alarm_type in ALARM_TYPES:
    # Counter for total alarms over time
    alarm_counters[alarm_type] = Counter(
        f'alarm_total_{alarm_type}_total',
        f'Total count of {alarm_type.replace("_", " ")} alarms'
    )
    
    # Gauge for current alarm rate per 10 seconds
    alarm_gauges[alarm_type] = Gauge(
        f'alarm_rate_{alarm_type}_per_10s',
        f'Current rate of {alarm_type.replace("_", " ")} alarms per 10 seconds'
    )

# Global generation counter
generation_count = 0
is_running = True

def get_alarm_rate_for_10_seconds(alarm_type):
    """Get realistic alarm rate for a given alarm type per 10 seconds"""
    current_time = datetime.now()
    
    # Different alarm types have different base frequencies per 10 seconds
    # Higher rates to ensure more frequent alarms
    if alarm_type in ["high_cpu_usage", "api_response_time_high", "memory_leak_detected"]:
        base_rate_per_10s = random.uniform(0.2, 0.8)  # 0.2-0.8 alarms per 10s
    elif alarm_type in ["database_connection_timeout", "network_latency_high"]:
        base_rate_per_10s = random.uniform(0.1, 0.4)  # 0.1-0.4 alarms per 10s
    else:
        base_rate_per_10s = random.uniform(0.05, 0.2)  # 0.05-0.2 alarms per 10s
    
    # Add time-based variation (higher during business hours)
    hour = current_time.hour
    if 9 <= hour <= 17:  # Business hours
        rate_multiplier = 2.0
    elif 18 <= hour <= 22:  # Evening
        rate_multiplier = 1.5
    else:  # Night/early morning
        rate_multiplier = 1.0
    
    # Add day-of-week variation (higher on weekdays)
    if current_time.weekday() < 5:  # Monday-Friday
        day_multiplier = 1.0
    else:  # Weekend
        day_multiplier = 0.6
    
    # Calculate final rate with some randomness
    final_rate = base_rate_per_10s * rate_multiplier * day_multiplier * random.uniform(0.9, 1.5)
    return max(0, final_rate)

def generate_10_second_alarms():
    """Generate alarms for the current 10-second interval"""
    global generation_count
    generation_count += 1
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_generated = 0
    
    print(f"[Gen #{generation_count}] Starting alarm generation at {current_time}", flush=True)
    
    for alarm_type in ALARM_TYPES:
        # Get the rate for this 10-second interval
        rate_per_10s = get_alarm_rate_for_10_seconds(alarm_type)
        
        # Update the gauge with current rate
        alarm_gauges[alarm_type].set(rate_per_10s)
        
        # Generate actual alarm count for this 10-second interval
        alarm_count = 0
        if rate_per_10s > 0:
            # Use probability-based generation for 10-second intervals
            rand = random.random()
            if rand < rate_per_10s:
                # Most of the time generate 1 alarm, occasionally more
                if rand < rate_per_10s * 0.6:
                    alarm_count = 1
                elif rand < rate_per_10s * 0.85:
                    alarm_count = 2
                else:
                    alarm_count = max(1, int(rate_per_10s * 5))
        
        # Increment the counter
        if alarm_count > 0:
            alarm_counters[alarm_type]._value._value += alarm_count
            total_generated += alarm_count
    
    print(f"[Gen #{generation_count}] Generated {total_generated} alarms across all types", flush=True)
    return total_generated

def alarm_generator_thread():
    """Background thread that generates alarms every 10 seconds"""
    print("🚀 Starting alarm generator thread...", flush=True)
    
    while is_running:
        try:
            # Generate alarms
            total = generate_10_second_alarms()
            
            # Wait 10 seconds for the next generation
            print(f"[Gen #{generation_count}] Waiting 10 seconds... (generated {total} alarms)", flush=True)
            time.sleep(10)
            
        except Exception as e:
            print(f"❌ ERROR in alarm generator (generation #{generation_count}): {e}", flush=True)
            import traceback
            traceback.print_exc()
            print("🔄 Retrying in 10 seconds...", flush=True)
            time.sleep(10)
    
    print("⏹️ Alarm generator thread stopped", flush=True)

@app.route('/metrics')
def metrics():
    """Prometheus metrics endpoint"""
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

@app.route('/health')
def health():
    """Health check endpoint"""
    return {'status': 'healthy', 'timestamp': datetime.now().isoformat(), 'generation_count': generation_count}

@app.route('/stats')
def stats():
    """Endpoint to show current alarm statistics"""
    stats_data = {
        'timestamp': datetime.now().isoformat(),
        'generation_count': generation_count,
        'current_totals': {},
        'current_rates_per_10s': {}
    }
    
    for alarm_type in ALARM_TYPES:
        stats_data['current_totals'][alarm_type] = int(alarm_counters[alarm_type]._value._value)
        stats_data['current_rates_per_10s'][alarm_type] = round(alarm_gauges[alarm_type]._value._value, 3)
    
    return stats_data

if __name__ == '__main__':
    print("🎯 Starting Real-time Alarm Metrics Exporter on port 8080...", flush=True)
    print(f"📊 Configured {len(ALARM_TYPES)} alarm types", flush=True)
    print("⏰ Generating alarms every 10 seconds...", flush=True)
    
    # Start the background alarm generator thread
    alarm_thread = threading.Thread(target=alarm_generator_thread, daemon=True)
    alarm_thread.start()
    
    print("✅ Real-time alarm metrics exporter ready!", flush=True)
    print("🔄 Metrics will be generated every 10 seconds with realistic patterns", flush=True)
    
    try:
        app.run(host='0.0.0.0', port=8080, debug=False)
    except KeyboardInterrupt:
        print("🛑 Shutting down...", flush=True)
        is_running = False
        sys.exit(0) 