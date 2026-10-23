"""Whether a dropped PDF is a new version of one already in the folder it reached (skill `curator-agent`)."""

from acervo.core.settings import Thresholds
from acervo.domain.decisions import Noul
from acervo.model_clients.decider import Decider
from acervo.pipeline.curator.log import Decision, record
from acervo.pipeline.curator.options import label
from acervo.pipeline.curator.tree import SnapshotNode, TreeSnapshot

STEP = "pdf_check"


async def replaced_pdf(
    state: str,
    tree: TreeSnapshot,
    folder: SnapshotNode | None,
    decider: Decider,
    thresholds: Thresholds,
    log: list[Decision],
) -> SnapshotNode | None:
    """The PDF of the folder the new one replaces, or None; one Noul per PDF, all in one call."""
    pdfs = {
        f"new_version:{tree.path(node)}": node
        for node in tree.children(folder)
        if node.kind == "file" and node.title.lower().endswith(".pdf")
    }
    if not pdfs:
        return None
    answers = await decider.ask(
        state,
        [Noul(id=id, question=f"O PDF recebido é uma nova versão de {label(node)}?") for id, node in pdfs.items()],
    )
    likely = max(pdfs, key=lambda id: answers.p_yes(id))
    replaced = pdfs[likely] if answers.p_yes(likely) > thresholds.pdf_new_version else None
    for id in pdfs:
        action = "replace_pdf" if replaced is pdfs[id] else "not_a_version"
        log.append(record(answers, id, STEP, action, thresholds.pdf_new_version))
    return replaced
