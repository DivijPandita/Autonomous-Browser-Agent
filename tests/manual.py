"""
Quick manual smoke test - hits your locally running FastAPI server.
Usage (with the server already running via `uvicorn app.main:app --reload`):

    python tests/manual_run.py
"""
import time
import httpx

BASE_URL = "http://localhost:8000"


def main():
    payload = {
        "instruction": "Search for 'playwright python tutorial' and extract the titles of the first 3 results.",
        "start_url": "https://www.google.com",
    }
    r = httpx.post(f"{BASE_URL}/tasks", json=payload, timeout=30)
    r.raise_for_status()
    task = r.json()
    task_id = task["id"]
    print(f"Created task {task_id}, polling...")

    while True:
        r = httpx.get(f"{BASE_URL}/tasks/{task_id}", timeout=30)
        task = r.json()
        if task["status"] in ("success", "failed"):
            print("Final status:", task["status"])
            print("Result:", task["result"])
            print("Error:", task["error"])
            print("Steps taken:", len(task["steps"]))
            for s in task["steps"]:
                print(f"  {s['step_number']}. {s['action_type']} - {s['thought']}")
            break
        time.sleep(2)


if __name__ == "__main__":
    main()