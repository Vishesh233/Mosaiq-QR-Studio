"""Bulk Create: CSV reading, row-wise errors, the 1000-row limit, and the worker that writes files.

Run:  .venv\\Scripts\\python.exe _bulk_test.py
"""
import os
import sys
import tempfile
import time

os.environ.setdefault("PYTHONUTF8", "1")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["APPDATA"] = tempfile.mkdtemp()

problems = []


def check(label, ok, detail=""):
    if not ok:
        problems.append(f"{label} {detail}".strip())


def raises(label, text, contains):
    from utils import bulk_csv
    try:
        bulk_csv.parse_rows(text)
        check(label, False, "no error raised")
    except bulk_csv.BulkFileError as e:
        check(label + " (message)", contains.lower() in str(e).lower(), str(e))


def test_reading():
    from utils import bulk_csv, qr_payloads

    rows = bulk_csv.parse_rows("Type , Content ,FILENAME\nurl,https://example.com/a,first\n,hello,\n")
    check("header names are case/space tolerant", len(rows) == 2 and rows[0].ok and rows[0].payload == "https://example.com/a")
    check("blank type = URL / Text", rows[1].type == "URL / Text" and rows[1].payload == "hello")
    check("blank filename gets a default", rows[1].stem == "url_qr_0002", rows[1].stem)
    check("row and line numbers", (rows[0].number, rows[0].line, rows[1].number, rows[1].line) == (1, 2, 2, 3))

    for delimiter in (";", "\t"):
        rows = bulk_csv.parse_rows(f"type{delimiter}content{delimiter}filename\nurl{delimiter}https://x.example{delimiter}a\n")
        check(f"delimiter {delimiter!r}", len(rows) == 1 and rows[0].payload == "https://x.example" and rows[0].stem == "a")

    rows = bulk_csv.parse_rows('content,filename\n"a, with ""quotes"" and\nnewline",q\n\n   \n,\nnext,n\n')
    check("quoted commas/newlines, blank lines skipped", len(rows) == 2
          and rows[0].payload == 'a, with "quotes" and\nnewline' and rows[1].payload == "next", repr([r.payload for r in rows]))

    # encodings
    import tempfile as tf
    for label, raw in (("utf-8 BOM", "﻿type,content\nurl,café\n".encode("utf-8")),
                       ("plain utf-8", "type,content\nurl,café\n".encode("utf-8")),
                       ("windows-1252", "type,content\nurl,café\n".encode("cp1252"))):
        path = os.path.join(tf.mkdtemp(), "x.csv")
        open(path, "wb").write(raw)
        rows = bulk_csv.read_rows(path)
        check(f"encoding {label}", rows[0].payload == "café", repr(rows[0].payload))

    # types
    cases = {
        "UPI": ("type,upi_id,payee,amount,note\nupi,shop@okaxis,Shop,99.5,hi\n", "upi://pay"),
        "WiFi": ("type,ssid,password,security,hidden\nwifi,Net,password123,WPA,yes\n", "WIFI:T:WPA;S:Net;P:password123;H:true;;"),
        "open WiFi": ("type,ssid,security\nwifi,Cafe,none\n", "WIFI:T:nopass;S:Cafe;;"),
        "Contact": ("type,name,phone,email\ncontact,Asha Verma,+91 98765 43210,a@b.co\n", "BEGIN:VCARD"),
        "Email": ("type,to,subject,body\nemail,hi@example.com,Hello,Body\n", "mailto:hi@example.com"),
        "SMS": ("type,number,message\nsms,+919876543210,On my way\n", "SMSTO:+919876543210"),
        "raw content under a structured type": ("type,content\nupi,upi://pay?pa=raw@bank&pn=Raw\n", "upi://pay?pa=raw@bank"),
    }
    for label, (text, starts) in cases.items():
        row = bulk_csv.parse_rows(text)[0]
        check(f"type {label}", row.ok and row.payload.startswith(starts), f"{row.error or row.payload!r}")
    for alias, expected in (("URL", "URL / Text"), ("Website", "URL / Text"), ("UPI payment", "UPI Payment"),
                            ("WI-FI", "WiFi"), ("vCard", "Contact"), ("E-mail", "Email"), ("sms", "SMS")):
        row = bulk_csv.parse_rows(f"type,content\n{alias},x\n")[0]
        check(f"alias {alias}", row.type == expected, row.type)

    # row-wise errors: bad rows are reported, good rows stay usable
    rows = bulk_csv.parse_rows(
        "type,content,upi_id,payee,amount,ssid,password,to,number,name,phone,filename\n"
        "url,https://ok.example,,,,,,,,,,good\n"
        "fax,hello,,,,,,,,,,badtype\n"
        "url,,,,,,,,,,,empty\n"
        "upi,,notanupiid,Shop,abc,,,,,,,badupi\n"
        "wifi,,,,,Net,short,,,,,badwifi\n"
        "email,,,,,,,not-an-email,,,,bademail\n"
        "sms,,,,,,,,12,,,badsms\n"
        "contact,,,,,,,,,,,badcontact\n"
        "url,https://ok2.example,,,,,,,,,,good2\n")
    errors = {r.stem: r.error for r in rows}
    check("good rows have no error", errors["good"] == "" and errors["good2"] == "")
    for stem in ("badtype", "empty", "badupi", "badwifi", "bademail", "badsms", "badcontact"):
        check(f"row {stem} has an error message", errors[stem] != "", repr(errors))
    check("unknown type names the problem", "Unknown type 'fax'" in errors["badtype"], errors["badtype"])
    check("empty row says what is missing", "Nothing to encode" in errors["empty"], errors["empty"])
    check("error rows keep their line numbers", [r.line for r in rows][1] == 3)
    check("usable rows are exactly the good ones", [r.stem for r in rows if r.ok] == ["good", "good2"])

    # file names
    rows = bulk_csv.parse_rows(
        "content,filename\na,same\nb,same\nc,SAME\nd,\ne,..\\..\\evil\nf,con\ng,a:b*c?\nh,"
        + "x" * 300 + "\ni,same_2\n")
    stems = [r.stem for r in rows]
    check("duplicates get numbers", stems[:3] == ["same", "same_2", "same_3"] or len(set(s.lower() for s in stems)) == len(stems), str(stems[:4]))
    check("all names are unique (case-insensitive)", len({s.lower() for s in stems}) == len(stems), str(stems))
    check("blank name -> default", stems[3] == "url_qr_0004", stems[3])
    check("path traversal is neutralised", all("\\" not in s and "/" not in s and ".." not in s for s in stems), str(stems))
    check("device name replaced", stems[5] == "url_qr_0006", stems[5])
    check("illegal characters replaced", stems[6] == "a_b_c_", stems[6])
    check("long names are cut", len(stems[7]) <= 100)
    check("changed names are noted", any("changed" in n for n in rows[4].notes + rows[6].notes))
    check("renamed duplicates are noted", any("Same file name" in n for n in rows[1].notes))

    # file-level errors
    raises("empty file", "", "empty")
    raises("only whitespace", "  \n \n", "empty")
    raises("header only", "type,content\n", "no rows")
    raises("no header", "https://example.com,hello\nhttps://b.example,x\n", "header")
    raises("blank lines only after header", "type,content\n\n\n", "no rows")

    # the 1000-row limit
    ok_text = "content\n" + "\n".join(f"https://example.com/{i}" for i in range(bulk_csv.MAX_ROWS)) + "\n"
    check("exactly 1000 rows load", len(bulk_csv.parse_rows(ok_text)) == 1000)
    raises("1001 rows refused", ok_text + "https://example.com/extra\n", "1000")
    try:
        bulk_csv.parse_rows(ok_text + "x\n")
    except bulk_csv.BulkFileError as e:
        check("limit message tells what to do", "split" in str(e).lower(), str(e))
    check("blank lines do not count towards the limit",
          len(bulk_csv.parse_rows(ok_text.replace("\n", "\n\n"))) == 1000)

    # unreadable files
    try:
        bulk_csv.read_rows(os.path.join(tempfile.mkdtemp(), "missing.csv"))
        check("missing file reported", False)
    except bulk_csv.BulkFileError as e:
        check("missing file message", "Could not read" in str(e), str(e))
    big = os.path.join(tempfile.mkdtemp(), "big.csv")
    with open(big, "wb") as fh:
        fh.write(b"content\n" + b"x" * (bulk_csv.MAX_FILE_BYTES + 10))
    try:
        bulk_csv.read_rows(big)
        check("oversized file refused", False)
    except bulk_csv.BulkFileError as e:
        check("oversized file message", "limit" in str(e), str(e))

    # too much data for one QR
    from utils.qr_generator import QRGenerator
    rows = bulk_csv.parse_rows("content,filename\n" + "z" * 5000 + ",toolong\nfine,fine\n")
    bulk_csv.validate_size(rows, QRGenerator())
    check("oversized text flagged on its row", not rows[0].ok and "too much data" in rows[0].error, rows[0].error)
    check("other rows unaffected", rows[1].ok)

    # the sample file is clean and covers every type
    sample = bulk_csv.parse_rows(bulk_csv.SAMPLE_CSV)
    check("sample CSV has no errors", all(r.ok for r in sample), str([(r.number, r.error) for r in sample if not r.ok]))
    check("sample covers all six types", {r.type for r in sample} == set(qr_payloads.TYPE_NAMES))
    check("sample uses no real-looking data", "examplebank" in bulk_csv.SAMPLE_CSV and "@okaxis" not in bulk_csv.SAMPLE_CSV)


def decode(path):
    from PIL import Image
    from utils.qr_scanner import QRScanner
    return QRScanner.decode_image(Image.open(path).convert("RGB"), thorough=False)


def test_runner():
    from utils import bulk_csv, bulk_runner, qr_export
    from utils.qr_generator import QRGenerator
    from utils.qr_render import QRStyle

    style = QRStyle(module_shape="rounded", eye_shape="rounded", gradient="linear",
                    fg="#0E7490", fg2="#1E3A8A")

    def wait(job, seconds=120):
        end = time.time() + seconds
        while job.running and time.time() < end:
            time.sleep(0.02)

    # ---- the sample file end to end ----
    rows = bulk_csv.parse_rows(bulk_csv.SAMPLE_CSV)
    folder = os.path.join(tempfile.mkdtemp(), "out")
    job = bulk_runner.BulkJob(rows, folder, style, "PNG")
    job.start()
    wait(job)
    check("sample: finished", job.state == bulk_runner.DONE and not job.running)
    check("sample: every row saved", job.saved == len(rows) == len(os.listdir(folder)), f"{job.saved}")
    for row, path in zip(rows, job.files):
        check(f"sample: {row.type} file scans back", decode(path) == row.payload, os.path.basename(path))
    done, total, finished = job.progress()
    check("progress reports the end", (done, total, finished) == (len(rows), len(rows), True), str((done, total, finished)))

    # ---- formats ----
    for fmt in ("SVG", "PDF"):
        out = os.path.join(tempfile.mkdtemp(), fmt)
        job = bulk_runner.BulkJob(rows[:3], out, style, fmt)
        job.start()
        wait(job)
        names = sorted(os.listdir(out))
        check(f"{fmt}: files written with the right extension",
              len(names) == 3 and all(n.endswith(qr_export.EXTENSIONS[fmt]) for n in names), str(names))
        head = open(os.path.join(out, names[0]), "rb").read(8)
        check(f"{fmt}: file looks right", head.startswith(b"<svg" if fmt == "SVG" else b"%PDF-"), repr(head))

    # ---- many files, styled ----
    many = bulk_csv.parse_rows("content,filename\n" + "\n".join(f"https://example.com/item/{i},code{i}" for i in range(60)))
    out = tempfile.mkdtemp()
    job = bulk_runner.BulkJob(many, out, style, "PNG")
    job.start()
    wait(job)
    check("60 codes written", job.saved == 60 and len(os.listdir(out)) == 60, str(len(os.listdir(out))))
    bad = [os.path.basename(p) for p, r in zip(job.files, many) if decode(p) != r.payload]
    check("all 60 scan back", not bad, str(bad[:5]))
    from PIL import Image
    image = Image.open(job.files[0]).convert("RGB")
    import numpy as np
    pixels = np.asarray(image).reshape(-1, 3).astype(int)
    inked = pixels[pixels.sum(axis=1) < 300]                           # module pixels, not the white margin
    mean = inked.mean(axis=0) if len(inked) else [0, 0, 0]
    check("the chosen style/colours are used", len(inked) > 0 and mean[2] > mean[0] + 40, str(mean))   # blue-ish gradient, not black

    # ---- failed rows do not stop the others ----
    original = qr_export.export
    def flaky(path, fmt, generator, data, style_, logo=None):
        if data.endswith("/7"):
            raise OSError(13, "Access is denied")
        return original(path, fmt, generator, data, style_, logo)
    qr_export.export = flaky
    try:
        out = tempfile.mkdtemp()
        job = bulk_runner.BulkJob(many[:12], out, style, "PNG")
        job.start()
        wait(job)
    finally:
        qr_export.export = original
    check("one failure, the rest saved", job.saved == 11 and len(job.failed) == 1, f"{job.saved}, {len(job.failed)}")
    check("the failure says which row and why", job.failed and job.failed[0][0].stem == "code7"
          and "Access is denied" in job.failed[0][1], str(job.failed))

    # ---- existing files are never overwritten ----
    out = tempfile.mkdtemp()
    keep = os.path.join(out, "code0.png")
    open(keep, "wb").write(b"precious")
    job = bulk_runner.BulkJob(many[:2], out, style, "PNG")
    job.start()
    wait(job)
    check("existing file untouched", open(keep, "rb").read() == b"precious")
    check("clash gets a numbered name", os.path.exists(os.path.join(out, "code0 (2).png")), str(os.listdir(out)))

    # ---- cancel ----
    big_rows = bulk_csv.parse_rows("content,filename\n" + "\n".join(
        f"https://example.com/long/path/for/a/bigger/code/{'x' * 80}/{i},c{i}" for i in range(400)))
    out = tempfile.mkdtemp()
    job = bulk_runner.BulkJob(big_rows, out, style, "PNG")
    job.start()
    first = None
    end = time.time() + 30
    while first is None and time.time() < end:
        first = job.progress()[0]
        time.sleep(0.01)
    job.cancel()
    wait(job)
    check("cancel stops the worker", not job.running and job.state == bulk_runner.CANCELLED, str(job.state))
    check("cancel stops early", 0 < job.saved < 400, str(job.saved))
    check("files on disk match what was reported", len(os.listdir(out)) == job.saved,
          f"{len(os.listdir(out))} vs {job.saved}")
    check("no half-written files", all(decode(os.path.join(out, n)) for n in os.listdir(out)[:10]))
    check("cancelled job still reports its end", job.progress()[2] in (True, False))

    # ---- impossible output folder ----
    blocker = os.path.join(tempfile.mkdtemp(), "a_file")
    open(blocker, "w").write("x")
    job = bulk_runner.BulkJob(many[:1], os.path.join(blocker, "sub"), style, "PNG")
    try:
        job.start()
        check("unusable folder reported", False)
    except OSError:
        pass

    # ---- starting twice ----
    job = bulk_runner.BulkJob(many[:1], tempfile.mkdtemp(), style, "PNG")
    job.start()
    try:
        job.start()
        check("second start refused", False)
    except RuntimeError:
        pass
    wait(job)

    # ---- rows with errors are never written ----
    mixed = bulk_csv.parse_rows("type,content,filename\nurl,ok,fine\nfax,bad,broken\n")
    out = tempfile.mkdtemp()
    job = bulk_runner.BulkJob(mixed, out, style, "PNG")
    job.start()
    wait(job)
    check("only valid rows are written", os.listdir(out) == ["fine.png"], str(os.listdir(out)))
    check("job total counts valid rows only", job.total == 1)


def main():
    test_reading()
    test_runner()
    if problems:
        print("BULK_FAIL")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print("BULK_OK: CSV reading, row-wise errors, 1000-row limit, file names, worker, cancel, formats")


if __name__ == "__main__":
    main()
