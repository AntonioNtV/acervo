import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useI18n } from "../i18n";
import { Button } from "./Button";
import { Input } from "./Input";

/** The curated grid: the emoji, then its name and other words in pt-BR, then in English; a search matches either. */
const EMOJIS: Array<[string, string, string]> = [
  ["📄", "página, documento", "page, document"],
  ["📁", "pasta", "folder"],
  ["📂", "pasta aberta", "open folder"],
  ["🗂️", "divisórias, fichário", "dividers, index"],
  ["📚", "livros, biblioteca", "books, library"],
  ["📖", "livro aberto", "open book"],
  ["📒", "caderno", "notebook, ledger"],
  ["📝", "nota, anotação", "memo, note"],
  ["📌", "alfinete, fixar", "pin, pushpin"],
  ["📎", "clipe, anexo", "paperclip, attachment"],
  ["🔖", "marcador", "bookmark"],
  ["🏷️", "etiqueta", "label, tag"],
  ["📋", "prancheta, lista", "clipboard, list"],
  ["✅", "feito, concluído", "done, check"],
  ["☑️", "caixa marcada", "checkbox"],
  ["❗", "importante, exclamação", "important, exclamation"],
  ["❓", "pergunta, dúvida", "question"],
  ["⚠️", "atenção, aviso", "warning"],
  ["🚫", "proibido", "forbidden"],
  ["⭐", "estrela, favorito", "star, favorite"],
  ["✨", "brilho, novo", "sparkles, new"],
  ["🔥", "fogo, urgente", "fire, urgent"],
  ["💡", "ideia, lâmpada", "idea, bulb"],
  ["🎯", "alvo, meta", "target, goal"],
  ["🚀", "foguete, lançamento", "rocket, launch"],
  ["📅", "calendário, data", "calendar, date"],
  ["⏰", "despertador, prazo", "alarm, deadline"],
  ["⏳", "ampulheta, espera", "hourglass, waiting"],
  ["🕒", "relógio, hora", "clock, time"],
  ["📈", "gráfico em alta, crescimento", "chart going up, growth"],
  ["📉", "gráfico em queda", "chart going down"],
  ["📊", "gráfico de barras, relatório", "bar chart, report"],
  ["💰", "saco de dinheiro", "money bag"],
  ["💵", "cédula, nota dólar", "banknote, dollar"],
  ["💳", "cartão de crédito", "credit card"],
  ["🧾", "recibo, nota fiscal", "receipt, invoice"],
  ["🏦", "banco", "bank"],
  ["🏢", "empresa, prédio escritório", "office, building company"],
  ["🏠", "casa, residencial", "house, home"],
  ["🚗", "carro, automóvel", "car, automobile"],
  ["✈️", "avião, viagem", "airplane, travel"],
  ["🏥", "hospital, saúde", "hospital, health"],
  ["💊", "remédio, pílula", "pill, medicine"],
  ["🛡️", "escudo, proteção seguro", "shield, protection insurance"],
  ["⚖️", "balança, justiça jurídico", "scales, justice legal"],
  ["📜", "pergaminho, contrato", "scroll, contract"],
  ["✍️", "assinatura, escrever", "signature, writing"],
  ["🤝", "aperto de mão, acordo", "handshake, deal"],
  ["👥", "pessoas, equipe", "people, team"],
  ["👤", "pessoa, perfil", "person, profile"],
  ["💬", "conversa, balão", "speech, chat"],
  ["📞", "telefone", "telephone, phone"],
  ["📧", "e-mail, email correio", "email, mail"],
  ["📦", "pacote, caixa", "package, box"],
  ["🛒", "carrinho de compras", "shopping cart"],
  ["🔑", "chave, acesso", "key, access"],
  ["🔒", "cadeado, fechado", "lock, locked"],
  ["🔍", "lupa, busca", "magnifier, search"],
  ["⚙️", "engrenagem, configuração", "gear, settings"],
  ["🛠️", "ferramentas", "tools"],
  ["🔧", "chave inglesa", "wrench"],
  ["💻", "notebook, computador", "laptop, computer"],
  ["🖥️", "monitor, tela", "desktop computer, screen"],
  ["📱", "celular", "mobile phone"],
  ["🧪", "tubo de ensaio, teste", "test tube"],
  ["🧠", "cérebro, conhecimento", "brain, knowledge"],
  ["🎓", "formatura, curso", "graduation, course"],
  ["🌎", "mundo, terra", "world, earth globe"],
  ["🌱", "planta, broto", "seedling, plant"],
  ["🌳", "árvore", "tree"],
  ["☀️", "sol", "sun"],
  ["🌙", "lua", "moon"],
  ["⚡", "raio, energia", "lightning, energy"],
  ["❤️", "coração", "heart"],
  ["🎉", "festa, celebração", "party, celebration"],
  ["🎁", "presente", "gift, present"],
  ["🏆", "troféu", "trophy"],
  ["🍀", "trevo, sorte", "clover, luck"],
  ["☕", "café", "coffee"],
  ["🍎", "maçã", "apple"],
  ["🎨", "arte, paleta design", "art, palette design"],
  ["🎵", "música", "music"],
  ["📷", "câmera, foto", "camera, photo"],
  ["🧭", "bússola", "compass"],
  ["🗺️", "mapa", "map"],
  ["🧩", "peça de quebra-cabeça", "puzzle piece"],
  ["🔗", "link, corrente", "link, chain"],
  ["🗃️", "caixa de fichas, arquivo", "card file box"],
  ["🗄️", "gaveteiro, arquivo", "file cabinet"],
  ["🧮", "ábaco, cálculo", "abacus, calculation"],
  ["🔔", "sino, notificação", "bell, notification"],
  ["🟢", "círculo verde", "green circle"],
  ["🟡", "círculo amarelo", "yellow circle"],
  ["🔴", "círculo vermelho", "red circle"],
  ["🔵", "círculo azul", "blue circle"],
  ["⚫", "círculo preto", "black circle"],
];

function fold(text: string): string {
  return text.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
}

/** The emojis whose pt-BR or English words contain the query, accents and case aside; all of them for none. */
export function findEmojis(query: string): Array<[string, string, string]> {
  const folded = fold(query.trim());
  return folded ? EMOJIS.filter(([, pt, en]) => fold(`${pt} ${en}`).includes(folded)) : EMOJIS;
}

const WIDTH = 320;
const GAP = 4;

/**
 * The emoji picker as a small panel under its anchor: the caller renders it while open, inside the box that also holds
 * the button opening it. A click outside that box or Escape closes it; Enter picks the first match. Given a `query`,
 * the caller types (the editor after ":") and the picker shows no search field of its own.
 */
export function EmojiPicker({
  onPick,
  onRemove,
  onClose,
  query,
}: {
  onPick: (emoji: string) => void;
  /** Given when there is an icon to remove. */
  onRemove?: () => void;
  onClose: () => void;
  query?: string;
}) {
  const { t, lang } = useI18n();
  const [typed, setTyped] = useState("");
  const panel = useRef<HTMLDivElement>(null);
  const search = useRef<HTMLInputElement>(null);
  const [place, setPlace] = useState<{ left: number; top: number } | null>(null);
  const shown = findEmojis(query ?? typed);

  // Fixed under the anchor, so the sidebar's or a card's overflow never clips it.
  useLayoutEffect(() => {
    const box = panel.current?.parentElement?.getBoundingClientRect();
    if (!box) return;
    setPlace({ left: Math.max(GAP, Math.min(box.left, window.innerWidth - WIDTH - GAP)), top: box.bottom + GAP });
  }, []);

  useEffect(() => {
    // A menu that opened this hands focus back to its trigger as it closes; take it after that.
    const id = setTimeout(() => search.current?.focus());
    const outside = (event: PointerEvent) => {
      const anchor = panel.current?.parentElement;
      if (anchor && !anchor.contains(event.target as Node)) onClose();
    };
    document.addEventListener("pointerdown", outside);
    return () => {
      clearTimeout(id);
      document.removeEventListener("pointerdown", outside);
    };
  }, [onClose]);

  return (
    <div
      ref={panel}
      role="dialog"
      aria-label={t("page.icon.pick")}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.stopPropagation();
          onClose();
        }
      }}
      style={{ width: WIDTH, ...place }}
      className="fixed z-30 rounded-[8px] border border-line-2 bg-bg p-2"
    >
      {query === undefined && (
        <div className="flex items-center gap-1.5">
          <Input
            ref={search}
            type="search"
            aria-label={t("page.icon.search")}
            placeholder={t("page.icon.search")}
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && shown[0]) onPick(shown[0][0]);
            }}
          />
          {onRemove && (
            <Button variant="quiet" size="sm" onClick={onRemove}>
              {t("page.icon.remove")}
            </Button>
          )}
        </div>
      )}
      {shown.length === 0 ? (
        <p className="m-0 px-1 pt-2 text-13 text-text-3">{t("page.icon.none")}</p>
      ) : (
        <div className="mt-2 grid max-h-[232px] grid-cols-8 gap-0.5 overflow-y-auto">
          {shown.map(([emoji, pt, en]) => (
            <button
              key={emoji}
              type="button"
              aria-label={(lang === "en" ? en : pt).split(",")[0]}
              onClick={() => onPick(emoji)}
              className="flex size-9 cursor-pointer items-center justify-center rounded-[6px] border-0 bg-transparent p-0 text-20 hover:bg-subtle"
            >
              {emoji}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
