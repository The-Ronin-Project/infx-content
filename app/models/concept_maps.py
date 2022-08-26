from elasticsearch import TransportError
from numpy import source
from sqlalchemy import text, bindparam
import app.models.terminologies
import app.models.codes
from app.database import get_db
from app.models.codes import Code

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
        self.mappings = [
            (
                app.models.codes.Code(x.sourceTerminologyCodeSystem, x.sourceTerminologyRelease, x.sourceConceptCode, x.sourceConceptDisplay),
                app.models.codes.Code(x.targetTerminologyCodeSystem, x.targetTerminologyRelease, x.targetConceptCode, x.targetConceptDisplay),
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
        conn = get_db()
        data = conn.execute(
            text(
                """
                select * from concept_maps.concept_map
                where uuid=:concept_map_uuid
                """
            ), {
                'concept_map_uuid': self.uuid
            }
        ).first()

        self.title = data.title
        self.description = data.description
        self.purpose = data.purpose
        self.publisher = data.publisher
        self.experimental = data.experimental
        self.author = data.author
        self.created_date = data.created_date

    @classmethod
    def load_all_versions_metadata(cls):
        """
        This function will return metadata for all concept map versions
        """
        conn = get_db()
        query = text(
            """
            select cmv.uuid as version_uuid, cmv.description as version_description, cm.description as concept_map_description, * 
            from concept_maps.concept_map_version cmv
            join concept_maps.concept_map cm on cmv.concept_map_uuid=cm.uuid
            """
        )
        results = conn.execute(query)
        response = []
        for result in results:
            response.append({
                'concept_map_uuid': result.concept_map_uuid,
                'concept_map_version_uuid': result.version_uuid,
                'version_description': result.version_description,
                'concept_map_description': result.concept_map_description,
                'comments': result.comments,
                'status': result.status,
                'effective_start': result.effective_start,
                'effective_end': result.effective_end,
                'version': result.version,
                'title': result.title,
                'author': result.author,
                'purpose': result.purpose,
            })

        return response

class ConceptMapVersion:
    def __init__(self, uuid):
        self.uuid = uuid
        self.concept_map = None
        self.description = None
        self.comments = None
        self.status = None
        self.created_date = None
        self.effective_start = None
        self.effective_end = None
        self.version = None
        self.mappings = {}
        
        self.load_data()

    def load_data(self):
        conn = get_db()
        data = conn.execute(
            text(
                """
                select * from concept_maps.concept_map_version
                where uuid=:version_uuid
                """
            ), {
                'version_uuid': self.uuid
            }
        ).first()

        self.concept_map = ConceptMap(data.concept_map_uuid)
        self.description = data.description
        self.comments = data.comments
        self.status = data.status
        self.created_date = data.created_date
        self.effective_start = data.effective_start
        self.effective_end = data.effective_end
        self.version = data.version

        self.load_mappings()

    def load_mappings(self):
        conn = get_db()
        query = """
            select source_concept.code as source_code, source_concept.display as source_display, source_concept.system as source_system, 
            tv_source.version as source_version, tv_source.fhir_uri as source_fhir_uri,
            relationship_codes.code as relationship_code, 
            concept_relationship.target_concept_code, concept_relationship.target_concept_display,
            concept_relationship.target_concept_system_version_uuid as target_system,
            tv_target.version as target_version, tv_target.fhir_uri as target_fhir_uri
            from concept_maps.source_concept
            left join concept_maps.concept_relationship
            on source_concept.uuid = concept_relationship.source_concept_uuid
            join concept_maps.relationship_codes
            on relationship_codes.uuid = concept_relationship.relationship_code_uuid
            join terminology_versions as tv_source
            on cast(tv_source.uuid as uuid) = cast(source_concept.system as uuid)
            join terminology_versions as tv_target
            on tv_target.uuid = concept_relationship.target_concept_system_version_uuid
            where source_concept.concept_map_version_uuid = :concept_map_version_uuid
        """

        results = conn.execute(
            text(
                query
            ), {
                'concept_map_version_uuid': self.uuid,
            }
        )

        for item in results:
            source_code = Code(item.source_fhir_uri, item.source_version, item.source_code, item.source_display)
            target_code = Code(item.target_fhir_uri, item.target_version, item.target_concept_code, item.target_concept_display)
            equivalence = item.relationship_code

            mapping = Mapping(source_code, equivalence, target_code)
            if source_code in self.mappings:
                self.mappings[source_code].append(mapping)
            else:
                self.mappings[source_code]=[mapping]
        
    def serialize_mappings(self):
        # Identify all the source terminology / target terminology pairings in the mappings
        source_target_pairs_set = set()

        for source_code, mappings in self.mappings.items():
            source_uri = source_code.system
            source_version = source_code.version
            for mapping in mappings:
                target_uri = mapping.target_code.system
                target_version = mapping.target_code.version

                source_target_pairs_set.add(
                    (source_uri, source_version, target_uri, target_version)
                )

        # Serialize the mappings
        groups = []

        for source_uri, source_version, target_uri, target_version in source_target_pairs_set:
            elements = []
            for source_code, mappings in self.mappings.items():
                if source_code.system == source_uri and source_code.version == source_version:
                    filtered_mappings = [x for x in mappings if x.target_code.system == target_uri and x.target_code.version == target_version]
                    elements.append(
                        {
                            "code": source_code.code,
                            "display": source_code.display,
                            "target": [
                                {
                                    "code": mapping.target_code.code,
                                    "display": mapping.target_code.display,
                                    "equivalence": mapping.equivalence,
                                    "comment": None
                                } 
                                for mapping in filtered_mappings]
                        }
                    )
        
            groups.append(
                    {
                    "source": source_uri,
                    "sourceVersion": source_version,
                    "target": target_uri,
                    "targetVersion": target_version,
                    "element": elements
                    }
            )
        
        return groups

    def serialize(self):
        combined_description = str(self.concept_map.description) + ' Version-specific notes:' + str(self.description)

        return {
            'title': self.concept_map.title,
            'description': combined_description,
            'purpose': self.concept_map.purpose,
            'publisher': self.concept_map.purpose,
            'experimental': self.concept_map.experimental,
            'comments': self.comments,
            'status': self.status,
            'effective_start': self.effective_start,
            'effective_end': self.effective_end,
            'version': self.version,
            'group': self.serialize_mappings(),
            'resourceType' : 'ConceptMap',
            # For now, we are intentionally leaving out created_dates as they are not part of the FHIR spec and not required for our use cases at this time
        }

class Mapping:
    def __init__(self, source_code, equivalence, target_code):
        self.source_code = source_code
        self.equivalence = equivalence #relationship code
        self.target_code = target_code

    def __repr__(self):
        return f"Mapping({self.source_code.code}, {self.equivalence}, {self.target_code.code})"