"""Bulk Create: read a CSV into rows of QR codes, with row-wise checking (no UI).

Columns (names are case-insensitive; order does not matter; extra columns are ignored):

    type       optional. URL / Text (default), UPI, WiFi, Contact, Email or SMS
    content    the exact text to encode (any type, when its own columns are empty)
    filename   optional. File name without extension; blank = e.g. upi_qr_0003
    url        for type URL / Text, same as content
    upi_id, payee, amount, note                    type UPI
    ssid, password, security, hidden               type WiFi
    name, phone, email, organisation               type Contact
    to, subject, body                              type Email
    number, message                                type SMS

A file with more than MAX_ROWS data rows is refused as a whole (with a clear message) instead
of silently loading part of it. Every row is checked on its own: a bad row gets its error text,
the others stay usable.
"""
import csv
import io
import os
from dataclasses import dataclass, field

from utils import filenames, qr_payloads

MAX_ROWS = 1000
MAX_FILE_BYTES = 5 * 1024 * 1024

TYPE_ALIASES = {
    "": "URL / Text", "url": "URL / Text", "text": "URL / Text", "link": "URL / Text",
    "url / text": "URL / Text", "url/text": "URL / Text", "website": "URL / Text",
    "upi": "UPI Payment", "upi payment": "UPI Payment",
    "wifi": "WiFi", "wi-fi": "WiFi",
    "contact": "Contact", "vcard": "Contact",
    "email": "Email", "e-mail": "Email", "mail": "Email",
    "sms": "SMS",
}


class BulkFileError(Exception):
    """The file as a whole cannot be used (the message is for the user)."""


@dataclass
class Row:
    number: int                    # 1-based position among the data rows
    line: int                      # line in the file (header = 1)
    type: str = "URL / Text"
    payload: str = ""
    stem: str = ""                 # file name without extension
    error: str = ""
    notes: list = field(default_factory=list)

    @property
    def ok(self):
        return not self.error


SAMPLE_CSV = (
    "type,filename,content,upi_id,payee,amount,note,ssid,password,security,hidden,name,phone,email,"
    "organisation,to,subject,body,number,message\n"
    "URL / Text,website,https://example.com/menu,,,,,,,,,,,,,,,,,\n"
    "UPI,cafe_payment,,sample@examplebank,Mosaiq Cafe,249.00,Order 1024,,,,,,,,,,,,,\n"
    "WiFi,guest_wifi,,,,,,Mosaiq Guest,sample-pass-123,WPA,no,,,,,,,,,\n"
    "Contact,asha_contact,,,,,,,,,,Asha Verma,+91 98765 43210,asha@example.com,Mosaiq,,,,,\n"
    "Email,hello_email,,,,,,,,,,,,,,hello@example.com,Hello,Nice to meet you,,\n"
    "SMS,call_me,,,,,,,,,,,,,,,,,+919876543210,Please call me\n"
    ",plain_text,Just some text,,,,,,,,,,,,,,,,,\n"
)


# ------------------------------------------------------------------ reading

def _decode(raw):
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise BulkFileError("This file is not text in a known encoding. Save it as CSV (UTF-8).")


def _dialect(text):
    first = text.splitlines()[0] if text.strip() else ""
    counts = {d: first.count(d) for d in (",", ";", "\t")}
    best = max(counts, key=counts.get)
    return best if counts[best] else ","


def read_rows(path):
    """The rows of a CSV file. Raises BulkFileError for a file that cannot be used."""
    try:
        size = os.path.getsize(path)
        if size > MAX_FILE_BYTES:
            raise BulkFileError(f"This file is {size // 1024 // 1024} MB; the limit is 5 MB.")
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as e:
        raise BulkFileError(f"Could not read the file: {e.strerror or e}") from e
    return parse_rows(_decode(raw))


def parse_rows(text):
    """Rows from CSV text (see read_rows)."""
    if not text.strip():
        raise BulkFileError("The file is empty.")
    delimiter = _dialect(text)
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
    try:
        header = next(reader)
    except StopIteration:
        raise BulkFileError("The file is empty.") from None
    names = [h.strip().lower() for h in header]
    known = {"type", "content", "filename", "url"} | {
        key for form in _FIELDS.values() for key in form}
    if not known & set(names):
        raise BulkFileError(
            "The first line must be a header with column names such as type, content and "
            "filename. Use Download sample CSV to see the format.")

    data_rows = []
    for line, cells in enumerate(reader, start=2):
        if not any(cell.strip() for cell in cells):
            continue                                     # blank line
        data_rows.append((line, cells))
        if len(data_rows) > MAX_ROWS:
            raise BulkFileError(
                f"This file has more than {MAX_ROWS} rows. Bulk Create handles up to {MAX_ROWS} at a "
                f"time; split the file and run it in parts.")
    if not data_rows:
        raise BulkFileError("The file has a header but no rows.")

    rows = []
    for number, (line, cells) in enumerate(data_rows, start=1):
        values = {name: (cells[i].strip() if i < len(cells) else "") for i, name in enumerate(names) if name}
        rows.append(_build_row(number, line, values))
    _unique_names(rows)
    return rows


# ------------------------------------------------------------------ one row

_FIELDS = {
    "URL / Text": ("url",),
    "UPI Payment": ("upi_id", "payee", "amount", "note"),
    "WiFi": ("ssid", "password", "security", "hidden"),
    "Contact": ("name", "phone", "email", "organisation"),
    "Email": ("to", "subject", "body"),
    "SMS": ("number", "message"),
}


def _truthy(text):
    return text.strip().lower() in ("1", "true", "yes", "y", "hidden")


def _payload(type_name, values):
    """The text to encode for a row; raises ValueError (message for the user)."""
    own = {key: values.get(key, "") for key in _FIELDS[type_name]}
    content = values.get("content", "")
    if not any(own.values()):
        if not content:
            raise ValueError("Nothing to encode: fill content or the columns of this type.")
        return content
    if type_name == "URL / Text":
        return own["url"] or content
    if type_name == "UPI Payment":
        return qr_payloads.build_upi(own["upi_id"], own["payee"], own["amount"], own["note"])
    if type_name == "WiFi":
        security = own["security"].upper() or "WPA"
        if security.lower() == "none":
            security = "None"
        return qr_payloads.build_wifi(own["ssid"], own["password"], security, _truthy(own["hidden"]))
    if type_name == "Contact":
        return qr_payloads.build_vcard(own["name"], own["phone"], own["email"], own["organisation"])
    if type_name == "Email":
        return qr_payloads.build_email(own["to"], own["subject"], own["body"])
    return qr_payloads.build_sms(own["number"], own["message"])


def _build_row(number, line, values):
    row = Row(number=number, line=line)
    type_text = values.get("type", "").strip().lower()
    row.type = TYPE_ALIASES.get(type_text, "URL / Text")
    typed = values.get("filename", "").strip()
    row.stem = filenames.safe_stem(typed, _default_stem(number, row.type)) if typed         else _default_stem(number, row.type)
    if type_text not in TYPE_ALIASES:
        row.error = (f"Unknown type '{values.get('type', '')}'. Use URL / Text, UPI, WiFi, "
                     f"Contact, Email or SMS.")
        return row
    if typed and row.stem != typed:
        row.notes.append(f"File name changed to {row.stem}.")
    try:
        row.payload = _payload(row.type, values)
    except ValueError as e:
        row.error = str(e)
    return row


def _default_stem(number, type_name):
    return f"{filenames.default_stem(type_name)}_{number:04d}"


def _unique_names(rows):
    """Two rows must never write the same file: the later one gets _2, _3 ..."""
    seen = {}
    for row in rows:
        key = row.stem.lower()
        if key in seen:
            seen[key] += 1
            new = f"{row.stem}_{seen[key]}"
            while new.lower() in seen:
                seen[key] += 1
                new = f"{row.stem}_{seen[key]}"
            row.notes.append(f"Same file name as an earlier row; saved as {new}.")
            row.stem = new
            seen[new.lower()] = 1
        else:
            seen[key] = 1


def validate_size(rows, generator):
    """Mark rows whose text does not fit into one QR code (done separately: it makes each code)."""
    for row in rows:
        if row.ok:
            try:
                generator.matrix(row.payload)
            except ValueError as e:
                row.error = str(e)
    return rows
