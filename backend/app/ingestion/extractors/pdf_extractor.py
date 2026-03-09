"""
PDF document extractor using PyMuPDF (fitz).
Extracts text, images, and metadata from PDF files.
"""
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import fitz  # PyMuPDF
from PIL import Image
import io
from app.utils.logger import app_logger


class PDFExtractor:
    """Extract content from PDF files."""
    
    def __init__(self, enable_ocr: bool = False, ocr_language: str = "eng"):
        self.enable_ocr = enable_ocr
        self.ocr_language = ocr_language
        
        if enable_ocr:
            try:
                import pytesseract
                self.ocr_engine = pytesseract
                app_logger.info("OCR enabled for PDF extraction")
            except ImportError:
                app_logger.warning("pytesseract not available, OCR disabled")
                self.enable_ocr = False
    
    def extract(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract text and images from a PDF file.
        
        Returns:
            Dict with 'pages', 'images', and 'metadata'
        """
        try:
            doc = fitz.open(file_path)
            
            pages_content = []
            all_images = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Extract text
                text = page.get_text("text")
                
                # Extract images
                images = self._extract_images_from_page(page, page_num)
                all_images.extend(images)
                
                # If OCR is enabled and text is sparse, try OCR
                if self.enable_ocr and len(text.strip()) < 100:
                    ocr_text = self._ocr_page(page)
                    if ocr_text:
                        text += "\n" + ocr_text
                
                pages_content.append({
                    "page_number": page_num + 1,
                    "text": text,
                    "has_images": len(images) > 0,
                    "image_count": len(images),
                })
            
            metadata = {
                "title": doc.metadata.get("title", ""),
                "author": doc.metadata.get("author", ""),
                "subject": doc.metadata.get("subject", ""),
                "total_pages": len(doc),
                "file_size": file_path.stat().st_size,
            }
            
            doc.close()
            
            app_logger.info(f"Extracted {len(pages_content)} pages and {len(all_images)} images from {file_path.name}")
            
            return {
                "pages": pages_content,
                "images": all_images,
                "metadata": metadata,
            }
        
        except Exception as e:
            app_logger.error(f"Error extracting PDF {file_path}: {e}")
            raise
    
    def _extract_images_from_page(self, page: fitz.Page, page_num: int) -> List[Dict[str, Any]]:
        """Extract images from a PDF page."""
        images = []
        image_list = page.get_images()
        
        for img_index, img in enumerate(image_list):
            try:
                xref = img[0]
                base_image = page.parent.extract_image(xref)
                
                if base_image:
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    
                    # Convert to PIL Image for potential OCR
                    pil_image = Image.open(io.BytesIO(image_bytes))
                    
                    # Try OCR on image if enabled
                    image_text = ""
                    if self.enable_ocr:
                        image_text = self._ocr_image(pil_image)
                    
                    images.append({
                        "page_number": page_num + 1,
                        "image_index": img_index,
                        "format": image_ext,
                        "width": pil_image.width,
                        "height": pil_image.height,
                        "text": image_text,
                        "size_bytes": len(image_bytes),
                    })
            except Exception as e:
                app_logger.warning(f"Failed to extract image {img_index} from page {page_num}: {e}")
        
        return images
    
    def _ocr_page(self, page: fitz.Page) -> str:
        """Perform OCR on a PDF page."""
        if not self.enable_ocr:
            return ""
        
        try:
            # Render page to image
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better OCR
            img_bytes = pix.tobytes("png")
            pil_image = Image.open(io.BytesIO(img_bytes))
            
            return self._ocr_image(pil_image)
        except Exception as e:
            app_logger.warning(f"OCR failed for page: {e}")
            return ""
    
    def _ocr_image(self, image: Image.Image) -> str:
        """Perform OCR on a PIL Image."""
        if not self.enable_ocr:
            return ""
        
        try:
            text = self.ocr_engine.image_to_string(image, lang=self.ocr_language)
            return text.strip()
        except Exception as e:
            app_logger.warning(f"Image OCR failed: {e}")
            return ""
    
    def get_page_count(self, file_path: Path) -> int:
        """Get the number of pages in a PDF."""
        try:
            doc = fitz.open(file_path)
            count = len(doc)
            doc.close()
            return count
        except Exception:
            return 0
