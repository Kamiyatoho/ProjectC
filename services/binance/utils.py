from datetime import datetime


def to_timestamp(dt: datetime) -> int:
    """
    Convert a datetime instance to milliseconds since epoch.

    :param dt: datetime object (naive or timezone-aware).
    :return: Milliseconds since Unix epoch as int.
    """
    return int(dt.timestamp() * 1000)


def from_timestamp(ms: int) -> datetime:
    """
    Convert milliseconds since epoch to a datetime instance.

    :param ms: Milliseconds since Unix epoch.
    :return: datetime object.
    """
    return datetime.fromtimestamp(ms / 1000)