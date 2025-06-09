import json
import os
import uuid
from typing import List, Dict, Optional
from werkzeug.utils import secure_filename
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class ProductService:
    def __init__(self):
        self.products_file = 'data/products.json'
        self.images_folder = 'static/product_images'
        self.allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
        
        # Ensure directories exist
        os.makedirs('data', exist_ok=True)
        os.makedirs(self.images_folder, exist_ok=True)
        
        # Initialize products file if it doesn't exist
        if not os.path.exists(self.products_file):
            self._save_products([])
    
    def _allowed_file(self, filename: str) -> bool:
        """Check if file extension is allowed"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in self.allowed_extensions
    
    def _load_products(self) -> List[Dict]:
        """Load products from JSON file"""
        try:
            with open(self.products_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            logger.warning("Could not load products file, returning empty list")
            return []
    
    def _save_products(self, products: List[Dict]) -> None:
        """Save products to JSON file"""
        try:
            with open(self.products_file, 'w') as f:
                json.dump(products, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save products: {str(e)}")
            raise Exception(f"Failed to save products: {str(e)}")
    
    def add_product(self, image_file, product_name: str, price_nzd: float, listing_link: str = None, sourcing_type: str = None, sourcing_data: str = None) -> Dict:
        """Add a new product to the catalog"""
        try:
            # Validate inputs
            if not image_file or not self._allowed_file(image_file.filename):
                raise ValueError("Invalid image file")
            
            if not product_name or not product_name.strip():
                raise ValueError("Product name is required")
            
            if price_nzd <= 0:
                raise ValueError("Price must be greater than 0")
            
            # Generate unique ID and filename
            product_id = str(uuid.uuid4())
            filename = secure_filename(image_file.filename)
            file_extension = filename.rsplit('.', 1)[1].lower()
            unique_filename = f"{product_id}.{file_extension}"
            
            # Save image file
            image_path = os.path.join(self.images_folder, unique_filename)
            image_file.save(image_path)
            
            # Create product object
            product = {
                'id': product_id,
                'name': product_name.strip(),
                'price_nzd': float(price_nzd),
                'image': unique_filename,
                'listing_link': listing_link.strip() if listing_link and listing_link.strip() else None,
                'sourcing_type': sourcing_type if sourcing_type in ['link', 'agent'] else None,
                'sourcing_data': sourcing_data.strip() if sourcing_data and sourcing_data.strip() else None,
                'created_at': self._get_current_timestamp()
            }
            
            # Load existing products and add new one
            products = self._load_products()
            products.append(product)
            self._save_products(products)
            
            logger.info(f"Added new product: {product_name} - NZD ${price_nzd}")
            return product
            
        except Exception as e:
            logger.error(f"Failed to add product: {str(e)}")
            raise Exception(f"Failed to add product: {str(e)}")
    
    def get_all_products(self) -> List[Dict]:
        """Get all products sorted by creation date (newest first)"""
        products = self._load_products()
        return sorted(products, key=lambda x: x.get('created_at', ''), reverse=True)
    
    def search_products(self, search_term: str) -> List[Dict]:
        """Search products by name"""
        if not search_term:
            return self.get_all_products()
        
        products = self.get_all_products()
        search_term = search_term.lower()
        
        return [p for p in products if search_term in p['name'].lower()]
    
    def delete_product(self, product_id: str) -> bool:
        """Delete a product by ID"""
        try:
            products = self._load_products()
            product_to_delete = None
            
            # Find the product
            for product in products:
                if product['id'] == product_id:
                    product_to_delete = product
                    break
            
            if not product_to_delete:
                raise ValueError(f"Product with ID {product_id} not found")
            
            # Remove image file
            image_path = os.path.join(self.images_folder, product_to_delete['image'])
            if os.path.exists(image_path):
                os.remove(image_path)
            
            # Remove from products list
            products = [p for p in products if p['id'] != product_id]
            self._save_products(products)
            
            logger.info(f"Deleted product: {product_to_delete['name']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete product: {str(e)}")
            raise Exception(f"Failed to delete product: {str(e)}")
    
    def _get_current_timestamp(self) -> str:
        """Get current timestamp as ISO string"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def get_product_by_id(self, product_id: str) -> Optional[Dict]:
        """Get a specific product by ID"""
        products = self._load_products()
        for product in products:
            if product['id'] == product_id:
                return product
        return None
    
    def add_product_from_bytes(self, image_bytes: bytes, product_name: str, price_nzd: float, file_extension: str = 'png', listing_link: str = None, sourcing_type: str = None, sourcing_data: str = None) -> Dict:
        """Add a new product to the catalog using image bytes (for OCR-cropped images)"""
        try:
            # Validate inputs
            if not image_bytes:
                raise ValueError("No image data provided")
            
            if not product_name or not product_name.strip():
                raise ValueError("Product name is required")
            
            if price_nzd <= 0:
                raise ValueError("Price must be greater than 0")
            
            # Generate unique ID and filename
            product_id = str(uuid.uuid4())
            unique_filename = f"{product_id}.{file_extension}"
            
            # Save image file from bytes
            image_path = os.path.join(self.images_folder, unique_filename)
            with open(image_path, 'wb') as f:
                f.write(image_bytes)
            
            # Create product object
            product = {
                'id': product_id,
                'name': product_name.strip(),
                'price_nzd': float(price_nzd),
                'image': unique_filename,
                'listing_link': listing_link.strip() if listing_link and listing_link.strip() else None,
                'sourcing_type': sourcing_type if sourcing_type in ['link', 'agent'] else None,
                'sourcing_data': sourcing_data.strip() if sourcing_data and sourcing_data.strip() else None,
                'created_at': self._get_current_timestamp()
            }
            
            # Load existing products and add new one
            products = self._load_products()
            products.append(product)
            self._save_products(products)
            
            logger.info(f"Added new product from bytes: {product_name} - NZD ${price_nzd}")
            return product
            
        except Exception as e:
            logger.error(f"Failed to add product from bytes: {str(e)}")
            raise Exception(f"Failed to add product from bytes: {str(e)}")
    
    def update_product(self, product_id: str, new_name: str = None, new_price: float = None, new_image_file=None, new_listing_link: str = None, new_sourcing_type: str = None, new_sourcing_data: str = None) -> Dict:
        """Update an existing product"""
        try:
            products = self._load_products()
            product_to_update = None
            product_index = -1
            
            # Find the product
            for i, product in enumerate(products):
                if product['id'] == product_id:
                    product_to_update = product
                    product_index = i
                    break
            
            if not product_to_update:
                raise ValueError(f"Product with ID {product_id} not found")
            
            # Update name if provided
            if new_name and new_name.strip():
                product_to_update['name'] = new_name.strip()
            
            # Update price if provided
            if new_price is not None:
                if new_price <= 0:
                    raise ValueError("Price must be greater than 0")
                product_to_update['price_nzd'] = float(new_price)
            
            # Update listing link if provided (allow empty string to clear the link)
            if new_listing_link is not None:
                product_to_update['listing_link'] = new_listing_link.strip() if new_listing_link.strip() else None
            
            # Update sourcing if provided
            if new_sourcing_type is not None:
                product_to_update['sourcing_type'] = new_sourcing_type if new_sourcing_type in ['link', 'agent'] else None
            if new_sourcing_data is not None:
                product_to_update['sourcing_data'] = new_sourcing_data.strip() if new_sourcing_data.strip() else None
            
            # Update image if provided
            if new_image_file and self._allowed_file(new_image_file.filename):
                # Remove old image file
                old_image_path = os.path.join(self.images_folder, product_to_update['image'])
                if os.path.exists(old_image_path):
                    os.remove(old_image_path)
                
                # Save new image
                filename = secure_filename(new_image_file.filename)
                file_extension = filename.rsplit('.', 1)[1].lower()
                unique_filename = f"{product_id}.{file_extension}"
                
                image_path = os.path.join(self.images_folder, unique_filename)
                new_image_file.save(image_path)
                
                product_to_update['image'] = unique_filename
            
            # Update the product in the list
            products[product_index] = product_to_update
            self._save_products(products)
            
            logger.info(f"Updated product: {product_to_update['name']}")
            return product_to_update
            
        except Exception as e:
            logger.error(f"Failed to update product: {str(e)}")
            raise Exception(f"Failed to update product: {str(e)}") 