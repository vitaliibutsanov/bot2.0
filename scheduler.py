import time

def schedule_task(task, interval=60):
    while True:
        task()
        time.sleep(interval)
