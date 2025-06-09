import logging
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from typing import List, Dict, Tuple, Optional
import os
from datetime import datetime
import pandas as pd

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class GoogleSheetsService:
    def __init__(self):
        self.SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        self.credentials = None
        self.spreadsheet_id = None
        self.service = None
        self.tracking_sheet_name = 'Sheet1'  # Use the default sheet name
        
        # Define column structure to match the sheet
        self.columns = {
            'order_number': 'A',
            'tracking_number': 'B',
            'date': 'C',
            'tracking_link': 'D',
            'completed': 'E'
        }
    
    def initialize_with_service_account(self, credentials_path: str, spreadsheet_id: str):
        """
        Initialize the service with a service account credentials file
        """
        try:
            logger.debug(f"Initializing Google Sheets service with credentials from {credentials_path}")
            self.credentials = service_account.Credentials.from_service_account_file(
                credentials_path, scopes=self.SCOPES)
            self.spreadsheet_id = spreadsheet_id
            self.service = build('sheets', 'v4', credentials=self.credentials)
            
            # Ensure tracking sheet exists with correct headers
            self._ensure_tracking_sheet_exists()
            logger.debug("Successfully initialized Google Sheets service")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets service: {str(e)}", exc_info=True)
            raise Exception(f"Failed to initialize Google Sheets service: {str(e)}")
    
    def _ensure_tracking_sheet_exists(self):
        """Ensure the tracking sheet exists with correct headers"""
        try:
            # Try to get the sheet
            self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.tracking_sheet_name}!A1:E1"
            ).execute()
        except:
            # Sheet doesn't exist, create it
            body = {
                'requests': [{
                    'addSheet': {
                        'properties': {
                            'title': self.tracking_sheet_name
                        }
                    }
                }]
            }
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=body
            ).execute()
            
            # Add headers to match the sheet
            headers = [['Order Number', 'Tracking Number', 'Date Added', 'Tracking Link', 'Completed']]
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.tracking_sheet_name}!A1:E1",
                valueInputOption='RAW',
                body={'values': headers}
            ).execute()
            
            # Add checkbox data validation to column E
            self._setup_checkbox_validation()
    
    def _get_existing_data(self) -> pd.DataFrame:
        """Get existing data from the tracking sheet"""
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.tracking_sheet_name}!A:E"
            ).execute()
            
            values = result.get('values', [])
            if not values:
                return pd.DataFrame(columns=['order_number', 'tracking_number', 'date', 'tracking_link', 'completed'])
            
            # Create DataFrame and normalize column names
            df = pd.DataFrame(values[1:], columns=values[0])  # Skip header row
            column_mapping = {
                'Order Number': 'order_number',
                'Tracking Number': 'tracking_number',
                'Date Added': 'date',
                'Tracking Link': 'tracking_link',
                'Completed': 'completed'
            }
            df = df.rename(columns=column_mapping)
            return df
        except Exception as e:
            logger.error(f"Failed to get existing data: {str(e)}", exc_info=True)
            return pd.DataFrame(columns=['order_number', 'tracking_number', 'date', 'tracking_link', 'completed'])
    
    def _generate_tracking_link(self, tracking_number: str) -> str:
        """Generate a ParcelApp tracking link for a tracking number"""
        if not tracking_number:
            return ""
        return f"https://parcelsapp.com/en/tracking/{tracking_number}"
    
    def _setup_checkbox_validation(self, start_row: int = None, end_row: int = None):
        """Setup checkbox data validation for column E for specific rows"""
        try:
            sheet_id = self._get_sheet_id()
            if sheet_id is None:
                logger.warning("Could not get sheet ID for checkbox validation")
                return
            
            # If no specific range provided, get the current data range
            if start_row is None or end_row is None:
                existing_df = self._get_existing_data()
                if existing_df.empty:
                    logger.debug("No data to apply checkbox validation to")
                    return
                
                # Apply validation to existing data rows only
                start_row = 2  # Row 2 (after header, 1-indexed)
                end_row = len(existing_df) + 1  # +1 because header takes row 1
            
            body = {
                'requests': [{
                    'setDataValidation': {
                        'range': {
                            'sheetId': sheet_id,
                            'startRowIndex': start_row - 1,  # Convert to 0-indexed
                            'endRowIndex': end_row,  # Convert to 0-indexed, end is exclusive
                            'startColumnIndex': 4,  # Column E (0-indexed)
                            'endColumnIndex': 5  # End at column E
                        },
                        'rule': {
                            'condition': {
                                'type': 'BOOLEAN'
                            },
                            'showCustomUi': True
                        }
                    }
                }]
            }
            
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=body
            ).execute()
            
            logger.debug(f"Successfully set up checkbox validation for column E, rows {start_row} to {end_row}")
            
        except Exception as e:
            logger.warning(f"Failed to setup checkbox validation: {str(e)}")

    def append_order_data(self, order_data: List[Dict]) -> bool:
        """Append new order data to the sheet"""
        try:
            if not order_data:
                return True
            
            logger.debug(f"Processing {len(order_data)} orders")
            # Get existing data
            existing_df = self._get_existing_data()
            
            # Prepare new data
            new_rows = []
            today = datetime.now().strftime('%d-%m-%Y')
            
            for order in order_data:
                logger.debug(f"Processing order: {order}")
                # Make sure we're accessing the correct dictionary keys
                order_number = str(order.get('order_number', ''))  # Convert to string to ensure consistency
                tracking_number = str(order.get('tracking_number', ''))
                
                if not order_number:  # Skip if no order number
                    logger.warning("Skipping order with no order number")
                    continue
                    
                tracking_link = self._generate_tracking_link(tracking_number)
                new_row = [
                    order_number,
                    tracking_number,
                    today,
                    tracking_link,
                    False  # Checkbox starts unchecked
                ]
                logger.debug(f"Created row: {new_row}")
                new_rows.append(new_row)
            
            if not new_rows:  # If no valid rows to add
                logger.debug("No valid rows to append")
                return True
                
            new_df = pd.DataFrame(new_rows, columns=['order_number', 'tracking_number', 'date', 'tracking_link', 'completed'])
            logger.debug(f"Created DataFrame with {len(new_df)} rows")
            
            # Remove duplicates based on order number
            if not existing_df.empty:
                logger.debug(f"Checking for duplicates against {len(existing_df)} existing rows")
                new_df = new_df[~new_df['order_number'].isin(existing_df['order_number'])]
                logger.debug(f"After duplicate removal: {len(new_df)} rows")
            
            if new_df.empty:
                logger.debug("No new data to append after duplicate removal")
                return True
            
            # Append new data
            values = new_df.values.tolist()
            body = {
                'values': values
            }
            
            logger.debug(f"Appending {len(values)} rows to sheet")
            
            # Get current row count before appending
            current_row_count = len(existing_df) + 1  # +1 for header
            
            append_result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.tracking_sheet_name}!A:E",
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            logger.debug(f"Append result: {append_result}")
            
            # Setup checkbox validation only for the newly added rows
            start_row = current_row_count + 1  # +1 because we're adding after existing data
            end_row = current_row_count + len(values)
            self._setup_checkbox_validation(start_row, end_row)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to append data to Google Sheet: {str(e)}", exc_info=True)
            raise Exception(f"Failed to append data to Google Sheet: {str(e)}")
    
    def _get_sheet_id(self) -> Optional[int]:
        """Get the sheet ID for the tracking sheet"""
        try:
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            for sheet in spreadsheet['sheets']:
                if sheet['properties']['title'] == self.tracking_sheet_name:
                    return sheet['properties']['sheetId']
            
            return None
        except Exception as e:
            print(f"Warning: Failed to get sheet ID: {str(e)}")
            return None
    
    def check_for_duplicate_orders(self, order_numbers: List[str]) -> List[str]:
        """Check which order numbers already exist in the sheet"""
        existing_df = self._get_existing_data()
        if existing_df.empty:
            return []
        
        # Convert to string for comparison
        existing_orders = existing_df['order_number'].astype(str).tolist()
        duplicates = [order for order in order_numbers if str(order) in existing_orders]
        return duplicates

    def bulk_update_orders(self, order_tracking_pairs: List[Tuple[str, str]]) -> Tuple[int, int, int]:
        """
        Bulk update orders with tracking information
        Args:
            order_tracking_pairs: List of tuples (order_number, tracking_number)
        Returns:
            Tuple of (added_count, updated_count, skipped_count)
        """
        try:
            logger.debug(f"Processing {len(order_tracking_pairs)} order/tracking pairs")
            
            # Get existing data
            existing_df = self._get_existing_data()
            today = datetime.now().strftime('%d-%m-%Y')
            
            logger.debug(f"Existing data shape: {existing_df.shape}")
            if not existing_df.empty:
                logger.debug(f"Existing order numbers: {existing_df['order_number'].tolist()}")
            
            # Track statistics
            added_count = 0
            updated_count = 0
            skipped_count = 0
            
            # Process each pair
            rows_to_add = []
            rows_to_update = []
            
            for order_number, tracking_number in order_tracking_pairs:
                if not order_number or not tracking_number:
                    skipped_count += 1
                    continue
                
                # Clean order number (remove # if present, strip whitespace)
                clean_order_number = str(order_number).strip()
                if clean_order_number.startswith('#'):
                    clean_order_number = clean_order_number[1:]
                
                logger.debug(f"Processing order: '{clean_order_number}' with tracking: '{tracking_number}'")
                
                tracking_link = self._generate_tracking_link(tracking_number)
                
                # Check if order already exists - be more thorough with the search
                existing_row_idx = None
                if not existing_df.empty:
                    # Clean existing order numbers for comparison
                    existing_df_clean = existing_df.copy()
                    existing_df_clean['clean_order'] = existing_df_clean['order_number'].astype(str).str.strip()
                    existing_df_clean['clean_order'] = existing_df_clean['clean_order'].str.replace('#', '', regex=False)
                    
                    mask = existing_df_clean['clean_order'] == clean_order_number
                    if mask.any():
                        existing_row_idx = existing_df_clean[mask].index[0]
                        logger.debug(f"Found existing order '{clean_order_number}' at pandas index {existing_row_idx}")
                
                if existing_row_idx is not None:
                    # Update existing row
                    # Convert pandas index to Google Sheets row number
                    # +2 because: +1 for header row, +1 to convert from 0-based to 1-based indexing
                    row_number = existing_row_idx + 2
                    logger.debug(f"Will update row {row_number} for order '{clean_order_number}'")
                    rows_to_update.append({
                        'row': row_number,
                        'order_number': clean_order_number,
                        'tracking_number': tracking_number,
                        'date': today,
                        'tracking_link': tracking_link
                    })
                    updated_count += 1
                else:
                    # Add new row
                    logger.debug(f"Will add new row for order '{clean_order_number}'")
                    rows_to_add.append([clean_order_number, tracking_number, today, tracking_link, False])
                    added_count += 1
            
            # Perform batch updates for existing rows
            if rows_to_update:
                logger.debug(f"Updating {len(rows_to_update)} existing rows")
                update_requests = []
                for update_row in rows_to_update:
                    logger.debug(f"Updating row {update_row['row']} with tracking: {update_row['tracking_number']}")
                    # Update tracking number (column B)
                    update_requests.append({
                        'range': f"{self.tracking_sheet_name}!B{update_row['row']}",
                        'values': [[update_row['tracking_number']]]
                    })
                    # Update date (column C)
                    update_requests.append({
                        'range': f"{self.tracking_sheet_name}!C{update_row['row']}",
                        'values': [[update_row['date']]]
                    })
                    # Update tracking link (column D)
                    update_requests.append({
                        'range': f"{self.tracking_sheet_name}!D{update_row['row']}",
                        'values': [[update_row['tracking_link']]]
                    })
                
                # Batch update
                body = {
                    'valueInputOption': 'RAW',
                    'data': update_requests
                }
                update_result = self.service.spreadsheets().values().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body=body
                ).execute()
                logger.debug(f"Batch update result: {update_result}")
            
            # Append new rows
            if rows_to_add:
                logger.debug(f"Adding {len(rows_to_add)} new rows")
                
                # Get current row count before appending
                current_row_count = len(existing_df) + 1  # +1 for header
                
                body = {
                    'values': rows_to_add
                }
                append_result = self.service.spreadsheets().values().append(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{self.tracking_sheet_name}!A:E",
                    valueInputOption='RAW',
                    insertDataOption='INSERT_ROWS',
                    body=body
                ).execute()
                logger.debug(f"Append result: {append_result}")
                
                # Setup checkbox validation only for the newly added rows
                start_row = current_row_count + 1  # +1 because we're adding after existing data
                end_row = current_row_count + len(rows_to_add)
                self._setup_checkbox_validation(start_row, end_row)
            
            logger.debug(f"Bulk update completed: {added_count} added, {updated_count} updated, {skipped_count} skipped")
            return added_count, updated_count, skipped_count
            
        except Exception as e:
            logger.error(f"Failed to bulk update orders: {str(e)}", exc_info=True)
            raise Exception(f"Failed to bulk update orders: {str(e)}") 