import { catalogs } from "./index";

const files = import.meta.glob<Record<string, unknown>>(["./*.ts", "!./index.ts", "!./*.test.ts"], { eager: true });

describe("i18n", () => {
  it("loads every file of the folder", () => {
    const names = Object.keys(files).map((path) => path.slice(2, -3));
    expect(Object.keys(catalogs).sort()).toEqual(names.sort());
    expect(names).toContain("app");
  });

  it.each(Object.entries(files))("%s has every key in both locales", (_path, mod) => {
    const ptBR = mod.ptBR as Record<string, string>;
    const en = mod.en as Record<string, string>;
    expect(Object.keys(en).sort()).toEqual(Object.keys(ptBR).sort());
    for (const text of [...Object.values(ptBR), ...Object.values(en)]) {
      expect(text.trim()).not.toBe("");
    }
  });
});
