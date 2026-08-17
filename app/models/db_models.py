from sqlalchemy import Column, String, Integer, Text, Float, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class DocumentNode(Base):
    __tablename__ = 'knowledge_nodes'

    id = Column(String(50), primary_key=True)
    document_id = Column(String(50), index=True, nullable=False)
    canonical_name = Column(String(255), index=True, nullable=False)
    category = Column(String(100))
    definition = Column(Text)
    synonyms = Column(JSON)
    keywords = Column(JSON)
    hierarchy_context = Column(Text)
    source_page = Column(Integer)
    
    # Relationships to sub-nodes and edges
    attributes = relationship("NodeAttribute", back_populates="node", cascade="all, delete-orphan")
    edges_out = relationship("DocumentEdge", foreign_keys='DocumentEdge.source_node_id', back_populates="source_node", cascade="all, delete-orphan")
    edges_in = relationship("DocumentEdge", foreign_keys='DocumentEdge.target_node_id', back_populates="target_node", cascade="all, delete-orphan")

class NodeAttribute(Base):
    __tablename__ = 'node_attributes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    node_id = Column(String(50), ForeignKey('knowledge_nodes.id', ondelete='CASCADE'))
    document_id = Column(String(50), index=True)
    attribute_name = Column(String(255), nullable=False)
    attribute_value = Column(Text, nullable=False)

    node = relationship("DocumentNode", back_populates="attributes")

class DocumentEdge(Base):
    __tablename__ = 'knowledge_edges'

    id = Column(String(50), primary_key=True)
    document_id = Column(String(50), index=True, nullable=False)
    source_node_id = Column(String(50), ForeignKey('knowledge_nodes.id', ondelete='CASCADE'))
    target_node_id = Column(String(50), ForeignKey('knowledge_nodes.id', ondelete='CASCADE'))
    relationship_type = Column(String(100), nullable=False)
    source_section = Column(Text)

    source_node = relationship("DocumentNode", foreign_keys=[source_node_id], back_populates="edges_out")
    target_node = relationship("DocumentNode", foreign_keys=[target_node_id], back_populates="edges_in")



