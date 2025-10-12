"""
Main FastAPI application.
"""
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import time
import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.core.database import connect_to_mongo, close_mongo_connection, get_database
from app.core.logging_config import setup_logging
from app.core.middleware import setup_middleware
from app.core.api_docs import setup_api_docs, get_api_info
from app.api import api_router
from app.services.conversion_service import ConversionService
from app.services.manuscript_service import manuscript_service
from app.models.manuscript import ManuscriptUpdate, ManuscriptStatus
from app.models.conversion import ConversionTaskCreate, ConversionQuality, ConversionStatus

import logging
logger = logging.getLogger(__name__)

async def process_manuscript_conversion(manuscript_id: str, task, conversion_service: ConversionService):
    """Process a single manuscript conversion in the background."""
    try:
        logger.info(f"🔄 Starting conversion for manuscript {manuscript_id}")
        
        # Process the conversion task
        result = await conversion_service.process_conversion_task(task)
        
        if result.status == ConversionStatus.COMPLETED:
            # Update manuscript status to complete with timestamp
            await manuscript_service.update_manuscript(
                manuscript_id, 
                ManuscriptUpdate(
                    status=ManuscriptStatus.COMPLETE, 
                    docx_s3_key=result.docx_s3_key,
                    processing_completed_at=datetime.utcnow()
                )
            )
            logger.info(f"✅ Successfully processed manuscript {manuscript_id}")
        else:
            # Update manuscript status to failed
            await manuscript_service.update_manuscript(
                manuscript_id, 
                ManuscriptUpdate(
                    status=ManuscriptStatus.FAILED, 
                    error_message=result.error_message,
                    processing_completed_at=datetime.utcnow()
                )
            )
            logger.error(f"❌ Failed to process manuscript {manuscript_id}: {result.error_message}")
            
    except Exception as e:
        logger.error(f"💥 Error in background conversion for manuscript {manuscript_id}: {e}")
        # Update manuscript status to failed with timestamp
        try:
            await manuscript_service.update_manuscript(
                manuscript_id, 
                ManuscriptUpdate(
                    status=ManuscriptStatus.FAILED,
                    error_message=str(e),
                    processing_completed_at=datetime.utcnow()
                )
            )
        except Exception as update_error:
            logger.error(f"Failed to update manuscript status after conversion error: {update_error}")


async def process_pending_manuscripts(conversion_service: ConversionService):
    """Background task to process pending manuscripts."""
    job_start_time = datetime.now()
    logger.info("📋 Manuscript processing job started")
    
    try:
        # Get pending manuscripts
        pending_manuscripts = await manuscript_service.get_pending_manuscripts(limit=5)
        
        if not pending_manuscripts:
            logger.info("📋 No pending manuscripts to process")
            return  # No pending manuscripts
            
        logger.info(f"📋 Found {len(pending_manuscripts)} pending manuscripts to process")
        
        # Process manuscripts one by one to avoid overwhelming the system
        for manuscript in pending_manuscripts:
            try:
                # Create conversion task first (while manuscript is still PENDING)
                task_data = ConversionTaskCreate(
                    manuscript_id=str(manuscript.id),
                    user_id=str(manuscript.user_id),
                    quality=ConversionQuality.STANDARD,
                    priority=1
                )
                task = await conversion_service.create_conversion_task(
                    task_data=task_data,
                    user_id=str(manuscript.user_id)
                )
                
                # Now update manuscript status to processing with timestamp
                await manuscript_service.update_manuscript(
                    str(manuscript.id), 
                    ManuscriptUpdate(
                        status=ManuscriptStatus.PROCESSING,
                        processing_started_at=datetime.utcnow()
                    )
                )
                logger.info(f"📝 Updated manuscript {manuscript.id} status to PROCESSING")
                
                # Start the conversion task in the background (non-blocking)
                asyncio.create_task(
                    process_manuscript_conversion(manuscript.id, task, conversion_service)
                )
                logger.info(f"🚀 Started background conversion for manuscript {manuscript.id}")
                    
            except Exception as e:
                logger.error(f"💥 Error setting up conversion for manuscript {manuscript.id}: {e}")
                # Update manuscript status to failed with timestamp
                try:
                    await manuscript_service.update_manuscript(
                        str(manuscript.id), 
                        ManuscriptUpdate(
                            status=ManuscriptStatus.FAILED,
                            error_message=f"Setup error: {str(e)}",
                            processing_completed_at=datetime.utcnow()
                        )
                    )
                except Exception as update_error:
                    logger.error(f"Failed to update manuscript status after setup error: {update_error}")
                    
    except Exception as e:
        logger.error(f"Error in process_pending_manuscripts: {e}")
    finally:
        job_duration = (datetime.now() - job_start_time).total_seconds()
        logger.info(f"📋 Manuscript processing job completed in {job_duration:.1f}s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    setup_logging()
    await connect_to_mongo()
    
    # Initialize and start the scheduler for manuscript processing
    scheduler = AsyncIOScheduler()
    conversion_service = ConversionService()
    
    # Add job to process pending manuscripts every 30 seconds
    # max_instances=1 ensures only one instance runs at a time (prevents overlaps)
    # coalesce=True means if multiple runs are missed, only execute once
    # misfire_grace_time=10 gives 10 seconds grace period for late starts
    scheduler.add_job(
        process_pending_manuscripts,
        trigger=IntervalTrigger(seconds=30),
        id='process_manuscripts',
        name='Process Pending Manuscripts',
        args=[conversion_service],
        max_instances=1,  # Prevent overlapping executions
        coalesce=True,    # If multiple runs are missed, only run once
        misfire_grace_time=10  # 10 second grace period for late starts
    )
    
    scheduler.start()
    print("📅 Manuscript processing scheduler started - checking every 30 seconds")
    
    yield
    
    # Shutdown
    scheduler.shutdown()
    await close_mongo_connection()


# Create FastAPI application
app = FastAPI(
    title="Manuscript Processor API",
    description="API for processing PDF manuscripts and converting them to Word documents",
    version="1.0.0",
    debug=settings.debug,
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=False,  # Must be False when allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add simple performance monitoring middleware
@app.middleware("http")
async def simple_performance_middleware(request: Request, call_next):
    """Simple performance monitoring middleware"""
    start_time = time.time()
    
    # Process request
    response = await call_next(request)
    
    # Performance tracking removed
    
    return response

# Setup middleware
setup_middleware(app)

# Setup API documentation
setup_api_docs(app)

# Include API routers with manuscript prefix
app.include_router(api_router, prefix="/xmlconverter/api")


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    api_info = get_api_info()
    return {
        "message": "Manuscript Processor API",
        "version": api_info["version"],
        "description": api_info["description"],
        "documentation": api_info["documentation"],
        "status": "running",
        "endpoints": {
            "health": "/xmlconverter/health",
            "api": "/xmlconverter/api/v1/",
            "docs": "/xmlconverter/docs"
        }
    }


@app.get("/xmlconverter/health", tags=["Health Check"])
async def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy", "message": "Manuscript Processor API is running"}


@app.get("/xmlconverter/health/detailed", tags=["Health Check"])
async def detailed_health_check():
    """Detailed health check with database and basic system status."""
    try:
        # Simple database check
        db = get_database()
        await db.command("ping")
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"
    
    return {
        "overall_status": "healthy" if db_status == "healthy" else "unhealthy",
        "checks": {
            "database": {"status": db_status},
            "api": {"status": "healthy"}
        }
    }




@app.get("/api-info", tags=["API Info"])
async def api_information():
    """Get comprehensive API information."""
    return get_api_info()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
