import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps } from "react";
import { I18nProvider } from "../i18n";
import { MediaRow } from "./MediaRow";

function renderRow(props: ComponentProps<typeof MediaRow>) {
  const { container } = render(
    <I18nProvider>
      <MediaRow {...props} />
    </I18nProvider>,
  );
  return container;
}

// jsdom has no media playback: play and pause only fire the events a browser would.
beforeEach(() => {
  localStorage.clear();
  vi.spyOn(HTMLMediaElement.prototype, "play").mockImplementation(function (this: HTMLMediaElement) {
    this.dispatchEvent(new Event("play"));
    return Promise.resolve();
  });
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(function (this: HTMLMediaElement) {
    this.dispatchEvent(new Event("pause"));
  });
});

afterEach(() => vi.restoreAllMocks());

describe("MediaRow", () => {
  it("downloads a file, shows its upload and tries a failed one again", async () => {
    const onDownload = vi.fn();
    const onRetry = vi.fn();
    const file = { kind: "file", name: "Tabela de franquias", ext: "xlsx", size: "248 KB", onDownload, onRetry } as const;
    const { rerender } = render(
      <I18nProvider>
        <MediaRow {...file} />
      </I18nProvider>,
    );

    expect(screen.getByText("Tabela de franquias")).toHaveTextContent("Tabela de franquias.xlsx");
    await userEvent.click(screen.getByRole("button", { name: "Baixar" }));

    rerender(
      <I18nProvider>
        <MediaRow {...file} progress={64} />
      </I18nProvider>,
    );
    expect(screen.getByText("Enviando… 64%")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();

    rerender(
      <I18nProvider>
        <MediaRow {...file} failed />
      </I18nProvider>,
    );
    expect(screen.getByText("Falhou")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Tentar de novo" }));

    expect(onDownload).toHaveBeenCalledOnce();
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("plays and pauses a video by click and Space, with its duration", async () => {
    const container = renderRow({ kind: "video", name: "Vistoria", ext: "mp4", src: "/v/vistoria.mp4" });
    const video = container.querySelector("video")!;
    Object.defineProperty(video, "duration", { value: 134 });
    fireEvent.loadedMetadata(video);

    expect(screen.getByText(/· 2:14/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Tocar" }));
    expect(screen.getByRole("button", { name: "Pausar" })).toHaveFocus();
    await userEvent.keyboard(" ");

    expect(screen.getByRole("button", { name: "Tocar" })).toBeInTheDocument();
    expect(HTMLMediaElement.prototype.play).toHaveBeenCalledOnce();
    expect(HTMLMediaElement.prototype.pause).toHaveBeenCalledOnce();
  });

  it("plays an audio and shows where it is", async () => {
    const container = renderRow({ kind: "audio", name: "Visita ao cliente", ext: "m4a", src: "/a/visita.m4a" });
    const audio = container.querySelector("audio")!;
    Object.defineProperty(audio, "duration", { value: 84 });
    fireEvent.loadedMetadata(audio);
    Object.defineProperty(audio, "currentTime", { value: 25 });
    fireEvent.timeUpdate(audio);

    expect(screen.getByText("0:25 / 1:24")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Tocar" }));

    expect(screen.getByRole("button", { name: "Pausar" })).toBeInTheDocument();
  });

  it("says when the file cannot be played", () => {
    const container = renderRow({ kind: "video", name: "Vistoria", ext: "mov", src: "/v/vistoria.mov" });

    fireEvent.error(container.querySelector("video")!);

    expect(screen.getByRole("alert")).toHaveTextContent("Não dá para tocar este arquivo aqui.");
    expect(screen.queryByRole("button", { name: "Tocar" })).not.toBeInTheDocument();
  });
});
