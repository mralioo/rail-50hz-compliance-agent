import uuid

from app.domain.documents.models import Document


class DocumentFactory:
    """Domain factory responsible for minting new Document aggregates."""

    @staticmethod
    def create(project_id: str = "default_project") -> Document:
        return Document(id=str(uuid.uuid4()), project_id=project_id)
