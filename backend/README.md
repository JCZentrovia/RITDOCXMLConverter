# Manuscript Processor Backend

FastAPI backend for the manuscript processing system.

## Setup

1. **Activate virtual environment:**
   ```bash
   source venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your MongoDB Atlas and AWS configuration:
   # - MongoDB Atlas connection details
   # - AWS region and S3 bucket name (no access keys needed for role-based access)
   ```

4. **Run development server:**
   ```bash
   python run.py
   # or
   uvicorn app.main:app --reload
   ```

## Project Structure

```
backend/
├── app/
│   ├── api/          # API route handlers
│   ├── core/         # Core functionality (config, database, security)
│   ├── models/       # Pydantic models
│   ├── services/     # Business logic services
│   └── main.py       # FastAPI application
├── venv/             # Python virtual environment
├── requirements.txt  # Python dependencies
├── .env.example      # Environment variables template
└── run.py           # Development server script
```

## API Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation

## Configuration

All configuration is handled through environment variables. See `.env.example` for available options.

### MongoDB Atlas Setup
- Create a MongoDB Atlas cluster
- Create a database user with read/write permissions
- Get the connection string in the format: `your-cluster.xxxxx.mongodb.net`
- Update `.env` with your cluster details

### AWS IAM Role Setup (Recommended)
For production deployments, use IAM roles instead of access keys:

1. **EC2 Instance Role**: Attach an IAM role to your EC2 instance with S3 permissions
2. **ECS Task Role**: For containerized deployments, assign IAM role to ECS tasks
3. **Lambda Execution Role**: For serverless deployments

Required S3 permissions:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::your-bucket-name",
                "arn:aws:s3:::your-bucket-name/*"
            ]
        }
    ]
}
```

### Local Development with AWS
For local development, you can use:
- AWS CLI configured with `aws configure`
- AWS credentials file (`~/.aws/credentials`)
- Environment variables (not recommended for production)

## Dependencies

- **FastAPI**: Modern web framework
- **Motor**: Async MongoDB driver
- **PyMongo**: MongoDB driver
- **python-jose**: JWT token handling
- **passlib**: Password hashing
- **boto3**: AWS S3 integration
- **APScheduler**: Task scheduling
- **pdf2docx**: PDF to Word conversion
