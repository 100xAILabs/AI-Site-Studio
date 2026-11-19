"""
Logging redaction filter for PII and credential protection (F-28).
Redacts email addresses, license keys, bearer tokens, and OTP codes
from all log records before they are output or forwarded.
"""

import re
import logging

# Regex patterns for sensitive data
EMAIL_REGEX = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')
BEARER_REGEX = re.compile(r'Bearer\s+[A-Za-z0-9_\-\.]{20,}', re.IGNORECASE)
JWT_REGEX = re.compile(r'\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b')
LICENSE_KEY_REGEX = re.compile(r'\b(AS-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4})\b')
OTP_IN_CONTEXT_REGEX = re.compile(r'(?:otp|code|pin)[:= ]+\b\d{4,8}\b', re.IGNORECASE)


class PIIRedactionFilter(logging.Filter):
    """Logging filter that scrubs personal data and credentials from log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            msg = record.msg
            if "@" in msg:
                msg = EMAIL_REGEX.sub("[REDACTED_EMAIL]", msg)
            if "Bearer" in msg or "bearer" in msg:
                msg = BEARER_REGEX.sub("Bearer [REDACTED_TOKEN]", msg)
            if "eyJ" in msg:
                msg = JWT_REGEX.sub("[REDACTED_JWT]", msg)
            if "AS-" in msg:
                msg = LICENSE_KEY_REGEX.sub("[REDACTED_KEY]", msg)
            if any(term in msg.lower() for term in ("otp", "verification code", "pin")):
                msg = OTP_IN_CONTEXT_REGEX.sub("code: [REDACTED_OTP]", msg)
            record.msg = msg

        # Also sanitize string arguments if present
        if record.args:
            if isinstance(record.args, dict):
                clean_args = {}
                for k, v in record.args.items():
                    if isinstance(v, str):
                        v_clean = EMAIL_REGEX.sub("[REDACTED_EMAIL]", v)
                        clean_args[k] = v_clean
                    else:
                        clean_args[k] = v
                record.args = clean_args
            elif isinstance(record.args, tuple):
                clean_args = []
                for v in record.args:
                    if isinstance(v, str):
                        clean_args.append(EMAIL_REGEX.sub("[REDACTED_EMAIL]", v))
                    else:
                        clean_args.append(v)
                record.args = tuple(clean_args)

        return True
