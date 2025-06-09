import logging
import re
from typing import Dict, Optional, Tuple, List
from PIL import Image
import io
import os
import cv2
import numpy as np
from io import BytesIO

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class OCRService:
    def __init__(self):
        # Set tesseract path for Homebrew installation
        self._set_tesseract_path()
        self.tesseract_available = self._check_tesseract()
        
    def _set_tesseract_path(self):
        """Set tesseract path for different installation methods"""
        try:
            import pytesseract
            
            # Common tesseract paths
            possible_paths = [
                '/opt/homebrew/bin/tesseract',  # Homebrew on Apple Silicon
                '/usr/local/bin/tesseract',     # Homebrew on Intel
                '/usr/bin/tesseract',           # System package managers
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    pytesseract.pytesseract.tesseract_cmd = path
                    logger.debug(f"Set tesseract path to: {path}")
                    break
        except ImportError:
            pass
        
    def _check_tesseract(self) -> bool:
        """Check if tesseract is available"""
        try:
            import pytesseract
            # Test if tesseract command is available
            pytesseract.get_tesseract_version()
            logger.info("Tesseract OCR is available and ready to use")
            return True
        except Exception as e:
            logger.warning(f"Tesseract not available: {str(e)}")
            return False
    
    def extract_all_products(self, image_file) -> List[Dict[str, any]]:
        """
        Extract ALL products from an image with their cropped images
        Returns list of dicts with 'name', 'price', 'image_data', and 'error' keys
        """
        try:
            if not self.tesseract_available:
                return [{'name': None, 'price': None, 'image_data': None, 
                        'error': 'OCR not available. Please install tesseract'}]
            
            # Open and process the image
            image = Image.open(image_file)
            
            # Convert PIL to OpenCV format for processing
            img_array = np.array(image)
            if len(img_array.shape) == 3:
                img_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            else:
                img_cv = img_array
            
            # Extract text with coordinate information
            extracted_data = self._extract_text_with_coordinates(image)
            
            if not extracted_data['text']:
                return [{'name': None, 'price': None, 'image_data': None,
                        'error': 'No text could be extracted from the image'}]
            
            logger.debug(f"Extracted text: {extracted_data['text']}")
            
            # Find all products with their text positions
            products_info = self._extract_multiple_products_with_positions(
                extracted_data['text'], 
                extracted_data.get('boxes', [])
            )
            
            if not products_info:
                return [{'name': None, 'price': None, 'image_data': None,
                        'error': 'No products detected in the image'}]
            
            # Process each product and crop its image
            results = []
            for i, product_info in enumerate(products_info):
                try:
                    # Crop the product image area
                    cropped_image = self._crop_product_image(img_cv, product_info, i, len(products_info))
                    
                    # Convert cropped image to bytes for storage
                    image_data = self._image_to_bytes(cropped_image)
                    
                    results.append({
                        'name': product_info['name'],
                        'price': product_info['price'],
                        'image_data': image_data,
                        'error': None
                    })
                except Exception as e:
                    logger.error(f"Error processing product {i}: {str(e)}")
                    results.append({
                        'name': product_info['name'],
                        'price': product_info['price'],
                        'image_data': None,
                        'error': f'Error cropping image: {str(e)}'
                    })
            
            logger.info(f"Successfully extracted {len(results)} products")
            return results
            
        except Exception as e:
            logger.error(f"Error in OCR extraction: {str(e)}")
            return [{'name': None, 'price': None, 'image_data': None,
                    'error': f'OCR processing error: {str(e)}'}]
    
    def _extract_text_with_coordinates(self, image: Image.Image) -> Dict:
        """Extract text with bounding box coordinates"""
        try:
            import pytesseract
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Get text with bounding boxes
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            text = pytesseract.image_to_string(image, config='--psm 6')
            
            return {
                'text': text.strip(),
                'boxes': data
            }
            
        except Exception as e:
            logger.error(f"Error extracting text with coordinates: {str(e)}")
            return {'text': '', 'boxes': []}
    
    def _extract_multiple_products_with_positions(self, text: str, boxes: Dict) -> List[Dict]:
        """Extract multiple products with their approximate positions"""
        products = []
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # Look for lines that contain both product names and prices
        product_pattern = r'^(.+?)\s+US=(\d+(?:\.\d{1,2})?)'
        
        for line_idx, line in enumerate(lines):
            # Clean the line
            cleaned_line = re.sub(r'^[|=\-~\s]*', '', line)
            cleaned_line = re.sub(r'[|=\-~\s]*$', '', cleaned_line)
            cleaned_line = re.sub(r'\s+', ' ', cleaned_line).strip()
            
            # Try to match product name + price pattern
            match = re.search(product_pattern, cleaned_line, re.IGNORECASE)
            if match:
                product_name = match.group(1).strip()
                price_str = match.group(2)
                
                # Clean up the product name further
                product_name = re.sub(r'^[|=\-~aq\s]*', '', product_name)
                product_name = product_name.strip()
                
                if len(product_name) > 3:  # Valid product name
                    try:
                        price_float = float(price_str)
                        products.append({
                            'name': product_name,
                            'price': f"{price_float:.2f}",
                            'line_index': line_idx,
                            'y_position': line_idx  # Approximate vertical position
                        })
                    except ValueError:
                        continue
        
        logger.debug(f"Found {len(products)} products: {products}")
        return products
    
    def _crop_product_image(self, img_cv: np.ndarray, product_info: Dict, product_index: int, total_products: int) -> np.ndarray:
        """
        Crop the product image from the screenshot based on layout analysis
        """
        height, width = img_cv.shape[:2]
        
        # Estimate product image area based on table layout
        # Assuming products are arranged vertically in a table
        
        # Calculate approximate row height
        row_height = height // max(total_products, 2)
        
        # Calculate crop area for this specific product
        y_start = max(0, product_index * row_height)
        y_end = min(height, (product_index + 1) * row_height)
        
        # Assume product image is in the left portion of each row
        # Typical table layout: [Image] [Name] [Price]
        image_width_ratio = 0.3  # Image takes up ~30% of width
        x_start = 0
        x_end = min(width, int(width * image_width_ratio))
        
        # Add some padding
        padding = 10
        y_start = max(0, y_start - padding)
        y_end = min(height, y_end + padding)
        x_start = max(0, x_start)
        x_end = min(width, x_end + padding)
        
        # Crop the image
        cropped = img_cv[y_start:y_end, x_start:x_end]
        
        # If the crop is too small, use a larger area
        if cropped.shape[0] < 50 or cropped.shape[1] < 50:
            # Fall back to a larger crop area
            y_start = max(0, product_index * row_height - 20)
            y_end = min(height, (product_index + 1) * row_height + 20)
            x_end = min(width, int(width * 0.5))  # Use 50% of width
            cropped = img_cv[y_start:y_end, x_start:x_end]
        
        logger.debug(f"Cropped product {product_index}: size {cropped.shape}")
        return cropped
    
    def _image_to_bytes(self, img_cv: np.ndarray) -> bytes:
        """Convert OpenCV image to bytes"""
        # Convert BGR to RGB
        img_rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
        
        # Convert to PIL Image
        pil_image = Image.fromarray(img_rgb)
        
        # Convert to bytes
        byte_io = BytesIO()
        pil_image.save(byte_io, format='PNG')
        return byte_io.getvalue()
    
    # Keep the original single product method for backward compatibility
    def extract_product_info(self, image_file) -> Dict[str, Optional[str]]:
        """
        Extract product information from an image (single product - backward compatibility)
        Returns dict with 'name', 'price', and 'error' keys
        """
        all_products = self.extract_all_products(image_file)
        
        if all_products and all_products[0].get('name'):
            # Return the best product (longest name)
            best_product = max(all_products, 
                             key=lambda p: len(p['name']) if p['name'] else 0)
            return {
                'name': best_product['name'],
                'price': best_product['price'],
                'error': best_product['error']
            }
        
        return {
            'name': None,
            'price': None,
            'error': all_products[0]['error'] if all_products else 'No products found'
        }
    
    def get_installation_instructions(self) -> str:
        """Return instructions for installing tesseract"""
        return """
        To enable OCR functionality, please install tesseract:
        
        macOS: brew install tesseract
        Ubuntu: sudo apt-get install tesseract-ocr
        Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
        
        After installation, restart the application.
        """ 