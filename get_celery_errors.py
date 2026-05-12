import redis
import json

r = redis.Redis(host='localhost', port=6379, db=0)
keys = r.keys('celery-task-meta-*')
for key in keys:
    data = json.loads(r.get(key))
    print(f"Task ID: {data.get('task_id')} | Status: {data.get('status')}")
    if data.get('status') == 'FAILURE':
        print(f"Error: {data.get('result')}")
        print(f"Traceback: {data.get('traceback')}")
    elif data.get('status') == 'SUCCESS':
        print(f"Result: {data.get('result')}")
    print("-" * 50)
