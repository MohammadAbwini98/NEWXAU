import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import type { DesktopSettings } from "../shared/contracts";

const DEFAULT_SETTINGS: DesktopSettings = {
  appearance: "system",
  sidebarCollapsed: false,
  lastRouteId: "dashboard",
  launchBackendOnStart: true
};

export class SettingsStore {
  private readonly filePath: string;
  private writeChain: Promise<void> = Promise.resolve();

  constructor(appDataRoot: string) {
    this.filePath = join(appDataRoot, "settings.json");
  }

  async get(): Promise<DesktopSettings> {
    try {
      const parsed = JSON.parse(await readFile(this.filePath, "utf8")) as Partial<DesktopSettings>;
      return { ...DEFAULT_SETTINGS, ...parsed };
    } catch {
      return { ...DEFAULT_SETTINGS };
    }
  }

  async update(patch: Partial<DesktopSettings>): Promise<DesktopSettings> {
    const next = { ...(await this.get()), ...patch };
    this.writeChain = this.writeChain.then(async () => {
      await mkdir(dirname(this.filePath), { recursive: true });
      const temporary = `${this.filePath}.tmp`;
      await writeFile(temporary, `${JSON.stringify(next, null, 2)}\n`, "utf8");
      await rename(temporary, this.filePath);
    });
    await this.writeChain;
    return next;
  }
}
