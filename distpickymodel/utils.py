import re
from datetime import datetime, timedelta

ip_address_regex = re.compile(r'^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}'
                              r'([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$')

url_regex = re.compile(
    r'^(?:http)s?://'  # http:// or https://
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
    r'localhost|'  # localhost...
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|'  # ...or ipv4
    r'\[?[A-F0-9]*:[A-F0-9:]+\]?)'  # ...or ipv6
    r'(?::\d+)?'  # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE)

version_regex = re.compile(r'^[1-9]{1}\d{0,1}\.((?!0)\d{2}|\d{1})$')


def sec_to_datetime(day_seconds):
    ''' Get a datetime object given the relative seconds of the day.
    '''

    now = datetime.utcnow()
    return now.replace(hour=23, minute=59, second=59, microsecond=0) - timedelta(days=1) + timedelta(
        seconds=day_seconds)


def dt_to_day_seconds(datetime_obj):
    '''Given a datetime, it returns the relative number of seconds within the day that such time represents
    '''
    return datetime_obj.hour * 3600 + datetime_obj.minute * 60 + datetime_obj.second + 1


def dt_to_dt_midnight(datetime_obj):
    '''Given a datetime_obj, it returns the same day but with time 23:59:59:00
    '''
    return datetime_obj.replace(hour=23, minute=59, second=59, microsecond=0)


def dt_to_time_string(datetime_obj):
    '''Given a datetime_obj, it return a string representation of its time part separated by semicolon
    '''
    return f"{datetime_obj.hour}:{datetime_obj.minute}:{datetime_obj.second}"


def string_to_seconds(time_string):
    '''Give a relative time in a string format separated by semicolon, return its conversion into relative day seconds
    '''
    tokens = time_string.split(':')
    return int(tokens[0]) * 3600 + int(tokens[1]) * 60 + int(tokens[2]) + 1
