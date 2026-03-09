"""
Image extractor with OCR support.
"""
from pathlib import Path
from typing import Dict, Any
from PIL import Image
from app.utils.logger import app_logger


class ImageExtractor:
    """Extract text from images using OCR."""
    
    def __init__(self, enable_ocr: bool = True, ocr_language: str = "eng"):
        self.enable_ocr = enable_ocr
        self.ocr_language = ocr_language
        
        if enable_ocr:
            try:
                import pytesseract
                self.ocr_engine = pytesseract
                app_logger.info("OCR enabled for image extraction")
            except ImportError:
                app_logger.warning("pytesseract not available, OCR disabled")
                self.enable_ocr = False
    
    def extract(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract text from image using OCR.
        
        Returns:
            Dict with 'text', 'metadata'
        """
        try:
            image = Image.open(file_path)
            
            text = ""
            if self.enable_ocr and self.ocr_engine:
                text = self.ocr_engine.image_to_string(image, lang=self.ocr_language)
                text = text.strip()
            
            metadata = {
                "format": image.format,
                "width": image.width,
                "height": image.height,
                "mode": image.mode,
                "file_size": file_path.stat().st_size,
            }
            
            app_logger.info(f"Extracted {len(text)} characters from image {file_path.name}")
            
            return {
                "text": text,
                "metadata": metadata,
            }
        
        except Exception as e:
            app_logger.error(f"Error extracting image {file_path}: {e}")
            raise
