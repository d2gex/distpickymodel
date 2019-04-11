import mongoengine

from distpickymodel import models

RUN_OP = 'RUN'
STOP_OP = 'STOP'
STOP_AND_RUN_OP = 'STOP AND RUN'
OPERATIONS = [RUN_OP, STOP_OP, STOP_AND_RUN_OP]
WEEK_DAYS = [x for x in range(7)]


class ServerInstructions(models.UniquenessMixin):
    '''Collection that holds the instructions that the server will send to each worker
    '''
    site = mongoengine.ReferenceField(models.Sites, required=True)
    operation = mongoengine.StringField(required=True, choices=OPERATIONS)
    stop_at = mongoengine.DateTimeField()
    exclude_dates = mongoengine.ListField(mongoengine.DateTimeField())
    weekdays = mongoengine.ListField(mongoengine.IntField(choices=WEEK_DAYS))
    times = mongoengine.ListField(mongoengine.IntField(min_value=1, max_value=24*3600))
    running = mongoengine.BooleanField(default=False)


class ExtendedScans(models.Scans):
    '''Extension of the models.Scans Collections that provides a relationship of such collection with the
    ServerInstructions collection
    '''
    run_instruction = mongoengine.ReferenceField(ServerInstructions, required=True)
    stop_instruction = mongoengine.ReferenceField(ServerInstructions)
