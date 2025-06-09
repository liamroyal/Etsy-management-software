import pandas as pd
from typing import List, Dict, Tuple
import os
import numpy as np
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class ExcelService:
    def __init__(self):
        self.column_mappings = {
            'order-number': ['order-number', 'order #', 'ORDER #', 'order_number'],
            'tracking': ['tracking', 'tracking number', 'TRACKING NUMBER', 'Tracking']
        }
    
    def find_matching_column(self, columns: List[str], target_type: str) -> str:
        """
        Find the first matching column name from the possible mappings
        Returns the found column name or None
        """
        logger.debug(f"Looking for {target_type} in columns: {columns}")
        # Convert all columns to lowercase for case-insensitive comparison
        columns_lower = [col.lower() for col in columns]
        possible_names = self.column_mappings[target_type]
        
        # First try exact match with original case
        for col in columns:
            if col in possible_names:
                logger.debug(f"Found exact match for {target_type}: {col}")
                return col
        
        # Then try lowercase match
        for possible_name in possible_names:
            if possible_name.lower() in columns_lower:
                # Return the original column name that matched
                matched_col = columns[columns_lower.index(possible_name.lower())]
                logger.debug(f"Found case-insensitive match for {target_type}: {matched_col}")
                return matched_col
        
        logger.warning(f"No match found for {target_type}. Tried: {possible_names}")
        return None
    
    def validate_excel_file(self, file_path: str) -> Tuple[bool, str, Dict[str, str]]:
        """
        Validates that the Excel file has the required columns.
        Returns (is_valid, error_message, column_mapping)
        """
        try:
            logger.debug(f"Reading Excel file: {file_path}")
            df = pd.read_excel(file_path)
            logger.debug(f"Found columns: {list(df.columns)}")
            column_mapping = {}
            
            # Find matching columns for each required field
            order_column = self.find_matching_column(df.columns, 'order-number')
            tracking_column = self.find_matching_column(df.columns, 'tracking')
            
            missing_columns = []
            if not order_column:
                missing_columns.append("Order Number (tried: " + ", ".join(self.column_mappings['order-number']) + ")")
            else:
                column_mapping['order-number'] = order_column
                
            if not tracking_column:
                missing_columns.append("Tracking Number (tried: " + ", ".join(self.column_mappings['tracking']) + ")")
            else:
                column_mapping['tracking'] = tracking_column
            
            if missing_columns:
                error_msg = f"Missing required columns: {', '.join(missing_columns)}"
                logger.error(error_msg)
                return False, error_msg, {}
            
            logger.debug(f"Validation successful. Column mapping: {column_mapping}")
            return True, "", column_mapping
        except Exception as e:
            error_msg = f"Error reading Excel file: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg, {}
    
    def clean_value(self, value) -> str:
        """
        Cleans a value by handling NaN, None, and other special cases
        """
        if pd.isna(value) or value is None:
            return ""
        return str(value).strip()
    
    def process_excel_file(self, file_path: str) -> Tuple[List[Dict], str]:
        """
        Processes the Excel file and returns a list of order data and any error message.
        Returns (order_data, error_message)
        """
        try:
            # Validate file first
            is_valid, error_message, column_mapping = self.validate_excel_file(file_path)
            if not is_valid:
                return [], error_message
            
            # Read Excel file
            df = pd.read_excel(file_path)
            logger.debug(f"Read Excel file with {len(df)} rows")
            
            # Extract required columns and clean the data
            order_data_dict = {}  # Use dict to handle duplicates - last occurrence wins
            skipped_count = 0
            empty_tracking_count = 0
            empty_order_count = 0
            duplicate_count = 0
            
            for _, row in df.iterrows():
                order_number = self.clean_value(row[column_mapping['order-number']])
                tracking_number = self.clean_value(row[column_mapping['tracking']])
                
                if not order_number:
                    empty_order_count += 1
                    continue
                
                if not tracking_number:
                    empty_tracking_count += 1
                    continue
                
                # Clean order number (remove # if present)
                clean_order = str(order_number).strip()
                if clean_order.startswith('#'):
                    clean_order = clean_order[1:]
                
                # Check if this order number already exists in our current batch
                if clean_order in order_data_dict:
                    duplicate_count += 1
                    logger.debug(f"Found duplicate order number '{clean_order}', keeping latest occurrence")
                
                # Store order info (this will override if duplicate exists)
                order_info = {
                    'order_number': clean_order,
                    'tracking_number': str(tracking_number)
                }
                order_data_dict[clean_order] = order_info
                logger.debug(f"Added/Updated order: {order_info}")
            
            # Convert dict back to list
            order_data = list(order_data_dict.values())
            
            skipped_count = empty_tracking_count + empty_order_count
            
            # Create detailed message about skipped rows
            messages = []
            if empty_order_count > 0:
                messages.append(f"{empty_order_count} row(s) with blank order numbers")
            if empty_tracking_count > 0:
                messages.append(f"{empty_tracking_count} row(s) with blank tracking numbers")
            if duplicate_count > 0:
                messages.append(f"{duplicate_count} duplicate order number(s) within file (kept latest)")
            
            message = f"Skipped {skipped_count} row(s)" + (f", handled {duplicate_count} duplicate(s)" if duplicate_count > 0 else "")
            if messages:
                message += ": " + ", ".join(messages)
            
            logger.debug(f"Processed {len(df)} rows, created {len(order_data)} unique entries. {message}")
            return order_data, message
            
        except Exception as e:
            error_msg = f"Error processing Excel file: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return [], error_msg 