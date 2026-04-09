"""
Shared filename generation helper for Manual AI exports (Excel + PDF).

Canonical format:
    "AI Overview export - {project_name} - {YYYY-MM-DD} - Clicandseo.{ext}"

Used by both the Excel route (manual_ai/routes/exports.py, download_manual_ai_excel)
and the PDF route (download_manual_ai_pdf). Keeping one source of truth prevents
the two formats from drifting apart.
"""

import re
from datetime import datetime

import pytz


# Characters that are invalid in filenames on most filesystems.
# We strip them instead of replacing with an underscore so the filename
# stays visually clean ("Bad/Name" → "BadName" rather than "Bad_Name").
_INVALID_FILENAME_CHARS = re.compile(r'[\/\\:\*\?"<>\|]')


def build_manual_ai_export_filename(
    project_name: str,
    extension: str,
    tz: str = 'Europe/Madrid',
) -> str:
    """
    Build the canonical Manual AI export filename.

    Args:
        project_name: Name of the project (from manual_ai_projects.name).
                      Spaces, accents, dashes and most unicode chars are
                      preserved. Filesystem-unsafe chars are stripped.
        extension:    File extension without leading dot (e.g. 'pdf', 'xlsx').
                      A leading dot is also accepted and stripped.
        tz:           Timezone used to format the date (default Europe/Madrid).

    Returns:
        A string of the form
            "AI Overview export - {clean_name} - {YYYY-MM-DD} - Clicandseo.{ext}"
        If project_name is empty or becomes empty after sanitization, the
        literal 'Project' is used as a fallback so we never produce
        "AI Overview export -  - 2026-04-09 - Clicandseo.pdf".

    Examples:
        >>> build_manual_ai_export_filename('HM Fertility', 'pdf')
        'AI Overview export - HM Fertility - 2026-04-09 - Clicandseo.pdf'
        >>> build_manual_ai_export_filename('Láserum - PT', 'xlsx')
        'AI Overview export - Láserum - PT - 2026-04-09 - Clicandseo.xlsx'
        >>> build_manual_ai_export_filename('Bad/Name:with*chars', 'pdf')
        'AI Overview export - BadNamewithchars - 2026-04-09 - Clicandseo.pdf'
        >>> build_manual_ai_export_filename('', 'pdf')
        'AI Overview export - Project - 2026-04-09 - Clicandseo.pdf'
    """
    try:
        timezone = pytz.timezone(tz)
    except Exception:
        # Fallback to UTC if an invalid timezone string is passed.
        timezone = pytz.UTC

    date_str = datetime.now(timezone).strftime('%Y-%m-%d')

    # Sanitize project name
    raw_name = (project_name or '').strip()
    clean_name = _INVALID_FILENAME_CHARS.sub('', raw_name).strip()
    if not clean_name:
        clean_name = 'Project'

    # Normalize extension
    ext = (extension or '').lstrip('.').lower() or 'bin'

    return f'AI Overview export - {clean_name} - {date_str} - Clicandseo.{ext}'
