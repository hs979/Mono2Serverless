# Static Analyzer Enhancement - File Upload Detection

## Changes Made

### Enhanced `tag_file()` Function

Added comprehensive detection for multiple architectural patterns:

#### 1. FileUpload Tag
Detects file upload functionality with patterns including:

**Python (Flask/FastAPI)**:
- `request.files`, `file.save()`, `UploadFile`
- `werkzeug.datastructures.FileStorage`
- `multipart/form-data`

**Node.js (Express)**:
- `multer`, `formidable`, `busboy`, `multiparty`, `express-fileupload`
- `req.files`, `req.file`, `upload.single()`, `upload.array()`

**Generic Patterns**:
- `file upload`, `image upload`, `avatar upload`, `document upload`
- `send_file`, `send_from_directory`, `/uploads/`
- `allowed_extensions`, `file_allowed`, `check_file_extension`

**S3 Upload Patterns**:
- `s3.upload`, `s3.putObject`, `upload_to_s3`
- `boto3.client('s3')`, `boto3.resource('s3')`

#### 2. WebSocket Tag
Detects real-time bidirectional communication:
- `websocket`, `ws://`, `wss://`
- `socket.io`, `socketio`
- `new WebSocket`, `ws.on()`, `io.on()`
- `@app.websocket` (FastAPI)

#### 3. AsyncTask Tag
Detects background job processing:

**Python**:
- `celery`, `@celery.task`, `@task`, `apply_async`, `delay()`
- `rq`, `redis-queue`, `dramatiq`, `huey`

**Node.js**:
- `bull`, `kue`, `agenda`, `bee-queue`
- `queue.add()`, `job.queue`

**Generic**:
- `task queue`, `job queue`, `async task`, `background task`, `worker`

#### 4. ScheduledTask Tag
Detects cron jobs and scheduled tasks:
- `cron`, `schedule`, `APScheduler`, `node-cron`, `node-schedule`
- `setInterval`, `crontab`, `cronjob`
- `@scheduled`, `schedule.every`

---

## How It Maps to Architecture Patterns

Based on the knowledge base patterns:

| Tag Detected | Suggests Pattern | Evidence For Service |
|--------------|------------------|---------------------|
| `FileUpload` | Pattern 1 or 3 | S3 bucket needed |
| `WebSocket` | Pattern 2 | API Gateway WebSocket API |
| `AsyncTask` | Pattern 3 | SQS (single consumer) or SNS (multiple consumers) |
| `ScheduledTask` | Pattern 3 or 4 | EventBridge Scheduler |
| `Auth` | Pattern 1 (baseline) | Cognito User Pools |
| `DynamoDB` | All patterns | DynamoDB (always required) |

---

## Integration with Architect Agent

The architect agent will now:

1. **Read `analysis_report.json`**:
   ```json
   {
     "file_tags": {
       "app.py": ["Auth", "FileUpload", "DynamoDB"],
       "tasks.py": ["AsyncTask", "DynamoDB"],
       "scheduler.py": ["ScheduledTask"]
     }
   }
   ```

2. **Consult Knowledge Base**:
   - `FileUpload` detected → Check Pattern 1 service list → Add S3
   - `AsyncTask` detected → Check Pattern 3 → Add SQS
   - `ScheduledTask` detected → Check Pattern 3/4 → Add EventBridge Scheduler
   - `WebSocket` detected → Select Pattern 2 → Use WebSocket API

3. **Apply Decision Rules** (from knowledge base):
   - **S3**: Add ONLY if `FileUpload` tag present
   - **SQS**: Add ONLY if `AsyncTask` tag present
   - **EventBridge**: Add ONLY if `ScheduledTask` tag present or more than 3 subscribers
   - **WebSocket API**: Use ONLY if `WebSocket` tag present

4. **Avoid Anti-Patterns**:
   - If no `AsyncTask` tag → Don't add SQS
   - If no `ScheduledTask` tag → Don't add EventBridge
   - If no `FileUpload` tag → Don't add S3

---

## Example Analysis Output

### Before Enhancement:
```json
{
  "file_tags": {
    "shopping-cart/app.py": ["Auth", "DynamoDB"]
  }
}
```

**Architect Decision**: Pattern 1, only Lambda + API Gateway + DynamoDB + Cognito

### After Enhancement:
```json
{
  "file_tags": {
    "shopping-cart/app.py": ["Auth", "DynamoDB", "FileUpload"],
    "shopping-cart/tasks.py": ["AsyncTask", "DynamoDB"]
  }
}
```

**Architect Decision**:
- Pattern 1 (baseline) + Pattern 3 elements
- Lambda + API Gateway + DynamoDB + Cognito (baseline)
- **+ S3** (because `FileUpload` detected)
- **+ SQS** (because `AsyncTask` detected)
- No EventBridge (no `ScheduledTask` detected)
- No Step Functions (no complex workflow detected)

---

## Testing

### Test Case 1: File Upload Detection (Python)
```python
# test_file.py
from flask import Flask, request
from werkzeug.utils import secure_filename

@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files['file']
    filename = secure_filename(file.filename)
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    return 'File uploaded'
```

**Expected Tags**: `["FileUpload"]`

### Test Case 2: File Upload Detection (Node.js)
```javascript
// test_file.js
const multer = require('multer');
const upload = multer({ dest: 'uploads/' });

app.post('/upload', upload.single('avatar'), (req, res) => {
  res.send('File uploaded');
});
```

**Expected Tags**: `["FileUpload"]`

### Test Case 3: WebSocket Detection
```python
# test_websocket.py
from fastapi import FastAPI, WebSocket

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_text("Hello")
```

**Expected Tags**: `["WebSocket"]`

### Test Case 4: Async Task Detection (Celery)
```python
# test_celery.py
from celery import Celery

app = Celery('tasks', broker='redis://localhost')

@app.task
def send_email(to, subject, body):
    # Send email logic
    pass
```

**Expected Tags**: `["AsyncTask"]`

### Test Case 5: Scheduled Task Detection
```python
# test_schedule.py
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()
scheduler.add_job(cleanup_expired_carts, 'cron', hour=2)
scheduler.start()
```

**Expected Tags**: `["ScheduledTask"]`

### Test Case 6: Combined Detection
```python
# test_combined.py
from flask import Flask, request
from celery import Celery
import boto3

s3 = boto3.client('s3')

@app.route('/upload', methods=['POST'])
def upload_to_s3():
    file = request.files['file']
    s3.upload_fileobj(file, 'my-bucket', file.filename)
    
    # Trigger async processing
    process_file.delay(file.filename)
    return 'File uploaded'

@celery.task
def process_file(filename):
    # Process file
    pass
```

**Expected Tags**: `["AsyncTask", "AWS_SDK", "FileUpload"]`

---

## Benefits

1. **Evidence-Based Design**: Architect makes decisions based on actual code patterns
2. **Avoids Over-Engineering**: Won't add S3/SQS/EventBridge without clear evidence
3. **Pattern-Driven**: Automatically suggests appropriate architecture pattern
4. **Comprehensive Detection**: Covers both Python and Node.js ecosystems
5. **Knowledge Base Alignment**: Tags directly map to knowledge base patterns

---

## Files Modified

1. `src/preprocessor/static_analyzer.py`:
   - Enhanced `tag_file()` function
   - Added 4 new tag types: `FileUpload`, `WebSocket`, `AsyncTask`, `ScheduledTask`
   - Comprehensive keyword detection for Python and Node.js

2. Related configurations (already updated):
   - `src/config/agents.yaml` (architect uses tags for decisions)
   - `src/config/tasks.yaml` (architect_blueprint task)
   - `knowledge/serverless_architecture_patterns.md` (patterns reference)
