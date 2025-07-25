import json
import os
import time
import threading
from datetime import datetime
from typing import Dict, Any
import redis
import requests
import schedule
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Scheduler API", version="1.0.0")

API_TOKEN = os.getenv('API_TOKEN')

def verify_token(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    token = authorization.replace("Bearer ", "")
    if token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return token

redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    password=os.getenv('REDIS_PASSWORD'),
    decode_responses=True
)

class ScheduleMessage(BaseModel):
    id: str
    scheduleTo: str
    payload: Dict[str, Any]
    webhookUrl: str

def fire_webhook(message_id: str, webhook_url: str, payload: Dict[str, Any]):
    try:
        response = requests.post(webhook_url, json=payload, timeout=30)
        response.raise_for_status()
        print(f"Webhook fired successfully for message {message_id}")
    except Exception as e:
        print(f"Failed to fire webhook for message {message_id}: {e}")
    finally:
        redis_client.delete(f"message:{message_id}")
        print(f"Message {message_id} cleaned from Redis")

def schedule_message(message_id: str, schedule_timestamp: str, webhook_url: str, payload: Dict[str, Any]):
    schedule_time = datetime.fromisoformat(schedule_timestamp.replace('Z', '+00:00'))
    current_time = datetime.now(schedule_time.tzinfo)
    
    if schedule_time <= current_time:
        fire_webhook(message_id, webhook_url, payload)
        return
    
    def job():
        fire_webhook(message_id, webhook_url, payload)
        return schedule.CancelJob
    
    schedule.every().day.at(schedule_time.strftime("%H:%M")).do(job).tag(message_id)

def scheduler_worker():
    while True:
        schedule.run_pending()
        time.sleep(1)

def restore_scheduled_messages():
    try:
        keys = redis_client.keys("message:*")
        restored_count = 0
        
        for key in keys:
            try:
                message_data = json.loads(redis_client.get(key))
                message_id = message_data["id"]
                schedule_to = message_data["scheduleTo"]
                webhook_url = message_data["webhookUrl"]
                payload = message_data["payload"]
                
                schedule_message(message_id, schedule_to, webhook_url, payload)
                restored_count += 1
                print(f"[{datetime.now().isoformat()}] Restored scheduled message - ID: {message_id}")
                
            except Exception as e:
                print(f"[{datetime.now().isoformat()}] Failed to restore message {key}: {e}")
        
        print(f"[{datetime.now().isoformat()}] Restored {restored_count} scheduled messages from Redis")
        
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] Error restoring messages: {e}")

restore_scheduled_messages()

scheduler_thread = threading.Thread(target=scheduler_worker, daemon=True)
scheduler_thread.start()

@app.post("/messages")
async def create_scheduled_message(message: ScheduleMessage, token: str = Depends(verify_token)):
    try:
        redis_key = f"message:{message.id}"
        
        if redis_client.exists(redis_key):
            print(f"[{datetime.now().isoformat()}] Message already exists in Redis - ID: {message.id}")
            raise HTTPException(status_code=409, detail="Message with this ID already exists")
        
        message_data = {
            "id": message.id,
            "scheduleTo": message.scheduleTo,
            "payload": message.payload,
            "webhookUrl": message.webhookUrl
        }
        
        redis_client.set(redis_key, json.dumps(message_data))
        print(f"[{datetime.now().isoformat()}] Message inserted to Redis - ID: {message.id}")
        
        schedule_message(message.id, message.scheduleTo, message.webhookUrl, message.payload)
        
        return {"status": "scheduled", "messageId": message.id}
    
    except HTTPException as http_exc:
        print(f"[{datetime.now().isoformat()}] HTTPException in create: {http_exc.status_code} - {http_exc.detail}")
        raise
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] Unexpected exception in create: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to schedule message: {str(e)}")

@app.delete("/messages/{message_id}")
async def delete_scheduled_message(message_id: str, token: str = Depends(verify_token)):
    try:
        redis_key = f"message:{message_id}"
        
        if not redis_client.exists(redis_key):
            print(f"[{datetime.now().isoformat()}] Message not found in Redis - ID: {message_id}")
            raise HTTPException(status_code=404, detail="Message not found")
        
        redis_client.delete(redis_key)
        
        schedule.clear(message_id)
        
        return {"status": "deleted", "messageId": message_id}
    
    except HTTPException as http_exc:
        print(f"[{datetime.now().isoformat()}] HTTPException in delete: {http_exc.status_code} - {http_exc.detail}")
        raise
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] Unexpected exception in delete: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete message: {str(e)}")

@app.get("/messages")
async def list_scheduled_messages(token: str = Depends(verify_token)):
    try:
        jobs = []
        for job in schedule.jobs:
            jobs.append({
                "messageId": list(job.tags)[0] if job.tags else "unknown",
                "nextRun": job.next_run.isoformat() if job.next_run else None,
                "job": str(job.job_func)
            })
        
        return {"scheduledJobs": jobs, "count": len(jobs)}
    
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] Error listing jobs: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list jobs: {str(e)}")

@app.get("/health")
async def health_check():
    try:
        redis_client.ping()
        return {"status": "healthy", "redis": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "redis": "disconnected", "error": str(e)}

if __name__ == "__main__":
    print(f"[{datetime.now().isoformat()}] Starting Scheduler API server")
    uvicorn.run(app, host="0.0.0.0", port=8000)