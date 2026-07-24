import type { IpcMainInvokeEvent } from "electron";

export function assertTrustedSender(event: IpcMainInvokeEvent): void {
  const url = event.senderFrame?.url ?? event.sender.getURL();
  const devOrigin = process.env.ELECTRON_RENDERER_URL;
  if (url.startsWith("file://")) return;
  if (devOrigin && url.startsWith(devOrigin)) return;
  throw new Error(`Rejected IPC request from untrusted renderer: ${url || "unknown"}`);
}
