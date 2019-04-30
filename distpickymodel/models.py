import datetime
import re
import six
import bson
import mongoengine

from pymongo import UpdateOne
from pymongo.errors import BulkWriteError
from distpickymodel import errors, utils

SITE_PRE_SAVE_UPDATE_KEYWORD = 'pre_save_update'
URL_REGEX_STRING = r'(?i)' + utils.url_regex.pattern


class StringField(mongoengine.fields.StringField):
    '''Class that subclasses native Mogoengine's StringField to temporarily cope with the bugs produced their issue
    https://github.com/MongoEngine/mongoengine/issues/1972
    '''

    def __init__(self, **kwargs):
        regex = kwargs.get('regex', None)  # Not sure what future holds for the 'regex' parameter
        if not regex or isinstance(regex, str):
            super().__init__(**kwargs)
            self.regex = regex  # important to override parent constructor as this creates a compiled regex
        elif not isinstance(regex, str):
            self.error(f"'regex' must be a string object. Instead {regex}")

    def validate(self, value):
        if not isinstance(value, six.string_types):
            self.error('StringField only accepts string values')

        if self.max_length is not None and len(value) > self.max_length:
            self.error('String value is too long')

        if self.min_length is not None and len(value) < self.min_length:
            self.error('String value is too short')

        if self.regex is not None and not re.match(self.regex, value):
            self.error('String value did not match validation regex')


class UniquenessMixin(mongoengine.Document):
    '''Mixing class that wraps up Mongonengine's Document class to provide extra functionality
    '''

    @property
    def updates(self):
        _updates, _removals = self._delta()
        return _updates

    def save(self, *args, **kwargs):
        '''Overrides Mongoengine's Document.save method.It does not allow saving a record in the database if one of the
        List-type attributes is not empty. This is to enforce using save_with_uniqueness method instead. Otherwise
        performs a save in the same terms as Document.save does
        '''
        try:
            many_unique = kwargs['many_unique']
        except KeyError:
            pass
        else:
            attribute = getattr(self, many_unique)
            self_name = self.__class__.__name__
            if len(attribute):
                raise errors.DbModelOperationError(f"It looks like you are trying to save a {self_name} "
                                                   f"object with a non-empty list of {many_unique}. "
                                                   f"Please use '{self_name.lower()}.save_with_uniqueness()' instead")
        return super().save(*args, **kwargs)

    def save_with_uniqueness(self, many_unique):
        '''It performs a save in the same terms as 'Document.save' does however it ensures that the 'add_to_set'
        modifier is used for the field indicated in many_unique. At present this method only supports one field where
        to used the add_to_set modifier.

        :param many_unique: 'List-type' field to which apply the add_to_set_modifier
        '''
        attribute = getattr(self, many_unique)
        self_name = self.__class__.__name__
        if not len(attribute):
            raise errors.DbModelOperationError(f"It looks like you are trying to save a {self_name} object with an "
                                               f"empty list {many_unique}. Please use '{self_name.lower()}.save()' "
                                               f"instead")

        updates, removals = self._delta()
        if not updates:
            raise errors.DbModelOperationError(f"It looks like you are trying to update '{self_name}' "
                                               f"but no fields were modified since this object was created or saved")
        kwargs = {(key if key != many_unique else 'add_to_set__' + key): value for key, value in updates.items()}
        pk = bson.ObjectId() if not self.id else self.id
        result = self.__class__.objects(id=pk).update_one(upsert=True, full_result=True, **kwargs)

        if result.upserted_id:
            self.id = result.upserted_id

        return self.id

    def is_modified(self):
        '''Check if the document has been modified
        '''
        updates, removals = self._delta()
        if updates or removals:
            return True
        return False

    @classmethod
    def bulk_update(cls, documents):
        '''Given a list of documents, send them all to the database to be updated in bulk by using pymongo's UpdateOne.
        Note that this is a class method so that I can be used with the model class instead.
        '''

        write_errors = []
        bulk_ops = []
        for document in documents:
            try:
                document.validate()
            except mongoengine.errors.ValidationError as ex:
                raise errors.DbModelOperationError(f"Document '{document}' with id '{document.id}' is invalid") \
                    from ex
            else:
                bulk_ops.append(UpdateOne({'_id': document.id}, {'$set': document.updates}))
        try:
            cls._get_collection().bulk_write(bulk_ops, ordered=False)
        except BulkWriteError as ex:
            write_errors = ex.details['writeErrors']

        return write_errors

    meta = {'allow_inheritance': True, 'abstract': True}


class Peers(UniquenessMixin):
    '''Collection that will store contextual details of a given peer, normally a worker.

    Each peer is identified by its ip_address and name. Peers could share the same IP address but will always have an
    unique Worker name.
    '''
    ip_address = StringField(required=True, regex=utils.ip_address_regex.pattern)
    name = mongoengine.StringField(required=True, unique=True)
    is_assigned = mongoengine.BooleanField(default=False)  # Flag that tell us if the Peer is assigned to a Scan
    is_allowed = mongoengine.BooleanField(default=False)
    created = mongoengine.DateTimeField(default=datetime.datetime.utcnow)
    updated = mongoengine.DateTimeField()


class SiteInstructions(mongoengine.EmbeddedDocument):
    '''Array that will store the different versions of the crawler instructions of a particular site along time

    Those that are the active ones will have the 'is_active' field set to True
    '''
    cover_instructions = mongoengine.DictField(required=True)
    article_instructions = mongoengine.DictField(required=True)
    created = mongoengine.DateTimeField(default=datetime.datetime.utcnow)
    updated = mongoengine.DateTimeField()
    is_active = mongoengine.BooleanField(default=True)


class Sites(mongoengine.Document):
    '''Collection that will store the details of the sites to be scanned.
    '''
    url = StringField(required=True, unique=True, regex=URL_REGEX_STRING)
    instructions = mongoengine.EmbeddedDocumentListField(SiteInstructions)

    @staticmethod
    def _enforce_only_one_active(instructions):
        '''Ensure that given in a given list of instructions only one record is active, if and only if, there is various
        records active. If no active records found the list of instructions is not modified

        :param instructions: a list of Embedded Document objects
        '''
        any_active = None
        for instruction in instructions:
            if any_active:
                instruction.is_active = False
            elif instruction.is_active:
                any_active = True

    def _pre_update(self, instructions):
        '''Method that may run before 'Document.save' or 'Document.update'. It ensures that the composition of a
        given list of instructions and those that are locally stored in the database, has only one record active
        '''
        db_me = Sites.objects(url=self.url).first()
        if db_me:
            instructions.extend(db_me.instructions)
        self._enforce_only_one_active(instructions)

    def save(self, *args, **kwargs):
        '''Overrides Mongoengine's Document.save method.It may perform one read and one save operation if pre_save
        condition is met. It ensures that the field instructions contains only one active record. The difference with
        update is that the underlying list in the database will be completely overwritten with the new
        Docucment.instructions field.
        '''

        force_insert = kwargs.get('force_insert', False)
        if not force_insert:
            raise errors.DbModelOperationError(f"Method of {self.__class__.__name__.lower()}.save() can only be used "
                                               f"for inserts. Please use 'force_insert' parameter")
        pre_save = kwargs.get('pre_save', True)
        if pre_save and self.instructions:
            self._enforce_only_one_active(self.instructions)
        return super().save(*args, **kwargs)

    def update(self, **kwargs):
        '''Overrides Mongoengine's Document.update method. It may perform one read and one update operation if pre_update
        condition is met. It ensures that the field instructions contains only one active record.

        '''
        upsert = kwargs.get('upsert', False)
        if upsert:
            raise errors.DbModelOperationError(f"Method of {self.__class__.__name__.lower()}.update() can only be "
                                               f"used for updates. Please do not use 'upsert' parameter")
        pre_update = kwargs.get('pre_update', True)

        instructions = kwargs.get('instructions', False)
        if instructions and pre_update:
            self._pre_update(instructions)
        return super().update(**kwargs)


class Scans(UniquenessMixin):
    '''Collection that will contain live data of each scan instance being undertaking by one peer on one site at one time.

    Every time a scan is commenced by a peer this structure is instantiated. Every time such scan is finished  by the
    same peer that instantiated it, this structure is also updated.
    '''
    peer = mongoengine.ReferenceField(Peers, required=True)
    site = mongoengine.ReferenceField(Sites, required=True)
    process_name = mongoengine.StringField(default=None)
    is_active = mongoengine.BooleanField(default=False)  # Flag that let us know if the scan is still undergoing
    full_scan = mongoengine.BooleanField(default=True)
    started_at = mongoengine.DateTimeField()  # started, complete and is_active tell us about the status of this scan
    finished_at = mongoengine.DateTimeField()
    documents = mongoengine.ListField(mongoengine.ReferenceField('WebDocuments'))


class ScanSettings(UniquenessMixin):
    '''Collection that will contain the details of all scan instances performed on all sites all along time.

    It provides the overall scraping context for each scan instance initiated. The contexts are associated to sites
    and not scans themselves.
    '''
    site = mongoengine.ReferenceField(Sites, required=True)
    num_levels = mongoengine.IntField(default=-1)
    min_span = mongoengine.IntField(default=5)
    max_span = mongoengine.IntField(default=60)
    max_links = mongoengine.IntField(default=100)  # Max num links per scan is 100 by default
    max_size = mongoengine.IntField(default=1024)  # Max size per article is 1024 Kb by default
    parser = mongoengine.StringField(default='html5lib')
    mime_types = mongoengine.ListField(default=['text/html'])
    is_active = mongoengine.BooleanField(default=True)  # Flag that tells if this scan is still applicable
    created = mongoengine.DateTimeField(default=datetime.datetime.utcnow)
    scans = mongoengine.ListField(mongoengine.ReferenceField(Scans))


class WebContent(mongoengine.EmbeddedDocument):
    '''Structure that will contain the content of scraped web pages as a result of each scan taking place.

    A Document may end up having different versions of the same content if required
    '''
    url = StringField(required=True, regex=URL_REGEX_STRING)
    title = mongoengine.StringField()
    version = StringField(required=True, regex=utils.version_regex.pattern)
    content = mongoengine.StringField()
    created = mongoengine.DateTimeField(default=datetime.datetime.utcnow)
    updated = mongoengine.DateTimeField()


class WebDocuments(UniquenessMixin):
    '''Collection that stores the web pages scanned and the hierarchy defining the relationships of such pages.

    WebDocument represents each web page scraped, wrapping the content extracted for such web page and defining the
    relationship between those pages. A page could have child links to other pages and an also ancestor. WebDocument
    defines this hierarchy through 'paren' and 'children' field.

    '''
    site = mongoengine.ReferenceField(Sites, required=True)
    scan = mongoengine.ReferenceField(Scans, required=True)
    parent = mongoengine.ReferenceField('self')
    children = mongoengine.ListField(mongoengine.ReferenceField('self'))
    content = mongoengine.EmbeddedDocumentListField(WebContent)
    url = StringField(required=True, regex=URL_REGEX_STRING)
    site_url = StringField(required=True, regex=URL_REGEX_STRING)
    level = mongoengine.IntField(required=True)
    num_node = mongoengine.IntField(required=True)
    is_cover = mongoengine.BooleanField(default=False)
    created = mongoengine.DateTimeField(default=datetime.datetime.utcnow)
    updated = mongoengine.DateTimeField()


