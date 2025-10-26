"""
Manuscript API endpoints for file upload, management, and processing.
"""
import logging
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.core.dependencies import get_current_active_user
from app.core.response_formatter import ResponseFormatter
from app.models.user import User
from app.models.manuscript import (
    UploadUrlRequest,
    UploadUrlResponse,
    DownloadUrlResponse,
    ManuscriptCreate,
    ManuscriptUpdate,
    Manuscript,
    ManuscriptResponse,
    ManuscriptListResponse,
    ManuscriptStatus
)
from app.services.manuscript_service import manuscript_service
from app.services.docbook_conversion_service import docbook_conversion_service
from app.services.epub_conversion_service import epub_conversion_service
from app.services.s3_service import s3_service
from app.services.pdf_conversion_service import ConversionQuality
from app.models.manuscript import ManuscriptStatus, ManuscriptUpdate
from datetime import datetime
from app.services.activity_service import activity_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/manuscripts", tags=["Manuscript Management"])


@router.post("/upload-url", response_model=UploadUrlResponse)
async def generate_upload_url(
    request: UploadUrlRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Generate a pre-signed URL for uploading a PDF file to S3.
    
    This endpoint creates a manuscript record and returns a pre-signed URL
    that the client can use to upload the file directly to S3.
    """
    try:
        # Validate file size (10MB limit)
        max_file_size = 10 * 1024 * 1024  # 10MB in bytes
        if request.file_size and request.file_size > max_file_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size exceeds maximum limit of {max_file_size // (1024 * 1024)}MB"
            )
        
        # Generate unique S3 key
        file_extension = request.file_name.split('.')[-1].lower()
        subfolder = 'pdf' if file_extension == 'pdf' else 'epub'
        s3_key = f"manuscripts/{str(current_user.id)}/{subfolder}/{uuid.uuid4()}.{file_extension}"
        
        # Generate pre-signed upload URL
        upload_url = s3_service.generate_presigned_upload_url(
            key=s3_key,
            content_type=request.content_type,
            expires_in=3600  # 1 hour
        )
        
        if not upload_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate upload URL"
            )
        
        # Create manuscript record
        if file_extension == 'pdf':
            manuscript_data = ManuscriptCreate(
                user_id=str(current_user.id),
                file_name=request.file_name,
                pdf_s3_key=s3_key,
            )
        else:
            manuscript_data = ManuscriptCreate(
                user_id=str(current_user.id),
                file_name=request.file_name,
                epub_s3_key=s3_key,
            )
        
        manuscript = await manuscript_service.create_manuscript(manuscript_data)
        
        # Log activity
        await activity_service.log_activity(
            user_id=str(current_user.id),
            activity_type="manuscript_upload_initiated",
            description=f"Generated upload URL for {request.file_name}",
            metadata={
                "manuscript_id": str(manuscript.id),
                "file_name": request.file_name,
                "file_size": request.file_size
            }
        )
        
        response = UploadUrlResponse(
            upload_url=upload_url,
            manuscript_id=str(manuscript.id),
            expires_in=3600
        )
        
        return ResponseFormatter.success(
            data=response,
            message="Upload URL generated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate upload URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/{manuscript_id}/confirm-upload")
async def confirm_upload(
    manuscript_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Confirm that a file has been successfully uploaded to S3.
    
    This endpoint should be called after the client has successfully
    uploaded the file using the pre-signed URL.
    """
    try:
        # Get manuscript
        manuscript = await manuscript_service.get_manuscript_by_id(
            manuscript_id, 
            str(current_user.id)
        )
        
        if not manuscript:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Manuscript not found"
            )
        
        # Update manuscript status to indicate upload is complete
        # The status remains PENDING for processing
        
        # Log activity
        await activity_service.log_activity(
            user_id=str(current_user.id),
            activity_type="manuscript_uploaded",
            description=f"Successfully uploaded {manuscript.file_name}",
            metadata={
                "manuscript_id": manuscript_id,
                "file_name": manuscript.file_name
            }
        )
        
        return ResponseFormatter.success(
            message="Upload confirmed successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to confirm upload for manuscript {manuscript_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/", response_model=ManuscriptListResponse)
async def get_manuscripts(
    skip: int = Query(0, ge=0, description="Number of manuscripts to skip"),
    limit: int = Query(50, ge=1, le=100, description="Number of manuscripts to return"),
    status: Optional[ManuscriptStatus] = Query(None, description="Filter by status"),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get manuscripts for the current user with pagination and filtering.
    """
    try:
        # Get manuscripts
        manuscripts = await manuscript_service.get_manuscripts_by_user(
            user_id=str(current_user.id),
            skip=skip,
            limit=limit,
            status=status
        )
        
        # Get total count
        total = await manuscript_service.count_manuscripts_by_user(
            user_id=str(current_user.id),
            status=status
        )
        
        # Convert to response format
        manuscript_responses = [
            ManuscriptResponse(
                id=str(manuscript.id),
                file_name=manuscript.file_name,
                status=manuscript.status,
                upload_date=manuscript.upload_date.isoformat() if manuscript.upload_date else None,
                processing_completed_at=manuscript.processing_completed_at.isoformat() if manuscript.processing_completed_at else None,
                error_message=manuscript.error_message
            )
            for manuscript in manuscripts
        ]
        
        response = ManuscriptListResponse(
            manuscripts=manuscript_responses,
            total=total,
            page=skip // limit + 1,
            size=len(manuscript_responses)
        )
        
        return ResponseFormatter.success(
            data=response,
            message=f"Retrieved {len(manuscript_responses)} manuscripts"
        )
        
    except Exception as e:
        logger.error(f"Failed to get manuscripts for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


@router.get("/{manuscript_id}")
async def get_manuscript(
    manuscript_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a specific manuscript by ID.
    """
    try:
        manuscript = await manuscript_service.get_manuscript_by_id(
            manuscript_id, 
            str(current_user.id)
        )
        
        if not manuscript:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Manuscript not found"
            )
        
        # Convert to response format
        response = Manuscript(
            id=str(manuscript.id),
            user_id=str(manuscript.user_id),
            file_name=manuscript.file_name,
            status=manuscript.status,
            pdf_s3_key=manuscript.pdf_s3_key,
            docx_s3_key=manuscript.docx_s3_key,
            upload_date=manuscript.upload_date,
            processing_started_at=manuscript.processing_started_at,
            processing_completed_at=manuscript.processing_completed_at,
            error_message=manuscript.error_message,
            retry_count=manuscript.retry_count,
            file_size=manuscript.file_size,
            content_type=manuscript.content_type
        )
        
        return ResponseFormatter.success(
            data=response,
            message="Manuscript retrieved successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get manuscript {manuscript_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{manuscript_id}/download-url", response_model=DownloadUrlResponse)
async def generate_download_url(
    manuscript_id: str,
    file_type: str = Query("docx", regex="^(pdf|docx|xml|zip)$", description="File type to download"),
    current_user: User = Depends(get_current_active_user)
):
    """
    Generate a pre-signed URL for downloading a manuscript file.
    
    Args:
        manuscript_id: ID of the manuscript
        file_type: Type of file to download (pdf or docx)
    """
    try:
        manuscript = await manuscript_service.get_manuscript_by_id(
            manuscript_id, 
            str(current_user.id)
        )
        
        if not manuscript:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Manuscript not found"
            )
        
        # Determine S3 key and file name based on file type
        if file_type == "pdf":
            s3_key = manuscript.pdf_s3_key
            file_name = manuscript.file_name
        elif file_type == "docx":
            if not manuscript.docx_s3_key:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Converted document not available"
                )
            if manuscript.status != ManuscriptStatus.COMPLETE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Document conversion not completed"
                )
            s3_key = manuscript.docx_s3_key
            # Change extension to .docx
            base_name = manuscript.file_name.rsplit('.', 1)[0]
            file_name = f"{base_name}.docx"
        elif file_type == "xml":
            if not manuscript.xml_s3_key:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Converted document not available"
                )
            if manuscript.status != ManuscriptStatus.COMPLETE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Document conversion not completed"
                )
            s3_key = manuscript.xml_s3_key
            # Change extension to .xml
            base_name = manuscript.file_name.rsplit('.', 1)[0]
            file_name = f"{base_name}.xml"
        elif file_type == "zip":
            if not manuscript.xml_s3_key:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Converted package not available"
                )
            if manuscript.status != ManuscriptStatus.COMPLETE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Document conversion not completed"
                )
            s3_key = manuscript.xml_s3_key
            # xml_s3_key now points to .zip; preserve name
            file_name = Path(s3_key).name

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file type"
            )
        
        # Generate pre-signed download URL
        download_url = s3_service.generate_presigned_download_url(
            key=s3_key,
            expires_in=3600  # 1 hour
        )
        
        if not download_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate download URL"
            )
        
        # Log activity
        await activity_service.log_activity(
            user_id=str(current_user.id),
            activity_type="manuscript_downloaded",
            description=f"Generated download URL for {file_name}",
            metadata={
                "manuscript_id": manuscript_id,
                "file_name": file_name,
                "file_type": file_type
            }
        )
        
        response = DownloadUrlResponse(
            download_url=download_url,
            file_name=file_name,
            expires_in=3600
        )
        
        return ResponseFormatter.success(
            data=response,
            message="Download URL generated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate download URL for manuscript {manuscript_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.delete("/{manuscript_id}")
async def delete_manuscript(
    manuscript_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete a manuscript and its associated files.
    """
    try:
        # Get manuscript first to get S3 keys
        manuscript = await manuscript_service.get_manuscript_by_id(
            manuscript_id, 
            str(current_user.id)
        )
        
        if not manuscript:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Manuscript not found"
            )
        
        # Delete files from S3
        if manuscript.pdf_s3_key:
            s3_service.delete_file(manuscript.pdf_s3_key)
        
        if manuscript.docx_s3_key:
            s3_service.delete_file(manuscript.docx_s3_key)
        
        # Delete manuscript record
        deleted = await manuscript_service.delete_manuscript(manuscript_id, str(current_user.id))
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Manuscript not found"
            )
        
        # Log activity
        await activity_service.log_activity(
            user_id=str(current_user.id),
            activity_type="manuscript_deleted",
            description=f"Deleted manuscript {manuscript.file_name}",
            metadata={
                "manuscript_id": manuscript_id,
                "file_name": manuscript.file_name
            }
        )
        
        return ResponseFormatter.success(
            message="Manuscript deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete manuscript {manuscript_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/statistics/overview")
async def get_manuscript_statistics(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get manuscript statistics for the current user.
    """
    try:
        # Get user-specific statistics
        total = await manuscript_service.count_manuscripts_by_user(str(current_user.id))
        pending = await manuscript_service.count_manuscripts_by_user(str(current_user.id), ManuscriptStatus.PENDING)
        processing = await manuscript_service.count_manuscripts_by_user(str(current_user.id), ManuscriptStatus.PROCESSING)
        completed = await manuscript_service.count_manuscripts_by_user(str(current_user.id), ManuscriptStatus.COMPLETE)
        failed = await manuscript_service.count_manuscripts_by_user(str(current_user.id), ManuscriptStatus.FAILED)
        
        stats = {
            "total": total,
            "pending": pending,
            "processing": processing,
            "completed": completed,
            "failed": failed
        }
        
        return ResponseFormatter.success(
            data=stats,
            message="Statistics retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to get manuscript statistics for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/v1/manuscripts/{manuscript_id}/convert/docbook")
async def convert_to_docbook(
    manuscript_id: str,
    current_user: User = Depends(get_current_active_user),
):
    manuscript = await manuscript_service.get_manuscript_by_id(manuscript_id, user_id=str(current_user.id))
    if not manuscript or manuscript.status not in [ManuscriptStatus.PENDING, ManuscriptStatus.PROCESSING]:
        raise HTTPException(status_code=400, detail="Invalid manuscript status for conversion")

    # Mark processing start
    await manuscript_service.update_manuscript(
        manuscript_id,
        ManuscriptUpdate(
            status=ManuscriptStatus.PROCESSING,
            processing_started_at=datetime.utcnow(),
        ),
        user_id=str(current_user.id),
    )

    # Branch by input type
    base_name = manuscript.file_name.rsplit('.',1)[0]
    if manuscript.pdf_s3_key:
        # Run PDF -> DOCX (existing) -> DocBook (V4) -> Package ZIP
        xml_s3_key, meta = await docbook_conversion_service.convert_pdf_to_docbook(
            pdf_s3_key=manuscript.pdf_s3_key,
            output_filename=f"{base_name}.xml",
            quality=ConversionQuality.STANDARD,
            include_metadata=True,
        )
    elif manuscript.epub_s3_key:
        # Run EPUB -> DocBook (V4) -> Package ZIP
        xml_s3_key, meta = await epub_conversion_service.convert_epub_to_package(
            epub_s3_key=manuscript.epub_s3_key,
            output_basename=f"{base_name}.xml",
        )
    else:
        raise HTTPException(status_code=400, detail="No supported source found for conversion")

    # Update manuscript with XML + completion
    await manuscript_service.update_manuscript(
        manuscript_id,
        ManuscriptUpdate(
            status=ManuscriptStatus.COMPLETE,
            xml_s3_key=xml_s3_key,
            processing_completed_at=datetime.utcnow(),
        ),
        user_id=str(current_user.id),
    )

    return ResponseFormatter.success({
        "manuscript_id": manuscript_id,
        "xml_s3_key": xml_s3_key,
        "metadata": meta
    })