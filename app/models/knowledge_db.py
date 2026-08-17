# from sqlalchemy import Column, String, Integer, Text, ForeignKey, JSON, UniqueConstraint
# from sqlalchemy.orm import relationship

# # ⚠️ UPDATE THIS IMPORT TO MATCH YOUR ACTUAL PROJECT ARCHITECTURE ⚠️
# # e.g., from app.db.base_class import Base
# from app.db.session import Base 

# class KnowledgeNode(Base):
#     """Global concepts extracted across all documents."""
#     __tablename__ = 'knowledge_nodes'

#     id = Column(String(64), primary_key=True) # MD5(canonical_name)
#     canonical_name = Column(String(255), unique=True, index=True, nullable=False)
#     category = Column(String(100))
#     definition = Column(Text)
#     synonyms = Column(JSON)
#     keywords = Column(JSON)
    
#     attributes = relationship("NodeAttribute", back_populates="node", cascade="all, delete-orphan")
#     provenances = relationship("NodeProvenance", back_populates="node", cascade="all, delete-orphan")

# class NodeAttribute(Base):
#     """Attributes tied to the global concept (e.g., 'Scale Type: 9-point')."""
#     __tablename__ = 'node_attributes'

#     id = Column(String(64), primary_key=True)
#     node_id = Column(String(64), ForeignKey('knowledge_nodes.id', ondelete='CASCADE'))
#     name = Column(String(255), nullable=False)
#     value = Column(Text, nullable=False)

#     __table_args__ = (UniqueConstraint('node_id', 'name', name='uq_node_attribute'),)
#     node = relationship("KnowledgeNode", back_populates="attributes")

# class NodeProvenance(Base):
#     """Document-specific occurrence of a concept. Preserves context."""
#     __tablename__ = 'node_provenances'

#     id = Column(String(64), primary_key=True)
#     node_id = Column(String(64), ForeignKey('knowledge_nodes.id', ondelete='CASCADE'))
#     document_id = Column(String(64), index=True, nullable=False)
#     source_page = Column(Integer)
#     hierarchy_context = Column(Text)
#     element_id = Column(String(128))
#     section_path = Column(JSON)

#     __table_args__ = (UniqueConstraint('node_id', 'document_id', 'element_id', 'source_page', name='uq_node_provenance'),)
#     node = relationship("KnowledgeNode", back_populates="provenances")

# class KnowledgeEdge(Base):
#     """Relationships between nodes, with document provenance."""
#     __tablename__ = 'knowledge_edges'

#     id = Column(String(64), primary_key=True)
#     document_id = Column(String(64), index=True, nullable=False)
#     source_node_id = Column(String(64), ForeignKey('knowledge_nodes.id', ondelete='CASCADE'))
#     target_node_id = Column(String(64), ForeignKey('knowledge_nodes.id', ondelete='CASCADE'))
#     relationship_type = Column(String(100), nullable=False)
#     source_section = Column(Text)
#     source_page = Column(Integer)

#     __table_args__ = (UniqueConstraint('document_id', 'source_node_id', 'relationship_type', 'target_node_id', name='uq_knowledge_edge'),)

# class ScientificRuleModel(Base):
#     __tablename__ = 'scientific_rules'

#     id = Column(String(64), primary_key=True)
#     document_id = Column(String(64), index=True, nullable=False)
#     rule_statement = Column(Text, nullable=False)
#     context = Column(Text)
#     source_page = Column(Integer)

# class ProcedureModel(Base):
#     __tablename__ = 'procedures'

#     id = Column(String(64), primary_key=True)
#     document_id = Column(String(64), index=True, nullable=False)
#     procedure_name = Column(String(255), nullable=False)
#     steps = Column(JSON)
#     source_page = Column(Integer)





from sqlalchemy import Column, String, Integer, Text, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import relationship

# Import the Base we just created
from app.db.session import Base 

class KnowledgeNode(Base):
    __tablename__ = 'knowledge_nodes'

    id = Column(String(64), primary_key=True) 
    canonical_name = Column(String(255), unique=True, index=True, nullable=False)
    category = Column(String(100))
    definition = Column(Text)
    synonyms = Column(JSON)
    keywords = Column(JSON)
    
    attributes = relationship("NodeAttribute", back_populates="node", cascade="all, delete-orphan")
    provenances = relationship("NodeProvenance", back_populates="node", cascade="all, delete-orphan")

class NodeAttribute(Base):
    __tablename__ = 'node_attributes'

    id = Column(String(64), primary_key=True)
    node_id = Column(String(64), ForeignKey('knowledge_nodes.id', ondelete='CASCADE'))
    name = Column(String(255), nullable=False)
    value = Column(Text, nullable=False)

    __table_args__ = (UniqueConstraint('node_id', 'name', name='uq_node_attribute'),)
    node = relationship("KnowledgeNode", back_populates="attributes")

class NodeProvenance(Base):
    __tablename__ = 'node_provenances'

    id = Column(String(64), primary_key=True)
    node_id = Column(String(64), ForeignKey('knowledge_nodes.id', ondelete='CASCADE'))
    document_id = Column(String(64), index=True, nullable=False)
    source_page = Column(Integer)
    hierarchy_context = Column(Text)
    element_id = Column(String(128))
    section_path = Column(JSON)

    __table_args__ = (UniqueConstraint('node_id', 'document_id', 'element_id', 'source_page', name='uq_node_provenance'),)
    node = relationship("KnowledgeNode", back_populates="provenances")

class KnowledgeEdge(Base):
    __tablename__ = 'knowledge_edges'

    id = Column(String(64), primary_key=True)
    document_id = Column(String(64), index=True, nullable=False)
    source_node_id = Column(String(64), ForeignKey('knowledge_nodes.id', ondelete='CASCADE'))
    target_node_id = Column(String(64), ForeignKey('knowledge_nodes.id', ondelete='CASCADE'))
    relationship_type = Column(String(100), nullable=False)
    source_section = Column(Text)
    source_page = Column(Integer)

    __table_args__ = (UniqueConstraint('document_id', 'source_node_id', 'relationship_type', 'target_node_id', name='uq_knowledge_edge'),)

class ScientificRuleModel(Base):
    __tablename__ = 'scientific_rules'

    id = Column(String(64), primary_key=True)
    document_id = Column(String(64), index=True, nullable=False)
    rule_statement = Column(Text, nullable=False)
    context = Column(Text)
    source_page = Column(Integer)

class ProcedureModel(Base):
    __tablename__ = 'procedures'

    id = Column(String(64), primary_key=True)
    document_id = Column(String(64), index=True, nullable=False)
    procedure_name = Column(String(255), nullable=False)
    steps = Column(JSON)
    source_page = Column(Integer)