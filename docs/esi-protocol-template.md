# ESI Protocol Template (Excerpt)

**Scope & Custodians:** [list]
**Data Sources:** M365 mail/SharePoint/OneDrive, endpoints, mobile, IM, line-of-business apps.
**Date Range:** [from/to]
**Search & Culling:** keywords, field constraints, date filters; TAR if applicable.
**Processing Standards:** deNIST, dedupe strategy (global/custodian/family), hash algorithm, timezone.
**Metadata Fields (minimum):** BegDoc, EndDoc, BegAttach, EndAttach, Custodian, Source, FilePath, FileName, MD5/SHA256, DateSent/DateReceived/DateCreated/DateModified, From/To/CC/BCC, Subject, FileExt, MessageID, ThreadID, Confidentiality flags.
**Production Specs:** TIFF/PDF, color handling, natives for spreadsheets/multimedia, redaction burn-in, placeholder policy.
**Load Files:** DAT (delims), OPT image cross-ref, extracted text path, image path conventions.
**Privilege & Redaction:** rules, coding instructions, logging requirements.
**Quality Control:** sampling plan, exception handling, error correction loop.
**Security:** encryption at rest/in transit; access controls; delivery via SFTP/Aspera.
