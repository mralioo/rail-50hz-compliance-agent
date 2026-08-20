import { KnowledgeBaseCard } from "../../src/components/knowledge/KnowledgeBaseCard";

export function Populated() {
  return <KnowledgeBaseCard kb={{ id: "db", name: "DB Ril 954.9101", doc_count: 42 }} />;
}

export function SingleDoc() {
  return <KnowledgeBaseCard kb={{ id: "vde", name: "VDE 0100-520", doc_count: 1 }} />;
}

export function Empty() {
  return <KnowledgeBaseCard kb={{ id: "general", name: "General Regulations", doc_count: 0 }} />;
}
