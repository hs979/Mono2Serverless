# Serverless Architecture Design Patterns

This document summarizes typical architecture patterns to guide the design of serverless architectures when converting monolithic applications.


## Five Typical Architecture Patterns

### Pattern 1: Simple REST API Pattern

**Use Case**: Applications with primarily CRUD operations, no complex business workflows, and no strict real-time requirements

**Core Services**:
- **API Gateway** (REST API) - Entry point
- **Lambda** - Business logic
- **DynamoDB** - Data storage
- **Cognito** - User authentication

**Communication Pattern**:
```
Client → API Gateway → Lambda → DynamoDB
          ↓
       Cognito (Auth)
```

**Service Checklist**:
- Required: Lambda
- Required: API Gateway REST API
- Required: DynamoDB
- Recommended: Cognito (for authentication)
- Required: CloudWatch (monitoring and logs)
- Recommended: X-Ray (tracing)
- Not Needed: Step Functions
- Not Needed: EventBridge
- Not Needed: SQS/SNS
- Optional: S3 (for static assets)

**Design Principles**:
1. All operations are synchronous request-response
2. Lambda functions are split by functionality
3. Use Cognito username as partition key for multi-tenancy isolation
4. Configure API Gateway usage plans and throttling

**When to Use**:
- Simple CRUD applications
- User actions return results immediately
- No long-running tasks
- No complex inter-service communication
- Avoid oversimplifying scenarios that need async processing

---

### Pattern 2: WebSocket Real-time Pattern

**Use Case**: Applications requiring real-time bidirectional communication, push notifications, collaborative features

**Core Services**:
- **API Gateway WebSocket** - WebSocket connection management
- **Lambda** - Event handlers
- **DynamoDB** - Connection state storage

**Communication Pattern**:
```
Client ←WebSocket→ API Gateway WebSocket
                        ↓
                   Lambda ($connect, $disconnect, custom routes)
                        ↓
                   DynamoDB (connection IDs)
                        ↓
                   API Gateway Management API (postToConnection)
```


**Service Checklist**:
- Required: Lambda
- Required: API Gateway WebSocket API
- Required: DynamoDB (store connection state)
- Required: CloudWatch
- Alternative: IoT Core (more powerful pub/sub)
- Usually Not Needed: EventBridge
- Not Needed: Step Functions

**Design Principles**:
1. Use DynamoDB to store active connectionIds
2. Scan DynamoDB to get all connections when broadcasting
3. Use API Gateway Management API's postToConnection to send messages
4. Handle 410 status (Gone) to clean up disconnected connections
5. Consider IoT Core for large-scale connections

**When to Use**:
- Chat applications, real-time notifications
- Collaborative editing, real-time dashboards
- Gaming, auction systems
- Not suitable for massive scale connections (consider IoT Core)

---

### Pattern 3: Event-Driven Fan-Out Pattern

**Use Case**: One event triggers multiple independent processing flows, parallel processing, decoupled microservices

**Core Services**:
- **S3** / **DynamoDB** - Event sources
- **SNS** - Event distribution
- **SQS** - Message queue (buffering)
- **Lambda** - Event processors

**Communication Pattern**:
```
S3 Event → SNS Topic → [SQS Queue 1 → Lambda 1]
                     → [SQS Queue 2 → Lambda 2]
                     → [SQS Queue 3 → Lambda 3]
                     
Or

DynamoDB Stream → Lambda → EventBridge → [Target 1, Target 2, ...]
```


**Service Checklist**:
- Required: Lambda
- Recommended: SNS (1:N distribution)
- Recommended: SQS (buffering and retry)
- Recommended: EventBridge (more powerful routing)
- Optional: DynamoDB Streams (CDC pattern)
- Optional: S3 (file events)
- Required: Dead Letter Queue (error handling)
- Not Needed: Step Functions (no orchestration)
- Usually Not Needed: API Gateway (typically no sync API)

**Design Principles**:
1. **SNS vs EventBridge Selection**:
   - SNS: Simple 1:N distribution, low latency
   - EventBridge: Complex routing rules, event filtering, schema registry
2. Use SQS as buffer between SNS and Lambda
3. Configure Dead Letter Queue to capture failed messages
4. Each processing flow is independent
5. Set CloudWatch alarms to monitor DLQ depth

**When to Use**:
- One event needs to trigger multiple independent actions
- Processing flows can execute in parallel
- Need to decouple different business functions
- Async processing is acceptable
- Not suitable when orchestration and flow control are needed (use Pattern 4)

**SNS vs EventBridge Decision**:
- SNS: Less than 5 subscribers, simple filtering, low cost
- EventBridge: More than 5 subscribers, complex routing, need event replay

---

### Pattern 4: Workflow Orchestration Pattern

**Use Case**: Complex business processes, long-running tasks, need retry and error handling, human approval

**Core Services**:
- **Step Functions** - Workflow orchestration
- **Lambda** - Task execution
- **DynamoDB** - State persistence
- **EventBridge** / **SNS** - Async notifications

**Communication Pattern**:
```
API Request → Step Functions State Machine
                ↓
            [Lambda Task 1] → [Lambda Task 2] → [Parallel Tasks] → [Choice]
                ↓                                                        ↓
            DynamoDB                                            Error Handler
                ↓
            SNS/EventBridge (completion notification)
```

**Service Checklist**:
- Required: Step Functions
- Required: Lambda (task execution)
- Recommended: DynamoDB (state storage)
- Recommended: SNS/EventBridge (workflow completion notification)
- Optional: SQS (DLQ)
- Optional: API Gateway (direct Step Functions integration)
- Optional: AppSync (GraphQL trigger)
- Avoid: Overuse Express workflows for short flows (use Standard)

**Design Principles**:
1. **Choose Standard vs Express Workflows**:
   - Standard: Long-running (more than 5 minutes), need audit trail, exactly-once
   - Express: High throughput (less than 5 minutes), at-least-once
2. **Task Token Pattern**: For human intervention (waitForTaskToken)
3. **Error Handling**: Retry + Catch + compensating transactions
4. **Direct Integration**: Prefer Service Integration (DynamoDB, SNS, SQS) over Lambda wrappers
5. **Parallel Processing**: Use Parallel state for independent tasks
6. **Timeout Settings**: Set reasonable timeout for each state

**When to Use**:
- Multi-step business processes (more than 3 steps)
- Need retry and error handling
- Need human approval or external system callbacks
- Need compensating transactions (Saga pattern)
- Long-running tasks (more than a few minutes)
- Not suitable for simple single-step operations (use Lambda directly)
- Not suitable for ultra-high throughput (more than 2000 TPS, consider Express + EventBridge)

**Difference from Pattern 3**:
- Pattern 3: Event-triggered, all flows independent and parallel, no dependencies
- Pattern 4: Orchestrated control, clear execution order and dependencies

---

### Pattern 5: Hybrid Microservices Pattern

**Use Case**: Large applications, multiple business domains, need service decoupling, sync + async hybrid communication

**Core Services**:
- **AppSync** / **API Gateway** - API layer
- **Lambda** - Microservice implementation
- **DynamoDB** - Service-private data
- **EventBridge** - Cross-service async communication
- **Step Functions** - Intra-service orchestration
- **SNS/SQS** - Message queue

**Communication Pattern**:
```
Frontend → AppSync/API Gateway
              ↓
        [Service A] ←REST/GraphQL→ [Service B]
              ↓                           ↓
        DynamoDB A                  DynamoDB B
              ↓                           ↓
        DDB Stream                  DDB Stream
              ↓                           ↓
        EventBridge ← - - - - - - - - - →
              ↓
        [Service C, D, E...] (async subscribers)
```

**Service Checklist**:
- Required: Lambda
- Required: API Gateway / AppSync
- Required: DynamoDB (one table per service)
- Required: EventBridge (inter-service communication)
- Recommended: DynamoDB Streams (CDC)
- Optional: Step Functions (intra-service orchestration)
- Optional: SNS/SQS (point-to-point communication)
- Recommended: SSM Parameter Store (service discovery)
- Optional: Redis/Neptune/OpenSearch (specialized databases)
- Required: CloudWatch, X-Ray (observability)

**Design Principles**:
1. **Service Boundaries**: Each service owns independent data storage, follow Database-per-Service pattern
2. **Communication Patterns**:
   - **Synchronous**: REST/GraphQL API (inter-service queries, e.g., validate product info)
   - **Asynchronous**: EventBridge events (inter-service state changes, e.g., OrderCreated)
3. **Service Discovery**: Use SSM Parameter Store to store service endpoints
4. **Data Consistency**: 
   - Strong consistency: Synchronous API calls + transactions
   - Eventual consistency: Async events + DynamoDB Streams
5. **Event Sourcing**: DynamoDB Stream → Lambda → EventBridge publishes domain events
6. **API Selection**:
   - AppSync: Frontend API, need GraphQL, subscriptions, real-time updates
   - API Gateway: Inter-service API, need REST, fine-grained control


**When to Use**:
- Large applications (more than 10 business functions)
- Multiple teams collaborating on development
- Need independent deployment and scaling
- Clear business domain boundaries
- Need to support multiple data access patterns
- Not suitable for small applications (consider Pattern 1 or monolith + modularization)
- Not suitable for team size less than 5

**Common Pitfalls**:
- Over-splitting services (one service per table)
- Too many synchronous calls between services causing latency accumulation
- Lack of unified observability
- Not considering distributed transactions and compensation

---

## Pattern Comparison Matrix

| Dimension | Pattern 1: Simple REST | Pattern 2: WebSocket | Pattern 3: Fan-Out | Pattern 4: Orchestration | Pattern 5: Microservices |
|------|----------------|------------------|---------------|------------|--------------|
| **Complexity** | Low | Low-Medium | Medium | Medium-High | High |
| **Service Count** | 3-5 | 3-4 | 5-8 | 5-10 | 10+ |
| **Communication** | Sync | WebSocket | Async | Sync+Async | Hybrid |
| **Data Consistency** | Strong | Eventual | Eventual | Optional | Eventual |
| **Cost** (relative) | $ | $$ | $$ | $$$ | $$$$ |
| **Team Size** | 1-2 | 1-2 | 2-3 | 3-5 | 5+ |
| **Suitable Scenarios** | CRUD apps | Real-time apps | Parallel processing | Complex workflows | Large systems |

---

## Architecture Design Decision Tree

```
Start: Analyze your application requirements
  ↓
Question 1: Need real-time bidirectional communication?
  ├─ Yes → Pattern 2: WebSocket Pattern
  └─ No → Continue
      ↓
Question 2: Have complex multi-step business processes?
  ├─ Yes → Need human approval or long-running?
  │       ├─ Yes → Pattern 4: Workflow Orchestration Pattern
  │       └─ No → Continue evaluation
  └─ No → Continue
      ↓
Question 3: One event triggers multiple independent processing flows?
  ├─ Yes → Pattern 3: Fan-Out Pattern
  └─ No → Continue
      ↓
Question 4: Multiple business domains need service splitting?
  ├─ Yes → Pattern 5: Hybrid Microservices Pattern
  └─ No → Pattern 1: Simple REST API Pattern
```

---

## Common Over-Engineering to Avoid

### 1. Overuse of Step Functions
**Wrong**: Wrapping all Lambda calls in Step Functions
```
API → Step Functions → Single Lambda → DynamoDB
```

**Correct**: Simple operations use Lambda directly
```
API → Lambda → DynamoDB
```

**When Step Functions are Needed**:
- More than 3 steps in workflow
- Need retry and error handling
- Need human approval
- Long-running tasks

---

### 2. Overuse of EventBridge
**Wrong**: Using EventBridge even with only 1-2 subscribers
```
Service A → EventBridge → Service B (only subscriber)
```

**Correct**: Point-to-point communication uses direct calls or SNS
```
Service A → API Gateway → Service B (synchronous)
Service A → SNS → Service B (asynchronous, simple scenario)
```

**When EventBridge is Needed**:
- More than 3 subscribers
- Need complex routing rules
- Need event filtering and transformation
- Need event replay and archiving

---

### 3. Over-splitting Microservices
**Wrong**: One microservice per DynamoDB table
```
UserService, UserProfileService, UserPreferenceService (3 services sharing user domain)
```

**Correct**: Split by business domain
```
UserService (includes profile, preference, and related functions)
```

**Service Splitting Principles**:
- By Business Capability
- By Bounded Context
- Consider team structure (Conway's Law)

---

### 4. Unnecessary SQS
**Wrong**: Adding SQS even for synchronous operations
```
API → Lambda → SQS → Lambda → DynamoDB → Response?
```

**Correct**: Synchronous operations use direct calls
```
API → Lambda → DynamoDB → Response
```

**When SQS is Needed**:
- Decoupling and buffering
- Handling traffic spikes
- Need retry mechanism
- Async task queues

---

### 5. Overuse of S3
**Wrong**: Storing all data in S3
```
GET /user/123 → Lambda → S3 (read user.json) → Parse and return
```

**Correct**: Structured data uses DynamoDB
```
GET /user/123 → Lambda → DynamoDB → Return
```

**S3 vs DynamoDB**:
- S3: Files, large objects, static assets, cold data
- DynamoDB: Structured data, hot data, fast queries

---

## Service Selection Checklist

### Lambda
- Required for all patterns
- Configure reasonable memory (128MB - 10GB)
- Configure reasonable timeout (based on actual needs, avoid 30s default)
- Use Lambda Layers for shared dependencies
- Enable X-Ray tracing

### API Gateway
- Use when REST API is needed
- Use when WebSocket is needed (WebSocket API)
- Consider AppSync as alternative (GraphQL scenarios)
- Configure Cognito or Lambda Authorizer
- Enable access logs and X-Ray tracing
- Set usage plans and throttling

### AppSync
- Use when frontend needs GraphQL
- Use when real-time subscriptions are needed
- Supports direct DynamoDB integration (VTL resolver)
- Supports Lambda resolver
- Supports HTTP data sources (can invoke Step Functions)

### DynamoDB
- Required for all patterns
- Single-table design vs multi-table design
- On-demand vs provisioned capacity (on-demand suitable for early stages)
- Enable Streams (CDC pattern)
- Enable TTL (auto cleanup expired data)
- Configure GSI (Global Secondary Indexes) for multiple query patterns

### Step Functions
- Multi-step workflows (more than 3 steps)
- Need retry and error handling
- Need human approval (waitForTaskToken)
- Long-running tasks
- Standard vs Express selection
- Prefer Service Integration over Lambda wrappers

### EventBridge
- More than 3 subscribers
- Complex routing rules
- Need event filtering and transformation
- Custom Event Bus vs Default Bus
- Configure DLQ to capture failed events
- Consider Schema Registry

### SNS
- Simple 1:N distribution (less than 5 subscribers)
- Low latency async notifications
- Configure SQS as subscribers (avoid Lambda throttling)
- Configure DLQ

### SQS
- Decoupling and buffering
- Handling traffic spikes
- Need retry mechanism
- Standard vs FIFO selection
- Configure reasonable visibility timeout
- Must configure DLQ

### S3
- File storage
- Static website hosting
- Data lake
- Configure lifecycle policies
- Configure event notifications (trigger Lambda/SNS)
- Enable versioning (optional)

### Cognito
- User authentication and authorization
- User Pool (user management)
- Identity Pool (temporary credentials)
- Supports OAuth 2.0 and OpenID Connect
- Supports MFA

### CloudWatch & X-Ray
- Required for all patterns
- Lambda auto-integration
- Configure custom metrics
- Configure alarms (DLQ depth, error rate, latency)
- Configure Dashboard
- Enable X-Ray tracing

---

## Migration Recommendations

### Progressive Path from Monolith to Serverless

#### Stage 1: Simple Modules → Pattern 1 (Simple REST API)
**Migration Target**: CRUD operations, simple query interfaces
**Steps**:
1. Identify stateless API endpoints
2. Extract data access layer, migrate to DynamoDB
3. Convert Controllers to Lambda functions
4. Use API Gateway to expose endpoints
5. Integrate Cognito authentication

---

#### Stage 2: Async Tasks → Pattern 3 (Fan-Out)
**Migration Target**: Background tasks, batch processing, message queues
**Steps**:
1. Identify async processing business logic
2. Use S3 or DynamoDB as trigger source
3. Use SNS/SQS to decouple producers and consumers
4. Convert each processor to independent Lambda

---

#### Stage 3: Complex Workflows → Pattern 4 (Workflow Orchestration)
**Migration Target**: Multi-step business processes, tasks requiring coordination
**Steps**:
1. Draw business process diagram
2. Identify steps, decision points, error handling
3. Design Step Functions state machine
4. Implement each step as Lambda or Service Integration
5. Implement compensation logic (Saga pattern)

---

#### Stage 4: Large Applications → Pattern 5 (Hybrid Microservices)
**Migration Target**: Entire application, multiple business domains
**Steps**:
1. Perform Domain-Driven Design (DDD), identify bounded contexts
2. Split services by business domain
3. Create independent CloudFormation/SAM templates for each service
4. Implement inter-service communication (sync API + async EventBridge)
5. Configure service discovery (SSM Parameter Store)
6. Implement distributed tracing and monitoring

---

### Anti-Pattern Warnings

#### Anti-Pattern 1: Direct Translation (Lift and Shift)
**Wrong Approach**: Package entire monolith as one Lambda function
```
Monolith.jar → Lambda (10000+ LOC, 3GB memory, 15 min timeout)
```
**Problems**: Slow cold start, hard to scale, hard to monitor, high cost

**Correct Approach**: Modularize first, then migrate gradually

---

#### Anti-Pattern 2: Distributed Monolith
**Wrong Approach**: Massive synchronous calls between services, tight coupling
```
Service A → Service B → Service C → Service D (all synchronous)
```
**Problems**: Latency accumulation, single point of failure, cascading failures

**Correct Approach**: Use async event communication, reduce synchronous dependencies

---

#### Anti-Pattern 3: Over-Serverlessification
**Wrong Approach**: Converting everything to Serverless, including unsuitable scenarios
```
Continuously running WebSocket server → Lambda (frequent invocations, high cost)
Big data analysis → Lambda (15 min timeout limit)
```
**Problems**: High cost, poor performance, many limitations

**Correct Approach**: Choose appropriate compute services based on workload characteristics
- Lambda: Event-driven, intermittent, short-running
- Fargate: Continuously running, long-running tasks
- EC2: Special requirements, need full control


## Monitoring and Observability

### Required Monitoring for All Patterns

#### CloudWatch Metrics
- Lambda: Invocation count, error rate, duration, concurrency
- API Gateway: Request count, latency, 4xx/5xx errors
- DynamoDB: Read/write capacity, throttling events
- Step Functions: Execution count, success rate, duration
- SQS: Message count, visibility timeout, DLQ depth

#### CloudWatch Alarms
- Lambda error rate more than 1%
- API Gateway latency more than p99
- DynamoDB throttling events more than 0
- SQS DLQ message count more than 0
- Step Functions failure rate more than 5%

#### X-Ray Tracing
- Enable tracing for all Lambda functions
- Enable API Gateway tracing
- Use X-Ray SDK to add custom annotations

#### CloudWatch Logs Insights Queries
```sql
-- Lambda error logs
fields @timestamp, @message
| filter @type = "ERROR"
| sort @timestamp desc
| limit 100

-- API Gateway slow requests
fields @timestamp, requestId, ip, requestTime
| filter requestTime > 1000
| sort requestTime desc
| limit 20

-- Step Functions failed executions
fields @timestamp, executionArn, cause
| filter status = "FAILED"
| sort @timestamp desc
```

#### Dashboard Example
```
┌────────────────────────────────────────────────┐
│ Serverless Application Dashboard              │
├────────────────────────────────────────────────┤
│ [Lambda Invocations] [Lambda Errors]          │
│ [API Latency p50/p99] [API Error Rate]        │
│ [DynamoDB Read/Write] [DynamoDB Throttles]     │
│ [SQS Messages]        [DLQ Depth]              │
│ [Step Functions]      [EventBridge Events]     │
└────────────────────────────────────────────────┘
```
