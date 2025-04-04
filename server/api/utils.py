import re
import datetime

def try_patterns(patterns, text, group=1, default_value=""):
    """
    Try each regex pattern on the given text.
    Return the first non-empty match from the specified group, or default_value if none match.
    """
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            try:
                value = match.group(group).strip()
            except IndexError:
                continue
            if value:
                return value
    return default_value

def extract_vendor_name(lines, text):
    """
    Determine vendor name using several strategies:
      1. If the text contains "Make check payable to:" then return the following text.
      2. If the first line is "INVOICE" (ignoring case) and there are at least 3 lines, combine the second and third lines (after cleaning).
      3. Otherwise, return the first non-empty line that doesn't include unwanted keywords.
    """
    vendor_payable = re.search(r"Make check payable to:\s*(.+)", text, re.IGNORECASE)
    if vendor_payable:
        vendor_candidate = vendor_payable.group(1).strip()
        if vendor_candidate:
            return vendor_candidate

    if lines:
        first_line = lines[0].strip()
        if first_line.lower() == "invoice" and len(lines) >= 3:
            line1 = re.sub(r'\S+@\S+', '', lines[1]).strip()  # remove email addresses
            line2 = lines[2].strip()
            line2 = re.sub(r'\s*m$', '', line2, flags=re.IGNORECASE).strip()  # clean trailing characters
            return f"{line1} {line2}".strip()
        else:
            unwanted = {"invoice", "billing", "account", "customer", "service", "phone", "united", "page:"}
            for line in lines:
                clean = line.strip()
                if clean and not any(kw in clean.lower() for kw in unwanted):
                    # Remove any "Page:" information if present
                    if "page:" in clean.lower():
                        clean = clean.split("page:")[0].strip()
                    return clean
    return "Unknown Vendor"

def parse_invoice(file_obj):
    """
    Extract invoice details from a PDF or image file.
    Returns a dictionary with basic fields:
      - vendor_name, invoice_number, invoice_date, amount
    And additional vendor fields:
      - address_line1, address_line2, city, state, zip_code,
        account_number, contact_email, contact_phone, bank_account_number,
        routing_number, bank_name, payee_name.
    """
    text = ""
    content_type = file_obj.content_type
    if content_type == "application/pdf":
        try:
            import pdfplumber
            with pdfplumber.open(file_obj) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            print("Error reading PDF with pdfplumber:", e)
            return {}
        if not text.strip():
            try:
                from pdf2image import convert_from_bytes
                from PIL import Image
                import pytesseract
                file_obj.seek(0)
                # Specify the poppler_path on Windows if needed:
                images = convert_from_bytes(file_obj.read(), poppler_path=r"C:\poppler-xx\Library\bin")
                for image in images:
                    text += pytesseract.image_to_string(image) + "\n"
            except Exception as e:
                print("Error during OCR with pdf2image:", e)
                return {}
    elif content_type in ["image/jpeg", "image/png"]:
        try:
            from PIL import Image
            import pytesseract
            image = Image.open(file_obj)
            text = pytesseract.image_to_string(image)
        except Exception as e:
            print("Error during OCR processing:", e)
            return {}
    else:
        print("Unsupported file type:", content_type)
        return {}

    print("Extracted Text:", text)
    lines = text.splitlines()

    # Basic Fields
    vendor_name = extract_vendor_name(lines, text)
    invoice_number = try_patterns([
        r"Invoice\s*no\.?:\s*([A-Z0-9]+)",
        r"INVOICE\s*NUMBER.*\n\s*([A-Z0-9]+)",
        r"Invoice\s*#[:\s\-]*([A-Z0-9]+)",
        r"Invoice[:\s]*([A-Z0-9X]+)"
    ], text, default_value="Unknown Invoice")
    raw_date = try_patterns([
        r"Issue\s*Date[:\s]*([A-Za-z]{3}\s*\d{1,2},\s*\d{4})",  # e.g., "Mar 08, 2025"
        r"Invoice\s*date[:\s\-]*([\d]{1,2}/[\d]{1,2}/[\d]{4})",
        r"INVOICE\s*DATE[:\s\-]*([\d]{1,2}/[\d]{1,2}/[\d]{4})",
        r"Date[:\s\-]*([\d]{1,2}/[\d]{1,2}/[\d]{4})",
    ], text, default_value="01/01/1970")
    invoice_date = "1970-01-01"
    for fmt in ("%b %d, %Y", "%m/%d/%Y"):
        try:
            date_obj = datetime.datetime.strptime(raw_date, fmt)
            invoice_date = date_obj.strftime("%Y-%m-%d")
            break
        except Exception:
            continue
    amount = try_patterns([
        r"(?:Total\s+DUE|Total\s+SALE)[:\s\-]*\$?([\d,]+\.\d{2})",
    ], text, default_value="0.00").replace(',', '')

    # Additional Fields
    address_line1 = try_patterns([
        r"^(.*\d+\s+[A-Za-z ]+)",  # A simple pattern to capture a street address from the start
    ], text)
    address_line2 = try_patterns([
        r"\n([A-Za-z ,]+(?=\n))",
    ], text)
    city = try_patterns([
        r",\s*([A-Za-z ]+)\s+\d{5}",
    ], text)
    state = try_patterns([
        r"\s([A-Z]{2})\s+\d{5}",
    ], text)
    zip_code = try_patterns([
        r"(\d{5}(?:-\d{4})?)",
    ], text)
    account_number = try_patterns([
        r"Account\s*Number[:\s\-]*([\w-]+)",
    ], text)
    contact_email = try_patterns([
        r"([\w\.-]+@[\w\.-]+\.\w+)",
    ], text)
    contact_phone = try_patterns([
        r"((?:\(\d{3}\)\s*\d{3}[-\s]?\d{4}))",
        r"((?:\d{3}[-\s]?\d{3}[-\s]?\d{4}))"
    ], text)
    bank_account_number = try_patterns([
        r"Bank\s+Account\s*Number[:\s\-]*([\w\d]+)",
    ], text)
    routing_number = try_patterns([
        r"Routing\s*Number[:\s\-]*([\w\d]+)",
    ], text)
    bank_name = try_patterns([
        r"Bank\s+Name[:\s\-]*([\w\s]+)",
    ], text)
    payee_name = try_patterns([
        r"Payee[:\s\-]*([\w\s]+)",
    ], text)

    return {
        "vendor_name": vendor_name,
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "amount": amount,
        "address_line1": address_line1,
        "address_line2": address_line2,
        "city": city,
        "state": state,
        "zip_code": zip_code,
        "account_number": account_number,
        "contact_email": contact_email,
        "contact_phone": contact_phone,
        "bank_account_number": bank_account_number,
        "routing_number": routing_number,
        "bank_name": bank_name,
        "payee_name": payee_name,
    }
