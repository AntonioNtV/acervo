import type { Message } from "../../data/chat";
import type { Payload, Proposal } from "../../data/proposals";

export const T0 = "2026-10-22T10:00:00Z";

export function message(id: string, fields: Partial<Message> = {}): Message {
  return {
    id,
    conversation_id: "c-1",
    role: "acervo",
    status: "done",
    text: "",
    error: null,
    understood_as: null,
    created_at: T0,
    attachments: [],
    ...fields,
  };
}

export function proposal(payload: Payload, fields: Partial<Proposal> = {}): Proposal {
  return {
    id: "p-1",
    kb_id: "kb-1",
    agent_id: "agent-chat",
    conversation_id: "c-1",
    message_id: "r-1",
    kind: payload.kind,
    payload,
    edited_payload: null,
    alternatives: null,
    status: "pending",
    accepted_by: null,
    applied_at: null,
    reject_reason: null,
    created_at: T0,
    updated_at: T0,
    ...fields,
  };
}

export const append: Payload = {
  kind: "append",
  page_id: "page-1",
  path: "Porto Seguro/Residencial/Vistoria",
  base_version_id: "v-1",
  anchor: "como-agendar",
  heading: "Como agendar",
  op: "append",
  lines: ["- Por vídeo, para imóveis até 300 m²."],
};

export const conflict: Payload = {
  kind: "conflict",
  page_id: "page-1",
  path: "Bradesco/Residencial/Renovação e prazos",
  base_version_id: "v-1",
  anchor: "prazos",
  heading: "Prazos",
  current: "Até 60 dias após o vencimento.",
  new: "Até 45 dias, a partir de novembro.",
};

export const createPage: Payload = {
  kind: "create_page",
  parent_id: "residencial",
  parent_path: "Bradesco/Residencial",
  title: "Checklist de vistoria",
  markdown: "# Checklist de vistoria\n\n- Fotos das fachadas\n",
};

export const savePdf: Payload = {
  kind: "save_pdf",
  parent_id: "residencial",
  parent_path: "Bradesco/Residencial",
  name: "Condições Gerais 2026.pdf",
};

export const replacePdf: Payload = { kind: "replace_pdf", node_id: "file-1", path: "Bradesco/Auto/Tabela auto 2025.pdf" };

export const move: Payload = {
  kind: "move",
  node_id: "file-1",
  from_path: "Bradesco/Auto/Tabela auto 2025.pdf",
  parent_id: "arquivo",
  to_path: "Bradesco/Auto/Arquivo",
};

export const rename: Payload = { kind: "rename", node_id: "page-1", path: "Bradesco/Auto/Renov", title: "Renovação" };

export const undo: Payload = { kind: "undo", proposal_id: "p-0", path: "Porto Seguro/Residencial/Vistoria" };

export const staged = { name: "CG_Residencial_2026.pdf", sha256: "abc", size: 2_100_000, storage_key: "staged/kb-1/abc" };
