# helpers/Time.py
import isodate

def Iso8601DurationToSeconds(duration: str) -> int:
    """
    Convert ISO8601 duration (e.g. 'PT1H10M52S') to total seconds as int.
    """
    try:
        td = isodate.parse_duration(duration)
        return int(td.total_seconds())
    except Exception:
        return 0