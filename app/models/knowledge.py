# # from pydantic import BaseModel, Field
# # from typing import List, Optional

# # class ExtractedConcept(BaseModel):
# #     """Represents a discrete scientific term, attribute, or methodology."""
# #     canonical_name: str = Field(..., description="The official scientific name of the concept.")
# #     definition: str = Field(..., description="Clear, authoritative definition based on the text.")
# #     category: str = Field(..., description="E.g., Sensory Attribute, Method, Scale, Family, Axis.")
# #     synonyms: List[str] = Field(default_factory=list, description="Alternative names or abbreviations.")
# #     keywords: List[str] = Field(default_factory=list, description="Searchable keywords related to this concept.")
# #     sentiment: Optional[str] = Field(None, description="Positive, Negative, or Neutral if applicable to descriptors.")

# # class ConceptRelationship(BaseModel):
# #     """Maps the graph edges between two concepts."""
# #     source_concept: str = Field(..., description="The canonical name of the origin concept.")
# #     target_concept: str = Field(..., description="The canonical name of the destination concept.")
# #     relationship_type: str = Field(
# #         ..., 
# #         description="Must be one of: is_child_of, described_by, measured_by, categorized_as, related_to, causes, influences, part_of, uses_method, benchmarked_by, triggered_by"
# #     )

# # class ScientificRule(BaseModel):
# #     """Captures Cause -> Effect logic and standardized rules."""
# #     rule_statement: str = Field(..., description="The complete scientific rule or benchmark.")
# #     condition: Optional[str] = Field(None, description="The 'If' trigger (e.g., If sugar concentration > 10%).")
# #     effect: Optional[str] = Field(None, description="The 'Then' result (e.g., Sweetness intensity plateaus).")

# # class Procedure(BaseModel):
# #     """Captures step-by-step scientific methods."""
# #     method_name: str = Field(..., description="Name of the test or procedure.")
# #     steps: List[str] = Field(..., description="Ordered list of operational steps.")

# # class KnowledgeExtractionPayload(BaseModel):
# #     """The master schema for the LLM output per structural section."""
# #     concepts: List[ExtractedConcept] = Field(default_factory=list)
# #     relationships: List[ConceptRelationship] = Field(default_factory=list)
# #     scientific_rules: List[ScientificRule] = Field(default_factory=list)
# #     procedures: List[Procedure] = Field(default_factory=list)

    




# from pydantic import BaseModel, Field
# from typing import List, Optional

# class NodeAttribute(BaseModel):
#     attribute_name: str = Field(description="Name of the sub-property or attribute (e.g., 'Sweetness Level', 'Temperature').")
#     attribute_value: str = Field(description="Value or description of the attribute.")

# class KnowledgeNode(BaseModel):
#     canonical_name: str = Field(description="The primary name of the scientific entity, method, or concept.")
#     category: str = Field(description="e.g., Method, Theory, Entity, Material, Instrument, Property.")
#     definition: str = Field(description="A concise scientific definition.")
#     attributes: List[NodeAttribute] = Field(description="Specific properties, sub-nodes, or characteristics of this concept.")
#     synonyms: List[str] = Field(default_factory=list)
#     keywords: List[str] = Field(default_factory=list)

# class KnowledgeRelationship(BaseModel):
#     source_node: str = Field(description="Exact canonical_name of the source node.")
#     target_node: str = Field(description="Exact canonical_name of the target node.")
#     relationship_type: str = Field(description="How they connect (e.g., uses_method, measures, is_a, requires).")

# class ScientificRule(BaseModel):
#     rule_statement: str
#     context: str

# class Procedure(BaseModel):
#     procedure_name: str
#     steps: List[str]

# class KnowledgeExtractionPayload(BaseModel):
#     nodes: List[KnowledgeNode]
#     relationships: List[KnowledgeRelationship]
#     scientific_rules: List[ScientificRule]
#     procedures: List[Procedure]






from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class ConceptAttribute(BaseModel):
    name: str
    value: str

class KnowledgeConcept(BaseModel):
    canonical_name: str
    category: Optional[str] = None
    definition: Optional[str] = None
    synonyms: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    attributes: List[ConceptAttribute] = Field(default_factory=list)
    
    # Provenance (Optional for backward compatibility with older extraction artifacts)
    hierarchy_context: Optional[str] = None
    source_page: Optional[int] = None
    element_id: Optional[str] = None
    section_path: Optional[List[str]] = None

class KnowledgeRelationship(BaseModel):
    source_concept: str
    target_concept: str
    relationship_type: str
    
    # Relationship Provenance
    source_section: Optional[str] = None
    source_page: Optional[int] = None

class ScientificRule(BaseModel):
    rule_statement: str
    context: Optional[str] = None
    source_page: Optional[int] = None

class Procedure(BaseModel):
    procedure_name: str
    steps: List[str] = Field(default_factory=list)
    source_page: Optional[int] = None

class KnowledgeExtractionPayload(BaseModel):
    document_id: str
    concepts: List[KnowledgeConcept] = Field(default_factory=list)
    relationships: List[KnowledgeRelationship] = Field(default_factory=list)
    scientific_rules: List[ScientificRule] = Field(default_factory=list)
    procedures: List[Procedure] = Field(default_factory=list)