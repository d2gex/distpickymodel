import re
import mongoengine
import pytest

from datetime import datetime
from distpickymodel import models, extended_model as e_model
from tests import conftest as cfg_test
from tests import utils


@pytest.fixture(scope='module', autouse=True)
def tear_up_down_db():
    try:
        utils.init_db_with_site_peers()
        utils.init_db_with_escan_instructions_and_settings()
        yield
    finally:
        cfg_test.db.drop_database(cfg_test.DATABASE)


@pytest.mark.first  # Necessary because of the second decorator makes 'pytest' run this test last and need to run first
@utils.truncate_collections([e_model.ServerInstructions], tear='both')
def test_instructions_db_operations():
    ''' Create, Insert and update instruction instances as follows:

    1) Ensure all required fields are met
    2) Ensure operations field is given the right choices
    '''

    # Ensure Scans and Peers have been created
    sites = list(models.Sites.objects.all())
    instructions = e_model.ServerInstructions()
    req_fields = [key for key, value in instructions._fields.items() if value.required]

    # (1.1) #  Check the required fields are actually required
    assert len(req_fields) == 2
    with pytest.raises(mongoengine.errors.ValidationError) as ex:
        instructions.save()
    for field in req_fields:
        assert re.search(r'\b{}\b'.format(field), str(ex.value))

    # (1.2) 'site' should be required
    instructions.site = sites[0]
    with pytest.raises(mongoengine.errors.ValidationError) as ex:
        instructions.save()
    assert re.search(r'\bsite\b', str(ex.value)) is None

    # (2)
    assert not (e_model.ServerInstructions.objects().all())
    instructions.operation = e_model.RUN_OP
    instructions.stop_at = datetime.utcnow
    instructions.running = True
    instructions.save()
    ret = e_model.ServerInstructions.objects().all()
    assert len(ret) == 1
    assert ret[0].running is True


@pytest.mark.second
def test_bulk_update_operation():
    ''' Test bulk_update operations as follows:

    1) Bulk update documents successfully
    2) Individual update errors are reported while successful ones are executed
    '''

    # Ensure sever_instructions collection is empty
    assert len(e_model.ServerInstructions.objects().all()) == 0

    # Create some documents to insert on the database.
    sites = models.Sites.objects().all()

    instruction = e_model.ServerInstructions()
    instruction.operation = e_model.STOP_AND_RUN_OP
    instruction.site = sites[0]
    instruction.times = [1, 10000]
    instruction.weekdays = [0, 1]
    instruction.save()

    instruction = e_model.ServerInstructions()
    instruction.operation = e_model.RUN_OP
    instruction.site = sites[1]
    instruction.times = [4, 50]
    instruction.weekdays = [1, 2, 4]
    instruction.save()

    instruction = e_model.ServerInstructions()
    instruction.operation = e_model.STOP_OP
    instruction.site = sites[2]
    instruction.times = [21000, 70000]
    instruction.weekdays = [5, 6]
    instruction.save()

    documents = list(e_model.ServerInstructions.objects().no_dereference().all())
    assert len(documents) == 3

    # (1)
    documents[0].weekdays = [1, 2]
    documents[1].weekdays = [3, 4]
    documents[2].weekdays = [1, 6]
    ret = e_model.ServerInstructions.bulk_update(documents)
    assert not ret
    documents = list(e_model.ServerInstructions.objects().no_dereference().all())
    assert documents[0].weekdays == [1, 2]
    assert documents[1].weekdays == [3, 4]
    assert documents[2].weekdays == [1, 6]

    # (2)  --> document[3] isn't updated so its '.updates' property will return an empty dictionary that pymongo does
    # not accept, triggering an error
    documents[0].weekdays = [0, 1]
    documents[1].weekdays = [1, 2]
    ret = e_model.ServerInstructions.bulk_update(documents)
    assert len(ret) == 1
    assert re.search(r"\B{}\B".format(re.escape("'$set' is empty.")), ret[0]['errmsg'])

    # --> First two documents though were updated properly while third remains the same
    documents = list(e_model.ServerInstructions.objects().no_dereference().all())
    assert documents[0].weekdays == [0, 1]
    assert documents[1].weekdays == [1, 2]
    assert documents[2].weekdays == [1, 6]


def test_extended_scan():
    ''' Check that the new required field Instruction for ExtendedScan is as such
    '''

    e_scan = e_model.ExtendedScans()
    with pytest.raises(mongoengine.errors.ValidationError) as ex:
        e_scan.save()
    assert re.search(r"\brun_instruction\b", str(ex.value))






