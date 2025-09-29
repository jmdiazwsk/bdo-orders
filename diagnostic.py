# diagnostic.py - Quick system health check
import subprocess
import json
import time

def run_command(cmd, description):
    """Run a command and return result"""
    print(f"\n=== {description} ===")
    print(f"Command: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        print(f"Exit code: {result.returncode}")
        if result.stdout:
            print(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            print(f"STDERR:\n{result.stderr}")
        return result.returncode == 0
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def main():
    print("BDO Orders Platform - System Diagnostic")
    print("=" * 50)
    
    # 1. Check Docker containers
    run_command("docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'", 
                "Docker Containers Status")
    
    # 2. Check specific containers
    containers = ['bdo-postgres', 'bdo-kafka', 'bdo-consumer', 'bdo-api', 'bdo-kcat']
    for container in containers:
        run_command(f"docker inspect {container} --format '{{{{.State.Status}}}}'", 
                   f"Container {container} Status")
    
    # 3. Check consumer logs
    run_command("docker logs --tail 10 bdo-consumer", 
                "Consumer Recent Logs")
    
    # 4. Check API health
    run_command("curl -s http://localhost:8000/health || echo 'API not responding'", 
                "API Health Check")
    
    # 5. Check database connection
    run_command('docker exec bdo-postgres psql -U orders_user -d orders_db -c "\\dt"', 
                "Database Tables")
    
    # 6. Check Kafka topics
    run_command("docker exec bdo-kcat kcat -b kafka:29092 -L", 
                "Kafka Topics List")
    
    # 7. Test message production and consumption
    print("\n=== Testing Kafka Message Flow ===")
    test_message = json.dumps({
        "order_id": f"diagnostic-{int(time.time())}",
        "user_id": "diag-user",
        "amount": 99.99,
        "country": "TEST",
        "created_at": "2025-09-28T12:00:00Z"
    })
    
    # Escape for shell
    escaped = test_message.replace("'", r"'\''")
    produce_cmd = f'docker exec -i bdo-kcat sh -lc "printf %s\\\\n \'{escaped}\' | kcat -b kafka:29092 -t orders -P"'
    
    if run_command(produce_cmd, "Test Message Production"):
        print("Waiting 3 seconds for consumer processing...")
        time.sleep(3)
        
        # Check consumer logs after message
        run_command("docker logs --tail 5 bdo-consumer", 
                    "Consumer Logs After Test Message")
        
        # Check if message was processed
        order_id = json.loads(test_message)["order_id"]
        run_command(f'docker exec bdo-postgres psql -U orders_user -d orders_db -c "SELECT * FROM orders WHERE order_id = \'{order_id}\';"', 
                    "Check Test Order in Database")
    
    print("\n" + "=" * 50)
    print("Diagnostic complete. Check the output above for any issues.")

if __name__ == "__main__":
    main()