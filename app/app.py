from bdb import effective
from io import StringIO
from uuid import UUID
import re
import logging
from app.helpers.structlog import config_structlog, common_handler
import structlog
import os
from flask import Flask, jsonify, request, Response
from decouple import config
from app.models.value_sets import *
from app.models.concept_maps import *
from app.models.surveys import *
from werkzeug.exceptions import HTTPException 

# Configure the logger when the application is imported. This ensures that
# everything below uses the same configured logger.
config_structlog()
logger = structlog.getLogger()
# This configures _all other loggers_ including every dependent module that
# has logging implemented to have the format defined in the helper module.
root_logger = logging.getLogger().root
root_logger.addHandler(common_handler)


def create_app(script_info=None):

    app = Flask(__name__)
    app.config['MOCK_DB'] = config('MOCK_DB', False)
    app.config['ENABLE_DATADOG_APM'] = config('ENABLE_DATADOG_APM', True)
 
    if app.config['ENABLE_DATADOG_APM']:
        from ddtrace import patch_all
        patch_all()

    @app.route('/ping')
    def ping():
        return 'OK'
    
    @app.errorhandler(HTTPException)
    def handle_exception(e):
        logger.critical(e.description, stack_info=True)
        return jsonify({"message": e.description}), e.code
    
    # Value Set Endpoints
    # FHIR endpoint
    @app.route('/ValueSet/<string:uuid>/$expand') #tricky, needs to be split up
    def expand_value_set(uuid):
        #force_new = request.values.get('force_new') == 'true'
        vs_version = ValueSetVersion.load(uuid)
        vs_version.expand()
        return jsonify(vs_version.serialize())

    @app.route('/ValueSets/') #READ ONLY - stays
    def get_all_value_sets_metadata():
        active_only = False if request.values.get('active_only') == 'false' else True
        return jsonify(ValueSet.load_all_value_set_metadata(active_only))

    @app.route('/ValueSets/all/') #READ ONLY - stays
    def get_all_value_sets():
        status = request.values.get('status').split(',')
        value_sets = ValueSet.load_all_value_sets_by_status(status)
        for x in value_sets: x.expand()
        serialized = [x.serialize() for x in value_sets]
        return jsonify(serialized)

    @app.route('/ValueSets/<string:identifier>/versions/') #READ ONLY - stays
    def get_value_set_versions(identifier):
        uuid = ValueSet.name_to_uuid(identifier)
        return jsonify(ValueSet.load_version_metadata(uuid))


    @app.route('/ValueSets/<string:identifier>/most_recent_active_version') #READ ONLY - stays (load_most_recent_active_version is a query)
    def get_most_recent_version(identifier):
        uuid = ValueSet.name_to_uuid(identifier)
        version = ValueSet.load_most_recent_active_version(uuid)
        version.expand()
        return jsonify(version.serialize())


    # Survey Endpoints
    @app.route('/surveys/<string:survey_uuid>')  #READ ONLY - stays
    def export_survey(survey_uuid):
        organization_uuid = request.values.get("organization_uuid")
        # print(survey_uuid, organization_uuid)
        exporter = SurveyExporter(survey_uuid, organization_uuid)

        file_buffer = StringIO()
        exporter.export_survey().to_csv(file_buffer)
        file_buffer.seek(0)
        response = Response(
            file_buffer, 
            mimetype="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={exporter.survey_title} {exporter.organization_name}.csv"
            })
        return response

    # Concept Map Endpoints 
    @app.route('/ConceptMaps/<string:version_uuid>') #READ ONLY - stays
    def get_concept_map_version(version_uuid):
        concept_map_version = ConceptMapVersion(version_uuid)
        return jsonify(concept_map_version.serialize())

    return app


application = create_app()

if __name__ == '__main__':
    application.run(debug=True, host="0.0.0.0", port=5500)