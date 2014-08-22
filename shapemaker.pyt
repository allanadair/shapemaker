"""
Asynchronous Python toolbox for building shapefiles from FeatureSets.

"""
from arcpy import AddMessage, env, Parameter
from arcpy.management import CopyFeatures
import json
import logging
from logging import Handler
from os.path import basename, dirname, join
from zipfile import ZIP_DEFLATED
from zipfile import ZipFile


class ToolboxLogHandler(Handler):
    """
    Custom logging handler for passing along messages.

    """
    def __init__(self):
        Handler.__init__(self)

    def emit(self, record):
        AddMessage(self.format(record))


def logger_init(instance, debug=False):
    """
    Shared function for initializing a custom logger.

    """
    if debug:
        # Set logging level to DEBUG
        instance.logger.setLevel(logging.DEBUG)

        # Console log handler
        logger = logging.StreamHandler()

    else:
        # Set logging level to INFO
        instance.logger.setLevel(logging.INFO)

        # Toolbox log handler
        logger = ToolboxLogHandler()

    # Create a universal logging formatter
    fmtstr = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    formatter = logging.Formatter(fmtstr)

    # Add formatter to console handler
    logger.setFormatter(formatter)

    # add handler to logger
    instance.logger.handlers = []  # Clear handlers. (ArcMap bug?)
    instance.logger.addHandler(logger)


class ShapeMaker(object):
    """
    Shapemaker tool. This tool will receive a featureset and build a shape
    file. The result will be a URL to a zip file.

    """
    def __init__(self, debug=False):
        """
        Initialization.

        """
        self.label = "Shapemaker"
        self.description = "Tool for generating shapefiles"
        self.canRunInBackground = True
        self._ws = env.scratchFolder
        self._baseurl = None
        env.overwriteOutput = True
        self.logger = logging.getLogger(self.label)
        logger_init(instance=self, debug=debug)

        if debug:
            self._cwd = '.'
        else:
            self._cwd = dirname(__file__.split('#')[0])

        # Set properties for building paths or URLs
        try:
            path = '\\'.join(self._cwd.split('\\')[:-2])
            name = 'serviceconfiguration.json'
            jsonfile = json.load(file('{0}\\{1}'.format(path, name)))
            service_props = jsonfile['service']['properties']
            extensions = jsonfile['service']['extensions']

            # We can get the server base url from the configuration
            # of the WPSServer, even if it is disabled.
            for ext in extensions:
                if ext['typeName'] == 'WPSServer':
                    extension_props = ext['properties']
                    break

            base = extension_props['onlineResource'].split('/services/')[0]
            vdir = service_props['jobsVirtualDirectory']

            self._baseurl = '{0}{1}'.format(base, vdir)

        except:
            self.logger.warning('Can\'t determine ArcGIS Server configuration')

    def getParameterInfo(self):
        """
        Parameter definitions.

        """
        p0 = Parameter(displayName=u'features',
                       name='features',
                       datatype='GPFeatureRecordSetLayer',
                       parameterType='Required',
                       direction='Input')

        p1 = Parameter(displayName=u'name',
                       name='name',
                       datatype='GPString',
                       parameterType='Required',
                       direction='Input')
        p1.value = 'data'

        p2 = Parameter(displayName=u'url',
                       name='url',
                       datatype='GPString',
                       parameterType='Derived',
                       direction='Output')

        return [p0, p1, p2]

    def execute(self, parameters, messages):
        """
        The source code of the tool.

        """
        features = parameters[0].value
        name = parameters[1].value
        zip_file = '{0}.zip'.format(name)
        shp_files = (join(self._ws, '{0}.shp'.format(name)),
                     join(self._ws, '{0}.shx'.format(name)),
                     join(self._ws, '{0}.dbf'.format(name)),
                     join(self._ws, '{0}.prj'.format(name)))

        try:
            # Copy features to shapefile
            output_path = '{0}\\{1}.shp'.format(self._ws,
                                                name)
            CopyFeatures(in_features=features,
                         out_feature_class=output_path)
            self.logger.info('Copied features to shapefile')

            # Add file gdb to a zip file
            with ZipFile(join(self._ws, zip_file), 'w') as zipf:
                for f in shp_files:
                    zipf.write(f,
                               arcname=basename(f),
                               compress_type=ZIP_DEFLATED)

            self.logger.info('Zipped shapefile')

            # Build a url (or path, when running locally) to the zip file
            if self._baseurl:

                jobpart = self._ws.split('\\')[-3:]
                jobpart = '/'.join(jobpart)
                jobpart = jobpart.replace('arcgisjobs/', '')

                url = '{0}/{1}/{2}'.format(self._baseurl, jobpart, zip_file)

                parameters[2].value = url

            else:
                parameters[2].value = join(self._ws, zip_file)

            self.logger.info(parameters[2].value)

        except Exception as e:
            self.logger.critical(unicode(e).replace('\n', ' '))


class Toolbox(object):
    """
    Elevation GP Toolbox. Modify the tools property as tools are added
    or removed.

    """
    def __init__(self):
        self.label = 'Shapemaker'
        self.alias = 'Shapemaker'
        self.description = 'Generates shapefiles'
        self.tools = [ShapeMaker]
