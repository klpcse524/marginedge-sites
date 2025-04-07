import re
import datetime
from pdf2image import convert_from_bytes
from PIL import Image, ImageOps
import pytesseract
from transformers import pipeline

# Initialize transformer-based NER pipeline.
ner_pipeline = pipeline("ner", model="dslim/bert-base-NER", aggregation_strategy="simple")

# --------------------------
# Helper Functions
# --------------------------
def clean_ocr_text(text):
    """Clean OCR text by reducing extra spaces while preserving newlines."""
    lines = text.splitlines()
    filtered_lines = [line for line in lines if not re.search(r"^(SE PAGE|PAGE \d+)", line, re.IGNORECASE)]
    cleaned_lines = [re.sub(r'\s+', ' ', line).strip() for line in filtered_lines]
    return "\n".join(cleaned_lines)

def enhanced_ocr(image):
    """Enhance image quality for OCR by converting to grayscale and autocontrast."""
    gray = image.convert("L")
    enhanced = ImageOps.autocontrast(gray)
    return pytesseract.image_to_string(enhanced)

def parse_date(raw_date):
    """Parse a date string into ISO format (YYYY-MM-DD)."""
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%B %d, %Y", "%b %d, %Y"):
        try:
            dt = datetime.datetime.strptime(raw_date, fmt)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            continue
    return datetime.datetime.today().strftime("%Y-%m-%d")

def extract_text_from_pdf(file_bytes, poppler_path=r"C:\poppler-24.08.0\Library\bin"):
    try:
        images = convert_from_bytes(file_bytes, poppler_path=poppler_path)
    except Exception as e:
        print("Error converting PDF to images:", e)
        return ""
    text = ""
    for image in images:
        page_text = pytesseract.image_to_string(image)
        if len(page_text.strip()) < 50:
            page_text = enhanced_ocr(image)
        text += page_text + "\n"
    return text

def extract_text(file_obj, poppler_path=r"C:\poppler-24.08.0\Library\bin"):
    file_obj.seek(0)
    content_type = file_obj.content_type
    if content_type == "application/pdf":
        file_bytes = file_obj.read()
        return extract_text_from_pdf(file_bytes, poppler_path=poppler_path)
    elif content_type in ["image/jpeg", "image/png"]:
        try:
            image = Image.open(file_obj)
            text = pytesseract.image_to_string(image)
            if len(text.strip()) < 50:
                text = enhanced_ocr(image)
            return text
        except Exception as e:
            print("Error processing image:", e)
            return ""
    else:
        return ""

def extract_field(pattern, text, default=""):
    """Helper to extract a field using a regex pattern."""
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return default

# --------------------------
# Universal Extraction Function
# --------------------------
def extract_invoice_fields_universal(text):
    """
    Extract key invoice fields from OCR text using a combination of regex heuristics
    and a transformer-based NER fallback.
    """
    cleaned_text = clean_ocr_text(text)
    
    # Get transformer-based NER results.
    try:
        ner_results = ner_pipeline(cleaned_text)
    except Exception as e:
        print("Error with NER pipeline:", e)
        ner_results = []
    
    # --- Vendor Name ---
    vendor_name = extract_field(r"REMIT TO[:\-]?\s*(.+)", cleaned_text)
    if vendor_name:
        vendor_name = vendor_name.split("DBA")[0].strip()
    
    # If vendor name is missing, equals "INVOICE", or is empty, use first few lines.
    if not vendor_name or vendor_name.upper() == "INVOICE":
        candidate_lines = []
        # Limit to the first 5 lines to avoid later sections like "Bill to Ship to"
        for line in cleaned_text.splitlines()[:5]:
            line = line.strip()
            if not line or line.upper() == "INVOICE" or line.lower() == "bill to ship to":
                continue
            # Remove email addresses and phone numbers from the line
            line = re.sub(r"[\w\.-]+@[\w\.-]+\.\w+", "", line)
            line = re.sub(r"\+\d+", "", line)
            candidate_lines.append(line.strip())
        if candidate_lines:
            # Join the candidate lines; here we join all to form a vendor name.
            vendor_name = " ".join(candidate_lines)
    
    # Clean up trailing unwanted characters (e.g., remove a trailing " m")
    vendor_name = re.sub(r'\s+m$', '', vendor_name).strip() if vendor_name else ""
    # Fallback to NER for vendor name if still unsatisfactory.
    if not vendor_name or vendor_name.lower() == "unknown vendor":
        for ent in ner_results:
            if ent.get("entity_group") == "ORG":
                vendor_name = ent.get("word").strip()
                break
    if not vendor_name:
        vendor_name = "Unknown Vendor"
    
    # --- Invoice Number ---
    invoice_number = "Unknown Invoice"
    patterns_invoice = [
        r"Invoice Number[:\s\-]*([\w\d]+)",
        r"INVOICE[#]*\s*[:\-]\s*(\d+)",
        r"Invoice no\.?:\s*([\w\d-]+)"
    ]
    for pat in patterns_invoice:
        match = re.search(pat, cleaned_text, re.IGNORECASE)
        if match:
            invoice_number = match.group(1).strip()
            break
    if invoice_number == "Unknown Invoice":
        for line in cleaned_text.splitlines():
            if re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", line):
                numbers = re.findall(r"\d+", line)
                if numbers:
                    invoice_number = numbers[0]
                break

    # --- Invoice Date ---
    raw_date = extract_field(r"Invoice Date[:\s\-]*([\d/]+)", cleaned_text)
    if not raw_date:
        raw_date = extract_field(r"(Due Date|DELIVERY)[:\s\-]*([\d/]+)", cleaned_text)
    if not raw_date:
        match = re.search(r"(\d{1,2}/\d{1,2}/\d{2,4})", cleaned_text)
        raw_date = match.group(1).strip() if match else ""
    if not raw_date:
        for ent in ner_results:
            if ent.get("entity_group") == "DATE":
                raw_date = ent.get("word").strip()
                break
    invoice_date = parse_date(raw_date) if raw_date else datetime.datetime.today().strftime("%Y-%m-%d")
    
    # --- Amount ---
    amount = extract_field(r"TOTAL DUE[:\s]*\$?\s*([\d,]+\.\d{2})", cleaned_text, default="0.00")
    if amount == "0.00":
        for pattern in [r"NET\s+INVOICE[:\s\-]*\$?([\d,]+\.\d{2})",
                        r"INVOICE TOTAL[:\s\-]*\$?([\d,]+\.\d{2})",
                        r"Total Sale[:\s\-]*\$?([\d,]+\.\d{2})"]:
            amt = extract_field(pattern, cleaned_text)
            if amt and amt != "0.00":
                amount = amt
                break
    if amount == "0.00":
        subtotals = re.findall(r"(?:DISHWASHER SUB TOTAL|OTHER SUB TOTAL)[:\s]*\$?([\d,]+\.\d{2})", cleaned_text, re.IGNORECASE)
        if subtotals:
            try:
                total_sum = sum(float(val.replace(',', '')) for val in subtotals)
                amount = f"{total_sum:.2f}"
            except Exception:
                amount = "0.00"
    if amount == "0.00":
        for line in cleaned_text.splitlines():
            if "total" in line.lower():
                tokens = re.findall(r"([\d,]+\.\d{2})", line)
                if tokens:
                    amount = tokens[-1].replace(',', '').strip()
                    break
    if amount == "0.00":
        for ent in ner_results:
            if ent.get("entity_group") == "MONEY":
                amt_text = re.sub(r'[^\d.]', '', ent.get("word"))
                try:
                    amount = f"{float(amt_text):.2f}"
                    break
                except Exception:
                    continue
    
    # --- Additional Fields ---
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
    """Extract text from the file and then extract invoice fields using universal logic."""
    text = extract_text(file_obj)
    print("Extracted Text:\n", text)
    fields = extract_invoice_fields_universal(text)
    print("Parsed Invoice Fields:", fields)
    return fields
