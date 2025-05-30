# output_manager.py
import logging
import csv
from datetime import date # Keep this import
from config import Config

logger = logging.getLogger(__name__)

# Define the CSV header as a global constant
# This MUST match the original CSV structure your app expects.
CSV_EXPORT_HEADER = [
    'Company Name',
    'Website',
    'Potential Pain Points',
    'Contact Email',
    'Source URL',
    'Date Added',
    'Is Duplicate',
    'Lead Category' # This was 'segment_name_internal' or 'category' in our data
]

def write_to_csv(data: list, filename: str):
    """
    Writes the processed company data to a CSV file (OVERWRITING).
    Uses the global CSV_EXPORT_HEADER.
    """
    logger.info(f"Writing data for {len(data)} processed entries to {filename}")

    if not data:
        logger.warning("No data provided to write_to_csv function.")
        return

    # Use set for efficient duplicate name checking within the output batch
    processed_company_names_in_batch = set()
    rows_written = 0
    skipped_generic = 0
    skipped_missing_data = 0
    today_date = date.today().isoformat()

    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            # Use the global CSV_EXPORT_HEADER for DictWriter fieldnames
            writer = csv.DictWriter(csvfile, fieldnames=CSV_EXPORT_HEADER)
            writer.writeheader() # Write the header row

            for company_info in data:
                if not isinstance(company_info, dict):
                    logger.warning(f"Skipping non-dictionary item in data: {type(company_info)}")
                    skipped_missing_data += 1
                    continue

                company_name = company_info.get('name', '').strip()
                # 'category' field in company_info should hold the segment name
                lead_category = company_info.get('category', 'Unknown Segment') 

                if not company_name:
                    logger.warning(f"Skipping entry with missing company name: {company_info.get('website', 'N/A')}")
                    skipped_missing_data += 1
                    continue

                if company_name.lower() in Config.GENERIC_COMPANY_NAMES:
                    logger.debug(f"Skipping CSV write for generic name: '{company_name}'")
                    skipped_generic += 1
                    continue

                is_duplicate_in_batch = company_name in processed_company_names_in_batch
                processed_company_names_in_batch.add(company_name)

                # Prepare row data ensuring keys match CSV_EXPORT_HEADER
                row_to_write = {
                    'Company Name': company_name,
                    'Website': company_info.get('website', 'N/A'),
                    'Potential Pain Points': company_info.get('pain_points', ''),
                    'Contact Email': company_info.get('contact_email', ''),
                    'Source URL': company_info.get('source_url', 'N/A'), # Ensure this key exists in company_info
                    'Date Added': today_date,
                    'Is Duplicate': str(is_duplicate_in_batch),
                    'Lead Category': lead_category # This comes from company_info['category']
                }
                
                # Ensure only fields defined in header are written, and in correct order by DictWriter
                # Filter out any extra keys from company_info that are not in CSV_EXPORT_HEADER
                filtered_row = {k: row_to_write.get(k) for k in CSV_EXPORT_HEADER}
                writer.writerow(filtered_row)
                rows_written += 1

        logger.info(f"Successfully wrote {rows_written} company rows to {filename} (overwrite mode).")
        if skipped_generic > 0:
            logger.info(f"Skipped writing {skipped_generic} entries due to generic names.")
        if skipped_missing_data > 0:
             logger.info(f"Skipped writing {skipped_missing_data} entries due to missing essential data.")
        logger.info(f"Identified {len(processed_company_names_in_batch)} unique company names in this batch.")

    except IOError as e:
        logger.error(f"Error writing CSV file {filename}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error during CSV writing: {e}", exc_info=True)
