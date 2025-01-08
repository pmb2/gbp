import os
import magic
import docx
import PyPDF2
import io
import json
from typing import Dict, Any, List, Optional
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from ..models import FAQ, Business
from .embeddings import generate_embedding

def get_file_mime_type(file_content: bytes) -> str:
    """Determine file type using python-magic"""
    mime = magic.Magic(mime=True)
    return mime.from_buffer(file_content)

def process_text_file(content: bytes) -> str:
    """Process plain text files"""
    return content.decode('utf-8', errors='ignore')

def process_docx(content: bytes) -> str:
    """Process .docx files"""
    import io
    doc = docx.Document(io.BytesIO(content))
    return '\n'.join([paragraph.text for paragraph in doc.paragraphs])

def process_pdf(content: bytes) -> str:
    """Process PDF files"""
    pdf_file = io.BytesIO(content)
    reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def process_markdown(content: bytes) -> str:
    """Process markdown files"""
    return content.decode('utf-8', errors='ignore')

def store_file_content(business_id: str, file_obj: Any, filename: str) -> Dict[str, Any]:
    """Store file content and generate embeddings with extensive error handling"""
    try:
        # Validate file size (10MB limit)
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
        file_obj.seek(0, 2)  # Seek to end
        file_size = file_obj.tell()
        file_obj.seek(0)  # Reset to beginning
        
        if file_size > MAX_FILE_SIZE:
            raise ValueError(f"File size exceeds limit of {MAX_FILE_SIZE/1024/1024}MB")

        # Read file content with timeout
        try:
            content = file_obj.read()
        except Exception as e:
            raise IOError(f"Failed to read file content: {str(e)}")

        # Validate file type
        try:
            mime_type = get_file_mime_type(content)
        except Exception as e:
            raise ValueError(f"Failed to determine file type: {str(e)}")

        # Process content based on mime type
        try:
            if mime_type == 'text/plain':
                text_content = process_text_file(content)
            elif mime_type == 'application/pdf':
                text_content = process_pdf(content)
            elif mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                text_content = process_docx(content)
            elif mime_type == 'text/markdown':
                text_content = process_markdown(content)
            else:
                raise ValueError(f"Unsupported file type: {mime_type}")
        except Exception as e:
            raise ValueError(f"Failed to process file content: {str(e)}")

        # Validate text content
        if not text_content or len(text_content.strip()) == 0:
            raise ValueError("Extracted text content is empty")

        # Generate embedding with validation
        try:
            embedding = generate_embedding(text_content)
            if not embedding:
                raise ValueError("Failed to generate embedding")
            if len(embedding) != 1536:  # Validate embedding dimensions
                raise ValueError(f"Invalid embedding dimensions: expected 1536, got {len(embedding)}")
        except Exception as e:
            raise ValueError(f"Embedding generation failed: {str(e)}")

        # Verify business exists
        try:
            business = Business.objects.get(business_id=business_id)
        except Business.DoesNotExist:
            raise ValueError(f"Business with ID {business_id} not found")

        # Store file safely
        try:
            file_path = f'knowledge_base/{business_id}/{filename}'
            saved_path = default_storage.save(file_path, ContentFile(content))
        except Exception as e:
            raise IOError(f"Failed to store file: {str(e)}")

        # Create FAQ entry with file metadata
        try:
            faq = FAQ.objects.create(
                business=business,
                question=f"Content from file: {filename}",
                answer=text_content,
                embedding=embedding,
                file_path=saved_path,
                file_type=mime_type,
                file_size=file_size
            )
        except Exception as e:
            # Cleanup stored file if FAQ creation fails
            default_storage.delete(saved_path)
            raise ValueError(f"Failed to create FAQ entry: {str(e)}")

        return {
            'id': faq.id,
            'name': filename,
            'size': file_size,
            'type': mime_type,
            'path': saved_path
        }

    except (ValueError, IOError) as e:
        # Log specific error types
        print(f"Error processing file {filename}: {str(e)}")
        raise
    except Exception as e:
        # Log unexpected errors
        print(f"Unexpected error processing file {filename}: {str(e)}")
        raise ValueError(f"Unexpected error: {str(e)}")

def process_folder(business_id: str, folder_path: str) -> List[Dict[str, Any]]:
    """Process all files in a folder"""
    results = []
    allowed_extensions = {'.txt', '.pdf', '.docx', '.md'}

    for root, _, files in os.walk(folder_path):
        for filename in files:
            if os.path.splitext(filename)[1].lower() in allowed_extensions:
                file_path = os.path.join(root, filename)
                with open(file_path, 'rb') as f:
                    try:
                        result = store_file_content(business_id, f, filename)
                        results.append(result)
                    except Exception as e:
                        print(f"Error processing {filename}: {str(e)}")
                        continue

    return results
