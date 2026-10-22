"""QR payload formats: build the text for each smart type, and recognise it again.

Pure functions, no UI. build_* raise ValueError with a message meant to be
shown to the user. parse() never raises; unknown text is returned as URL/text.
"""

import re
from dataclasses import dataclass, field
from urllib.parse import quote, unquote

NL = chr(10)
NUL = chr(0)

TYPE_NAMES = ("URL / Text", "UPI Payment", "WiFi", "Contact", "Email", "SMS")

WIFI_SECURITY = ("WPA", "WEP", "None")

_VPA_RE = re.compile(r"^[A-Za-z0-9._-]{2,256}@[A-Za-z][A-Za-z0-9.]{1,63}$")
_AMOUNT_RE = re.compile(r"^\d{1,9}(\.\d{1,2})?$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+?\d{3,15}$")


@dataclass
class ParsedQR:
    kind: str                       # url, text, upi, wifi, contact, email, sms
    title: str                      # e.g. "WiFi: MyNetwork"
    fields: list = field(default_factory=list)   # [(label, value), ...]
    raw: str = ""
    # (button label, value to copy) for the type's most useful single value
    action: tuple = None

    @property
    def readable(self):
        lines = [self.title]
        lines += [f"{label}: {value}" for label, value in self.fields]
        return "\n".join(lines)


# ==================================================
# Helpers
# ==================================================

def _enc(value):
    """Percent-encode everything (space -> %20, never '+')."""
    return quote(value, safe="")


def _query(text):
    """Parse 'a=1&b=2' with %-decoding only ('+' stays a plus)."""
    result = {}
    for part in text.split("&"):
        if not part:
            continue
        key, _, value = part.partition("=")
        result[unquote(key).lower()] = unquote(value)
    return result


def _check_email(address, label="Email address"):
    if not _EMAIL_RE.match(address):
        raise ValueError(f"{label} is not valid (example: name@example.com).")


def _clean_phone(number, label="Phone number"):
    cleaned = re.sub(r"[\s\-().]", "", number)
    if not _PHONE_RE.match(cleaned):
        raise ValueError(
            f"{label} is not valid. Use digits, with an optional leading +."
        )
    return cleaned


# ==================================================
# Build
# ==================================================

def build_upi(upi_id, name, amount="", note=""):
    upi_id, name = upi_id.strip(), name.strip()
    amount, note = amount.strip(), note.strip()

    if not upi_id:
        raise ValueError("Please enter the UPI ID.")
    if not _VPA_RE.match(upi_id):
        raise ValueError("UPI ID is not valid (example: name@bank).")
    if not name:
        raise ValueError("Please enter the payee name.")
    if amount:
        if not _AMOUNT_RE.match(amount) or float(amount) <= 0:
            raise ValueError(
                "Amount must be a positive number with at most 2 decimals."
            )

    parts = [f"pa={_enc(upi_id)}", f"pn={_enc(name)}"]
    if amount:
        parts.append(f"am={amount}")
    parts.append("cu=INR")
    if note:
        parts.append(f"tn={_enc(note)}")

    return "upi://pay?" + "&".join(parts)


def _wifi_escape(value):
    return re.sub(r'([\\;,:"])', r"\\\1", value)


def build_wifi(ssid, password="", security="WPA", hidden=False):
    if not ssid:
        raise ValueError("Please enter the network name (SSID).")
    if len(ssid.encode("utf-8")) > 32:
        raise ValueError("The network name (SSID) is at most 32 bytes.")
    if security not in WIFI_SECURITY:
        raise ValueError("Unknown security type.")

    if security == "None":
        password = ""
        auth = "nopass"
    else:
        if not password:
            raise ValueError("Please enter the WiFi password.")
        if security == "WPA" and not 8 <= len(password) <= 63:
            raise ValueError("A WPA password must be 8 to 63 characters.")
        auth = security

    text = f"WIFI:T:{auth};S:{_wifi_escape(ssid)};"
    if password:
        text += f"P:{_wifi_escape(password)};"
    if hidden:
        text += "H:true;"
    return text + ";"


def _vcard_escape(value):
    value = value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
    return value.replace("\r\n", "\\n").replace("\n", "\\n")


def build_vcard(name, phone="", email="", organisation=""):
    name, email = name.strip(), email.strip()
    organisation = organisation.strip()

    if not name:
        raise ValueError("Please enter the contact name.")
    if email:
        _check_email(email)
    if phone.strip():
        phone = _clean_phone(phone)

    first, _, last = name.rpartition(" ")
    if not first:
        first, last = "", name

    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"N:{_vcard_escape(last)};{_vcard_escape(first)};;;",
        f"FN:{_vcard_escape(name)}",
    ]
    if organisation:
        lines.append(f"ORG:{_vcard_escape(organisation)}")
    if phone.strip():
        lines.append(f"TEL;TYPE=CELL:{phone}")
    if email:
        lines.append(f"EMAIL:{_vcard_escape(email)}")
    lines.append("END:VCARD")

    return "\r\n".join(lines)


def build_email(to, subject="", body=""):
    to = to.strip()
    if not to:
        raise ValueError("Please enter the recipient's email address.")
    _check_email(to, "Recipient address")

    text = f"mailto:{to}"
    params = []
    if subject:
        params.append(f"subject={_enc(subject)}")
    if body:
        params.append(f"body={_enc(body)}")
    if params:
        text += "?" + "&".join(params)
    return text


def build_sms(number, message=""):
    if not number.strip():
        raise ValueError("Please enter the phone number.")
    return f"SMSTO:{_clean_phone(number)}:{message}"


# ==================================================
# Parse
# ==================================================

def _split_unescaped(text, sep, newline_escape=False):
    """Split on `sep`, honouring backslash escapes; unescape the pieces.

    newline_escape: treat backslash-n as a line break (vCard), not "n".
    """
    pieces, current, i = [], [], 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            current.append(NL if newline_escape and nxt in "nN" else nxt)
            i += 2
            continue
        if ch == sep:
            pieces.append("".join(current))
            current = []
        else:
            current.append(ch)
        i += 1
    pieces.append("".join(current))
    return pieces




def _parse_upi(raw):
    query = _query(raw.split("?", 1)[1]) if "?" in raw else {}
    vpa = query.get("pa", "")
    if not vpa:
        return None

    fields = [
        ("Payee", query.get("pn", "")),
        ("UPI ID", vpa),
        ("Amount", f"{query.get('cur', query.get('cu', 'INR'))} {query['am']}"
         if query.get("am") else ""),
        ("Note", query.get("tn", "")),
    ]
    payee = query.get("pn") or vpa
    return ParsedQR(
        "upi", f"UPI payment: {payee}",
        [(k, v) for k, v in fields if v], raw,
        ("Copy UPI ID", vpa),
    )


def _parse_wifi(raw):
    values = {}
    for part in _split_unescaped(raw[5:], ";"):
        key, sep, value = part.partition(":")
        if sep:
            values[key.upper()] = value

    ssid = values.get("S", "")
    if not ssid:
        return None

    security = values.get("T", "").upper()
    if security in ("", "NOPASS"):
        security_label = "None"
    else:
        security_label = security

    fields = [("Network", ssid), ("Security", security_label)]
    password = values.get("P", "")
    if password:
        fields.append(("Password", password))
    if values.get("H", "").lower() == "true":
        fields.append(("Hidden", "Yes"))

    return ParsedQR(
        "wifi", f"WiFi: {ssid}", fields, raw,
        ("Copy password", password) if password else None,
    )


def _vcard_unescape(value):
    return "".join(_split_unescaped(value, NUL, True))


def _parse_vcard(raw):
    text = re.sub(r"\r?\n[ \t]", "", raw)       # unfold continuation lines
    props = {}
    for line in re.split(r"\r?\n", text):
        name, sep, value = line.partition(":")
        if not sep:
            continue
        key = name.split(";", 1)[0].upper()
        props.setdefault(key, value)

    name = _vcard_unescape(props.get("FN", ""))
    if not name and props.get("N"):
        pieces = _split_unescaped(props["N"], ";", True) + ["", ""]
        name = f"{pieces[1]} {pieces[0]}".strip()
    if not name and not any(k in props for k in ("TEL", "EMAIL")):
        return None

    phone = _vcard_unescape(props.get("TEL", ""))
    email = _vcard_unescape(props.get("EMAIL", ""))
    fields = [
        ("Name", name),
        ("Phone", phone),
        ("Email", email),
        ("Organisation", ", ".join(
            p for p in _split_unescaped(props.get("ORG", ""), ";", True) if p)),
    ]
    fields = [(k, v) for k, v in fields if v]
    return ParsedQR(
        "contact", f"Contact: {name or email or phone}",
        fields, raw,
        ("Copy phone", phone) if phone else None,
    )


def _parse_mailto(raw):
    body = raw[7:]
    to, _, query_text = body.partition("?")
    to = unquote(to)
    if not to:
        return None
    query = _query(query_text)
    fields = [("To", to), ("Subject", query.get("subject", "")),
              ("Message", query.get("body", ""))]
    return ParsedQR(
        "email", f"Email: {to}", [(k, v) for k, v in fields if v], raw,
        ("Copy address", to),
    )


def _parse_sms(raw):
    body = raw.split(":", 1)[1]
    if raw[:6].lower() == "smsto:":
        number, _, message = body.partition(":")
    else:
        number, _, query_text = body.partition("?")
        message = _query(query_text).get("body", "")
    number = unquote(number)
    if not number:
        return None
    fields = [("To", number), ("Message", message)]
    return ParsedQR(
        "sms", f"SMS: {number}", [(k, v) for k, v in fields if v], raw,
        ("Copy number", number),
    )


def parse(text):
    """Recognise a scanned payload. Never raises; falls back to URL/text."""
    stripped = text.strip()
    lowered = stripped.lower()

    parsers = (
        ("upi://pay", _parse_upi),
        ("wifi:", _parse_wifi),
        ("begin:vcard", _parse_vcard),
        ("mailto:", _parse_mailto),
        ("smsto:", _parse_sms),
        ("sms:", _parse_sms),
    )
    for prefix, parser in parsers:
        if lowered.startswith(prefix):
            parsed = parser(stripped)
            if parsed is not None:
                parsed.raw = text
                return parsed
            break

    if re.match(r"^(https?://|www\.)\S+$", stripped, re.IGNORECASE):
        return ParsedQR("url", "URL detected", [], text, ("Copy link", stripped))

    return ParsedQR("text", "Plain text", [], text)
