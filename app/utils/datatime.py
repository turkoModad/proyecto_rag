from datetime import datetime, timezone, timedelta


def utc_now() -> datetime:
    """Retorna datetime UTC con timezone info"""
    return datetime.now(timezone.utc)

def days_ago(days: int) -> datetime:
    """Retorna datetime de hace X días en UTC"""
    return utc_now() - timedelta(days=days)