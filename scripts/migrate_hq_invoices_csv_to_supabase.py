"""
Migrate existing HQ invoices CSV data to Supabase
Reads CSV files from the standalone script's output folder and loads into hq_invoices table
"""
import os
import sys
import pandas as pd
import psycopg2
import glob
import re
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_csv_files(source_folder: str, days: int = 30) -> pd.DataFrame:
    """
    Process CSV files from the standalone script output folder
    Only processes files from the last N days (default: 30)
    """
    csv_files = glob.glob(os.path.join(source_folder, '**/*.csv'), recursive=True)
    
    # Filter out hidden files
    csv_files = [f for f in csv_files if not os.path.basename(f).startswith('~$')]
    
    logger.info(f"Found {len(csv_files)} CSV files total")
    
    # Filter by date - only process files from last N days
    cutoff_date = datetime.now() - timedelta(days=days)
    filtered_files = []
    
    for file_path in csv_files:
        try:
            # Try to extract date from filename (format: *_YYYYMMDD.csv)
            filename = os.path.basename(file_path)
            date_match = re.search(r'(\d{8})', filename)
            if date_match:
                file_date_str = date_match.group(1)
                try:
                    file_date = datetime.strptime(file_date_str, '%Y%m%d')
                    if file_date >= cutoff_date:
                        filtered_files.append(file_path)
                    else:
                        logger.debug(f"Skipping {filename} (date: {file_date.date()}, older than {days} days)")
                except:
                    # If date parsing fails, include the file (better safe than sorry)
                    filtered_files.append(file_path)
            else:
                # If no date in filename, check file modification time
                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                if file_mtime >= cutoff_date:
                    filtered_files.append(file_path)
                else:
                    logger.debug(f"Skipping {filename} (modified: {file_mtime.date()}, older than {days} days)")
        except Exception as e:
            logger.warning(f"Error checking file date for {file_path}: {e}")
            # Include file if we can't determine date
            filtered_files.append(file_path)
    
    logger.info(f"Filtering to last {days} days: {len(filtered_files)} files to process")
    
    all_data = []
    
    for file_path in csv_files:
        try:
            df = pd.read_csv(file_path)
            filename = os.path.basename(file_path)
            
            # Determine file type based on filename pattern
            if re.match(r'^INV_', filename) or re.match(r'^DAIMA_.*_SD\d+_\d+\.csv$', filename):
                processed_df = process_invoice_file(df, filename)
            elif re.match(r'^BT_', filename) or re.match(r'.*_BTR\d+_\d+\.csv$', filename):
                processed_df = process_transfer_file(df, filename)
            else:
                # Try to determine type from content
                if 'DocumentType' in df.columns and any('Branch Transfer' in str(x) for x in df['DocumentType'].values):
                    processed_df = process_transfer_file(df, filename)
                else:
                    processed_df = process_invoice_file(df, filename)
            
            if processed_df is not None and not processed_df.empty:
                all_data.append(processed_df)
                logger.info(f"  Processed {filename}: {len(processed_df)} records")
            
        except Exception as e:
            logger.warning(f"Error processing file {file_path}: {e}")
            continue
    
    if not all_data:
        logger.error("No CSV files found or processed")
        return pd.DataFrame()
    
    if not all_data:
        logger.error("No CSV files found or processed")
        return pd.DataFrame()
    
    # Combine all DataFrames
    combined_df = pd.concat(all_data, ignore_index=True)
    logger.info(f"Total records combined: {len(combined_df)}")
    
    # Filter to last 30 days based on DATE column
    if 'DATE' in combined_df.columns and not combined_df['DATE'].isna().all():
        cutoff_date = datetime.now() - timedelta(days=30)
        initial_count = len(combined_df)
        combined_df = combined_df[combined_df['DATE'] >= cutoff_date]
        filtered_count = len(combined_df)
        if initial_count > filtered_count:
            logger.info(f"Filtered to last 30 days: {filtered_count:,} records (removed {initial_count - filtered_count:,} older records)")
    
    return combined_df

def process_invoice_file(df: pd.DataFrame, filename: str) -> pd.DataFrame:
    """Process invoice files"""
    processed_df = pd.DataFrame()
    
    # Map columns (case-insensitive)
    column_mapping = {
        'clientname': 'BRANCH',
        'dt_itemcode': 'ITEM CODE',
        'dt_itemname': 'ITEM NAME',
        'dt_quantity': 'QUANTITY',
        'hd2_comments': 'REF',
        'salesinnumber': 'INVOICE NUMBER',
        'hd2_date': 'DATE',
        'acctname': 'BRANCH',
        'documentnumber': 'INVOICE NUMBER',
        'documentdate': 'DATE',
        'itemcode': 'ITEM CODE',
        'itemname': 'ITEM NAME',
        'quantity': 'QUANTITY',
    }
    
    # Normalize column names
    df.columns = [col.lower().strip() for col in df.columns]
    
    # Apply mapping
    for old_name, new_name in column_mapping.items():
        if old_name in df.columns and new_name not in processed_df.columns:
            processed_df[new_name] = df[old_name]
    
    # Fill missing columns
    required_cols = ['BRANCH', 'ITEM CODE', 'ITEM NAME', 'QUANTITY', 'REF', 'DATE', 'INVOICE NUMBER']
    for col in required_cols:
        if col not in processed_df.columns:
            processed_df[col] = None
    
    # Convert DATE to datetime
    if 'DATE' in processed_df.columns:
        processed_df['DATE'] = pd.to_datetime(processed_df['DATE'], errors='coerce')
    
    # Add document type
    processed_df['DOCUMENT_TYPE'] = 'Invoice'
    
    return processed_df

def process_transfer_file(df: pd.DataFrame, filename: str) -> pd.DataFrame:
    """Process transfer files"""
    processed_df = pd.DataFrame()
    
    # Normalize column names
    df.columns = [col.lower().strip() for col in df.columns]
    
    # Map columns
    column_mapping = {}
    for col in df.columns:
        col_lower = col.lower()
        if 'customer' in col_lower or ('branch' in col_lower and 'name' in col_lower):
            column_mapping[col] = 'BRANCH'
        elif 'reference' in col_lower:
            column_mapping[col] = 'REF'
        elif 'date' in col_lower and 'document' in col_lower:
            column_mapping[col] = 'DATE'
        elif 'quantity' in col_lower:
            column_mapping[col] = 'QUANTITY'
        elif 'itemname' in col_lower or 'item name' in col_lower:
            column_mapping[col] = 'ITEM NAME'
        elif 'itemcode' in col_lower or 'item code' in col_lower:
            column_mapping[col] = 'ITEM CODE'
        elif 'documentnumber' in col_lower or 'transfer' in col_lower:
            column_mapping[col] = 'INVOICE NUMBER'
    
    # Apply mapping
    for old_name, new_name in column_mapping.items():
        if old_name in df.columns and new_name not in processed_df.columns:
            processed_df[new_name] = df[old_name]
    
    # Fill missing columns
    required_cols = ['BRANCH', 'ITEM CODE', 'ITEM NAME', 'QUANTITY', 'REF', 'DATE', 'INVOICE NUMBER']
    for col in required_cols:
        if col not in processed_df.columns:
            processed_df[col] = None
    
    # Convert DATE to datetime
    if 'DATE' in processed_df.columns:
        processed_df['DATE'] = pd.to_datetime(processed_df['DATE'], errors='coerce')
    
    # Add document type
    processed_df['DOCUMENT_TYPE'] = 'Branch Transfer'
    
    return processed_df

def calculate_monthly_quantities(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate monthly quantities and get last values per branch/item"""
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    # Filter current month
    current_month_df = df[
        (df['DATE'].dt.month == current_month) & 
        (df['DATE'].dt.year == current_year)
    ]
    
    # Calculate monthly quantities
    monthly_qty = current_month_df.groupby(['BRANCH', 'ITEM CODE'])['QUANTITY'].sum().reset_index()
    monthly_qty = monthly_qty.rename(columns={'QUANTITY': 'THIS_MONTH_QTY'})
    
    # Get last values per branch/item
    grouped = df.groupby(['BRANCH', 'ITEM CODE']).agg({
        'ITEM NAME': 'last',
        'REF': 'last',
        'DATE': 'max',
        'QUANTITY': 'last',
        'INVOICE NUMBER': 'last',
        'DOCUMENT_TYPE': 'last'
    }).reset_index()
    
    # Merge with monthly quantities
    final_output = pd.merge(
        grouped,
        monthly_qty,
        on=['BRANCH', 'ITEM CODE'],
        how='left'
    )
    
    # Fill NaN with 0
    final_output['THIS_MONTH_QTY'] = final_output['THIS_MONTH_QTY'].fillna(0)
    
    # Convert DATE to date only
    final_output['DATE'] = pd.to_datetime(final_output['DATE']).dt.date
    
    return final_output

def load_to_supabase(connection_string: str, df: pd.DataFrame):
    """Load processed data into Supabase hq_invoices table using bulk insert"""
    if df.empty:
        logger.error("No data to load")
        return False
    
    conn = None
    try:
        conn = psycopg2.connect(connection_string)
        conn.autocommit = False
        cursor = conn.cursor()
        
        logger.info(f"📥 Loading {len(df):,} records into hq_invoices table...")
        
        # Prepare data for bulk insert
        columns = [
            'branch', 'invoice_number', 'item_code', 'item_name', 'quantity', 
            'ref', 'date', 'document_type', 'source_branch', 'destination_branch', 'this_month_qty'
        ]
        
        # Use execute_values for faster bulk insert
        from psycopg2.extras import execute_values
        
        batch_size = 1000
        total_inserted = 0
        
        # Prepare data tuples
        data_tuples = []
        for _, row in df.iterrows():
            try:
                data_tuples.append((
                    str(row.get('BRANCH', '')),
                    str(row.get('INVOICE NUMBER', '')),
                    str(row.get('ITEM CODE', '')),
                    str(row.get('ITEM NAME', '')),
                    float(row.get('QUANTITY', 0) or 0),
                    str(row.get('REF', '') or ''),
                    row.get('DATE'),
                    str(row.get('DOCUMENT_TYPE', 'Invoice')),
                    'BABA DOGO HQ',
                    str(row.get('BRANCH', '')),
                    float(row.get('THIS_MONTH_QTY', 0) or 0)
                ))
            except Exception as e:
                logger.warning(f"Skipping row due to error: {e}")
                continue
        
        logger.info(f"   Prepared {len(data_tuples):,} records for insertion")
        
        # Insert in batches using execute_values
        insert_sql = """
            INSERT INTO hq_invoices 
            (branch, invoice_number, item_code, item_name, quantity, ref, date, 
             document_type, source_branch, destination_branch, this_month_qty)
            VALUES %s
            ON CONFLICT (branch, invoice_number, item_code, date)
            DO UPDATE SET
                item_name = EXCLUDED.item_name,
                quantity = EXCLUDED.quantity,
                ref = EXCLUDED.ref,
                document_type = EXCLUDED.document_type,
                source_branch = EXCLUDED.source_branch,
                destination_branch = EXCLUDED.destination_branch,
                this_month_qty = EXCLUDED.this_month_qty,
                processed_at = CURRENT_TIMESTAMP
        """
        
        for i in range(0, len(data_tuples), batch_size):
            batch = data_tuples[i:i+batch_size]
            try:
                execute_values(cursor, insert_sql, batch, page_size=batch_size)
                conn.commit()
                total_inserted += len(batch)
                
                if total_inserted % 5000 == 0:
                    logger.info(f"   ✅ Inserted {total_inserted:,} / {len(data_tuples):,} records ({100*total_inserted//len(data_tuples)}%)...")
            except Exception as e:
                logger.error(f"   ❌ Error inserting batch {i//batch_size + 1}: {e}")
                conn.rollback()
                # Try row by row for this batch
                for row_data in batch:
                    try:
                        cursor.execute("""
                            INSERT INTO hq_invoices 
                            (branch, invoice_number, item_code, item_name, quantity, ref, date, 
                             document_type, source_branch, destination_branch, this_month_qty)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (branch, invoice_number, item_code, date)
                            DO UPDATE SET
                                item_name = EXCLUDED.item_name,
                                quantity = EXCLUDED.quantity,
                                ref = EXCLUDED.ref,
                                document_type = EXCLUDED.document_type,
                                source_branch = EXCLUDED.source_branch,
                                destination_branch = EXCLUDED.destination_branch,
                                this_month_qty = EXCLUDED.this_month_qty,
                                processed_at = CURRENT_TIMESTAMP
                        """, row_data)
                        conn.commit()
                        total_inserted += 1
                    except Exception as e2:
                        logger.warning(f"   Skipped duplicate or invalid row: {e2}")
                        conn.rollback()
                        continue
        
        logger.info(f"✅ Successfully inserted {total_inserted:,} records")
        
        # Verify
        cursor.execute("SELECT COUNT(*) FROM hq_invoices")
        result = cursor.fetchone()
        count = result[0] if result else 0
        logger.info(f"✅ Verified: {count:,} total rows in hq_invoices table")
        
        # Show date range
        try:
            cursor.execute("SELECT MIN(date), MAX(date) FROM hq_invoices WHERE date IS NOT NULL")
            date_range = cursor.fetchone()
            if date_range and date_range[0]:
                logger.info(f"📅 Date range: {date_range[0]} to {date_range[1]}")
        except Exception as e:
            logger.warning(f"Could not get date range: {e}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error loading to Supabase: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if conn:
            try:
                conn.rollback()
                cursor.close()
                conn.close()
            except:
                pass
        return False

if __name__ == "__main__":
    # Get connection string - command line argument takes priority
    connection_string = None
    
    if len(sys.argv) >= 2:
        connection_string = sys.argv[1]
        logger.info("✅ Using connection string from command line")
    else:
        # Try to load from app config
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            sys.path.insert(0, os.path.join(script_dir, ".."))
            from app.config import settings
            if settings.DATABASE_URL:
                connection_string = settings.DATABASE_URL
                logger.info("✅ Using DATABASE_URL from app.config")
        except Exception as e:
            logger.warning(f"Could not load from config: {e}")
    
    if not connection_string:
        logger.error("❌ No connection string provided!")
        logger.error("Usage: python migrate_hq_invoices_csv_to_supabase.py [connection_string] [source_folder]")
        logger.error("\nExample:")
        logger.error('  python migrate_hq_invoices_csv_to_supabase.py "postgresql://user:pass@host:port/db"')
        logger.error('  python migrate_hq_invoices_csv_to_supabase.py "postgresql://user:pass@host:port/db" "D:\\DATA ANALYTICS\\HQ_DAIMA_INVOICES"')
        sys.exit(1)
    
    # Get source folder (default: D:\DATA ANALYTICS\HQ_DAIMA_INVOICES)
    if len(sys.argv) >= 3:
        source_folder = sys.argv[2]
    else:
        source_folder = r"D:\DATA ANALYTICS\HQ_DAIMA_INVOICES"
    
    if not os.path.exists(source_folder):
        logger.error(f"❌ Source folder not found: {source_folder}")
        logger.info("Please provide the path to the folder containing CSV files from the standalone script")
        sys.exit(1)
    
    logger.info(f"📁 Processing CSV files from: {source_folder}")
    
    # Process CSV files
    combined_df = process_csv_files(source_folder)
    
    if combined_df.empty:
        logger.error("❌ No data to migrate")
        sys.exit(1)
    
    # Calculate monthly quantities and get last values
    logger.info("📊 Calculating monthly quantities and last values...")
    final_df = calculate_monthly_quantities(combined_df)
    logger.info(f"✅ Processed to {len(final_df)} unique branch/item combinations")
    
    # Load to Supabase
    success = load_to_supabase(connection_string, final_df)
    
    if success:
        logger.info("\n✅ Migration completed successfully!")
        logger.info("✅ HQ invoices data is now in Supabase")
        logger.info("✅ The fetcher will continue from here incrementally")
    else:
        logger.error("\n❌ Migration failed")
        sys.exit(1)

