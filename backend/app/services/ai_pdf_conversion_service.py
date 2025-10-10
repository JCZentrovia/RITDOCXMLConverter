"""
AI-powered PDF to DOCX conversion service.

This service implements a sophisticated conversion pipeline:
1. PDF → JPG images (using pdf2image)
2. JPG → Markdown (using OpenAI Vision API)
3. Markdown → DOCX (using pypandoc)
"""

import os
import gc
import tempfile
import shutil
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# PDF to image conversion
from pdf2image import convert_from_path
from PIL import Image

# OpenAI for image to markdown conversion
import openai
from openai import AsyncOpenAI

# Markdown to DOCX conversion
import pypandoc

# Core imports
from app.core.config import settings
from app.core.logging_config import LoggingContext
from app.services.s3_service import s3_service

logger = logging.getLogger(__name__)

# Configuration constants
DEFAULT_DPI = 300
DEFAULT_BATCH_SIZE = 5
DEFAULT_JPEG_QUALITY = 95
MAX_IMAGE_SIZE = 1500  # Max dimension for images


class PromptManager:
    """Manages shared prompts for AI image processing"""
    
    @staticmethod
    def get_user_prompt() -> str:
        """Get the user prompt for Markdown generation"""
        return """
Your goal is to generate well-structured, complete Markdown content from this image without omitting any details. Follow these steps and guidelines carefully:

1. Analyze the image content thoroughly:
   - Identify key elements such as text blocks, figures, lists, mathematical expressions, tables, and headings.
   - Map out the logical structure of the document.
   - Pay special attention to identifying all figures and their captions in the PDF image.

2. Generate Markdown structure:
   - Logical reading order must be maintained.
   - Remove only soft hyphens — i.e., hyphens at the end of a line that are followed by a line break and the continuation of the same word.
   - Use standard Markdown syntax for all elements.
   - The structure must strictly follow the content in the provided PDF image, with no deviations.

3. Content conversion guidelines:
   - **Headings**: Use # ## ### #### ##### ###### for different heading levels
   - **Lists**: Use - for unordered lists, 1. 2. 3. for ordered lists
   - **Tables**: Use standard Markdown table syntax with | separators
   - **Bold text**: Use **bold text** syntax
   - **Italic text**: Use *italic text* syntax
   - **Code blocks**: Use ```language for code blocks, `inline code` for inline code
   - **Links**: Use [link text](URL) format
   - **Images**: Use ![alt text](image_reference) format

4. Mathematical content:
   - For inline math: Use $LaTeX syntax$
   - For display math: Use $$LaTeX syntax$$
   - Ensure LaTeX accurately reflects the structure of the math expression, including symbols, operators, and formatting.
   - Convert all mathematical expressions from the image to proper LaTeX syntax.

5. Figure and image handling:
   - Use ![descriptive alt text](figure_reference) for each figure
   - Include detailed, meaningful descriptions in the alt text
   - Add figure captions as regular text below the image reference
   - Reference figures appropriately in the text

6. Table conversion:
   - Convert all tables to standard Markdown table format
   - Ensure proper alignment and formatting
   - Maintain all data from the original table

7. Text formatting:
   - Preserve all text formatting (bold, italic, etc.)
   - Maintain paragraph breaks and spacing
   - Keep the original text hierarchy and structure

8. Quality assurance:
   - Ensure no content has been omitted, abbreviated, or summarized.
   - Every piece of text, figure, table, and mathematical expression must be captured.
   - Maintain the exact order and structure as shown in the image.

9. Calculate a confidence score between 0-100 based on the accuracy, completeness, and proper formatting of your Markdown output.

Remember:
- Absolutely no content can be omitted, abbreviated, or summarized under any circumstances.
- Each part of the PDF image must be captured exactly as it appears, even if it is repetitive or seems trivial.
- Do not use placeholders or comments like <!-- Similar structure continues -->.
- Every instance of a similar or repeating pattern must be fully expanded in the generated Markdown.
- The generated Markdown should be clean, well-formatted, and follow standard Markdown conventions.
- All mathematical expressions must be converted to LaTeX syntax.
- All figures must have descriptive alt text and proper referencing.

Begin your response with generating the Markdown content.
"""
    
    @staticmethod
    def get_system_prompt() -> str:
        """Get the system prompt for AI models"""
        return """
You are an advanced AI system designed to process PDF page images and generate complete, well-formatted Markdown content. 
Do not resize, crop, or alter the image in any way. 
Your task is crucial for converting PDF documents to accessible, searchable Markdown format with proper LaTeX math formatting. 
"""
    
    @staticmethod
    def get_tool_schema() -> List[Dict[str, Any]]:
        """Get the tool schema for structured output"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "generate_markdown",
                    "description": "Generates Markdown content as per the guidelines provided in the user query with a confidence score and reasoning.",
                    "parameters": {
                    "type": "object",
                    "properties": {
                        "score": {
                            "type": "number",
                            "description": "Confidence score of the generated Markdown content, typically between 0 and 100."
                        },
                        "markdown": {
                            "type": "string",
                            "description": "The complete Markdown content generated as per the guidelines provided in the user query."
                        },
                        "figures": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "reference": {
                                        "type": "string",
                                        "description": "The reference used in the markdown (e.g., figure_1, image_2)."
                                    },
                                    "description": {
                                        "type": "string",
                                        "description": "IMPORTANT: MUST always be written in clear, precise English, regardless of the document language."
                                    },
                                    "caption": {
                                        "type": "string",
                                        "description": "The caption text for the figure, if present."
                                    }
                                },
                                "required": ["reference", "description"]
                            },
                            "description": "An array of objects containing figure references and descriptions."
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Brief explanation of the confidence score and any challenges faced during generation."
                        }
                    },
                    "required": ["score", "markdown", "figures", "reasoning"]
                    }
                }
            }
        ]


class AIPDFConversionService:
    """AI-powered PDF to DOCX conversion service"""
    
    def __init__(self):
        self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        
    async def convert_to_images(self, pdf_path: str, output_dir: str, page_numbers_list: List[int], dpi: int = DEFAULT_DPI) -> List[str]:
        """
        Convert PDF pages to JPG images with specified DPI using batch processing to handle large PDFs
        
        Args:
            pdf_path: Path to the PDF file
            output_dir: Directory to save images
            page_numbers_list: List of page numbers to convert (1-based)
            dpi: DPI for image conversion
            
        Returns:
            List of paths to created image files
        """
        image_paths = []
        
        try:
            # Sort page numbers for efficient processing
            sorted_pages = sorted(page_numbers_list)
            total_pages = len(sorted_pages)
            
            logger.info(f"Converting {total_pages} PDF pages to images at {dpi} DPI using batch size {DEFAULT_BATCH_SIZE}...")
            
            # Process pages in batches to avoid memory issues
            for batch_start in range(0, len(sorted_pages), DEFAULT_BATCH_SIZE):
                batch_end = min(batch_start + DEFAULT_BATCH_SIZE, len(sorted_pages))
                batch_pages = sorted_pages[batch_start:batch_end]
                
                # Get the actual page range for pdf2image (1-based)
                first_page = batch_pages[0]
                last_page = batch_pages[-1]
                
                logger.info(f"Processing batch {batch_start//DEFAULT_BATCH_SIZE + 1}: pages {first_page}-{last_page} ({len(batch_pages)} pages)")
                
                try:
                    # Convert only the pages in this batch (run in executor to avoid blocking)
                    loop = asyncio.get_event_loop()
                    batch_images = await loop.run_in_executor(
                        None,  # Use default ThreadPoolExecutor
                        lambda: convert_from_path(
                            pdf_path, 
                            dpi=dpi, 
                            fmt='JPEG', 
                            use_cropbox=True, 
                            size=MAX_IMAGE_SIZE,
                            first_page=first_page,
                            last_page=last_page
                        )
                    )
                    
                    # Save images from this batch
                    for i, image in enumerate(batch_images):
                        actual_page_num = first_page + i
                        if actual_page_num in page_numbers_list:
                            image_filename = f"page{actual_page_num:04d}.jpg"
                            image_path = os.path.join(output_dir, image_filename)
                            image.save(image_path, 'JPEG', quality=DEFAULT_JPEG_QUALITY)
                            image_paths.append(image_path)
                            logger.info(f"Saved page {actual_page_num} as {image_filename}")
                    
                    # Clear batch images from memory and force garbage collection
                    del batch_images
                    gc.collect()  # Force garbage collection to free memory
                    
                    logger.info(f"Completed batch {batch_start//DEFAULT_BATCH_SIZE + 1}/{(len(sorted_pages) + DEFAULT_BATCH_SIZE - 1)//DEFAULT_BATCH_SIZE}")
                    
                except Exception as batch_error:
                    logger.error(f"Error processing batch {batch_start//DEFAULT_BATCH_SIZE + 1} (pages {first_page}-{last_page}): {str(batch_error)}")
                    # Force garbage collection even on error to free any partial memory
                    gc.collect()
                    # Continue with next batch instead of failing completely
                    continue
            
            logger.info(f"Successfully converted {len(image_paths)} pages to images")
            return image_paths
            
        except Exception as e:
            logger.error(f"Error converting PDF to images: {str(e)}")
            return []

    def convert_image_to_markdown_sync(self, image_path: str, page_number: int) -> Dict[str, Any]:
        """
        Convert a single image to markdown using OpenAI Vision API (synchronous version for threading)
        
        Args:
            image_path: Path to the image file
            page_number: Page number for logging
            
        Returns:
            Dictionary containing markdown content, score, figures, and reasoning
        """
        try:
            # Read and encode image
            with open(image_path, "rb") as image_file:
                import base64
                image_data = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Prepare the message for OpenAI
            messages = [
                {
                    "role": "system",
                    "content": PromptManager.get_system_prompt()
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": PromptManager.get_user_prompt()
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ]
            
            # Create a synchronous OpenAI client for threading
            import openai
            sync_client = openai.OpenAI(api_key=self.openai_client.api_key)
            
            # Call OpenAI API with structured output
            response = sync_client.chat.completions.create(
                model="gpt-4o",  # Use GPT-4 Vision model
                messages=messages,
                tools=PromptManager.get_tool_schema(),
                tool_choice={"type": "function", "function": {"name": "generate_markdown"}},
                max_tokens=4000,
                temperature=0.1
            )
            
            # Extract the structured response
            tool_call = response.choices[0].message.tool_calls[0]
            import json
            result = json.loads(tool_call.function.arguments)  # Parse the JSON response
            
            logger.info(f"Generated markdown for page {page_number} with confidence score: {result.get('score', 0)}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error converting page {page_number} to markdown: {str(e)}")
            return {
                "score": 0,
                "markdown": f"# Error Processing Page {page_number}\n\nFailed to process image: {str(e)}",
                "figures": [],
                "reasoning": f"Error occurred during processing: {str(e)}"
            }

    async def convert_image_to_markdown(self, image_path: str) -> Dict[str, Any]:
        """
        Convert a single image to markdown using OpenAI Vision API
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dictionary containing markdown content, score, figures, and reasoning
        """
        try:
            # Read and encode image
            with open(image_path, "rb") as image_file:
                import base64
                image_data = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Prepare the message for OpenAI
            messages = [
                {
                    "role": "system",
                    "content": PromptManager.get_system_prompt()
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": PromptManager.get_user_prompt()
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ]
            
            # Call OpenAI API with structured output
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o",  # Use GPT-4 Vision model
                messages=messages,
                tools=PromptManager.get_tool_schema(),
                tool_choice={"type": "function", "function": {"name": "generate_markdown"}},
                max_tokens=4000,
                temperature=0.1
            )
            
            # Extract the structured response
            tool_call = response.choices[0].message.tool_calls[0]
            import json
            result = json.loads(tool_call.function.arguments)  # Parse the JSON response
            
            logger.info(f"Generated markdown for {os.path.basename(image_path)} with confidence score: {result.get('score', 0)}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error converting image {image_path} to markdown: {str(e)}")
            return {
                "score": 0,
                "markdown": f"# Error Processing Page\n\nFailed to process image: {str(e)}",
                "figures": [],
                "reasoning": f"Error occurred during processing: {str(e)}"
            }

    async def convert_images_to_markdown_threaded(self, image_paths: List[str], max_workers: int = 5) -> List[Dict[str, Any]]:
        """
        Convert multiple images to markdown using OpenAI Vision API with threading
        
        Args:
            image_paths: List of paths to image files
            max_workers: Maximum number of concurrent threads (default: 5)
            
        Returns:
            List of dictionaries containing markdown content for each image
        """
        logger.info(f"Converting {len(image_paths)} images to markdown using {max_workers} threads...")
        
        # Prepare results list with correct ordering
        results = [None] * len(image_paths)
        
        def process_image_wrapper(index_and_path):
            index, image_path = index_and_path
            page_number = index + 1
            return index, self.convert_image_to_markdown_sync(image_path, page_number)
        
        # Use asyncio-compatible ThreadPoolExecutor to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks to the executor
            tasks = []
            for i, path in enumerate(image_paths):
                task = loop.run_in_executor(
                    executor, 
                    process_image_wrapper, 
                    (i, path)
                )
                tasks.append(task)
            
            # Wait for all tasks to complete (non-blocking)
            completed_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for task_result in completed_results:
                if isinstance(task_result, Exception):
                    # Handle exception
                    logger.error(f"Error processing image: {str(task_result)}")
                    # Find the index for this failed task (approximate)
                    error_index = len([r for r in results if r is not None])
                    if error_index < len(results):
                        results[error_index] = {
                            "score": 0,
                            "markdown": f"# Error Processing Page {error_index + 1}\n\nFailed to process image: {str(task_result)}",
                            "figures": [],
                            "reasoning": f"Error occurred during processing: {str(task_result)}"
                        }
                else:
                    # Handle successful result
                    index, result = task_result
                    results[index] = result
                    logger.info(f"Completed page {index + 1}/{len(image_paths)}")
        
        logger.info(f"Completed all {len(image_paths)} images with threading")
        return results

    def combine_markdown_files(self, markdown_results: List[Dict[str, Any]]) -> str:
        """
        Combine multiple markdown results into a single document
        
        Args:
            markdown_results: List of markdown conversion results
            
        Returns:
            Combined markdown content
        """
        combined_content = []
        
        # Add document header
        combined_content.append("# Converted Document")
        combined_content.append("")
        combined_content.append(f"*Converted on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        combined_content.append("")
        
        # Add each page
        for i, result in enumerate(markdown_results, 1):
            combined_content.append(f"## Page {i}")
            combined_content.append("")
            combined_content.append(result.get("markdown", ""))
            combined_content.append("")
            combined_content.append("---")
            combined_content.append("")
        
        return "\n".join(combined_content)

    async def convert_markdown_to_docx(self, markdown_content: str, output_path: str) -> bool:
        """
        Convert markdown content to DOCX using pypandoc_binary
        
        Args:
            markdown_content: The markdown content to convert
            output_path: Path where the DOCX file should be saved
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create temporary markdown file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as temp_md:
                temp_md.write(markdown_content)
                temp_md_path = temp_md.name
            
            try:
                # Convert markdown to DOCX using pypandoc (run in executor to avoid blocking)
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,  # Use default ThreadPoolExecutor
                    lambda: pypandoc.convert_file(
                        temp_md_path,
                        'docx',
                        outputfile=output_path,
                        extra_args=[
                            '--wrap=none',       # Don't wrap lines
                            '--standalone'       # Create standalone document
                        ]
                    )
                )
                
                logger.info(f"Successfully converted markdown to DOCX: {output_path}")
                return True
                
            finally:
                # Clean up temporary file
                os.unlink(temp_md_path)
                
        except Exception as e:
            logger.error(f"Error converting markdown to DOCX: {str(e)}")
            return False

    async def convert_pdf_to_docx(self, pdf_s3_key: str, docx_s3_key: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Main conversion method: PDF → Images → Markdown → DOCX
        
        Args:
            pdf_s3_key: S3 key of the input PDF file
            docx_s3_key: S3 key where the output DOCX should be stored
            
        Returns:
            Tuple of (success, error_message, metadata)
        """
        temp_dir = None
        
        try:
            # Create temporary directory for processing
            temp_dir = tempfile.mkdtemp(prefix="ai_pdf_conversion_")
            pdf_path = os.path.join(temp_dir, "input.pdf")
            images_dir = os.path.join(temp_dir, "images")
            docx_path = os.path.join(temp_dir, "output.docx")
            
            os.makedirs(images_dir, exist_ok=True)
            
            logger.info(f"Starting AI-powered PDF conversion: {pdf_s3_key} → {docx_s3_key}")
            
            # Step 1: Download PDF from S3 (run in executor to avoid blocking)
            logger.info("Step 1: Downloading PDF from S3...")
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None,  # Use default ThreadPoolExecutor
                lambda: s3_service.download_file(pdf_s3_key, pdf_path)
            )
            if not success:
                return False, "Failed to download PDF from S3", {}
            
            # Step 2: Get PDF info and convert to images
            logger.info("Step 2: Converting PDF to images...")
            try:
                import fitz  # PyMuPDF
                pdf_doc = fitz.open(pdf_path)
                total_pages = pdf_doc.page_count
                pdf_doc.close()
            except ImportError:
                # Fallback: try to get page count from pdf2image
                from pdf2image import pdfinfo_from_path
                info = pdfinfo_from_path(pdf_path)
                total_pages = info.get('Pages', 1)
            
            # Convert all pages to images
            page_numbers = list(range(1, total_pages + 1))
            image_paths = await self.convert_to_images(pdf_path, images_dir, page_numbers)
            
            if not image_paths:
                return False, "Failed to convert PDF to images", {}
            
            logger.info(f"Successfully converted {len(image_paths)} pages to images")
            
            # Step 3: Convert images to markdown using OpenAI with threading
            logger.info("Step 3: Converting images to markdown using OpenAI with 5 threads...")
            markdown_results = await self.convert_images_to_markdown_threaded(image_paths, max_workers=5)
            
            # Step 4: Combine markdown files
            logger.info("Step 4: Combining markdown content...")
            combined_markdown = self.combine_markdown_files(markdown_results)
            
            # Step 5: Convert to DOCX
            logger.info("Step 5: Converting markdown to DOCX...")
            success = await self.convert_markdown_to_docx(combined_markdown, docx_path)
            if not success:
                return False, "Failed to convert markdown to DOCX", {}
            
            # Step 6: Upload DOCX to S3 (run in executor to avoid blocking)
            logger.info("Step 6: Uploading DOCX to S3...")
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None,  # Use default ThreadPoolExecutor
                lambda: s3_service.upload_file(docx_path, docx_s3_key)
            )
            if not success:
                return False, "Failed to upload DOCX to S3", {}
            
            # Calculate metadata
            pdf_size = os.path.getsize(pdf_path)
            docx_size = os.path.getsize(docx_path)
            
            # Calculate average confidence score
            confidence_scores = [result.get("score", 0) for result in markdown_results]
            avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
            
            metadata = {
                "total_pages": total_pages,
                "images_generated": len(image_paths),
                "average_confidence_score": round(avg_confidence, 2),
                "input_file_size_mb": round(pdf_size / (1024 * 1024), 2),
                "output_file_size_mb": round(docx_size / (1024 * 1024), 2),
                "conversion_method": "AI-powered (PDF→Images→Markdown→DOCX)",
                "ai_model": "gpt-4o"
            }
            
            logger.info(f"AI conversion completed successfully. Average confidence: {avg_confidence:.1f}%")
            
            return True, "", metadata
            
        except Exception as e:
            error_msg = f"AI PDF conversion failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, {}
            
        finally:
            # Clean up temporary directory
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except Exception as cleanup_error:
                    logger.warning(f"Failed to clean up temporary directory: {cleanup_error}")


# Create global instance
ai_pdf_conversion_service = AIPDFConversionService()
