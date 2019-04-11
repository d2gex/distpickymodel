import re
import bson
import mongoengine
import pytest
import yaml

from distpickymodel import errors
from distpickymodel import models
from unittest.mock import Mock
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


def test_string_field_subclass():
    '''Test Subclass StringField behaves as mongoengine.StringField however:

    1) 'regex' if provided must be a str objet => throw an exception
    2) 'regex' can be None as default value
    3) if regular expression in 'regex' is not met when using the validate method=> throw an exception
    4) The opposite to 3) should as well be true
    '''

    # (1)
    with pytest.raises(mongoengine.errors.ValidationError) as ex:
        models.StringField(regex=Mock())
    assert re.search(r"\B'regex' must be a string object\b", str(ex.value))

    # (2)
    try:
        models.StringField()
    except mongoengine.ValidationError as ex:
        raise AssertionError(f"StringField instantiation threw an error when it should not: {ex}")

    # (3)
    ip_address_regex = r'^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}' \
                       r'([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$'
    field = models.StringField(regex=ip_address_regex)
    with pytest.raises(mongoengine.errors.ValidationError):
        field.validate('This is not an ip address')

    # (4)
    field.validate('192.168.1.1')


def test_documents_db_operations():
    '''Create, Insert and Update new documents and its different content versions and ensure that both the Document
    and Content model respect the 'required' fields. Documents are also interlinked with each other.

    The following cases are tested:
    1) site_d, url and site_url required fields within the Document model are respected
    2) url and version fields within the Content model are required
    3) Document may have a parent and a child
    4) When attaching various children to a document, only those that are unique will remain. The rest will be
    ignored
    '''

    # Ensure Sites, Peers and Scan Settings have been created
    sites = models.Sites.objects()
    peers = models.Peers.objects()
    scan_settings = models.ScanSettings.objects()
    assert len(sites) > 0
    assert len(peers) > 0
    assert len(scan_settings) > 0

    root_document = models.WebDocuments()
    doc_req_fields = [key for key, value in root_document._fields.items() if value.required]
    assert len(doc_req_fields) == 6

    # (1.1)
    with pytest.raises(mongoengine.errors.ValidationError) as ex:
        root_document.save()
    for field in doc_req_fields:
        assert field in str(ex.value)

    # (1.2)
    scan = models.Scans(site=sites[0], peer=peers[0], id=bson.ObjectId())  # create a mock of Scans
    root_document.scan = scan
    with pytest.raises(mongoengine.errors.ValidationError) as ex:
        root_document.save()
    assert 'scan' not in str(ex.value)

    # (1.3)
    root_document.site = sites[0]
    with pytest.raises(mongoengine.errors.ValidationError) as ex:
        root_document.save()
    assert re.search(r'\bsite\b', str(ex.value)) is None

    # (1.4)
    root_document.site_url = sites[0].url
    with pytest.raises(mongoengine.errors.ValidationError) as ex:
        root_document.save()
    assert re.search(r'\bsite_url\b', str(ex.value)) is None

    root_document.url = sites[0].url
    root_document.is_cover = True

    # (1.5)
    with pytest.raises(mongoengine.errors.ValidationError) as ex:
        root_document.save()
    assert re.search(r'\burl\b', str(ex.value)) is None

    # (1.6)
    root_document.level = 1
    with pytest.raises(mongoengine.errors.ValidationError) as ex:
        root_document.save()
    assert re.search(r'\blevel\b', str(ex.value)) is None

    # (1.7)
    root_document.num_node = 1
    root_document.save()

    # (2)
    content = models.WebContent()
    root_document.content.append(content)
    content_req_fields = [key for key, value in content._fields.items() if value.required]
    assert len(content_req_fields) == 2

    # (2.1)
    with pytest.raises(mongoengine.errors.ValidationError) as ex:
        root_document.save()
    for field in content_req_fields:
        assert field in str(ex.value)

    # (2.2)
    content.url = root_document.url
    with pytest.raises(mongoengine.errors.ValidationError) as ex:
        root_document.save()
    assert re.search(r'\burl\b', str(ex.value)) is None

    content.version = "1.0"
    root_document.save()

    # 3.1 Parent Relationship
    child_document = models.WebDocuments()
    child_document.site = sites[0]
    child_document.scan = scan
    child_document.site_url = sites[0].url
    child_document.url = child_document.site_url + "/" + "child.html"
    child_document.level = 2
    child_document.num_node = 2
    child_document.parent = root_document
    child_document.is_cover = False
    child_document.save()

    root_document.children.append(child_document)
    root_document.save()

    # ---> check documents hierarchy can be accessible both in a top-bottom and bottom-top approach
    assert child_document.parent.id == root_document.id
    ret_doc = models.WebDocuments.objects().filter(id=root_document.id)
    # parent -> child
    assert ret_doc[0].children[0].id == child_document.id
    # child -> parent
    assert child_document.parent.id == ret_doc[0].id

    # 3.2 Child Relationship
    grand_child_document = models.WebDocuments()
    grand_child_document.site = sites[0]
    grand_child_document.scan = scan
    grand_child_document.site_url = child_document.site_url + "/" + "child"
    grand_child_document.url = grand_child_document.site_url + "/" + "grand_child.html"
    grand_child_document.level = 3
    grand_child_document.num_node = 3
    grand_child_document.parent = child_document
    grand_child_document.is_cover = False
    grand_child_document.save()

    child_document.children.append(grand_child_document)
    child_document.save()

    # ---> check documents hierarchy can be accessible both in a top-bottom and bottom-top approach
    assert child_document.children[0].id == grand_child_document.id
    ret_doc = models.WebDocuments.objects().filter(id=root_document.id)
    # parent -> child -> child
    assert ret_doc[0].children[0].children[0].id == grand_child_document.id
    # child -> parent -> parent
    assert grand_child_document.parent.parent.id == root_document.id

    # (4)
    children = models.WebDocuments.objects().filter(id=child_document.id).only('children').first().children
    assert len(children) == 1
    # --> Ensure that the duplicate isn't inserted in the collection ...
    duplicate_document = models.WebDocuments()
    duplicate_document.id = grand_child_document.id
    child_document.children.append(duplicate_document)
    child_document.save_with_uniqueness('children')

    children = models.WebDocuments.objects().filter(id=child_document.id).only('children').first().children
    assert len(children) == 1
    # --> ... However unique ones are inserted
    unique_document = models.WebDocuments()
    unique_document.id = bson.ObjectId()
    child_document.children.append(unique_document)
    child_document.save_with_uniqueness('children')
    children = models.WebDocuments.objects().filter(id=child_document.id).only('children').first().children
    sites = models.Sites.objects()
    peers = models.Peers.objects()
    assert len(sites) > 0
    assert len(children) == 2


def test_scan_settings_db_operations():
    '''Create and insert new scan settings and ensure the required fields are respected.
    '''

    # Ensure Sites and Peers have been created
    sites = models.Sites.objects()
    peers = models.Peers.objects()
    assert len(sites) > 0
    assert len(peers) > 0

    scan_settings = models.ScanSettings()
    scan_settings.max_links = utils.MAX_LINKS
    scan_settings.max_size = utils.MAX_CONTENT_SIZE
    with pytest.raises(mongoengine.errors.ValidationError, match=re.escape("Field is required: ['site']")):
        scan_settings.save()

    scan_settings.site = sites[0]
    scan_settings.save()
    assert scan_settings.site.url == utils.SITE_URL_1

    scan_settings = models.ScanSettings()
    scan_settings.max_links = utils.MAX_LINKS
    scan_settings.max_size = utils.MAX_CONTENT_SIZE
    scan_settings.site = sites[1]
    scan_settings.save()
    assert scan_settings.site.url == utils.SITE_URL_2

    scan_settings = models.ScanSettings()
    scan_settings.max_links = utils.MAX_LINKS
    scan_settings.max_size = utils.MAX_CONTENT_SIZE
    scan_settings.site = sites[2]
    scan_settings.save()
    assert scan_settings.site.url == utils.SITE_URL_3


def test_scans_db_operations():
    '''Create, Insert and Update scans instances as follows:

    1) A scan without a list of documents can be saved with .save
    2) A scan with a non-empty list of document cannot be saved with .save
    3) A scan with a non-empty list of document can be saved with .save_with_uniqueness
    4) Uniqueness is actually enforced when using .save_with_uniqueness
    5) A scan with an empty list of documents cannot be saved with .save_with_uniqueness
    '''

    # Ensure Sites, Peers, Scan Settings and documents have been created
    sites = models.Sites.objects()
    peers = models.Peers.objects()
    scan_settings = models.ScanSettings.objects()
    documents = models.WebDocuments.objects()
    assert len(sites) > 0
    assert len(peers) > 0
    assert len(scan_settings) > 0
    assert len(documents) > 0

    # (1)
    scans = models.Scans()
    scans.peer = peers[0]
    scans.site = sites[0]
    scans.save()
    ret = models.Scans.objects(id=scans.id).first()
    assert ret.id == scans.id

    # (2)
    scans = models.Scans()
    scans.peer = peers[1]
    scans.site = sites[1]
    scans.documents.append(documents[0])
    scans.is_active = True
    with pytest.raises(errors.DbModelOperationError):
        scans.save(many_unique='documents')

    # (3)
    scan_id = scans.save_with_uniqueness('documents')

    ret = models.Scans.objects.filter(id=scan_id).first()
    assert ret.id == scan_id
    assert ret.is_active is True

    # (4.1)
    scans.id = scan_id
    scans.documents.append(documents[0])
    # ---> Ensure the two documents to be inserted are the same
    assert len(scans.documents) == 2
    assert scans.documents[0] == scans.documents[-1]
    # ---> Check that the second same document did not insert
    scans.save_with_uniqueness('documents')
    assert len(models.Scans.objects(id=scan_id).first().documents) == 1

    # (4.2)
    # ---> Rollback the scans.documents to have only one document
    scans.documents = scans.documents[:-1]
    assert len(scans.documents) == 1
    # ---> Add another document that has a different dbRef
    assert scans.documents[0].id == documents[0].id
    scans.documents.append(documents[1])
    assert scans.documents[0].id != scans.documents[-1].id
    # ---> Check that the second different document now was inserted
    scans.save_with_uniqueness('documents')
    assert len(models.Scans.objects(id=scan_id).first().documents) == 2

    # (5)
    scans = models.Scans()
    scans.peer = peers[1]
    scans.site = sites[1]
    scans.is_active = True
    with pytest.raises(errors.DbModelOperationError):
        scans.save_with_uniqueness('documents')


def test_site_instructions():
    '''Create, Insert and Update site instructions as follows

    1) Audit the number of required fields
    2) Saves can only be done when 'force_insert' flag has been settled
    3) Saving instructions from the scratch will only allow one set of instructions active which will be the first
    one found. The rest will be turned false
    4) Updates do not allow 'upsert' parameter
    5) Updates should only allow one set of instructions to be True, whether there is or not existing instruction
    records in the database that has its 'is_active' set to True
    6) Updates should allow to reset the instructions array when an empty list is provided
    7) 6) should be applicable to saves too
    '''

    models.Sites.objects().delete()
    assert not len(models.Sites.objects.all())

    # (1.1)
    web_ins_1 = models.SiteInstructions()
    doc_req_fields = [key for key, value in web_ins_1._fields.items() if value.required]
    assert len(doc_req_fields) == 2

    site = models.Sites()
    site.instructions.append(web_ins_1)
    site.url = 'http://192.168.1.1'
    with pytest.raises(mongoengine.errors.ValidationError) as ex:
        site.save(force_insert=True)
    for field in doc_req_fields:
        assert field in str(ex.value)

    # (1.2)
    yml_instructions = f"{utils.TEST_PATH}/stubs/yml_cases"
    with open(yml_instructions, "r") as fp:
        instructions_set = yaml.safe_load(fp)

    web_ins_1.cover_instructions = instructions_set
    with pytest.raises(mongoengine.errors.ValidationError) as ex:
        site.save(force_insert=True)
    assert re.search(r"\barticle_instructions\b", str(ex.value))

    # (2)
    web_ins_1.article_instructions = {'instructions': 'some more data'}
    with pytest.raises(errors.DbModelOperationError) as ex:
        site.save()
    assert re.search(r"\B'force_insert'\B", str(ex.value))

    # --> Ensure that force_insert is True
    with pytest.raises(errors.DbModelOperationError) as ex:
        site.save(force_insert=False)
    assert re.search(r"\B'force_insert'\B", str(ex.value))

    # (3)
    web_ins_2 = models.SiteInstructions()
    web_ins_2.cover_instructions = {'cover_2': 'some cover content here'}
    web_ins_2.article_instructions = {'article_2': 'some article content here'}
    web_ins_2.is_active = True

    web_ins_3 = models.SiteInstructions()
    web_ins_3.cover_instructions = {'cover_3': 'some content here'}
    web_ins_3.article_instructions = {'article_3': 'some article content here'}
    web_ins_3.is_active = True

    site.instructions.append(web_ins_2)
    site.instructions.append(web_ins_3)
    site.save(force_insert=True)
    db_ret = models.Sites.objects.first()
    assert len(db_ret.instructions) == 3
    assert db_ret.instructions[0].is_active is True
    assert db_ret.instructions[1].is_active is False
    assert db_ret.instructions[2].is_active is False

    # (4)
    web_ins_4 = models.SiteInstructions()
    web_ins_4.cover_instructions = {'cover_4': 'some content here'}
    web_ins_4.article_instructions = {'article_4': 'some article content here'}
    web_ins_4.is_active = True

    with pytest.raises(errors.DbModelOperationError) as ex:
        site.update(upsert=True)
    assert re.search(r"\B'upsert'\B", str(ex.value))

    # (5)
    site.update(instructions=[web_ins_4])
    db_ret = models.Sites.objects.first()
    assert len(db_ret.instructions) == 4
    assert db_ret.instructions[0].is_active is True
    assert db_ret.instructions[1].is_active is False
    assert db_ret.instructions[2].is_active is False
    assert db_ret.instructions[3].is_active is False

    # (6)
    site.update(instructions=[])
    db_ret = models.Sites.objects.first()
    assert len(db_ret.instructions) == 0

    # (7)
    site = models.Sites()
    site.url = 'http://192.168.1.2'
    site.save(force_insert=True)
    db_ret = models.Sites.objects(id=site.id).first()
    assert len(db_ret.instructions) == 0