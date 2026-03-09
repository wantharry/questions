"""
HTML document extractor using BeautifulSoup.
"""
from pathlib import Path
from typing import Dict, Any
from bs4 import BeautifulSoup
from app.utils.logger import app_logger


class HTMLExtractor:
    """Extract content from HTML files."""
    
    def __init__(self):
        pass
    
    def extract(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract text and metadata from HTML file.
        
        Returns:
            Dict with 'text', 'title', 'metadata'
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                html_content = f.read()
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            # Get title
            title = ""
            if soup.title:
                title = soup.title.string or ""
            elif soup.find('h1'):
                title = soup.find('h1').get_text(strip=True)
            
            # Extract main content
            text = soup.get_text(separator='\n', strip=True)
            
            # Clean up multiple newlines
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            text = '\n'.join(lines)
            
            metadata = {
                "title": title,
                "file_size": file_path.stat().st_size,
            }
            
            # Try to extract meta tags
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc and meta_desc.get("content"):
                metadata["description"] = meta_desc.get("content")
            
            meta_keywords = soup.find("meta", attrs={"name": "keywords"})
            if meta_keywords and meta_keywords.get("content"):
                metadata["keywords"] = meta_keywords.get("content")
            
            app_logger.info(f"Extracted {len(text)} characters from HTML {file_path.name}")
            
            return {
                "text": text,
                "title": title,
                "metadata": metadata,
            }
        
        except Exception as e:
            app_logger.error(f"Error extracting HTML {file_path}: {e}")
            raise
