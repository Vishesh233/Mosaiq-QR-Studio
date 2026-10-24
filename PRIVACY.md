# Privacy Policy: Mosaiq QR Studio

_Last updated: 23 October 2026 (version 2.2)_

Mosaiq QR Studio runs entirely on your PC.

- **No data collection.** The app does not collect, store or send personal data, usage data, analytics or crash reports.
- **No network access.** The app makes no network requests. When you click a link found in a scanned QR code, that link is handed to your default web browser; nothing else is sent anywhere. Scanned UPI payment, WiFi, contact, email and SMS codes are only shown on screen: the app never starts a payment, joins a network, saves a contact or sends a message by itself.
- **Camera.** If you choose **Use Camera** on the Scan tab, the app uses your webcam to look for a QR code. The camera is on only while that view is open and is released as soon as a code is found, you press Stop, you leave the Scan tab or you close the app. Camera images are processed in memory only; they are never saved, recorded or sent anywhere.
- **Clipboard.** The app reads the clipboard only when you press **Paste** (or Ctrl+V) on the Scan tab, and only to look for an image. It writes to the clipboard only when you press a Copy button.
- **Screen.** When you choose **Screen Region**, the app takes one picture of your screen so you can select the QR code on it. That picture is used in memory only and is discarded; it is never saved or sent anywhere.
- **Your files stay local.** Images you open or drop for scanning or as a logo, the CSV files you load in Bulk Create, and the QR codes you save (PNG, SVG or PDF, one at a time or in bulk), are read and written only on your PC, in the places you choose.
- **History (local only).** The History page lists the codes you generated and scanned. It is kept in a small file (`history.json`) and a folder of small preview pictures (`history\thumbs`) next to the settings file under your Windows user profile, and nowhere else; it is never sent anywhere. It holds the text of each code (for example a link, a UPI ID or a contact card), the form values and design you used for generated codes, and the date. For scanned codes only the decoded text is kept, never the scanned picture or camera image; the small preview is a fresh drawing of that text. At most 200 codes are kept: the oldest are removed automatically, together with their previews.
  - **You are in control.** *Save history* in Settings switches it off completely (nothing is written). *Clear history* in Settings deletes the list and every preview picture.
  - **WiFi passwords are not saved by default.** A WiFi entry keeps the network name and type, but its password is left blank and no preview picture is stored for it (the picture of a WiFi code contains the password). Only if you switch on *Save WiFi passwords* in Settings are passwords and their previews saved.
  - When the app is installed from the Microsoft Store, uninstalling it removes the history together with the settings.
- **Settings.** The app saves your theme, intro-animation preference, history switches, the last colours you picked and the last Bulk Create folder, in a small settings file under your Windows user profile. When the app is installed from the Microsoft Store, uninstalling it removes that file.
- **Error log.** If a part of the app cannot start (for example the scanning component on a PC without the Windows Media Feature Pack) or a file cannot be written, a short technical note is written to a small log file (`mosaiq.log`, about 100 KB at most) next to the settings file; each theme change adds one line saying how its animation started and ended (for example "skipped (click)"). It does not contain the contents of any QR code or your files, stays on your PC and is never sent anywhere.

Questions: open an issue at https://github.com/Vishesh233/Mosaiq-QR-Studio/issues
