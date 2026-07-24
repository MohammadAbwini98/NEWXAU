import { safeStorage } from "electron";
import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";

const ALLOWED_SECRETS = new Set([
  "CAPITALCOM_API_KEY",
  "CAPITALCOM_IDENTIFIER",
  "CAPITALCOM_PASSWORD",
  "POSTGRES_DSN",
  "POSTGRES_SCHEMA",
  "TELEGRAM_BOT_TOKEN",
  "TELEGRAM_CHAT_ID"
]);

type SecretPayload = Record<string, string>;

export class SecretStore {
  private readonly filePath: string;
  private writeChain: Promise<void> = Promise.resolve();

  constructor(appDataRoot: string) {
    this.filePath = join(appDataRoot, "secrets.bin.json");
  }

  private assertAllowed(name: string): void {
    if (!ALLOWED_SECRETS.has(name)) throw new Error(`Unsupported secret name: ${name}`);
  }

  private async readPayload(): Promise<SecretPayload> {
    try {
      return JSON.parse(await readFile(this.filePath, "utf8")) as SecretPayload;
    } catch {
      return {};
    }
  }

  async status(): Promise<Record<string, boolean>> {
    const payload = await this.readPayload();
    return Object.fromEntries([...ALLOWED_SECRETS].map((name) => [name, Boolean(payload[name])]));
  }

  async set(name: string, value: string): Promise<void> {
    this.assertAllowed(name);
    if (!safeStorage.isEncryptionAvailable()) {
      throw new Error("Windows credential encryption is unavailable.");
    }
    const payload = await this.readPayload();
    payload[name] = safeStorage.encryptString(value).toString("base64");
    await this.persist(payload);
  }

  async remove(name: string): Promise<void> {
    this.assertAllowed(name);
    const payload = await this.readPayload();
    delete payload[name];
    await this.persist(payload);
  }

  async environment(): Promise<Record<string, string>> {
    if (!safeStorage.isEncryptionAvailable()) return {};
    const payload = await this.readPayload();
    const environment: Record<string, string> = {};
    for (const [name, encoded] of Object.entries(payload)) {
      if (!ALLOWED_SECRETS.has(name)) continue;
      try {
        environment[name] = safeStorage.decryptString(Buffer.from(encoded, "base64"));
      } catch {
        // A corrupt or foreign-user value is ignored; plaintext is never returned to the renderer.
      }
    }
    return environment;
  }

  private async persist(payload: SecretPayload): Promise<void> {
    this.writeChain = this.writeChain.then(async () => {
      await mkdir(dirname(this.filePath), { recursive: true });
      const temporary = `${this.filePath}.tmp`;
      await writeFile(temporary, `${JSON.stringify(payload, null, 2)}\n`, {
        encoding: "utf8",
        mode: 0o600
      });
      await rename(temporary, this.filePath);
    });
    await this.writeChain;
  }
}
