from elasticsearch import TransportError
from sqlalchemy import text

import app.models.terminologies
import app.models.codes
from app.database import get_db

# This is from when we used `scrappyMaps`. It's used for mapping inclusions and can be removed as soon as that has been ported to the new maps.
class DeprecatedConceptMap:
    def __init__(self, uuid, relationship_types, concept_map_name):
        self.uuid = uuid
        self.relationship_types = relationship_types
        
        self.concept_map_name = concept_map_name

        self.mappings = []
        self.load_mappings()

    def load_mappings(self):
        conn = get_db()
        mapping_query = conn.execute(
            text(
                """
                select *
                from "scrappyMaps".map_table
                where "mapsetName" = :map_set_name
                and "targetConceptDisplay" != 'null'
                """
            ), {
                'map_set_name': self. concept_map_name,
                # 'relationship_codes': self.relationship_types
            }
        )
        source_system = None
        source_version = None
        target_system = None
        target_version = None
        self.mappings = [
            (
                app.models.codes.Code(source_system, source_version, x.sourceConceptCode, x.sourceConceptDisplay),
                app.models.codes.Code(target_system, target_version, x.targetConceptCode, x.targetConceptDisplay),
                x.relationshipCode
            ) for x in mapping_query
        ]

    @property
    def source_code_to_target_map(self):
        result = {}
        for item in self.mappings:
            if item[2] not in self.relationship_types:
                continue
            code = item[0].code.strip()
            mapped_code_object = item[1]
            if code not in result:
                result[code] = [mapped_code_object]
            else:
                result[code].append(mapped_code_object)
        return result

    @property
    def target_code_to_source_map(self):
        result = {}
        for item in self.mappings:
            if item[2] not in self.relationship_types:
                continue
            code = item[1].code.strip()
            mapped_code_object = item[0]
            if code not in result:
                result[code] = [mapped_code_object]
            else:
                result[code].append(mapped_code_object)
        return result

# This is the new maps system
class ConceptMap:
    def __init__(self, uuid):
        self.uuid = uuid
        # self.name = None
        self.title = None
        self.description = None
        self.purpose = None
        self.publisher = None
        self.experimental = None
        self.author = None
        self.created_date = None

        self.load_data()

    def load_data(self):
        pass

class ConceptMapVersion:
    def __init__(self, uuid):
        self.uuid = uuid
        self.concept_map = ConceptMap(None)
        self.description = None
        self.comments = None
        self.status = None
        self.created_date = None
        self.effective_start = None
        self.effective_end = None
        self.version = None
        
        self.load_data()

    def load_data(self):
        pass

    def serialize(self):
        combined_description = str(self.concept_map.description) + ' ' + str(self.description)

        return {
            'title': self.concept_map.title,
            'description': combined_description,
            'purpose': self.concept_map.purpose,
            # todo: publisher, experimental, author all need to be loaded from parent
            # todo: comments, status, effective_start, effective_end, and version should be loaded from the ConceptMapVersion

            # For now, we are intentionally leaving out created_dates as they are not part of the FHIR spec and not required for our use cases at this time
        }

class Mapping:
    pass