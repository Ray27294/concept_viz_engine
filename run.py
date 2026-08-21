import subprocess
import sys
import time

def main():
    print("Starting Concept Viz Engine...")
    
    try:
        print("-> Starting Backend on port 8000...")
        backend_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--reload"],
            cwd="backend"
        )
        
        time.sleep(2)
        
        print("-> Starting Frontend...")
        frontend_process = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd="frontend",
            shell=True
        )
        
        print("\nSystem is running! Press Ctrl+C to stop.")
        
        backend_process.wait()
        frontend_process.wait()
        
    except KeyboardInterrupt:
        print("\n Shutting down...")
        backend_process.terminate()
        frontend_process.terminate()
        print("Goodbye!")

if __name__ == "__main__":
    main()