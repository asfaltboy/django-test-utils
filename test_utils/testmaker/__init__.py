import logging
import os
from os import path
from django.core import serializers as django_serializers
from test_utils.management.commands.relational_dumpdata import _relational_dumpdata
from django.template import Context, Template
from django.conf import settings

TESTMAKER_TEMPLATE = """
from django.test import TestCase
from django.test import Client
from django import template
from django.db.models import get_model

class Testmaker(TestCase):
{% if create_fixtures %}
    fixtures = ["{{ fixture_file }}"]
{% else %}
    #fixtures = ["{{ app_name }}_testmaker"]
{% endif %}
"""

class Testmaker(object):

    def __init__(self, app=None, verbosity=1, create_fixtures=False, format='xml', addrport='', **kwargs):
        self.app = app
        self.verbosity = verbosity
        self.create_fixtures = create_fixtures
        self.format = format
        self.addrport = addrport
        self.kwargs = kwargs
        #Assume we're writing new tests until proven otherwise
        self.new_tests = True

    def perpare(self):
        self.set_paths()
        self.setup_logging()
        self.prepare_test_file()
        self.insert_middleware()


    def set_paths(self):
        if self.app:
            self.app_name = self.app.__name__.split('.')[-2]
            self.base_dir = path.dirname(self.app.__file__)
        else:
            self.app_name = 'tmp'
            #TODO: Need to make this platform independent.
            self.base_dir = '/tmp/'

        #Figure out where to store data
        self.fixtures_dir = path.join(self.base_dir, 'fixtures')
        self.fixture_file = path.join(self.fixtures_dir, '%s_testmaker.%s' % (self.app_name, self.format))
        if self.create_fixtures:
            if not path.exists(self.fixtures_dir):
                os.mkdir(self.fixtures_dir)

        #Setup test and serializer files
        self.tests_dir = path.join(self.base_dir, 'tests')
        self.test_file = path.join(self.tests_dir, '%s_testmaker.py' % (self.app_name))
        #TODO: Make this have the correct file extension based on serializer used
        self.serialize_file = path.join(self.tests_dir, '%s_testdata.serialized' % (self.app_name))

        if not path.exists(self.tests_dir):
            os.mkdir(self.tests_dir)
        if path.exists(self.test_file):
            self.new_tests = False

        if self.verbosity > 0:
            print "Handling app '%s'" % self.app_name
            print "Logging tests to %s" % self.test_file
            if self.create_fixtures:
                print "Logging fixtures to %s" % self.fixture_file

    def setup_logging(self, test_file=None, serialize_file=None):
        #supress other logging
        logging.basicConfig(level=logging.CRITICAL,
                            filename="/dev/null")

        if not test_file:
            test_file = self.test_file
        else:
            self.test_file = test_file
        log = logging.getLogger('testprocessor')
        log.setLevel(logging.INFO)
        handler = logging.FileHandler(test_file, 'a')
        handler.setFormatter(logging.Formatter('%(message)s'))
        log.addHandler(handler)
        self.log = log

        if not serialize_file:
            serialize_file = self.serialize_file
        else:
            self.serialize_file = serialize_file
        log_s = logging.getLogger('testserializer')
        log_s.setLevel(logging.INFO)
        handler_s = logging.FileHandler(self.serialize_file, 'a')
        handler_s.setFormatter(logging.Formatter('%(message)s'))
        log_s.addHandler(handler_s)
        self.serializer = log_s

    def prepare_test_file(self):
        if self.new_tests:
            t = Template(TESTMAKER_TEMPLATE)
            c = Context({
                'create_fixtures': self.create_fixtures,
                'app_name': self.app_name,
                'fixture_file': self.fixture_file,
            })
            self.log.info(t.render(c))
        else:
            if self.verbosity > 0:
                print "Appending to current log file"

    def insert_middleware(self):
        if self.verbosity > 0:
            print "Inserting TestMaker logging server..."
        settings.MIDDLEWARE_CLASSES += ('test_utils.testmaker.middleware.testmaker.TestMakerMiddleware',)

    def make_fixtures(self):
        if self.verbosity > 0:
            print "Creating fixture at " + self.fixture_file
        objects, collected = _relational_dumpdata(self.app, set())
        serial_file = open(self.fixture_file, 'a')
        try:
            django_serializers.serialize(self.format, objects, stream=serial_file, indent=4)
        except Exception, e:
            print ("Unable to serialize database: %s" % e)
