# Metadata & Load Files (Relativity‑style DAT/OPT)

**Common DAT delimiters** (example):

- Field delimiter: ASCII 20 (þ) or pipe `|`
- Quote: ASCII 254 (þ) or double‑quote `"`
- Newline: CRLF

**Minimum Fields** (illustrative):
BegDoc, EndDoc, BegAttach, EndAttach, Custodian, Source, FilePath, FileName, FileExt, MD5/SHA256,
DateCreated, DateModified, DateSent, DateReceived, From, To, CC, BCC, Subject, MessageID, ThreadID,
AttachCount, HasRedactions, Confidentiality, TextPath, NativePath, ImagePath

**OPT Image Cross-Reference:**

- Columns usually: ImageKey, VolumeID, RelativePath, DocumentBreak (Y/N), PageCount
- Ensure paths are **relative** to production root (avoid absolute machine paths)
- Validate image counts align with Beg/End ranges; insert `D` breaks appropriately

**Quality Tips**

- Validate field counts per row; confirm delimiter consistency
- Check non-ASCII normalization (smart quotes, em dashes)
- Confirm date fields are normalized (UTC or specified zone)
- Test ingest into a sandbox workspace before delivery
