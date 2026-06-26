import os
import csv
import glob
import logging

# Set up logger
logger = logging.getLogger(__name__)

# Dictionary of column synonyms for automatic mapping
HEADER_MAPPINGS = {
    "name": ["fullname", "contact name", "customer", "name"],
    "email": ["emailaddress", "email", "email_address"],
    "phone": ["phone", "phoneno", "phone_no", "telephone"],
    "address": ["fulladdress", "addr", "address", "location"],
    "birthdate": ["dob", "birthdate", "dateofbirth", "date_of_birth"]
}

class CSVExtractor:
    """Connector to scan and extract contacts from messy regional CSV exports."""

    def __init__(self, drop_dir: str = None):
        self.drop_dir = drop_dir or os.getenv("CSV_DROP_DIR", "/csv-drop")

    def _get_column_mapping(self, headers: list[str]) -> dict[str, str]:
        """Finds mapping from file headers to standardized internal keys using synonyms."""
        mapping = {}
        for h in headers:
            clean_h = h.strip().lower()
            for target_field, synonyms in HEADER_MAPPINGS.items():
                if clean_h in synonyms:
                    mapping[h] = target_field
                    break
        return mapping

    def _read_csv_file(self, file_path: str) -> list[dict]:
        """Reads a CSV file, automatically detecting and handling encoding (UTF-8 vs Windows-1252)."""
        encodings = ["utf-8", "windows-1252", "latin-1"]
        content = None
        
        for enc in encodings:
            try:
                logger.debug(f"Attempting to read {file_path} with encoding: {enc}")
                with open(file_path, "r", encoding=enc) as f:
                    # Attempt to read all lines to trigger decode exceptions early
                    content = f.read()
                # If we successfully read without error, use this encoding
                success_encoding = enc
                break
            except (UnicodeDecodeError, LookupError):
                continue
                
        if content is None:
            raise ValueError(f"Could not decode CSV file {file_path} with any supported encoding.")
            
        logger.info(f"Successfully decoded {os.path.basename(file_path)} using {success_encoding} encoding.")
        
        # Parse the read content using csv.reader
        lines = content.splitlines()
        reader = csv.reader(lines)
        
        headers = next(reader)
        col_map = self._get_column_mapping(headers)
        
        # Log which columns we identified
        identified = [col_map[h] for h in headers if h in col_map]
        logger.debug(f"Identified columns in {os.path.basename(file_path)}: {identified}")
        
        file_records = []
        for row_idx, row in enumerate(reader, start=1):
            if not row: # Skip empty rows
                continue
            
            raw_record = {}
            for col_idx, value in enumerate(row):
                if col_idx < len(headers):
                    raw_record[headers[col_idx]] = value.strip()
            
            # Map raw fields to standard intermediate keys
            standardized_record = {}
            for raw_key, value in raw_record.items():
                if raw_key in col_map:
                    standardized_record[col_map[raw_key]] = value
                    
            # Inject trace ID (filename + row index) to ensure uniqueness and traceability
            filename = os.path.basename(file_path)
            standardized_record["id"] = f"{filename}:{row_idx}"
            standardized_record["source_file"] = filename
            
            # Keep raw data copy for provenance
            standardized_record["raw_data"] = raw_record
            
            file_records.append(standardized_record)
            
        return file_records

    def extract(self) -> list[dict]:
        """Scans directory and extracts records from all CSV files found."""
        records = []
        search_path = os.path.join(self.drop_dir, "*.csv")
        csv_files = glob.glob(search_path)
        
        logger.info(f"Scanning directory '{self.drop_dir}' for CSV files...")
        if not csv_files:
            logger.warning(f"No CSV files found in directory: {self.drop_dir}")
            return []
            
        logger.info(f"Found {len(csv_files)} CSV files to process: {[os.path.basename(f) for f in csv_files]}")
        
        for file_path in csv_files:
            try:
                file_records = self._read_csv_file(file_path)
                records.extend(file_records)
                logger.info(f"Extracted {len(file_records)} records from {os.path.basename(file_path)}.")
            except Exception as e:
                logger.error(f"Error processing CSV file {file_path}: {e}")
                # We do not want one bad CSV file to crash the entire pipeline run,
                # but we raise it or skip it based on strict failure policy. 
                # Let's log and continue to show production-grade resilience, 
                # or add to a failed file list.
                continue
                
        logger.info(f"Successfully extracted a total of {len(records)} records from all CSV files.")
        return records
