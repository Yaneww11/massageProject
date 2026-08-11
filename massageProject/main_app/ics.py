from datetime import datetime
from zoneinfo import ZoneInfo

from massageProject.main_app.context_processors import get_cached_business_info, get_cached_homepage

RESERVATION_TIMEZONE = ZoneInfo('Europe/Sofia')
UTC = ZoneInfo('UTC')


def _escape_ics_text(value):
    # Normalize line endings: CRLF and bare CR both become LF, then escape.
    # Browsers normalize textarea submissions to CRLF, so we must handle that.
    normalized = value.replace('\r\n', '\n').replace('\r', '\n')
    return (
        normalized.replace('\\', '\\\\')
        .replace(',', '\\,')
        .replace(';', '\\;')
        .replace('\n', '\\n')
    )


def _format_ics_datetime(local_date, local_time):
    local_dt = datetime.combine(local_date, local_time, tzinfo=RESERVATION_TIMEZONE)
    return local_dt.astimezone(UTC).strftime('%Y%m%dT%H%M%SZ')


def build_reservation_ics(request, reservation):
    homepage = get_cached_homepage()
    business_info = get_cached_business_info()

    dtstart = _format_ics_datetime(reservation.date, reservation.time)
    dtend = _format_ics_datetime(reservation.date, reservation.end_time)
    dtstamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')

    summary = _escape_ics_text(f'{reservation.service.name} — {homepage.brand_name}')
    location = _escape_ics_text(business_info.address) if business_info else ''

    description_parts = [reservation.specialist.name]
    if reservation.additional_text:
        description_parts.append(reservation.additional_text)
    description = _escape_ics_text('\n'.join(description_parts))

    uid = f'reservation-{reservation.pk}@{request.get_host()}'

    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        f'PRODID:-//{_escape_ics_text(homepage.brand_name)}//Reservation Calendar//BG',
        'BEGIN:VEVENT',
        f'UID:{uid}',
        f'DTSTAMP:{dtstamp}',
        f'DTSTART:{dtstart}',
        f'DTEND:{dtend}',
        f'SUMMARY:{summary}',
        f'LOCATION:{location}',
        f'DESCRIPTION:{description}',
        'BEGIN:VALARM',
        'ACTION:DISPLAY',
        'DESCRIPTION:Reminder',
        'TRIGGER:-PT1H',
        'END:VALARM',
        'END:VEVENT',
        'END:VCALENDAR',
    ]
    return '\r\n'.join(lines) + '\r\n'
