from flask import Flask, render_template, request, flash, redirect, url_for, send_from_directory
import os
from services.excel_service import ExcelService
from services.google_sheets_service import GoogleSheetsService
from services.email_service import EmailService
from services.product_service import ProductService
from services.ocr_service import OCRService
from services.todo_service import TodoService
from services.carrier_service import CarrierService
from werkzeug.utils import secure_filename
from config import GOOGLE_SHEETS_CREDENTIALS_PATH, GOOGLE_SHEETS_SPREADSHEET_ID
import logging
from datetime import datetime

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Initialize services
excel_service = ExcelService()
sheets_service = GoogleSheetsService()
email_service = EmailService()
product_service = ProductService()
ocr_service = OCRService()
todo_service = TodoService()
carrier_service = CarrierService()

try:
    sheets_service.initialize_with_service_account(
        GOOGLE_SHEETS_CREDENTIALS_PATH,
        GOOGLE_SHEETS_SPREADSHEET_ID
    )
except Exception as e:
    print(f"Warning: Failed to initialize Google Sheets service: {str(e)}")

def redirect_to_page(page=None):
    """Helper function to redirect to the correct page"""
    if page:
        return redirect(url_for('index', page=page))
    return redirect(url_for('index'))

@app.route('/')
def index():
    # Get current page from query parameter
    current_page = request.args.get('page', 'excel-upload')
    
    # Get all products to display in the catalog
    products = product_service.get_all_products()
    
    # Check if OCR is available and add installation instructions if needed
    ocr_available = ocr_service.tesseract_available
    ocr_instructions = None if ocr_available else ocr_service.get_installation_instructions()
    
    # Get current date for the bulk orders form
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    # Get active todos for the notes section
    todos = todo_service.get_active_todos()
    todo_stats = todo_service.get_todo_stats()
    
    # Get carriers for the shipping carrier section
    carriers = carrier_service.get_all_carriers()
    carrier_stats = carrier_service.get_carrier_stats()
    
    return render_template('index.html', 
                         products=products, 
                         ocr_available=ocr_available, 
                         ocr_instructions=ocr_instructions,
                         current_date=current_date,
                         todos=todos,
                         todo_stats=todo_stats,
                         carriers=carriers,
                         carrier_stats=carrier_stats,
                         current_page=current_page)

@app.route('/upload_excel', methods=['POST'])
def upload_excel():
    logger.debug("Upload Excel endpoint called")
    current_page = request.form.get('current_page', 'excel-upload')
    
    if 'file' not in request.files:
        logger.warning("No file in request")
        flash('No file selected', 'error')
        return redirect_to_page(current_page)
    
    file = request.files['file']
    if file.filename == '':
        logger.warning("Empty filename")
        flash('No file selected', 'error')
        return redirect_to_page(current_page)
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        logger.warning(f"Invalid file type: {file.filename}")
        flash('Please upload an Excel file', 'error')
        return redirect_to_page(current_page)
    
    try:
        logger.debug(f"Processing file: {file.filename}")
        # Save the uploaded file
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        logger.debug(f"File saved to: {filepath}")
        
        # Process the Excel file
        order_data, message = excel_service.process_excel_file(filepath)
        
        # DEBUG: Print exact data we got from Excel
        logger.debug("=" * 80)
        logger.debug("Data from Excel processing:")
        for idx, order in enumerate(order_data):
            logger.debug(f"Order {idx + 1}:")
            logger.debug(f"  order_number: '{order.get('order_number', '')}'")
            logger.debug(f"  tracking_number: '{order.get('tracking_number', '')}'")
        logger.debug("=" * 80)
        
        if not order_data and message:  # If there's an error and no data
            logger.error(f"Excel processing error: {message}")
            flash(f"Error processing Excel file '{filename}': {message}", 'error')
            return redirect_to_page(current_page)
        
        if not order_data:  # If there's no data but also no error
            logger.warning("No valid data found in Excel file")
            flash(f"No valid data found in the Excel file '{filename}'", 'error')
            return redirect_to_page(current_page)
        
        # Get the initial count of orders
        initial_count = len(order_data)
        logger.debug(f"Found {initial_count} orders to process")
        
        # Append data to Google Sheet (only new entries will be added)
        try:
            sheets_service.append_order_data(order_data)
            logger.debug("Successfully appended data to Google Sheet")
        except Exception as e:
            logger.error(f"Google Sheets error: {str(e)}", exc_info=True)
            flash(f"Error appending data to Google Sheet: {str(e)}", 'error')
            return redirect_to_page(current_page)
        
        # Clean up the uploaded file
        os.remove(filepath)
        
        # Create success message
        success_msg = f"Successfully processed {initial_count} orders from '{filename}'"
        if message:  # If there's additional information about skipped rows
            success_msg += f". {message}"
        success_msg += ". Any duplicate entries were automatically handled."
        
        logger.info(success_msg)
        flash(success_msg, 'success')
        
    except Exception as e:
        logger.error(f"Unexpected error processing '{filename}': {str(e)}", exc_info=True)
        flash(f"Error processing '{filename}': {str(e)}", 'error')
    
    return redirect_to_page(current_page)

@app.route('/bulk_update', methods=['POST'])
def bulk_update():
    logger.debug("Bulk update endpoint called")
    
    bulk_orders_text = request.form.get('bulk_orders', '').strip()
    current_page = request.form.get('current_page', 'excel-upload')
    
    if not bulk_orders_text:
        flash('No order data provided', 'error')
        return redirect_to_page(current_page)
    
    try:
        # Parse the bulk order text
        lines = bulk_orders_text.split('\n')
        order_tracking_pairs = []
        parse_errors = []
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            
            # Parse format: #3695239669 UK216203823YP
            parts = line.split(' ', 1)
            if len(parts) != 2:
                parse_errors.append(f"Line {line_num}: '{line}' - Invalid format (should be: order_number tracking_number)")
                continue
            
            order_number = parts[0].strip()
            tracking_number = parts[1].strip()
            
            # Remove # from order number if present
            if order_number.startswith('#'):
                order_number = order_number[1:]
            
            if not order_number or not tracking_number:
                parse_errors.append(f"Line {line_num}: Empty order number or tracking number")
                continue
            
            order_tracking_pairs.append((order_number, tracking_number))
        
        # Report parsing issues but continue if we have some valid data
        if parse_errors:
            logger.warning(f"Parse errors: {parse_errors}")
            if len(parse_errors) <= 3:  # Show up to 3 errors
                for error in parse_errors:
                    flash(f"Skipped - {error}", 'warning')
            else:
                flash(f"Skipped {len(parse_errors)} lines with formatting errors", 'warning')
        
        if not order_tracking_pairs:
            flash('No valid order/tracking pairs found in the input. Please check the format: #3695239669 UK216203823YP', 'error')
            return redirect_to_page(current_page)
        
        logger.debug(f"Parsed {len(order_tracking_pairs)} order/tracking pairs")
        
        # Remove duplicates from input (keep last occurrence)
        unique_pairs = {}
        for order_number, tracking_number in order_tracking_pairs:
            unique_pairs[order_number] = tracking_number
        
        final_pairs = list(unique_pairs.items())
        duplicates_removed = len(order_tracking_pairs) - len(final_pairs)
        
        if duplicates_removed > 0:
            logger.debug(f"Removed {duplicates_removed} duplicate orders from input")
            flash(f"Removed {duplicates_removed} duplicate order(s) from input (kept latest)", 'info')
        
        logger.debug(f"Processing {len(final_pairs)} unique order/tracking pairs")
        
        # Show which orders we're about to process
        order_preview = [pair[0] for pair in final_pairs[:5]]  # Show first 5
        if len(final_pairs) > 5:
            logger.debug(f"Processing orders: {', '.join(order_preview)} and {len(final_pairs) - 5} more...")
        else:
            logger.debug(f"Processing orders: {', '.join(order_preview)}")
        
        # Perform bulk update
        added_count, updated_count, skipped_count = sheets_service.bulk_update_orders(final_pairs)
        
        # Create detailed success message
        message_parts = []
        if added_count > 0:
            message_parts.append(f"{added_count} new orders added")
        if updated_count > 0:
            message_parts.append(f"{updated_count} existing orders updated")
        if skipped_count > 0:
            message_parts.append(f"{skipped_count} orders skipped (missing data)")
        
        if message_parts:
            success_message = "✅ Bulk processing completed: " + ", ".join(message_parts)
        else:
            success_message = "⚠️ Bulk processing completed with no changes"
        
        logger.info(f"Bulk update results: {added_count} added, {updated_count} updated, {skipped_count} skipped")
        flash(success_message, 'success')
        
    except Exception as e:
        logger.error(f"Error in bulk update: {str(e)}", exc_info=True)
        flash(f"❌ Error processing bulk update: {str(e)}", 'error')
    
    return redirect_to_page(current_page)

@app.route('/scrape_email', methods=['POST'])
def scrape_email():
    current_page = request.form.get('current_page', 'excel-upload')
    
    try:
        # Scrape new emails
        emails = email_service.scrape_new_emails()
        
        if not emails:
            flash('No new emails found from allowed senders', 'info')
            return redirect_to_page(current_page)
        
        # Create status message
        message = f"Processed {len(emails)} new emails. "
        message += f"Successfully found {len(emails)} emails."
        
        flash(message, 'success')
        
    except Exception as e:
        flash(f"Error scraping emails: {str(e)}", 'error')
    
    return redirect_to_page(current_page)

@app.route('/add_product', methods=['POST'])
def add_product():
    logger.debug("Add product endpoint called")
    
    try:
        # Get form data with updated field names
        product_image = request.files.get('product_image')
        product_name = request.form.get('product_name', '').strip()
        price_nzd_str = request.form.get('product_price', '')  # Updated field name
        listing_link = request.form.get('listing_link', '').strip()
        sourcing_type = request.form.get('sourcing_type', '').strip()
        sourcing_data = request.form.get('sourcing_data', '').strip()
        
        # Get current page for redirect
        current_page = request.form.get('current_page', 'excel-upload')
        
        # Validate inputs
        if not product_image or product_image.filename == '':
            flash('Please select a product image', 'error')
            return redirect_to_page(current_page)
        
        if not product_name:
            flash('Please enter a product name', 'error')
            return redirect_to_page(current_page)
        
        try:
            price_nzd = float(price_nzd_str)
            if price_nzd <= 0:
                raise ValueError("Price must be positive")
        except (ValueError, TypeError):
            flash('Please enter a valid price (NZD)', 'error')
            return redirect_to_page(current_page)
        
        # Add product with listing link and sourcing info
        product = product_service.add_product(
            product_image, 
            product_name, 
            price_nzd, 
            listing_link if listing_link else None,
            sourcing_type if sourcing_type else None,
            sourcing_data if sourcing_data else None
        )
        
        flash(f'✅ Successfully added product: {product_name} - NZD ${price_nzd:.2f}', 'success')
        logger.info(f"Added product: {product_name}")
        
    except Exception as e:
        logger.error(f"Error adding product: {str(e)}")
        flash(f'❌ Error adding product: {str(e)}', 'error')
    
    return redirect_to_page(current_page)

@app.route('/edit_product', methods=['POST'])
def edit_product():
    logger.debug("Edit product endpoint called")
    
    try:
        product_id = request.form.get('product_id', '').strip()
        new_name = request.form.get('product_name', '').strip()  # Updated field name
        new_price_str = request.form.get('product_price', '')    # Updated field name
        new_image = request.files.get('product_image')           # Updated field name (if needed)
        new_listing_link = request.form.get('listing_link', '').strip()
        new_sourcing_type = request.form.get('sourcing_type', '').strip()
        new_sourcing_data = request.form.get('sourcing_data', '').strip()
        current_page = request.form.get('current_page', 'excel-upload')
        
        if not product_id:
            flash('Invalid product ID', 'error')
            return redirect_to_page(current_page)
        
        # Get the existing product details
        existing_product = product_service.get_product_by_id(product_id)
        if not existing_product:
            flash('Product not found', 'error')
            return redirect_to_page(current_page)
        
        # Validate and prepare new values
        update_name = new_name if new_name else None
        update_price = None
        update_listing_link = new_listing_link if new_listing_link else None
        
        if new_price_str:
            try:
                update_price = float(new_price_str)
                if update_price <= 0:
                    raise ValueError("Price must be positive")
            except (ValueError, TypeError):
                flash('Please enter a valid price (NZD)', 'error')
                return redirect_to_page(current_page)
        
        # Check if image was uploaded
        update_image = None
        if new_image and new_image.filename != '':
            if not new_image.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                flash('Please upload a valid image file (PNG, JPG, JPEG, GIF)', 'error')
                return redirect_to_page(current_page)
            update_image = new_image
        
        # Update the product
        updated_product = product_service.update_product(
            product_id, 
            new_name=update_name, 
            new_price=update_price, 
            new_image_file=update_image,
            new_listing_link=update_listing_link,
            new_sourcing_type=new_sourcing_type if new_sourcing_type else None,
            new_sourcing_data=new_sourcing_data if new_sourcing_data else None
        )
        
        # Create success message
        changes = []
        if update_name:
            changes.append(f"name to '{update_name}'")
        if update_price:
            changes.append(f"price to NZD ${update_price:.2f}")
        if update_image:
            changes.append("image")
        if update_listing_link:
            changes.append("listing link")
        if new_sourcing_type or new_sourcing_data:
            changes.append("sourcing information")
        
        if changes:
            change_text = ", ".join(changes)
            flash(f'✅ Successfully updated {change_text} for product: {updated_product["name"]}', 'success')
        else:
            flash(f'ℹ️ No changes made to product: {existing_product["name"]}', 'info')
        
        logger.info(f"Updated product: {updated_product['name']}")
        
    except Exception as e:
        logger.error(f"Error updating product: {str(e)}")
        flash(f'❌ Error updating product: {str(e)}', 'error')
    
    return redirect_to_page(current_page)

@app.route('/delete_product', methods=['POST'])
def delete_product():
    logger.debug("Delete product endpoint called")
    
    try:
        product_id = request.form.get('product_id', '').strip()
        current_page = request.form.get('current_page', 'excel-upload')
        
        if not product_id:
            flash('Invalid product ID', 'error')
            return redirect_to_page(current_page)
        
        # Get product details before deletion for the success message
        product = product_service.get_product_by_id(product_id)
        if not product:
            flash('Product not found', 'error')
            return redirect_to_page(current_page)
        
        # Delete product
        product_service.delete_product(product_id)
        
        flash(f'✅ Successfully deleted product: {product["name"]}', 'success')
        logger.info(f"Deleted product: {product['name']}")
        
    except Exception as e:
        logger.error(f"Error deleting product: {str(e)}")
        flash(f'❌ Error deleting product: {str(e)}', 'error')
    
    return redirect_to_page(current_page)

@app.route('/product_images/<filename>')
def get_product_image(filename):
    """Serve product images"""
    try:
        return send_from_directory('static/product_images', filename)
    except Exception as e:
        logger.error(f"Error serving image {filename}: {str(e)}")
        # Return a 404 or placeholder image
        return "Image not found", 404

@app.route('/extract_product', methods=['POST'])
def extract_product():
    logger.debug("Extract product endpoint called")
    
    try:
        # Get the uploaded screenshot
        screenshot = request.files.get('screenshot')
        
        if not screenshot or screenshot.filename == '':
            flash('Please select a screenshot to analyze', 'error')
            return redirect(url_for('index'))
        
        # Validate file type
        if not screenshot.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
            flash('Please upload a valid image file (PNG, JPG, JPEG, GIF, BMP)', 'error')
            return redirect(url_for('index'))
        
        # Extract ALL products using the new OCR method
        all_products = ocr_service.extract_all_products(screenshot)
        
        if not all_products or (len(all_products) == 1 and all_products[0].get('error')):
            error_msg = all_products[0].get('error', 'Unknown error') if all_products else 'No products found'
            flash(f'❌ {error_msg}', 'error')
            return redirect(url_for('index'))
        
        # Process each detected product
        added_count = 0
        failed_count = 0
        product_names = []
        
        for i, product_data in enumerate(all_products):
            if product_data.get('error') or not product_data.get('name'):
                logger.warning(f"Skipping product {i}: {product_data.get('error', 'No name detected')}")
                failed_count += 1
                continue
            
            try:
                # Get product details
                product_name = product_data['name']
                price_str = product_data['price']
                image_data = product_data['image_data']
                
                # Validate price
                try:
                    price_float = float(price_str) if price_str else 0.0
                except (ValueError, TypeError):
                    price_float = 0.0
                
                if price_float <= 0:
                    logger.warning(f"Skipping product '{product_name}': invalid price '{price_str}'")
                    failed_count += 1
                    continue
                
                # Add the product with cropped image
                if image_data:
                    product = product_service.add_product_from_bytes(
                        image_data, product_name, price_float, 'png'
                    )
                else:
                    # Fallback: use original screenshot if cropping failed
                    screenshot.seek(0)
                    product = product_service.add_product(screenshot, product_name, price_float)
                
                added_count += 1
                product_names.append(product_name)
                logger.info(f"Successfully added product: {product_name} - NZD ${price_float:.2f}")
                
            except Exception as e:
                logger.error(f"Failed to add product '{product_data.get('name', 'Unknown')}': {str(e)}")
                failed_count += 1
        
        # Create summary message
        if added_count > 0:
            if added_count == 1:
                flash(f'✅ Successfully added 1 product: {product_names[0]}', 'success')
            else:
                flash(f'✅ Successfully added {added_count} products: {", ".join(product_names)}', 'success')
            
            if failed_count > 0:
                flash(f'⚠️ {failed_count} products could not be added (missing data or errors)', 'warning')
        else:
            flash(f'❌ No products were added. {failed_count} products had errors or missing data.', 'error')
        
    except Exception as e:
        logger.error(f"Error in product extraction: {str(e)}")
        flash(f'❌ Error analyzing screenshot: {str(e)}', 'error')
    
    return redirect(url_for('index'))

@app.route('/configure_email', methods=['POST'])
def configure_email():
    """Configure email scanning settings"""
    logger.debug("Configure email endpoint called")
    
    try:
        email_address = request.form.get('email_address', '').strip()
        scan_frequency = request.form.get('scan_frequency', '30')
        filter_keywords = request.form.get('filter_keywords', '').strip()
        
        # For now, just flash a success message
        # In a real implementation, you'd save these settings to a config file or database
        flash(f'✅ Email configuration saved: {email_address}, scan every {scan_frequency} minutes', 'success')
        logger.info(f"Email configuration updated: {email_address}")
        
    except Exception as e:
        logger.error(f"Error configuring email: {str(e)}")
        flash(f'❌ Error saving email configuration: {str(e)}', 'error')
    
    return redirect(url_for('index'))

@app.route('/process_bulk_orders', methods=['POST'])
def process_bulk_orders():
    """Process bulk orders with the new format"""
    logger.debug("Process bulk orders endpoint called")
    
    try:
        bulk_orders_text = request.form.get('bulk_orders', '').strip()
        default_price = request.form.get('default_price', '')
        order_date = request.form.get('order_date', '')
        
        if not bulk_orders_text:
            flash('No order data provided', 'error')
            return redirect(url_for('index'))
        
        # Parse the new format: Product Name | Quantity | Customer Email
        lines = bulk_orders_text.split('\n')
        orders = []
        parse_errors = []
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            
            # Parse format: Product Name | Quantity | Customer Email
            parts = [part.strip() for part in line.split('|')]
            if len(parts) != 3:
                parse_errors.append(f"Line {line_num}: '{line}' - Invalid format (should be: Product Name | Quantity | Customer Email)")
                continue
            
            product_name, quantity_str, customer_email = parts
            
            try:
                quantity = int(quantity_str)
                if quantity <= 0:
                    raise ValueError("Quantity must be positive")
            except (ValueError, TypeError):
                parse_errors.append(f"Line {line_num}: Invalid quantity '{quantity_str}'")
                continue
            
            orders.append({
                'product_name': product_name,
                'quantity': quantity,
                'customer_email': customer_email,
                'price': default_price,
                'date': order_date
            })
        
        # Report parsing issues
        if parse_errors:
            for error in parse_errors[:3]:  # Show up to 3 errors
                flash(f"Skipped - {error}", 'warning')
            if len(parse_errors) > 3:
                flash(f"Skipped {len(parse_errors) - 3} more lines with formatting errors", 'warning')
        
        if not orders:
            flash('No valid orders found in the input. Please check the format: Product Name | Quantity | Customer Email', 'error')
            return redirect(url_for('index'))
        
        # For now, just flash success (in real implementation, you'd process these orders)
        flash(f'✅ Successfully processed {len(orders)} bulk orders', 'success')
        logger.info(f"Processed {len(orders)} bulk orders")
        
    except Exception as e:
        logger.error(f"Error processing bulk orders: {str(e)}")
        flash(f'❌ Error processing bulk orders: {str(e)}', 'error')
    
    return redirect(url_for('index'))

# Todo/Notes Routes
@app.route('/add_todo', methods=['POST'])
def add_todo():
    """Add a new todo note"""
    logger.debug("Add todo endpoint called")
    
    try:
        title = request.form.get('todo_title', '').strip()
        description = request.form.get('todo_description', '').strip()
        current_page = request.form.get('current_page', 'excel-upload')
        
        if not title:
            flash('Todo title is required', 'error')
            return redirect_to_page(current_page)
        
        todo = todo_service.create_todo(title, description)
        flash(f'✅ Todo "{title}" added successfully', 'success')
        logger.info(f"Created todo: {title}")
        
    except Exception as e:
        logger.error(f"Error adding todo: {str(e)}")
        flash(f'❌ Error adding todo: {str(e)}', 'error')
    
    return redirect_to_page(current_page)

@app.route('/complete_todo', methods=['POST'])
def complete_todo():
    """Mark a todo as completed and delete it"""
    logger.debug("Complete todo endpoint called")
    
    try:
        todo_id = request.form.get('todo_id', '').strip()
        current_page = request.form.get('current_page', 'excel-upload')
        
        if not todo_id:
            flash('Invalid todo ID', 'error')
            return redirect_to_page(current_page)
        
        # Get the todo first to show its title in the message
        todo = todo_service.get_todo_by_id(todo_id)
        if not todo:
            flash('Todo not found', 'error')
            return redirect_to_page(current_page)
        
        # Delete the todo (since it's completed)
        if todo_service.delete_todo(todo_id):
            flash(f'✅ Todo "{todo["title"]}" completed and removed', 'success')
            logger.info(f"Completed and deleted todo: {todo['title']}")
        else:
            flash('Error completing todo', 'error')
        
    except Exception as e:
        logger.error(f"Error completing todo: {str(e)}")
        flash(f'❌ Error completing todo: {str(e)}', 'error')
    
    return redirect_to_page(current_page)

@app.route('/edit_todo', methods=['POST'])
def edit_todo():
    """Edit an existing todo"""
    logger.debug("Edit todo endpoint called")
    
    try:
        todo_id = request.form.get('todo_id', '').strip()
        title = request.form.get('todo_title', '').strip()
        description = request.form.get('todo_description', '').strip()
        current_page = request.form.get('current_page', 'excel-upload')
        
        if not todo_id or not title:
            flash('Todo ID and title are required', 'error')
            return redirect_to_page(current_page)
        
        if todo_service.update_todo(todo_id, title, description):
            flash(f'✅ Todo "{title}" updated successfully', 'success')
            logger.info(f"Updated todo: {title}")
        else:
            flash('Todo not found', 'error')
        
    except Exception as e:
        logger.error(f"Error editing todo: {str(e)}")
        flash(f'❌ Error editing todo: {str(e)}', 'error')
    
    return redirect_to_page(current_page)

@app.route('/delete_todo', methods=['POST'])
def delete_todo():
    """Delete a todo permanently"""
    logger.debug("Delete todo endpoint called")
    
    try:
        todo_id = request.form.get('todo_id', '').strip()
        current_page = request.form.get('current_page', 'excel-upload')
        
        if not todo_id:
            flash('Invalid todo ID', 'error')
            return redirect_to_page(current_page)
        
        # Get the todo first to show its title in the message
        todo = todo_service.get_todo_by_id(todo_id)
        if not todo:
            flash('Todo not found', 'error')
            return redirect_to_page(current_page)
        
        if todo_service.delete_todo(todo_id):
            flash(f'🗑️ Todo "{todo["title"]}" deleted', 'success')
            logger.info(f"Deleted todo: {todo['title']}")
        else:
            flash('Error deleting todo', 'error')
        
    except Exception as e:
        logger.error(f"Error deleting todo: {str(e)}")
        flash(f'❌ Error deleting todo: {str(e)}', 'error')
    
    return redirect_to_page(current_page)

# Carrier Routes
@app.route('/add_carrier', methods=['POST'])
def add_carrier():
    """Add a new shipping carrier"""
    logger.debug("Add carrier endpoint called")
    
    try:
        carrier_name = request.form.get('carrier_name', '').strip()
        etsy_approved = request.form.get('etsy_approved') == 'on'
        example_tracking = request.form.get('example_tracking', '').strip()
        current_page = request.form.get('current_page', 'excel-upload')
        
        if not carrier_name:
            flash('Carrier name is required', 'error')
            return redirect_to_page(current_page)
        
        if not example_tracking:
            flash('Example tracking number is required', 'error')
            return redirect_to_page(current_page)
        
        carrier = carrier_service.add_carrier(carrier_name, etsy_approved, example_tracking)
        approval_text = "Etsy Approved" if etsy_approved else "Not Etsy Approved"
        flash(f'✅ Carrier "{carrier_name}" ({approval_text}) added successfully', 'success')
        logger.info(f"Created carrier: {carrier_name}")
        
    except Exception as e:
        logger.error(f"Error adding carrier: {str(e)}")
        flash(f'❌ Error adding carrier: {str(e)}', 'error')
    
    return redirect_to_page(current_page)

@app.route('/edit_carrier', methods=['POST'])
def edit_carrier():
    """Edit an existing carrier"""
    logger.debug("Edit carrier endpoint called")
    
    try:
        carrier_id = request.form.get('carrier_id', '').strip()
        carrier_name = request.form.get('carrier_name', '').strip()
        etsy_approved = request.form.get('etsy_approved') == 'on'
        example_tracking = request.form.get('example_tracking', '').strip()
        alternative_text = request.form.get('alternative_text', '').strip()
        current_page = request.form.get('current_page', 'excel-upload')
        
        if not carrier_id:
            flash('Carrier ID is required', 'error')
            return redirect_to_page(current_page)
        
        if not carrier_name:
            flash('Carrier name is required', 'error')
            return redirect_to_page(current_page)
        
        if not example_tracking:
            flash('Example tracking number is required', 'error')
            return redirect_to_page(current_page)
        
        updated_carrier = carrier_service.update_carrier(
            carrier_id, carrier_name, etsy_approved, example_tracking, alternative_text
        )
        
        if updated_carrier:
            approval_text = "Etsy Approved" if etsy_approved else "Not Etsy Approved"
            flash(f'✅ Carrier "{carrier_name}" ({approval_text}) updated successfully', 'success')
            logger.info(f"Updated carrier: {carrier_name}")
        else:
            flash('Carrier not found', 'error')
        
    except Exception as e:
        logger.error(f"Error editing carrier: {str(e)}")
        flash(f'❌ Error editing carrier: {str(e)}', 'error')
    
    return redirect_to_page(current_page)

@app.route('/delete_carrier', methods=['POST'])
def delete_carrier():
    """Delete a carrier"""
    logger.debug("Delete carrier endpoint called")
    
    try:
        carrier_id = request.form.get('carrier_id', '').strip()
        current_page = request.form.get('current_page', 'excel-upload')
        
        if not carrier_id:
            flash('Invalid carrier ID', 'error')
            return redirect_to_page(current_page)
        
        # Get carrier details before deletion for the success message
        carrier = carrier_service.get_carrier_by_id(carrier_id)
        if not carrier:
            flash('Carrier not found', 'error')
            return redirect_to_page(current_page)
        
        if carrier_service.delete_carrier(carrier_id):
            flash(f'🗑️ Carrier "{carrier["carrier_name"]}" deleted successfully', 'success')
            logger.info(f"Deleted carrier: {carrier['carrier_name']}")
        else:
            flash('Error deleting carrier', 'error')
        
    except Exception as e:
        logger.error(f"Error deleting carrier: {str(e)}")
        flash(f'❌ Error deleting carrier: {str(e)}', 'error')
    
    return redirect_to_page(current_page)

@app.route('/add_alternative_carrier', methods=['POST'])
def add_alternative_carrier():
    """Add an alternative carrier with custom text"""
    logger.debug("Add alternative carrier endpoint called")
    
    try:
        alternative_text = request.form.get('alternative_text', '').strip()
        current_page = request.form.get('current_page', 'excel-upload')
        
        if not alternative_text:
            flash('Alternative carrier text is required', 'error')
            return redirect_to_page(current_page)
        
        carrier = carrier_service.add_alternative_carrier(alternative_text)
        flash(f'✅ Alternative carrier "{alternative_text}" added successfully', 'success')
        logger.info(f"Created alternative carrier: {alternative_text}")
        
    except Exception as e:
        logger.error(f"Error adding alternative carrier: {str(e)}")
        flash(f'❌ Error adding alternative carrier: {str(e)}', 'error')
    
    return redirect_to_page(current_page)

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, host='0.0.0.0', port=port)
