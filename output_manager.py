# output_manager.py
import logging
import csv
from datetime import date
from config import Config # Import Config to use GENERIC_COMPANY_NAMES

# Configure logging
logger = logging.getLogger(__name__)

def write_to_csv(data: list, filename: str):
    """
    Writes the processed company data (including category) to a CSV file (OVERWRITING).

    Args:
        data: List of company data dictionaries (expected to have 'category' key)
        filename: Path to output CSV file
    """
    logger.info(f"Writing data for {len(data)} processed entries to {filename}")

    if not data:
        logger.warning("No data provided to write_to_csv function.")
        return

    # --- MODIFIED: Added 'Lead Category' to header, placed last ---
    header = [
        'Company Name',
        'Website',
        'Potential Pain Points',
        'Contact Email',
        'Source URL',
        'Date Added',
        'Is Duplicate', # Keep duplicate flag before category
        'Lead Category' # New column added at the end
    ]
    # --- END MODIFICATION ---

    # Use set for efficient duplicate name checking within the output batch
    processed_company_names_in_batch = set()
    rows_written = 0
    skipped_generic = 0
    skipped_missing_data = 0
    today_date = date.today().isoformat()

    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(header)

            for company_info in data:
                # Ensure it's a dictionary
                if not isinstance(company_info, dict):
                    logger.warning(f"Skipping non-dictionary item in data: {type(company_info)}")
                    skipped_missing_data += 1
                    continue

                company_name = company_info.get('name', '').strip()
                company_category = company_info.get('category', 'Unknown') # Get category

                # Basic check for essential data
                if not company_name:
                    logger.warning(f"Skipping entry with missing company name: {company_info.get('website', 'N/A')}")
                    skipped_missing_data += 1
                    continue

                # Skip generic company names (using Config)
                if company_name.lower() in Config.GENERIC_COMPANY_NAMES:
                    logger.debug(f"Skipping CSV write for generic name: '{company_name}'")
                    skipped_generic += 1
                    continue

                # Check for duplicates *within this specific output batch*
                # NOTE: This doesn't check against previous runs.
                is_duplicate_in_batch = company_name in processed_company_names_in_batch
                processed_company_names_in_batch.add(company_name)

                # Prepare row data including the new category
                row = [
                    company_name,
                    company_info.get('website', 'N/A'),
                    company_info.get('pain_points', ''),
                    company_info.get('contact_email', ''),
                    company_info.get('source_url', 'N/A'),
                    today_date,
                    str(is_duplicate_in_batch), # Duplicate status within this run
                    company_category # Add the category value here
                ]
                writer.writerow(row)
                rows_written += 1

        logger.info(f"Successfully wrote {rows_written} company rows to {filename} (overwrite mode).")
        if skipped_generic > 0:
            logger.info(f"Skipped writing {skipped_generic} entries due to generic names.")
        if skipped_missing_data > 0:
             logger.info(f"Skipped writing {skipped_missing_data} entries due to missing essential data.")
        # Log count of unique names identified *in this batch* for clarity
        logger.info(f"Identified {len(processed_company_names_in_batch)} unique company names in this batch.")

    except IOError as e:
        logger.error(f"Error writing CSV file {filename}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error during CSV writing: {e}", exc_info=True)
