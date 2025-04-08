import re
import datetime
import io
import logging
from pdf2image import convert_from_bytes
from PIL import Image, ImageOps
import pytesseract
from transformers import pipeline

logger = logging.getLogger(__name__)

POPPLER_PATH = r'C:\poppler-24.08.0\Library\bin'
TESSERACT_PATH = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

try:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
except Exception as e:
    logger.error(f"Tesseract initialization error: {e}")
    raise RuntimeError("Tesseract not properly configured")

# Initialize transformer-based NER pipeline.
ner_pipeline = pipeline("ner", model="dslim/bert-base-NER", aggregation_strategy="simple")

def clean_ocr_text(text):
    """Clean OCR text by reducing extra spaces while preserving newlines."""
    lines = text.splitlines()
    filtered_lines = [line for line in lines if not re.search(r"^(SE PAGE|PAGE \d+)", line, re.IGNORECASE)]
    cleaned_lines = [re.sub(r'\s+', ' ', line).strip() for line in filtered_lines]
    return "\n".join(cleaned_lines)

def enhanced_ocr(image):
    """Enhance image quality for OCR by converting to grayscale and autocontrast."""
    gray = image.convert('L')
    enhanced = ImageOps.autocontrast(gray)
    return pytesseract.image_to_string(enhanced)

def parse_date(raw_date):
    date_formats = [
        "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y", "%d/%m/%y",
        "%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"
    ]
    for fmt in date_formats:
        try:
            dt = datetime.datetime.strptime(raw_date, fmt)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            continue
    return datetime.datetime.today().strftime("%Y-%m-%d")

def extract_text_from_pdf(pdf_bytes):
    try:
        images = convert_from_bytes(pdf_bytes, poppler_path=POPPLER_PATH)
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        raise ValueError(f"PDF processing failed: {str(e)}")
    full_text = ""
    for image in images:
        try:
            page_text = pytesseract.image_to_string(image)
            if len(page_text.strip()) < 100:
                page_text = enhanced_ocr(image)
            full_text += page_text + "\n"
        except Exception as e:
            logger.error(f"Page processing error: {e}")
            continue
    return full_text

def extract_text(file_obj):
    file_obj.seek(0)
    content_type = file_obj.content_type.lower()
    if content_type == "application/pdf":
        pdf_bytes = file_obj.read()
        return extract_text_from_pdf(pdf_bytes)
    elif content_type in ["image/jpeg", "image/png"]:
        try:
            image = Image.open(io.BytesIO(file_obj.read()))
            text = pytesseract.image_to_string(image)
            if len(text.strip()) < 100:
                text = enhanced_ocr(image)
            return text
        except Exception as e:
            logger.error(f"Image extraction error: {e}")
            raise ValueError(f"Image processing failed: {str(e)}")
    else:
        raise ValueError(f"Unsupported file type: {content_type}")

def extract_field(pattern, text, default=""):
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else default

def extract_vendor_name(text):
    """
    Extract a human-readable vendor name by processing the first few lines
    of the OCR text. It removes unwanted headers and email addresses and then
    joins the first two meaningful lines.
    """
    lines = text.splitlines()
    candidate_lines = []
    
    # Process the first 5 lines for vendor information.
    for line in lines[:5]:
        line = line.strip()
        if not line:
            continue
        # Skip headers or ambiguous lines.
        if line.upper() == "INVOICE" or line.lower().startswith("bill to"):
            continue
        # Remove any email addresses from the line.
        line = re.sub(r"[\w\.-]+@[\w\.-]+\.\w+", "", line).strip()
        # If the resulting line is not too short, add it as a candidate.
        if len(line) > 3:
            candidate_lines.append(line)
    
    # If we have at least two candidate lines, join the first two.
    if len(candidate_lines) >= 2:
        vendor_name = candidate_lines[0] + " " + candidate_lines[1]
    elif candidate_lines:
        vendor_name = candidate_lines[0]
    else:
        vendor_name = "Unknown Vendor"
    
    # Clean trailing artifacts (e.g. remove trailing " m")
    vendor_name = re.sub(r'\s+m$', '', vendor_name).strip()
    return vendor_name

def extract_invoice_number(text):
    patterns = [
        r'Invoice\s*(?:No|#|Number)[:\s-]+([A-Z0-9\-]+)',
        r'Bill\s*(?:No|#|Number)[:\s-]+([A-Z0-9\-]+)',
        r'Invoice no\.?:\s*([A-Z0-9\-]+)'
    ]
    for pattern in patterns:
        inv_num = extract_field(pattern, text)
        if inv_num:
            return inv_num
    potential_numbers = re.findall(r'\b\d{3,}\b', text)
    if potential_numbers:
        return potential_numbers[0]
    return None

def extract_invoice_date(text):
    date_patterns = [
        r'Invoice\s*Date[:\s-]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        r'Date[:\s-]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
    ]
    for pattern in date_patterns:
        raw_date = extract_field(pattern, text)
        if raw_date:
            parsed = parse_date(raw_date)
            if parsed:
                return parsed
    return datetime.datetime.today().strftime("%Y-%m-%d")

def extract_amount(text):
    patterns = [
        r'Total Due[:\s-]*\$?\s*([\d,]+\.\d{2})',
        r'Grand Total[:\s-]*\$?\s*([\d,]+\.\d{2})'
    ]
    for pattern in patterns:
        amt = extract_field(pattern, text, default="0.00")
        if amt and amt != "0.00":
            try:
                return f"{float(amt.replace(',', '')):.2f}"
            except:
                continue
    currency_matches = re.findall(r'\$?\s*(\d+\.\d{2})\b', text)
    if currency_matches:
        try:
            return f"{max(float(x) for x in currency_matches):.2f}"
        except:
            pass
    return "0.00"

def extract_invoice_fields_universal(text):
    cleaned_text = clean_ocr_text(text)
    # Do not truncate text now—use the full text for invoice number and date extraction.
    
    vendor_name = extract_vendor_name(cleaned_text)
    invoice_number = extract_invoice_number(cleaned_text)
    if not invoice_number:
        invoice_number = f"INV-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
    invoice_date = extract_invoice_date(cleaned_text)
    amount = extract_amount(cleaned_text)
    
    account_number = extract_field(r"Account Number[:\s\-]*(\S+)", cleaned_text)
    items_supplied = extract_field(r"Items Supplied[:\s\-]*(.+)", cleaned_text)
    category = extract_field(r"Category[:\s\-]*(.+)", cleaned_text)
    address_line_1 = extract_field(r"Address(?: Line 1)?[:\s\-]*(.+)", cleaned_text)
    address_line_2 = extract_field(r"Address(?: Line 2)?[:\s\-]*(.+)", cleaned_text)
    city = extract_field(r"City[:\s\-]*(.+)", cleaned_text)
    state = extract_field(r"State[:\s\-]*(.+)", cleaned_text)
    zip_code = extract_field(r"ZIP Code[:\s\-]*(\S+)", cleaned_text)
    contact_email = extract_field(r"([\w\.-]+@[\w\.-]+\.\w+)", cleaned_text)
    contact_phone = extract_field(r"Contact Phone[:\s\-]*(\S+)", cleaned_text)
    bank_account_number = extract_field(r"Bank Account Number[:\s\-]*(\S+)", cleaned_text)
    routing_number = extract_field(r"Routing Number[:\s\-]*(\S+)", cleaned_text)
    bank_name = extract_field(r"Bank Name[:\s\-]*(.+)", cleaned_text)
    account_payee = extract_field(r"Account Payee[:\s\-]*(.+)", cleaned_text)
    
    if len(vendor_name) > 255:
        vendor_name = vendor_name[:255]
    
    return {
        "vendor_name": vendor_name,
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "amount": amount,
        "account_number": account_number,
        "items_supplied": items_supplied,
        "category": category,
        "address_line_1": address_line_1,
        "address_line_2": address_line_2,
        "city": city,
        "state": state,
        "zip_code": zip_code,
        "contact_email": contact_email,
        "contact_phone": contact_phone,
        "bank_account_number": bank_account_number,
        "routing_number": routing_number,
        "bank_name": bank_name,
        "account_payee": account_payee,
    }

def extract_invoice_data_hybrid(file_obj):
    try:
        text = extract_text(file_obj)
        if not text.strip():
            raise ValueError("No text could be extracted from the file")
        fields = extract_invoice_fields_universal(text)
        logger.info(f"Parsed Invoice Fields: {fields}")
        return fields
    except Exception as e:
        logger.error(f"Invoice processing error: {e}", exc_info=True)
        raise ValueError(f"Invoice processing failed: {str(e)}")
