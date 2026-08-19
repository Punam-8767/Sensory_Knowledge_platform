# 🍽️ Sensory Knowledge Platform

AI-powered sensory knowledge platform that converts unstructured sensory documents into structured knowledge, validated relationships, and grounded answers.

This project is designed for research papers, ISO documents, scientific books, and sensory evaluation PDFs.

---

## 📌 Overview

The goal is not only to extract text from documents.

The main goal is to preserve:

* Document structure
* Page-level context
* Tables and figures
* Scientific concepts
* Sensory relationships
* Source provenance

Example relationship:

```text
Food → contains → Elaichi
Elaichi → has_attribute → Flavour
Flavour → has_intensity → Strong
```

---

## 🔄 Workflow

```text
Document Upload
→ PDF Processing
→ Structure Extraction
→ Knowledge Extraction
→ Normalization
→ Validation
→ MySQL Storage
→ Human Review
→ Qdrant Sync
→ Grounded Question Answering
```

---

## ✨ Key Features

* PDF upload and metadata extraction
* Text, table, and image extraction
* OCR fallback for scanned pages
* Chapter, section, topic, paragraph, table, and figure hierarchy extraction
* LLM-based sensory knowledge extraction
* Strict JSON and Pydantic validation
* Concept normalization and synonym mapping
* MySQL-based knowledge graph storage
* Qdrant-based semantic search
* Human review for new concepts
* Grounded Q&A with source/page reference

---

## 🛠️ Tech Stack

* **Backend:** Python, FastAPI
* **AI/LLM:** OpenAI, Prompt Engineering
* **Document Processing:** PyMuPDF, OCR, Table Extraction
* **Validation:** Pydantic
* **Database:** MySQL
* **Vector Database:** Qdrant
* **Tools:** Git, GitHub, Postman, VS Code

---

## ⚙️ How It Works

1. User uploads a sensory document.
2. System extracts text, tables, images, page numbers, and locations.
3. Document hierarchy is created using structure-aware processing.
4. LLM extracts concepts, sensory attributes, methods, scales, and relationships.
5. Extracted knowledge is validated and normalized.
6. Trusted concepts and relationships are stored in MySQL.
7. Approved concepts are synced with Qdrant for semantic search.
8. User questions are answered using verified MySQL knowledge and LLM.

---

## 🚀 Why Not Traditional RAG Only?

Traditional RAG mostly retrieves similar text chunks.

This platform preserves document structure and concept relationships before answering.

So instead of only searching text, it understands connected knowledge like:

```text
Food → contains → Ingredient → has_attribute → Sensory Property
```

This helps reduce hallucination and improves answer reliability.

---

## 🎯 Project Purpose

This platform helps convert sensory science documents into a searchable and validated knowledge system for:

* Sensory research
* Food product evaluation
* Knowledge extraction
* Questionnaire generation
* Concept discovery
* Grounded AI question answering

---

## 👩‍💻 Author

**Punam Surwase**

AI / GenAI Developer
Python | FastAPI | LLMs | Document AI | MySQL | Qdrant
