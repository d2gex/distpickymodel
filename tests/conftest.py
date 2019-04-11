import mongoengine

DATABASE = 'distpickymodel'
HOST = 'localhost'
db = mongoengine.connect(DATABASE, host=HOST)

