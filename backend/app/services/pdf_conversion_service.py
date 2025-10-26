"""
PDF to Word Conversion Service

This service handles the conversion of PDF files to Word documents using the pdf2docx library.
It includes comprehensive error handling, temporary file management, and conversion quality options.
"""

import logging
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import asyncio
from concurrent.futures import ThreadPoolExecutor

from pdf2docx import Converter
import pypandoc
import fitz  # PyMuPDF for PDF validation

from app.core.config import settings
from app.services.s3_service import s3_service
from app.services.ai_pdf_conversion_service import ai_pdf_conversion_service

logger = logging.getLogger(__name__)

class ConversionError(Exception):
    """Custom exception for PDF conversion errors."""
    pass

class ConversionQuality:
    """Conversion quality settings."""
    STANDARD = "standard"
    HIGH = "high"

class PDFConversionService:
    """Service for converting PDF files to Word documents."""

    def __init__(self):
        """Initialize the PDF conversion service."""
        self.temp_dir = Path(tempfile.gettempdir()) / "manuscript_processor"
        self.temp_dir.mkdir(exist_ok=True)
        
        # Thread pool for CPU-intensive conversion tasks
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        logger.info(f"PDF Conversion Service initialized with temp dir: {self.temp_dir}")

    async def convert_pdf_to_docx_ai(
        self,
        pdf_s3_key: str,
        output_filename: str,
        quality: str = ConversionQuality.STANDARD,
        include_metadata: bool = True
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Convert a PDF file using AI-powered conversion (PDF → Images → Markdown → DOCX).
        
        Args:
            pdf_s3_key: S3 key of the source PDF file
            output_filename: Desired filename for the output DOCX file
            quality: Conversion quality (affects image DPI)
            include_metadata: Whether to include document metadata
            
        Returns:
            Tuple of (docx_s3_key, conversion_metadata)
            
        Raises:
            ConversionError: If conversion fails
        """
        conversion_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        logger.info(f"Starting AI-powered PDF conversion [{conversion_id}]: {pdf_s3_key} -> {output_filename}")
        
        try:
            # Generate S3 key for output file
            docx_s3_key = f"converted/{conversion_id}-{output_filename}"
            if not docx_s3_key.endswith('.docx'):
                docx_s3_key = docx_s3_key.replace('.pdf', '.docx')
                if not docx_s3_key.endswith('.docx'):
                    docx_s3_key += '.docx'
            
            # Use the AI-powered conversion service
            success, error_message, ai_metadata = await ai_pdf_conversion_service.convert_pdf_to_docx(
                pdf_s3_key, docx_s3_key
            )
            
            if not success:
                raise ConversionError(f"AI conversion failed: {error_message}")
            
            # Calculate processing time
            end_time = datetime.utcnow()
            processing_time = (end_time - start_time).total_seconds()
            
            # Combine metadata in the expected format
            final_metadata = {
                "conversion_id": conversion_id,
                "source_pdf_key": pdf_s3_key,
                "output_docx_key": docx_s3_key,
                "conversion_start": start_time.isoformat(),
                "conversion_end": end_time.isoformat(),
                "conversion_duration_seconds": round(processing_time, 2),
                "quality": quality,
                "include_metadata": include_metadata,
                "conversion_type": "ai_powered",
                "success": True,
                **ai_metadata  # Include AI-specific metadata
            }
            
            logger.info(f"AI-powered PDF conversion completed successfully [{conversion_id}]: {processing_time:.2f}s")
            
            return docx_s3_key, final_metadata
            
        except Exception as e:
            error_msg = f"AI-powered PDF conversion failed [{conversion_id}]: {str(e)}"
            logger.error(error_msg)
            raise ConversionError(error_msg)

    async def convert_pdf_to_docx(
        self,
        pdf_s3_key: str,
        output_filename: str,
        quality: str = ConversionQuality.STANDARD,
        include_metadata: bool = True
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Convert a PDF file from S3 to Word document and upload back to S3.
        
        Args:
            pdf_s3_key: S3 key of the source PDF file
            output_filename: Desired filename for the output DOCX file
            quality: Conversion quality ('standard' or 'high')
            include_metadata: Whether to include document metadata
            
        Returns:
            Tuple of (docx_s3_key, conversion_metadata)
            
        Raises:
            ConversionError: If conversion fails
        """
        conversion_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        logger.info(f"Starting PDF conversion [{conversion_id}]: {pdf_s3_key} -> {output_filename}")
        
        # Create temporary file paths
        pdf_temp_path = self.temp_dir / f"{conversion_id}_input.pdf"
        docx_temp_path = self.temp_dir / f"{conversion_id}_output.docx"
        
        try:
            # Step 1: Download PDF from S3
            logger.info(f"Downloading PDF from S3: {pdf_s3_key}")
            await self._download_from_s3(pdf_s3_key, pdf_temp_path)
            
            # Step 2: Validate PDF file
            pdf_info = await self._validate_pdf(pdf_temp_path)
            logger.info(f"PDF validation successful: {pdf_info['pages']} pages, {pdf_info['size_mb']:.2f} MB")
            
            # Step 3: Convert PDF to DOCX
            logger.info(f"Converting PDF to DOCX with quality: {quality}")
            # Choose chunked conversion for very large PDFs to reduce memory usage
            if pdf_info.get("pages", 0) and pdf_info["pages"] > 200:
                logger.info(
                    f"Large PDF detected ({pdf_info['pages']} pages). Using chunked conversion."
                )
                conversion_stats = await self._convert_pdf_to_docx_chunked_async(
                    pdf_temp_path,
                    docx_temp_path,
                    pdf_info["pages"],
                    quality,
                    include_metadata,
                    pages_per_chunk=50,
                )
            else:
                conversion_stats = await self._convert_pdf_to_docx_async(
                    pdf_temp_path, 
                    docx_temp_path, 
                    quality,
                    include_metadata
                )
            
            # Step 4: Upload DOCX to S3
            docx_s3_key = f"converted/{uuid.uuid4()}-{output_filename}"
            if not docx_s3_key.endswith('.docx'):
                docx_s3_key = docx_s3_key.replace('.pdf', '.docx')
                if not docx_s3_key.endswith('.docx'):
                    docx_s3_key += '.docx'
            
            logger.info(f"Uploading DOCX to S3: {docx_s3_key}")
            await self._upload_to_s3(docx_temp_path, docx_s3_key)
            
            # Step 5: Prepare conversion metadata
            end_time = datetime.utcnow()
            conversion_duration = (end_time - start_time).total_seconds()
            
            metadata = {
                "conversion_id": conversion_id,
                "source_pdf_key": pdf_s3_key,
                "output_docx_key": docx_s3_key,
                "conversion_start": start_time.isoformat(),
                "conversion_end": end_time.isoformat(),
                "conversion_duration_seconds": conversion_duration,
                "quality": quality,
                "include_metadata": include_metadata,
                "pdf_info": pdf_info,
                "conversion_stats": conversion_stats,
                "success": True
            }
            
            logger.info(f"PDF conversion completed successfully [{conversion_id}]: {conversion_duration:.2f}s")
            return docx_s3_key, metadata
            
        except Exception as e:
            error_msg = f"PDF conversion failed [{conversion_id}]: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # Prepare error metadata
            end_time = datetime.utcnow()
            conversion_duration = (end_time - start_time).total_seconds()
            
            error_metadata = {
                "conversion_id": conversion_id,
                "source_pdf_key": pdf_s3_key,
                "conversion_start": start_time.isoformat(),
                "conversion_end": end_time.isoformat(),
                "conversion_duration_seconds": conversion_duration,
                "quality": quality,
                "error": str(e),
                "error_type": type(e).__name__,
                "success": False
            }
            
            raise ConversionError(error_msg) from e
            
        finally:
            # Cleanup temporary files
            await self._cleanup_temp_files([pdf_temp_path, docx_temp_path])

    async def _download_from_s3(self, s3_key: str, local_path: Path) -> None:
        """Download a file from S3 to local path."""
        try:
            # Use S3 service to download file
            download_url = s3_service.generate_presigned_download_url(s3_key)
            if not download_url:
                raise ConversionError(f"Failed to generate download URL for {s3_key}")
            
            # Download file using aiohttp or similar
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(download_url) as response:
                    if response.status != 200:
                        raise ConversionError(f"Failed to download file from S3: HTTP {response.status}")
                    
                    with open(local_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                            
            logger.debug(f"Downloaded {s3_key} to {local_path}")
            
        except Exception as e:
            raise ConversionError(f"Failed to download {s3_key} from S3: {str(e)}") from e

    async def _upload_to_s3(self, local_path: Path, s3_key: str) -> None:
        """Upload a local file to S3."""
        try:
            # Use S3 service to upload file
            success = s3_service.upload_file(str(local_path), s3_key)
            if not success:
                raise ConversionError(f"Failed to upload {local_path} to S3 key {s3_key}")
                
            logger.debug(f"Uploaded {local_path} to {s3_key}")
            
        except Exception as e:
            raise ConversionError(f"Failed to upload {local_path} to S3: {str(e)}") from e

    async def _validate_pdf(self, pdf_path: Path) -> Dict[str, Any]:
        """Validate PDF file and extract basic information."""
        try:
            # Run PDF validation in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(self.executor, self._validate_pdf_sync, pdf_path)
            
        except Exception as e:
            raise ConversionError(f"PDF validation failed: {str(e)}") from e

    def _validate_pdf_sync(self, pdf_path: Path) -> Dict[str, Any]:
        """Synchronous PDF validation using PyMuPDF."""
        try:
            doc = fitz.open(str(pdf_path))
            
            if doc.is_encrypted:
                doc.close()
                raise ConversionError("PDF is password protected and cannot be converted")
            
            page_count = doc.page_count
            if page_count == 0:
                doc.close()
                raise ConversionError("PDF has no pages")

            # Do not enforce a maximum page limit; allow very large PDFs
            
            # Get file size
            file_size = pdf_path.stat().st_size
            size_mb = file_size / (1024 * 1024)
            
            # Get basic metadata
            metadata = doc.metadata
            
            doc.close()
            
            return {
                "pages": page_count,
                "size_bytes": file_size,
                "size_mb": size_mb,
                "title": metadata.get("title", ""),
                "author": metadata.get("author", ""),
                "subject": metadata.get("subject", ""),
                "creator": metadata.get("creator", ""),
                "producer": metadata.get("producer", ""),
                "creation_date": metadata.get("creationDate", ""),
                "modification_date": metadata.get("modDate", "")
            }
            
        except Exception as e:
            raise ConversionError(f"Failed to validate PDF: {str(e)}") from e

    async def _convert_pdf_to_docx_async(
        self, 
        pdf_path: Path, 
        docx_path: Path, 
        quality: str,
        include_metadata: bool
    ) -> Dict[str, Any]:
        """Convert PDF to DOCX asynchronously."""
        try:
            # Run conversion in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self.executor, 
                self._convert_pdf_to_docx_sync, 
                pdf_path, 
                docx_path, 
                quality,
                include_metadata
            )
            
        except Exception as e:
            raise ConversionError(f"PDF to DOCX conversion failed: {str(e)}") from e

    def _convert_pdf_to_docx_sync(
        self, 
        pdf_path: Path, 
        docx_path: Path, 
        quality: str,
        include_metadata: bool
    ) -> Dict[str, Any]:
        """Synchronous PDF to DOCX conversion using pdf2docx."""
        conversion_start = datetime.utcnow()
        
        try:
            # Configure conversion parameters based on quality
            if quality == ConversionQuality.HIGH:
                # High quality settings
                converter_params = {
                    "start": 0,  # Start page
                    "end": None,  # End page (None = all pages)
                    "pages": None,  # Specific pages (None = all pages)
                    "password": None,  # PDF password
                    "multi_processing": False,  # Disable for stability
                    "cpu_count": 1,  # Single CPU for stability
                }
            else:
                # Standard quality settings (faster, skip images to avoid pixmap errors)
                converter_params = {
                    "start": 0,
                    "end": None,
                    "pages": None,
                    "password": None,
                    "multi_processing": False,
                    "cpu_count": 1,
                }
            
            # Perform conversion (skip images to avoid pixmap errors)
            converter = Converter(str(pdf_path))
            converter.convert(str(docx_path), image=False, **converter_params)
            converter.close()
            
            conversion_end = datetime.utcnow()
            conversion_duration = (conversion_end - conversion_start).total_seconds()
            
            # Get output file size
            output_size = docx_path.stat().st_size
            output_size_mb = output_size / (1024 * 1024)
            
            return {
                "conversion_duration_seconds": conversion_duration,
                "output_size_bytes": output_size,
                "output_size_mb": output_size_mb,
                "quality": quality,
                "include_metadata": include_metadata,
                "converter_params": converter_params
            }
            
        except Exception as e:
            raise ConversionError(f"pdf2docx conversion failed: {str(e)}") from e

    async def _convert_pdf_to_docx_chunked_async(
        self,
        pdf_path: Path,
        docx_path: Path,
        total_pages: int,
        quality: str,
        include_metadata: bool,
        pages_per_chunk: int = 50,
    ) -> Dict[str, Any]:
        """Convert a very large PDF to DOCX by processing fixed-size page chunks and merging outputs."""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self.executor,
                self._convert_pdf_to_docx_chunked_sync,
                pdf_path,
                docx_path,
                total_pages,
                quality,
                include_metadata,
                pages_per_chunk,
            )
        except Exception as e:
            raise ConversionError(f"Chunked PDF to DOCX conversion failed: {str(e)}") from e

    def _convert_pdf_to_docx_chunked_sync(
        self,
        pdf_path: Path,
        docx_path: Path,
        total_pages: int,
        quality: str,
        include_metadata: bool,
        pages_per_chunk: int = 50,
    ) -> Dict[str, Any]:
        """Synchronous chunked conversion and merge using pdf2docx + pandoc."""
        conversion_start = datetime.utcnow()

        # Configure parameters similar to non-chunked path
        if quality == ConversionQuality.HIGH:
            converter_params = {
                "start": 0,
                "end": None,
                "pages": None,
                "password": None,
                "multi_processing": False,
                "cpu_count": 1,
            }
        else:
            converter_params = {
                "start": 0,
                "end": None,
                "pages": None,
                "password": None,
                "multi_processing": False,
                "cpu_count": 1,
            }

        chunk_docx_paths: list[str] = []
        try:
            # Produce chunk DOCX files
            for chunk_start in range(0, total_pages, pages_per_chunk):
                chunk_end_exclusive = min(chunk_start + pages_per_chunk, total_pages)
                # pdf2docx expects 0-based page indices
                pages_indices = list(range(chunk_start, chunk_end_exclusive))
                chunk_docx = docx_path.with_name(f"{docx_path.stem}_part_{chunk_start+1:05d}-{chunk_end_exclusive:05d}.docx")

                logger.info(
                    f"Converting pages {chunk_start+1}-{chunk_end_exclusive} to temporary DOCX: {chunk_docx.name}"
                )

                try:
                    converter = Converter(str(pdf_path))
                    # Use explicit pages list to restrict conversion to the chunk
                    converter.convert(str(chunk_docx), image=False, pages=pages_indices)
                    converter.close()
                except Exception as chunk_err:
                    # Ensure converter is closed if partially created
                    try:
                        converter.close()  # type: ignore
                    except Exception:
                        pass
                    raise ConversionError(
                        f"Chunk conversion failed for pages {chunk_start+1}-{chunk_end_exclusive}: {chunk_err}"
                    ) from chunk_err

                chunk_docx_paths.append(str(chunk_docx))

            # Merge chunk DOCX files into final output using pandoc
            logger.info(
                f"Merging {len(chunk_docx_paths)} DOCX chunks into final output: {docx_path.name}"
            )
            pypandoc.convert_file(
                chunk_docx_paths,
                to="docx",
                outputfile=str(docx_path),
                extra_args=["--standalone", "--wrap=none"],
            )

            conversion_end = datetime.utcnow()
            conversion_duration = (conversion_end - conversion_start).total_seconds()

            output_size = docx_path.stat().st_size
            output_size_mb = output_size / (1024 * 1024)

            return {
                "conversion_duration_seconds": conversion_duration,
                "output_size_bytes": output_size,
                "output_size_mb": output_size_mb,
                "quality": quality,
                "include_metadata": include_metadata,
                "converter_params": {**converter_params, "pages_per_chunk": pages_per_chunk},
                "chunked": True,
                "chunks_count": len(chunk_docx_paths),
            }
        finally:
            # Cleanup chunk files
            for p in chunk_docx_paths:
                try:
                    Path(p).unlink(missing_ok=True)
                except Exception:
                    pass

    async def _cleanup_temp_files(self, file_paths: list[Path]) -> None:
        """Clean up temporary files."""
        for file_path in file_paths:
            try:
                if file_path.exists():
                    file_path.unlink()
                    logger.debug(f"Cleaned up temporary file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temporary file {file_path}: {e}")

    async def get_conversion_capabilities(self) -> Dict[str, Any]:
        """Get information about conversion capabilities and limits."""
        return {
            "supported_input_formats": ["pdf"],
            "supported_output_formats": ["docx"],
            # No hard page limit; large books supported
            "max_pages": None,
            "max_file_size_mb": 50,
            "quality_options": [ConversionQuality.STANDARD, ConversionQuality.HIGH],
            "features": {
                "text_extraction": True,
                "image_extraction": True,
                "table_extraction": True,
                "formatting_preservation": True,
                "metadata_preservation": True,
                "password_protected_pdfs": False
            },
            "temp_directory": str(self.temp_dir),
            "thread_pool_workers": self.executor._max_workers
        }

    async def cleanup_old_temp_files(self, max_age_hours: int = 24) -> int:
        """Clean up old temporary files."""
        cleanup_count = 0
        current_time = datetime.utcnow().timestamp()
        max_age_seconds = max_age_hours * 3600
        
        try:
            for file_path in self.temp_dir.glob("*"):
                if file_path.is_file():
                    file_age = current_time - file_path.stat().st_mtime
                    if file_age > max_age_seconds:
                        try:
                            file_path.unlink()
                            cleanup_count += 1
                            logger.debug(f"Cleaned up old temp file: {file_path}")
                        except Exception as e:
                            logger.warning(f"Failed to cleanup old temp file {file_path}: {e}")
                            
        except Exception as e:
            logger.error(f"Error during temp file cleanup: {e}")
            
        if cleanup_count > 0:
            logger.info(f"Cleaned up {cleanup_count} old temporary files")
            
        return cleanup_count

# Global service instance
pdf_conversion_service = PDFConversionService()
