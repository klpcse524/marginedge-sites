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
    # Filter out common header/footer lines.
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

# --------------------------
# Universal Extraction Function
# --------------------------
def extract_invoice_fields_universal(text):
    """
    Extract vendor_name, invoice_number, invoice_date, and amount from OCR text using a
    combination of regex heuristics and NER fallback.
    """
    cleaned_text = clean_ocr_text(text)
    upper_text = cleaned_text.upper()

    # --- Vendor Name ---
    vendor_name = None
    remit_match = re.search(r"REMIT TO[:\-]?\s*(.+)", cleaned_text, re.IGNORECASE)
    if remit_match:
        vendor_line = remit_match.group(1).strip()
        vendor_name = vendor_line.split("DBA")[0].strip()
    if not vendor_name:
        # Fallback: use the first non-empty line that is not a header.
        lines = [line for line in cleaned_text.splitlines() if line.strip() and not re.search(r"^(SE PAGE|PAGE \d+)", line, re.IGNORECASE)]
        vendor_name = lines[0] if lines else "Unknown Vendor"
    # Remove trailing address parts (split at first digit)
    vendor_name = re.split(r"\d", vendor_name)[0].strip()

    # --- Invoice Number ---
    invoice_number = "Unknown Invoice"
    inv_patterns = [
        r"Invoice Number[:\s\-]*([\w\d]+)",
        r"INVOICE[#]*\s*[:\-]\s*(\d+)"
    ]
    for pat in inv_patterns:
        inv_match = re.search(pat, cleaned_text, re.IGNORECASE)
        if inv_match:
            invoice_number = inv_match.group(1)
            break
    if invoice_number == "Unknown Invoice":
        # Fallback: look for a line with a date and pick a nearby number.
        for line in cleaned_text.splitlines():
            if re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", line):
                numbers = re.findall(r"\d+", line)
                if len(numbers) >= 2:
                    invoice_number = numbers[1]
                elif numbers:
                    invoice_number = numbers[0]
                break

    # --- Invoice Date ---
    raw_date = ""
    date_match = re.search(r"Invoice Date[:\s\-]*([\d/]+)", cleaned_text, re.IGNORECASE)
    if date_match:
        raw_date = date_match.group(1).strip()
    else:
        date_match = re.search(r"(Due Date|DELIVERY)[:\s\-]*([\d/]+)", cleaned_text, re.IGNORECASE)
        if date_match:
            raw_date = date_match.group(2).strip()
        else:
            date_match = re.search(r"(\d{1,2}/\d{1,2}/\d{2,4})", cleaned_text)
            raw_date = date_match.group(1).strip() if date_match else datetime.datetime.today().strftime("%m/%d/%Y")
    invoice_date = parse_date(raw_date)

    # --- Amount ---
    amount = "0.00"
    # First, try to capture the final total from a "TOTAL DUE" line.
    total_due_match = re.search(r"TOTAL DUE[:\s]*\$?\s*([\d,]+\.\d{2})", cleaned_text, re.IGNORECASE)
    if total_due_match:
        amount = total_due_match.group(1).replace(',', '').strip()
    else:
        # Try common patterns: NET INVOICE, INVOICE TOTAL, Total Sale.
        patterns_amount = [
            r"NET\s+INVOICE[:\s\-]*\$?([\d,]+\.\d{2})",
            r"INVOICE TOTAL[:\s\-]*\$?([\d,]+\.\d{2})",
            r"Total Sale[:\s\-]*\$?([\d,]+\.\d{2})"
        ]
        for pattern in patterns_amount:
            amt_match = re.search(pattern, cleaned_text, re.IGNORECASE | re.MULTILINE)
            if amt_match:
                amount = amt_match.group(1).replace(',', '').strip()
                break
        # Fallback: try to sum up known subtotals if available.
        if amount == "0.00":
            subtotals = re.findall(r"(?:DISHWASHER SUB TOTAL|OTHER SUB TOTAL)[:\s]*\$?([\d,]+\.\d{2})", cleaned_text, re.IGNORECASE)
            if subtotals:
                try:
                    total = sum(float(val.replace(',', '')) for val in subtotals)
                    amount = f"{total:.2f}"
                except Exception:
                    amount = "0.00"
        # Final fallback: scan for any line with "total" and pick the last monetary value.
        if amount == "0.00":
            for line in cleaned_text.splitlines():
                if "total" in line.lower():
                    tokens = re.findall(r"([\d,]+\.\d{2})", line)
                    if tokens:
                        amount = tokens[-1].replace(',', '').strip()
                        break

    return {
        "vendor_name": vendor_name,
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "amount": amount,
    }

def extract_invoice_data_hybrid(file_obj):
    """Extract text from the file and then extract invoice fields using universal logic."""
    text = extract_text(file_obj)
    print("Extracted Text:\n", text)
    fields = extract_invoice_fields_universal(text)
    print("Parsed Invoice Fields:", fields)
    return fields
