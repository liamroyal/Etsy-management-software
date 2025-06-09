import json
import os
import uuid
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class CarrierService:
    def __init__(self, data_file: str = 'data/carriers.json'):
        self.data_file = data_file
        self.carriers = []
        self._ensure_data_directory()
        self._load_carriers()
    
    def _ensure_data_directory(self):
        """Ensure the data directory exists"""
        data_dir = os.path.dirname(self.data_file)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir)
    
    def _load_carriers(self):
        """Load carriers from JSON file"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    self.carriers = json.load(f)
                logger.debug(f"Loaded {len(self.carriers)} carriers from {self.data_file}")
            else:
                # Initialize with some default carriers
                self.carriers = self._get_default_carriers()
                self._save_carriers()
                logger.debug(f"Created default carriers data at {self.data_file}")
        except Exception as e:
            logger.error(f"Error loading carriers: {str(e)}")
            self.carriers = self._get_default_carriers()
    
    def _get_default_carriers(self) -> List[Dict]:
        """Get default carrier data"""
        return [
            {
                "id": str(uuid.uuid4()),
                "carrier_name": "USPS",
                "etsy_approved": True,
                "example_tracking": "9405511899564298845722"
            },
            {
                "id": str(uuid.uuid4()),
                "carrier_name": "UPS",
                "etsy_approved": True,
                "example_tracking": "1Z12345E0205271688"
            },
            {
                "id": str(uuid.uuid4()),
                "carrier_name": "FedEx",
                "etsy_approved": True,
                "example_tracking": "1234567890123456"
            },
            {
                "id": str(uuid.uuid4()),
                "carrier_name": "DHL Express",
                "etsy_approved": True,
                "example_tracking": "1234567890"
            },
            {
                "id": str(uuid.uuid4()),
                "carrier_name": "Canada Post",
                "etsy_approved": True,
                "example_tracking": "1234567890123456"
            },
            {
                "id": str(uuid.uuid4()),
                "carrier_name": "Royal Mail",
                "etsy_approved": True,
                "example_tracking": "AB123456789GB"
            },
            {
                "id": str(uuid.uuid4()),
                "carrier_name": "Australia Post",
                "etsy_approved": True,
                "example_tracking": "1234567890123456"
            },
            {
                "id": str(uuid.uuid4()),
                "carrier_name": "LaserShip",
                "etsy_approved": False,
                "example_tracking": "1LS12345678901234567"
            }
        ]
    
    def _save_carriers(self):
        """Save carriers to JSON file"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.carriers, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved {len(self.carriers)} carriers to {self.data_file}")
        except Exception as e:
            logger.error(f"Error saving carriers: {str(e)}")
            raise
    
    def get_all_carriers(self) -> List[Dict]:
        """Get all carriers"""
        return self.carriers.copy()
    
    def get_carrier_by_id(self, carrier_id: str) -> Optional[Dict]:
        """Get a carrier by ID"""
        for carrier in self.carriers:
            if carrier['id'] == carrier_id:
                return carrier.copy()
        return None
    
    def add_carrier(self, carrier_name: str, etsy_approved: bool, example_tracking: str, alternative_text: str = None) -> Dict:
        """Add a new carrier"""
        carrier = {
            "id": str(uuid.uuid4()),
            "carrier_name": carrier_name.strip(),
            "etsy_approved": etsy_approved,
            "example_tracking": example_tracking.strip()
        }
        
        # Add alternative text field if provided (for alternative carriers)
        if alternative_text is not None:
            carrier["alternative_text"] = alternative_text.strip()
        
        self.carriers.append(carrier)
        self._save_carriers()
        
        logger.info(f"Added new carrier: {carrier_name}")
        return carrier.copy()
    
    def update_carrier(self, carrier_id: str, carrier_name: str = None, 
                      etsy_approved: bool = None, example_tracking: str = None, alternative_text: str = None) -> Optional[Dict]:
        """Update an existing carrier"""
        for i, carrier in enumerate(self.carriers):
            if carrier['id'] == carrier_id:
                if carrier_name is not None:
                    carrier['carrier_name'] = carrier_name.strip()
                if etsy_approved is not None:
                    carrier['etsy_approved'] = etsy_approved
                if example_tracking is not None:
                    carrier['example_tracking'] = example_tracking.strip()
                if alternative_text is not None:
                    carrier['alternative_text'] = alternative_text.strip()
                
                self._save_carriers()
                logger.info(f"Updated carrier: {carrier['carrier_name']}")
                return carrier.copy()
        
        return None
    
    def delete_carrier(self, carrier_id: str) -> bool:
        """Delete a carrier"""
        for i, carrier in enumerate(self.carriers):
            if carrier['id'] == carrier_id:
                deleted_carrier = self.carriers.pop(i)
                self._save_carriers()
                logger.info(f"Deleted carrier: {deleted_carrier['carrier_name']}")
                return True
        
        return False
    
    def add_alternative_carrier(self, alternative_text: str) -> Dict:
        """Add an alternative carrier with custom text"""
        carrier = {
            "id": str(uuid.uuid4()),
            "carrier_name": "Alternative Carrier",
            "etsy_approved": False,  # Alternative carriers are not typically Etsy approved
            "example_tracking": "Custom tracking method",
            "alternative_text": alternative_text.strip(),
            "is_alternative": True  # Flag to identify alternative carriers
        }
        
        self.carriers.append(carrier)
        self._save_carriers()
        
        logger.info(f"Added alternative carrier with text: {alternative_text}")
        return carrier.copy()
    
    def search_carriers(self, query: str) -> List[Dict]:
        """Search carriers by name"""
        query = query.lower().strip()
        if not query:
            return self.get_all_carriers()
        
        results = []
        for carrier in self.carriers:
            if query in carrier['carrier_name'].lower():
                results.append(carrier.copy())
        
        return results
    
    def get_etsy_approved_carriers(self) -> List[Dict]:
        """Get only Etsy-approved carriers"""
        return [carrier.copy() for carrier in self.carriers if carrier['etsy_approved']]
    
    def get_carrier_stats(self) -> Dict:
        """Get carrier statistics"""
        total = len(self.carriers)
        etsy_approved = len([c for c in self.carriers if c['etsy_approved']])
        not_approved = total - etsy_approved
        
        return {
            'total': total,
            'etsy_approved': etsy_approved,
            'not_approved': not_approved
        } 