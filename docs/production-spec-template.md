# Production Specifications (Template)

**Format:** TIFF (b/w, 300 DPI) unless color required; PDFs for certain filetypes; natives for spreadsheets/audio/video.
**Images:** Single-page TIFF/PDF; `ImagePath` in OPT
**Text:** Extracted text `.txt`; OCR where needed; `TextPath` in DAT
**Natives:** Provided for specified extensions; `NativePath` in DAT; placeholders in images folder
**Redactions:** Burned‑in; reason code tracked
**Bates:** Prefix `ABC00000001`; no duplicates; family integrity
**Load Files:** DAT (delims specified), OPT (image cross-ref)
**Delivery:** Encrypted ZIP; checksum & delivery log; SFTP or Aspera
