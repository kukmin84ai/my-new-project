"""Lightweight knowledge graph using file-based PropertyGraph for Bibliotheca AI.

Replaces Neo4j with a simpler file-based approach suitable for personal use.
Entity schema: Concept, Person, Theory, Method, Organization
Relationships: PROPOSES, CONTRADICTS, EXTENDS, PREREQUISITE_FOR, CITES
"""
import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from src.config import get_settings

logger = logging.getLogger("bibliotheca.graph")

# Entity Types
ENTITY_TYPES = ["Concept", "Person", "Theory", "Method", "Organization"]

# Relationship Types
RELATIONSHIP_TYPES = [
    "PROPOSES", "CONTRADICTS", "EXTENDS",
    "PREREQUISITE_FOR", "CITES", "RELATED_TO",
    "AUTHORED_BY", "PUBLISHED_IN",
]


@dataclass
class Entity:
    name: str
    entity_type: str
    description: str = ""
    source_book: str = ""
    properties: dict = field(default_factory=dict)


@dataclass
class Relationship:
    source: str
    target: str
    relationship_type: str
    weight: float = 1.0
    source_book: str = ""
    properties: dict = field(default_factory=dict)


@dataclass
class Triplet:
    subject: str
    predicate: str
    object: str
    source_file: str = ""
    source_chunk_id: str = ""
    confidence: float = 1.0


class KnowledgeGraph:
    """File-based knowledge graph store.

    Uses JSON file backend for simplicity. Can be upgraded to FalkorDB
    for larger datasets.
    """

    def __init__(self, store_dir: Optional[Path] = None, subject: str = "default"):
        settings = get_settings()
        base_dir = Path(store_dir) if store_dir else settings.graph_store_dir
        base_dir = Path(base_dir)

        # Migrate: move legacy root-level files to default/ subdirectory
        self._migrate_legacy(base_dir)

        self.store_dir = base_dir / subject
        self.store_dir.mkdir(parents=True, exist_ok=True)

        self.entities_file = self.store_dir / "entities.json"
        self.relationships_file = self.store_dir / "relationships.json"

        self.entities: dict[str, Entity] = {}
        self.relationships: list[Relationship] = []
        self._load()

    @staticmethod
    def _migrate_legacy(base_dir: Path) -> None:
        """Move legacy root-level graph files into default/ subdirectory."""
        legacy_entities = base_dir / "entities.json"
        legacy_rels = base_dir / "relationships.json"
        if legacy_entities.exists() or legacy_rels.exists():
            default_dir = base_dir / "default"
            default_dir.mkdir(parents=True, exist_ok=True)
            if legacy_entities.exists() and not (default_dir / "entities.json").exists():
                legacy_entities.rename(default_dir / "entities.json")
                logger.info("Migrated legacy entities.json to default/")
            if legacy_rels.exists() and not (default_dir / "relationships.json").exists():
                legacy_rels.rename(default_dir / "relationships.json")
                logger.info("Migrated legacy relationships.json to default/")

    def _load(self) -> None:
        """Load graph from disk."""
        if self.entities_file.exists():
            data = json.loads(self.entities_file.read_text(encoding="utf-8"))
            self.entities = {k: Entity(**v) for k, v in data.items()}
        if self.relationships_file.exists():
            data = json.loads(self.relationships_file.read_text(encoding="utf-8"))
            self.relationships = [Relationship(**r) for r in data]

    def _save(self) -> None:
        """Persist graph to disk."""
        self.entities_file.write_text(
            json.dumps(
                {k: asdict(v) for k, v in self.entities.items()},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.relationships_file.write_text(
            json.dumps(
                [asdict(r) for r in self.relationships],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def add_entity(self, entity: Entity) -> None:
        """Add or update an entity."""
        self.entities[entity.name] = entity
        self._save()
        logger.debug("Added entity: %s (%s)", entity.name, entity.entity_type)

    def add_relationship(self, rel: Relationship) -> None:
        """Add a relationship between entities."""
        if rel.relationship_type not in RELATIONSHIP_TYPES:
            logger.warning("Unknown relationship type: %s", rel.relationship_type)
        self.relationships.append(rel)
        self._save()

    def add_triplets(self, triplets: list[Triplet]) -> None:
        """Add triplets extracted from text. max_triplets handled by caller."""
        for t in triplets:
            # Auto-create entities if they don't exist
            if t.subject not in self.entities:
                self.entities[t.subject] = Entity(
                    name=t.subject,
                    entity_type="Concept",
                    source_book=t.source_file,
                )
            if t.object not in self.entities:
                self.entities[t.object] = Entity(
                    name=t.object,
                    entity_type="Concept",
                    source_book=t.source_file,
                )
            self.relationships.append(
                Relationship(
                    source=t.subject,
                    target=t.object,
                    relationship_type=t.predicate,
                    source_book=t.source_file,
                )
            )
        self._save()
        logger.info("Added %d triplets to knowledge graph", len(triplets))

    def search_entity(self, name: str) -> Optional[Entity]:
        """Find entity by exact or partial name match."""
        # Exact match
        if name in self.entities:
            return self.entities[name]
        # Partial match (case-insensitive)
        name_lower = name.lower()
        for key, entity in self.entities.items():
            if name_lower in key.lower():
                return entity
        return None

    def get_relationships(
        self,
        entity_name: str,
        relationship_type: Optional[str] = None,
    ) -> list[Relationship]:
        """Get all relationships for an entity."""
        results = []
        for rel in self.relationships:
            if rel.source == entity_name or rel.target == entity_name:
                if relationship_type is None or rel.relationship_type == relationship_type:
                    results.append(rel)
        return results

    def get_neighbors(self, entity_name: str, depth: int = 1) -> dict:
        """Get entity neighborhood up to given depth."""
        visited: set[str] = set()
        result: dict[str, list] = {"entities": [], "relationships": []}

        def _traverse(name: str, current_depth: int) -> None:
            if current_depth > depth or name in visited:
                return
            visited.add(name)
            if name in self.entities:
                result["entities"].append(self.entities[name])
            for rel in self.get_relationships(name):
                result["relationships"].append(rel)
                next_name = rel.target if rel.source == name else rel.source
                _traverse(next_name, current_depth + 1)

        _traverse(entity_name, 0)
        return result

    def get_stats(self) -> dict:
        """Return graph statistics."""
        return {
            "entity_count": len(self.entities),
            "relationship_count": len(self.relationships),
            "entity_types": {
                t: sum(1 for e in self.entities.values() if e.entity_type == t)
                for t in ENTITY_TYPES
            },
        }

    def remove_entity(self, name: str) -> bool:
        """Remove an entity and all its relationships."""
        if name not in self.entities:
            return False
        del self.entities[name]
        self.relationships = [
            r for r in self.relationships
            if r.source != name and r.target != name
        ]
        self._save()
        logger.info("Removed entity: %s", name)
        return True

    def clear(self) -> None:
        """Remove all entities and relationships."""
        self.entities.clear()
        self.relationships.clear()
        self._save()
        logger.info("Cleared knowledge graph")


def extract_triplets_prompt(text: str, max_triplets: int = 12) -> str:
    """Generate prompt for LLM-based triplet extraction.

    This returns a prompt string to send to Ollama for entity/relationship extraction.
    The caller handles the LLM call.
    """
    return f"""Extract knowledge graph triplets from the following academic text.

Entity types: {', '.join(ENTITY_TYPES)}
Relationship types: {', '.join(RELATIONSHIP_TYPES)}

Extract up to {max_triplets} triplets in JSON format:
[{{"subject": "...", "predicate": "...", "object": "..."}}]

Text:
{text[:3000]}

Triplets (JSON array only):"""


def parse_triplets_response(response_text: str, source_file: str = "", source_chunk_id: str = "") -> list[Triplet]:
    """Parse LLM response into Triplet objects.

    Attempts to extract a JSON array from the response text, handling
    common formatting issues like markdown code fences.
    """
    text = response_text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        # Try to find a JSON array in the text
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1:
            logger.warning("Could not parse triplets from LLM response")
            return []
        try:
            raw = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            logger.warning("Could not parse triplets from LLM response")
            return []

    triplets: list[Triplet] = []
    for item in raw:
        if isinstance(item, dict) and "subject" in item and "predicate" in item and "object" in item:
            triplets.append(
                Triplet(
                    subject=str(item["subject"]).strip(),
                    predicate=str(item["predicate"]).strip().upper(),
                    object=str(item["object"]).strip(),
                    source_file=source_file,
                    source_chunk_id=source_chunk_id,
                    confidence=float(item.get("confidence", 1.0)),
                )
            )
    return triplets
