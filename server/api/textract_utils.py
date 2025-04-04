import boto3
import io
import datetime
import json
from pdf2image import convert_from_bytes

def analyze_document(file_bytes):
    """
    Call AWS Textract to analyze the document.
    If Textract returns an UnsupportedDocumentException (often with scanned PDFs),
    fallback to converting the PDF to a PNG using pdf2image and re-call Textract.
    Saves the Textract response to a file for inspection.
    """
    textract = boto3.client('textract', region_name='us-east-1')  # Use correct region (e.g., "us-east-1")
    try:
        response = textract.analyze_document(
            Document={'Bytes': file_bytes},
            FeatureTypes=['FORMS', 'TABLES']
        )
        # Save the response for inspection
        with open("textract_response.json", "w", encoding="utf-8") as f:
            json.dump(response, f, indent=2)
        return response
    except textract.exceptions.UnsupportedDocumentException as ude:
        print("Textract unsupported document format. Falling back to image conversion.", ude)
        try:
            images = convert_from_bytes(file_bytes, poppler_path=r"C:\poppler-24.08.0\Library\bin")
            if images:
                from io import BytesIO
                img_byte_arr = BytesIO()
                images[0].save(img_byte_arr, format='PNG')
                png_bytes = img_byte_arr.getvalue()
                response = textract.analyze_document(
                    Document={'Bytes': png_bytes},
                    FeatureTypes=['FORMS', 'TABLES']
                )
                with open("textract_response_fallback.json", "w", encoding="utf-8") as f:
                    json.dump(response, f, indent=2)
                return response
            else:
                raise Exception("No images generated from PDF.")
        except Exception as e:
            print("Fallback conversion error:", e)
            raise e
    except Exception as e:
        raise e

def parse_textract_response(response):
    """
    Parse Textract's JSON response to extract key-value pairs.
    Returns a dictionary mapping keys (lowercase) to their corresponding values.
    """
    blocks = response.get("Blocks", [])
    kvs = {}
    blocks_dict = {block['Id']: block for block in blocks}
    for block in blocks:
        if block.get("BlockType") == "KEY_VALUE_SET" and "KEY" in block.get("EntityTypes", []):
            key = ""
            value = ""
            if "Relationships" in block:
                for rel in block["Relationships"]:
                    if rel["Type"] == "CHILD":
                        for child_id in rel["Ids"]:
                            child = blocks_dict.get(child_id, {})
                            if child.get("BlockType") == "WORD":
                                key += child.get("Text", "") + " "
            key = key.strip().lower()
            if "Relationships" in block:
                for rel in block["Relationships"]:
                    if rel["Type"] == "VALUE":
                        for value_id in rel["Ids"]:
                            value_block = blocks_dict.get(value_id, {})
                            if value_block.get("BlockType") == "WORD":
                                value += value_block.get("Text", "") + " "
            kvs[key] = value.strip()
    return kvs

def extract_invoice_data_textract(file_bytes):
    """
    Use AWS Textract (with fallback to image conversion) to extract invoice fields.
    Returns a dictionary of extracted fields.
    """
    response = analyze_document(file_bytes)
    kvs = parse_textract_response(response)
    
    # Map Textract keys to desired fields.
    # **IMPORTANT:** Adjust the keys below based on your Textract JSON.
    data = {
        "vendor_name": kvs.get("vendor", "Unknown Vendor"),
        "invoice_number": kvs.get("invoice", "Unknown Invoice"),
        "invoice_date": kvs.get("invoice date", "01/01/1970"),
        "amount": kvs.get("total due", "0.00"),
        "address_line1": kvs.get("address line 1", ""),
        "address_line2": kvs.get("address line 2", ""),
        "city": kvs.get("city", ""),
        "state": kvs.get("state", ""),
        "zip_code": kvs.get("zip", ""),
        "account_number": kvs.get("account number", ""),
        "contact_email": kvs.get("email", ""),
        "contact_phone": kvs.get("phone", ""),
        "bank_account_number": kvs.get("bank account number", ""),
        "routing_number": kvs.get("routing number", ""),
        "bank_name": kvs.get("bank name", ""),
        "payee_name": kvs.get("payee", ""),
    }
    
    # Convert invoice_date to ISO format if possible.
    try:
        date_obj = datetime.datetime.strptime(data["invoice_date"], "%m/%d/%Y")
        data["invoice_date"] = date_obj.strftime("%Y-%m-%d")
    except Exception:
        data["invoice_date"] = "1970-01-01"
    
    return data
