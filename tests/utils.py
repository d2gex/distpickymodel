import functools
import json
import mongoengine

from pathlib import Path
from os import path
from datetime import datetime, timedelta
from distpickymodel import utils, models, extended_model as e_model

file_path = Path(__file__).resolve()
ROOT_PATH = str(file_path.parents[1])
TEST_PATH = path.join(ROOT_PATH, 'tests')
STUBS = path.join(TEST_PATH, 'mockups', 'crawler', 'stubs')

MIN_SPAN = 5
MAX_SPAN = 60
MAX_CONTENT_SIZE = 1024
MAX_LINKS = 100
URL_COVER = 'http://cover.html'

SITE_URL_1 = "https://www.site1.com"
SITE_URL_2 = "https://www.site2.com"
SITE_URL_3 = "https://www.site3.com"
SITE_URL_4 = "https://www.site4.com"

PEER_NAME_1 = json.dumps("server_non_deck_apps-2-1")
PEER_NAME_2 = json.dumps("server_non_deck_apps-2-2")
PEER_NAME_3 = json.dumps("server_non_deck_apps-3-1")


class UtilsError(Exception):
    pass


def create_instruction(operation, site_doc, stop_at=None, times=None, weekdays=None, exclude_dates=None):
    '''Given a set of options, creates an instruction and store it in the local database.
    :param operation: type of operation that the instruction will do: RUN_OP, STOP_OP or STOP_AND_RUN_OP
    :param site_doc: existing Mongo document of type Sites that this instruction will be associated with
    :param stop_at: time at which a STOP_OP instruction will run
    :param times: array of times in a day over which a RUN_OP instruction will run
    :param weekdays: array of days over which a RUN_OP instruction will run
    :param exclude_dates: array of dates over which a RUN_OP instruction will NOT run
    A STOP_AND_RUN_OP will generate two separate instructions: RUN_OP AND STOP_OP
    '''
    instruction = e_model.ServerInstructions()

    if operation not in e_model.OPERATIONS:
        raise UtilsError(f"Only the following operations are available '{e_model.OPERATIONS}'. Instead: '{operation}'")
    instruction.operation = operation

    # Check site exist
    site = models.Sites.objects(id=site_doc.id).first()
    if not site:
        raise UtilsError(f"Site instance with id '{site_doc.id}' does not exist in the database")
    instruction.site = site_doc

    if operation in (e_model.RUN_OP, e_model.STOP_AND_RUN_OP):

        # 'times' and 'weekdays' are mandatory
        if times is None or not times:
            raise UtilsError(f"Operation '{operation}' requires a non-empty 'times' parameter")
        if weekdays is None or not weekdays:
            raise UtilsError(f"Operation '{operation}' requires a non-empty 'weekdays' parameter")
        # if 'exclude_days' is present it should be non-empty
        if exclude_dates is not None and not exclude_dates:
            raise UtilsError(f"Operation '{operation}' requires a non-empty 'exclude_dates' parameter if "
                             f"this is provided")
        # Convert 'times' list to 'times in seconds' unique list
        for time in times:
            tokens = time.split(':')
            if len(tokens) != 3:
                raise UtilsError(f"time element of 'times' parameter should follow the format 'HH:ii::ss'. "
                                 f"Instead '{time}'")
            try:
                time_sec = utils.string_to_seconds(time)
            except ValueError as ex:
                raise UtilsError(f"time element '{time}' of 'times' parameter is not a string representation "
                                 f"of a valid time.Expected: [0,23]:[0,59]:[0,59]") \
                    from ex
            else:
                instruction.times.append(time_sec)
        instruction.times = sorted(list({*instruction.times}))

        # Make 'weekdays' list unique
        for day in weekdays:
            if day not in e_model.WEEK_DAYS:
                raise UtilsError(f"day element '{day}' from 'weekdays' parameter "
                                 f"is out of boundaries '{[x for x in e_model.WEEK_DAYS]}'")
            instruction.weekdays.append(day)
        instruction.weekdays = sorted(list({*instruction.weekdays}))

        # Make sure 'exclude_dates' elements have their time set to midnight and remove duplicates
        if exclude_dates:
            instruction.exclude_dates = sorted(list({utils.dt_to_dt_midnight(ex_day) for ex_day in exclude_dates}))

    if operation in (e_model.STOP_OP, e_model.STOP_AND_RUN_OP):
        if stop_at is None:
            raise UtilsError(f"Operation '{operation}' requires a 'stop_at' parameter")
        instruction.stop_at = stop_at

    # Check rules
    db_instructions = e_model.ServerInstructions.objects(site=site).all()
    if len(db_instructions) == 2:
        raise UtilsError("The following instructions: {} are already stored in the database. "
                         "Only 2 instructions can be stored simultaneously".
                         format(["'" + x.operation + "'" for x in db_instructions]))
    if len(db_instructions) == 1:
        if db_instructions[0].operation == operation:
            raise UtilsError("There is a exact same instruction already stored in the database. "
                             "2 instructions of the same operation type cannot coexist together ")

        if {db_instructions[0].operation, operation} == {e_model.STOP_AND_RUN_OP, e_model.STOP_OP}:
            raise UtilsError(f"There is already a instruction stored in the database: "
                             f"'{db_instructions[0].operation}' that is incompatible '{operation}")

    try:
        instruction.save()
    except mongoengine.errors.ValidationError as ex:
        raise UtilsError(f"A new instruction to be saved in the database failed") from ex
    else:
        return instruction.id


def truncate_collections(collections, tear='down'):
    '''On-demand Teardown necessary to delete data in certain collections given as an argument to each of the test
    functions.
    '''

    def func_as_args(func):
        @functools.wraps(func)
        def func_wrapper(*args, **kwargs):

            def delete_collections(data):
                for collection in data:
                    collection.objects().delete()

            if tear in ('up', 'both'):
                delete_collections(collections)
            func(*args, **kwargs)
            if tear in ('down', 'both'):
                delete_collections(collections)

        return func_wrapper

    return func_as_args


def init_db_with_site_peers():
    ''' Create 3 Peers and 3 Sites objects and update the database
    '''
    # Create Sites
    site = models.Sites()
    site.url = SITE_URL_1
    site.save(force_insert=True)

    site = models.Sites()
    site.url = SITE_URL_2

    site.save(force_insert=True)

    site = models.Sites()
    site.url = SITE_URL_3
    site.save(force_insert=True)

    # Create peers
    peer = models.Peers()
    peer.ip_address = "192.168.1.1"
    peer.name = PEER_NAME_1
    peer.is_allowed = True
    peer.is_assigned = True
    peer.save()

    peer = models.Peers()
    peer.ip_address = "192.168.1.2"
    peer.name = PEER_NAME_2
    peer.is_allowed = True
    peer.is_assigned = True
    peer.save()

    peer = models.Peers()
    peer.ip_address = "192.168.1.3"
    peer.name = PEER_NAME_3
    peer.is_allowed = True
    peer.is_assigned = True
    peer.save()


def init_db_with_escan_instructions_and_settings():
    '''Create 3 currently-running ServerInstructions, 3 Extended Scans and 1 ScanSettings objects so that:

    1) ExtendedScan[0] is associated with ServerInstructions[0], Peers[0], Sites[0] and ScanSettings[0]
    2) ExtendedScan[1] is associated with ServerInstructions[1], Peers[1] and Sites[1]
    3) ExtendedScan[2] is associated with ServerInstructions[2], Peers[2] and Sites[2]
    4) ExtendedScan[0] is also associated with ScanSettings[0]
    5) Case 1) corresponds to a typical case of a scan being undergoing
    '''

    sites = list(models.Sites.objects().all())
    peers = models.Peers.objects().all()

    # --> Create 3 instructions wthat are currently running
    time_10_ago = datetime.utcnow().replace(microsecond=0) - timedelta(seconds=10)
    time_20_ago = time_10_ago - timedelta(seconds=10)
    time_30_ago = time_20_ago - timedelta(seconds=10)

    time_10_ago_string = utils.dt_to_time_string(time_10_ago)
    time_20_ago_string = utils.dt_to_time_string(time_20_ago)
    time_30_ago_string = utils.dt_to_time_string(time_30_ago)

    create_instruction(e_model.RUN_OP, sites[1], times=[time_20_ago_string],
                       weekdays=[time_20_ago.weekday()])

    create_instruction(e_model.RUN_OP, sites[2], times=[time_30_ago_string],
                       weekdays=[time_30_ago.weekday()])

    create_instruction(e_model.RUN_OP, sites[0], times=[time_10_ago_string],
                       weekdays=[time_10_ago.weekday()])

    instructions = list(e_model.ServerInstructions.objects().all())
    for instruction in instructions:
        instruction.running = True
    e_model.ServerInstructions.bulk_update(instructions)

    # Create 3 Extended Scan objects and associate it to Peers, Sites and Instructions
    e_scan = e_model.ExtendedScans()
    e_scan.peer = peers[0]
    e_scan.site = sites[0]
    e_scan.run_instruction = instructions[0]
    e_scan.process_name = 'Process-x'
    e_scan.started_at = datetime.utcnow().replace(microsecond=0)
    e_scan.is_active = True
    e_scan.save()

    # Create One Scan Settings and make the first Extended Scan object be associated to it
    scan_settings = models.ScanSettings()
    scan_settings.max_links = MAX_LINKS
    scan_settings.max_size = MAX_CONTENT_SIZE
    scan_settings.site = sites[0]
    scan_settings.scans.append(e_scan)
    scan_settings.save()

    e_scan = e_model.ExtendedScans()
    e_scan.peer = peers[1]
    e_scan.site = sites[1]
    e_scan.run_instruction = instructions[1]
    e_scan.process_name = 'Process-y'
    e_scan.started_at = datetime.utcnow().replace(microsecond=0)
    e_scan.is_active = True
    e_scan.save()

    e_scan = e_model.ExtendedScans()
    e_scan.peer = peers[2]
    e_scan.site = sites[1]
    e_scan.run_instruction = instructions[2]
    e_scan.process_name = 'Process-z'
    e_scan.started_at = datetime.utcnow().replace(microsecond=0)
    e_scan.is_active = True
    e_scan.save()



