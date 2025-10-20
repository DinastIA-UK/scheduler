# Scheduler API

> Send messages to the future

A webhook scheduling service built by DinastIA Community - the largest AI Agents community in Brazil.

This API allows you to schedule webhook calls for specific timestamps. Messages are stored in Redis and executed only once at the specified time.

## ✨ Features

- **Message Scheduling**: When you create a scheduled message, it's stored in Redis and added to the internal scheduler
- **One-time Execution**: Jobs are scheduled to run only once at the specified timestamp
- **Persistence**: On server restart, all messages from Redis are automatically restored and rescheduled
- **Cleanup**: After webhook execution, messages are automatically removed from Redis
- **Date-specific Scheduling**: Support for scheduling messages to exact future dates (using APScheduler)

## 🔧 Requirements

- Python 3.x
- Redis server running locally
- Required dependencies (install with `pip install -r requirements.txt`)

## 📦 Installation

1. Clone the repository:
```bash
git clone https://github.com/DinastIA-UK/scheduler.git
cd scheduler
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file with:
```env
# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_TOKEN=your-secret-token-here
```

## 🚀 Running

```bash
python scheduler_api.py
```

The server will start on `http://localhost:8000`

## 🔐 Authentication

All endpoints (except `/health`) require Bearer token authentication:

```
Authorization: Bearer your-secret-token-here
```

## 📡 API Endpoints

### Create Scheduled Message

**POST** `/messages`

Headers:
```
Authorization: Bearer your-secret-token-here
Content-Type: application/json
```

Body:
```json
{
  "id": "unique-message-id",
  "scheduleTo": "2024-12-25T10:30:00Z",
  "payload": {
    "data": "your webhook payload"
  },
  "webhookUrl": "https://your-webhook-endpoint.com"
}
```

Response:
```json
{
  "status": "scheduled",
  "messageId": "unique-message-id"
}
```

### List Scheduled Messages

**GET** `/messages`

Headers:
```
Authorization: Bearer your-secret-token-here
```

Response:
```json
{
  "scheduledJobs": [
    {
      "messageId": "unique-message-id",
      "nextRun": "2024-12-25T10:30:00+00:00",
      "trigger": "date[2024-12-25 10:30:00 UTC]"
    }
  ],
  "count": 1
}
```

### Delete Scheduled Message

**DELETE** `/messages/{message_id}`

Headers:
```
Authorization: Bearer your-secret-token-here
```

Response:
```json
{
  "status": "deleted",
  "messageId": "unique-message-id"
}
```

### Health Check

**GET** `/health`

No authentication required.

Response:
```json
{
  "status": "healthy",
  "redis": "connected",
  "scheduler": "running",
  "scheduled_jobs": 0
}
```

## ⚠️ Error Codes

- `401` - Missing or invalid authentication token
- `404` - Message not found (when deleting)
- `409` - Message with ID already exists (when creating)
- `500` - Internal server error

## 🐛 Bug Fixes

### Version 1.1.0 - APScheduler Migration

**Problem**: The previous implementation used the `schedule` library, which only supports recurring schedules (daily, weekly, etc.) and could not handle specific future dates. When scheduling a message for `2026-04-15T02:41:45Z`, it would incorrectly schedule for the next occurrence of that time (e.g., the next day at 02:41).

**Solution**: Migrated to `APScheduler` with `DateTrigger`, which properly supports one-time execution at specific timestamps in the future.

**Changes**:
- ✅ Replaced `schedule` library with `apscheduler`
- ✅ Added `pytz` for proper timezone handling
- ✅ Implemented `DateTrigger` for exact date scheduling
- ✅ Improved logging for better debugging
- ✅ Enhanced health check to include scheduler status

**Migration**: No breaking changes - API remains 100% compatible.

## 🧪 Testing

### Example: Schedule a message for 2026

```bash
curl -X POST http://localhost:8000/messages \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "test-2026",
    "scheduleTo": "2026-04-15T02:41:45.000Z",
    "payload": {
      "message": "This will be sent in 2026!"
    },
    "webhookUrl": "https://webhook.site/your-unique-id"
  }'
```

### Verify the scheduled date

```bash
curl -X GET http://localhost:8000/messages \
  -H "Authorization: Bearer your-token"
```

The `nextRun` field should correctly show `2026-04-15T02:41:45+00:00`.

## 📚 Dependencies

- `fastapi==0.104.1` - Modern web framework
- `uvicorn==0.24.0` - ASGI server
- `redis==5.0.1` - Redis client
- `requests==2.31.0` - HTTP library
- `pydantic==2.5.0` - Data validation
- `python-dotenv==1.0.0` - Environment variables
- `apscheduler==3.10.4` - Advanced job scheduling
- `pytz==2024.1` - Timezone handling

## 👥 About

This project is developed by [DinastIA Community](https://github.com/DinastIA-UK), the largest AI Agents community in Brazil, dedicated to advancing artificial intelligence and automation technologies.

## 📄 License

This project is licensed under the MIT License.