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
    """Store file content and generate embeddings with extensive error handling and chunking"""
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

        # Process content based on mime type with enhanced error handling
        try:
            print(f"\nProcessing file content:")
            print(f"MIME type: {mime_type}")
            print(f"File size: {file_size/1024:.1f}KB")
            
            if mime_type == 'text/plain':
                text_content = process_text_file(content)
            elif mime_type == 'application/pdf':
                text_content = process_pdf(content)
            elif mime_type in [
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/msword'
            ]:
                text_content = process_docx(content)
            elif mime_type == 'text/markdown':
                text_content = process_markdown(content)
            else:
                raise ValueError(f"Unsupported file type: {mime_type}")
                
            print(f"Successfully extracted text content")
            print(f"Extracted text length: {len(text_content)} characters")
            print(f"Text preview: {text_content[:200]}...")
            
        except Exception as e:
            error_msg = f"Failed to process file content: {str(e)}\n"
            error_msg += f"File: {filename}\n"
            error_msg += f"MIME type: {mime_type}\n"
            error_msg += f"Size: {file_size/1024:.1f}KB"
            print(f"ERROR: {error_msg}")
            raise ValueError(error_msg)

        # Validate text content
        if not text_content or len(text_content.strip()) == 0:
            raise ValueError("Extracted text content is empty")

        # Generate embedding with validation
        try:
            # Enhanced content chunking with better text handling
            MAX_CHUNK_SIZE = 1500  # Increased for better context
            MIN_CHUNK_SIZE = 100   # Minimum size to process
            chunks = []
            
            # Clean and normalize text first
            text_content = text_content.replace('\r\n', '\n').strip()
            paragraphs = [p.strip() for p in text_content.split('\n\n') if p.strip()]
            
            print(f"\nStarting content chunking:")
            print(f"Total content length: {len(text_content)} characters")
            print(f"Found {len(paragraphs)} paragraphs")
            
            current_chunk = ""
            
            for para in paragraphs:
                # Skip empty paragraphs
                if not para.strip():
                    continue
                    
                # If adding this paragraph would exceed max size
                if len(current_chunk) + len(para) > MAX_CHUNK_SIZE:
                    # Save current chunk if it meets minimum size
                    if len(current_chunk.strip()) >= MIN_CHUNK_SIZE:
                        chunks.append(current_chunk.strip())
                        print(f"Created chunk of {len(current_chunk)} characters")
                    current_chunk = para + "\n\n"
                else:
                    current_chunk += para + "\n\n"
            
            # Add final chunk if it meets minimum size
            if len(current_chunk.strip()) >= MIN_CHUNK_SIZE:
                chunks.append(current_chunk.strip())
                print(f"Created final chunk of {len(current_chunk)} characters")
            
            print(f"Created {len(chunks)} chunks for processing")
            
            # Generate embeddings for each chunk with better error handling
            embeddings = []
            for idx, chunk in enumerate(chunks):
                try:
                    print(f"\nProcessing chunk {idx + 1}/{len(chunks)}")
                    print(f"Chunk length: {len(chunk)} characters")
                    print(f"Chunk preview: {chunk[:100]}...")
                    
                    embedding = generate_embedding(chunk)
                    
                    if embedding is None:
                        print(f"Warning: Embedding generation returned None for chunk {idx + 1}")
                        continue
                        
                    if len(embedding) != 1536:
                        print(f"Warning: Invalid embedding dimensions for chunk {idx + 1}: {len(embedding)}")
                        continue
                    
                    embeddings.append({
                        'text': chunk,
                        'embedding': embedding
                    })
                    print(f"Successfully generated embedding for chunk {idx + 1}")
                    
                except Exception as e:
                    print(f"Error processing chunk {idx + 1}: {str(e)}")
                    continue
            
            if not embeddings:
                error_msg = "Failed to generate any valid embeddings. "
                error_msg += f"Processed {len(chunks)} chunks but none were successful. "
                error_msg += "Check the logs for specific chunk processing errors."
                raise ValueError(error_msg)
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

        # Create FAQ entries for each chunk with file metadata
        try:
            faqs = []
            for idx, chunk_data in enumerate(embeddings):
                faq = FAQ.objects.create(
                    business=business,
                    question=f"Content from {filename} (Part {idx + 1}/{len(embeddings)})",
                    answer=chunk_data['text'],
                    embedding=chunk_data['embedding'],
                    file_path=saved_path,
                    file_type=mime_type,
                    file_size=file_size,
                    chunk_index=idx
                )
                faqs.append(faq)
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
